import tkinter as tk
from tkinter import filedialog, ttk

BG = "black"
FG_ACCENT = "#7adfff"
FG_LABEL = "#a0a0a0"
FG_VALUE = "#ffffff"
FG_SECTION = "#ffb86c"
ENTRY_BG = "#1a1a1a"
FONT = ("Consolas", 10)
FONT_BOLD = ("Consolas", 10, "bold")
FONT_SMALL = ("Consolas", 9)


def open_settings(parent_root, cfg: dict, config_path: str, on_save=None):
    win = tk.Toplevel(parent_root)
    win.overrideredirect(True)
    win.configure(bg=BG)
    win.attributes("-topmost", True)
    win.wm_attributes("-alpha", 0.97)

    WIN_W, WIN_H = 620, 680

    # Center on screen, clamped so it never goes off-screen
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    x = max(0, min((sw - WIN_W) // 2, sw - WIN_W))
    y = max(0, min((sh - WIN_H) // 2, sh - WIN_H))
    win.geometry(f"{WIN_W}x{WIN_H}+{x}+{y}")

    win.grab_set()

    # ── drag support ────────────────────────────────────────────────────────
    _drag = {"x": 0, "y": 0}

    def _start(e): _drag["x"], _drag["y"] = e.x, e.y
    def _move(e):
        nx = max(0, min(e.x_root - _drag["x"], sw - WIN_W))
        ny = max(0, min(e.y_root - _drag["y"], sh - WIN_H))
        win.geometry(f"+{nx}+{ny}")

    # ── title bar ────────────────────────────────────────────────────────────
    topbar = tk.Frame(win, bg=BG)
    topbar.pack(fill="x")

    title = tk.Label(topbar, text="⛭  Settings", fg=FG_ACCENT, bg=BG,
                     font=FONT_BOLD, anchor="w")
    title.pack(side="left", padx=10, pady=6)

    close_btn = tk.Label(topbar, text="✕", fg="#ff6666", bg=BG,
                         font=("Consolas", 13, "bold"), cursor="hand2")
    close_btn.pack(side="right", padx=8, pady=4)
    close_btn.bind("<Enter>", lambda e: close_btn.config(fg="#ffaaaa"))
    close_btn.bind("<Leave>", lambda e: close_btn.config(fg="#ff6666"))
    close_btn.bind("<Button-1>", lambda e: win.destroy())

    # drag via topbar / title
    for w in (topbar, title):
        w.bind("<Button-1>", _start)
        w.bind("<B1-Motion>", _move)

    tk.Frame(win, bg="#2a2a2a", height=1).pack(fill="x")

    # ── content area ─────────────────────────────────────────────────────────
    body = tk.Frame(win, bg=BG)
    body.pack(fill="both", expand=True, padx=14, pady=6)

    entries = {}  # key → Entry widget

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
            def _browse(e=e, t=browse_title, ft=browse_types):
                p = filedialog.askopenfilename(parent=win, title=t, filetypes=ft or [("All files", "*.*")])
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
        for code, lbl in [("en", "English"), ("de", "Deutsch"), ("fr", "Français"), ("pl", "Polski"), ("ru", "Русский")]:
            tk.Radiobutton(row, text=lbl, variable=var, value=code,
                           bg=BG, fg=FG_VALUE, selectcolor="#1a1a1a",
                           activebackground=BG, activeforeground=FG_VALUE,
                           font=FONT).pack(side="left", padx=(0, 10))

    _TARGET_LANG_OPTIONS = [
        "English", "German", "French", "Spanish", "Portuguese",
        "Russian", "Chinese", "Turkish", "Polish", "Italian",
    ]

    _MODEL_OPTIONS = [
        # sorted by cost (cheapest first)
        "gpt-4.1-nano",
        "gpt-4o-mini",
        "gpt-4.1-mini",
        "gpt-4.1",
        "gpt-4o",
        # reasoning models (no temperature)
        "o4-mini",
        "o3-mini",
        "o3",
        "o1-mini",
        "o1",
    ]

    def _setup_combobox_style():
        style = ttk.Style(win)
        style.theme_use("clam")
        style.configure("Dark.TCombobox",
                        fieldbackground=ENTRY_BG,
                        background=ENTRY_BG,
                        foreground=FG_VALUE,
                        selectbackground=ENTRY_BG,
                        selectforeground=FG_VALUE,
                        bordercolor="#2a2a2a",
                        arrowcolor=FG_ACCENT,
                        padding=3)
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
        cb = ttk.Combobox(row, textvariable=var, values=values,
                          style="Dark.TCombobox", font=FONT, width=28)
        cb.pack(side="left", fill="x", expand=True)
        entries[key] = var

    def field_model(key, label):
        row = tk.Frame(body, bg=BG)
        row.pack(fill="x", pady=(4, 0))
        tk.Label(row, text=label, fg=FG_LABEL, bg=BG,
                 font=FONT_SMALL, anchor="w", width=34).pack(side="left")
        _setup_combobox_style()
        current = cfg.get(key, _MODEL_OPTIONS[0])
        values = list(_MODEL_OPTIONS)
        if current not in values:
            values.insert(0, current)

        var = tk.StringVar(value=current)
        cb = ttk.Combobox(row, textvariable=var, values=values,
                          style="Dark.TCombobox", font=FONT, width=28)
        cb.pack(side="left", fill="x", expand=True)
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
        show_var = tk.BooleanVar(value=False)
        def _toggle():
            e.config(show="" if show_var.get() else "•")
        chk = tk.Checkbutton(row, text="show", variable=show_var, command=_toggle,
                             bg=BG, fg=FG_LABEL, selectcolor="#1a1a1a",
                             activebackground=BG, font=FONT_SMALL)
        chk.pack(side="left", padx=(6, 0))

    # ── sections & fields ─────────────────────────────────────────────────────

    section("Interface")
    field_lang("lang", "UI language")
    field_target_lang("target_lang", "Translate into")
    field("no_translate_langs", "Skip langs (comma-sep.)", width=30)
    field("ignore_names",       "Ignore players (comma-sep.)", width=40)

    section("LLM / API")
    field("gpt_api",   "API URL", width=44)
    field_model("gpt_model", "Model")
    field("temperature", "Temperature  (0.0 – 2.0)", width=10)
    field_key("open_ai_api_key", "API key")
    field("open_ai_api_key_file", "API key file",
          width=36, browse_file=True, browse_title="Select API key file",
          browse_types=[("Text files", "*.txt"), ("All files", "*.*")])

    section("Log & Performance")
    field("log_path", "console.log path",
          width=36, browse_file=True, browse_title="Select CS2 console.log",
          browse_types=[("Log files", "*.log"), ("All files", "*.*")])
    field("poll_interval_ms", "Poll interval (ms)", width=10)

    # ── bottom bar ────────────────────────────────────────────────────────────
    tk.Frame(win, bg="#2a2a2a", height=1).pack(fill="x")
    btn_bar = tk.Frame(win, bg=BG)
    btn_bar.pack(fill="x", padx=14, pady=8)

    def _make_btn(parent, text, cmd):
        b = tk.Label(parent, text=text, fg=FG_VALUE, bg="#1e1e1e",
                     font=FONT_BOLD, cursor="hand2", padx=16, pady=5,
                     relief="flat")
        b.bind("<Button-1>", lambda e: cmd())
        b.bind("<Enter>", lambda e: b.config(bg="#2a2a2a"))
        b.bind("<Leave>", lambda e: b.config(bg="#1e1e1e"))
        return b

    def _save():
        new_cfg = dict(cfg)

        for key, widget in entries.items():
            if isinstance(widget, tk.StringVar):
                new_cfg[key] = widget.get()
            else:
                raw = widget.get().strip()
                if key in ("no_translate_langs", "ignore_names"):
                    new_cfg[key] = [x.strip() for x in raw.split(",") if x.strip()]
                elif key == "temperature":
                    try:
                        new_cfg[key] = float(raw)
                    except ValueError:
                        pass
                elif key == "poll_interval_ms":
                    try:
                        new_cfg[key] = int(raw)
                    except ValueError:
                        pass
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

    _make_btn(btn_bar, "Cancel", win.destroy).pack(side="right", padx=(6, 0))
    _make_btn(btn_bar, "Save", _save).pack(side="right")

    win.bind("<Escape>", lambda e: win.destroy())
