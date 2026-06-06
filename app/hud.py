
import os
import re
import time
import tkinter as tk
from queue import Empty

class TkHud:
    COLORS = {
        "dt": "#a0a0a0",
        "scope": "#7adfff",
        "name": "#ffb86c",
        "msg": "#ffffff",
        "meta": "#8f8f8f",
        "err": "#ff6b6b",
        "lang": "#7adfff",
    }

    _TICKER_MS = 16
    _TICKER_GAP = 60
    _COMPACT_H = 26

    def __init__(self, queue, alpha: float = 0.75, font="Consolas 11",
                 geometry: str = None, on_geometry_change=None, on_settings=None,
                 on_font_change=None, on_alpha_change=None,
                 compact_mode: bool = False, ticker_speed: int = 2,
                 show_status_dot: bool = True, always_on_top: bool = True):
        self.queue = queue
        self.on_geometry_change = on_geometry_change
        self.on_settings = on_settings
        self.on_font_change = on_font_change
        self.on_alpha_change = on_alpha_change
        self._line_count = 0
        self._stream_marks: dict = {}
        self._resize = {"x": 0, "y": 0, "w": 0, "h": 0}
        self._font = font
        self._compact = False
        self._ticker_active = False
        self._ticker_px = max(1, ticker_speed)
        self._ticker_last_t = 0.0
        self._ticker_accum = 0.0
        self._normal_geometry: str | None = None
        self._status_color: str = ""
        self._status_setting_enabled: bool = show_status_dot

        self.root = tk.Tk()
        self.root.title("CS2 Chat HUD")
        self.root.attributes("-topmost", always_on_top)
        self.root.overrideredirect(True)
        self.root.configure(bg="black")
        self.root.wm_attributes("-alpha", alpha)
        self.visible = True

        _icon_dir = os.path.dirname(os.path.abspath(__file__))
        _ico = os.path.join(_icon_dir, "icon.ico")
        _png = os.path.join(_icon_dir, "icon.png")
        self._ico_path = None
        try:
            if os.path.isfile(_ico):
                self._ico_path = _ico
                self.root.iconbitmap(_ico)
            elif os.path.isfile(_png):
                from PIL import Image, ImageTk
                _img = Image.open(_png)
                self._icon_ref = ImageTk.PhotoImage(_img)
                self.root.iconphoto(True, self._icon_ref)
        except Exception:
            pass

        if os.name == "nt":
            try:
                import ctypes
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except Exception:
                pass

        w, h = 800, 320
        self.root.geometry(geometry if geometry else f"{w}x{h}+40+720")

        self._drag = {"x": 0, "y": 0}
        self.root.bind("<Button-1>", self._start_move)
        self.root.bind("<B1-Motion>", self._on_move)
        self.root.bind("<ButtonRelease-1>", self._on_release)
        self.root.bind("<Escape>", lambda e: self.root.destroy())
        self.root.bind("<F1>", self._toggle_visible)
        self.root.bind("<F2>", lambda e: self._cycle_alpha())

        frame = tk.Frame(self.root, bg="black")
        frame.pack(fill="both", expand=True)

        # ── Normal mode layout ────────────────────────────────────────────────
        self._normal_frame = tk.Frame(frame, bg="black")
        self._normal_frame.pack(fill="both", expand=True)

        topbar = tk.Frame(self._normal_frame, bg="black")
        topbar.pack(fill="x", side="top")

        self._tooltip_win = None
        self._tooltip_text = ""

        self._status_canvas_n = tk.Canvas(
            topbar, width=14, height=14, bg="black", bd=0, highlightthickness=0,
        )
        self._status_canvas_n.pack(side="left", padx=(6, 0), pady=2)
        self._status_dot_n = self._status_canvas_n.create_oval(
            2, 2, 12, 12, fill="#555555", outline="",
        )
        self._status_canvas_n.bind("<Enter>", self._tooltip_show)
        self._status_canvas_n.bind("<Leave>", self._tooltip_hide)

        close_btn = tk.Label(topbar, text="✕", fg="#ff6666", bg="black",
                             font=("Consolas", 12, "bold"), cursor="hand2")
        close_btn.pack(side="right", padx=4, pady=2)
        close_btn.bind("<Enter>", lambda e: close_btn.config(fg="#ffaaaa"))
        close_btn.bind("<Leave>", lambda e: close_btn.config(fg="#ff6666"))
        close_btn.bind("<Button-1>", lambda e: self.root.destroy())

        settings_btn = tk.Label(topbar, text="⛭", fg="#7adfff", bg="black",
                                font=("Consolas", 12, "bold"), cursor="hand2")
        settings_btn.pack(side="right", padx=4, pady=2)
        settings_btn.bind("<Enter>", lambda e: settings_btn.config(fg="#ffffff"))
        settings_btn.bind("<Leave>", lambda e: settings_btn.config(fg="#7adfff"))
        settings_btn.bind("<Button-1>", lambda e: self.on_settings() if self.on_settings else None)

        compact_btn = tk.Label(topbar, text="⊟", fg="#aaaaaa", bg="black",
                               font=("Consolas", 12, "bold"), cursor="hand2")
        compact_btn.pack(side="right", padx=4, pady=2)
        compact_btn.bind("<Enter>", lambda e: compact_btn.config(fg="#ffffff"))
        compact_btn.bind("<Leave>", lambda e: compact_btn.config(fg="#aaaaaa"))
        compact_btn.bind("<Button-1>", lambda e: self.set_compact(True))

        self._resize_handle = tk.Frame(self._normal_frame, bg="#1a1a1a", cursor="size_nw_se", width=16, height=16)
        self._resize_handle.pack(side="bottom", anchor="se")
        self._resize_handle.pack_propagate(False)

        self.text = tk.Text(
            self._normal_frame,
            bg="black", fg=self.COLORS["meta"],
            insertbackground="white",
            relief="flat", bd=0, highlightthickness=0,
            wrap="word"
        )
        self.text.pack(fill="both", expand=True, padx=8, pady=4)
        self.text.configure(font=font, state="disabled")

        for tag, color in self.COLORS.items():
            self.text.tag_configure(tag, foreground=color)

        self.text.bind("<MouseWheel>", self._on_mousewheel)
        self.text.bind("<Control-MouseWheel>", self._on_ctrl_mousewheel)
        self.text.bind("<Button-4>", lambda e: self.text.yview_scroll(-1, "units"))
        self.text.bind("<Button-5>", lambda e: self.text.yview_scroll(1, "units"))
        self._resize_handle.bind("<Button-1>", self._resize_start)
        self._resize_handle.bind("<B1-Motion>", self._resize_move)
        self._resize_handle.bind("<ButtonRelease-1>", self._resize_end)

        # ── Compact mode layout (single row: ticker | ⛭ ✕) ──────────────────
        self._compact_frame = tk.Frame(frame, bg="black")
        # Not packed initially; set_compact() controls visibility

        self._status_canvas_c = tk.Canvas(
            self._compact_frame, width=14, height=14, bg="black", bd=0, highlightthickness=0,
        )
        self._status_canvas_c.pack(side="left", padx=(6, 2), pady=3)
        self._status_dot_c = self._status_canvas_c.create_oval(
            2, 2, 12, 12, fill="#555555", outline="",
        )
        self._status_canvas_c.bind("<Enter>", self._tooltip_show)
        self._status_canvas_c.bind("<Leave>", self._tooltip_hide)

        self._ticker_canvas = tk.Canvas(
            self._compact_frame, bg="black", bd=0, highlightthickness=0,
        )
        self._ticker_canvas.pack(side="left", fill="both", expand=True, padx=(0, 0), pady=3)

        _cc = tk.Label(self._compact_frame, text="✕", fg="#ff6666", bg="black",
                       font=("Consolas", 12, "bold"), cursor="hand2")
        _cc.pack(side="right", padx=4)
        _cc.bind("<Enter>", lambda e: _cc.config(fg="#ffaaaa"))
        _cc.bind("<Leave>", lambda e: _cc.config(fg="#ff6666"))
        _cc.bind("<Button-1>", lambda e: self.root.destroy())

        _cs = tk.Label(self._compact_frame, text="⛭", fg="#7adfff", bg="black",
                       font=("Consolas", 12, "bold"), cursor="hand2")
        _cs.pack(side="right", padx=4)
        _cs.bind("<Enter>", lambda e: _cs.config(fg="#ffffff"))
        _cs.bind("<Leave>", lambda e: _cs.config(fg="#7adfff"))
        _cs.bind("<Button-1>", lambda e: self.on_settings() if self.on_settings else None)

        _ce = tk.Label(self._compact_frame, text="⊞", fg="#aaaaaa", bg="black",
                       font=("Consolas", 12, "bold"), cursor="hand2")
        _ce.pack(side="right", padx=4)
        _ce.bind("<Enter>", lambda e: _ce.config(fg="#ffffff"))
        _ce.bind("<Leave>", lambda e: _ce.config(fg="#aaaaaa"))
        _ce.bind("<Button-1>", lambda e: self.set_compact(False))

        self._poll()
        if os.name == "nt":
            self.root.after(100, self._round_corners)
            self.root.after(200, self._show_in_taskbar)
        if compact_mode:
            self.root.after(50, lambda: self.set_compact(True))

    # ── resize handle ────────────────────────────────────────────────────────

    def _resize_start(self, event):
        self._resize["x"] = event.x_root
        self._resize["y"] = event.y_root
        self._resize["w"] = self.root.winfo_width()
        self._resize["h"] = self.root.winfo_height()
        return "break"  # prevent window drag from firing

    def _resize_move(self, event):
        dw = event.x_root - self._resize["x"]
        dh = event.y_root - self._resize["y"]
        nw = max(300, self._resize["w"] + dw)
        nh = max(120, self._resize["h"] + dh)
        self.root.geometry(f"{nw}x{nh}")
        self._round_corners()
        return "break"

    def _resize_end(self, event):
        if self.on_geometry_change:
            self.on_geometry_change(self.root.geometry())
        self._round_corners()
        return "break"

    # ── rounded corners ──────────────────────────────────────────────────────

    def _round_corners(self, radius: int = 20):
        if os.name != "nt":
            return
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            if not hwnd:
                hwnd = self.root.winfo_id()
            w, h = self.root.winfo_width(), self.root.winfo_height()
            if w > 1 and h > 1:
                r = min(radius, h // 2, w // 2)
                hrgn = ctypes.windll.gdi32.CreateRoundRectRgn(0, 0, w + 1, h + 1, r * 2, r * 2)
                ctypes.windll.user32.SetWindowRgn(hwnd, hrgn, True)
        except Exception:
            pass

    def _show_in_taskbar(self):
        if os.name != "nt":
            return
        try:
            import ctypes
            GWL_EXSTYLE = -20
            WS_EX_APPWINDOW = 0x00040000
            WS_EX_TOOLWINDOW = 0x00000080
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            if not hwnd:
                hwnd = self.root.winfo_id()
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style = (style | WS_EX_APPWINDOW) & ~WS_EX_TOOLWINDOW
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
            # Hide/show cycle forces the taskbar to register the new style.
            # Icon must be re-applied after deiconify — the cycle resets it.
            def _reshow():
                self.root.deiconify()
                try:
                    if self._ico_path:
                        self.root.iconbitmap(self._ico_path)
                    elif hasattr(self, "_icon_ref"):
                        self.root.iconphoto(True, self._icon_ref)
                except Exception:
                    pass
            self.root.withdraw()
            self.root.after(50, _reshow)
        except Exception:
            pass

    # ── compact / ticker mode ─────────────────────────────────────────────────

    def set_compact(self, enabled: bool):
        if self._compact == enabled:
            return
        self._compact = enabled
        if enabled:
            self._normal_geometry = self.root.geometry()
            self._normal_frame.pack_forget()
            self._compact_frame.pack(fill="both", expand=True)
            self._ticker_active = True
            self._ticker_last_t = time.monotonic()
            self._ticker_accum = 0.0
            m = re.match(r'\d+x\d+([+-]\d+[+-]\d+)', self.root.geometry())
            pos = m.group(1) if m else "+40+720"
            w = self.root.winfo_width() or 800
            self.root.geometry(f"{w}x{self._COMPACT_H}{pos}")
            self.root.update_idletasks()
            self._round_corners()
            self.root.after(self._TICKER_MS, self._ticker_tick)
        else:
            self._ticker_active = False
            self._compact_frame.pack_forget()
            self._ticker_canvas.delete("all")
            self._normal_frame.pack(fill="both", expand=True)
            if self._normal_geometry:
                self.root.geometry(self._normal_geometry)
            self.root.update_idletasks()
            self._round_corners()
            self.text.see("end")

    def set_ticker_speed(self, px: int):
        self._ticker_px = max(1, px)

    _STATUS_FILLS = {"green": "#44dd44", "yellow": "#ffcc00", "red": "#ff4444", "blue": "#4488ff"}

    def set_status_color(self, color: str, tooltip: str = ""):
        fill = self._STATUS_FILLS.get(color, "#555555")
        def _apply():
            self._status_color = color
            self._status_canvas_n.itemconfig(self._status_dot_n, fill=fill)
            self._status_canvas_c.itemconfig(self._status_dot_c, fill=fill)
            self._tooltip_text = tooltip
            self._update_dot_visibility()
        try:
            self.root.after(0, _apply)
        except Exception:
            pass

    def set_status_visible(self, enabled: bool):
        self._status_setting_enabled = enabled
        try:
            self.root.after(0, self._update_dot_visibility)
        except Exception:
            pass

    def set_topmost(self, enabled: bool):
        try:
            self.root.attributes("-topmost", enabled)
        except Exception:
            pass

    def set_font(self, font_str: str):
        self._font = font_str
        try:
            self.text.configure(font=font_str)
        except Exception:
            pass

    def _update_dot_visibility(self):
        force_show = self._status_color in ("yellow", "red")
        show = force_show or self._status_setting_enabled
        state = "normal" if show else "hidden"
        self._status_canvas_n.itemconfig(self._status_dot_n, state=state)
        self._status_canvas_c.itemconfig(self._status_dot_c, state=state)

    def _tooltip_show(self, event):
        if not self._tooltip_text or self._tooltip_win:
            return
        x = self.root.winfo_pointerx() + 14
        y = self.root.winfo_pointery() + 14
        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.wm_attributes("-topmost", True)
        win.configure(bg="#1e1e1e")
        tk.Label(
            win, text=self._tooltip_text,
            bg="#1e1e1e", fg="#e0e0e0",
            font=("Consolas", 9), justify="left",
            padx=10, pady=7,
        ).pack()
        win.geometry(f"+{x}+{y}")
        self._tooltip_win = win

    def _tooltip_hide(self, event):
        if self._tooltip_win:
            self._tooltip_win.destroy()
            self._tooltip_win = None

    def _ticker_tick(self):
        if not self._ticker_active:
            return
        now = time.monotonic()
        elapsed = now - self._ticker_last_t
        self._ticker_last_t = now
        # _ticker_px is "pixels per frame at 60 fps" → convert to px/s
        self._ticker_accum += self._ticker_px * 60.0 * elapsed
        dx = int(self._ticker_accum)
        self._ticker_accum -= dx
        if dx:
            self._ticker_canvas.move("ticker", -dx, 0)
            for item in self._ticker_canvas.find_withtag("ticker"):
                try:
                    bbox = self._ticker_canvas.bbox(item)
                    if bbox and bbox[2] < 0:
                        self._ticker_canvas.delete(item)
                except Exception:
                    pass
        self.root.after(self._TICKER_MS, self._ticker_tick)

    def _ticker_add(self, dt: str, scope: str, name: str, msg: str,
                    orig: str = "", lang: str = ""):
        canvas = self._ticker_canvas
        cw = canvas.winfo_width()
        if cw <= 1:
            cw = 800
        rightmost = cw
        for item in canvas.find_withtag("ticker"):
            bbox = canvas.bbox(item)
            if bbox:
                rightmost = max(rightmost, bbox[2])
        x = max(cw, rightmost + self._TICKER_GAP)
        ch = canvas.winfo_height()
        y = (ch // 2) if ch > 1 else 13

        def put(text: str, color: str):
            nonlocal x
            item = canvas.create_text(
                x, y, text=text, fill=color, font=self._font,
                anchor="w", tags=("ticker",),
            )
            bb = canvas.bbox(item)
            if bb:
                x = bb[2]

        put(dt + "  ", self.COLORS["dt"])
        put(f"[{scope}] ", self.COLORS["scope"])
        put(name + ": ", self.COLORS["name"])
        if orig and lang:
            put(f"[{lang}] ", self.COLORS["lang"])
            put(orig + "  →  ", self.COLORS["meta"])
        elif orig:
            put(orig + "  →  ", self.COLORS["meta"])
        put(msg, self.COLORS["msg"])

    # ── window drag ──────────────────────────────────────────────────────────

    _ALPHA_STEPS = (1.0, 0.8, 0.6, 0.4, 0.2)

    def _cycle_alpha(self):
        cur = float(self.root.attributes("-alpha"))
        idx = min(range(len(self._ALPHA_STEPS)), key=lambda i: abs(self._ALPHA_STEPS[i] - cur))
        new_alpha = self._ALPHA_STEPS[(idx + 1) % len(self._ALPHA_STEPS)]
        self.root.attributes("-alpha", new_alpha)
        if self.on_alpha_change:
            self.on_alpha_change(new_alpha)

    def _toggle_visible(self, *_):
        self.visible = not self.visible
        self.root.withdraw() if not self.visible else self.root.deiconify()

    def _start_move(self, event):
        self._drag["x"] = event.x_root - self.root.winfo_x()
        self._drag["y"] = event.y_root - self.root.winfo_y()

    def _on_move(self, event):
        x, y = event.x_root - self._drag["x"], event.y_root - self._drag["y"]
        self.root.geometry(f"+{x}+{y}")

    def _on_release(self, event):
        if not self._compact and self.on_geometry_change:
            self.on_geometry_change(self.root.geometry())

    def _on_mousewheel(self, event):
        delta = -1 if event.delta > 0 else 1
        self.text.yview_scroll(delta, "units")

    def _on_ctrl_mousewheel(self, event):
        parts = self._font.rsplit(" ", 1)
        family = parts[0] if len(parts) == 2 else "Consolas"
        try:
            size = int(parts[-1])
        except ValueError:
            size = 11
        size += 1 if event.delta > 0 else -1
        size = max(7, min(size, 28))
        self._font = f"{family} {size}"
        self.text.configure(font=self._font)
        if self.on_font_change:
            self.on_font_change(self._font)
        return "break"

    # ── text management ──────────────────────────────────────────────────────

    def _trim_if_needed(self):
        if self._line_count > 2000:
            self.text.delete('1.0', '201.0')
            self._line_count -= 200

    def _poll(self):
        try:
            while True:
                typ, payload = self.queue.get_nowait()
                if typ == "structured":
                    self._append_struct(**payload)
                elif typ == "line":
                    self._append_line(payload)
                elif typ == "error":
                    self._append_line(payload, tag="err")
                elif typ == "stream_init":
                    self._stream_init(**payload)
                elif typ == "stream_update":
                    self._stream_update(**payload)
                elif typ == "stream_done":
                    self._stream_done(**payload)
                elif typ == "stream_remove":
                    self._stream_remove(**payload)
                self.queue.task_done()
        except Empty:
            pass
        self.root.after(33, self._poll)

    def _append_line(self, line: str, tag="meta"):
        self.text.configure(state="normal")
        self.text.insert("end", line.rstrip() + "\n", (tag,))
        self._line_count += 1
        self._trim_if_needed()
        if not self._compact:
            self.text.see("end")
        self.text.configure(state="disabled")

    def _append_struct(self, dt: str, scope: str, name: str, msg: str,
                       orig: str = "", lang: str = ""):
        if self._compact:
            self._ticker_add(dt, scope, name, msg, orig, lang)
        # Always write to text widget too — it's just hidden in compact mode,
        # so content is fully preserved when switching back to normal mode.
        self.text.configure(state="normal")
        self.text.insert("end", dt + "  ", ("dt",))
        self.text.insert("end", f"[{scope}] ", ("scope",))
        self.text.insert("end", name + ": ", ("name",))
        self.text.insert("end", msg + "\n", ("msg",))
        self._line_count += 1
        self._trim_if_needed()
        if orig:
            self.text.insert("end", "  ↳ ", ("meta",))
            if lang:
                self.text.insert("end", f"[{lang}] ", ("lang",))
            self.text.insert("end", orig + "\n", ("meta",))
            self._line_count += 1
            self._trim_if_needed()
        if not self._compact:
            self.text.see("end")
        self.text.configure(state="disabled")

    # ── streaming ────────────────────────────────────────────────────────────

    def _stream_init(self, id: str, dt: str, scope: str, name: str, orig: str = ""):
        pass  # no placeholder shown; result appears on stream_done

    def _stream_update(self, id: str, delta: str):
        pass

    def _stream_done(self, id: str, dt: str, scope: str, name: str,
                     orig: str, lang: str, msg: str):
        self._append_struct(dt=dt, scope=scope, name=name, msg=msg, orig=orig, lang=lang)

    def _stream_remove(self, id: str):
        pass  # nothing was inserted, nothing to remove

    def run(self):
        self.root.mainloop()
