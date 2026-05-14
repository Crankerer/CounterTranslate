import os, time
from .util import ts
from .i18n import t


def open_follow(path: str):
    """
    Continuously attempts to open the given file until it exists.
    Once found, returns the file handle (opened for reading) and its stat info.
    """
    printed_waiting = False
    while True:
        try:
            f = open(path, "r", encoding="utf-8", errors="ignore")
            st = os.stat(path)
            f.seek(0, os.SEEK_END)
            return f, st
        except FileNotFoundError:
            if not printed_waiting:
                print(ts(), t("file.wait_not_found", path=path))
                printed_waiting = True
            time.sleep(2.0)
