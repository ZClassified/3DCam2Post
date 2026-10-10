import subprocess

import flet as ft

REPO_URL = "https://github.com/ZClassified/3DCam2Post"
COPYRIGHT = "© 2026 ZClassified"

# Keep in sync with THIRD_PARTY_NOTICES.md
COMPONENTS = [
    ("FFmpeg", "GPL-3.0-or-later", "https://ffmpeg.org"),
    ("Flet", "Apache-2.0", "https://flet.dev"),
    ("Flutter", "BSD-3-Clause", "https://flutter.dev"),
    ("xxHash / python-xxhash", "BSD-2-Clause", "https://github.com/ifduyue/python-xxhash"),
    ("Python", "PSF License", "https://www.python.org"),
    ("PyInstaller (bootloader)", "GPL-2.0 + exception", "https://pyinstaller.org"),
]


def ffmpeg_version(ffmpeg_path, is_windows):
    if not ffmpeg_path:
        return None
    try:
        r = subprocess.run([ffmpeg_path, "-hide_banner", "-version"], stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL, text=True, timeout=10,
                           creationflags=0x08000000 if is_windows else 0)
        line = r.stdout.splitlines()[0] if r.stdout else ""
        # "ffmpeg version 8.1-essentials_build-www.gyan.dev Copyright (c) ..." -> "8.1-essentials_build-www.gyan.dev"
        return line.split(" Copyright")[0].replace("ffmpeg version ", "").strip() or None
    except Exception:
        return None


def build_about_dialog(tr, app_version, ffmpeg_info, on_close):
    def link(text, url, size=13):
        return ft.Text(spans=[ft.TextSpan(text, url=url, style=ft.TextStyle(
            color=ft.Colors.PRIMARY, decoration=ft.TextDecoration.UNDERLINE))], size=size)

    rows = []
    for name, lic, url in COMPONENTS:
        label = f"{name} {ffmpeg_info}" if name == "FFmpeg" and ffmpeg_info else name
        rows.append(ft.Row([
            ft.Container(link(label, url), expand=True),
            ft.Text(lic, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
        ]))

    content = ft.Column([
        ft.Text(f"3DCam2Post v{app_version}", size=18, weight=ft.FontWeight.BOLD),
        ft.Text(COPYRIGHT, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
        link(REPO_URL, REPO_URL, size=12),
        ft.Divider(),
        ft.Text(tr("about_license"), size=13),
        link("GNU General Public License v3.0", "https://www.gnu.org/licenses/gpl-3.0.html", size=12),
        ft.Divider(),
        ft.Text(tr("about_components"), weight=ft.FontWeight.BOLD),
        ft.Column(rows, spacing=4),
        ft.Text(tr("about_ffmpeg_note"), size=12, color=ft.Colors.ON_SURFACE_VARIANT),
    ], tight=True, spacing=8, scroll=ft.ScrollMode.AUTO)

    return ft.AlertDialog(
        modal=False,
        title=ft.Text(tr("about_title"), weight=ft.FontWeight.BOLD),
        content=ft.Container(content, width=520),
        actions=[ft.TextButton(tr("btn_close"), on_click=lambda e: on_close())],
        actions_alignment=ft.MainAxisAlignment.END,
    )
