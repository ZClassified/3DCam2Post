from core.ingest_manager import IngestManager
from ui.settings_dialog import SettingsDialog
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
import customtkinter as ctk
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
        "btn_save": "SPEICHERN",
        "btn_settings": "Einstellungen"
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
        "btn_save": "SAVE",
        "btn_settings": "Settings"
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

        app_w, app_h = 1800, 950
        self.center_window(self.root, app_w, app_h)
        
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
        self.btn_settings.configure(text=self.tr("btn_settings"))
        self.btn_add_src.configure(text=self.tr("btn_add_source"))
        self.btn_clr_lst.configure(text=self.tr("btn_clear_list"))
        self.lbl_proj_title.configure(text=self.tr("lbl_project"))
        self.adv_day_label.configure(text=self.tr("lbl_day"))

        headers = [
            self.tr("col_id"), self.tr("col_cam"), self.tr("col_eye"), 
            self.tr("col_size"), self.tr("col_target"), self.tr("col_trans"), self.tr("col_stat")
        ]
        columns = ("pair", "cam", "eye", "size", "target", "transfer", "status")
        for col, head in zip(columns, headers):
            self.tree.heading(col, text=head)

        self.log_frame.configure(text=self.tr("grp_log"))
        self.lbl_sc.configure(text=self.tr("lbl_scene"))
        self.lbl_set.configure(text=self.tr("lbl_setting"))
        self.lbl_tk.configure(text=self.tr("lbl_take"))
        self.cam_id_label.configure(text=self.tr("lbl_cam_id"))

        self.pad_frame.configure(text=self.tr("grp_hotkeys"))
        self.btn_hk_scene.configure(text=self.tr("hk_scene"))
        self.btn_hk_setting.configure(text=self.tr("hk_setting"))
        self.btn_hk_remove.configure(text=self.tr("hk_remove"))
        self.btn_hk_take.configure(text=self.tr("hk_take_plus"))
        self.btn_hk_next.configure(text=self.tr("hk_next"))

        self.btn_start.configure(text=self.tr("btn_start"))
        self.btn_manual_target.configure(text=self.tr("btn_choose_root"))
        
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
        top_frame = ctk.CTkFrame(self.root)
        top_frame.pack(fill="x")
        
        self.btn_add_src = ctk.CTkButton(top_frame, text=self.tr("btn_add_source"), command=self.add_source, 
                  fg_color="#0078d7", text_color="white", font=("Arial", 12, "bold"))
        self.btn_add_src.pack(side=tk.LEFT, padx=10)
        
        self.btn_clr_lst = ctk.CTkButton(top_frame, text=self.tr("btn_clear_list"), command=self.clear_list, 
                  fg_color="#6c757d", text_color="white", font=("Arial", 11))
        self.btn_clr_lst.pack(side=tk.LEFT, padx=(0, 20))
        
        self.lbl_proj_title = ctk.CTkLabel(top_frame, text=self.tr("lbl_project"), font=("Arial", 12))
        self.lbl_proj_title.pack(side=tk.LEFT, padx=(10, 5))
        ctk.CTkEntry(top_frame, textvariable=self.project_name, width=150, 
                 font=("Arial", 12, "bold")).pack(side=tk.LEFT, padx=(0, 20))
        
        self.adv_day_label = ctk.CTkLabel(top_frame, text=self.tr("lbl_day"), font=("Arial", 12))
        self.adv_day_label.pack(side=tk.LEFT, padx=(0, 5))
        self.adv_day_entry = ctk.CTkEntry(top_frame, textvariable=self.day, width=40, font=("Arial", 12))
        self.adv_day_entry.pack(side=tk.LEFT)
        
        self.btn_settings = ctk.CTkButton(top_frame, text=self.tr("btn_settings"), font=("Arial", 12, "bold"), 
                                      command=self.open_settings)
        self.btn_settings.pack(side=tk.RIGHT)

        self.paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.paned.pack(fill="both", expand=True, padx=10)

        list_frame = ctk.CTkFrame(self.paned, width=800)
        columns = ("pair", "cam", "eye", "size", "target", "transfer", "status")
        
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background="#2b2b2b", fieldbackground="#2b2b2b", foreground="white", borderwidth=0, font=("Arial", 12), rowheight=30)
        style.configure("Treeview.Heading", background="#1f1f1f", foreground="white", relief="flat", font=("Arial", 12, "bold"))
        style.map("Treeview", background=[("selected", "#1f538d")])
        
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings")

        
        headers = [
            self.tr("col_id"), self.tr("col_cam"), self.tr("col_eye"), 
            self.tr("col_size"), self.tr("col_target"), self.tr("col_trans"), self.tr("col_stat")
        ]
        widths = [50, 90, 70, 100, 320, 100, 120]
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
        self.paned.add(list_frame, weight=2)

        self.right_frame = ctk.CTkFrame(self.paned)
        self.paned.add(self.right_frame, weight=1)
        
        self.canvas = tk.Canvas(self.right_frame, width=640, height=360, bg="#1a1a1a")
        self.canvas.pack(pady=5)
        
        self.log_frame = tk.LabelFrame(self.right_frame, text=self.tr("grp_log"), bg='#2b2b2b', fg='white', pady=10, padx=10, font=("Arial", 12, "bold"))
        self.log_frame.pack(fill="x")
        f_font = ("Arial", 26, "bold")
        l_font = ("Arial", 14)
        
        self.lbl_sc = ctk.CTkLabel(self.log_frame, text=self.tr("lbl_scene"), font=l_font)
        self.lbl_sc.grid(row=0, column=0, pady=(0, 5))
        ctk.CTkEntry(self.log_frame, textvariable=self.scene, font=f_font, width=60, justify="center").grid(row=1, column=0, padx=10, pady=(0, 10))
        
        self.lbl_set = ctk.CTkLabel(self.log_frame, text=self.tr("lbl_setting"), font=l_font)
        self.lbl_set.grid(row=0, column=1, pady=(0, 5))
        ctk.CTkEntry(self.log_frame, textvariable=self.setting, font=f_font, width=60, justify="center").grid(row=1, column=1, padx=10, pady=(0, 10))
        
        self.lbl_tk = ctk.CTkLabel(self.log_frame, text=self.tr("lbl_take"), font=l_font)
        self.lbl_tk.grid(row=0, column=2, pady=(0, 5))
        ctk.CTkEntry(self.log_frame, textvariable=self.take, font=f_font, width=60, justify="center").grid(row=1, column=2, padx=10, pady=(0, 10))
        
        self.cam_id_label = ctk.CTkLabel(self.log_frame, text=self.tr("lbl_cam_id"), font=l_font)
        self.cam_id_label.grid(row=0, column=3, padx=20, pady=(0, 5))
        self.cam_id_entry = ctk.CTkEntry(self.log_frame, textvariable=self.cam_id, font=f_font, width=40, justify="center", text_color="#005a9e")
        self.cam_id_entry.grid(row=1, column=3, padx=20, pady=(0, 10))

        self.pad_frame = tk.LabelFrame(self.right_frame, text=self.tr("grp_hotkeys"), bg='#2b2b2b', fg='white', pady=10, padx=10, font=("Arial", 12, "bold"))
        self.pad_frame.pack(fill="x", pady=10)
        btn_style = {"font": ("Arial", 12, "bold"), "height": 36, "text_color": "white"}
        
        self.btn_hk_scene = ctk.CTkButton(self.pad_frame, text=self.tr("hk_scene"), fg_color="#005a9e", command=self.hk_new_scene, **btn_style)
        self.btn_hk_scene.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.btn_hk_setting = ctk.CTkButton(self.pad_frame, text=self.tr("hk_setting"), fg_color="#c87800", command=self.hk_new_setting, **btn_style)
        self.btn_hk_setting.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        self.btn_hk_remove = ctk.CTkButton(self.pad_frame, text=self.tr("hk_remove"), fg_color="#a52a2a", command=self.hk_toggle_transfer, **btn_style)
        self.btn_hk_remove.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.btn_hk_take = ctk.CTkButton(self.pad_frame, text=self.tr("hk_take_plus"), fg_color="#5a5a5a", command=self.hk_plus_take, **btn_style)
        self.btn_hk_take.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)
        self.btn_hk_next = ctk.CTkButton(self.pad_frame, text=self.tr("hk_next"), fg_color="#28a745", command=self.hk_confirm_and_next, **btn_style)
        self.btn_hk_next.grid(row=1, column=2, sticky="nsew", padx=5, pady=5)
        
        self.pad_frame.columnconfigure((0,1,2), weight=1)

        ingest_frame = ctk.CTkFrame(self.right_frame)
        ingest_frame.pack(fill="x", side=tk.BOTTOM, pady=10)
        ctk.CTkLabel(ingest_frame, textvariable=self.total_size_str, font=("Arial", 12, "bold"), text_color="#0078d7").pack(anchor="e")
        
        self.lbl_mbps = ctk.CTkLabel(ingest_frame, text="", font=("Arial", 12), text_color="#aaaaaa")
        self.lbl_mbps.pack(anchor="e")
        self.progress = ctk.CTkProgressBar(ingest_frame, mode="determinate")
        self.progress.set(0)
        self.progress.pack(fill="x")

        self.lbl_target_path = ctk.CTkLabel(ingest_frame, textvariable=self.target_display, font=("Arial", 12, "italic"), wraplength=500)
        self.lbl_target_path.pack()
        self.btn_manual_target = ctk.CTkButton(ingest_frame, text=self.tr("btn_choose_root"), command=self.choose_stammordner_manual, fg_color="#218838", text_color="white", font=("Arial", 12, "bold"))
        self.btn_manual_target.pack(fill="x", pady=10)
        
        btn_frame = ctk.CTkFrame(ingest_frame, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(0, 10))
        self.btn_start = ctk.CTkButton(btn_frame, text=self.tr("btn_start"), fg_color="#28a745", text_color="white", font=("Arial", 12, "bold"), command=self.start_ingest)
        self.btn_start.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        self.btn_cancel = ctk.CTkButton(btn_frame, text="ABBRECHEN", fg_color="#dc3545", text_color="white", font=("Arial", 12, "bold"), command=self.cancel_ingest, state="disabled")
        self.btn_cancel.pack(side="right", fill="x", expand=True, padx=(5, 0))


        status_bar = ctk.CTkFrame(self.root)
        status_bar.pack(side=tk.BOTTOM, fill="x")
        ctk.CTkLabel(status_bar, textvariable=self.status_msg, anchor="w", font=("Arial", 12)).pack(side=tk.LEFT)
        ctk.CTkLabel(status_bar, textvariable=self.disk_space_str, anchor="e", text_color="#aaaaaa", font=("Arial", 12)).pack(side=tk.RIGHT)

        self.root.after(100, lambda: self.set_sash())

    def set_sash(self):
        try:
            self.paned.sash_place(0, 900, 0)
        except Exception:
            pass

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
        SettingsDialog(self.root, self.defaults, HAS_XXHASH, self.tr, self.on_settings_saved, self.open_manual)

    def on_settings_saved(self, new_defaults):
        self.defaults = new_defaults
        self.save_config()
        self.update_ui_texts()

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
            from tkinter import messagebox
            messagebox.showwarning(self.tr("title"), self.tr("err_no_root"))
            return
        
        self.load_manifest()

        base = Path(self.defaults["stammordner"]) / self.project_name.get()
        
        to_copy = []
        for i, item_id in enumerate(self.tree.get_children()):
            c = next((cl for cl in self.all_clips if cl['id'] == self.tree.item(item_id, "values")[0]), None)
            if c and c['transfer'] and not c['done'] and c['logged']:
                to_copy.append((c, item_id))

        if not to_copy:
            from tkinter import messagebox
            messagebox.showinfo("Info", self.tr("msg_no_copy"))
            return

        # Check for Overwrite
        existing_files = []
        for c, item_id in to_copy:
            bn = self.format_name(c, 1)
            current_root = base / (f"Tag_{self.day.get().zfill(2)}" if self.defaults["sort_mode"] == "Drehtage" else f"Szene_{str(c['scene']).zfill(self.defaults['padding_s'])}")
            for eye in ['L', 'R']:
                src = c[f'path_{eye}']
                if src:
                    ext = Path(src).suffix
                    is_p2 = ext.lower() == '.mxf'
                    if is_p2:
                        target = current_root / ("LINKS" if eye == "L" else "RECHTS") / "CONTENTS" / "VIDEO" / f"{bn}_{eye}{ext}"
                    else:
                        target = current_root / ("LINKS" if eye == "L" else "RECHTS") / f"{bn}_{eye}{ext}"
                    if target.exists():
                        existing_files.append(target.name)
        
        if existing_files:
            from tkinter import messagebox
            msg = f"Achtung: {len(existing_files)} Zieldateien existieren bereits (z.B. {existing_files[0]}).\\n\\nAbbrechen: Stoppt den Vorgang.\\nFortsetzen: Überschreibt die Dateien mit den aktuellen Clips."
            if not messagebox.askokcancel("Dateien existieren bereits", msg, icon=messagebox.WARNING):
                return
            if not messagebox.askyesno("Ganz sicher?", "Bist du dir GANZ sicher? Bereits kopierte Dateien mit gleichem Namen werden überschrieben!"):
                return

        self.btn_start.configure(state="disabled")
        self.btn_cancel.configure(state="normal")
        self.manager = None

        
        callbacks = {
            'on_status': lambda msg: self.root.after(0, lambda: self.status_msg.set(msg)),
            'on_progress': lambda item_id, pct: self.root.after(0, lambda: self.update_progress(item_id, pct)),
            'on_total_progress': lambda pct, mbps, eta: self.root.after(0, lambda: self.update_total_progress(pct, mbps, eta)),
            'on_clip_start': lambda item_id: self.root.after(0, lambda: self.tree.set(item_id, "status", self.tr("status_work"))),
            'on_clip_done': lambda item_id, m_data: self.root.after(0, lambda: self.handle_clip_done(item_id, m_data)),
            'on_error': lambda msg: self.root.after(0, lambda: self.status_msg.set(msg))
        }
        
        self.manager = IngestManager(self.defaults, self.temp_thumb_dir, self.ffmpeg_path, self.is_windows, callbacks)

        
        import threading
        def run():
            m_data, log = self.manager.run_ingest(
                to_copy, 
                self.project_name.get(), 
                lambda c: base / (f"Tag_{self.day.get().zfill(2)}" if self.defaults["sort_mode"] == "Drehtage" else f"Szene_{str(c['scene']).zfill(self.defaults['padding_s'])}"),
                lambda c: self.format_name(c, 1),
                base, 
                report_dir, 
                self.manifest_data
            )
            self.manifest_data = m_data
            self.root.after(0, self.post_ingest)

        threading.Thread(target=run, daemon=True).start()


    def cancel_ingest(self):
        if hasattr(self, 'manager') and self.manager:
            self.manager.cancel_event.set()
            self.status_msg.set("ABBRUCH WIRD AUSGEFÜHRT...")
            self.btn_cancel.configure(state="disabled")

    def update_total_progress(self, pct, mbps, eta):
        self.progress.set(pct / 100)
        self.lbl_mbps.configure(text=f"{mbps:.1f} MB/s | ETA: {eta:.0f}s")

    def update_progress(self, item_id, pct):
        self.tree.set(item_id, "status", self.tr("status_done"))
        self.progress.configure(value=pct)
        
    def handle_clip_done(self, item_id, m_data):
        self.manifest_data = m_data

    def post_ingest(self):
        cleaned = self.cleanup_manifest_if_done()
        self.sync_clips_with_manifest()

        final_msg = self.tr("msg_complete")
        if self.defaults["verify_copy"]: final_msg += f"\\n{self.tr('msg_report')}"
        if cleaned: final_msg += f"\\n{self.tr('msg_clean')}"
        
        from tkinter import messagebox
        messagebox.showinfo("Ingest", final_msg)
        self.btn_start.configure(state="normal")
        self.btn_cancel.configure(state="disabled")
        self.lbl_mbps.configure(text="")
        self.progress.set(0)
        

    # --- SCANNING & SYNC ---
    def add_source(self):
        p = filedialog.askdirectory()
        if p: threading.Thread(target=self.scan_folder, args=(p,), daemon=True).start()

    def scan_folder(self, root_path):
        manager = IngestManager(self.defaults, self.temp_thumb_dir, self.ffmpeg_path, self.is_windows, {})
        found = manager.scan_folder(root_path)
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
            subprocess.run([self.ffmpeg_path, '-y', '-ss', '1.0', '-i', vid, '-frames:v', '1', '-s', '640x360', str(t_path)], stderr=subprocess.DEVNULL, creationflags=c_flags)
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
        except: self.take.set("1")
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
        except: self.take.set("1")
    def hk_new_setting(self, e=None):
        try: self.setting.set(str(int(self.setting.get())+1)); self.take.set("1")
        except: self.setting.set("1"); self.take.set("1")
    def hk_new_scene(self, e=None):
        try: self.scene.set(str(int(self.scene.get())+1)); self.setting.set("1"); self.take.set("1")
        except: self.scene.set("1"); self.setting.set("1"); self.take.set("1")
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