import flet as ft
from ui.main_window import IngestProApp, APP_VERSION

def main(page: ft.Page):
    page.title = f"3DCam2Post Bridge v{APP_VERSION}"
    # Flet automatically looks in the 'assets' folder
    page.window.icon = "icon.ico"
    page.icon = "icon.ico"
    page.theme_mode = ft.ThemeMode.DARK
    page.window.width = 1800
    page.window.height = 950
    page.padding = 20
    
    app = IngestProApp(page)
    # The IngestProApp will add its components directly to the page

if __name__ == "__main__":
    # Remove assets_dir="." to use the default 'assets' folder
    ft.run(main)
