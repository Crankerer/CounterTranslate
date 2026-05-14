import os
import sys
import shutil
import subprocess


def main():
    base = os.path.dirname(os.path.abspath(sys.executable))
    pending = os.path.join(base, "update_pending")
    current = os.path.join(base, "current")

    if os.path.isdir(pending):
        if os.path.isdir(current):
            shutil.rmtree(current)
        os.rename(pending, current)

    app_exe = os.path.join(current, "CounterTranslate_app.exe")
    if not os.path.isfile(app_exe):
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            0,
            f"App not found:\n{app_exe}\n\nPlease reinstall.",
            "CounterTranslate",
            0x10,
        )
        sys.exit(1)

    subprocess.Popen([app_exe] + sys.argv[1:])
    sys.exit(0)


if __name__ == "__main__":
    main()
