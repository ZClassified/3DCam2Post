import os
import datetime
import base64
import hashlib
import xml.etree.ElementTree as ET
import subprocess
from pathlib import Path

try:
    import xxhash
    HAS_XXHASH = True
except ImportError:
    HAS_XXHASH = False

class ReportGenerator:
    def __init__(self, temp_thumb_dir, ffmpeg_path, is_windows):
        self.temp_thumb_dir = Path(temp_thumb_dir)
        self.ffmpeg_path = ffmpeg_path
        self.is_windows = is_windows

    def generate_checksum(self, file_path, algo="md5"):
        if algo == "sha256": hasher = hashlib.sha256()
        elif algo == "xxhash":
            if HAS_XXHASH: hasher = xxhash.xxh64()
            else: hasher = hashlib.md5()
        else: hasher = hashlib.md5()

        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096 * 1024), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def generate_reports(self, project_name, processed_clips, report_dir):
        if not processed_clips: return
        
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ts_file = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        
        mhl_name = f"Transfer_{ts_file}.mhl"
        mhl_path = Path(report_dir) / mhl_name
        self.write_mhl(mhl_path, processed_clips, timestamp)
        
        html_name = f"Report_{project_name}_{ts_file}.html"
        html_path = Path(report_dir) / html_name
        self.write_html_report(html_path, project_name, processed_clips, timestamp)

    def write_mhl(self, path, clips, timestamp):
        root = ET.Element("hashlist", version="1.1")
        creator = ET.SubElement(root, "creatorinfo")
        ET.SubElement(creator, "creationdate").text = timestamp
        ET.SubElement(creator, "tool").text = "3DCam2Post Bridge"
        
        for item in clips:
            h_entry = ET.SubElement(root, "hash")
            try: rel_path = os.path.relpath(item['path'], path.parent)
            except: rel_path = item['path']
                
            ET.SubElement(h_entry, "file").text = str(rel_path)
            ET.SubElement(h_entry, item['algo']).text = item['hash']
            ET.SubElement(h_entry, "size").text = str(item['size'])
            
        tree = ET.ElementTree(root)
        try:
            from xml.dom import minidom
            xmlstr = minidom.parseString(ET.tostring(root)).toprettyxml(indent="  ")
            with open(path, "w", encoding="utf-8") as f: f.write(xmlstr)
        except:
            tree.write(path, encoding="utf-8", xml_declaration=True)

    def write_html_report(self, path, project_name, clips, timestamp):
        css = """
        body { font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #333; margin: 40px; font-size: 13px; line-height: 1.5; }
        h1 { color: #2c3e50; border-bottom: 2px solid #2c3e50; padding-bottom: 10px; margin-bottom: 20px; font-size: 24px; }
        .meta { margin-bottom: 30px; background: #f8f9fa; padding: 15px; border-radius: 6px; border: 1px solid #e9ecef; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; font-size: 12px; }
        th { background: #343a40; color: #fff; text-align: left; padding: 10px; font-weight: 600; text-transform: uppercase; font-size: 11px; }
        td { border-bottom: 1px solid #dee2e6; padding: 10px; vertical-align: top; }
        tr:nth-child(even) { background-color: #f8f9fa; }
        .thumb-cell { display: flex; gap: 5px; }
        .thumb { width: 106px; height: 60px; object-fit: cover; border: 1px solid #dee2e6; display: block; background: #000; }
        .success { color: #28a745; font-weight: bold; }
        .tech { font-family: Consolas, Monaco, 'Andale Mono', monospace; font-size: 11px; color: #555; }
        .path { font-family: Consolas, monospace; font-size: 10px; color: #666; word-break: break-all; }
        .eye-badge { display: inline-block; padding: 1px 4px; border-radius: 3px; font-size: 9px; font-weight: bold; color: white; margin-right: 3px; }
        .eye-L { background-color: #007bff; }
        .eye-R { background-color: #dc3545; }
        """
        
        grouped = {}
        cnt_vid = 0; cnt_aud = 0; cnt_xml = 0
        
        for item in clips:
            if item['type'] == 'video': cnt_vid += 1
            elif item['type'] == 'audio': cnt_aud += 1
            elif item['type'] == 'xml': cnt_xml += 1
            
            if item['type'] == 'video':
                cid = item['clip_id']
                if cid not in grouped: grouped[cid] = {'L': None, 'R': None, 'meta': {}, 'name': ''}
                
                eye = item['eye']
                grouped[cid][eye] = item
                if not grouped[cid]['meta']: 
                    grouped[cid]['meta'] = item.get('meta', {})
                    grouped[cid]['name'] = item['name'].replace(f"_{eye}", "")
        
        rows = ""
        for cid, data in grouped.items():
            l_item = data.get('L')
            r_item = data.get('R')
            
            main = l_item if l_item else r_item
            if not main: continue 
            
            meta = data['meta']
            
            t1 = self.get_thumb_base64(cid, 1)
            t2 = self.get_thumb_base64(cid, 2)
            t3 = self.get_thumb_base64(cid, 3)
            
            paths_html = ""
            hashes_html = ""
            
            if l_item:
                paths_html += f"<span class='eye-badge eye-L'>L</span> <span class='path'>{l_item['path']}</span><br>"
                hashes_html += f"<span class='eye-badge eye-L'>L</span> <span class='tech'>{l_item['hash']}</span><br>"
            if r_item:
                paths_html += f"<span class='eye-badge eye-R'>R</span> <span class='path'>{r_item['path']}</span>"
                hashes_html += f"<span class='eye-badge eye-R'>R</span> <span class='tech'>{r_item['hash']}</span>"
            
            orig_html = ""
            if l_item: orig_html += f"L: {l_item.get('original_name', '-')}<br>"
            if r_item: orig_html += f"R: {r_item.get('original_name', '-')}"

            tc_display = meta.get('start_tc', 'N/A')
            if tc_display == "00:00:00:00" and ".MTS" in main['original_name'].upper():
                 tc_display = "N/A"

            rows += f"""
            <tr>
                <td width="330">
                    <div class="thumb-cell">
                        <img src="data:image/jpeg;base64,{t1}" class="thumb" title="Start Frame">
                        <img src="data:image/jpeg;base64,{t2}" class="thumb" title="Mid Frame">
                        <img src="data:image/jpeg;base64,{t3}" class="thumb" title="End Frame">
                    </div>
                </td>
                <td>
                    <b>{data['name']}</b><br>
                    <small>{orig_html}</small>
                </td>
                <td class="tech">
                    Format: {meta.get('res', 'N/A')}<br>
                    FPS: {meta.get('fps', 'N/A')}<br>
                    Dur: {meta.get('duration_str', 'N/A')} ({meta.get('frames', '0')} f)<br>
                    Codec: {meta.get('codec', 'N/A')} {meta.get('bitrate', '')}<br>
                    TC: {tc_display}
                </td>
                <td>{paths_html}</td>
                <td>{hashes_html}</td>
                <td class="success">VERIFIED</td>
            </tr>
            """

        html = f"""
        <html>
        <head><title>Ingest Report</title><style>{css}</style></head>
        <body>
            <h1>OFFLOAD REPORT</h1>
            <div class="meta">
                <strong>Project:</strong> {project_name}<br>
                <strong>Date:</strong> {timestamp}<br>
                <strong>Total Files Processed:</strong> {len(clips)} <small>(Video: {cnt_vid}, Audio: {cnt_aud}, XML: {cnt_xml})</small><br>
                <strong>Status:</strong> Verification Successful
            </div>
            <table>
                <thead>
                    <tr>
                        <th>Thumbnails (10% / 50% / 90%)</th>
                        <th>Clip Info</th>
                        <th>Technical Metadata</th>
                        <th>Destination Paths</th>
                        <th>Checksums ({main['algo'] if main else 'MD5'})</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>
        </body>
        </html>
        """
        
        try:
            with open(path, "w", encoding="utf-8") as f: f.write(html)
        except Exception as e: print(f"HTML Report Error: {e}")

    def get_thumb_base64(self, clip_id, index):
        t_path = self.temp_thumb_dir / f"t_{clip_id}_{index}.jpg"
        if t_path.exists():
            try:
                with open(t_path, "rb") as img_file:
                    return base64.b64encode(img_file.read()).decode('utf-8')
            except: pass
        return ""

    def create_report_thumbnails(self, video_path, clip_id, duration_sec, fps_val, start_offset_sec=0):
        if not os.path.exists(self.ffmpeg_path): return
        if (self.temp_thumb_dir / f"t_{clip_id}_1.jpg").exists(): return

        try:
            dur = float(duration_sec) if duration_sec else 0
            if dur < 1: dur = 5
        except: dur = 5
        
        timestamps = [dur * 0.1, dur * 0.5, dur * 0.9]
        c_flags = 0x08000000 if self.is_windows else 0
        
        for i, ts in enumerate(timestamps):
            out = self.temp_thumb_dir / f"t_{clip_id}_{i+1}.jpg"
            subprocess.run([
                self.ffmpeg_path, '-y', '-ss', str(ts), '-i', str(video_path), 
                '-frames:v', '1', '-s', '320x180', str(out)
            ], stderr=subprocess.DEVNULL, creationflags=c_flags)
