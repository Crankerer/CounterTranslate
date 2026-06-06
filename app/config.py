import os, json

DEFAULT_API_URL = "https://crimson-dog-44043.zap.cloud/v1/chat/completions"

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


def load_config(path: str) -> dict:
    # 1) Read the file safely
    try:
        with open(path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            if not isinstance(cfg, dict):
                cfg = {}
    except FileNotFoundError:
        cfg = {}
    except Exception:
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
    """Save configuration as a formatted JSON file."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
