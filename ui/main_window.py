import os
import re
import sys
import json
import queue
import shutil
import asyncio
import logging
import platform
import threading
import subprocess
from pathlib import Path

import flet as ft

from core.ingest_manager import IngestManager, build_name, write_json_atomic, HAS_XXHASH
from core.matching import choose_pair_candidate, resolve_manifest_key
from core.paths import resource_path, config_path, legacy_config_paths, thumb_dir, file_key
from ui.i18n import make_tr
from ui.settings_dialog import SettingsDialog
from ui.about import ffmpeg_version

APP_VERSION = "1.3.2"
MANIFEST_FILE = "ingest_manifest.json"

ROW_H = 44
RIGHT_W = 520
PREVIEW_W, PREVIEW_H = 252, 142
MONO = "Consolas"
INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
LOW_SPACE = 100 * 1024 ** 3
BLANK_PNG = ("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=")

DEFAULTS = {
    "language": "en", "use_cam_id": False, "verify_copy": False,
    "generate_thumbs": True, "hash_algo": "md5",
    "padding_s": 2, "padding_e": 2, "padding_t": 3,
    "sort_mode": "Drehtage", "stammordner": "",
    "audio_source": "Links", "strip_audio_eye": False, "copy_audio": True,
    "last_project": "Project_Name", "last_day": "1",
    "output_mode": "p2",
}

# Clip states that are derived from the manifest and get recomputed on sync
MANIFEST_STATES = {"complete", "match", "partial", "failed", "working"}


def fmt_size(b):
    gb = b / 1024 ** 3
    if gb >= 1000:
        return f"{gb / 1024:.2f} TB"
    if gb >= 1 or b == 0:
        return f"{gb:.2f} GB"
    return f"{b / 1024 ** 2:.1f} MB"


def inc(value):
    try:
        return str(int(value) + 1)
    except (TypeError, ValueError):
        return "1"


def open_path(p):
    try:
        if os.name == "nt":
            os.startfile(p)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(p)])
        else:
            subprocess.Popen(["xdg-open", str(p)])
    except Exception as e:
        logging.error(f"Open {p} failed: {e}")


class IngestProApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.is_windows = platform.system() == "Windows"

        ffmpeg_bin = "ffmpeg.exe" if self.is_windows else "ffmpeg"
        local_ffmpeg = resource_path(ffmpeg_bin)
        self.ffmpeg_path = str(local_ffmpeg) if local_ffmpeg.exists() else shutil.which(ffmpeg_bin)

        self.settings = dict(DEFAULTS)
        self.load_config()
        self.tr = make_tr(lambda: self.settings.get("language"))

        self.thumb_dir = thumb_dir()
        self._clear_thumb_cache()

        self.clips = []
        self.manifest = {}
        self.current = -1
        self.busy = False
        self.manager = None
        self._text_focused = False
        self._dialog_open = False
        self._list_px = 0.0
        self._list_h = 600.0

        self.project_name = self.settings.get("last_project") or "Project_Name"
        self.day = str(self.settings.get("last_day") or "1")
        self.scene, self.setting, self.take, self.cam_id = "1", "1", "1", "A"

        self.preview_queue = queue.Queue()
        threading.Thread(target=self._preview_worker, daemon=True).start()

        self.src_picker = ft.FilePicker()
        self.root_picker = ft.FilePicker()
        self.page.services.extend([self.src_picker, self.root_picker])
        self.page.on_keyboard_event = self.on_keyboard

        self.build_ui()
        self.load_manifest()
        self.refresh()
        if not self.ffmpeg_path:
            self.set_status(self.tr("ffmpeg_missing"), warn=True)
        self.page.update()

    # ================================================================ helpers
    def _ui(self, fn, *args):
        """Run fn(*args) on the Flet event loop and push the update (safe from worker threads)."""
        async def run():
            fn(*args)
            self.page.update()
        try:
            self.page.run_task(run)
        except Exception as e:
            logging.error(f"UI dispatch failed: {e}")

    def _clear_thumb_cache(self):
        for f in self.thumb_dir.glob("*.jpg"):
            try:
                f.unlink()
            except OSError:
                pass

    # ================================================================ config / manifest
    def load_config(self):
        candidates = [config_path(), *legacy_config_paths()]
        for p in candidates:
            if p.exists():
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        self.settings.update(json.load(f))
                    self.settings.pop("copy_video", None)
                    break
                except Exception as e:
                    logging.error(f"Config load error ({p}): {e}")

    def save_config(self):
        try:
            write_json_atomic(config_path(), self.settings)
        except Exception as e:
            logging.error(f"Config save error: {e}")

    def project_dir(self):
        root, project = self.settings.get("stammordner"), self.project_name.strip()
        if not root or not project:
            return None
        return Path(root) / project

    def manifest_path(self):
        d = self.project_dir()
        return d / MANIFEST_FILE if d else None

    def load_manifest(self):
        self.manifest = {}
        path = self.manifest_path()
        if path and path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.manifest = json.load(f)
            except Exception as e:
                logging.error(f"Manifest load error: {e}")
                self.set_status(f"Manifest: {e}", warn=True)
        self.assign_mkeys(self.clips)

    # ================================================================ clip model
    def new_clip(self, key, item):
        return {
            'key': key, 'mkey': key, 'id': item['id'], 'cam': item['cam'],
            'path_L': None, 'path_R': None, 'size_L': 0, 'size_R': 0, 'mtime_L': None, 'mtime_R': None, 'recid_L': None, 'recid_R': None,
            'span': False,
            'scene': "", 'setting': "", 'take': "", 'cam_id': "",
            'logged': False, 'transfer': False, 'state': 'new',
            'done_L': False, 'done_R': False, 'locked_name': None,
        }

    def assign_mkeys(self, clips):
        """(Re)assigns manifest keys for the given clips and applies the manifest state to them."""
        targets = {id(c) for c in clips}
        taken = {c['mkey'] for c in self.clips if id(c) not in targets}
        for c in sorted(clips, key=lambda c: c['key']):
            c['mkey'] = resolve_manifest_key(self.manifest, c, taken)
            taken.add(c['mkey'])
            self.apply_manifest(c)

    def apply_manifest(self, c):
        m = self.manifest.get(c['mkey'])
        c['done_L'] = c['done_R'] = False
        c['locked_name'] = None
        if c['state'] in MANIFEST_STATES:
            c['state'] = 'new'
        if not m:
            return

        for eye in "LR":
            c[f'done_{eye}'] = m.get(f"status_{eye}") == "done"

        c.update(scene=m.get('scene', ""), setting=m.get('setting', ""), take=m.get('take', ""),
                 cam_id=m.get('cam_id', ""), logged=True)
        any_done = c['done_L'] or c['done_R']
        if any_done:
            c['locked_name'] = m.get('target_name')
        missing_present = [e for e in "LR" if not c[f'done_{e}'] and c[f'path_{e}']]
        if c['done_L'] and c['done_R']:
            c['state'], c['transfer'] = 'complete', False
        elif any_done and missing_present:
            c['state'], c['transfer'] = 'match', True
        elif any_done:
            c['state'], c['transfer'] = 'partial', False
        else:
            failed = "failed" in (m.get("status_L"), m.get("status_R"))
            c['state'], c['transfer'] = ('failed' if failed else 'new'), True

    def clip_name(self, c):
        if c.get('locked_name'):
            return c['locked_name']
        if not c['logged']:
            return None
        return build_name(self.settings, self.project_name.strip(), c['scene'], c['setting'], c['take'], c['cam_id'])

    def eyes_to_copy(self, c):
        present = [e for e in "LR" if c[f'path_{e}']]
        todo = [e for e in present if not c[f'done_{e}']]
        return todo or present

    def copy_size(self, c):
        size = sum(c[f'size_{e}'] for e in self.eyes_to_copy(c))
        if self.settings.get("output_mode") == "p2_mov":
            size *= 2
        return size

    def clip_root(self, base, c):
        if self.settings["sort_mode"] == "Drehtage":
            return base / f"Tag_{str(self.day).strip().zfill(2)}"
        return base / f"Szene_{str(c['scene']).zfill(int(self.settings['padding_s']))}"

    def clip_status(self, c):
        st = c['state']
        if st == 'working':
            return self.tr("status_work"), ft.Colors.LIGHT_BLUE_300, None
        if st == 'failed':
            return self.tr("status_failed"), ft.Colors.RED_400, None
        if st == 'complete':
            return self.tr("status_complete"), ft.Colors.GREEN_400, None
        missing = "/".join(e for e in "LR" if not c[f'done_{e}'])
        if st == 'match':
            return self.tr("status_match", eye=missing), ft.Colors.AMBER_400, None
        if st == 'partial':
            return self.tr("status_partial", eye=missing), ft.Colors.AMBER_200, None
        if c.get('span') and not c['logged']:
            return self.tr("status_span"), ft.Colors.AMBER_400, self.tr("tip_span")
        if c['logged'] and c['transfer']:
            return self.tr("status_logged"), ft.Colors.ON_SURFACE, None
        if c['logged']:
            return self.tr("status_skip"), ft.Colors.ON_SURFACE_VARIANT, None
        return self.tr("status_new"), ft.Colors.ON_SURFACE_VARIANT, None

    # ================================================================ UI building
    def _tf(self, label, value, width, on_change, big=False, on_blur=None):
        def blur(e):
            self._set_text_focus(False)
            if on_blur:
                on_blur(e)
        return ft.TextField(
            label=label, value=value, width=width, on_change=on_change,
            text_align=ft.TextAlign.CENTER if big else ft.TextAlign.START,
            text_size=22 if big else 14, dense=not big,
            on_focus=lambda e: self._set_text_focus(True), on_blur=blur,
            on_submit=self._leave_text,
        )

    @staticmethod
    def _keycap(k):
        return ft.Container(
            content=ft.Text(k, size=11, weight=ft.FontWeight.BOLD, font_family=MONO),
            padding=ft.Padding.symmetric(horizontal=6, vertical=1),
            border=ft.Border.all(1, ft.Colors.OUTLINE), border_radius=4,
        )

    def _hk_button(self, key, label, handler, tooltip=None):
        return ft.OutlinedButton(
            content=ft.Row([self._keycap(key), ft.Text(label, size=13, no_wrap=True)], spacing=6, tight=True),
            on_click=lambda e: self._run_hotkey(handler), expand=True, tooltip=tooltip,
            style=ft.ButtonStyle(padding=ft.Padding.symmetric(horizontal=8)),
        )

    def _card(self, content, padding=16, expand=None):
        return ft.Container(content=content, padding=padding, border_radius=10,
                            bgcolor=ft.Colors.SURFACE_CONTAINER, expand=expand)

    def build_ui(self):
        tr = self.tr
        # ---------- header
        self.lbl_root = ft.Text(self.settings["stammordner"] or tr("root_none"), size=13,
                                overflow=ft.TextOverflow.ELLIPSIS, max_lines=1, expand=True)
        self.root_box = ft.Container(
            content=ft.Column([
                ft.Text(tr("lbl_root"), size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.Row([ft.Icon(ft.Icons.FOLDER_OUTLINED, size=18), self.lbl_root], spacing=6),
            ], spacing=0, tight=True),
            width=340, padding=ft.Padding.symmetric(horizontal=12, vertical=6),
            border=ft.Border.all(1, ft.Colors.OUTLINE), border_radius=6,
            on_click=self.pick_root, ink=True, tooltip=self.settings["stammordner"] or None,
        )
        self.tf_project = self._tf(tr("lbl_project"), self.project_name, 220,
                                   self.on_project_change, on_blur=self.on_project_commit)
        self.tf_day = self._tf(tr("lbl_day"), self.day, 70, self.on_day_change, on_blur=self.on_day_commit)
        self.lbl_target = ft.Text("", size=12, color=ft.Colors.ON_SURFACE_VARIANT, font_family=MONO,
                                  overflow=ft.TextOverflow.ELLIPSIS, max_lines=1, expand=True)
        self.btn_settings = ft.IconButton(ft.Icons.SETTINGS, on_click=self.open_settings, tooltip=tr("btn_settings"))

        header = ft.Row([
            ft.Column([
                ft.Text("3DCam2Post", size=20, weight=ft.FontWeight.BOLD),
                ft.Text("Stereo 3D Ingest", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
            ], spacing=0, tight=True),
            ft.Container(width=12),
            self.root_box, self.tf_project, self.tf_day,
            self.lbl_target,
            self.btn_settings,
        ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER)

        # ---------- clip list
        self.btn_add = ft.FilledButton(tr("btn_add_source"), icon=ft.Icons.ADD, on_click=self.pick_source)
        self.btn_clear = ft.TextButton(tr("btn_clear_list"), icon=ft.Icons.CLEAR_ALL, on_click=self.clear_list)
        self.lbl_counts = ft.Text("", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        toolbar = ft.Row([self.btn_add, self.btn_clear, ft.Container(expand=True), self.lbl_counts])

        def hcell(text, width=None, expand=None, align=ft.TextAlign.START):
            return ft.Container(ft.Text(text, size=11, weight=ft.FontWeight.BOLD,
                                        color=ft.Colors.ON_SURFACE_VARIANT, text_align=align),
                                width=width, expand=expand)
        table_header = ft.Container(
            content=ft.Row([
                ft.Container(width=40), hcell(tr("col_id"), 110),
                hcell(tr("col_eyes"), 64), hcell(tr("col_target"), expand=True),
                hcell(tr("col_size"), 76, align=ft.TextAlign.RIGHT), hcell(tr("col_stat"), 150),
            ], spacing=8),
            padding=ft.Padding.symmetric(horizontal=8, vertical=8),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
            border_radius=ft.BorderRadius.only(top_left=8, top_right=8),
        )
        self.list_view = ft.ListView(expand=True, item_extent=ROW_H, on_scroll=self._on_list_scroll,
                                     scroll_interval=30, on_size_change=self._on_list_size)
        self.empty_state = ft.Container(
            content=ft.Column([
                ft.Icon(ft.Icons.SD_CARD_OUTLINED, size=56, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.Text(tr("empty_title"), size=18, weight=ft.FontWeight.BOLD),
                ft.Text(tr("empty_hint"), color=ft.Colors.ON_SURFACE_VARIANT, text_align=ft.TextAlign.CENTER),
                ft.Container(height=8),
                ft.FilledButton(tr("btn_add_source"), icon=ft.Icons.ADD, on_click=self.pick_source),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, tight=True, spacing=8),
            alignment=ft.Alignment.CENTER, expand=True, padding=40,
        )
        left = ft.Column([
            toolbar,
            ft.Container(
                content=ft.Column([table_header, self.list_view, self.empty_state], spacing=0, expand=True),
                border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT), border_radius=8, expand=True,
            ),
        ], expand=True, spacing=10)

        # ---------- preview
        def eye_preview(label, color):
            img = ft.Image(src=BLANK_PNG, width=PREVIEW_W, height=PREVIEW_H, fit=ft.BoxFit.CONTAIN)
            box = ft.Stack([
                ft.Container(img, width=PREVIEW_W, height=PREVIEW_H, bgcolor=ft.Colors.BLACK, border_radius=6,
                             alignment=ft.Alignment.CENTER),
                ft.Container(ft.Text(label, size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                             bgcolor=color, padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                             border_radius=4, left=6, top=6),
            ], width=PREVIEW_W, height=PREVIEW_H)
            return img, box
        self.img_L, box_L = eye_preview("L", ft.Colors.BLUE_700)
        self.img_R, box_R = eye_preview("R", ft.Colors.RED_700)
        self.lbl_preview = ft.Text(tr("preview_none"), size=12, color=ft.Colors.ON_SURFACE_VARIANT,
                                   font_family=MONO, overflow=ft.TextOverflow.ELLIPSIS, max_lines=1)
        preview_card = self._card(ft.Column([ft.Row([box_L, box_R], spacing=8), self.lbl_preview], spacing=8),
                                  padding=8)

        # ---------- logging
        self.tf_scene = self._tf(tr("lbl_scene"), self.scene, 100, self._update_log_state, big=True)
        self.tf_setting = self._tf(tr("lbl_setting"), self.setting, 100, self._update_log_state, big=True)
        self.tf_take = self._tf(tr("lbl_take"), self.take, 100, self._update_log_state, big=True)
        self.tf_cam_id = self._tf(tr("lbl_cam_id"), self.cam_id, 90, self._update_log_state, big=True)
        log_fields = [self.tf_scene, self.tf_setting, self.tf_take]
        if self.settings["use_cam_id"]:
            log_fields.append(self.tf_cam_id)

        self.lbl_next_name = ft.Text("", size=16, weight=ft.FontWeight.BOLD, font_family=MONO,
                                     overflow=ft.TextOverflow.ELLIPSIS, max_lines=1)
        self.lbl_clip_name = ft.Text("", size=12, color=ft.Colors.ON_SURFACE_VARIANT, font_family=MONO,
                                     overflow=ft.TextOverflow.ELLIPSIS, max_lines=1)
        self.btn_confirm = ft.FilledButton(
            content=ft.Row([ft.Text(tr("btn_confirm"), size=15, weight=ft.FontWeight.BOLD),
                            self._keycap("→")], alignment=ft.MainAxisAlignment.CENTER, spacing=10),
            on_click=lambda e: self._run_hotkey(self.hk_confirm_and_next),
            bgcolor=ft.Colors.GREEN_700, color=ft.Colors.WHITE, height=48, expand=True,
        )
        log_card = self._card(ft.Column([
            ft.Text(tr("grp_log"), weight=ft.FontWeight.BOLD),
            ft.Row(log_fields, spacing=12),
            ft.Column([
                ft.Text(tr("next_name"), size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                self.lbl_next_name, self.lbl_clip_name,
            ], spacing=2),
            ft.Row([self.btn_confirm]),
            ft.Row([
                self._hk_button("S", tr("hk_scene"), self.hk_new_scene),
                self._hk_button("E", tr("hk_setting"), self.hk_new_setting),
                self._hk_button("T", tr("hk_take_plus"), self.hk_plus_take),
                self._hk_button("Entf" if self.settings["language"] == "de" else "Del",
                                tr("hk_remove_short"), self.hk_toggle_transfer, tooltip=tr("hk_remove")),
            ], spacing=6),
            ft.Text(tr("hk_hint"), size=11, color=ft.Colors.ON_SURFACE_VARIANT),
        ], spacing=10))

        # ---------- ingest
        self.lbl_free = ft.Text("", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        mode = self.settings.get("output_mode", "p2")
        self.lbl_output = ft.Text(tr("out_label", mode=tr(f"out_short_{mode}")), size=12,
                                  color=ft.Colors.ON_SURFACE_VARIANT, tooltip=tr("desc_output"))
        self.lbl_summary = ft.Text("", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.LIGHT_BLUE_300)
        self.lbl_ingest_warn = ft.Text("", size=12, color=ft.Colors.AMBER_400, visible=False)
        self.pb_ingest = ft.ProgressBar(value=0, visible=False, height=8, border_radius=4)
        self.lbl_current = ft.Text("", size=11, color=ft.Colors.ON_SURFACE_VARIANT, font_family=MONO,
                                   overflow=ft.TextOverflow.ELLIPSIS, max_lines=1, expand=True)
        self.lbl_mbps = ft.Text("", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        self.btn_start = ft.FilledButton(tr("btn_start"), icon=ft.Icons.PLAY_ARROW, on_click=self.start_ingest,
                                         bgcolor=ft.Colors.BLUE_700, color=ft.Colors.WHITE, height=46, expand=True)
        self.btn_cancel = ft.OutlinedButton(tr("btn_cancel"), icon=ft.Icons.STOP, on_click=self.cancel_ingest,
                                            disabled=True, height=46)
        self.row_progress = ft.Row([self.lbl_current, self.lbl_mbps], visible=False)
        ingest_card = self._card(ft.Column([
            ft.Row([
                self.lbl_summary, ft.Container(expand=True),
                ft.Column([self.lbl_free, self.lbl_output], spacing=0,
                          horizontal_alignment=ft.CrossAxisAlignment.END),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            self.lbl_ingest_warn, self.pb_ingest, self.row_progress,
            ft.Row([self.btn_start, self.btn_cancel]),
        ], spacing=8))

        right = ft.Column([preview_card, log_card, ft.Container(expand=True), ingest_card],
                          width=RIGHT_W, spacing=12)

        # ---------- status bar
        self.status_text = ft.Text(self.tr("status_ready"), size=12, overflow=ft.TextOverflow.ELLIPSIS,
                                   max_lines=1, expand=True)
        self.mode_icon = ft.Icon(ft.Icons.KEYBOARD, size=16)
        self.mode_text = ft.Text("", size=12)
        status_bar = ft.Row([
            self.status_text,
            ft.Row([self.mode_icon, self.mode_text], spacing=6, tight=True),
            ft.Container(width=16),
            ft.Text(f"v{APP_VERSION}", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
        ])

        layout = ft.Column([
            header,
            ft.Row([left, right], expand=True, spacing=16, vertical_alignment=ft.CrossAxisAlignment.STRETCH),
            status_bar,
        ], expand=True, spacing=12)

        # Focus sink: focusing it takes the focus away from text fields so hotkeys work again
        self.kb = ft.KeyboardListener(content=layout, autofocus=True)
        self.page.controls.clear()
        self.page.add(ft.Container(self.kb, expand=True))
        self._set_text_focus(False)
        self.update_target_label()

    # ================================================================ refresh
    def build_row(self, i, c):
        selected = i == self.current
        name = self.clip_name(c)
        stat, stat_color, stat_tip = self.clip_status(c)

        def badge(eye):
            present, done = bool(c[f'path_{eye}']), c[f'done_{eye}']
            if done:
                bg, fg, border = ft.Colors.GREEN_700, ft.Colors.WHITE, None
            elif present:
                bg, fg, border = (ft.Colors.BLUE_700 if eye == "L" else ft.Colors.RED_700), ft.Colors.WHITE, None
            else:
                bg, fg, border = None, ft.Colors.OUTLINE, ft.Border.all(1, ft.Colors.OUTLINE_VARIANT)
            return ft.Container(ft.Text(eye, size=11, weight=ft.FontWeight.BOLD, color=fg),
                                bgcolor=bg, border=border, width=24, height=20, border_radius=4,
                                alignment=ft.Alignment.CENTER)

        size = c['size_L'] + c['size_R']
        return ft.Container(
            content=ft.Row([
                ft.Container(ft.Checkbox(value=c['transfer'], data=i, on_change=self.on_row_check), width=40),
                ft.Text(c['mkey'], width=110, weight=ft.FontWeight.BOLD, font_family=MONO, size=13,
                        tooltip=f"{c['cam']} · {c['id']}"),
                ft.Row([badge("L"), badge("R")], width=64, spacing=4),
                ft.Text(name or "–", expand=True, font_family=MONO, size=13,
                        color=ft.Colors.ON_SURFACE if name else ft.Colors.ON_SURFACE_VARIANT,
                        overflow=ft.TextOverflow.ELLIPSIS, max_lines=1),
                ft.Text(fmt_size(size), width=76, size=12, text_align=ft.TextAlign.RIGHT),
                ft.Text(stat, width=150, size=12, weight=ft.FontWeight.BOLD, color=stat_color,
                        tooltip=stat_tip, overflow=ft.TextOverflow.ELLIPSIS, max_lines=1),
            ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            height=ROW_H, data=i, on_click=self.on_row_click,
            padding=ft.Padding.symmetric(horizontal=8),
            bgcolor=ft.Colors.PRIMARY_CONTAINER if selected else None,
            border=ft.Border.only(
                left=ft.BorderSide(3, ft.Colors.PRIMARY if selected else ft.Colors.TRANSPARENT),
                bottom=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT)),
        )

    def refresh(self):
        """Rebuild the whole list and all summaries (call after structural changes)."""
        self.list_view.controls = [self.build_row(i, c) for i, c in enumerate(self.clips)]
        self.refresh_summary()

    def refresh_row(self, i):
        if 0 <= i < len(self.clips) and i < len(self.list_view.controls):
            self.list_view.controls[i] = self.build_row(i, self.clips[i])

    def refresh_summary(self):
        has = bool(self.clips)
        self.list_view.visible = has
        self.empty_state.visible = not has

        logged = sum(1 for c in self.clips if c['logged'])
        done = sum(1 for c in self.clips if c['state'] == 'complete')
        self.lbl_counts.value = self.tr("counts", n=len(self.clips), logged=logged, done=done) if has else ""

        pending = [c for c in self.clips if c['transfer'] and c['logged']]
        unlogged = sum(1 for c in self.clips if c['transfer'] and not c['logged'])
        self.lbl_summary.value = self.tr("ingest_summary", n=len(pending),
                                         size=fmt_size(sum(self.copy_size(c) for c in pending)))
        self.lbl_ingest_warn.value = self.tr("warn_unlogged", n=unlogged) if unlogged else ""
        self.lbl_ingest_warn.visible = bool(unlogged)
        self.update_free_space()
        self.update_name_preview()

    def update_free_space(self):
        root = self.settings.get("stammordner")
        try:
            self.lbl_free.value = self.tr("free_space", size=fmt_size(shutil.disk_usage(root).free)) if root else ""
        except OSError:
            self.lbl_free.value = ""

    def update_target_label(self):
        d = self.project_dir()
        if not d:
            self.lbl_target.value = ""
            return
        sub = f"Tag_{self.day.strip().zfill(2)}" if self.settings["sort_mode"] == "Drehtage" else "Szene_XX"
        self.lbl_target.value = self.tr("target_prefix") + str(d / sub)

    def update_name_preview(self):
        self.lbl_next_name.value = build_name(self.settings, self.project_name.strip(),
                                              self.scene, self.setting, self.take, self.cam_id)
        c = self.clips[self.current] if 0 <= self.current < len(self.clips) else None
        name = self.clip_name(c) if c else None
        self.lbl_clip_name.value = f"{self.tr('clip_name')}: {name}" if name else ""

    def set_status(self, msg, warn=False, error=False):
        self.status_text.value = msg
        self.status_text.color = ft.Colors.RED_400 if error else (ft.Colors.AMBER_400 if warn else None)

    def _set_text_focus(self, focused):
        self._text_focused = focused
        self.mode_icon.name = ft.Icons.EDIT if focused else ft.Icons.KEYBOARD
        self.mode_icon.color = ft.Colors.AMBER_400 if focused else ft.Colors.GREEN_400
        self.mode_text.value = self.tr("mode_text" if focused else "mode_hotkeys")
        self.mode_text.color = self.mode_icon.color

    async def _leave_text(self, e=None):
        if self._text_focused:
            self._set_text_focus(False)
            await self.kb.focus()
        self.page.update()

    def set_busy(self, busy):
        self.busy = busy
        for ctrl in (self.btn_add, self.btn_clear, self.btn_settings, self.root_box, self.tf_project, self.tf_day):
            ctrl.disabled = busy
        self.btn_start.disabled = busy
        self.btn_cancel.disabled = not busy
        self.pb_ingest.visible = busy
        self.row_progress.visible = busy
        if busy:
            self.pb_ingest.value = 0
        else:
            self.lbl_current.value = ""
            self.lbl_mbps.value = ""

    # ================================================================ list scrolling
    def _on_list_scroll(self, e):
        self._list_px = e.pixels
        self._list_h = e.viewport_dimension or self._list_h

    def _on_list_size(self, e):
        self._list_h = e.height or self._list_h

    async def _ensure_visible(self, idx):
        top, bottom = idx * ROW_H, (idx + 1) * ROW_H
        if top < self._list_px:
            target = top
        elif bottom > self._list_px + self._list_h:
            target = bottom - self._list_h
        else:
            return
        self._list_px = max(0.0, target)
        await self.list_view.scroll_to(offset=self._list_px, duration=80)

    # ================================================================ header handlers
    def on_project_change(self, e):
        self.project_name = INVALID_CHARS.sub("_", e.control.value)
        self.update_target_label()
        self.update_name_preview()

    def on_project_commit(self, e=None):
        if self.tf_project.value != self.project_name:
            self.tf_project.value = self.project_name
        self.settings["last_project"] = self.project_name
        self.save_config()
        self.load_manifest()
        self.refresh()
        self.page.update()

    def on_day_change(self, e):
        self.day = INVALID_CHARS.sub("_", e.control.value).strip() or "1"
        self.update_target_label()

    def on_day_commit(self, e=None):
        self.settings["last_day"] = self.day
        self.save_config()
        self.page.update()

    def _update_log_state(self, e=None):
        self.scene = self.tf_scene.value.strip()
        self.setting = self.tf_setting.value.strip()
        self.take = self.tf_take.value.strip()
        self.cam_id = INVALID_CHARS.sub("_", self.tf_cam_id.value.strip())
        self.update_name_preview()

    def update_log_fields(self):
        self.tf_scene.value, self.tf_setting.value = self.scene, self.setting
        self.tf_take.value, self.tf_cam_id.value = self.take, self.cam_id
        self.update_name_preview()

    async def pick_root(self, e):
        if self.busy:
            return
        path = await self.root_picker.get_directory_path(dialog_title=self.tr("lbl_root"))
        if path:
            self.settings["stammordner"] = path
            self.save_config()
            self.lbl_root.value = path
            self.root_box.tooltip = path
            self.update_target_label()
            self.load_manifest()
            self.refresh()
            self.page.update()

    def open_settings(self, e):
        if self.busy:
            return
        self._dialog_open = True
        dlg = SettingsDialog(self.page, dict(self.settings), HAS_XXHASH, self.tr,
                             self.on_settings_saved, APP_VERSION,
                             on_close=self._on_dialog_closed,
                             ffmpeg_info=lambda: ffmpeg_version(self.ffmpeg_path, self.is_windows))
        dlg.open()

    def _on_dialog_closed(self):
        self._dialog_open = False
        self.page.run_task(self._refocus)

    def on_settings_saved(self, new_settings):
        self._dialog_open = False
        self.settings.update(new_settings)
        self.save_config()
        self.build_ui()
        self.refresh()
        self.page.update()

    # ================================================================ list handlers
    async def on_row_click(self, e):
        await self._leave_text()
        self.select(e.control.data, scroll=False)
        self.page.update()

    def on_row_check(self, e):
        idx = e.control.data
        if 0 <= idx < len(self.clips):
            self.clips[idx]['transfer'] = e.control.value
            self.refresh_row(idx)
            self.refresh_summary()
            self.page.update()

    def select(self, idx, scroll=True):
        if not (0 <= idx < len(self.clips)):
            return
        old, self.current = self.current, idx
        self.refresh_row(old)
        self.refresh_row(idx)
        self.update_name_preview()
        c = self.clips[idx]
        self.lbl_preview.value = f"{c['cam']}  ·  " + "  ·  ".join(
            f"{e}: {Path(c[f'path_{e}']).name}" for e in "LR" if c[f'path_{e}']) or c['mkey']
        self.request_preview(c)
        if scroll:
            self.page.run_task(self._ensure_visible, idx)

    def select_rel(self, d):
        if not self.clips:
            return
        if self.current < 0:
            self.select(0)
        else:
            self.select(max(0, min(len(self.clips) - 1, self.current + d)))

    async def clear_list(self, e):
        if self.busy or not self.clips:
            return
        ok = await self.dialog(self.tr("dlg_clear_title"), self.tr("dlg_clear_body"),
                               actions=[(self.tr("btn_abort"), False, None),
                                        (self.tr("btn_clear"), True, ft.Colors.RED_700)])
        if not ok:
            return
        self.clips, self.current = [], -1
        self.img_L.src = self.img_R.src = BLANK_PNG
        self.lbl_preview.value = self.tr("preview_none")
        self.refresh()
        self.set_status(self.tr("status_ready"))
        self.page.update()

    # ================================================================ scanning
    async def pick_source(self, e):
        if self.busy:
            return
        path = await self.src_picker.get_directory_path(dialog_title=self.tr("btn_add_source"))
        if not path:
            return
        self.set_status(self.tr("scanning", path=path))
        self.page.update()
        threading.Thread(target=self._scan_worker, args=(path,), daemon=True).start()

    def _scan_worker(self, path):
        try:
            found = IngestManager(self.settings, self.thumb_dir, self.ffmpeg_path, self.is_windows).scan_folder(path)
            self._ui(self._merge_scan, path, found)
        except Exception as ex:
            logging.error(f"Scan error {path}: {ex}", exc_info=True)
            self._ui(self.set_status, f"Scan: {ex}", False, True)

    def _merge_scan(self, path, found):
        by_key = {c['key']: c for c in self.clips}
        selected_key = self.clips[self.current]['key'] if 0 <= self.current < len(self.clips) else None
        touched, added, dupes, spans = set(), 0, 0, 0

        for it in sorted(found, key=lambda x: x['p']):
            eye = it['e']
            group = [c for c in by_key.values() if c['id'] == it['id'] and c['cam'] == it['cam']]
            c = choose_pair_candidate(group, eye, it.get('t'), it['p'], it.get('recid'))
            if c is None:
                key, n = it['id'], 1
                while key in by_key:
                    n += 1
                    key = f"{it['id']}~{n}"
                c = by_key[key] = self.new_clip(key, it)
                if n > 1:
                    dupes += 1
            if c[f'path_{eye}'] == it['p']:
                continue
            c[f'path_{eye}'], c[f'size_{eye}'], c[f'mtime_{eye}'] = it['p'], it['s'], it.get('t')
            c[f'recid_{eye}'] = it.get('recid')
            c['span'] = c['span'] or it.get('span', False)
            spans += bool(it.get('span'))
            touched.add(c['key'])
            added += 1

        self.clips = sorted(by_key.values(), key=lambda c: c['key'])
        self.assign_mkeys([c for c in self.clips if c['key'] in touched])

        keys = [c['key'] for c in self.clips]
        self.current = keys.index(selected_key) if selected_key in keys else -1
        self.refresh()
        if not found:
            self.set_status(self.tr("scan_none", path=path), warn=True)
        elif dupes:
            self.set_status(self.tr("scan_dupes", n=dupes), warn=True)
        elif spans:
            self.set_status(self.tr("scan_spans", n=spans), warn=True)
        else:
            self.set_status(self.tr("scan_done", n=added, path=path))
        if self.current < 0 and self.clips:
            self.select(0)
        elif selected_key in touched:
            self.select(self.current, scroll=False)

    # ================================================================ preview
    def request_preview(self, c):
        with self.preview_queue.mutex:
            self.preview_queue.queue.clear()
        self.preview_queue.put((c['key'], c['path_L'], c['path_R']))

    def _make_thumb(self, video):
        if not video or not self.ffmpeg_path:
            return None
        out = self.thumb_dir / f"prev_{file_key(video)}.jpg"
        if not out.exists():
            subprocess.run([self.ffmpeg_path, '-y', '-ss', '1.0', '-i', video, '-frames:v', '1',
                            '-vf', 'scale=480:-2', str(out)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           creationflags=0x08000000 if self.is_windows else 0)
        if out.exists():
            return out.read_bytes()
        return None

    def _preview_worker(self):
        while True:
            key, path_l, path_r = self.preview_queue.get()
            try:
                imgs = (self._make_thumb(path_l), self._make_thumb(path_r))
                self._ui(self._show_preview, key, *imgs)
            except Exception as e:
                logging.error(f"Preview error: {e}")

    def _show_preview(self, key, img_l, img_r):
        if not (0 <= self.current < len(self.clips)) or self.clips[self.current]['key'] != key:
            return
        self.img_L.src = img_l or BLANK_PNG
        self.img_R.src = img_r or BLANK_PNG

    # ================================================================ hotkeys
    async def on_keyboard(self, e: ft.KeyboardEvent):
        if self._dialog_open:
            return
        key = e.key or ""
        if self._text_focused:
            if key == "Escape":
                await self._leave_text()
            return
        if e.ctrl or e.alt or e.meta:
            return
        if key == "Arrow Down":
            self.select_rel(1)
        elif key == "Arrow Up":
            self.select_rel(-1)
        elif self.busy:
            return
        elif key == "Arrow Right":
            self.hk_confirm_and_next()
        elif key in ("Delete", "Backspace"):
            self.hk_toggle_transfer()
        elif key.upper() == "S":
            self.hk_new_scene()
        elif key.upper() == "E":
            self.hk_new_setting()
        elif key.upper() == "T":
            self.hk_plus_take()
        else:
            return
        self.page.update()

    def _run_hotkey(self, fn):
        if not self.busy:
            fn()
            self.page.update()

    def hk_new_scene(self):
        self.scene, self.setting, self.take = inc(self.scene), "1", "1"
        self.update_log_fields()

    def hk_new_setting(self):
        self.setting, self.take = inc(self.setting), "1"
        self.update_log_fields()

    def hk_plus_take(self):
        self.take = inc(self.take)
        self.update_log_fields()

    def hk_toggle_transfer(self):
        if 0 <= self.current < len(self.clips):
            c = self.clips[self.current]
            c['transfer'] = not c['transfer']
            self.refresh_row(self.current)
            self.refresh_summary()

    def hk_confirm_and_next(self):
        if not (0 <= self.current < len(self.clips)):
            return
        c = self.clips[self.current]
        if c.get('locked_name'):
            # Other eye already copied under this name – keep it so L/R stay paired
            c['transfer'] = True
            self.set_status(self.tr("locked_name", name=c['locked_name']), warn=True)
        else:
            c.update(scene=self.scene, setting=self.setting, take=self.take, cam_id=self.cam_id,
                     logged=True, transfer=True)
            if c['state'] == 'failed':
                c['state'] = 'new'
            self.take = inc(self.take)
            self.update_log_fields()
        self.refresh_row(self.current)
        self.refresh_summary()
        self.select_rel(1)

    # ================================================================ dialogs
    async def dialog(self, title, body, items=None, actions=None, width=520):
        """Shows a modal dialog and returns the value of the pressed action."""
        fut = asyncio.get_running_loop().create_future()

        def finish(value):
            if not fut.done():
                fut.set_result(value)
            self.page.pop_dialog()

        content = [ft.Text(body)] if body else []
        if items:
            shown = items[:25]
            lines = [ft.Text(i, size=12, font_family=MONO, selectable=True) for i in shown]
            if len(items) > len(shown):
                lines.append(ft.Text(self.tr("and_more", n=len(items) - len(shown)), size=12, italic=True))
            content.append(ft.Container(ft.Column(lines, spacing=2, scroll=ft.ScrollMode.AUTO),
                                        height=min(300, 20 * len(lines) + 10), padding=8,
                                        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST, border_radius=6))
        actions = actions or [(self.tr("btn_ok"), True, None)]
        # Not modal: Esc / click outside dismisses, which always counts as "cancel" (None)
        dlg = ft.AlertDialog(
            modal=False, title=ft.Text(title),
            content=ft.Container(ft.Column(content, tight=True, spacing=10), width=width),
            actions=[ft.FilledButton(label, bgcolor=color, color=ft.Colors.WHITE if color else None,
                                     on_click=lambda e, v=value: finish(v))
                     if color else ft.TextButton(label, on_click=lambda e, v=value: finish(v))
                     for label, value, color in actions],
            on_dismiss=lambda e: fut.done() or fut.set_result(None),
        )
        self._dialog_open = True
        self.page.show_dialog(dlg)
        try:
            return await fut
        finally:
            self._dialog_open = False
            await self._refocus()

    async def _refocus(self):
        """After a dialog closes nothing has focus and the first key press would get lost."""
        try:
            await self.kb.focus()
        except Exception as e:
            logging.error(f"Refocus failed: {e}")

    # ================================================================ ingest
    async def start_ingest(self, e):
        if self.busy:
            return
        await self._leave_text()
        tr = self.tr
        if not self.settings.get("stammordner"):
            await self.dialog(tr("grp_ingest"), tr("err_no_root"))
            return
        if not Path(self.settings["stammordner"]).is_dir():
            await self.dialog(tr("grp_ingest"), tr("err_root_missing", path=self.settings["stammordner"]))
            return
        if not self.project_name.strip():
            await self.dialog(tr("grp_ingest"), tr("err_no_project"))
            return

        selected = [c for c in self.clips if c['transfer'] and c['logged']]
        if not selected:
            self.set_status(tr("msg_no_copy"), warn=True)
            self.page.update()
            return

        base = self.project_dir()
        planner = IngestManager(self.settings, self.thumb_dir, self.ffmpeg_path, self.is_windows)
        jobs, pre_errors = [], []
        for c in selected:
            bn = self.clip_name(c)
            sub = dict(c)
            wanted = self.eyes_to_copy(c)
            for eye in "LR":
                if eye not in wanted:
                    sub[f'path_{eye}'] = None
            plans = planner.plan_clip(sub, self.clip_root(base, c), bn)
            if not plans:
                pre_errors.append(tr("err_missing_src", name=c['mkey']))
                continue
            jobs.append({'key': c['mkey'], 'bn': bn, 'plans': plans,
                         'clip': {k: c[k] for k in ('id', 'scene', 'setting', 'take', 'cam_id', 'recid_L', 'recid_R')}})
        if not jobs:
            await self.dialog(tr("grp_ingest"), tr("msg_no_copy"), items=pre_errors)
            return
        if not self.ffmpeg_path and any(planner.needs_ffmpeg(j['plans']) for j in jobs):
            await self.dialog(tr("grp_ingest"), tr("err_ffmpeg_mov"))
            return

        # Two clips must never write to the same file
        owners, dupes = {}, []
        for j in jobs:
            for t in planner.plan_targets(j['plans']):
                k = str(t).lower()
                if k in owners and owners[k] != j['key']:
                    dupes.append(f"{t.name}   ({owners[k]} / {j['key']})")
                owners.setdefault(k, j['key'])
        if dupes:
            await self.dialog(tr("dlg_dupes_title"), tr("dlg_dupes_body"), items=dupes)
            return

        existing = [str(t.relative_to(base)) for j in jobs for t in planner.plan_targets(j['plans']) if t.exists()]
        if existing:
            ok = await self.dialog(tr("dlg_exist_title"), tr("dlg_exist_body", n=len(existing)), items=existing,
                                   actions=[(tr("btn_abort"), False, None),
                                            (tr("btn_overwrite"), True, ft.Colors.RED_700)])
            if not ok:
                return

        need = sum(planner.plan_bytes(j['plans']) for j in jobs)
        try:
            free = shutil.disk_usage(self.settings["stammordner"]).free
            if free < need:
                await self.dialog(tr("grp_ingest"), tr("err_space", free=fmt_size(free), need=fmt_size(need)))
                return
            if free - need < LOW_SPACE:
                self.set_status(tr("warn_space"), warn=True)
        except OSError as ex:
            await self.dialog(tr("grp_ingest"), str(ex))
            return

        self.set_busy(True)
        self.page.update()

        callbacks = {
            'on_status': lambda msg: self._ui(self._on_ingest_status, msg),
            'on_total_progress': lambda pct, mbps, eta: self._ui(self._on_ingest_progress, pct, mbps, eta),
            'on_clip_start': lambda key: self._ui(self._on_clip_start, key),
            'on_clip_done': lambda key, entry, failed: self._ui(self._on_clip_done, key, entry, failed),
        }
        self.manager = IngestManager(self.settings, self.thumb_dir, self.ffmpeg_path, self.is_windows, callbacks)
        threading.Thread(target=self._ingest_worker,
                         args=(self.manager, jobs, self.project_name.strip(), base, pre_errors),
                         daemon=True).start()

    def _ingest_worker(self, manager, jobs, project, base, pre_errors):
        try:
            result = manager.run_ingest(jobs, project, base, self.manifest, base / MANIFEST_FILE)
        except Exception as ex:
            logging.error(f"Ingest crashed: {ex}", exc_info=True)
            result = {'manifest': None, 'errors': [f"Ingest: {ex}"], 'warnings': [], 'clips_ok': 0,
                      'clips_failed': len(jobs), 'cancelled': False, 'bytes': 0,
                      'html_report': None, 'csv': None}
        result['errors'] = pre_errors + result['errors']
        self._ui(self._on_ingest_finished, result, base)

    def _find(self, key):
        for i, c in enumerate(self.clips):
            if c['mkey'] == key:
                return i, c
        return -1, None

    def _on_ingest_status(self, msg):
        self.lbl_current.value = msg

    def _on_ingest_progress(self, pct, mbps, eta):
        self.pb_ingest.value = pct / 100
        m, s = divmod(int(eta), 60)
        self.lbl_mbps.value = f"{pct:.0f} %  ·  {mbps:.1f} MB/s  ·  ETA {m}:{s:02d}"

    def _on_clip_start(self, key):
        i, c = self._find(key)
        if c:
            c['state'] = 'working'
            self.refresh_row(i)

    def _on_clip_done(self, key, entry, failed_eyes):
        self.manifest[key] = entry
        i, c = self._find(key)
        if c:
            self.apply_manifest(c)
            if failed_eyes:
                c['state'] = 'failed'
            self.refresh_row(i)

    async def _on_ingest_finished_async(self, result, base):
        tr = self.tr
        errors, warnings = result.get('errors', []), result.get('warnings', [])
        if result.get('cancelled'):
            title = tr("dlg_done_cancel")
        elif errors:
            title = tr("dlg_done_err")
        else:
            title = tr("dlg_done_ok")
        self.set_status(title, warn=result.get('cancelled'), error=bool(errors))
        self.page.update()

        lines = [f"✖ {e}" for e in errors] + [f"• {w}" for w in warnings]
        body = tr("done_summary", ok=result.get('clips_ok', 0), failed=result.get('clips_failed', 0),
                  size=fmt_size(result.get('bytes', 0)))
        if result.get('csv'):
            body += "\n" + tr("done_csv")
        actions = [(tr("btn_open_folder"), "folder", None)]
        if result.get('html_report'):
            actions.append((tr("btn_open_report"), "report", None))
        actions.append((tr("btn_ok"), "ok", ft.Colors.BLUE_700))

        choice = await self.dialog(title, body, items=lines or None, actions=actions, width=640)
        if choice == "folder":
            open_path(base)
        elif choice == "report":
            open_path(result['html_report'])

    def _on_ingest_finished(self, result, base):
        if result.get('manifest') is not None:
            self.manifest = result['manifest']
        for c in self.clips:
            was_failed = c['state'] == 'failed'
            self.apply_manifest(c)
            if was_failed and c['state'] != 'complete':
                c['state'] = 'failed'
        self.set_busy(False)
        self.manager = None
        self.refresh()
        self.page.run_task(self._on_ingest_finished_async, result, base)

    def cancel_ingest(self, e):
        if self.manager:
            self.manager.cancel_event.set()
            self.btn_cancel.disabled = True
            self.set_status(self.tr("cancelling"), warn=True)
            self.page.update()
