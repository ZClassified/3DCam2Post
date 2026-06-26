import tkinter as tk
from tkinter import ttk
import customtkinter as ctk

class SettingsDialog:
    def __init__(self, parent, defaults, has_xxhash, tr, on_save, on_open_manual):
        self.defaults = defaults
        self.tr = tr
        self.on_save = on_save
        self.has_xxhash = has_xxhash
        self.on_open_manual = on_open_manual
        
        self.win = ctk.CTkToplevel(parent)
        self.win.title(self.tr("win_settings"))
        self.center_window(self.win, 600, 950)
        self.win.grab_set()

        self.lang_var = ctk.StringVar(value=self.defaults.get("language", "de"))
        self.cam_var = ctk.BooleanVar(value=self.defaults.get("use_cam_id", False))
        self.sort_var = ctk.StringVar(value=self.defaults.get("sort_mode", "Drehtage"))
        self.pad_s = ctk.StringVar(value=str(self.defaults.get("padding_s", 2)))
        self.pad_e = ctk.StringVar(value=str(self.defaults.get("padding_e", 2)))
        self.pad_t = ctk.StringVar(value=str(self.defaults.get("padding_t", 3)))
        self.verify_var = ctk.BooleanVar(value=self.defaults.get("verify_copy", False))
        self.thumb_var = ctk.BooleanVar(value=self.defaults.get("generate_thumbs", True))
        self.algo_var = ctk.StringVar(value=self.defaults.get("hash_algo", "md5"))
        self.audio_var = ctk.StringVar(value=self.defaults.get("audio_source", "Links"))
        self.strip_audio_var = ctk.BooleanVar(value=self.defaults.get("strip_audio_eye", False))
        
        self.build_ui()

    def center_window(self, win, width, height):
        win.update_idletasks()
        screen_width = win.winfo_screenwidth()
        screen_height = win.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        win.geometry(f'{width}x{height}+{x}+{y}')

    def build_ui(self):
        lang_sect = tk.LabelFrame(self.win, text=self.tr("sec_lang"), bg="#2b2b2b", fg="white", font=("Arial", 12, "bold"))
        lang_sect.pack(fill="x", padx=15, pady=5)
        ctk.CTkRadioButton(lang_sect, text="Deutsch", variable=self.lang_var, value="de").pack(side="left", padx=10, pady=5)
        ctk.CTkRadioButton(lang_sect, text="English", variable=self.lang_var, value="en").pack(side="left", padx=10, pady=5)
        
        adv_sect = tk.LabelFrame(self.win, text=self.tr("sec_advanced"), bg="#2b2b2b", fg="white", font=("Arial", 12, "bold"))
        adv_sect.pack(fill="x", padx=15, pady=5)
        ctk.CTkCheckBox(adv_sect, text=self.tr("opt_cam_id"), variable=self.cam_var).pack(anchor="w", pady=5, padx=10)
        
        ctk.CTkLabel(adv_sect, text="---", text_color="#cccccc").pack(fill="x", pady=2)
        ctk.CTkRadioButton(adv_sect, text=self.tr("opt_sort_day"), variable=self.sort_var, value="Drehtage").pack(anchor="w", padx=10, pady=2)
        ctk.CTkRadioButton(adv_sect, text=self.tr("opt_sort_scene"), variable=self.sort_var, value="Szenen").pack(anchor="w", padx=10, pady=2)

        ctk.CTkLabel(adv_sect, text="---", text_color="#cccccc").pack(fill="x", pady=2)
        pad_frame = ctk.CTkFrame(adv_sect)
        pad_frame.pack(anchor="w", pady=5, padx=10)
        
        pad_s_cb = ctk.CTkComboBox(pad_frame, values=["1","2","3"], width=60, variable=self.pad_s)
        pad_e_cb = ctk.CTkComboBox(pad_frame, values=["1","2","3"], width=60, variable=self.pad_e)
        pad_t_cb = ctk.CTkComboBox(pad_frame, values=["2","3","4","5"], width=60, variable=self.pad_t)
        
        ctk.CTkLabel(pad_frame, text=self.tr("lbl_digits_s")).pack(side="left", padx=(5,0))
        pad_s_cb.pack(side="left", padx=(5, 15))
        ctk.CTkLabel(pad_frame, text=self.tr("lbl_digits_e")).pack(side="left")
        pad_e_cb.pack(side="left", padx=(5, 15))
        ctk.CTkLabel(pad_frame, text=self.tr("lbl_digits_t")).pack(side="left")
        pad_t_cb.pack(side="left", padx=5)

        verify_sect = tk.LabelFrame(self.win, text=self.tr("sec_verify"), bg="#2b2b2b", fg="white", font=("Arial", 12, "bold"))
        verify_sect.pack(fill="x", padx=15, pady=5)
        ctk.CTkCheckBox(verify_sect, text=self.tr("opt_verify"), variable=self.verify_var).pack(anchor="w", padx=10, pady=5)
        
        ctk.CTkCheckBox(verify_sect, text=self.tr("opt_thumbs"), variable=self.thumb_var).pack(anchor="w", padx=20, pady=2)
        ctk.CTkLabel(verify_sect, text=self.tr("desc_verify"), font=("Arial", 10), text_color="#aaaaaa", justify="left").pack(anchor="w", padx=20, pady=(0, 5))
        
        ctk.CTkRadioButton(verify_sect, text=self.tr("opt_md5"), variable=self.algo_var, value="md5").pack(anchor="w", padx=20, pady=2)
        xx_text = self.tr("opt_xx")
        xx_state = "normal" if self.has_xxhash else "disabled"
        if not self.has_xxhash: xx_text += " [Nicht installiert/Not installed]"
        ctk.CTkRadioButton(verify_sect, text=xx_text, variable=self.algo_var, value="xxhash", state=xx_state).pack(anchor="w", padx=20, pady=2)
        ctk.CTkRadioButton(verify_sect, text=self.tr("opt_sha"), variable=self.algo_var, value="sha256").pack(anchor="w", padx=20, pady=2)

        audio_sect = tk.LabelFrame(self.win, text=self.tr("sec_audio"), bg="#2b2b2b", fg="white", font=("Arial", 12, "bold"))
        audio_sect.pack(fill="x", padx=15, pady=5)
        ctk.CTkRadioButton(audio_sect, text=self.tr("opt_audio_l"), variable=self.audio_var, value="Links").pack(side="left", padx=10, pady=5)
        ctk.CTkRadioButton(audio_sect, text=self.tr("opt_audio_r"), variable=self.audio_var, value="Rechts").pack(side="left", padx=10, pady=5)
        ctk.CTkRadioButton(audio_sect, text=self.tr("opt_audio_b"), variable=self.audio_var, value="Beide").pack(side="left", padx=10, pady=5)
        ctk.CTkCheckBox(audio_sect, text=self.tr("opt_strip"), variable=self.strip_audio_var).pack(anchor="w", pady=5, padx=10)

        help_sect = tk.LabelFrame(self.win, text=self.tr("sec_help"), bg="#2b2b2b", fg="white", font=("Arial", 12, "bold"))
        help_sect.pack(fill="x", padx=15, pady=20)
        ctk.CTkButton(help_sect, text=self.tr("btn_manual"), fg_color="#17a2b8", text_color="white", font=("Arial", 12, "bold"), command=self.on_open_manual).pack(fill="x", padx=10, pady=10)
        
        ctk.CTkButton(self.win, text=self.tr("btn_save"), fg_color="#28a745", text_color="white", font=("Arial", 12, "bold"), command=self.save).pack(side="bottom", pady=20, fill="x", padx=20)

    def save(self):
        self.defaults.update({
            "language": self.lang_var.get(),
            "use_cam_id": self.cam_var.get(),
            "verify_copy": self.verify_var.get(),
            "generate_thumbs": self.thumb_var.get(),
            "hash_algo": self.algo_var.get(),
            "audio_source": self.audio_var.get(),
            "strip_audio_eye": self.strip_audio_var.get(),
            "padding_s": int(self.pad_s.get()),
            "padding_e": int(self.pad_e.get()),
            "padding_t": int(self.pad_t.get()),
            "sort_mode": self.sort_var.get()
        })
        self.on_save(self.defaults)
        self.win.destroy()
