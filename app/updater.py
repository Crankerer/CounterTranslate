import json, os, re, sys, tempfile, subprocess, time, zipfile
from urllib.request import Request, urlopen

from app._build_version import CURRENT_VERSION
from app import log_setup as _log_setup

OWNER = "Crankerer"
REPO = "CounterTranslate"
APP_EXE_NAME = "CounterTranslate_app.exe"
LAUNCHER_EXE_NAME = "CounterTranslate.exe"
UA = f"{REPO}-updater/1.0"


class _UpdateUI:
    """Small centered status window shown only when an update is being applied."""

    BG = "#111111"

    def __init__(self, current: str, latest: str):
        import tkinter as tk
        self._tk = tk
        self.root = tk.Tk()
        self.root.title("CounterTranslate – Updater")
        self.root.overrideredirect(True)
        self.root.configure(bg=self.BG)
        self.root.wm_attributes("-alpha", 0.95)
        self.root.attributes("-topmost", True)

        w, h = 440, 110
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

        tk.Label(
            self.root, text="CounterTranslate  –  Update",
            fg="#7adfff", bg=self.BG, font=("Consolas", 10, "bold"),
        ).pack(pady=(12, 4))

        tk.Label(
            self.root, text=f"v{current}  →  {latest}",
            fg="#a0a0a0", bg=self.BG, font=("Consolas", 9),
        ).pack()

        self._status_var = tk.StringVar(value="")
        tk.Label(
            self.root, textvariable=self._status_var,
            fg="#ffffff", bg=self.BG, font=("Consolas", 10),
        ).pack(pady=(6, 0))

        self.root.update()

    def set(self, text: str):
        self._status_var.set(text)
        self.root.update()

    def close(self):
        try:
            self.root.destroy()
        except Exception:
            pass


def _gh_headers(accept_json=False):
    hdr = {"User-Agent": UA}
    if accept_json:
        hdr["Accept"] = "application/vnd.github+json"
    token = os.getenv("GITHUB_TOKEN")
    if token:
        hdr["Authorization"] = f"Bearer {token}"
        hdr["X-GitHub-Api-Version"] = "2022-11-28"
    return hdr

def _http_json(url):
    headers = _gh_headers(accept_json=True)
    req = Request(url, headers=headers)
    with urlopen(req, timeout=15) as r:
        return json.load(r)

def _download(url, dest, on_progress=None):
    req = Request(url, headers={**_gh_headers(), "Accept": "application/octet-stream"})
    with urlopen(req, timeout=120) as r, open(dest, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        received = 0
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            received += len(chunk)
            if on_progress:
                on_progress(received, total)

def _parse_version(s):
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", s or "")
    return tuple(map(int, m.groups())) if m else (0, 0, 0)

def _app_path():
    try:
        _compiled = bool(__compiled__)
    except NameError:
        _compiled = False
    if getattr(sys, "frozen", False) or _compiled:
        return sys.executable
    return os.path.abspath(sys.argv[0])

def _pick_asset(release):
    assets = release.get("assets", [])
    exe_pref = [a for a in assets
                if a["name"].lower().endswith(".exe")
                and any(x in a["name"].lower() for x in ("win", "windows", "x64", "amd64"))]
    if exe_pref:
        return exe_pref[0], "exe"
    exe_any = [a for a in assets if a["name"].lower().endswith(".exe")]
    if exe_any:
        return exe_any[0], "exe"
    zip_pref = [a for a in assets
                if a["name"].lower().endswith(".zip")
                and any(x in a["name"].lower() for x in ("win", "windows", "x64", "amd64"))]
    if zip_pref:
        return zip_pref[0], "zip"
    zip_any = [a for a in assets if a["name"].lower().endswith(".zip")]
    if zip_any:
        return zip_any[0], "zip"
    return None, None

def _extract_update_from_zip(zip_path):
    with zipfile.ZipFile(zip_path) as z:
        members = z.namelist()
        exes = [m for m in members if m.lower().endswith(".exe")]
        if not exes:
            return None, None, None

        app_name_lower = APP_EXE_NAME.lower()
        named = [m for m in exes if os.path.basename(m).lower() == app_name_lower]
        if not named:
            _log_setup.get().warning("[Updater] %s not found in ZIP. Found: %s", APP_EXE_NAME, [os.path.basename(m) for m in exes])
            return None, None, None
        pick = named[0]

        launcher_name_lower = LAUNCHER_EXE_NAME.lower()
        launcher_members = [m for m in exes if os.path.basename(m).lower() == launcher_name_lower]

        out_dir = tempfile.mkdtemp()
        z.extractall(out_dir)

        _log_setup.get().debug("[Updater] %s found in ZIP", pick)

        new_exe = os.path.normpath(os.path.join(out_dir, pick))

        _log_setup.get().debug("[Updater] full path %s", new_exe)

        update_root = os.path.dirname(new_exe)

        new_launcher = (
            os.path.normpath(os.path.join(out_dir, launcher_members[0]))
            if launcher_members else None
        )
        if new_launcher:
            _log_setup.get().debug("[Updater] Launcher found in ZIP: %s", launcher_members[0])
        else:
            _log_setup.get().debug("[Updater] Launcher not found in ZIP")

        return update_root, new_exe, new_launcher

def maybe_update(prereleases=False):
    ui = None
    try:
        # --- silent check, no UI yet ---
        url = f"https://api.github.com/repos/{OWNER}/{REPO}/releases"
        rel_data = _http_json(url)

        if isinstance(rel_data, list):
            if not rel_data:
                _log_setup.get().info("[Updater] No releases found.")
                return False
            if prereleases:
                rel = rel_data[0]
            else:
                rel = next(
                    (r for r in rel_data
                     if not r.get("draft") and not r.get("prerelease")),
                    rel_data[0]
                )
        elif isinstance(rel_data, dict):
            rel = rel_data
        else:
            _log_setup.get().warning("[Updater] Unexpected release type: %s", type(rel_data))
            return False

        if not rel or rel.get("draft"):
            _log_setup.get().info("[Updater] No valid release found.")
            return False

        latest_version_str = rel.get("tag_name") or rel.get("name")
        latest_v = _parse_version(latest_version_str)
        current_v = _parse_version(CURRENT_VERSION)

        _log_setup.get().info("[Updater] Local: %s | Remote: %s", CURRENT_VERSION, latest_version_str)

        if latest_v <= current_v:
            _log_setup.get().info("[Updater] Already up to date.")
            return False

        # --- ask user ---
        import tkinter as tk
        from tkinter import messagebox
        _root = tk.Tk()
        _root.withdraw()
        _root.attributes("-topmost", True)
        want = messagebox.askyesno(
            "CounterTranslate – Update",
            f"A new version is available:\n\n  {latest_version_str}\n\nDo you want to update now?",
            parent=_root,
        )
        _root.destroy()
        if not want:
            _log_setup.get().info("[Updater] User declined update.")
            return False

        # --- update found: show UI from here on ---
        ui = _UpdateUI(CURRENT_VERSION, latest_version_str)

        asset, kind = _pick_asset(rel)
        if not asset:
            ui.set("No suitable Windows asset found.")
            time.sleep(2)
            ui.close()
            return False

        total_bytes = asset.get("size") or 0
        total_mb = f"{total_bytes / (1 << 20):.1f} MB" if total_bytes else ""

        def on_progress(received, total):
            if total:
                pct = int(received / total * 100)
                ui.set(f"Downloading...  {pct}%  ({received / (1 << 20):.1f} / {total / (1 << 20):.1f} MB)")
            else:
                ui.set(f"Downloading...  {received / (1 << 20):.1f} MB")

        ui.set(f"Downloading...  0%  (0.0 / {total_mb})" if total_mb else "Downloading...")

        fd, tmp_file = tempfile.mkstemp()
        os.close(fd)
        _download(asset["browser_download_url"], tmp_file, on_progress=on_progress)

        ui.set("Extracting..." if kind == "zip" else "Preparing...")

        if kind == "zip":
            update_root, new_exe, new_launcher = _extract_update_from_zip(tmp_file)
            if not new_exe:
                ui.set("Error: main EXE not found in ZIP.")
                time.sleep(3)
                ui.close()
                return False
        else:
            new_exe = tmp_file
            update_root = os.path.dirname(new_exe)
            new_launcher = None

        target = _app_path()
        # current\ subfolder → one level up is the install root
        install_dir = os.path.dirname(target)
        root_dir = os.path.dirname(install_dir)
        launcher_exe = os.path.join(root_dir, LAUNCHER_EXE_NAME)
        update_pending = os.path.join(root_dir, "update_pending")

        # If the ZIP contained a new launcher, copy it into root_dir first so
        # the restart always uses the current name — this handles installs where
        # the launcher still carries the old project name (CS2ChatTranslationBot.exe).
        if new_launcher and os.path.isfile(new_launcher):
            import shutil as _shutil2
            _shutil2.copy2(new_launcher, launcher_exe)
            _log_setup.get().info("[Updater] Launcher updated: %s", launcher_exe)

        if not os.path.isfile(launcher_exe):
            ui.set("Error: launcher not found.")
            time.sleep(3)
            ui.close()
            _log_setup.get().warning("[Updater] Launcher not found: %s", launcher_exe)
            return False

        ui.set("Installing...  Restarting shortly.")
        time.sleep(1.5)
        ui.close()

        # Move extracted update into update_pending\ — the launcher applies it on next start
        import shutil as _shutil
        if os.path.isdir(update_pending):
            _shutil.rmtree(update_pending)
        _shutil.move(update_root, update_pending)

        _log_setup.get().info("[Updater] Pending update staged at: %s", update_pending)
        _log_setup.get().info("[Updater] Relaunching via launcher: %s", launcher_exe)
        subprocess.Popen(
            [launcher_exe] + sys.argv[1:],
            cwd=root_dir,
            close_fds=True,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        sys.exit(0)

    except Exception as e:
        _log_setup.get().error("[Updater] Update failed: %s", e)
        if ui:
            ui.set(f"Update failed: {e}")
            time.sleep(3)
            ui.close()
        return False
