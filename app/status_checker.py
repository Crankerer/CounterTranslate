import threading
import time
import requests

_STATUS_URL = "https://crimson-dog-44043.zap.cloud/status"
_TIMEOUT = 8
_INTERVAL = 300


def _fmt_uptime(seconds: int) -> str:
    h, rem = divmod(seconds, 3600)
    m = rem // 60
    return f"{h}h {m:02d}m" if h else f"{m}m"


def _format_tooltip(d: dict) -> str:
    lines = [f"Status:  {d.get('status', '?')}"]
    ck = d.get("ct_key")
    if ck is None:
        lines.append("Key:     not configured")
    elif ck.get("valid"):
        days = ck.get("days_until_expiry")
        days_str = f"{days} days left" if days is not None else "no expiry"
        lines.append(f"Key:     valid ({days_str})")
    else:
        err = ck.get("error", "invalid / expired")
        lines.append(f"Key:     {err}")
    oa = d.get("openai", {})
    lines.append(f"OpenAI:  {'reachable' if oa.get('reachable') else 'NOT reachable'}")
    if oa.get("error"):
        lines.append(f"         {oa['error']}")
    uptime = d.get("uptime_seconds")
    if uptime is not None:
        lines.append(f"Uptime:  {_fmt_uptime(int(uptime))}")
    return "\n".join(lines)


def _check(key: str = "") -> tuple[str, str]:
    try:
        headers = {}
        if key.startswith("ct-"):
            headers["Authorization"] = f"Bearer {key}"
        r = requests.get(_STATUS_URL, timeout=_TIMEOUT, headers=headers)
        if r.status_code != 200:
            return "red", "Proxy not reachable"
        d = r.json()
        tooltip = _format_tooltip(d)
        ck = d.get("ct_key")
        if ck is None or not ck.get("valid", False):
            return "red", tooltip
        oa = d.get("openai", {})
        if not oa.get("key_set", False) or not oa.get("reachable", False):
            return "yellow", tooltip
        if d.get("status") != "ok":
            return "yellow", tooltip
        return "green", tooltip
    except Exception:
        return "red", "Proxy not reachable"


def start(on_status_change, get_key=None, initial_delay: float = 3.0):
    """Start a daemon thread that polls proxy /status every 5 min.

    get_key: optional callable returning the current API key string.
             If the key starts with 'ct-' it is sent as a Bearer token so
             the server validates it and includes a ct_key block in the response.
    """
    def _worker():
        time.sleep(initial_delay)
        while True:
            key = get_key() if callable(get_key) else ""
            color, tooltip = _check(key)
            try:
                on_status_change(color, tooltip)
            except Exception:
                pass
            time.sleep(_INTERVAL)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return t
