import os, json, tempfile, threading, time

from . import log_setup as _log_setup

DEFAULT_API_URL = "https://crimson-dog-44043.zap.cloud/v1/chat/completions"

# Guards save_config so two writers can never interleave.
_SAVE_LOCK = threading.Lock()

# A parse failure is almost always a torn read (the file was being replaced
# while we read it), which resolves within milliseconds — retry before
# declaring the file corrupt.
_READ_RETRIES = 3
_READ_RETRY_DELAY = 0.05

# On Windows os.replace fails with PermissionError while any reader still has
# the destination file open. Readers hold it for a moment only, so retry rather
# than let the save fail (callers deliberately swallow save errors).
_REPLACE_RETRIES = 6
_REPLACE_RETRY_DELAY = 0.05

DEFAULTS = {
    "log_path": "",
    "ignore_names": [],
    "poll_interval_ms": 100,
    "llm_api": "http://localhost:1234/v1/chat/completions",
    "llm_model": "local-model",
    "gpt_api": "",
    "gpt_model": "gpt-4.1-nano",
    "temperature": 0.2,
    "no_translate_langs": ["de"],
    "target_lang": "German",
    "open_ai_api_key": os.environ.get("OPENAI_API_KEY", ""),
    "lang": "en",
    "compact_mode": False,
    "ticker_speed": 2,
    "hud_alpha": 0.72,
    "show_status_dot": True,
    "always_on_top": True,
    "hud_font": "Consolas 11",
}


def _merge_defaults(cfg: dict) -> tuple[dict, bool]:
    """Merge DEFAULTS into the existing config (used for backward compatibility)."""
    changed = False
    for k, v in DEFAULTS.items():
        if k not in cfg:
            cfg[k] = v
            changed = True
    return cfg, changed


def _read_config_file(path: str) -> dict:
    """Read and parse the config file. Raises if it exists but is unusable."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("config root is not a JSON object")
    return data


def _backup_unreadable(path: str, err: Exception | None) -> None:
    """Move an unparseable config aside so it is never silently overwritten."""
    bak = path + ".bak"
    try:
        os.replace(path, bak)
        _log_setup.get().error(
            "[config] %s is unreadable (%s) — moved to %s, continuing with defaults",
            path, err, bak,
        )
    except Exception as e:
        _log_setup.get().error(
            "[config] %s is unreadable (%s) and could not be preserved (%s) — "
            "continuing with defaults", path, err, e,
        )


def load_config(path: str) -> dict:
    # 1) Read the file. Retry a parse failure briefly: a truncated read means
    #    another thread was mid-save, not that the config is broken. Only a
    #    file that stays unreadable is treated as corrupt — and then it is
    #    moved aside rather than overwritten by the defaults below.
    cfg = None
    last_err: Exception | None = None
    for attempt in range(_READ_RETRIES):
        try:
            cfg = _read_config_file(path)
            break
        except FileNotFoundError:
            cfg = {}
            break
        except Exception as e:
            last_err = e
            if attempt + 1 < _READ_RETRIES:
                time.sleep(_READ_RETRY_DELAY)

    if cfg is None:
        _backup_unreadable(path, last_err)
        cfg = {}

    # 2) Merge in defaults (for migrating older files)
    cfg, changed = _merge_defaults(cfg)

    # 3) Load API key from an external file if defined
    key_file = (cfg.get("open_ai_api_key_file") or "").strip()
    if not (cfg.get("open_ai_api_key") or "").strip() and key_file:
        try:
            with open(key_file, "r", encoding="utf-8") as fh:
                cfg["open_ai_api_key"] = fh.read().strip()
                changed = True
        except Exception:
            pass

    # 4) Normalize the log_path (prevents mixed slash formats)
    lp = cfg.get("log_path", "")
    if isinstance(lp, str) and lp:
        norm_lp = os.path.normpath(lp)
        if norm_lp != lp:
            cfg["log_path"] = norm_lp
            changed = True

    # 5) Write back the migrated config if anything changed
    if changed:
        try:
            save_config(path, cfg)
        except Exception:
            pass

    return cfg


def save_config(path: str, cfg: dict) -> None:
    """Save configuration as a formatted JSON file.

    Writes a temp file in the same directory and swaps it in via os.replace
    (atomic on Windows and POSIX), so a concurrent reader — e.g. the tailer's
    5-second config reload — can never observe a truncated file.
    """
    directory = os.path.dirname(os.path.abspath(path))
    with _SAVE_LOCK:
        fd, tmp = tempfile.mkstemp(prefix=".config-", suffix=".tmp", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            for attempt in range(_REPLACE_RETRIES):
                try:
                    os.replace(tmp, path)
                    break
                except PermissionError:
                    if attempt + 1 >= _REPLACE_RETRIES:
                        raise
                    time.sleep(_REPLACE_RETRY_DELAY)
        except Exception:
            try:
                os.remove(tmp)
            except OSError:
                pass
            raise
