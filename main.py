import logging

import flet as ft

from core.paths import user_data_dir
from ui.main_window import IngestProApp, APP_VERSION

logging.basicConfig(
    filename=str(user_data_dir() / "3dcam2post.log"),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)


def main(page: ft.Page):
    page.title = f"3DCam2Post Bridge v{APP_VERSION}"
    # Flet automatically looks in the 'assets' folder
    page.window.icon = "icon.ico"
    page.theme_mode = ft.ThemeMode.DARK
    page.theme = ft.Theme(color_scheme_seed=ft.Colors.BLUE)
    page.dark_theme = ft.Theme(color_scheme_seed=ft.Colors.BLUE)
    page.window.width = 1500
    page.window.height = 940
    page.window.min_width = 1200
    page.window.min_height = 860
    page.padding = 16

    IngestProApp(page)


if __name__ == "__main__":
    ft.run(main)
