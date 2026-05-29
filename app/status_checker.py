import threading
import time
import requests

_STATUS_URL = "https://crimson-dog-44043.zap.cloud/status"
_TIMEOUT = 8
_INTERVAL = 60


def _check() -> str:
    try:
        r = requests.get(_STATUS_URL, timeout=_TIMEOUT)
        if r.status_code != 200:
            return "red"
        d = r.json()
        if not d.get("custom_key", {}).get("valid", False):
            return "yellow"
        oa = d.get("openai", {})
        if not oa.get("key_set", False) or not oa.get("reachable", False):
            return "yellow"
        if d.get("status") != "ok":
            return "yellow"
        return "green"
    except Exception:
        return "red"


def start(on_status_change, initial_delay: float = 3.0):
    """Start a daemon thread that polls proxy /status every 60 s."""
    def _worker():
        time.sleep(initial_delay)
        while True:
            color = _check()
            try:
                on_status_change(color)
            except Exception:
                pass
            time.sleep(_INTERVAL)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return t
