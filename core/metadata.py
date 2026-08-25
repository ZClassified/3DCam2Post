import os
import re
import datetime
import subprocess
import logging
import xml.etree.ElementTree as ET

class MetadataExtractor:
    def __init__(self, ffmpeg_path, is_windows):
        self.ffmpeg_path = ffmpeg_path
        self.is_windows = is_windows

    def extract_ffmpeg_metadata(self, file_path):
        meta = {'codec': '-', 'fps': '25', 'dur': '-', 'res': '-', 'bitrate': '', 
                'start_tc': 'N/A', 'frames': 0, 'duration_sec': 0, 'start_sec': 0}
        
        if not os.path.exists(self.ffmpeg_path): return meta
        
        cmd = [self.ffmpeg_path, '-i', str(file_path)]
        try:
            startupinfo = None
            if self.is_windows:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, startupinfo=startupinfo, text=True)
            output = result.stderr
            
            dur_match = re.search(r"Duration:\s*(\d{1,2}:\d{2}:\d{2}\.\d{2})", output)
            start_match = re.search(r",\s*start:\s*([0-9.]+)", output)
            
            if start_match:
                meta['start_sec'] = float(start_match.group(1))

            if dur_match:
                meta['dur'] = dur_match.group(1)
                try:
                    h,m,s = meta['dur'].split(':')
                    seconds = float(h)*3600 + float(m)*60 + float(s)
                    meta['duration_sec'] = seconds
                except: pass
            
            vid_match = re.search(r"Stream.*Video: (.*?),.*?, (\d{3,4}x\d{3,4}).*, (\d+(?:\.\d+)?) fps", output)
            if vid_match:
                meta['codec'] = vid_match.group(1).split(' ')[0]
                meta['res'] = vid_match.group(2)
                meta['fps'] = vid_match.group(3)
                
                if meta['duration_sec'] > 0:
                    try:
                        meta['frames'] = int(meta['duration_sec'] * float(meta['fps']))
                        meta['duration_str'] = str(datetime.timedelta(seconds=int(meta['duration_sec'])))
                    except: pass
            
            tc_match = re.search(r"timecode\s*:\s*(\d{2}:\d{2}:\d{2}[:;]\d{2})", output, re.IGNORECASE)
            if tc_match:
                meta['start_tc'] = tc_match.group(1)
                
        except Exception as e:
            logging.error(f"FFmpeg meta error: {e}")
        return meta

    def extract_p2_metadata(self, vid_path):
        meta = {'codec': '-', 'fps': '-', 'dur': '-', 'res': '-', 'bitrate': '', 
                'start_tc': '-', 'duration_sec': 0}
        try:
            vid_path = Path(vid_path)
            clip_dir = vid_path.parent.parent / "CLIP"
            if not clip_dir.exists():
                return meta

            src_xml = None
            target_xml_name = f"{vid_path.stem}.xml".upper()
            for f in clip_dir.iterdir():
                if f.name.upper() == target_xml_name:
                    src_xml = f
                    break

            if not src_xml or not src_xml.exists():
                return meta
            
            tree = ET.parse(src_xml)
            root = tree.getroot()
            
            for elem in root.iter():
                tag = elem.tag.split('}')[-1]
                if tag == "Codec": 
                    meta['codec'] = elem.text
                    c_class = elem.attrib.get('Class')
                    if c_class: meta['bitrate'] = f"({c_class} Mbit)"
                elif tag == "FrameRate": meta['fps'] = elem.text
                elif tag == "Duration": meta['frames'] = elem.text
                elif tag == "VideoFormat": meta['res'] = elem.text
                elif tag == "StartTimecode": meta['start_tc'] = elem.text
            
            if 'frames' in meta and 'fps' in meta:
                try:
                    f = int(meta['frames'])
                    fps_val = float(meta['fps'].replace('p','').replace('i',''))
                    seconds = int(f / fps_val)
                    meta['duration_sec'] = float(f / fps_val)
                    meta['duration_str'] = str(datetime.timedelta(seconds=seconds))
                except: pass
        except: pass
        return meta
