import flet as ft

class SettingsDialog:
    def __init__(self, page: ft.Page, defaults, has_xxhash, tr, on_save, on_open_manual, app_version="1.1.0"):
        self.page = page
        self.defaults = defaults
        self.has_xxhash = has_xxhash
        self.tr = tr
        self.on_save_cb = on_save
        self.on_open_manual = on_open_manual
        self.app_version = app_version

        # State Variables
        self.lang_var = self.defaults.get("language", "de")
        self.cam_var = self.defaults.get("use_cam_id", False)
        self.sort_var = self.defaults.get("sort_mode", "Drehtage")
        self.pad_s = str(self.defaults.get("padding_s", 2))
        self.pad_e = str(self.defaults.get("padding_e", 2))
        self.pad_t = str(self.defaults.get("padding_t", 3))
        self.verify_var = self.defaults.get("verify_copy", False)
        self.thumb_var = self.defaults.get("generate_thumbs", True)
        self.algo_var = self.defaults.get("hash_algo", "md5")
        self.audio_var = self.defaults.get("audio_source", "Links")
        self.strip_audio_var = self.defaults.get("strip_audio_eye", False)

        self.dialog = ft.AlertDialog(
            title=ft.Row([
                ft.Text(self.tr("win_settings"), weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                ft.Text(f"v{self.app_version}", size=12, color=ft.Colors.GREY_500)
            ]),
            content=self.build_content(),
            actions=[
                ft.ElevatedButton(self.tr("btn_manual"), on_click=lambda e: self.on_open_manual(), bgcolor=ft.Colors.CYAN_700, color=ft.Colors.WHITE),
                ft.ElevatedButton(self.tr("btn_save"), on_click=self.save_clicked, bgcolor=ft.Colors.GREEN_700, color=ft.Colors.WHITE)
            ],
            actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

    def _set_lang(self, e): self.lang_var = e.control.value
    def _set_cam(self, e): self.cam_var = e.control.value
    def _set_sort(self, e): self.sort_var = e.control.value
    def _set_verify(self, e): self.verify_var = e.control.value
    def _set_thumb(self, e): self.thumb_var = e.control.value
    def _set_algo(self, e): self.algo_var = e.control.value
    def _set_audio(self, e): self.audio_var = e.control.value
    def _set_strip(self, e): self.strip_audio_var = e.control.value
    def _set_pad_s(self, e): self.pad_s = e.control.value
    def _set_pad_e(self, e): self.pad_e = e.control.value
    def _set_pad_t(self, e): self.pad_t = e.control.value

    def build_content(self):
        xx_text = self.tr("opt_xx")
        if not self.has_xxhash: xx_text += " [Not installed]"

        return ft.Container(
            width=600,
            height=700,
            content=ft.Column(
                scroll=ft.ScrollMode.AUTO,
                spacing=15,
                controls=[
                    # Language
                    ft.Text(self.tr("sec_lang"), weight=ft.FontWeight.BOLD, size=16),
                    ft.RadioGroup(
                        content=ft.Row([ft.Radio(value="de", label="Deutsch"), ft.Radio(value="en", label="English")]),
                        value=self.lang_var, on_change=self._set_lang
                    ),
                    ft.Divider(),

                    # Advanced
                    ft.Text(self.tr("sec_advanced"), weight=ft.FontWeight.BOLD, size=16),
                    ft.Switch(label=self.tr("opt_cam_id"), value=self.cam_var, on_change=self._set_cam),
                    ft.RadioGroup(
                        content=ft.Column([
                            ft.Radio(value="Drehtage", label=self.tr("opt_sort_day")),
                            ft.Radio(value="Szenen", label=self.tr("opt_sort_scene"))
                        ]),
                        value=self.sort_var, on_change=self._set_sort
                    ),
                    ft.Row([
                        ft.Text(self.tr("lbl_digits_s")),
                        ft.Dropdown(value=self.pad_s, width=80, options=[ft.dropdown.Option(key=str(i), text=str(i)) for i in range(1, 4)], on_select=self._set_pad_s),
                        ft.Text(self.tr("lbl_digits_e")),
                        ft.Dropdown(value=self.pad_e, width=80, options=[ft.dropdown.Option(key=str(i), text=str(i)) for i in range(1, 4)], on_select=self._set_pad_e),
                        ft.Text(self.tr("lbl_digits_t")),
                        ft.Dropdown(value=self.pad_t, width=80, options=[ft.dropdown.Option(key=str(i), text=str(i)) for i in range(2, 6)], on_select=self._set_pad_t),
                    ], alignment=ft.MainAxisAlignment.START),
                    ft.Divider(),

                    # Verification
                    ft.Text(self.tr("sec_verify"), weight=ft.FontWeight.BOLD, size=16),
                    ft.Switch(label=self.tr("opt_verify"), value=self.verify_var, on_change=self._set_verify),
                    ft.Switch(label=self.tr("opt_thumbs"), value=self.thumb_var, on_change=self._set_thumb),
                    ft.Text(self.tr("desc_verify"), color=ft.Colors.GREY_400, size=12),
                    ft.RadioGroup(
                        content=ft.Column([
                            ft.Radio(value="md5", label=self.tr("opt_md5")),
                            ft.Radio(value="xxhash", label=xx_text, disabled=not self.has_xxhash),
                            ft.Radio(value="sha256", label=self.tr("opt_sha")),
                        ]),
                        value=self.algo_var, on_change=self._set_algo
                    ),
                    ft.Divider(),

                    # Audio
                    ft.Text(self.tr("sec_audio"), weight=ft.FontWeight.BOLD, size=16),
                    ft.RadioGroup(
                        content=ft.Row([
                            ft.Radio(value="Links", label=self.tr("opt_audio_l")),
                            ft.Radio(value="Rechts", label=self.tr("opt_audio_r")),
                            ft.Radio(value="Beide", label=self.tr("opt_audio_b")),
                        ]),
                        value=self.audio_var, on_change=self._set_audio
                    ),
                    ft.Switch(label=self.tr("opt_strip"), value=self.strip_audio_var, on_change=self._set_strip)
                ]
            )
        )

    def save_clicked(self, e):
        self.defaults.update({
            "language": self.lang_var,
            "use_cam_id": self.cam_var,
            "verify_copy": self.verify_var,
            "generate_thumbs": self.thumb_var,
            "hash_algo": self.algo_var,
            "audio_source": self.audio_var,
            "strip_audio_eye": self.strip_audio_var,
            "padding_s": int(self.pad_s),
            "padding_e": int(self.pad_e),
            "padding_t": int(self.pad_t),
            "sort_mode": self.sort_var
        })
        self.close_dialog()
        if self.on_save_cb:
            self.on_save_cb(self.defaults)

    def open(self):
        self.page.show_dialog(self.dialog)

    def close_dialog(self, e=None):
        self.page.pop_dialog()
