import flet as ft
from ui.main_window import IngestProApp

def main(page: ft.Page):
    page.title = "3DCam2Post Bridge"
    page.window.icon = "design/3DCam2Post-Icon-V1.ico"
    page.theme_mode = ft.ThemeMode.DARK
    page.window.width = 1800
    page.window.height = 950
    page.padding = 20
    
    app = IngestProApp(page)
    # The IngestProApp will add its components directly to the page

if __name__ == "__main__":
    ft.run(main, assets_dir=".")
