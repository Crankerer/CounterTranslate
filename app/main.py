import os, sys
from pathlib import Path
from queue import Queue
from concurrent.futures import ThreadPoolExecutor

from app.config import load_config, save_config, DEFAULTS
from app.hud import TkHud
from app.tailer import start_tail_thread
from app.util import ts
import app.i18n as _i18n_mod
from app.updater import maybe_update
import app.log_setup as _log_setup

# --- Laufzeitpfade: EXE vs. Script ---
# sys.frozen = PyInstaller; __compiled__ = Nuitka
try:
    _is_compiled = bool(__compiled__)
except NameError:
    _is_compiled = False

if getattr(sys, 'frozen', False) or _is_compiled:
    # BASE_DIR = current\ subfolder (where the app EXE and lang\ live)
    BASE_DIR = os.path.dirname(sys.executable)
    # config.json lives one level up in the install root (survives updates)
    CONFIG_DIR = os.path.dirname(BASE_DIR)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    CONFIG_DIR = BASE_DIR

if getattr(sys, 'frozen', False) or _is_compiled:
    sys.path.insert(0, BASE_DIR)

CONFIG_FILENAME = os.path.join(CONFIG_DIR, "config.json")

def pick_base_folder(t, initial_dir: str | None = None) -> str:
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    try:
        folder = filedialog.askdirectory(
            title=t("dialog.pick_base_folder"),
            initialdir=initial_dir or os.getcwd(),
        )
        return folder or ""
    finally:
        root.destroy()

def ensure_config_exists(path: str, t) -> None:
    if not os.path.isfile(path):
        cfg = {"log_path": "", **DEFAULTS}
        try:
            save_config(path, cfg)
            print(t("cfg.first_time", path=path))
        except Exception as e:
            print(t("cfg.create_fail", err=e))

def request_api_key(t) -> str:
    import tkinter as tk
    from tkinter import simpledialog, messagebox
    root = tk.Tk()
    root.withdraw()
    try:
        key = simpledialog.askstring(
            t("api.dialog.title"),
            t("api.dialog.prompt"),
            show="*"
        )
        if not key:
            messagebox.showwarning(
                t("api.dialog.warning.empty_title"),
                t("api.dialog.warning.empty_msg")
            )
            return ""
        key = key.strip()
        if not key.startswith("sk-"):
            messagebox.showwarning(
                t("api.dialog.warning.invalid_title"),
                t("api.dialog.warning.invalid_msg")
            )
            return ""
        return key
    finally:
        root.destroy()

def main():
    _log = _log_setup.setup(CONFIG_DIR)
    _log.info("=== CounterTranslate startup ===")

    # 1) Konfiguration laden (load_config handles missing file gracefully)
    cfg = load_config(CONFIG_FILENAME)

    # 2) i18n Singleton konfigurieren — ab hier ist t() überall verfügbar
    lang_code = (cfg.get("lang") or "en").strip().lower()
    _i18n_mod.configure(BASE_DIR, lang_code)
    from app.i18n import t

    # 3) config.json erstmalig anlegen (jetzt mit echten i18n-Strings)
    ensure_config_exists(CONFIG_FILENAME, t)

    # 4) API-Key ggf. erfragen & speichern
    api_key = (cfg.get("open_ai_api_key") or "").strip()
    if not api_key:
        print(t("api.missing"))
        key = request_api_key(t)
        if not key:
            print(t("abort.no_api"))
            return
        cfg["open_ai_api_key"] = key
        try:
            save_config(CONFIG_FILENAME, cfg)
            print(t("api.saved", path=CONFIG_FILENAME))
        except Exception as e:
            print(t("api.save_fail", err=e))

    # 4) log_path prüfen (leer/ungültig → Steam-Basisordner wählen & Pfad bauen)
    raw_log_path = (cfg.get("log_path") or "").strip()
    if not raw_log_path or not os.path.isfile(raw_log_path):
        hint = "leer" if not raw_log_path else f"nicht gefunden: {raw_log_path}"
        print(t("log.hint_choose", hint=hint))

        _cs2_default = r"C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive"
        if raw_log_path:
            _init = os.path.dirname(raw_log_path)
        elif os.path.isdir(_cs2_default):
            _init = _cs2_default
        else:
            _init = r"C:\Program Files (x86)\Steam\steamapps\common"

        base = pick_base_folder(t, _init)
        if not base:
            print(t("abort.no_folder"))
            return

        log_path = Path(base) / "game" / "csgo" / "console.log"
        log_path_str = os.path.normpath(str(log_path))

        cfg["log_path"] = log_path_str
        try:
            save_config(CONFIG_FILENAME, cfg)
            print(t("cfg.log_saved", path=CONFIG_FILENAME, log=log_path_str))
        except Exception as e:
            print(t("cfg.save_fail", err=e))
    else:
        log_path = raw_log_path

    ignore_names = cfg.get("ignore_names", [])
    poll_ms = int(cfg.get("poll_interval_ms", 100))

    print(t("hud.title"))
    print(t("app.header"))
    print(t("hud.logfile", log=log_path))
    print(t("hud.ignore", names=', '.join(ignore_names) or '(keine)'))
    print(t("hud.gpt_api", api=cfg.get("gpt_api")))
    print(t("hud.gpt_model", model=cfg.get("gpt_model")))
    print(t("hud.api_key", state='(gesetzt)' if cfg.get("open_ai_api_key") else '(leer)'))
    print(t("hud.temp", temp=cfg.get("temperature")))
    print(t("hud.target_lang", lang=cfg.get("target_lang", "German")))
    print(t("hud.no_translate", langs=', '.join(cfg.get('no_translate_langs', [])) or '(leer)'))
    print(t("hud.poll", ms=poll_ms))
    key_file = (cfg.get("open_ai_api_key_file") or "").strip()
    if key_file:
        print(t("hud.key_file", path=key_file))
    print()
    _log.info(
        f"config: log={log_path} | model={cfg.get('gpt_model')} "
        f"| api={cfg.get('gpt_api')} | target_lang={cfg.get('target_lang')} "
        f"| no_translate={cfg.get('no_translate_langs')} | temp={cfg.get('temperature')}"
    )

    # HUD + Tail starten
    from app.hud import TkHud
    from app.tailer import start_tail_thread
    from app.settings_ui import open_settings

    q = Queue()

    def save_geometry(geo: str):
        cfg["hud_geometry"] = geo
        try:
            save_config(CONFIG_FILENAME, cfg)
        except Exception:
            pass

    def open_settings_dialog():
        nonlocal cfg
        def on_save(new_cfg):
            nonlocal cfg
            cfg = new_cfg
            try:
                save_config(CONFIG_FILENAME, cfg)
                print(t("cfg.log_saved", path=CONFIG_FILENAME, log=cfg.get("log_path", "")))
            except Exception as e:
                print(t("cfg.save_fail", err=e))
        open_settings(hud.root, cfg, CONFIG_FILENAME, on_save=on_save)

    hud = TkHud(
        q, alpha=0.72, font="Consolas 11",
        geometry=cfg.get("hud_geometry"),
        on_geometry_change=save_geometry,
        on_settings=open_settings_dialog,
    )

    class _HudStream:
        """Tee: writes to original stdout (if available) and feeds lines to the HUD queue."""
        def __init__(self, original, queue):
            self._orig = original  # None in --noconsole builds
            self._q = queue
            self._buf = ""

        def write(self, text):
            if self._orig is not None:
                try:
                    self._orig.write(text)
                except Exception:
                    pass
            self._buf += text
            while "\n" in self._buf:
                line, self._buf = self._buf.split("\n", 1)
                if line:
                    try:
                        is_err = line.startswith(("[LLM-Error]", "[Error]"))
                        log = _log_setup.get()
                        if is_err:
                            log.error(line)
                        else:
                            log.info(line)
                    except Exception:
                        pass
                    try:
                        is_err = line.startswith(("[LLM-Error]", "[Error]"))
                        self._q.put(("error" if is_err else "line", line))
                    except Exception:
                        pass

        def flush(self):
            if self._orig is not None:
                try:
                    self._orig.flush()
                except Exception:
                    pass

        def fileno(self):
            if self._orig is not None:
                try:
                    return self._orig.fileno()
                except Exception:
                    pass
            return -1

    original_stdout = sys.stdout
    sys.stdout = _HudStream(original_stdout, q)

    pool = ThreadPoolExecutor(max_workers=3)
    tail_thread = start_tail_thread(log_path, CONFIG_FILENAME, ignore_names, poll_ms, cfg, q, pool)

    try:
        hud.run()
    finally:
        sys.stdout = original_stdout
        try:
            pool.shutdown(wait=False)
        except Exception:
            pass

if __name__ == "__main__":
    # Only run the self-updater if this is a frozen/packaged build
    if getattr(sys, "frozen", False) or _is_compiled:
        maybe_update(prereleases=False)

    # then start your actual app
    main()