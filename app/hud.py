
import os
import re
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

    _TICKER_MS = 30
    _TICKER_PX = 2
    _TICKER_GAP = 60

    def __init__(self, queue, alpha: float = 0.75, font="Consolas 11",
                 geometry: str = None, on_geometry_change=None, on_settings=None,
                 compact_mode: bool = False):
        self.queue = queue
        self.on_geometry_change = on_geometry_change
        self.on_settings = on_settings
        self._line_count = 0
        self._stream_marks: dict = {}
        self._resize = {"x": 0, "y": 0, "w": 0, "h": 0}
        self._font = font
        self._compact = False
        self._ticker_active = False
        self._normal_geometry: str | None = None

        self.root = tk.Tk()
        self.root.title("CS2 Chat HUD")
        self.root.attributes("-topmost", True)
        self.root.overrideredirect(True)
        self.root.configure(bg="black")
        self.root.wm_attributes("-alpha", alpha)
        self.visible = True

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

        # Topbar with Close / Settings buttons
        topbar = tk.Frame(frame, bg="black")
        topbar.pack(fill="x", side="top")

        close_btn = tk.Label(topbar, text="✕", fg="#ff6666", bg="black",
                             font=("Consolas", 14, "bold"), cursor="hand2")
        close_btn.pack(side="right", padx=6, pady=2)
        close_btn.bind("<Enter>", lambda e: close_btn.config(fg="#ffaaaa"))
        close_btn.bind("<Leave>", lambda e: close_btn.config(fg="#ff6666"))
        close_btn.bind("<Button-1>", lambda e: self.root.destroy())

        settings_btn = tk.Label(topbar, text="⛭", fg="#7adfff", bg="black",
                                font=("Consolas", 13, "bold"), cursor="hand2")
        settings_btn.pack(side="right", padx=2, pady=2)
        settings_btn.bind("<Enter>", lambda e: settings_btn.config(fg="#ffffff"))
        settings_btn.bind("<Leave>", lambda e: settings_btn.config(fg="#7adfff"))
        settings_btn.bind("<Button-1>", lambda e: self.on_settings() if self.on_settings else None)

        # Resize handle must be packed before the expanding text widget so it
        # actually gets allocated space at the bottom-right corner.
        self._resize_handle = tk.Frame(frame, bg="#1a1a1a", cursor="size_nw_se", width=16, height=16)
        self._resize_handle.pack(side="bottom", anchor="se")
        self._resize_handle.pack_propagate(False)

        self.text = tk.Text(
            frame,
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
        self.text.bind("<Button-4>", lambda e: self.text.yview_scroll(-1, "units"))
        self.text.bind("<Button-5>", lambda e: self.text.yview_scroll(1, "units"))
        self._resize_handle.bind("<Button-1>", self._resize_start)
        self._resize_handle.bind("<B1-Motion>", self._resize_move)
        self._resize_handle.bind("<ButtonRelease-1>", self._resize_end)

        self._ticker_canvas = tk.Canvas(
            frame, bg="black", height=26, bd=0, highlightthickness=0,
        )
        # Not packed here — set_compact() controls visibility

        self._poll()
        if os.name == "nt":
            self.root.after(100, self._round_corners)
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
                hrgn = ctypes.windll.gdi32.CreateRoundRectRgn(0, 0, w + 1, h + 1, radius * 2, radius * 2)
                ctypes.windll.user32.SetWindowRgn(hwnd, hrgn, True)
        except Exception:
            pass

    # ── compact / ticker mode ─────────────────────────────────────────────────

    def set_compact(self, enabled: bool):
        if self._compact == enabled:
            return
        self._compact = enabled
        if enabled:
            self._normal_geometry = self.root.geometry()
            self.text.pack_forget()
            self._resize_handle.pack_forget()
            self._ticker_canvas.pack(fill="x", padx=8, pady=6)
            self._ticker_active = True
            self.root.update_idletasks()
            compact_h = self.root.winfo_reqheight()
            m = re.match(r'\d+x\d+([+-]\d+[+-]\d+)', self.root.geometry())
            pos = m.group(1) if m else "+40+720"
            w = self.root.winfo_width() or 800
            self.root.geometry(f"{w}x{compact_h}{pos}")
            self.root.after(self._TICKER_MS, self._ticker_tick)
        else:
            self._ticker_active = False
            self._ticker_canvas.pack_forget()
            self._ticker_canvas.delete("all")
            self._resize_handle.pack(side="bottom", anchor="se")
            self.text.pack(fill="both", expand=True, padx=8, pady=4)
            if self._normal_geometry:
                self.root.geometry(self._normal_geometry)
        self.root.after(30, self._round_corners)

    def _ticker_tick(self):
        if not self._ticker_active:
            return
        self._ticker_canvas.move("ticker", -self._TICKER_PX, 0)
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

    def _cycle_alpha(self):
        cur = float(self.root.attributes("-alpha"))
        next_alpha = 0.9 if cur < 0.8 else 0.6 if cur < 0.9 else 0.75
        self.root.attributes("-alpha", next_alpha)

    def _toggle_visible(self, *_):
        self.visible = not self.visible
        self.root.withdraw() if not self.visible else self.root.deiconify()

    def _start_move(self, event):
        self._drag["x"], self._drag["y"] = event.x, event.y

    def _on_move(self, event):
        x, y = event.x_root - self._drag["x"], event.y_root - self._drag["y"]
        self.root.geometry(f"+{x}+{y}")

    def _on_release(self, event):
        if not self._compact and self.on_geometry_change:
            self.on_geometry_change(self.root.geometry())

    def _on_mousewheel(self, event):
        delta = -1 if event.delta > 0 else 1
        self.text.yview_scroll(delta, "units")

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
        if self._compact:
            return
        self.text.configure(state="normal")
        self.text.insert("end", line.rstrip() + "\n", (tag,))
        self._line_count += 1
        self._trim_if_needed()
        self.text.see("end")
        self.text.configure(state="disabled")

    def _append_struct(self, dt: str, scope: str, name: str, msg: str,
                       orig: str = "", lang: str = ""):
        if self._compact:
            self._ticker_add(dt, scope, name, msg, orig, lang)
            return
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
