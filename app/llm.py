import json
import re
import requests
from .http_session import SESSION
from .i18n import t
from .util import ts
from . import log_setup as _log_setup

_NO_TEMP_MODELS = frozenset({"o1", "o1-mini", "o1-preview", "o3", "o3-mini", "o4-mini"})
_O_SERIES_RE = re.compile(r'^o\d', re.IGNORECASE)


def _supports_temperature(model: str) -> bool:
    m = model.strip().lower()
    return m not in _NO_TEMP_MODELS and not _O_SERIES_RE.match(m)


def build_system_prompt(skip_langs: list[str], target_lang: str = "German") -> str:
    skip_codes = sorted({(c or "").split('-')[0].strip().lower() for c in skip_langs if c})
    skip_list = ", ".join(skip_codes) if skip_codes else "(empty)"
    return (
        "You are a precise translator bot for CS2 chat.\n"
        "Input is JSON with fields `name` and `message`.\n\n"
        f"GOAL: Translate `message` into {target_lang} when necessary.\n\n"
        "OUTPUT FORMAT:\n"
        "- If translation is needed: start with the detected source language code in brackets, "
        "then a space, then the translation.\n"
        f"  Example for Russian input: `[ru] {target_lang} translation here`\n"
        "- If translation is NOT needed: return absolutely nothing (empty response).\n\n"
        "RULES:\n"
        f"- Detect source language (ISO 639-1 primary tag). SKIP_LANGS = [{skip_list}].\n"
        "- If source language is in SKIP_LANGS: return EMPTY.\n"
        "- If text is only emotes, punctuation, numbers, or whitespace: return EMPTY.\n"
        f"- Otherwise: output `[lang_code] {target_lang}_translation`.\n"
        "- Preserve tone; neutralize abusive content.\n"
        "- No explanations or prefaces — only the formatted output or empty.\n"
    )


def call_chatgpt_stream(
    api_url: str, model: str, api_key: str, temperature: float,
    name: str, message: str, system_prompt: str, timeout_s: float = 15.0
):
    """Generator: yields raw SSE text chunks. Full response format: '[xx] translated' or empty."""
    if not api_key:
        print(ts(), t("llm.error.no_key"))
        return

    _log_setup.get().debug(
        f"[llm_request] api={api_url} model={model} name={name} msg={message[:120]}"
    )

    payload = {
        "model": model,
        "stream": True,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps({"name": name, "message": message}, ensure_ascii=False)},
        ],
    }
    if _supports_temperature(model):
        payload["temperature"] = float(temperature)

    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        res = SESSION.post(
            api_url,
            headers=headers,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            stream=True,
            timeout=timeout_s,
        )
        if res.status_code == 401:
            print(ts(), t("llm.error.unauthorized"))
            return
        if res.status_code == 429:
            print(ts(), t("llm.error.rate_limit"))
        res.raise_for_status()
        for raw_line in res.iter_lines():
            if not raw_line:
                continue
            line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
            if not line.startswith("data: "):
                continue
            data_str = line[6:]
            if data_str.strip() == "[DONE]":
                break
            try:
                data = json.loads(data_str)
                delta = (data.get("choices") or [{}])[0].get("delta", {}).get("content") or ""
                if delta:
                    yield delta
            except (json.JSONDecodeError, IndexError, KeyError):
                continue
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


def call_chatgpt(
    api_url: str, model: str, api_key: str, temperature: float,
    name: str, message: str, system_prompt: str, timeout_s: float = 12.0,
) -> str:
    return "".join(
        call_chatgpt_stream(api_url, model, api_key, temperature, name, message, system_prompt, timeout_s)
    )
