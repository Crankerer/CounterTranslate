
import os
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

    def __init__(self, queue, alpha: float = 0.75, font="Consolas 11",
                 geometry: str = None, on_geometry_change=None, on_settings=None):
        self.queue = queue
        self.on_geometry_change = on_geometry_change
        self.on_settings = on_settings
        self._line_count = 0
        self._stream_marks: dict = {}   # id → mark name (placed at LINE START)
        self._resize = {"x": 0, "y": 0, "w": 0, "h": 0}

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

        # Resize handle — bottom-right corner
        resize_handle = tk.Frame(frame, bg="#1a1a1a", cursor="size_nw_se", width=16, height=16)
        resize_handle.pack(side="bottom", anchor="se")
        resize_handle.pack_propagate(False)
        resize_handle.bind("<Button-1>", self._resize_start)
        resize_handle.bind("<B1-Motion>", self._resize_move)
        resize_handle.bind("<ButtonRelease-1>", self._resize_end)

        self._poll()

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
        return "break"

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
        if self.on_geometry_change:
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
        self.text.configure(state="normal")
        self.text.insert("end", line.rstrip() + "\n", (tag,))
        self._line_count += 1
        self._trim_if_needed()
        self.text.see("end")
        self.text.configure(state="disabled")

    def _append_struct(self, dt: str, scope: str, name: str, msg: str,
                       orig: str = "", lang: str = ""):
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
        self.text.configure(state="normal")
        mark = f"stream_{id}"
        # Place mark at the very start of the new line — before the header.
        # LEFT gravity: mark never moves regardless of subsequent inserts on this line.
        self.text.mark_set(mark, "end")
        self.text.mark_gravity(mark, "left")
        self.text.insert("end", dt + "  ", ("dt",))
        self.text.insert("end", f"[{scope}] ", ("scope",))
        self.text.insert("end", name + ": ⟳\n", ("meta",))
        self._stream_marks[id] = mark
        self._line_count += 1
        self._trim_if_needed()
        self.text.see("end")
        self.text.configure(state="disabled")

    def _stream_update(self, id: str, delta: str):
        pass  # no live chunk display; _stream_done replaces ⟳ on completion

    def _stream_done(self, id: str, dt: str, scope: str, name: str,
                     orig: str, lang: str, msg: str):
        mark = self._stream_marks.get(id)
        if not mark:
            return
        self.text.configure(state="normal")
        # mark is guaranteed to be at the LINE START (set before the header insert).
        # Use it directly — no linestart modifier needed.
        line_start = self.text.index(mark)
        line_end   = self.text.index(f"{mark} lineend +1c")
        self.text.delete(line_start, line_end)
        self._line_count -= 1
        self.text.mark_unset(mark)
        del self._stream_marks[id]
        # Re-insert using a right-gravity temp mark so sequential inserts advance.
        tmp = f"_ins_{id}"
        self.text.mark_set(tmp, line_start)
        self.text.mark_gravity(tmp, "right")
        self.text.insert(tmp, dt + "  ", ("dt",))
        self.text.insert(tmp, f"[{scope}] ", ("scope",))
        self.text.insert(tmp, name + ": ", ("name",))
        self.text.insert(tmp, msg + "\n", ("msg",))
        self._line_count += 1
        self._trim_if_needed()
        if orig:
            self.text.insert(tmp, "  ↳ ", ("meta",))
            if lang:
                self.text.insert(tmp, f"[{lang}] ", ("lang",))
            self.text.insert(tmp, orig + "\n", ("meta",))
            self._line_count += 1
            self._trim_if_needed()
        self.text.mark_unset(tmp)
        self.text.see("end")
        self.text.configure(state="disabled")

    def _stream_remove(self, id: str):
        mark = self._stream_marks.get(id)
        if not mark:
            return
        self.text.configure(state="normal")
        line_start = self.text.index(mark)
        line_end   = self.text.index(f"{mark} lineend +1c")
        self.text.delete(line_start, line_end)
        self._line_count = max(0, self._line_count - 1)
        self.text.mark_unset(mark)
        del self._stream_marks[id]
        self.text.configure(state="disabled")

    def run(self):
        self.root.mainloop()
