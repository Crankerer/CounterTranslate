import json
import re
import requests
from .http_session import SESSION
from .i18n import t
from .util import ts
from . import log_setup as _log_setup
from .config import DEFAULT_API_URL

# No temperature is ever sent: GPT-5+ and o-series models reject anything
# but the default (a 400 on every request), so the setting was removed.

# Original GPT-5 family (not gpt-5.x): reasons by default, which adds seconds
# of latency per chat line. "minimal" keeps it near non-reasoning speed.
_MINIMAL_REASONING_RE = re.compile(r'^gpt-5(-mini|-nano)?(-\d{4}-\d{2}-\d{2})?$', re.IGNORECASE)

# gpt-5.x and gpt-6+ only accept "none" (they reject "minimal"); without it
# some (e.g. gpt-6-luna) reason by default. "none" turns reasoning off.
_NO_REASONING_RE = re.compile(r'^gpt-(5\.\d+|[6-9]|\d{2,})', re.IGNORECASE)


def build_system_prompt(skip_langs: list[str], target_lang: str = "German") -> str:
    skip_codes = sorted({(c or "").split('-')[0].strip().lower() for c in skip_langs if c})
    skip_list = ", ".join(skip_codes) if skip_codes else "(empty)"
    # Small, fast models (gpt-5-nano at minimal reasoning) echoed messages
    # back untranslated and mistranslated game slang with the old terse
    # prompt. The CS2 glossary, the explicit "never echo" rule and the
    # examples are what fixed that — keep them when editing.
    return (
        f"You translate Counter-Strike 2 in-game chat into {target_lang}.\n"
        "Input: JSON with `name` (the player's name — context only, never translate it) "
        "and `message`.\n\n"
        "OUTPUT: exactly one line `[xx] translation`, where xx is the ISO 639-1 code of the "
        f"message's language and the translation is written in {target_lang} — "
        "or output nothing at all.\n\n"
        "Output NOTHING when:\n"
        f"- the message is written in one of these languages: [{skip_list}], or in {target_lang};\n"
        "- there is nothing to translate: only emotes, punctuation, numbers, links, single letters, "
        "or universal gaming shorthand (gg, ez, wp, glhf, gl hf, nt, ns, lol, xd, ok, eco, rush b).\n\n"
        "Otherwise TRANSLATE:\n"
        f"- Always produce real {target_lang}. Never return the message unchanged or still in its "
        "original language.\n"
        "- Players write short, informal, often misspelled messages. Translate the intended meaning "
        "as a teammate would understand it, not word for word.\n"
        "- CS2 terms: A/B (а/б, а/в) are bombsites; mid, long, short, ramp, apps, connector, "
        "palace, banana, heaven, CT/T spawn are map callouts — keep callouts as they are. "
        "\"smoke\", \"flash\", \"molly\", \"nade\" are grenades; \"eco\", \"save\", \"force\", "
        "\"rush\", \"plant\", \"defuse\", \"lurk\", \"rotate\" are tactics; \"AWP\", \"AK\", \"deagle\" are "
        "weapons. \"хп\"/\"hp\" is health.\n"
        "- Keep the tone and its strength: rude stays rude, but do not make it harsher, "
        "and tone down slurs.\n"
        "- One line only: no quotes, notes, alternatives or explanations.\n\n"
        "Format examples. They use English only to show the pattern — your translation "
        f"must be in {target_lang}:\n"
        "{\"name\":\"Oleg\",\"message\":\"кто на а?\"} → [ru] who's on A?\n"
        "{\"name\":\"Oleg\",\"message\":\"киньте флешку\"} → [ru] throw a flash\n"
        "{\"name\":\"Marta\",\"message\":\"nie rushujcie, czekamy\"} → [pl] don't rush, we wait\n"
        "A message like \"gg wp\" gets a completely empty response — not a placeholder.\n"
    )


def call_chatgpt(
    api_url: str, model: str, api_key: str,
    name: str, message: str, system_prompt: str, timeout_s: float = 10.0,
) -> str:
    """Non-streaming chat-completions request. Returns the response text, or "" on error/empty."""
    api_url = (api_url or "").strip() or DEFAULT_API_URL
    if not api_key:
        print(ts(), t("llm.error.no_key"))
        return ""

    _log_setup.get().debug(
        f"[llm_request] api={api_url} model={model} name={name} msg={message[:120]}"
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps({"name": name, "message": message}, ensure_ascii=False)},
        ],
    }
    if _MINIMAL_REASONING_RE.match(model.strip()):
        payload["reasoning_effort"] = "minimal"
    elif _NO_REASONING_RE.match(model.strip()):
        payload["reasoning_effort"] = "none"
    if api_url == DEFAULT_API_URL:
        # Fast tier (formerly "priority"): ~0.95 s instead of ~1.33 s per line
        # for gpt-6-luna, at twice the token price. Proxy only — custom
        # servers such as LM Studio may reject the unknown field.
        payload["service_tier"] = "priority"

    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        res = SESSION.post(
            api_url,
            headers=headers,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            timeout=timeout_s,
        )
        if res.status_code == 401:
            print(ts(), t("llm.error.unauthorized"))
            return ""
        res.raise_for_status()
        data = res.json()
        content = (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""
        return content.strip()
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
