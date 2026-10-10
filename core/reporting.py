import os
import html
import base64
import datetime
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from core.paths import file_key

# MHL v1.1 hash element names
MHL_TAGS = {"md5": "md5", "xxhash": "xxhash64be", "sha256": "sha256"}


class ReportGenerator:
    def __init__(self, temp_thumb_dir, ffmpeg_path, is_windows):
        self.temp_thumb_dir = Path(temp_thumb_dir)
        self.ffmpeg_path = ffmpeg_path
        self.is_windows = is_windows

    def generate_reports(self, project_name, files, report_dir, errors=None):
        ts_file = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        report_dir = Path(report_dir)
        report_dir.mkdir(parents=True, exist_ok=True)

        mhl_path = report_dir / f"Transfer_{ts_file}.mhl"
        self.write_mhl(mhl_path, files, timestamp)

        html_path = report_dir / f"Report_{project_name}_{ts_file}.html"
        self.write_html_report(html_path, project_name, files, timestamp, errors or [])
        return mhl_path, html_path

    def write_mhl(self, path, files, timestamp):
        root = ET.Element("hashlist", version="1.1")
        creator = ET.SubElement(root, "creatorinfo")
        ET.SubElement(creator, "creationdate").text = timestamp
        ET.SubElement(creator, "tool").text = "3DCam2Post Bridge"

        for item in files:
            if item.get('hash') in (None, "N/A"):
                continue
            h_entry = ET.SubElement(root, "hash")
            try:
                rel_path = os.path.relpath(item['path'], path.parent)
            except ValueError:
                rel_path = item['path']
            ET.SubElement(h_entry, "file").text = str(rel_path).replace(os.sep, "/")
            ET.SubElement(h_entry, "size").text = str(item['size'])
            ET.SubElement(h_entry, MHL_TAGS.get(item['algo'], item['algo'])).text = item['hash']

        ET.indent(root, space="  ")
        ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)

    def write_html_report(self, path, project_name, files, timestamp, errors):
        esc = html.escape
        css = """
        body { font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #333; margin: 40px; font-size: 13px; line-height: 1.5; }
        h1 { color: #2c3e50; border-bottom: 2px solid #2c3e50; padding-bottom: 10px; margin-bottom: 20px; font-size: 24px; }
        .meta { margin-bottom: 30px; background: #f8f9fa; padding: 15px; border-radius: 6px; border: 1px solid #e9ecef; }
        .errors { margin-bottom: 30px; background: #fdecea; padding: 15px; border-radius: 6px; border: 1px solid #f5c2c7; color: #842029; }
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

        counts = {'video': 0, 'audio': 0, 'xml': 0}
        grouped = {}
        for item in files:
            counts[item['type']] = counts.get(item['type'], 0) + 1
            if item['type'] != 'video':
                continue
            g = grouped.setdefault(item['clip_id'], {'L': None, 'R': None, 'meta': item.get('meta', {}),
                                                     'name': item.get('base_name', item['name']), 'thumbs': []})
            g[item['eye']] = item
            if item.get('thumbs'):
                g['thumbs'] = item['thumbs']

        algo = next((f['algo'] for f in files if f.get('algo')), 'md5')
        rows = []
        for cid, data in grouped.items():
            l_item, r_item = data['L'], data['R']
            meta = data['meta']
            thumbs = "".join(
                f'<img src="data:image/jpeg;base64,{self._b64(t)}" class="thumb">' for t in data['thumbs'])
            paths_html = hashes_html = orig_html = ""
            for eye, it in (("L", l_item), ("R", r_item)):
                if not it:
                    continue
                badge = f"<span class='eye-badge eye-{eye}'>{eye}</span>"
                paths_html += f"{badge} <span class='path'>{esc(it['path'])}</span><br>"
                hashes_html += f"{badge} <span class='tech'>{esc(it['hash'])}</span><br>"
                orig_html += f"{eye}: {esc(it.get('original_name', '-'))}<br>"

            rows.append(f"""
            <tr>
                <td width="330"><div class="thumb-cell">{thumbs}</div></td>
                <td><b>{esc(data['name'])}</b><br><small>{orig_html}</small></td>
                <td class="tech">
                    Format: {esc(str(meta.get('res', 'N/A')))}<br>
                    FPS: {esc(str(meta.get('fps', 'N/A')))}<br>
                    Dur: {esc(str(meta.get('duration_str', 'N/A')))} ({meta.get('frames', 0)} f)<br>
                    Codec: {esc(str(meta.get('codec', 'N/A')))} {esc(str(meta.get('bitrate', '')))}<br>
                    TC: {esc(str(meta.get('start_tc', 'N/A')))}
                    {('<br>Rec: ' + esc(meta['rec_date'])) if meta.get('rec_date') else ''}
                </td>
                <td>{paths_html}</td>
                <td>{hashes_html}</td>
                <td class="success">VERIFIED</td>
            </tr>""")

        err_html = ""
        if errors:
            err_html = "<div class='errors'><strong>Errors:</strong><br>" + "<br>".join(esc(e) for e in errors) + "</div>"
        status = "Verification Successful" if not errors else f"{len(errors)} error(s) – see list"

        doc = f"""<!doctype html>
<html>
<head><meta charset="utf-8"><title>Ingest Report {esc(project_name)}</title><style>{css}</style></head>
<body>
    <h1>OFFLOAD REPORT</h1>
    <div class="meta">
        <strong>Project:</strong> {esc(project_name)}<br>
        <strong>Date:</strong> {timestamp}<br>
        <strong>Total Files Processed:</strong> {len(files)} <small>(Video: {counts['video']}, Audio: {counts['audio']}, XML: {counts['xml']})</small><br>
        <strong>Status:</strong> {status}
    </div>
    {err_html}
    <table>
        <thead><tr>
            <th>Thumbnails (10% / 50% / 90%)</th><th>Clip Info</th><th>Technical Metadata</th>
            <th>Destination Paths</th><th>Checksums ({esc(algo)})</th><th>Status</th>
        </tr></thead>
        <tbody>{''.join(rows)}</tbody>
    </table>
</body>
</html>"""
        with open(path, "w", encoding="utf-8") as f:
            f.write(doc)

    @staticmethod
    def _b64(path):
        try:
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode('ascii')
        except OSError:
            return ""

    def create_report_thumbnails(self, video_path, duration_sec):
        """Creates 3 thumbnails (10/50/90 %) and returns their paths."""
        if not self.ffmpeg_path or not os.path.exists(self.ffmpeg_path):
            return []
        try:
            dur = float(duration_sec or 0)
        except (TypeError, ValueError):
            dur = 0
        if dur < 1:
            dur = 1

        key = file_key(video_path)
        c_flags = 0x08000000 if self.is_windows else 0
        out_paths = []
        for i, frac in enumerate((0.1, 0.5, 0.9), start=1):
            out = self.temp_thumb_dir / f"rep_{key}_{i}.jpg"
            if not out.exists():
                subprocess.run([
                    self.ffmpeg_path, '-y', '-ss', f"{dur * frac:.2f}", '-i', str(video_path),
                    '-frames:v', '1', '-s', '320x180', str(out)
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=c_flags)
            if out.exists():
                out_paths.append(out)
        return out_paths
