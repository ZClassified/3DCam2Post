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


def pair_key(recid):
    """
    Part of a recording identifier that is identical for both eyes:
    P2 UMID -> material number, AVCHD "AVCHD:<date>|<tc>" -> the whole id.
    """
    if not recid:
        return None
    if recid.startswith("AVCHD:"):
        return recid
    return umid_material(recid)


# ---------------------------------------------------------------- AVCHD (3DA1)
MDPM_UUID = bytes.fromhex("17EE8C60F84D11D98CD60800200C9A66")


def _bcd(b):
    hi, lo = b >> 4, b & 0x0F
    if hi > 9 or lo > 9:
        raise ValueError("not BCD")
    return hi * 10 + lo


def _unescape(data):
    """Removes H.264 emulation prevention bytes (00 00 03 -> 00 00)."""
    out, zeros = bytearray(), 0
    for b in data:
        if zeros >= 2 and b == 3:
            zeros = 0
            continue
        out.append(b)
        zeros = zeros + 1 if b == 0 else 0
    return bytes(out)


def parse_mdpm(raw):
    """Timecode and recording start from the first MDPM SEI (Panasonic/Sony AVCHD) in an H.264 stream."""
    i = raw.find(MDPM_UUID)
    if i < 0:
        return {}
    seg = _unescape(raw[i + 16:i + 16 + 400])
    if seg[:4] != b"MDPM":
        return {}
    tags = {}
    for k in range(seg[4]):
        e = seg[5 + k * 5:10 + k * 5]
        if len(e) == 5:
            tags[e[0]] = e[1:]
    info = {}
    try:
        if 0x13 in tags:
            f, s, m, h = tags[0x13]
            sep = ";" if f & 0x40 else ":"
            info['start_tc'] = f"{_bcd(h & 0x3F):02d}:{_bcd(m & 0x7F):02d}:{_bcd(s & 0x7F):02d}{sep}{_bcd(f & 0x3F):02d}"
    except ValueError:
        pass
    try:
        if 0x18 in tags and 0x19 in tags:
            a, b = tags[0x18], tags[0x19]
            info['rec_date'] = (f"{_bcd(a[1]):02d}{_bcd(a[2]):02d}-{_bcd(a[3]):02d}-{_bcd(b[0]):02d}"
                                f"T{_bcd(b[1]):02d}:{_bcd(b[2]):02d}:{_bcd(b[3]):02d}")
    except ValueError:
        pass
    return info


def read_avchd_mdpm(path, ffmpeg_path, is_windows):
    """Reads the MDPM block of the first video frame of an MTS file ({} if unavailable)."""
    if not ffmpeg_path or not os.path.exists(ffmpeg_path):
        return {}
    try:
        r = subprocess.run([ffmpeg_path, "-v", "error", "-nostdin", "-i", str(path), "-map", "0:v", "-c", "copy",
                            "-frames:v", "1", "-bsf:v", "h264_mp4toannexb", "-f", "h264", "-"],
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                           creationflags=0x08000000 if is_windows else 0, timeout=30)
        return parse_mdpm(r.stdout)
    except Exception as e:
        logging.error(f"MDPM read error {path}: {e}")
        return {}


def avchd_recid(info):
    if info.get('rec_date') and info.get('start_tc'):
        return f"AVCHD:{info['rec_date']}|{info['start_tc']}"
    return None


def read_avchd_playlist_flags(stream_dir):
    """
    Maps clip number (e.g. "20001") -> True if the playlist marks it as continuation of the
    previous file (connection_condition 6 = one recording split into several files).
    """
    flags = {}
    try:
        playlist_dir = find_child_dir(Path(stream_dir).parent, "PLAYLIST")
        if not playlist_dir:
            return flags
        for mpl in playlist_dir.iterdir():
            if mpl.suffix.upper() != ".MPL":
                continue
            data = mpl.read_bytes()
            i = 0
            while True:
                i = data.find(b"M2TS", i)
                if i < 0:
                    break
                name = data[i - 5:i].decode("ascii", "replace")
                cc = data[i + 5] & 0x0F if len(data) > i + 5 else 0
                if cc == 6:
                    flags[name] = True
                i += 4
    except Exception as e:
        logging.error(f"Playlist read error {stream_dir}: {e}")
    return flags


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
        meta = self.extract_ffmpeg_metadata(file_path)
        if Path(file_path).suffix.lower() == ".mts":
            mdpm = read_avchd_mdpm(file_path, self.ffmpeg_path, self.is_windows)
            if mdpm.get('start_tc') and not is_valid_tc(meta.get('start_tc')):
                meta['start_tc'] = mdpm['start_tc']
            if mdpm.get('rec_date'):
                meta['rec_date'] = mdpm['rec_date'].replace("T", " ")
        return meta

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
