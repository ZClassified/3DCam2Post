import os
import re
import datetime
import subprocess
import logging
import xml.etree.ElementTree as ET
from fractions import Fraction
from pathlib import Path

TC_PATTERN = re.compile(r"^\d{2}:\d{2}:\d{2}[:;.]\d{2}$")


def is_valid_tc(tc) -> bool:
    return bool(tc) and bool(TC_PATTERN.match(str(tc).strip()))


def _local(tag):
    return tag.split('}')[-1]


def find_child_dir(parent: Path, name: str):
    """Case-insensitive lookup of a sub directory (P2 cards use CLIP/clip/AUDIO/...)."""
    if not parent.exists():
        return None
    for folder in parent.iterdir():
        if folder.is_dir() and folder.name.upper() == name.upper():
            return folder
    return None


def find_p2_xml(vid_path) -> Path | None:
    vid_path = Path(vid_path)
    clip_dir = find_child_dir(vid_path.parent.parent, "CLIP")
    if not clip_dir:
        return None
    target = f"{vid_path.stem}.XML".upper()
    for f in clip_dir.iterdir():
        if f.name.upper() == target:
            return f
    return None


def read_p2_umid(vid_path):
    """GlobalClipID (UMID, 64 hex chars) from the P2 clip XML, or None."""
    try:
        xml = find_p2_xml(vid_path)
        if xml:
            for elem in ET.parse(xml).getroot().iter():
                if _local(elem.tag) == "GlobalClipID" and elem.text:
                    umid = elem.text.strip().upper()
                    return umid if len(umid) == 64 else None
    except Exception as e:
        logging.error(f"P2 UMID error for {vid_path}: {e}")
    return None


def umid_material(umid):
    """Material number part of a basic UMID – identical for the L and R clip of the 3DP1."""
    return umid[32:] if umid and len(umid) == 64 else None


class MetadataExtractor:
    def __init__(self, ffmpeg_path, is_windows):
        self.ffmpeg_path = ffmpeg_path
        self.is_windows = is_windows

    def extract(self, file_path):
        if Path(file_path).suffix.lower() == ".mxf":
            meta = self.extract_p2_metadata(file_path)
            # Fill gaps (e.g. missing XML) from ffmpeg
            if meta.get('duration_sec', 0) == 0 or not is_valid_tc(meta.get('start_tc')):
                ff = self.extract_ffmpeg_metadata(file_path)
                for k, v in ff.items():
                    if meta.get(k) in (None, '-', '', 0, 'N/A'):
                        meta[k] = v
            return meta
        return self.extract_ffmpeg_metadata(file_path)

    def extract_ffmpeg_metadata(self, file_path):
        meta = {'codec': '-', 'fps': '25', 'dur': '-', 'res': '-', 'bitrate': '',
                'start_tc': 'N/A', 'frames': 0, 'duration_sec': 0, 'start_sec': 0}

        if not self.ffmpeg_path or not os.path.exists(self.ffmpeg_path):
            return meta

        cmd = [self.ffmpeg_path, '-hide_banner', '-i', str(file_path)]
        try:
            c_flags = 0x08000000 if self.is_windows else 0
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    creationflags=c_flags, text=True, errors="replace")
            output = result.stderr

            dur_match = re.search(r"Duration:\s*(\d{1,2}:\d{2}:\d{2}\.\d{2})", output)
            start_match = re.search(r",\s*start:\s*([0-9.]+)", output)

            if start_match:
                meta['start_sec'] = float(start_match.group(1))

            if dur_match:
                meta['dur'] = dur_match.group(1)
                try:
                    h, m, s = meta['dur'].split(':')
                    meta['duration_sec'] = float(h) * 3600 + float(m) * 60 + float(s)
                except ValueError:
                    pass

            vid_match = re.search(r"Stream.*Video: (.*?),.*?, (\d{3,4}x\d{3,4}).*?, (\d+(?:\.\d+)?) fps", output)
            if vid_match:
                meta['codec'] = vid_match.group(1).split(' ')[0]
                meta['res'] = vid_match.group(2)
                meta['fps'] = vid_match.group(3)

                if meta['duration_sec'] > 0:
                    try:
                        meta['frames'] = int(meta['duration_sec'] * float(meta['fps']))
                        meta['duration_str'] = str(datetime.timedelta(seconds=int(meta['duration_sec'])))
                    except ValueError:
                        pass

            tc_match = re.search(r"timecode\s*:\s*(\d{2}:\d{2}:\d{2}[:;]\d{2})", output, re.IGNORECASE)
            if tc_match:
                meta['start_tc'] = tc_match.group(1)

        except Exception as e:
            logging.error(f"FFmpeg meta error: {e}")
        return meta

    def extract_p2_metadata(self, vid_path):
        meta = {'codec': '-', 'fps': '-', 'dur': '-', 'res': '-', 'bitrate': '',
                'start_tc': '-', 'duration_sec': 0, 'frames': 0}
        try:
            src_xml = find_p2_xml(vid_path)
            if not src_xml:
                return meta

            root = ET.parse(src_xml).getroot()

            # Prefer values inside the <Video> essence (audio has its own Codec/StartTimecode)
            video = next((e for e in root.iter() if _local(e.tag) == "Video"), None)
            scopes = [video, root] if video is not None else [root]

            def first(tag):
                for scope in scopes:
                    for elem in scope.iter():
                        if _local(elem.tag) == tag and elem.text:
                            return elem
                return None

            codec = first("Codec")
            if codec is not None:
                meta['codec'] = codec.text
                if codec.attrib.get('Class'):
                    meta['bitrate'] = f"({codec.attrib['Class']} Mbit)"
            for tag, key in (("FrameRate", "fps"), ("VideoFormat", "res"), ("StartTimecode", "start_tc")):
                e = first(tag)
                if e is not None:
                    meta[key] = e.text.strip()

            dur = first("Duration")
            unit = first("EditUnit")
            if dur is not None:
                frames = int(dur.text)
                meta['frames'] = frames
                seconds = None
                if unit is not None and '/' in unit.text:
                    seconds = float(frames * Fraction(unit.text.strip()))
                elif meta['fps'] != '-':
                    seconds = frames / float(re.sub(r"[^0-9.]", "", meta['fps']))
                if seconds:
                    meta['duration_sec'] = seconds
                    meta['duration_str'] = str(datetime.timedelta(seconds=int(seconds)))
        except Exception as e:
            logging.error(f"P2 meta error for {vid_path}: {e}")
        return meta
