import sys
import os
import subprocess
import shutil
import re
import threading
import json
import platform
import tempfile
import logging
import time
import queue
import base64
from pathlib import Path

import flet as ft

from core.ingest_manager import IngestManager
from ui.settings_dialog import SettingsDialog

try:
    import xxhash
    HAS_XXHASH = True
except ImportError:
    HAS_XXHASH = False

APP_VERSION = "1.1.0"
CONFIG_FILE = "ingest_config.json"
MANIFEST_FILE = "ingest_manifest.json"

TRANSLATIONS = {
    "de": {
        "title": f"3DCam2Post Bridge v{APP_VERSION} (Flet Edition)",
        "btn_add_source": "+ QUELL-ORDNER",
        "btn_clear_list": "Liste leeren",
        "lbl_project": "Projekt:",
        "lbl_day": "Tag:",
        "col_id": "ID", "col_cam": "Kamera", "col_eye": "Auge", "col_size": "Größe", "col_target": "Name", "col_trans": "Transfer", "col_stat": "Status",
        "grp_log": " Logging ",
        "lbl_scene": "Szene", "lbl_setting": "Einst.", "lbl_take": "Take", "lbl_cam_id": "Cam-ID",
        "grp_hotkeys": " Hotkeys ",
        "hk_scene": "Szene [S]", "hk_setting": "Einst. [E]", "hk_remove": "X [Entf]", "hk_take_plus": "Take+ [T]", "hk_next": "Bestätigen [->]",
        "lbl_total_size": "Gesamtgröße",
        "lbl_free_space": "Frei auf Ziel",
        "btn_choose_root": "STAMMORDNER WÄHLEN",
        "btn_start": "INGEST STARTEN",
        "status_ready": "Bereit",
        "status_work": "Arbeite...",
        "status_done": "Fertig",
        "status_complete": "Komplett (L+R)",
        "status_match": "MATCH: Ergänze ",
        "status_cancelled": "Ingest abgebrochen!",
        "target_manual": "Ziel: Manuelle Wahl",
        "err_manual": "Handbuch nicht gefunden",
        "err_no_root": "Bitte erst einen Stammordner wählen!",
        "msg_no_copy": "Nichts zu kopieren.",
        "err_space": "Zu wenig Speicherplatz!",
        "warn_space": "Weniger als 100GB frei",
        "msg_complete": "Ingest abgeschlossen!",
        "msg_report": "Reports erstellt (HTML & MHL).",
        "msg_clean": "Projekt komplett! Manifest wurde bereinigt.",
        "confirm_clear": "Liste leeren?",
        "msg_manifest_loaded": "Manifest erkannt: Clips synchronisiert.",
        "win_settings": "Einstellungen",
        "sec_lang": " Sprache / Language ",
        "sec_advanced": " Erweiterte Einstellungen ",
        "opt_cam_id": "Cam-ID im Dateinamen",
        "opt_sort_day": "Archiv-Sortierung: Nach Drehtagen",
        "opt_sort_scene": "Archiv-Sortierung: Nach Szenen",
        "lbl_digits_s": "Stellen Szene:", "lbl_digits_e": "Einstell.:", "lbl_digits_t": "Take:",
        "sec_verify": " File Verification & Reports ",
        "opt_verify": "Prüfung aktivieren (MHL & HTML Report)",
        "opt_thumbs": "Vorschaubilder für HTML-Report generieren",
        "desc_verify": "Erstellt MHL und HTML Report. Erhöht Datensicherheit.",
        "opt_md5": "MD5 (Standard)",
        "opt_xx": "xxHash (High Speed)",
        "opt_sha": "SHA-256 (High Security)",
        "sec_audio": " Audio ",
        "opt_audio_l": "Links", "opt_audio_r": "Rechts", "opt_audio_b": "Beide",
        "opt_strip": "L/R Suffix bei Audio entfernen",
        "btn_manual": "📖 HANDBUCH (PDF)",
        "btn_save": "SPEICHERN",
        "btn_settings": "Einstellungen"
    },
    "en": {
        "title": f"3DCam2Post Bridge v{APP_VERSION} (Flet Edition)",
        "btn_add_source": "+ ADD SOURCE",
        "btn_clear_list": "Clear List",
        "lbl_project": "Project:",
        "lbl_day": "Day:",
        "col_id": "ID", "col_cam": "Camera", "col_eye": "Eye", "col_size": "Size", "col_target": "Name", "col_trans": "Transfer", "col_stat": "Status",
        "grp_log": " Logging ",
        "lbl_scene": "Scene", "lbl_setting": "Shot", "lbl_take": "Take", "lbl_cam_id": "Cam-ID",
        "grp_hotkeys": " Hotkeys ",
        "hk_scene": "Scene [S]", "hk_setting": "Shot [E]", "hk_remove": "X [Del]", "hk_take_plus": "Take+ [T]", "hk_next": "Confirm [->]",
        "lbl_total_size": "Total Size",
        "lbl_free_space": "Free on target",
        "btn_choose_root": "CHOOSE ROOT",
        "btn_start": "START INGEST",
        "status_ready": "Ready",
        "status_work": "Working...",
        "status_done": "Done",
        "status_complete": "Complete (L+R)",
        "status_match": "MATCH: Merging ",
        "status_cancelled": "Ingest cancelled!",
        "target_manual": "Target: Manual Selection",
        "err_manual": "Manual not found",
        "err_no_root": "Please select a root folder first!",
        "msg_no_copy": "Nothing to copy.",
        "err_space": "Insufficient disk space!",
        "warn_space": "Less than 100GB free",
        "msg_complete": "Ingest complete!",
        "msg_report": "Reports created (HTML & MHL).",
        "msg_clean": "Project complete! Manifest cleaned up.",
        "confirm_clear": "Clear list?",
        "msg_manifest_loaded": "Manifest detected: Clips synchronized.",
        "win_settings": "Settings",
        "sec_lang": " Sprache / Language ",
        "sec_advanced": " Advanced Settings ",
        "opt_cam_id": "Cam-ID in Filename",
        "opt_sort_day": "Archive Sorting: By Shooting Day",
        "opt_sort_scene": "Archive Sorting: By Scene",
        "lbl_digits_s": "Digits Scene:", "lbl_digits_e": "Shot:", "lbl_digits_t": "Take:",
        "sec_verify": " File Verification & Reports ",
        "opt_verify": "Enable Verification (Create MHL & HTML Reports)",
        "opt_thumbs": "Generate thumbnails for HTML Report",
        "desc_verify": "Creates MHL (Hash List) and HTML Report.",
        "opt_md5": "MD5 (Standard)",
        "opt_xx": "xxHash (High Speed)",
        "opt_sha": "SHA-256 (High Security)",
        "sec_audio": " Audio ",
        "opt_audio_l": "Left", "opt_audio_r": "Right", "opt_audio_b": "Both",
        "opt_strip": "Remove L/R Suffix from Audio",
        "btn_manual": "📖 MANUAL (PDF)",
        "btn_save": "SAVE",
        "btn_settings": "Settings"
    }
}

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # 1. Direct path in root
    p = os.path.join(base_path, relative_path)
    if os.path.exists(p):
        return p
    # 2. Path in assets
    p_assets = os.path.join(base_path, "assets", relative_path)
    if os.path.exists(p_assets):
        return p_assets
    # 3. Path in ui
    p_ui = os.path.join(base_path, "ui", relative_path)
    if os.path.exists(p_ui):
        return p_ui
    return p

class IngestProApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.os_type = platform.system()
        self.is_windows = (self.os_type == "Windows")

        ffmpeg_bin = "ffmpeg.exe" if self.is_windows else "ffmpeg"
        self.ffmpeg_path = resource_path(ffmpeg_bin)
        if not os.path.exists(self.ffmpeg_path):
            sys_ffmpeg = shutil.which(ffmpeg_bin)
            if sys_ffmpeg:
                self.ffmpeg_path = sys_ffmpeg

        self.defaults = {
            "language": "de", "use_cam_id": False, "verify_copy": False,  
            "generate_thumbs": True, "hash_algo": "md5",
            "padding_s": 2, "padding_e": 2, "padding_t": 3,
            "sort_mode": "Drehtage", "stammordner": "",
            "audio_source": "Links", "strip_audio_eye": False,
            "copy_video": True, "copy_audio": True
        }
        self.load_config()

        self.temp_thumb_dir = Path(tempfile.gettempdir()) / "3D_Ingest_Thumbs"
        self.temp_thumb_dir.mkdir(parents=True, exist_ok=True)

        self.all_clips = []
        self.manifest_data = {} 
        self.current_index = -1
        self._text_field_focused = False
        self.manager = None
        
        # State
        self.project_name = "Projekt_Name"
        self.day = "1"
        self.scene = "1"
        self.setting = "1"
        self.take = "1"
        self.cam_id = "A"
        self.status_msg = self.tr("status_ready")

        self.thumb_queue = queue.Queue()
        self.thumb_thread = threading.Thread(target=self.preview_worker, daemon=True)
        self.thumb_thread.start()
        
        # Pickers
        self.src_picker = ft.FilePicker()
        self.root_picker = ft.FilePicker()
        self.page.services.extend([self.src_picker, self.root_picker])

        self.page.on_keyboard_event = self.on_keyboard

        self.build_ui()
        if self.defaults["stammordner"]:
            self.load_manifest()

    def tr(self, key):
        lang_code = self.defaults.get("language", "de")
        return TRANSLATIONS.get(lang_code, TRANSLATIONS["de"]).get(key, f"MISSING: {key}")

    # --- CONFIG ---
    def load_config(self):
        c_path = Path(resource_path(CONFIG_FILE))
        if c_path.exists():
            try:
                with open(c_path, "r", encoding="utf-8") as f:
                    self.defaults.update(json.load(f))
            except Exception as e:
                print(f"Config Load Error: {e}")

    def save_config(self):
        try:
            c_path = Path(resource_path(CONFIG_FILE))
            with open(c_path, "w", encoding="utf-8") as f:
                json.dump(self.defaults, f, indent=4)
        except Exception as e:
            print(f"Config Save Error: {e}")

    def get_manifest_path(self):
        if not self.defaults["stammordner"] or not self.project_name:
            return None
        return Path(self.defaults["stammordner"]) / self.project_name / MANIFEST_FILE

    def load_manifest(self):
        path = self.get_manifest_path()
        self.manifest_data = {}
        if path and path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.manifest_data = json.load(f)
                self.sync_clips_with_manifest()
            except Exception: pass

    def save_manifest(self):
        path = self.get_manifest_path()
        if path:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(self.manifest_data, f, indent=4)
            except Exception as e:
                print(f"Manifest Save Error: {e}")

    # --- UI BUIDLING ---
    def _on_tf_focus(self, e):
        self._text_field_focused = True

    def _on_tf_blur(self, e):
        self._text_field_focused = False

    def build_ui(self):
        # Header Controls
        self.tf_project = ft.TextField(
            label=self.tr("lbl_project"), 
            value=self.project_name, 
            width=200, 
            on_change=self.on_project_change,
            on_focus=self._on_tf_focus,
            on_blur=self._on_tf_blur
        )
        self.tf_day = ft.TextField(
            label=self.tr("lbl_day"), 
            value=self.day, 
            width=80, 
            on_change=self.on_day_change,
            on_focus=self._on_tf_focus,
            on_blur=self._on_tf_blur
        )

        header = ft.Row([
            ft.ElevatedButton(self.tr("btn_add_source"), icon=ft.Icons.FOLDER_OPEN, on_click=self.pick_source, bgcolor=ft.Colors.BLUE_700, color=ft.Colors.WHITE),
            ft.TextButton(self.tr("btn_clear_list"), icon=ft.Icons.CLEAR_ALL, on_click=self.clear_list, icon_color=ft.Colors.RED_400),
            ft.Container(width=20),
            self.tf_project,
            self.tf_day,
            ft.Container(expand=True),
            ft.IconButton(ft.Icons.SETTINGS, on_click=self.open_settings, tooltip=self.tr("btn_settings"))
        ], alignment=ft.MainAxisAlignment.START)

        # List Area
        self.clip_list_view = ft.ListView(expand=True, spacing=10, padding=10)
        
        # Right Side (Log & Preview)
        self.img_preview = ft.Image(src=base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="), width=640, height=360, fit=ft.BoxFit.CONTAIN)
        self.preview_container = ft.Container(
            content=self.img_preview,
            width=640, height=360,
            bgcolor=ft.Colors.BLACK87,
            border_radius=8,
            alignment=ft.Alignment.CENTER
        )

        self.tf_scene = ft.TextField(
            label=self.tr("lbl_scene"), 
            value=self.scene, 
            width=100, 
            text_align=ft.TextAlign.CENTER, 
            text_size=20, 
            on_change=self._update_log_state,
            on_focus=self._on_tf_focus,
            on_blur=self._on_tf_blur
        )
        self.tf_setting = ft.TextField(
            label=self.tr("lbl_setting"), 
            value=self.setting, 
            width=100, 
            text_align=ft.TextAlign.CENTER, 
            text_size=20, 
            on_change=self._update_log_state,
            on_focus=self._on_tf_focus,
            on_blur=self._on_tf_blur
        )
        self.tf_take = ft.TextField(
            label=self.tr("lbl_take"), 
            value=self.take, 
            width=100, 
            text_align=ft.TextAlign.CENTER, 
            text_size=20, 
            on_change=self._update_log_state,
            on_focus=self._on_tf_focus,
            on_blur=self._on_tf_blur
        )
        self.tf_cam_id = ft.TextField(
            label=self.tr("lbl_cam_id"), 
            value=self.cam_id, 
            width=80, 
            text_align=ft.TextAlign.CENTER, 
            text_size=20, 
            on_change=self._update_log_state,
            on_focus=self._on_tf_focus,
            on_blur=self._on_tf_blur
        )

        log_controls = [self.tf_scene, self.tf_setting, self.tf_take]
        if self.defaults["use_cam_id"]: log_controls.append(self.tf_cam_id)

        log_card = ft.Card(
            content=ft.Container(
                padding=20,
                content=ft.Column([
                    ft.Text(self.tr("grp_log"), weight=ft.FontWeight.BOLD),
                    ft.Row(log_controls, alignment=ft.MainAxisAlignment.SPACE_EVENLY)
                ])
            )
        )

        hk_card = ft.Card(
            content=ft.Container(
                padding=20,
                content=ft.Column([
                    ft.Text(self.tr("grp_hotkeys"), weight=ft.FontWeight.BOLD),
                    ft.Row([
                        ft.ElevatedButton(self.tr("hk_scene"), on_click=lambda _: self.hk_new_scene(), bgcolor=ft.Colors.BLUE_800, color=ft.Colors.WHITE, expand=True),
                        ft.ElevatedButton(self.tr("hk_setting"), on_click=lambda _: self.hk_new_setting(), bgcolor=ft.Colors.ORANGE_800, color=ft.Colors.WHITE, expand=True),
                    ]),
                    ft.Row([
                        ft.ElevatedButton(self.tr("hk_remove"), on_click=lambda _: self.hk_toggle_transfer(), bgcolor=ft.Colors.RED_800, color=ft.Colors.WHITE, expand=True),
                        ft.ElevatedButton(self.tr("hk_take_plus"), on_click=lambda _: self.hk_plus_take(), bgcolor=ft.Colors.GREY_800, color=ft.Colors.WHITE, expand=True),
                        ft.ElevatedButton(self.tr("hk_next"), on_click=lambda _: self.hk_confirm_and_next(), bgcolor=ft.Colors.GREEN_800, color=ft.Colors.WHITE, expand=True),
                    ])
                ])
            )
        )

        # Bottom Ingest Controls
        self.lbl_target = ft.Text(self.defaults["stammordner"] or self.tr("err_no_root"), size=12, italic=True)
        self.lbl_total_size = ft.Text("0.00 GB", weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_400)
        
        self.pb_ingest = ft.ProgressBar(value=0, visible=False)
        self.lbl_mbps = ft.Text("", size=12, color=ft.Colors.GREY_400)
        
        self.btn_root = ft.ElevatedButton(self.tr("btn_choose_root"), icon=ft.Icons.FOLDER, on_click=self.pick_root)
        self.btn_start = ft.ElevatedButton(self.tr("btn_start"), icon=ft.Icons.PLAY_ARROW, bgcolor=ft.Colors.GREEN_700, color=ft.Colors.WHITE, on_click=self.start_ingest, expand=True)
        self.btn_cancel = ft.ElevatedButton("ABBRECHEN", icon=ft.Icons.STOP, bgcolor=ft.Colors.RED_700, color=ft.Colors.WHITE, on_click=self.cancel_ingest, disabled=True)

        ingest_card = ft.Card(
            content=ft.Container(
                padding=15,
                content=ft.Column([
                    ft.Row([self.lbl_target, ft.Container(expand=True), self.lbl_total_size]),
                    self.pb_ingest,
                    ft.Row([self.btn_root, ft.Container(expand=True), self.lbl_mbps]),
                    ft.Row([self.btn_start, self.btn_cancel])
                ])
            )
        )

        right_col = ft.Column([
            self.preview_container,
            log_card,
            hk_card,
            ft.Container(expand=True),
            ingest_card
        ], width=640)

        main_row = ft.Row([
            ft.Container(content=self.clip_list_view, expand=True, border=ft.Border.all(1, ft.Colors.OUTLINE), border_radius=8),
            right_col
        ], expand=True)

        self.status_bar = ft.Text(self.status_msg, size=12)
        self.lbl_version = ft.Text(f"v{APP_VERSION}", size=11, color=ft.Colors.GREY_500, weight=ft.FontWeight.W_500)

        self.page.add(
            header,
            main_row,
            ft.Row([
                self.status_bar,
                ft.Container(expand=True),
                self.lbl_version
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        )

    # --- STATE HANDLERS ---
    def on_project_change(self, e): 
        self.project_name = e.control.value
        self.load_manifest()
        self.refresh_ui()

    def on_day_change(self, e): 
        self.day = e.control.value

    def _update_log_state(self, e=None):
        self.scene = self.tf_scene.value
        self.setting = self.tf_setting.value
        self.take = self.tf_take.value
        self.cam_id = self.tf_cam_id.value

    def update_log_fields(self):
        self.tf_scene.value = self.scene
        self.tf_setting.value = self.setting
        self.tf_take.value = self.take
        self.tf_cam_id.value = self.cam_id
        self.page.update()

    def set_status(self, msg):
        self.status_bar.value = msg
        self.page.update()

    def open_settings(self, e):
        dlg = SettingsDialog(self.page, self.defaults, HAS_XXHASH, self.tr, self.on_settings_saved, self.open_manual, APP_VERSION)
        dlg.open()

    def on_settings_saved(self, new_defaults):
        self.defaults = new_defaults
        self.save_config()
        self.page.controls.clear()
        self.status_msg = self.tr("status_ready")
        self.build_ui()
        self.refresh_ui()

    def open_manual(self):
        lang = self.defaults.get("language", "de")
        filename = "3DC2P Manual DE.pdf" if lang == "de" else "3DC2P Manual ENG.pdf"
        p = Path(resource_path(filename))
        if p.exists():
            try:
                if self.is_windows: os.startfile(p)
                elif self.os_type == "Darwin": subprocess.run(["open", str(p)])
                else: subprocess.run(["xdg-open", str(p)])
            except Exception as e:
                self.set_status(f"Error opening manual: {e}")
        else:
            self.set_status(self.tr("err_manual"))

    # --- LIST / CARDS ---
    def refresh_ui(self):
        self.clip_list_view.controls.clear()
        total_transfer_size = 0

        for i, c in enumerate(self.all_clips):
            is_selected = (i == self.current_index)
            
            eyes_str = "/".join([e for e in ["L","R"] if c[f'path_{e}']])
            tgt = self.format_name(c, i+1) if c['logged'] else "-"
            
            if c.get('tag') == 'complete':
                stat_text = self.tr("status_complete")
                stat_color = ft.Colors.GREEN_400
            elif c['done'] and c.get('tag') != 'complete':
                stat_text = self.tr("status_done")
                stat_color = ft.Colors.BLUE_400
            else:
                stat_text = c.get('status_text', self.tr("status_ready"))
                stat_color = ft.Colors.ORANGE_400 if 'tag' in c and c['tag'] == 'match' else ft.Colors.GREY_400

            if c['transfer'] and not c['done']:
                total_transfer_size += c['size_bytes']

            bg_color = ft.Colors.BLUE_900 if is_selected else ft.Colors.SURFACE_VARIANT

            card = ft.Container(
                bgcolor=bg_color,
                border_radius=8,
                padding=10,
                on_click=lambda e, idx=i: self.select_clip(idx),
                content=ft.Row([
                    ft.Checkbox(value=c['transfer'], on_change=lambda e, idx=i: self.toggle_transfer_from_cb(idx, e.control.value)),
                    ft.Column([
                        ft.Text(f"ID: {c['id']} | {c['cam']} | Eye: {eyes_str}", weight=ft.FontWeight.BOLD),
                        ft.Text(tgt, color=ft.Colors.GREY_300, italic=True),
                    ], expand=True),
                    ft.Column([
                        ft.Text(f"{c['size_bytes']/1024**3:.2f} GB", text_align=ft.TextAlign.RIGHT),
                        ft.Text(stat_text, color=stat_color, text_align=ft.TextAlign.RIGHT, weight=ft.FontWeight.BOLD)
                    ], alignment=ft.MainAxisAlignment.CENTER)
                ])
            )
            self.clip_list_view.controls.append(card)

        self.lbl_total_size.value = f"{total_transfer_size / (1024**3):.2f} GB"
        self.page.update()

    def select_clip(self, idx):
        self.current_index = idx
        self.refresh_ui()
        c = self.all_clips[idx]
        with self.thumb_queue.mutex: self.thumb_queue.queue.clear()
        self.thumb_queue.put(c)

    def toggle_transfer_from_cb(self, idx, val):
        self.all_clips[idx]['transfer'] = val
        self.refresh_ui()

    def format_name(self, clip, idx=1):
        name = f"{self.project_name}_S{str(clip['scene']).zfill(self.defaults['padding_s'])}_E{str(clip['setting']).zfill(self.defaults['padding_e'])}_T{str(clip['take']).zfill(self.defaults['padding_t'])}"
        if self.defaults["use_cam_id"]: name += f"_{self.cam_id}"
        return name

    def clear_list(self, e):
        self.all_clips = []
        self.current_index = -1
        self.refresh_ui()
        self.set_status(self.tr("status_ready"))

    # --- SCANNING / PICKERS ---
    async def pick_source(self, e):
        path = await self.src_picker.get_directory_path()
        if path:
            threading.Thread(target=self._scan_folder, args=(path,), daemon=True).start()

    async def pick_root(self, e):
        path = await self.root_picker.get_directory_path()
        if path:
            self.defaults["stammordner"] = path
            self.save_config()
            self.lbl_target.value = path
            self.load_manifest()
            self.page.update()

    def _scan_folder(self, path):
        self.set_status(f"Scanning {path}...")
        manager = IngestManager(self.defaults, self.temp_thumb_dir, self.ffmpeg_path, self.is_windows, {})
        found = manager.scan_folder(path)
        
        current_map = {c['id']: c for c in self.all_clips}
        for item in found:
            cid = item['id']
            if cid not in current_map:
                current_map[cid] = {
                    'id': cid, 'path_L': None, 'path_R': None, 'cam': item['cam'], 
                    'scene': "", 'setting': "", 'take': "", 
                    'logged': False, 'transfer': False, 'done': False, 'size_bytes': 0,
                    'tag': 'normal', 'status_text': self.tr("status_ready")
                }
            if not current_map[cid][f'path_{item["e"]}']:
                current_map[cid][f'path_{item["e"]}'] = item['p']
                current_map[cid]['size_bytes'] += item['s']
        
        self.all_clips = [current_map[cid] for cid in sorted(current_map.keys())]
        self.sync_clips_with_manifest()
        
        if not found:
            self.set_status(f"Keine 3D-Clips in {path} gefunden." if self.defaults.get("language", "de") == "de" else f"No 3D clips found in {path}.")
        else:
            self.set_status(self.tr("status_ready"))
        self.refresh_ui()

    def sync_clips_with_manifest(self):
        matched = 0
        for clip in self.all_clips:
            cid = clip['id']
            if cid in self.manifest_data:
                m = self.manifest_data[cid]
                clip['scene'] = m.get('scene', "")
                clip['setting'] = m.get('setting', "")
                clip['take'] = m.get('take', "")
                clip['logged'] = True
                
                l_done = m.get("status_L") == "done"
                r_done = m.get("status_R") == "done"
                
                if l_done and r_done:
                    clip['status_text'] = self.tr("status_complete")
                    clip['tag'] = 'complete'
                    clip['done'] = True
                    clip['transfer'] = False
                elif (l_done or r_done):
                    missing = "R" if l_done else "L"
                    clip['status_text'] = f"{self.tr('status_match')}{missing}"
                    clip['tag'] = 'match'
                    clip['transfer'] = True
                    matched += 1
                else:
                    clip['status_text'] = self.tr("status_ready")
                    clip['tag'] = 'normal'
                    clip['transfer'] = True

    # --- PREVIEW WORKER ---
    def preview_worker(self):
        while True:
            try:
                data = self.thumb_queue.get()
                vid = data['path_L'] or data['path_R']
                if vid and os.path.exists(self.ffmpeg_path):
                    t_path = self.temp_thumb_dir / f"t_{data['id']}.jpg"
                    if not t_path.exists():
                        c_flags = 0x08000000 if self.is_windows else 0
                        subprocess.run([self.ffmpeg_path, '-y', '-ss', '1.0', '-i', vid, '-frames:v', '1', '-s', '640x360', str(t_path)], stderr=subprocess.DEVNULL, creationflags=c_flags)
                    if t_path.exists():
                        with open(t_path, "rb") as img_file:
                            self.img_preview.src = img_file.read()
                        self.page.update()
                self.thumb_queue.task_done()
            except Exception: pass

    # --- HOTKEYS ---
    def on_keyboard(self, e: ft.KeyboardEvent):
        if self._text_field_focused:
            return
        key = e.key
        key_upper = key.upper() if key else ""
        if key == "Arrow Down": self.select_rel(1)
        elif key == "Arrow Up": self.select_rel(-1)
        elif key == "Arrow Right": self.hk_confirm_and_next()
        elif key == "Delete" or key == "Backspace": self.hk_toggle_transfer()
        elif key_upper == "S": self.hk_new_scene()
        elif key_upper == "E": self.hk_new_setting()
        elif key_upper == "T": self.hk_plus_take()

    def select_rel(self, d):
        if not self.all_clips: return
        ni = self.current_index + d
        if 0 <= ni < len(self.all_clips):
            self.select_clip(ni)

    def hk_new_scene(self):
        try: self.scene = str(int(self.scene)+1); self.setting = "1"; self.take = "1"
        except: self.scene = "1"; self.setting = "1"; self.take = "1"
        self.update_log_fields()
    
    def hk_new_setting(self):
        try: self.setting = str(int(self.setting)+1); self.take = "1"
        except: self.setting = "1"; self.take = "1"
        self.update_log_fields()

    def hk_plus_take(self):
        try: self.take = str(int(self.take)+1)
        except: self.take = "1"
        self.update_log_fields()

    def hk_toggle_transfer(self):
        if self.current_index >= 0 and self.current_index < len(self.all_clips):
            c = self.all_clips[self.current_index]
            c['transfer'] = not c['transfer']
            self.refresh_ui()

    def hk_confirm_and_next(self):
        if self.current_index >= 0 and self.current_index < len(self.all_clips):
            c = self.all_clips[self.current_index]
            c.update({'scene': self.scene, 'setting': self.setting, 'take': self.take, 'logged': True, 'transfer': True})
            try: self.take = str(int(self.take) + 1)
            except: self.take = "1"
            self.update_log_fields()
            self.refresh_ui()
            self.select_rel(1)

    # --- INGEST ---
    def start_ingest(self, e):
        if not self.defaults["stammordner"]:
            self.set_status("ERROR: " + self.tr("err_no_root"))
            return
        
        self.load_manifest()
        base = Path(self.defaults["stammordner"]) / self.project_name
        
        to_copy = []
        for i, c in enumerate(self.all_clips):
            if c['transfer'] and not c['done'] and c['logged']:
                to_copy.append((c, i))

        if not to_copy:
            self.set_status(self.tr("msg_no_copy"))
            return

        total_copy_bytes = sum(c['size_bytes'] for c, _ in to_copy)
        try:
            total_disk, used_disk, free_disk = shutil.disk_usage(self.defaults["stammordner"])
            if free_disk < total_copy_bytes:
                self.set_status(f"ERROR: {self.tr('err_space')} ({free_disk / (1024**3):.1f} GB frei < {total_copy_bytes / (1024**3):.1f} GB)")
                return
            if free_disk - total_copy_bytes < 100 * (1024**3):
                self.set_status(f"WARNUNG: {self.tr('warn_space')}")
        except Exception: pass

        self.btn_start.disabled = True
        self.btn_cancel.disabled = False
        self.pb_ingest.visible = True
        self.pb_ingest.value = 0
        self.page.update()

        def _on_status(msg):
            self.status_bar.value = msg
            self.page.update()

        def _on_total(pct, mbps, eta):
            self.pb_ingest.value = pct / 100
            self.lbl_mbps.value = f"{mbps:.1f} MB/s | ETA: {eta:.0f}s"
            self.page.update()

        def _on_clip_start(idx):
            self.all_clips[idx]['status_text'] = self.tr("status_work")
            self.refresh_ui()

        def _on_clip_done(idx, m_data):
            self.manifest_data = m_data
            self.all_clips[idx]['done'] = True
            self.save_manifest()
            self.refresh_ui()

        callbacks = {
            'on_status': _on_status,
            'on_total_progress': _on_total,
            'on_clip_start': _on_clip_start,
            'on_clip_done': _on_clip_done,
            'on_error': _on_status
        }
        
        self.manager = IngestManager(self.defaults, self.temp_thumb_dir, self.ffmpeg_path, self.is_windows, callbacks)

        def run():
            m_data, log = self.manager.run_ingest(
                to_copy, 
                self.project_name, 
                lambda c: base / (f"Tag_{str(self.day).zfill(2)}" if self.defaults["sort_mode"] == "Drehtage" else f"Szene_{str(c['scene']).zfill(self.defaults['padding_s'])}"),
                lambda c: self.format_name(c, 1),
                base, 
                base, 
                self.manifest_data
            )
            self.manifest_data = m_data
            self.save_manifest()
            self.post_ingest()

        threading.Thread(target=run, daemon=True).start()

    def cancel_ingest(self, e):
        if self.manager:
            self.manager.cancel_event.set()
            self.set_status("ABBRUCH WIRD AUSGEFÜHRT...")
            self.btn_cancel.disabled = True
            self.page.update()

    def post_ingest(self):
        self.sync_clips_with_manifest()
        if self.manager and self.manager.cancel_event.is_set():
            self.set_status(self.tr("status_cancelled"))
        else:
            self.set_status(self.tr("msg_complete"))
        
        self.btn_start.disabled = False
        self.btn_cancel.disabled = True
        self.pb_ingest.visible = False
        self.lbl_mbps.value = ""
        self.refresh_ui()