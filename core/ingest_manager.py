import os
import re
import csv
import json
import time
import copy
import hashlib
import logging
import datetime
import threading
import xml.etree.ElementTree as ET
from pathlib import Path

from core.metadata import MetadataExtractor, find_child_dir, find_p2_xml, is_valid_tc
from core.reporting import ReportGenerator

try:
    import xxhash
    HAS_XXHASH = True
except ImportError:
    HAS_XXHASH = False

VIDEO_DIRS = {"VIDEO", "STREAM"}
CHUNK_SIZE = 8 * 1024 * 1024  # 8 MB
PROGRESS_INTERVAL = 0.1  # seconds between progress callbacks
RESOLVE_CSV = "Resolve_Timecode_Import.csv"


def eye_dir(eye):
    return "LINKS" if eye == "L" else "RECHTS"


def build_name(settings, project, scene, setting, take, cam_id=""):
    name = (f"{project}"
            f"_S{str(scene).zfill(int(settings.get('padding_s', 2)))}"
            f"_E{str(setting).zfill(int(settings.get('padding_e', 2)))}"
            f"_T{str(take).zfill(int(settings.get('padding_t', 3)))}")
    if settings.get("use_cam_id") and cam_id:
        name += f"_{cam_id}"
    return name


def new_hasher(algo):
    if algo == "sha256":
        return hashlib.sha256()
    if algo == "xxhash" and HAS_XXHASH:
        return xxhash.xxh64()
    return hashlib.md5()


def hash_file(path, algo):
    h = new_hasher(algo)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK_SIZE), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json_atomic(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    os.replace(tmp, path)


class IngestManager:
    def __init__(self, settings, temp_thumb_dir, ffmpeg_path, is_windows, callbacks=None):
        """
        callbacks (all optional, called from the worker thread):
            on_status(msg)
            on_total_progress(pct, mb_per_sec, eta_sec)
            on_clip_start(key)
            on_clip_done(key, manifest_entry, failed_eyes)
            on_error(msg)
        """
        self.settings = settings
        self.callbacks = callbacks or {}
        self.cancel_event = threading.Event()

        self.metadata = MetadataExtractor(ffmpeg_path, is_windows)
        self.reporting = ReportGenerator(temp_thumb_dir, ffmpeg_path, is_windows)

        self._total_bytes = 0
        self._done_bytes = 0
        self._start_time = 0.0
        self._last_progress = 0.0

    def _cb(self, name, *args):
        fn = self.callbacks.get(name)
        if fn:
            try:
                fn(*args)
            except Exception as e:
                logging.error(f"Callback {name} failed: {e}", exc_info=True)

    def status(self, msg):
        self._cb('on_status', msg)

    # ------------------------------------------------------------------ scan
    def scan_folder(self, root_path):
        found = []
        for root, dirs, files in os.walk(Path(root_path)):
            if Path(root).name.upper() not in VIDEO_DIRS:
                continue
            for f in files:
                f_lower = f.lower()
                if not f_lower.endswith(('.mts', '.mxf')):
                    continue
                m = re.match(r'^([23])(\w+)\.', f, re.IGNORECASE)
                if not m:
                    continue
                p = Path(root) / f
                found.append({
                    'p': str(p),
                    'id': m.group(2),
                    'e': "L" if m.group(1) == "2" else "R",
                    'cam': "3DA1" if f_lower.endswith('.mts') else "3DP1",
                    's': p.stat().st_size,
                })
        return found

    # ------------------------------------------------------------------ plan
    @staticmethod
    def find_p2_audio(vid_path):
        vid_path = Path(vid_path)
        audio_dir = find_child_dir(vid_path.parent.parent, "AUDIO")
        if not audio_dir:
            return []
        pat = re.compile(rf"^{re.escape(vid_path.stem)}(\d{{2}})\.MXF$", re.IGNORECASE)
        tracks = []
        for f in audio_dir.iterdir():
            m = pat.match(f.name)
            if m:
                tracks.append((int(m.group(1)), f))
        return [f for _, f in sorted(tracks)]

    def _wants_audio(self, eye):
        if not self.settings.get("copy_audio", True):
            return False
        src = self.settings.get("audio_source", "Links")
        if src in ("Links", "Left"):
            return eye == "L"
        if src in ("Rechts", "Right"):
            return eye == "R"
        return True

    def plan_clip(self, clip, clip_root: Path, bn: str):
        """Returns a list of per-eye copy plans for a clip (only eyes whose source exists)."""
        plans = []
        for eye in ('L', 'R'):
            src = clip.get(f'path_{eye}')
            if not src or not Path(src).exists():
                continue
            src = Path(src)
            is_p2 = src.suffix.lower() == '.mxf'
            if is_p2:
                dest_folder = clip_root / eye_dir(eye) / "CONTENTS"
                video_dst = dest_folder / "VIDEO" / f"{bn}_{eye}{src.suffix}"
            else:
                dest_folder = clip_root / eye_dir(eye)
                video_dst = dest_folder / f"{bn}_{eye}{src.suffix}"

            audio = []
            if is_p2 and self._wants_audio(eye):
                for a in self.find_p2_audio(src):
                    suffix = a.stem[-2:]
                    name = f"{bn}_{suffix}.MXF" if self.settings.get("strip_audio_eye") else f"{bn}_{eye}{suffix}.MXF"
                    audio.append((a, dest_folder / "AUDIO" / name))

            xml_src = find_p2_xml(src) if is_p2 else None
            xml_dst = dest_folder / "CLIP" / f"{bn}_{eye}.XML" if is_p2 else None

            plans.append({
                'eye': eye, 'src': src, 'is_p2': is_p2, 'dest_folder': dest_folder,
                'video_dst': video_dst, 'audio': audio, 'xml_src': xml_src, 'xml_dst': xml_dst,
            })
        return plans

    @staticmethod
    def plan_bytes(plans):
        total = 0
        for p in plans:
            total += p['src'].stat().st_size
            total += sum(a.stat().st_size for a, _ in p['audio'])
        return total

    @staticmethod
    def plan_targets(plans):
        out = []
        for p in plans:
            out.append(p['video_dst'])
            out.extend(dst for _, dst in p['audio'])
            if p['xml_dst']:
                out.append(p['xml_dst'])
        return out

    # ------------------------------------------------------------------ copy
    def _progress(self, force=False):
        now = time.time()
        if not force and now - self._last_progress < PROGRESS_INTERVAL:
            return
        self._last_progress = now
        elapsed = now - self._start_time
        if elapsed <= 0 or not self._total_bytes:
            return
        speed = self._done_bytes / elapsed
        pct = min(100.0, self._done_bytes / self._total_bytes * 100)
        eta = max(0.0, (self._total_bytes - self._done_bytes) / speed) if speed > 0 else 0
        self._cb('on_total_progress', pct, speed / (1024 * 1024), eta)

    def _copy_file(self, src: Path, dst: Path):
        """Copy with optional inline hashing. Returns (ok, hash_or_None, error_or_None)."""
        verify = self.settings.get("verify_copy", False)
        algo = self.settings.get("hash_algo", "md5")
        src_size = src.stat().st_size
        copied = 0
        hasher = new_hasher(algo) if verify else None

        def fail(msg):
            self._done_bytes += src_size - copied
            try:
                if dst.exists():
                    dst.unlink()
            except OSError:
                pass
            return False, None, msg

        if self.cancel_event.is_set():
            return False, None, None

        self.status(f"{src.name} → {dst.name}")
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            with open(src, 'rb') as fsrc, open(dst, 'wb') as fdst:
                while True:
                    if self.cancel_event.is_set():
                        break
                    chunk = fsrc.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    if hasher:
                        hasher.update(chunk)
                    fdst.write(chunk)
                    copied += len(chunk)
                    self._done_bytes += len(chunk)
                    self._progress()
                if verify:
                    fdst.flush()
                    os.fsync(fdst.fileno())

            if self.cancel_event.is_set():
                fail(None)
                return False, None, None

            if dst.stat().st_size != src_size:
                return fail(f"Size mismatch: {src.name}")

            if verify:
                self.status(f"Verify {algo.upper()}: {dst.name}")
                src_hash = hasher.hexdigest()
                dst_hash = hash_file(dst, algo)
                if src_hash != dst_hash:
                    return fail(f"Checksum mismatch: {dst.name}")
                return True, dst_hash, None
            return True, None, None
        except Exception as e:
            logging.error(f"Copy Error {src} -> {dst}: {e}", exc_info=True)
            return fail(f"{src.name}: {e}")

    def _write_p2_xml(self, xml_src: Path, xml_dst: Path, new_name: str):
        tree = ET.parse(xml_src)
        for elem in tree.getroot().iter():
            if elem.tag.split('}')[-1] in ('ClipName', 'UserClipName'):
                elem.text = new_name
        xml_dst.parent.mkdir(parents=True, exist_ok=True)
        tree.write(xml_dst, encoding='UTF-8', xml_declaration=True)

    # ------------------------------------------------------------------ csv
    def update_resolve_csv(self, log_data, dest_folder: Path):
        """Merges new timecodes into the project's Resolve CSV (keeps entries from earlier days)."""
        new = {i['file']: i['start_tc'] for i in log_data
               if i.get('type') == 'video' and is_valid_tc(i.get('start_tc'))}
        if not new:
            return None
        csv_path = Path(dest_folder) / RESOLVE_CSV
        rows = {}
        if csv_path.exists():
            try:
                with open(csv_path, newline='', encoding='utf-8') as f:
                    for r in csv.DictReader(f):
                        if r.get('File Name'):
                            rows[r['File Name']] = r.get('Start TC', '')
            except Exception as e:
                logging.error(f"Reading existing Resolve CSV failed: {e}")
        rows.update(new)
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['File Name', 'Start TC'])
            for name in sorted(rows):
                w.writerow([name, rows[name]])
        return csv_path

    # ------------------------------------------------------------------ run
    def run_ingest(self, jobs, project_name, base_target: Path, manifest_data, manifest_path: Path | None):
        """
        jobs: list of dicts {'key', 'clip', 'bn', 'plans'} (plans from plan_clip).
        Returns a result dict with manifest, errors, warnings, files, reports.
        """
        self.cancel_event.clear()
        manifest = copy.deepcopy(manifest_data)
        algo = self.settings.get('hash_algo', 'md5')
        verify = self.settings.get("verify_copy", False)
        result = {'manifest': manifest, 'errors': [], 'warnings': [], 'files': [],
                  'clips_ok': 0, 'clips_failed': 0, 'cancelled': False,
                  'html_report': None, 'mhl': None, 'csv': None, 'bytes': 0}

        self._total_bytes = sum(self.plan_bytes(j['plans']) for j in jobs)
        self._done_bytes = 0
        self._start_time = time.time()

        for job in jobs:
            if self.cancel_event.is_set():
                break
            key, clip, bn = job['key'], job['clip'], job['bn']
            self._cb('on_clip_start', key)

            entry = manifest.setdefault(key, {"status_L": "missing", "status_R": "missing"})
            entry.update({
                "target_name": bn, "scene": clip['scene'], "setting": clip['setting'],
                "take": clip['take'], "cam_id": clip.get('cam_id', ''), "clip_id": clip['id'],
            })
            failed_eyes = []

            for plan in job['plans']:
                if self.cancel_event.is_set():
                    break
                eye, src = plan['eye'], plan['src']
                ok, v_hash, err = self._copy_file(src, plan['video_dst'])
                if not ok:
                    if err:
                        result['errors'].append(err)
                        self._cb('on_error', err)
                        failed_eyes.append(eye)
                        entry[f"status_{eye}"] = "failed"
                    continue

                eye_ok = True
                meta = self.metadata.extract(src)
                thumbs = []
                if verify and self.settings.get("generate_thumbs", True) and eye == job['plans'][0]['eye']:
                    self.status(f"Thumbnails: {plan['video_dst'].name}")
                    thumbs = self.reporting.create_report_thumbnails(
                        plan['video_dst'], meta.get('duration_sec'))

                result['files'].append({
                    'name': plan['video_dst'].name, 'file': plan['video_dst'].name,
                    'path': str(plan['video_dst']), 'hash': v_hash or "N/A", 'algo': algo,
                    'size': plan['video_dst'].stat().st_size, 'type': 'video',
                    'clip_id': key, 'eye': eye, 'meta': meta, 'base_name': bn,
                    'original_name': src.name, 'start_tc': meta.get('start_tc'), 'thumbs': thumbs,
                })

                if plan['is_p2']:
                    if plan['xml_src']:
                        try:
                            self._write_p2_xml(plan['xml_src'], plan['xml_dst'], f"{bn}_{eye}")
                            result['files'].append({
                                'path': str(plan['xml_dst']), 'type': 'xml', 'algo': algo,
                                'hash': hash_file(plan['xml_dst'], algo) if verify else "N/A",
                                'size': plan['xml_dst'].stat().st_size,
                            })
                        except Exception as e:
                            logging.error(f"XML error {plan['xml_src']}: {e}", exc_info=True)
                            result['warnings'].append(f"XML {src.name}: {e}")
                    else:
                        result['warnings'].append(f"{src.name}: P2 XML missing")

                    if self._wants_audio(eye):
                        if len(plan['audio']) < 4:
                            result['warnings'].append(
                                f"{src.name}: {len(plan['audio'])}/4 audio tracks found")
                        for a_src, a_dst in plan['audio']:
                            a_ok, a_hash, a_err = self._copy_file(a_src, a_dst)
                            if not a_ok:
                                eye_ok = False
                                if a_err:
                                    result['errors'].append(a_err)
                                    self._cb('on_error', a_err)
                                break
                            result['files'].append({
                                'path': str(a_dst), 'hash': a_hash or "N/A", 'algo': algo,
                                'size': a_dst.stat().st_size, 'type': 'audio',
                            })

                if self.cancel_event.is_set() and not eye_ok:
                    break
                if eye_ok:
                    entry[f"status_{eye}"] = "done"
                    entry[f"src_{eye}"] = {"name": src.name, "size": src.stat().st_size}
                else:
                    entry[f"status_{eye}"] = "failed"
                    failed_eyes.append(eye)

            entry["updated"] = datetime.datetime.now().isoformat(timespec="seconds")
            if manifest_path:
                try:
                    write_json_atomic(manifest_path, manifest)
                except Exception as e:
                    result['errors'].append(f"Manifest: {e}")

            if failed_eyes:
                result['clips_failed'] += 1
            elif not self.cancel_event.is_set():
                result['clips_ok'] += 1
            self._cb('on_clip_done', key, copy.deepcopy(entry), failed_eyes)

        self._progress(force=True)
        result['cancelled'] = self.cancel_event.is_set()
        result['bytes'] = self._done_bytes

        if verify and result['files']:
            self.status("Reports…")
            try:
                result['mhl'], result['html_report'] = self.reporting.generate_reports(
                    project_name, result['files'], base_target, result['errors'])
            except Exception as e:
                logging.error(f"Report error: {e}", exc_info=True)
                result['errors'].append(f"Report: {e}")

        try:
            result['csv'] = self.update_resolve_csv(result['files'], base_target)
        except Exception as e:
            logging.error(f"Resolve CSV error: {e}", exc_info=True)
            result['errors'].append(f"Resolve CSV: {e}")

        return result
