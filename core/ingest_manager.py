import os
import shutil
import re
import csv
import time
import logging
import threading
from pathlib import Path
import xml.etree.ElementTree as ET

from core.metadata import MetadataExtractor
from core.reporting import ReportGenerator

logging.basicConfig(
    filename='3dcam2post.log', 
    level=logging.ERROR, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class IngestManager:
    def __init__(self, settings, temp_thumb_dir, ffmpeg_path, is_windows, callbacks):
        """
        callbacks is a dict:
        {
            'on_status': func(msg),
            'on_progress': func(item_id, pct),
            'on_total_progress': func(pct, mb_per_sec, eta_sec),
            'on_clip_start': func(item_id),
            'on_clip_done': func(item_id, status_str),
            'on_error': func(msg)
        }
        """
        self.settings = settings
        self.callbacks = callbacks
        self.cancel_event = threading.Event()
        
        self.metadata = MetadataExtractor(ffmpeg_path, is_windows)
        self.reporting = ReportGenerator(temp_thumb_dir, ffmpeg_path, is_windows)

    def status(self, msg):
        if 'on_status' in self.callbacks:
            self.callbacks['on_status'](msg)

    def scan_folder(self, root_path):
        found = []
        root_path = Path(root_path)
        for root, dirs, files in os.walk(root_path):
            d_name = Path(root).name.upper()
            if d_name not in ["VIDEO", "STREAM"]: continue
            
            for f in files:
                f_lower = f.lower()
                if f_lower.endswith(('.mts', '.mxf')):
                    m = re.match(r'^([23])(\w+)\.', f, re.IGNORECASE)
                    if m:
                        eye_code = m.group(1)
                        is_mts = f_lower.endswith('.mts')
                        item = {
                            'p': str(Path(root) / f),
                            'id': m.group(2),
                            'e': "L" if eye_code == "2" else "R",
                            'cam': "3DA1" if is_mts else "3DP1",
                            's': (Path(root) / f).stat().st_size
                        }
                        found.append(item)
        return found

    def process_xml_p2(self, src_video, new_name, clip_folder, eye):
        try:
            src_video = Path(src_video)
            parent_dir = src_video.parent.parent
            clip_dir_path = None
            if parent_dir.exists():
                for folder in parent_dir.iterdir():
                    if folder.name.upper() == "CLIP":
                        clip_dir_path = folder
                        break
            if not clip_dir_path: return None

            src_xml = None
            target_xml_name = f"{src_video.stem}.xml".upper()
            for f in clip_dir_path.iterdir():
                if f.name.upper() == target_xml_name:
                    src_xml = f
                    break
            if not src_xml: return None

            tree = ET.parse(src_xml)
            root = tree.getroot()
            for elem in root.iter():
                tag_local = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
                if tag_local in ['ClipName', 'UserClipName']: elem.text = f"{new_name}_{eye}"
            
            dst_xml = Path(clip_folder) / f"{new_name}_{eye}.XML"
            tree.write(dst_xml, encoding='UTF-8', xml_declaration=True)
            return dst_xml
        except Exception as e: 
            logging.error(f"Error processing XML for {src_video}: {e}", exc_info=True)
            return None

    def copy_audio_p2(self, vid_path, bn, eye, dst):
        copied_files = []
        try:
            vid_path = Path(vid_path)
            parent_dir = vid_path.parent.parent
            audio_src_dir = None
            if parent_dir.exists():
                for folder in parent_dir.iterdir():
                    if folder.name.upper() == "AUDIO":
                        audio_src_dir = folder
                        break
            if not audio_src_dir: return []

            raw_base = vid_path.stem
            found_audio_tracks = 0
            for t in range(4):
                search_name = f"{raw_base}{t:02d}.MXF".upper()
                for f in audio_src_dir.iterdir():
                    if f.name.upper() == search_name:
                        found_audio_tracks += 1
                        suffix = f"{t:02d}"
                        final_name = f"{bn}_{suffix}.MXF" if self.settings["strip_audio_eye"] else f"{bn}_{eye}{suffix}.MXF"
                        target = Path(dst) / final_name
                        if self._chunked_copy(f, target):
                            copied_files.append(target)
                        
            if found_audio_tracks < 4:
                logging.error(f"P2 Audio Missing Alert: Found only {found_audio_tracks} tracks for {vid_path.name}")
                
        except Exception as e: 
            logging.error(f"Error copying audio for {vid_path}: {e}", exc_info=True)
        return copied_files

    def _chunked_copy(self, src, dst, update_global=True):
        if self.cancel_event.is_set():
            return None
            
        try:
            algo = self.settings.get("hash_algo", "md5")
            src_hash = None
            if self.settings["verify_copy"]:
                self.status(f"Prüfe Quelle ({algo.upper()}): {src.name}...")
                src_hash = self.reporting.generate_checksum(src, algo)

            self.status(f"Kopiere: {src.name}...")
            
            src_size = src.stat().st_size
            copied = 0
            chunk_size = 8 * 1024 * 1024  # 8 MB
            
            with open(src, 'rb') as fsrc, open(dst, 'wb') as fdst:
                while True:
                    if self.cancel_event.is_set():
                        break
                    chunk = fsrc.read(chunk_size)
                    if not chunk:
                        break
                    fdst.write(chunk)
                    copied += len(chunk)
                    
                    if update_global and hasattr(self, 'global_bytes_copied'):
                        self.global_bytes_copied += len(chunk)
                        
                        now = time.time()
                        elapsed = now - self.global_start_time
                        if elapsed > 0:
                            mb_per_sec = (self.global_bytes_copied / elapsed) / (1024*1024)
                            pct = (self.global_bytes_copied / self.global_total_bytes) * 100 if self.global_total_bytes else 0
                            remaining_bytes = self.global_total_bytes - self.global_bytes_copied
                            eta_sec = remaining_bytes / (self.global_bytes_copied / elapsed) if self.global_bytes_copied > 0 else 0
                            
                            if 'on_total_progress' in self.callbacks:
                                self.callbacks['on_total_progress'](pct, mb_per_sec, eta_sec)

            if self.cancel_event.is_set():
                if dst.exists():
                    os.remove(dst)
                return None

            if src.stat().st_size != dst.stat().st_size:
                raise IOError(f"Größenfehler: {src.name}")

            if self.settings["verify_copy"] and src_hash:
                self.status(f"Verifiziere Ziel ({algo.upper()}): {dst.name}...")
                dst_hash = self.reporting.generate_checksum(dst, algo)
                if src_hash != dst_hash:
                    raise IOError(f"CHECKSUM ERROR bei {dst.name}")
                return dst_hash
            return "ok" # Fallback if no hash needed, but we need something truthy

        except Exception as e:
            logging.error(f"Copy Error {src} -> {dst}: {e}", exc_info=True)
            if 'on_error' in self.callbacks:
                self.callbacks['on_error'](f"Copy Error {src.name}: {e}")
            return None

    def generate_resolve_csv(self, log_data, dest_folder):
        try:
            csv_path = dest_folder / "Resolve_Timecode_Import.csv"
            tc_map = {}
            for item in log_data:
                file_name = item.get('file')
                start_tc = item.get('start_tc')
                if file_name and start_tc and start_tc != "00:00:00:00" and start_tc != "":
                    tc_map[file_name] = start_tc
            
            if not tc_map: return

            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['File Name', 'Start TC'])
                for fname, tc in tc_map.items():
                    writer.writerow([fname, tc])
        except Exception as e:
            logging.error(f"Resolve CSV Fehler: {e}", exc_info=True)
            if 'on_error' in self.callbacks:
                self.callbacks['on_error'](f"Resolve CSV Fehler: {e}")

    def run_ingest(self, clips_data, project_name, current_root_func, get_target_name_func, base_target, report_dir, manifest_data):
        total_clips = len(clips_data)
        processed_files_log = []
        self.cancel_event.clear()
        
        # Calculate total transfer size for global progress
        self.global_total_bytes = sum(c[0]['size_bytes'] for c in clips_data)
        self.global_bytes_copied = 0
        self.global_start_time = time.time()
        
        for i, (clip, item_id) in enumerate(clips_data):
            if self.cancel_event.is_set():
                break
                
            if 'on_clip_start' in self.callbacks:
                self.callbacks['on_clip_start'](item_id)
            
            current_root = current_root_func(clip)
            bn = get_target_name_func(clip)
            cid = clip['id']
            
            if cid not in manifest_data:
                manifest_data[cid] = {
                    "target_name": bn,
                    "scene": clip['scene'], "setting": clip['setting'], "take": clip['take'],
                    "status_L": "missing", "status_R": "missing"
                }

            for eye in ['L', 'R']:
                if self.cancel_event.is_set(): break
                
                src = clip[f'path_{eye}']
                if src and Path(src).exists():
                    src_path = Path(src)
                    is_p2 = src_path.suffix.lower() == '.mxf'
                    
                    if is_p2:
                        dest_folder = current_root / ("LINKS" if eye == "L" else "RECHTS") / "CONTENTS"
                        for d in ["VIDEO", "CLIP", "AUDIO"]: (dest_folder/d).mkdir(parents=True, exist_ok=True)
                        target_video = dest_folder / "VIDEO" / f"{bn}_{eye}{src_path.suffix}"
                    else:
                        dest_folder = current_root / ("LINKS" if eye == "L" else "RECHTS")
                        dest_folder.mkdir(parents=True, exist_ok=True)
                        target_video = dest_folder / f"{bn}_{eye}{src_path.suffix}"

                    v_hash = self._chunked_copy(src_path, target_video)
                    
                    if self.cancel_event.is_set(): break
                    
                    if is_p2:
                        meta_data = self.metadata.extract_p2_metadata(src_path)
                    else:
                        meta_data = self.metadata.extract_ffmpeg_metadata(src_path)
                    
                    if self.settings.get("verify_copy", False) and self.settings.get("generate_thumbs", True):
                        self.reporting.create_report_thumbnails(
                            target_video, cid, meta_data.get('duration_sec'), 
                            meta_data.get('fps'), meta_data.get('start_sec', 0)
                        )

                    if v_hash:
                        processed_files_log.append({
                            'name': target_video.name, 'path': str(target_video),
                            'hash': v_hash if v_hash != "ok" else "N/A", 
                            'algo': self.settings.get('hash_algo', 'md5'),
                            'size': target_video.stat().st_size, 'type': 'video',
                            'clip_id': cid, 'eye': eye, 'meta': meta_data,
                            'original_name': src_path.name,
                            'file': target_video.name, 'start_tc': meta_data.get('start_tc')
                        })

                    if is_p2:
                        xml_target = self.process_xml_p2(src_path, bn, dest_folder/"CLIP", eye)
                        if xml_target and v_hash:
                             xh = self.reporting.generate_checksum(xml_target, self.settings.get('hash_algo', 'md5'))
                             processed_files_log.append({
                                'path': str(xml_target), 'hash': xh, 'algo': self.settings.get('hash_algo', 'md5'),
                                'size': xml_target.stat().st_size, 'type': 'xml'
                            })

                    if is_p2 and self.settings.get("copy_audio", True): 
                        audio_files = self.copy_audio_p2(src_path, bn, eye, dest_folder/"AUDIO")
                        for af in audio_files:
                             if v_hash:
                                ah = self.reporting.generate_checksum(af, self.settings.get('hash_algo', 'md5'))
                                processed_files_log.append({
                                    'path': str(af), 'hash': ah, 'algo': self.settings.get('hash_algo', 'md5'),
                                    'size': af.stat().st_size, 'type': 'audio'
                                })
                    
                    manifest_data[cid][f"status_{eye}"] = "done"

            if not self.cancel_event.is_set():
                clip['done'] = True
                if 'on_clip_done' in self.callbacks:
                    self.callbacks['on_clip_done'](item_id, manifest_data)
                if 'on_progress' in self.callbacks:
                    self.callbacks['on_progress'](item_id, 100)
            
        if self.settings.get("verify_copy", False) and not self.cancel_event.is_set():
            self.reporting.generate_reports(project_name, processed_files_log, report_dir)

        if not self.cancel_event.is_set():
            self.generate_resolve_csv(processed_files_log, base_target)
        
        return manifest_data, processed_files_log
