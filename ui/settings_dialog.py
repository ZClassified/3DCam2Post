import flet as ft

from core.ingest_manager import build_name


class SettingsDialog:
    def __init__(self, page: ft.Page, settings, has_xxhash, tr, on_save, app_version="", on_close=None):
        self.page = page
        self.s = settings  # working copy, only handed back on save
        self.has_xxhash = has_xxhash
        self.tr = tr
        self.on_save_cb = on_save
        self.on_close_cb = on_close
        self.app_version = app_version
        self._saved = False

        self.lbl_example = ft.Text("", font_family="Consolas", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        self.sw_thumbs = ft.Switch(label=tr("opt_thumbs"), value=self.s.get("generate_thumbs", True),
                                   on_change=self._setter("generate_thumbs"),
                                   disabled=not self.s.get("verify_copy", False))
        self.rg_algo = ft.RadioGroup(
            content=ft.Column([
                ft.Radio(value="md5", label=tr("opt_md5")),
                ft.Radio(value="xxhash", label=tr("opt_xx") + ("" if has_xxhash else tr("not_installed")),
                         disabled=not has_xxhash),
                ft.Radio(value="sha256", label=tr("opt_sha")),
            ], spacing=0),
            value=self.s.get("hash_algo", "md5"), on_change=self._setter("hash_algo"),
            disabled=not self.s.get("verify_copy", False),
        )
        self.audio_opts = ft.Column([
            ft.Row([
                ft.Text(tr("lbl_audio_source")),
                ft.RadioGroup(
                    content=ft.Row([ft.Radio(value="Links", label=tr("opt_audio_l")),
                                    ft.Radio(value="Rechts", label=tr("opt_audio_r")),
                                    ft.Radio(value="Beide", label=tr("opt_audio_b"))]),
                    value=self.s.get("audio_source", "Links"), on_change=self._setter("audio_source")),
            ]),
            ft.Switch(label=tr("opt_strip"), value=self.s.get("strip_audio_eye", False),
                      on_change=self._setter("strip_audio_eye")),
        ], disabled=not self.s.get("copy_audio", True))

        self.dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Text(tr("win_settings"), weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                ft.Text(f"v{app_version}", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
            ]),
            content=self.build_content(),
            actions=[
                ft.TextButton(tr("btn_abort"), on_click=self.close_dialog),
                ft.FilledButton(tr("btn_save"), on_click=self.save_clicked),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            on_dismiss=self._dismissed,
        )
        self._update_example()

    def _setter(self, key, cast=None, after=None):
        def handler(e):
            v = e.control.value
            self.s[key] = cast(v) if cast else v
            if after:
                after()
            self._update_example()
            self.page.update()
        return handler

    def _on_verify(self):
        on = self.s.get("verify_copy", False)
        self.sw_thumbs.disabled = not on
        self.rg_algo.disabled = not on

    def _on_copy_audio(self):
        self.audio_opts.disabled = not self.s.get("copy_audio", True)

    def _update_example(self):
        name = build_name(self.s, self.s.get("last_project") or "Projekt", 1, 2, 3, "A")
        self.lbl_example.value = self.tr("naming_example", name=f"{name}_L.MXF")

    @staticmethod
    def _section(title):
        return ft.Text(title, weight=ft.FontWeight.BOLD, size=15)

    def _pad_dropdown(self, key, rng):
        return ft.Dropdown(value=str(self.s.get(key, 2)), width=90, dense=True,
                           options=[ft.dropdown.Option(key=str(i), text=str(i)) for i in rng],
                           on_select=self._setter(key, int))

    def build_content(self):
        tr = self.tr
        return ft.Container(
            width=560, height=620,
            content=ft.Column(scroll=ft.ScrollMode.AUTO, spacing=12, controls=[
                self._section(tr("sec_lang")),
                ft.RadioGroup(content=ft.Row([ft.Radio(value="de", label="Deutsch"),
                                              ft.Radio(value="en", label="English")]),
                              value=self.s.get("language", "de"), on_change=self._setter("language")),
                ft.Divider(),

                self._section(tr("sec_naming")),
                ft.Switch(label=tr("opt_cam_id"), value=self.s.get("use_cam_id", False),
                          on_change=self._setter("use_cam_id")),
                ft.Row([
                    ft.Text(tr("lbl_digits_s")), self._pad_dropdown("padding_s", range(1, 5)),
                    ft.Text(tr("lbl_digits_e")), self._pad_dropdown("padding_e", range(1, 5)),
                    ft.Text(tr("lbl_digits_t")), self._pad_dropdown("padding_t", range(1, 6)),
                ], spacing=10),
                self.lbl_example,
                ft.RadioGroup(content=ft.Column([
                    ft.Radio(value="Drehtage", label=tr("opt_sort_day")),
                    ft.Radio(value="Szenen", label=tr("opt_sort_scene")),
                ], spacing=0), value=self.s.get("sort_mode", "Drehtage"), on_change=self._setter("sort_mode")),
                ft.Divider(),

                self._section(tr("sec_output")),
                ft.RadioGroup(content=ft.Column([
                    ft.Radio(value="p2", label=tr("opt_out_p2")),
                    ft.Radio(value="p2_mov", label=tr("opt_out_p2_mov")),
                    ft.Radio(value="mov", label=tr("opt_out_mov")),
                ], spacing=0), value=self.s.get("output_mode", "p2"), on_change=self._setter("output_mode")),
                ft.Text(tr("desc_output"), size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.Divider(),

                self._section(tr("sec_verify")),
                ft.Switch(label=tr("opt_verify"), value=self.s.get("verify_copy", False),
                          on_change=self._setter("verify_copy", after=self._on_verify)),
                self.sw_thumbs,
                self.rg_algo,
                ft.Divider(),

                self._section(tr("sec_audio")),
                ft.Switch(label=tr("opt_copy_audio"), value=self.s.get("copy_audio", True),
                          on_change=self._setter("copy_audio", after=self._on_copy_audio)),
                self.audio_opts,
            ]),
        )

    def save_clicked(self, e):
        self._saved = True
        self.page.pop_dialog()
        if self.on_save_cb:
            self.on_save_cb(self.s)

    def open(self):
        self.page.show_dialog(self.dialog)

    def close_dialog(self, e=None):
        self.page.pop_dialog()
        self._dismissed()

    def _dismissed(self, e=None):
        if not self._saved and self.on_close_cb:
            self.on_close_cb()
