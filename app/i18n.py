# app/i18n.py
from __future__ import annotations
import json, os
from typing import Any, Dict

_DEFAULTS: Dict[str, str] = {
    # Fallback texts (can remain empty; used as a last resort)
    "app.title": "CS2 Chat Log LLM Monitor",
    "app.header": "========================",
    "cfg.first_time": "[Info] First configuration created: {path}",
    "cfg.create_fail": "[Warning] Could not create config.json: {err}",
    "api.missing": "[Notice] No OpenAI API key found in config.json.",
    "api.saved": "[OK] OpenAI API key saved to {path}",
    "api.save_fail": "[Warning] Could not save API key: {err}",
    "api.dialog.title": "OpenAI API Key Required",
    "api.dialog.prompt": "Please enter your OpenAI API key (usually starts with 'sk-'):",
    "api.dialog.warning.empty_title": "Missing API Key",
    "api.dialog.warning.empty_msg": "No API key entered. The program will exit.",
    "api.dialog.warning.invalid_title": "Invalid Key",
    "api.dialog.warning.invalid_msg": "The key does not appear to be a valid OpenAI key.",
    "abort.no_api": "[Abort] No valid API key entered.",
    "log.hint_choose": "[Notice] log_path is {hint}. Please select your 'Counter-Strike Global Offensive' folder …",
    "dialog.pick_base_folder": "Select the 'Counter-Strike Global Offensive' folder",
    "abort.no_folder": "[Abort] No folder selected.",
    "cfg.log_saved": "[OK] log_path saved to {path}: {log}",
    "cfg.save_fail": "[Warning] Could not save config: {err}",
    "hud.title": "CS2 Chat Log LLM Monitor",
    "hud.logfile": "Log file           : {log}",
    "hud.ignore": "Ignore names       : {names}",
    "hud.gpt_api": "GPT API            : {api}",
    "hud.gpt_model": "GPT Model          : {model}",
    "hud.api_key": "API key            : {state}",
    "hud.temp": "Temperature        : {temp}",
    "hud.no_translate": "no_translate_langs : {langs}",
    "hud.poll": "Poll interval      : {ms} ms",
    "hud.target_lang": "Target language     : {lang}",
    "hud.key_file": "API key file        : {path}",
    "llm.error.no_key": "[LLM-Error] No API key (OPENAI_API_KEY or config).",
    "llm.error.unauthorized": "[LLM-Error] 401 Unauthorized — API key invalid or missing.",
    "llm.error.rate_limit": "[LLM-Error] 429 Rate limit — waiting briefly.",
    "llm.error.timeout": "[LLM-Error] Timeout — LLM did not respond in time.",
    "llm.error.exception": "[LLM-Error] {err}",
    "tail.start": "[Info] Monitoring started.",
    "tail.log_missing": "[Info] Log file not available. Waiting…",
    "tail.rotation": "[Info] Log rotation detected — reopening.",
    "tail.truncation": "[Info] Log truncation detected — reopening.",
    "tail.terminated": "Terminated by user (Ctrl+C).",
    "tail.error": "[Error] {err}",
    "tail.config_reloaded": "[Info] Configuration reloaded.",
    "tail.log_changed": "[Info] Log path changed — switching to: {path}",
}

class I18N:
    def __init__(self, texts: Dict[str, str]):
        self.texts = {**_DEFAULTS, **(texts or {})}

    def t(self, key: str, **kwargs: Any) -> str:
        s = self.texts.get(key, key)  # if key is missing, display the key itself
        try:
            return s.format(**kwargs)
        except Exception:
            return s

def _load_json(path: str) -> Dict[str, str]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_i18n(base_dir: str, lang_code: str) -> I18N:
    # Looks for lang/lang_<code>.json with fallback to EN, then defaults
    candidates = [
        os.path.join(base_dir, "lang", f"lang_{lang_code}.json"),
        os.path.join(base_dir, "lang", "lang_en.json"),
    ]
    for p in candidates:
        if os.path.isfile(p):
            try:
                return I18N(_load_json(p))
            except Exception:
                pass
    return I18N({})


# --- Module-level singleton ---
_instance: 'I18N | None' = None

def configure(base_dir: str, lang_code: str) -> I18N:
    """Call once at startup (in main.py) before any module uses t()."""
    global _instance
    _instance = load_i18n(base_dir, lang_code)
    return _instance

def t(key: str, **kwargs: Any) -> str:
    """Module-level translation function. Returns key unchanged if configure() not yet called."""
    if _instance is None:
        return key
    return _instance.t(key, **kwargs)
