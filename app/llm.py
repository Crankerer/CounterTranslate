import json
import requests
from .http_session import SESSION
from .util import ts

def _supports_temperature(model: str) -> bool:
    m = model.lower()
    if m.startswith("o"):        # o1, o3, o4-mini, …
        return False
    if m.startswith("gpt-5"):    # gpt-5, gpt-5-nano, gpt-5-mini, gpt-5-pro
        return False
    return True

def build_system_prompt(skip_langs: list[str], target_lang: str = "German") -> str:
    skip_codes = sorted({(c or "").split('-')[0].strip().lower() for c in skip_langs if c})
    skip_list = ", ".join(skip_codes) if skip_codes else "(empty)"
    return (
        "You are a precise translator bot for CS2 chat.\n"
        "Input is JSON with fields `name` and `message`.\n\n"
        f"GOAL: Reply in {target_lang} — but ONLY when necessary.\n\n"
        "RULES:\n"
        f"- Detect the language of `message` (ISO 639-1 primary code). SKIP_LANGS = [{skip_list}].\n"
        "- If the language of `message` is in SKIP_LANGS, RETURN AN EMPTY RESPONSE.\n"
        "- If text contains only emotes, punctuation, or whitespace, RETURN EMPTY.\n"
        f"- Otherwise: Translate into {target_lang} — without prefaces or explanations.\n"
        "- Preserve meaning & tone; neutralize abusive content.\n"
        "- Return only the translated text.\n"
    )

def call_chatgpt(api_url: str, model: str, api_key: str, temperature: float,
                 name: str, message: str, system_prompt: str, t, timeout_s: float = 12.0) -> str:
    """
    LLM-Aufruf mit Sprachunterstützung (t-Funktion für Übersetzungen).
    """
    if not api_key:
        print(ts(), t("llm.error.no_key"))
        return ""

    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps({"name": name, "message": message}, ensure_ascii=False)}
        ]
    }

    if _supports_temperature(model):
        payload["temperature"] = float(temperature)

    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        res = SESSION.post(
            api_url,
            headers=headers,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            timeout=timeout_s
        )
        if res.status_code == 401:
            print(ts(), t("llm.error.unauthorized"))
            return ""
        if res.status_code == 429:
            print(ts(), t("llm.error.rate_limit"))
        res.raise_for_status()
        data = res.json()
        choice0 = (data.get("choices") or [{}])[0]
        content = ((choice0.get("message") or {}).get("content") or "").strip()
        return content
    except requests.Timeout:
        print(ts(), t("llm.error.timeout"))
    except requests.HTTPError as e:
        try:
            api_msg = e.response.json().get("error", {}).get("message", str(e))
        except Exception:
            api_msg = str(e)
        print(ts(), t("llm.error.exception", err=api_msg))
    except Exception as e:
        print(ts(), t("llm.error.exception", err=e))
    return ""
