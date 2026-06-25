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
import hashlib
import datetime
import base64
import tkinter as tk
import xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image, ImageTk
from tkinter import filedialog, messagebox, ttk

# Versuche xxhash zu importieren
try:
    import xxhash
    HAS_XXHASH = True
except ImportError:
    HAS_XXHASH = False

# --- KONFIGURATION ---
CONFIG_FILE = "ingest_config.json"
MANIFEST_FILE = "ingest_manifest.json"

# --- ÜBERSETZUNGEN / TRANSLATIONS ---
TRANSLATIONS = {
    "de": {
        "title": "3DCam2Post Bridge v0.9.2 (A1 Patch)",
        "btn_add_source": "+ QUELL-ORDNER HINZUFÜGEN",
        "btn_clear_list": "Liste leeren",
        "lbl_project": "   Projekt:",
        "lbl_day": "  Tag:",
        "col_id": "ID", "col_cam": "Kamera", "col_eye": "Auge", "col_size": "Größe", "col_target": "Geloggter Name", "col_trans": "Transfer", "col_stat": "Status",
        "grp_log": " Logging ",
        "lbl_scene": "Szene", "lbl_setting": "Einstellung", "lbl_take": "Take", "lbl_cam_id": "Cam-ID",
        "grp_hotkeys": " Hotkeys ",
        "hk_scene": "Szene [s]", "hk_setting": "Einstellung [e]", "hk_remove": "X [Entf]", "hk_take_plus": "Take+ [t]", "hk_next": "Bestätigen & Weiter [->]",
        "lbl_total_size": "Gesamtgröße",
        "lbl_free_space": "Frei auf Ziel",
        "btn_choose_root": "STAMMORDNER WÄHLEN",
        "btn_start": "INGEST STARTEN",
        "status_ready": "Bereit",
        "status_work": "Arbeite...",
        "status_done": "Fertig (Teil)",
        "status_complete": "Komplett (L+R)",
        "status_match": "MATCH: Ergänze ",
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
        # Settings
        "win_settings": "Einstellungen",
        "sec_lang": " Sprache / Language ",
        "sec_advanced": " Erweiterte Einstellungen ",
        "opt_cam_id": "Cam-ID im Dateinamen",
        "opt_sort_day": "Archiv-Sortierung: Nach Drehtagen (Tag_XX)",
        "opt_sort_scene": "Archiv-Sortierung: Nach Szenen (Szene_XX)",
        "lbl_digits_s": "Stellen Szene:", "lbl_digits_e": "Einstell.:", "lbl_digits_t": "Take:",
        "sec_verify": " File Verification & Reports ",
        "opt_verify": "Prüfung aktivieren (MHL & HTML Report erstellen)",
        "opt_thumbs": "Vorschaubilder für HTML-Report generieren (dauert länger)",
        "desc_verify": "Erstellt MHL (Hash List) und HTML Report. Erhöht Datensicherheit und Kopierzeit.",
        "opt_md5": "MD5 (Standard)",
        "opt_xx": "xxHash (High Speed)",
        "opt_sha": "SHA-256 (High Security)",
        "sec_audio": " Audio ",
        "opt_audio_l": "Links", "opt_audio_r": "Rechts", "opt_audio_b": "Beide",
        "opt_strip": "L/R Suffix bei Audio entfernen",
        "sec_help": " Hilfe ",
        "btn_manual": "📖 HANDBUCH ÖFFNEN (PDF)",
        "btn_save": "SPEICHERN"
    },
    "en": {
        "title": "3DCam2Post Bridge v0.9.2 (A1 Patch)",
        "btn_add_source": "+ ADD SOURCE FOLDER",
        "btn_clear_list": "Clear List",
        "lbl_project": "   Project:",
        "lbl_day": "  Day:",
        "col_id": "ID", "col_cam": "Camera", "col_eye": "Eye", "col_size": "Size", "col_target": "Logged Name", "col_trans": "Transfer", "col_stat": "Status",
        "grp_log": " Logging ",
        "lbl_scene": "Scene", "lbl_setting": "Shot", "lbl_take": "Take", "lbl_cam_id": "Cam-ID",
        "grp_hotkeys": " Hotkeys ",
        "hk_scene": "Scene [s]", "hk_setting": "Shot [e]", "hk_remove": "X [Del]", "hk_take_plus": "Take+ [t]", "hk_next": "Confirm & Next [->]",
        "lbl_total_size": "Total Size",
        "lbl_free_space": "Free on target",
        "btn_choose_root": "CHOOSE ROOT FOLDER",
        "btn_start": "START INGEST",
        "status_ready": "Ready",
        "status_work": "Working...",
        "status_done": "Done",
        "status_complete": "Complete (L+R)",
        "status_match": "MATCH: Merging ",
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
        # Settings
        "win_settings": "Settings",
        "sec_lang": " Sprache / Language ",
        "sec_advanced": " Advanced Settings ",
        "opt_cam_id": "Cam-ID in Filename",
        "opt_sort_day": "Archive Sorting: By Shooting Day (Tag_XX)",
        "opt_sort_scene": "Archive Sorting: By Scene (Szene_XX)",
        "lbl_digits_s": "Digits Scene:", "lbl_digits_e": "Shot:", "lbl_digits_t": "Take:",
        "sec_verify": " File Verification & Reports ",
        "opt_verify": "Enable Verification (Create MHL & HTML Reports)",
        "opt_thumbs": "Generate thumbnails for HTML Report (takes extra time)",
        "desc_verify": "Creates MHL (Hash List) and HTML Report. Increases data safety and copy time.",
        "opt_md5": "MD5 (Standard)",
        "opt_xx": "xxHash (High Speed)",
        "opt_sha": "SHA-256 (High Security)",
        "sec_audio": " Audio ",
        "opt_audio_l": "Left", "opt_audio_r": "Right", "opt_audio_b": "Both",
        "opt_strip": "Remove L/R Suffix from Audio",
        "sec_help": " Help ",
        "btn_manual": "📖 OPEN MANUAL (PDF)",
        "btn_save": "SAVE"
    }
}

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

class IngestProApp:
    def __init__(self, root):
        self.root = root
        self.root.withdraw()
        
        self.os_type = platform.system()
        self.is_windows = (self.os_type == "Windows")

        ffmpeg_bin = "ffmpeg.exe" if self.is_windows else "ffmpeg"
        self.ffmpeg_path = resource_path(ffmpeg_bin)
        if not os.path.exists(self.ffmpeg_path):
            sys_ffmpeg = shutil.which(ffmpeg_bin)
            if sys_ffmpeg:
                self.ffmpeg_path = sys_ffmpeg

        self.defaults = {
            "language": "de", 
            "use_cam_id": False,
            "verify_copy": False,  
            "generate_thumbs": True,
            "hash_algo": "md5",
            "padding_s": 2, "padding_e": 2, "padding_t": 3,
            "sort_mode": "Drehtage",
            "stammordner": "",
            "audio_source": "Links",
            "strip_audio_eye": False,
            "copy_video": True,
            "copy_audio": True
        }
        self.load_config()

        self.root.title(self.tr("title"))

        app_w, app_h = 1450, 950
        self.center_window(self.root, app_w, app_h)
        self.root.deiconify()
        
        self.temp_thumb_dir = Path(tempfile.gettempdir()) / "3D_Ingest_Thumbs"
        self.temp_thumb_dir.mkdir(parents=True, exist_ok=True)

        self.thumb_queue = queue.Queue()
        self.thumb_thread = threading.Thread(target=self.preview_worker, daemon=True)
        self.thumb_thread.start()

        self.all_clips = []
        self.manifest_data = {} 
        self.current_index = -1
        
        # UI Vars
        self.project_name = tk.StringVar(value="Projekt_Name")
        self.scene = tk.StringVar(value="1")
        self.setting = tk.StringVar(value="1")
        self.take = tk.StringVar(value="1")
        self.cam_id = tk.StringVar(value="A")
        self.day = tk.StringVar(value="1")
        
        self.status_msg = tk.StringVar(value=self.tr("status_ready"))
        self.target_display = tk.StringVar(value=self.tr("target_manual"))
        self.total_size_str = tk.StringVar(value=f"{self.tr('lbl_total_size')}: 0.00 GB")
        self.disk_space_str = tk.StringVar(value=f"{self.tr('lbl_free_space')}: --")

        self.project_name.trace_add("write", lambda *args: (self.refresh_all_target_names(), self.load_manifest()))

        self.setup_ui()
        self.bind_hotkeys()
        self.apply_config_ui()
        
        if self.defaults["stammordner"]:
            self.load_manifest()

    def tr(self, key):
        lang_code = self.defaults.get("language", "de")
        lang_dict = TRANSLATIONS.get(lang_code, TRANSLATIONS["de"])
        return lang_dict.get(key, f"MISSING: {key}")

    def update_ui_texts(self):
        self.root.title(self.tr("title"))
        self.btn_add_src.config(text=self.tr("btn_add_source"))
        self.btn_clr_lst.config(text=self.tr("btn_clear_list"))
        self.lbl_proj_title.config(text=self.tr("lbl_project"))
        self.adv_day_label.config(text=self.tr("lbl_day"))

        headers = [
            self.tr("col_id"), self.tr("col_cam"), self.tr("col_eye"), 
            self.tr("col_size"), self.tr("col_target"), self.tr("col_trans"), self.tr("col_stat")
        ]
        columns = ("pair", "cam", "eye", "size", "target", "transfer", "status")
        for col, head in zip(columns, headers):
            self.tree.heading(col, text=head)

        self.log_frame.config(text=self.tr("grp_log"))
        self.lbl_sc.config(text=self.tr("lbl_scene"))
        self.lbl_set.config(text=self.tr("lbl_setting"))
        self.lbl_tk.config(text=self.tr("lbl_take"))
        self.cam_id_label.config(text=self.tr("lbl_cam_id"))

        self.pad_frame.config(text=self.tr("grp_hotkeys"))
        self.btn_hk_scene.config(text=self.tr("hk_scene"))
        self.btn_hk_setting.config(text=self.tr("hk_setting"))
        self.btn_hk_remove.config(text=self.tr("hk_remove"))
        self.btn_hk_take.config(text=self.tr("hk_take_plus"))
        self.btn_hk_next.config(text=self.tr("hk_next"))

        self.btn_start.config(text=self.tr("btn_start"))
        self.btn_manual_target.config(text=self.tr("btn_choose_root"))
        
        self.apply_config_ui()
        self.calculate_total_transfer_size()
        
        if self.status_msg.get() in [TRANSLATIONS["de"]["status_ready"], TRANSLATIONS["en"]["status_ready"]]:
            self.status_msg.set(self.tr("status_ready"))

    def center_window(self, win, width, height):
        screen_width = win.winfo_screenwidth()
        screen_height = win.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        win.geometry(f'{width}x{height}+{x}+{y}')

    # --- CONFIG & MANIFEST ---
    def load_config(self):
        c_path = Path(resource_path(CONFIG_FILE))
        if c_path.exists():
            try:
                with open(c_path, "r") as f:
                    self.defaults.update(json.load(f))
            except Exception as e:
                print(f"Config Load Error: {e}")

    def save_config(self):
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(self.defaults, f, indent=4)
        except Exception as e:
            print(f"Config Save Error: {e}")

    def get_manifest_path(self):
        if not self.defaults["stammordner"] or not self.project_name.get():
            return None
        return Path(self.defaults["stammordner"]) / self.project_name.get() / MANIFEST_FILE

    def load_manifest(self, *args):
        path = self.get_manifest_path()
        self.manifest_data = {}
        if path and path.exists():
            try:
                with open(path, "r") as f:
                    self.manifest_data = json.load(f)
                self.sync_clips_with_manifest()
            except Exception as e:
                print(f"Manifest Load Error: {e}")

    def save_manifest(self):
        path = self.get_manifest_path()
        if path:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                with open(path, "w") as f:
                    json.dump(self.manifest_data, f, indent=4)
            except Exception as e:
                print(f"Manifest Save Error: {e}")

    def cleanup_manifest_if_done(self):
        if not self.manifest_data: return False
        all_done = True
        for k, v in self.manifest_data.items():
            if v.get("status_L") != "done" or v.get("status_R") != "done":
                all_done = False
                break
        if all_done:
            path = self.get_manifest_path()
            if path and path.exists():
                try:
                    os.remove(path)
                    return True
                except Exception: pass
        return False

    def open_manual(self):
        lang = self.defaults.get("language", "de")
        filename = "3DC2P Manual DE.pdf" if lang == "de" else "3DC2P Manual ENG.pdf"
        path = Path(resource_path(filename))
        if not path.exists():
            messagebox.showerror(self.tr("title"), f"{self.tr('err_manual')}:\n{path}")
            return
        try:
            if self.is_windows: os.startfile(path)
            elif self.os_type == "Darwin": subprocess.run(["open", str(path)])
            else: subprocess.run(["xdg-open", str(path)])
        except Exception: pass

    # --- UI SETUP ---
    def setup_ui(self):
        top_frame = tk.Frame(self.root, pady=10, padx=15)
        top_frame.pack(fill="x")
        
        self.btn_add_src = tk.Button(top_frame, text=self.tr("btn_add_source"), command=self.add_source, 
                  bg="#0078d7", fg="white", font=("Arial", 10, "bold"))
        self.btn_add_src.pack(side=tk.LEFT)
        
        self.btn_clr_lst = tk.Button(top_frame, text=self.tr("btn_clear_list"), command=self.clear_list, 
                  bg="#6c757d", fg="white", font=("Arial", 9))
        self.btn_clr_lst.pack(side=tk.LEFT, padx=10)
        
        self.lbl_proj_title = tk.Label(top_frame, text=self.tr("lbl_project"))
        self.lbl_proj_title.pack(side=tk.LEFT)
        tk.Entry(top_frame, textvariable=self.project_name, width=20, 
                 font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)
        
        self.adv_day_label = tk.Label(top_frame, text=self.tr("lbl_day"))
        self.adv_day_label.pack(side=tk.LEFT)
        self.adv_day_entry = tk.Entry(top_frame, textvariable=self.day, width=4)
        self.adv_day_entry.pack(side=tk.LEFT, padx=5)
        
        self.btn_settings = tk.Button(top_frame, text="⚙", font=("Arial", 14), 
                                      command=self.open_settings, relief=tk.FLAT)
        self.btn_settings.pack(side=tk.RIGHT)

        paned = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, sashwidth=4)
        paned.pack(fill="both", expand=True, padx=10, pady=5)

        list_frame = tk.Frame(paned)
        columns = ("pair", "cam", "eye", "size", "target", "transfer", "status")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings")
        
        headers = [
            self.tr("col_id"), self.tr("col_cam"), self.tr("col_eye"), 
            self.tr("col_size"), self.tr("col_target"), self.tr("col_trans"), self.tr("col_stat")
        ]
        widths = [50, 70, 60, 80, 300, 80, 80]
        for col, head, w in zip(columns, headers, widths):
            self.tree.heading(col, text=head)
            self.tree.column(col, width=w, anchor="center" if col == "transfer" else "w")

        # Color Tags
        self.tree.tag_configure('match', foreground='#e6a300') # Gold
        self.tree.tag_configure('complete', foreground='#28a745') # Grün
        self.tree.tag_configure('normal', foreground='black')

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill="both", expand=True)
        scrollbar.pack(side=tk.RIGHT, fill="y")
        self.tree.bind("<<TreeviewSelect>>", self.on_clip_selected)
        paned.add(list_frame)

        self.right_frame = tk.Frame(paned, padx=20)
        paned.add(self.right_frame)
        
        self.canvas = tk.Canvas(self.right_frame, width=480, height=270, bg="#1a1a1a")
        self.canvas.pack(pady=5)
        
        self.log_frame = tk.LabelFrame(self.right_frame, text=self.tr("grp_log"), pady=10, padx=10, font=("Arial", 10, "bold"))
        self.log_frame.pack(fill="x")
        f_font = ("Arial", 22, "bold")
        
        self.lbl_sc = tk.Label(self.log_frame, text=self.tr("lbl_scene"))
        self.lbl_sc.grid(row=0, column=0)
        tk.Entry(self.log_frame, textvariable=self.scene, font=f_font, width=4, justify="center").grid(row=1, column=0, padx=8)
        
        self.lbl_set = tk.Label(self.log_frame, text=self.tr("lbl_setting"))
        self.lbl_set.grid(row=0, column=1)
        tk.Entry(self.log_frame, textvariable=self.setting, font=f_font, width=4, justify="center").grid(row=1, column=1, padx=8)
        
        self.lbl_tk = tk.Label(self.log_frame, text=self.tr("lbl_take"))
        self.lbl_tk.grid(row=0, column=2)
        tk.Entry(self.log_frame, textvariable=self.take, font=f_font, width=4, justify="center").grid(row=1, column=2, padx=8)
        
        self.cam_id_label = tk.Label(self.log_frame, text=self.tr("lbl_cam_id"))
        self.cam_id_label.grid(row=0, column=3, padx=20)
        self.cam_id_entry = tk.Entry(self.log_frame, textvariable=self.cam_id, font=f_font, width=3, justify="center", fg="#005a9e")
        self.cam_id_entry.grid(row=1, column=3, padx=20)

        self.pad_frame = tk.LabelFrame(self.right_frame, text=self.tr("grp_hotkeys"), pady=10, padx=10, font=("Arial", 9, "bold"))
        self.pad_frame.pack(fill="x", pady=10)
        btn_style = {"font": ("Arial", 9, "bold"), "height": 2, "fg": "white"}
        
        self.btn_hk_scene = tk.Button(self.pad_frame, text=self.tr("hk_scene"), bg="#005a9e", command=self.hk_new_scene, **btn_style)
        self.btn_hk_scene.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        self.btn_hk_setting = tk.Button(self.pad_frame, text=self.tr("hk_setting"), bg="#c87800", command=self.hk_new_setting, **btn_style)
        self.btn_hk_setting.grid(row=0, column=1, sticky="nsew", padx=2, pady=2)
        self.btn_hk_remove = tk.Button(self.pad_frame, text=self.tr("hk_remove"), bg="#a52a2a", command=self.hk_toggle_transfer, **btn_style)
        self.btn_hk_remove.grid(row=1, column=0, sticky="nsew", padx=2, pady=2)
        self.btn_hk_take = tk.Button(self.pad_frame, text=self.tr("hk_take_plus"), bg="#5a5a5a", command=self.hk_plus_take, **btn_style)
        self.btn_hk_take.grid(row=1, column=1, sticky="nsew", padx=2, pady=2)
        self.btn_hk_next = tk.Button(self.pad_frame, text=self.tr("hk_next"), bg="#28a745", command=self.hk_confirm_and_next, **btn_style)
        self.btn_hk_next.grid(row=1, column=2, sticky="nsew", padx=2, pady=2)
        
        self.pad_frame.columnconfigure((0,1,2), weight=1)

        ingest_frame = tk.Frame(self.right_frame)
        ingest_frame.pack(fill="x", side=tk.BOTTOM, pady=10)
        tk.Label(ingest_frame, textvariable=self.total_size_str, font=("Arial", 10, "bold"), fg="#0078d7").pack(anchor="e")
        self.progress = ttk.Progressbar(ingest_frame, orient="horizontal", mode="determinate")
        self.progress.pack(fill="x", pady=5)
        self.lbl_target_path = tk.Label(ingest_frame, textvariable=self.target_display, font=("Arial", 8, "italic"), wraplength=400)
        self.lbl_target_path.pack()
        self.btn_manual_target = tk.Button(ingest_frame, text=self.tr("btn_choose_root"), command=self.choose_stammordner_manual, bg="#218838", fg="white", font=("Arial", 10, "bold"), pady=5)
        self.btn_manual_target.pack(fill="x", pady=5)
        self.btn_start = tk.Button(ingest_frame, text=self.tr("btn_start"), bg="#28a745", fg="white", font=("Arial", 12, "bold"), pady=12, command=self.start_ingest)
        self.btn_start.pack(fill="x")

        status_bar = tk.Frame(self.root, bd=1, relief=tk.SUNKEN)
        status_bar.pack(side=tk.BOTTOM, fill="x")
        tk.Label(status_bar, textvariable=self.status_msg, anchor="w", padx=10).pack(side=tk.LEFT)
        tk.Label(status_bar, textvariable=self.disk_space_str, anchor="e", padx=10, fg="#555").pack(side=tk.RIGHT)

    def bind_hotkeys(self):
        self.root.bind("<Right>", self.hk_confirm_and_next)
        self.root.bind("<Left>", self.hk_prev_clip)
        self.root.bind("<Up>", lambda e: self.select_rel(-1))
        self.root.bind("<Down>", lambda e: self.select_rel(1))
        self.root.bind("<Delete>", self.hk_toggle_transfer)
        self.root.bind("<BackSpace>", self.hk_toggle_transfer)
        self.root.bind("t", self.hk_plus_take)
        self.root.bind("T", self.hk_plus_take)
        self.root.bind("e", self.hk_new_setting)
        self.root.bind("E", self.hk_new_setting)
        self.root.bind("s", self.hk_new_scene)
        self.root.bind("S", self.hk_new_scene)

    def apply_config_ui(self):
        if self.defaults["use_cam_id"]: 
            self.cam_id_label.grid(row=0, column=3, padx=20)
            self.cam_id_entry.grid(row=1, column=3, padx=20)
        else: 
            self.cam_id_label.grid_forget()
            self.cam_id_entry.grid_forget()

        self.target_display.set(f"Stamm: {self.defaults['stammordner']}" if self.defaults['stammordner'] else self.tr("err_no_root"))
        self.update_disk_info()
        self.refresh_all_target_names()

    # --- SETTINGS WINDOW ---
    def open_settings(self):
        win = tk.Toplevel(self.root)
        win.title(self.tr("win_settings"))
        self.center_window(win, 600, 950)
        win.grab_set()

        lang_sect = tk.LabelFrame(win, text=self.tr("sec_lang"), padx=10, pady=10, font=("Arial", 10, "bold"))
        lang_sect.pack(fill="x", padx=15, pady=5)
        lang_var = tk.StringVar(value=self.defaults.get("language", "de"))
        tk.Radiobutton(lang_sect, text="Deutsch", variable=lang_var, value="de").pack(side=tk.LEFT, padx=10)
        tk.Radiobutton(lang_sect, text="English", variable=lang_var, value="en").pack(side=tk.LEFT, padx=10)
        
        adv_sect = tk.LabelFrame(win, text=self.tr("sec_advanced"), padx=10, pady=10, font=("Arial", 10, "bold"))
        adv_sect.pack(fill="x", padx=15, pady=5)
        cam_var = tk.BooleanVar(value=self.defaults["use_cam_id"])
        tk.Checkbutton(adv_sect, text=self.tr("opt_cam_id"), variable=cam_var).pack(anchor="w", pady=(0, 5))
        
        tk.Label(adv_sect, text="---", fg="#ccc").pack(fill="x", pady=2)
        sort_var = tk.StringVar(value=self.defaults["sort_mode"])
        tk.Radiobutton(adv_sect, text=self.tr("opt_sort_day"), variable=sort_var, value="Drehtage").pack(anchor="w")
        tk.Radiobutton(adv_sect, text=self.tr("opt_sort_scene"), variable=sort_var, value="Szenen").pack(anchor="w")

        tk.Label(adv_sect, text="---", fg="#ccc").pack(fill="x", pady=2)
        pad_frame = tk.Frame(adv_sect)
        pad_frame.pack(anchor="w", pady=5)
        pad_s = ttk.Combobox(pad_frame, values=[1,2,3], width=3)
        pad_s.set(self.defaults["padding_s"])
        pad_e = ttk.Combobox(pad_frame, values=[1,2,3], width=3)
        pad_e.set(self.defaults["padding_e"])
        pad_t = ttk.Combobox(pad_frame, values=[2,3,4,5], width=3)
        pad_t.set(self.defaults["padding_t"])
        tk.Label(pad_frame, text=self.tr("lbl_digits_s")).pack(side=tk.LEFT)
        pad_s.pack(side=tk.LEFT, padx=(5, 15))
        tk.Label(pad_frame, text=self.tr("lbl_digits_e")).pack(side=tk.LEFT)
        pad_e.pack(side=tk.LEFT, padx=(5, 15))
        tk.Label(pad_frame, text=self.tr("lbl_digits_t")).pack(side=tk.LEFT)
        pad_t.pack(side=tk.LEFT, padx=5)

        verify_sect = tk.LabelFrame(win, text=self.tr("sec_verify"), padx=10, pady=10, font=("Arial", 10, "bold"))
        verify_sect.pack(fill="x", padx=15, pady=5)
        verify_var = tk.BooleanVar(value=self.defaults["verify_copy"])
        tk.Checkbutton(verify_sect, text=self.tr("opt_verify"), variable=verify_var, font=("Arial", 10, "bold")).pack(anchor="w")
        
        thumb_var = tk.BooleanVar(value=self.defaults.get("generate_thumbs", True))
        tk.Checkbutton(verify_sect, text=self.tr("opt_thumbs"), variable=thumb_var).pack(anchor="w", padx=20)
        
        tk.Label(verify_sect, text=self.tr("desc_verify"), font=("Arial", 8), fg="#666", justify=tk.LEFT).pack(anchor="w", padx=20, pady=(0, 5))
        
        algo_var = tk.StringVar(value=self.defaults.get("hash_algo", "md5"))
        tk.Radiobutton(verify_sect, text=self.tr("opt_md5"), variable=algo_var, value="md5").pack(anchor="w", padx=20)
        xx_text = self.tr("opt_xx")
        xx_state = "normal" if HAS_XXHASH else "disabled"
        if not HAS_XXHASH: xx_text += " [Nicht installiert/Not installed]"
        tk.Radiobutton(verify_sect, text=xx_text, variable=algo_var, value="xxhash", state=xx_state).pack(anchor="w", padx=20)
        tk.Radiobutton(verify_sect, text=self.tr("opt_sha"), variable=algo_var, value="sha256").pack(anchor="w", padx=20)

        audio_sect = tk.LabelFrame(win, text=self.tr("sec_audio"), padx=10, pady=10)
        audio_sect.pack(fill="x", padx=15, pady=5)
        audio_var = tk.StringVar(value=self.defaults["audio_source"])
        tk.Radiobutton(audio_sect, text=self.tr("opt_audio_l"), variable=audio_var, value="Links").pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(audio_sect, text=self.tr("opt_audio_r"), variable=audio_var, value="Rechts").pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(audio_sect, text=self.tr("opt_audio_b"), variable=audio_var, value="Beide").pack(side=tk.LEFT, padx=5)
        strip_audio_var = tk.BooleanVar(value=self.defaults["strip_audio_eye"])
        tk.Checkbutton(audio_sect, text=self.tr("opt_strip"), variable=strip_audio_var).pack(anchor="w", pady=5)

        help_sect = tk.LabelFrame(win, text=self.tr("sec_help"), padx=10, pady=10, font=("Arial", 10, "bold"))
        help_sect.pack(fill="x", padx=15, pady=20)
        tk.Button(help_sect, text=self.tr("btn_manual"), bg="#17a2b8", fg="white", font=("Arial", 10, "bold"), pady=8, command=self.open_manual).pack(fill="x")
        
        def save():
            self.defaults.update({
                "language": lang_var.get(),
                "use_cam_id": cam_var.get(),
                "verify_copy": verify_var.get(),
                "generate_thumbs": thumb_var.get(),
                "hash_algo": algo_var.get(),
                "audio_source": audio_var.get(),
                "strip_audio_eye": strip_audio_var.get(),
                "padding_s": int(pad_s.get()),
                "padding_e": int(pad_e.get()),
                "padding_t": int(pad_t.get()),
                "sort_mode": sort_var.get()
            })
            self.save_config()
            self.update_ui_texts()
            win.destroy()
            
        tk.Button(win, text=self.tr("btn_save"), bg="#28a745", fg="white", font=("Arial", 10, "bold"), pady=10, command=save).pack(side=tk.BOTTOM, pady=20, fill="x", padx=20)

    # --- HELPERS ---
    def update_disk_info(self):
        path = self.defaults["stammordner"]
        if path and os.path.exists(path):
            try:
                usage = shutil.disk_usage(path)
                free_gb = usage.free / (1024**3)
                self.disk_space_str.set(f"{self.tr('lbl_free_space')}: {free_gb:.2f} GB")
                return usage.free
            except Exception: pass
        self.disk_space_str.set(f"{self.tr('lbl_free_space')}: --")
        return None

    def calculate_total_transfer_size(self):
        total = sum(c.get('size_bytes', 0) for c in self.all_clips if c['transfer'] and not c['done'])
        self.total_size_str.set(f"{self.tr('lbl_total_size')}: {total / (1024**3):.2f} GB")
        return total

    # --- CHECKSUM LOGIC ---
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

    # --- REPORTING ENGINE ---
    def generate_reports(self, processed_clips, report_dir):
        if not processed_clips: return
        
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ts_file = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        
        mhl_name = f"Transfer_{ts_file}.mhl"
        mhl_path = report_dir / mhl_name
        self.write_mhl(mhl_path, processed_clips, timestamp)
        
        html_name = f"Report_{self.project_name.get()}_{ts_file}.html"
        html_path = report_dir / html_name
        self.write_html_report(html_path, processed_clips, timestamp)

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

    def write_html_report(self, path, clips, timestamp):
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
        
        # 1. Group Clips by ID
        grouped = {}
        cnt_vid = 0; cnt_aud = 0; cnt_xml = 0
        
        for item in clips:
            if item['type'] == 'video': cnt_vid += 1
            elif item['type'] == 'audio': cnt_aud += 1
            elif item['type'] == 'xml': cnt_xml += 1
            
            # Grouping Logic
            if item['type'] == 'video':
                cid = item['clip_id']
                if cid not in grouped: grouped[cid] = {'L': None, 'R': None, 'meta': {}, 'name': ''}
                
                eye = item['eye']
                grouped[cid][eye] = item
                # Übernehme Metadaten vom ersten gefundenen Clip (L oder R)
                if not grouped[cid]['meta']: 
                    grouped[cid]['meta'] = item.get('meta', {})
                    grouped[cid]['name'] = item['name'].replace(f"_{eye}", "") # Base Name ohne Eye Suffix
        
        rows = ""
        for cid, data in grouped.items():
            l_item = data.get('L')
            r_item = data.get('R')
            
            # Falls nur ein Auge vorhanden (z.B. Einzel-Ingest oder Fehler), nimm das vorhandene als "Main"
            main = l_item if l_item else r_item
            if not main: continue 
            
            meta = data['meta']
            
            # Thumbs (nur einmal, bevorzugt L)
            t1 = self.get_thumb_base64(cid, 1)
            t2 = self.get_thumb_base64(cid, 2)
            t3 = self.get_thumb_base64(cid, 3)
            
            # Paths & Hashes Construction
            paths_html = ""
            hashes_html = ""
            
            if l_item:
                paths_html += f"<span class='eye-badge eye-L'>L</span> <span class='path'>{l_item['path']}</span><br>"
                hashes_html += f"<span class='eye-badge eye-L'>L</span> <span class='tech'>{l_item['hash']}</span><br>"
            if r_item:
                paths_html += f"<span class='eye-badge eye-R'>R</span> <span class='path'>{r_item['path']}</span>"
                hashes_html += f"<span class='eye-badge eye-R'>R</span> <span class='tech'>{r_item['hash']}</span>"
            
            # Orig Names
            orig_html = ""
            if l_item: orig_html += f"L: {l_item.get('original_name', '-')}<br>"
            if r_item: orig_html += f"R: {r_item.get('original_name', '-')}"

            # Timecode check
            tc_display = meta.get('start_tc', 'N/A')
            if tc_display == "00:00:00:00" and ".MTS" in main['original_name'].upper():
                 tc_display = "N/A" # A1 meist kein valider SMPTE TC im File-Header

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
                <strong>Project:</strong> {self.project_name.get()}<br>
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
        """Generiert 3 Thumbnails für den Report (10%, 50%, 90%)."""
        if not os.path.exists(self.ffmpeg_path): return
        
        # Check if thumbs already exist (optimization)
        if (self.temp_thumb_dir / f"t_{clip_id}_1.jpg").exists(): return

        # Fallback wenn duration fehlerhaft
        try:
            dur = float(duration_sec) if duration_sec else 0
            if dur < 1: dur = 5 # Fallback
        except: dur = 5
        
        # Berechnung der Zeitpunkte (10%, 50%, 90% der Dauer) + Start Offset
        # WICHTIG: A1 .mts hat oft einen Offset. Wir berechnen relativ zur Datei.
        # -ss vor input macht seek schnell und reset timestamp. 
        # Wir nehmen timestamps relativ zum Dateistart (0).
        timestamps = [
            dur * 0.1,
            dur * 0.5,
            dur * 0.9
        ]
        
        c_flags = 0x08000000 if self.is_windows else 0
        
        for i, ts in enumerate(timestamps):
            out = self.temp_thumb_dir / f"t_{clip_id}_{i+1}.jpg"
            # Nutze -ss VOR -i für schnelles seeking, aber wir müssen sicherstellen
            # dass es nicht genau auf 0 fällt bei MTS, da manchmal frames fehlen.
            # ts ist hier relativ zum Start des Files.
            subprocess.run([
                self.ffmpeg_path, '-y', '-ss', str(ts), '-i', str(video_path), 
                '-frames:v', '1', '-s', '320x180', str(out)
            ], stderr=subprocess.DEVNULL, creationflags=c_flags)

    # --- INGEST LOGIC ---
    def choose_stammordner_manual(self):
        p = filedialog.askdirectory()
        if p:
            self.defaults["stammordner"] = p
            self.save_config()
            self.target_display.set(f"Stamm: {p}")
            self.update_disk_info()
            self.load_manifest()

    def start_ingest(self):
        if not self.defaults["stammordner"]:
            messagebox.showwarning(self.tr("title"), self.tr("err_no_root"))
            return
        
        self.load_manifest()
        base = Path(self.defaults["stammordner"]) / self.project_name.get()
        
        to_copy = []
        for i, item_id in enumerate(self.tree.get_children()):
            c = next((cl for cl in self.all_clips if cl['id'] == self.tree.item(item_id, "values")[0]), None)
            if c and c['transfer'] and not c['done'] and c['logged']:
                to_copy.append((c, item_id, i+1))

        if not to_copy:
            messagebox.showinfo("Info", self.tr("msg_no_copy"))
            return

        needed = self.calculate_total_transfer_size()
        free = self.update_disk_info() or 0
        limit_100gb = 100 * (1024**3)

        if free < needed:
            messagebox.showerror(self.tr("err_space"), f"{self.tr('err_space')}\nBenötigt: {needed/1024**3:.2f}GB\nFrei: {free/1024**3:.2f}GB")
            return
        if free < limit_100gb:
            if not messagebox.askyesno("Warnung", f"{self.tr('warn_space')} ({free/1024**3:.2f}GB). Trotzdem starten?"): return

        report_dir = None
        if self.defaults["verify_copy"]:
            if self.defaults["sort_mode"] == "Drehtage":
                    sub_folder = f"Tag_{self.day.get().zfill(2)}"
                    report_dir = base / sub_folder
            else:
                report_dir = base
            try: report_dir.mkdir(parents=True, exist_ok=True)
            except: pass

        self.btn_start.config(state="disabled")
        threading.Thread(target=self.ingest_worker, args=(to_copy, base, report_dir), daemon=True).start()

    def ingest_worker(self, clips_data, base_target, report_dir):
        total_clips = len(clips_data)
        processed_files_log = []
        
        for i, (clip, item_id, easy_idx) in enumerate(clips_data):
            self.root.after(0, lambda id=item_id: self.tree.set(id, "status", self.tr("status_work")))
            
            sub = f"Tag_{self.day.get().zfill(2)}" if self.defaults["sort_mode"] == "Drehtage" else f"Szene_{str(clip['scene']).zfill(self.defaults['padding_s'])}"
            current_root = base_target / sub
            
            bn = self.format_name(clip, easy_idx)
            cid = clip['id']
            
            if cid not in self.manifest_data:
                self.manifest_data[cid] = {
                    "target_name": bn,
                    "scene": clip['scene'], "setting": clip['setting'], "take": clip['take'],
                    "status_L": "missing", "status_R": "missing"
                }

            # Kopiere für beide Augen (sofern Pfad vorhanden)
            for eye in ['L', 'R']:
                src = clip[f'path_{eye}']
                if src and Path(src).exists():
                    src_path = Path(src)
                    
                    # ENTSCHEIDUNG: P2 (MXF) vs FLAT (MTS/MP4/MOV)
                    # P1 = MXF (P2 Struktur), A1 = MTS (Flat Struktur)
                    is_p2 = src_path.suffix.lower() == '.mxf'
                    
                    if is_p2:
                        # P2 Struktur (für AG-3DP1)
                        dest_folder = current_root / ("LINKS" if eye == "L" else "RECHTS") / "CONTENTS"
                        for d in ["VIDEO", "CLIP", "AUDIO"]: (dest_folder/d).mkdir(parents=True, exist_ok=True)
                        target_video = dest_folder / "VIDEO" / f"{bn}_{eye}{src_path.suffix}"
                    else:
                        # Flat Struktur (für AG-3DA1)
                        # Hier kommen .mts Dateien direkt in den LINKS/RECHTS Ordner,
                        # OHNE CONTENTS/VIDEO Struktur.
                        dest_folder = current_root / ("LINKS" if eye == "L" else "RECHTS")
                        dest_folder.mkdir(parents=True, exist_ok=True)
                        target_video = dest_folder / f"{bn}_{eye}{src_path.suffix}"

                    # Copy
                    v_hash = self._safe_copy(src_path, target_video)
                    
                    # Metadata Extraction
                    if is_p2:
                        meta_data = self.extract_p2_metadata(src_path)
                    else:
                        meta_data = self.extract_ffmpeg_metadata(src_path)
                    
                    # Report Thumbnails generieren (nur 1x pro Clip-ID)
                    if self.defaults.get("verify_copy", False) and self.defaults.get("generate_thumbs", True):
                        self.create_report_thumbnails(
                            target_video, 
                            cid, 
                            meta_data.get('duration_sec'), 
                            meta_data.get('fps'),
                            meta_data.get('start_sec', 0)
                        )

                    # Log Video
                    if v_hash:
                        processed_files_log.append({
                            'name': target_video.name, 'path': str(target_video),
                            'hash': v_hash, 'algo': self.defaults.get('hash_algo', 'md5'),
                            'size': target_video.stat().st_size, 'type': 'video',
                            'clip_id': cid, 'eye': eye, 'meta': meta_data,
                            'original_name': src_path.name
                        })

                    # P2 XML Handling (Nur für P1/MXF relevant)
                    if is_p2:
                        xml_target = self.process_xml_p2(src_path, bn, dest_folder/"CLIP", eye)
                        if xml_target and v_hash:
                             xh = self.generate_checksum(xml_target, self.defaults.get('hash_algo', 'md5'))
                             processed_files_log.append({
                                'path': str(xml_target), 'hash': xh, 'algo': self.defaults.get('hash_algo', 'md5'),
                                'size': xml_target.stat().st_size, 'type': 'xml'
                            })

                    # P2 Audio Handling (Nur für P1/MXF relevant)
                    if is_p2 and self.defaults["copy_audio"]: 
                        audio_files = self.copy_audio_p2(src_path, bn, eye, dest_folder/"AUDIO")
                        for af in audio_files:
                             if v_hash:
                                ah = self.generate_checksum(af, self.defaults.get('hash_algo', 'md5'))
                                processed_files_log.append({
                                    'path': str(af), 'hash': ah, 'algo': self.defaults.get('hash_algo', 'md5'),
                                    'size': af.stat().st_size, 'type': 'audio'
                                })
                    
                    self.manifest_data[cid][f"status_{eye}"] = "done"
                    self.save_manifest() 

            clip['done'] = True
            progress_pct = int((i + 1) / total_clips * 100)
            self.root.after(0, lambda id=item_id, p=progress_pct: (self.tree.set(id, "status", self.tr("status_done")), self.progress.configure(value=p)))
            
        if self.defaults["verify_copy"]:
            self.generate_reports(processed_files_log, report_dir)

        # Generiere automatisch die Resolve CSV (immer, unabhängig von verify_copy)
        self.generate_resolve_csv(processed_files_log, Path(self.target.get()))

        cleaned = self.cleanup_manifest_if_done()
        self.root.after(0, self.sync_clips_with_manifest)

        final_msg = self.tr("msg_complete")
        if self.defaults["verify_copy"]: final_msg += f"\n{self.tr('msg_report')}"
        if cleaned: final_msg += f"\n{self.tr('msg_clean')}"
        
        self.root.after(0, lambda: (
            messagebox.showinfo("Ingest", final_msg),
            self.btn_start.config(state="normal"),
            self.progress.configure(value=0)
        ))

    def _safe_copy(self, src, dst):
        try:
            algo = self.defaults.get("hash_algo", "md5")
            src_hash = None
            if self.defaults["verify_copy"]:
                self.root.after(0, lambda: self.status_msg.set(f"Prüfe Quelle ({algo.upper()}): {src.name}..."))
                src_hash = self.generate_checksum(src, algo)

            self.root.after(0, lambda: self.status_msg.set(f"Kopiere: {src.name}..."))
            shutil.copy2(src, dst)
            
            if src.stat().st_size != dst.stat().st_size:
                raise IOError(f"Größenfehler: {src.name}")

            if self.defaults["verify_copy"] and src_hash:
                self.root.after(0, lambda: self.status_msg.set(f"Verifiziere Ziel ({algo.upper()}): {dst.name}..."))
                dst_hash = self.generate_checksum(dst, algo)
                if src_hash != dst_hash:
                    raise IOError(f"CHECKSUM ERROR bei {dst.name}")
                return dst_hash
            return None

        except Exception as e:
            print(f"Copy Error {src}: {e}")
            self.root.after(0, lambda e=e: self.status_msg.set(f"Fehler: {e}"))
            return None

    def generate_resolve_csv(self, log_data, dest_folder):
        """Erstellt eine Resolve-kompatible CSV-Datei mit Timecodes für alle importierten Clips"""
        try:
            csv_path = dest_folder / "Resolve_Timecode_Import.csv"
            
            # Sammle alle validen Timecodes
            # Nutze ein dict um Duplikate zu vermeiden, falls ein File mehrfach auftaucht
            tc_map = {}
            for item in log_data:
                # final_name z.B. "Project_S01_E01_T01_L.mxf"
                file_name = item.get('file')
                start_tc = item.get('start_tc')
                if file_name and start_tc and start_tc != "00:00:00:00" and start_tc != "":
                    tc_map[file_name] = start_tc
            
            if not tc_map:
                return # Keine validen P2/TC Metadaten gefunden, keine CSV nötig

            import csv
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['File Name', 'Start TC'])
                for fname, tc in tc_map.items():
                    writer.writerow([fname, tc])
            
            print(f"Resolve CSV erfolgreich generiert: {csv_path}")
        except Exception as e:
            print(f"Fehler bei der Resolve CSV Generierung: {e}")

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
            
            # 1. Parse Duration & Start
            # Regex angepasst für variable Leerzeichen und das Komma
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
            
            # 2. Parse Stream info
            # Video: h264 (High)... 1920x1080 ... 25 fps
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
            
            # 3. Timecode check
            # Normalerweise steht Timecode in einem Metadata Feld. A1 hat das oft nicht.
            # Wir lassen start_tc standardmäßig auf N/A, es sei denn wir finden explizit:
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
            src_xml = vid_path.parent.parent / "CLIP" / f"{vid_path.stem}.XML"
            if not src_xml.exists(): return meta
            
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
            
            # Duration String Calc
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
        except Exception: return None

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
            for t in range(4):
                search_name = f"{raw_base}{t:02d}.MXF".upper()
                for f in audio_src_dir.iterdir():
                    if f.name.upper() == search_name:
                        suffix = f"{t:02d}"
                        final_name = f"{bn}_{suffix}.MXF" if self.defaults["strip_audio_eye"] else f"{bn}_{eye}{suffix}.MXF"
                        target = Path(dst) / final_name
                        self._safe_copy(f, target)
                        copied_files.append(target)
        except Exception: pass
        return copied_files

    # --- SCANNING & SYNC ---
    def add_source(self):
        p = filedialog.askdirectory()
        if p: threading.Thread(target=self.scan_folder, args=(p,), daemon=True).start()

    def scan_folder(self, root_path):
        found = []
        root_path = Path(root_path)
        for root, dirs, files in os.walk(root_path):
            # Prüfe auf VIDEO (P2/MXF) oder STREAM (AVCHD/MTS)
            d_name = Path(root).name.upper()
            if d_name not in ["VIDEO", "STREAM"]: continue
            
            for f in files:
                f_lower = f.lower()
                if f_lower.endswith(('.mts', '.mxf')):
                    # Regex sucht nach Muster 2XXXX.mts oder 3XXXX.mts (für A1) oder P2 style
                    # A1 Pattern: 20005.MTS -> 2 (Links), 0005 (ID)
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
        self.root.after(0, self.merge_new_clips, found)

    def merge_new_clips(self, found_list):
        current_map = {c['id']: c for c in self.all_clips}
        for item in found_list:
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
        self.refresh_tree()
        self.calculate_total_transfer_size()

    def sync_clips_with_manifest(self):
        matched_count = 0
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
                    matched_count += 1
                else:
                    clip['status_text'] = self.tr("status_ready")
                    clip['tag'] = 'normal'
                    clip['transfer'] = True
        
        if matched_count > 0:
            self.refresh_all_target_names()
            self.status_msg.set(self.tr("msg_manifest_loaded"))
        self.refresh_tree()

    def refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        for i, c in enumerate(self.all_clips):
            eyes_str = "/".join([e for e in ["L","R"] if c[f'path_{e}']])
            tgt = self.format_name(c, i+1) if c['logged'] else ""
            
            if c.get('tag') == 'complete':
                display_status = self.tr("status_complete")
            elif c['done'] and c.get('tag') != 'complete':
                display_status = self.tr("status_done")
            else:
                display_status = c.get('status_text', self.tr("status_ready"))
            
            self.tree.insert("", "end", values=(
                c['id'], c['cam'], eyes_str, 
                f"{c['size_bytes']/1024**3:.2f} GB", tgt, 
                "[X]" if c['transfer'] else "[  ]", display_status
            ), tags=(c.get('tag', 'normal'),))

    def format_name(self, clip, idx=1):
        name = f"{self.project_name.get()}_S{str(clip['scene']).zfill(self.defaults['padding_s'])}_E{str(clip['setting']).zfill(self.defaults['padding_e'])}_T{str(clip['take']).zfill(self.defaults['padding_t'])}"
        if self.defaults["use_cam_id"]: name += f"_{self.cam_id.get()}"
        return name

    def refresh_all_target_names(self):
        if not hasattr(self, 'tree'): return
        for i, item_id in enumerate(self.tree.get_children()):
            c = next((cl for cl in self.all_clips if cl['id'] == self.tree.item(item_id, "values")[0]), None)
            if c and c['logged']: self.tree.set(item_id, "target", self.format_name(c, i+1))

    # --- PREVIEW / NAV ---
    def on_clip_selected(self, e):
        sel = self.tree.selection()
        if not sel: return
        cid = self.tree.item(sel[0], "values")[0]
        self.current_index = self.tree.index(sel[0])
        with self.thumb_queue.mutex: self.thumb_queue.queue.clear()
        c = next((cl for cl in self.all_clips if cl['id'] == cid), None)
        if c: self.thumb_queue.put(c)

    def preview_worker(self):
        while True:
            try:
                data = self.thumb_queue.get()
                self._generate_and_show_thumb(data)
                self.thumb_queue.task_done()
            except Exception: pass

    def _generate_and_show_thumb(self, data):
        vid = data['path_L'] or data['path_R']
        if not vid or not os.path.exists(self.ffmpeg_path): return
        t_path = self.temp_thumb_dir / f"t_{data['id']}.jpg"
        if not t_path.exists():
            c_flags = 0x08000000 if self.is_windows else 0
            # Preview Thumbnail: Nutze relative seek (-ss vor -i) für Speed bei .MTS
            subprocess.run([self.ffmpeg_path, '-y', '-ss', '1.0', '-i', vid, '-frames:v', '1', '-s', '480x270', str(t_path)], stderr=subprocess.DEVNULL, creationflags=c_flags)
        if t_path.exists():
            try:
                img = ImageTk.PhotoImage(Image.open(t_path))
                self.root.after(0, lambda: (self.canvas.delete("all"), self.canvas.create_image(0, 0, anchor="nw", image=img), setattr(self.canvas, 'image', img)))
            except Exception: pass

    def hk_confirm_and_next(self, e=None):
        if self.current_index == -1: return
        item_id = self.tree.get_children()[self.current_index]
        c = next((cl for cl in self.all_clips if cl['id'] == self.tree.item(item_id, "values")[0]), None)
        if c:
            c.update({'scene': self.scene.get(), 'setting': self.setting.get(), 'take': self.take.get(), 'logged': True, 'transfer': True})
            self.tree.set(item_id, "target", self.format_name(c))
            self.tree.set(item_id, "transfer", "[X]")
        try: self.take.set(str(int(self.take.get()) + 1))
        except: pass
        self.calculate_total_transfer_size()
        self.select_rel(1)

    def hk_toggle_transfer(self, e=None):
        if self.current_index == -1: return
        item_id = self.tree.get_children()[self.current_index]
        c = next((cl for cl in self.all_clips if cl['id'] == self.tree.item(item_id, "values")[0]), None)
        if c:
            c['transfer'] = not c['transfer']
            self.tree.set(item_id, "transfer", "[X]" if c['transfer'] else "[  ]")
        self.calculate_total_transfer_size()

    def clear_list(self):
        if messagebox.askyesno(self.tr("btn_clear_list"), self.tr("confirm_clear")):
            self.all_clips = []
            self.tree.delete(*self.tree.get_children())
            self.calculate_total_transfer_size()

    def hk_plus_take(self, e=None):
        try: self.take.set(str(int(self.take.get())+1))
        except: pass
    def hk_new_setting(self, e=None):
        try: self.setting.set(str(int(self.setting.get())+1)); self.take.set("1")
        except: pass
    def hk_new_scene(self, e=None):
        try: self.scene.set(str(int(self.scene.get())+1)); self.setting.set("1"); self.take.set("1")
        except: pass
    def hk_prev_clip(self, e=None): self.select_rel(-1)
    def select_rel(self, d):
        ch = self.tree.get_children()
        if not ch: return
        ni = self.current_index + d
        if 0 <= ni < len(ch):
            self.tree.selection_set(ch[ni])
            self.tree.see(ch[ni])
            self.current_index = ni

if __name__ == "__main__":
    root = tk.Tk()
    app = IngestProApp(root)
    root.mainloop()