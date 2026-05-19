import os
import tkinter as tk
from tkinter import filedialog, ttk
from app.i18n import t
from app.config import DEFAULT_API_URL


def _apply_round_region(win, radius: int = 20) -> None:
    if os.name != "nt":
        return
    try:
        import ctypes
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
        if not hwnd:
            hwnd = win.winfo_id()
        w, h = win.winfo_width(), win.winfo_height()
        if w > 1 and h > 1:
            hrgn = ctypes.windll.gdi32.CreateRoundRectRgn(0, 0, w + 1, h + 1, radius * 2, radius * 2)
            ctypes.windll.user32.SetWindowRgn(hwnd, hrgn, True)
    except Exception:
        pass

BG = "black"
FG_ACCENT = "#7adfff"
FG_LABEL = "#a0a0a0"
FG_VALUE = "#ffffff"
FG_SECTION = "#ffb86c"
ENTRY_BG = "#1a1a1a"
FONT = ("Consolas", 10)
FONT_BOLD = ("Consolas", 10, "bold")
FONT_SMALL = ("Consolas", 9)


def open_settings(parent_root, cfg: dict, config_path: str, on_save=None, base_dir: str = ""):
    win = tk.Toplevel(parent_root)
    win.overrideredirect(True)
    win.configure(bg=BG)
    win.attributes("-topmost", True)
    win.wm_attributes("-alpha", 0.97)

    WIN_W, WIN_H = 620, 680

    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    x = max(0, min((sw - WIN_W) // 2, sw - WIN_W))
    y = max(0, min((sh - WIN_H) // 2, sh - WIN_H))
    win.geometry(f"{WIN_W}x{WIN_H}+{x}+{y}")

    win.grab_set()

    # ── drag support ─────────────────────────────────────────────────────────
    _drag = {"x": 0, "y": 0}

    def _start(e): _drag["x"], _drag["y"] = e.x, e.y
    def _move(e):
        nx = max(0, min(e.x_root - _drag["x"], sw - WIN_W))
        ny = max(0, min(e.y_root - _drag["y"], sh - WIN_H))
        win.geometry(f"+{nx}+{ny}")

    # ── title bar ─────────────────────────────────────────────────────────────
    topbar = tk.Frame(win, bg=BG)
    topbar.pack(fill="x")

    title = tk.Label(topbar, text=t("settings.title"), fg=FG_ACCENT, bg=BG,
                     font=FONT_BOLD, anchor="w")
    title.pack(side="left", padx=10, pady=6)

    close_btn = tk.Label(topbar, text="✕", fg="#ff6666", bg=BG,
                         font=("Consolas", 13, "bold"), cursor="hand2")
    close_btn.pack(side="right", padx=8, pady=4)
    close_btn.bind("<Enter>", lambda e: close_btn.config(fg="#ffaaaa"))
    close_btn.bind("<Leave>", lambda e: close_btn.config(fg="#ff6666"))
    close_btn.bind("<Button-1>", lambda e: win.destroy())

    for w in (topbar, title):
        w.bind("<Button-1>", _start)
        w.bind("<B1-Motion>", _move)

    tk.Frame(win, bg="#2a2a2a", height=1).pack(fill="x")

    # ── content area ──────────────────────────────────────────────────────────
    body = tk.Frame(win, bg=BG)
    body.pack(fill="both", expand=True, padx=14, pady=6)

    entries = {}  # key → widget

    # ── language rebuild ──────────────────────────────────────────────────────
    def _on_lang_change(new_code):
        if base_dir:
            import app.i18n as _i18n
            _i18n.configure(base_dir, new_code)
        snap = dict(cfg)
        snap["gpt_api"] = _get_api_url()
        for k, w in entries.items():
            if isinstance(w, tk.BooleanVar):
                snap[k] = w.get()
            elif isinstance(w, tk.StringVar):
                val = w.get()
                if k in ("no_translate_langs", "ignore_names"):
                    snap[k] = [x.strip() for x in val.split(",") if x.strip()]
                else:
                    snap[k] = val
            else:
                raw = w.get().strip()
                if k in ("no_translate_langs", "ignore_names"):
                    snap[k] = [x.strip() for x in raw.split(",") if x.strip()]
                elif k == "temperature":
                    try: snap[k] = float(raw)
                    except ValueError: pass
                elif k in ("poll_interval_ms", "ticker_speed"):
                    try: snap[k] = int(raw)
                    except ValueError: pass
                else:
                    snap[k] = raw
        win.destroy()
        open_settings(parent_root, snap, config_path, on_save=on_save, base_dir=base_dir)

    # ── field helpers ─────────────────────────────────────────────────────────
    def section(text):
        tk.Label(body, text=text, fg=FG_SECTION, bg=BG,
                 font=FONT_BOLD, anchor="w").pack(fill="x", pady=(10, 1))
        tk.Frame(body, bg="#2a2a2a", height=1).pack(fill="x")

    def field(key, label, *, width=56, show=None, browse_file=False,
              browse_title="Select file", browse_types=None):
        row = tk.Frame(body, bg=BG)
        row.pack(fill="x", pady=(4, 0))
        tk.Label(row, text=label, fg=FG_LABEL, bg=BG,
                 font=FONT_SMALL, anchor="w", width=34).pack(side="left")
        e = tk.Entry(row, bg=ENTRY_BG, fg=FG_VALUE, insertbackground=FG_VALUE,
                     relief="flat", bd=3, highlightthickness=1,
                     highlightcolor=FG_ACCENT, highlightbackground="#2a2a2a",
                     font=FONT, show=show, width=width)
        val = cfg.get(key, "")
        if isinstance(val, list):
            val = ", ".join(str(v) for v in val)
        else:
            val = str(val) if val is not None else ""
        e.insert(0, val)
        e.pack(side="left", fill="x", expand=True)
        entries[key] = e

        if browse_file:
            def _browse(e=e, ti=browse_title, ft=browse_types):
                p = filedialog.askopenfilename(parent=win, title=ti, filetypes=ft or [("All files", "*.*")])
                if p:
                    e.delete(0, "end")
                    e.insert(0, p)
            btn = tk.Label(row, text="…", fg=FG_ACCENT, bg="#1a1a1a",
                           font=FONT_BOLD, cursor="hand2", padx=6, pady=1)
            btn.pack(side="left", padx=(4, 0))
            btn.bind("<Button-1>", lambda ev, b=_browse: b())
            btn.bind("<Enter>", lambda ev, b=btn: b.config(fg="#ffffff"))
            btn.bind("<Leave>", lambda ev, b=btn: b.config(fg=FG_ACCENT))

    def field_lang(key, label):
        row = tk.Frame(body, bg=BG)
        row.pack(fill="x", pady=(4, 0))
        tk.Label(row, text=label, fg=FG_LABEL, bg=BG,
                 font=FONT_SMALL, anchor="w", width=34).pack(side="left")
        var = tk.StringVar(value=cfg.get(key, "en"))
        entries[key] = var
        for code, lbl in [("en", "English"), ("de", "Deutsch"), ("fr", "Français"),
                          ("pl", "Polski"), ("ru", "Русский")]:
            tk.Radiobutton(row, text=lbl, variable=var, value=code,
                           command=lambda c=code: _on_lang_change(c),
                           bg=BG, fg=FG_VALUE, selectcolor="#1a1a1a",
                           activebackground=BG, activeforeground=FG_VALUE,
                           font=FONT).pack(side="left", padx=(0, 10))

    _TARGET_LANG_OPTIONS = [
        "English", "German", "French", "Spanish", "Portuguese",
        "Russian", "Chinese", "Turkish", "Polish", "Italian",
    ]

    _SKIP_LANG_OPTIONS = [
        ("de", "Deutsch"), ("en", "English"), ("fr", "Français"),
        ("es", "Español"), ("pt", "Português"), ("ru", "Русский"),
        ("zh", "中文"), ("tr", "Türkçe"), ("pl", "Polski"),
        ("it", "Italiano"), ("cs", "Čeština"), ("nl", "Nederlands"),
        ("uk", "Українська"), ("ko", "한국어"), ("ja", "日本語"),
    ]

    def _setup_combobox_style():
        style = ttk.Style(win)
        style.theme_use("clam")
        style.configure("Dark.TCombobox",
                        fieldbackground=ENTRY_BG, background=ENTRY_BG,
                        foreground=FG_VALUE, selectbackground=ENTRY_BG,
                        selectforeground=FG_VALUE, bordercolor="#2a2a2a",
                        arrowcolor=FG_ACCENT, padding=3)
        style.map("Dark.TCombobox",
                  fieldbackground=[("readonly", ENTRY_BG)],
                  foreground=[("readonly", FG_VALUE)],
                  background=[("active", "#2a2a2a")])
        win.option_add("*TCombobox*Listbox.background", ENTRY_BG)
        win.option_add("*TCombobox*Listbox.foreground", FG_VALUE)
        win.option_add("*TCombobox*Listbox.selectBackground", "#2a2a2a")
        win.option_add("*TCombobox*Listbox.selectForeground", FG_ACCENT)
        win.option_add("*TCombobox*Listbox.font", FONT)

    def field_target_lang(key, label):
        row = tk.Frame(body, bg=BG)
        row.pack(fill="x", pady=(4, 0))
        tk.Label(row, text=label, fg=FG_LABEL, bg=BG,
                 font=FONT_SMALL, anchor="w", width=34).pack(side="left")
        _setup_combobox_style()
        current = cfg.get(key, _TARGET_LANG_OPTIONS[0])
        values = list(_TARGET_LANG_OPTIONS)
        if current not in values:
            values.insert(0, current)
        var = tk.StringVar(value=current)
        ttk.Combobox(row, textvariable=var, values=values,
                     style="Dark.TCombobox", font=FONT, width=28).pack(side="left", fill="x", expand=True)
        entries[key] = var

    def field_key(key, label):
        row = tk.Frame(body, bg=BG)
        row.pack(fill="x", pady=(4, 0))
        tk.Label(row, text=label, fg=FG_LABEL, bg=BG,
                 font=FONT_SMALL, anchor="w", width=34).pack(side="left")
        e = tk.Entry(row, bg=ENTRY_BG, fg=FG_VALUE, insertbackground=FG_VALUE,
                     relief="flat", bd=3, highlightthickness=1,
                     highlightcolor=FG_ACCENT, highlightbackground="#2a2a2a",
                     font=FONT, show="•", width=44)
        val = cfg.get(key, "")
        e.insert(0, val if val else "")
        e.pack(side="left", fill="x", expand=True)
        entries[key] = e
        _visible = [False]
        eye = tk.Label(row, text="👁", fg="#444444", bg=BG,
                       font=("Consolas", 13), cursor="hand2", padx=4)
        eye.pack(side="left")
        def _toggle(ev=None, _e=e, _eye=eye, _vis=_visible):
            _vis[0] = not _vis[0]
            _e.config(show="" if _vis[0] else "•")
            _eye.config(fg=FG_ACCENT if _vis[0] else "#444444")
        eye.bind("<Button-1>", _toggle)

    def field_check(key, label):
        row = tk.Frame(body, bg=BG)
        row.pack(fill="x", pady=(4, 0))
        tk.Label(row, text=label, fg=FG_LABEL, bg=BG,
                 font=FONT_SMALL, anchor="w", width=34).pack(side="left")
        var = tk.BooleanVar(value=bool(cfg.get(key, False)))
        entries[key] = var
        tk.Checkbutton(
            row, variable=var,
            bg=BG, fg=FG_VALUE, selectcolor="#1a1a1a",
            activebackground=BG, activeforeground=FG_VALUE,
            font=FONT,
        ).pack(side="left")

    def field_multicheck(key, label):
        current = cfg.get(key, [])
        if isinstance(current, str):
            current = [x.strip() for x in current.split(",") if x.strip()]
        selected = set(current)
        var = tk.StringVar(value=", ".join(sorted(selected)))
        entries[key] = var

        row = tk.Frame(body, bg=BG)
        row.pack(fill="x", pady=(4, 0))
        tk.Label(row, text=label, fg=FG_LABEL, bg=BG,
                 font=FONT_SMALL, anchor="w", width=34).pack(side="left")
        display = tk.Label(row, textvariable=var, fg=FG_VALUE, bg=ENTRY_BG,
                           font=FONT, anchor="w", padx=6, width=22)
        display.pack(side="left", fill="x", expand=True)
        arrow = tk.Label(row, text="▾", fg=FG_ACCENT, bg=ENTRY_BG,
                         font=FONT_BOLD, cursor="hand2", padx=6)
        arrow.pack(side="left")

        def _open_popup(event=None):
            popup = tk.Toplevel(win)
            popup.overrideredirect(True)
            popup.configure(bg="#1a1a1a")
            popup.attributes("-topmost", True)
            popup.grab_set()
            x = row.winfo_rootx() + 34 * 7  # align with entry area
            y = row.winfo_rooty() + row.winfo_height()
            popup.geometry(f"+{x}+{y}")

            check_vars = {}
            for code, name in _SKIP_LANG_OPTIONS:
                cv = tk.BooleanVar(value=code in selected)
                check_vars[code] = cv
                tk.Checkbutton(popup, text=f"{name}  [{code}]", variable=cv,
                               bg="#1a1a1a", fg=FG_VALUE, selectcolor="#2a2a2a",
                               activebackground="#2a2a2a", activeforeground=FG_VALUE,
                               font=FONT, anchor="w").pack(fill="x", padx=10, pady=1)

            def _apply():
                new_sel = sorted(c for c, cv in check_vars.items() if cv.get())
                selected.clear()
                selected.update(new_sel)
                var.set(", ".join(new_sel))
                popup.grab_release()
                popup.destroy()

            tk.Frame(popup, bg="#2a2a2a", height=1).pack(fill="x", pady=(4, 0))
            ok = tk.Label(popup, text="OK", fg=FG_VALUE, bg="#1e1e1e",
                          font=FONT_BOLD, cursor="hand2", padx=16, pady=4)
            ok.pack(pady=4)
            ok.bind("<Button-1>", lambda e: _apply())
            ok.bind("<Enter>", lambda e: ok.config(bg="#2a2a2a"))
            ok.bind("<Leave>", lambda e: ok.config(bg="#1e1e1e"))
            popup.bind("<Escape>", lambda e: _apply())

        display.bind("<Button-1>", _open_popup)
        arrow.bind("<Button-1>", _open_popup)

    # ── sections & fields ─────────────────────────────────────────────────────

    section(t("settings.section.interface"))
    field_lang("lang",            t("settings.field.ui_lang"))
    field_target_lang("target_lang", t("settings.field.target_lang"))
    field_multicheck("no_translate_langs", t("settings.field.skip_langs"))
    field("ignore_names",         t("settings.field.ignore_players"),   width=40)
    field_check("compact_mode",   t("settings.field.compact_mode"))
    field("ticker_speed",         t("settings.field.ticker_speed"),      width=6)

    section(t("settings.section.llm"))

    # API URL — empty = use DEFAULT_API_URL (no placeholder text shown)
    _api_url_row = tk.Frame(body, bg=BG)
    _api_url_row.pack(fill="x", pady=(4, 0))
    tk.Label(_api_url_row, text=t("settings.field.api_url"), fg=FG_LABEL, bg=BG,
             font=FONT_SMALL, anchor="w", width=34).pack(side="left")
    _stored_url = (cfg.get("gpt_api") or "").strip()
    _api_url_var = tk.StringVar(value=_stored_url)
    tk.Entry(_api_url_row, bg=ENTRY_BG, fg=FG_VALUE, insertbackground=FG_VALUE,
             relief="flat", bd=3, highlightthickness=1,
             highlightcolor=FG_ACCENT, highlightbackground="#2a2a2a",
             font=FONT, textvariable=_api_url_var, width=44).pack(side="left", fill="x", expand=True)

    def _get_api_url() -> str:
        return _api_url_var.get().strip()

    # Model — only shown when a custom URL is entered
    _model_row = tk.Frame(body, bg=BG)
    tk.Label(_model_row, text=t("settings.field.model"), fg=FG_LABEL, bg=BG,
             font=FONT_SMALL, anchor="w", width=34).pack(side="left")
    _model_var = tk.StringVar(value=cfg.get("gpt_model", "gpt-4.1-nano"))
    tk.Entry(_model_row, bg=ENTRY_BG, fg=FG_VALUE, insertbackground=FG_VALUE,
             relief="flat", bd=3, highlightthickness=1,
             highlightcolor=FG_ACCENT, highlightbackground="#2a2a2a",
             font=FONT, textvariable=_model_var, width=30).pack(side="left", fill="x", expand=True)
    entries["gpt_model"] = _model_var

    def _update_model_visibility(*_):
        if _api_url_var.get().strip():
            _model_row.pack(fill="x", pady=(4, 0), after=_api_url_row)
        else:
            _model_row.pack_forget()

    _api_url_var.trace_add("write", _update_model_visibility)
    _update_model_visibility()

    field("temperature",         t("settings.field.temperature"),   width=10)
    field_key("open_ai_api_key", t("settings.field.api_key"))

    section(t("settings.section.log"))
    field("log_path",         t("settings.field.log_path"),
          width=36, browse_file=True,
          browse_title=t("settings.field.log_path"),
          browse_types=[("Log files", "*.log"), ("All files", "*.*")])
    field("poll_interval_ms", t("settings.field.poll_interval"), width=10)

    # ── bottom bar ────────────────────────────────────────────────────────────
    tk.Frame(win, bg="#2a2a2a", height=1).pack(fill="x")
    btn_bar = tk.Frame(win, bg=BG)
    btn_bar.pack(fill="x", padx=14, pady=8)

    def _make_btn(parent, text, cmd):
        b = tk.Label(parent, text=text, fg=FG_VALUE, bg="#1e1e1e",
                     font=FONT_BOLD, cursor="hand2", padx=16, pady=5, relief="flat")
        b.bind("<Button-1>", lambda e: cmd())
        b.bind("<Enter>", lambda e: b.config(bg="#2a2a2a"))
        b.bind("<Leave>", lambda e: b.config(bg="#1e1e1e"))
        return b

    def _save():
        new_cfg = dict(cfg)
        new_cfg["gpt_api"] = _get_api_url()
        if not new_cfg["gpt_api"]:
            new_cfg["gpt_model"] = "gpt-4.1-nano"
        for key, widget in entries.items():
            if isinstance(widget, tk.BooleanVar):
                new_cfg[key] = widget.get()
                continue
            if isinstance(widget, tk.StringVar):
                val = widget.get()
                if key in ("no_translate_langs", "ignore_names"):
                    new_cfg[key] = [x.strip() for x in val.split(",") if x.strip()]
                else:
                    new_cfg[key] = val
            else:
                raw = widget.get().strip()
                if key in ("no_translate_langs", "ignore_names"):
                    new_cfg[key] = [x.strip() for x in raw.split(",") if x.strip()]
                elif key == "temperature":
                    try: new_cfg[key] = float(raw)
                    except ValueError: pass
                elif key in ("poll_interval_ms", "ticker_speed"):
                    try: new_cfg[key] = int(raw)
                    except ValueError: pass
                elif key == "open_ai_api_key":
                    if raw:
                        new_cfg[key] = raw
                else:
                    new_cfg[key] = raw
        if on_save:
            on_save(new_cfg)
        win.destroy()

    try:
        from app._build_version import CURRENT_VERSION
    except ImportError:
        CURRENT_VERSION = "dev"
    tk.Label(btn_bar, text=f"v{CURRENT_VERSION}", fg="#444444", bg=BG,
             font=FONT_SMALL).pack(side="left")

    _make_btn(btn_bar, t("settings.btn.cancel"), win.destroy).pack(side="right", padx=(6, 0))
    _make_btn(btn_bar, t("settings.btn.save"), _save).pack(side="right")

    win.bind("<Escape>", lambda e: win.destroy())
    win.after(100, lambda: _apply_round_region(win))
