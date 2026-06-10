
import re

TS_CORE = r'\d{2}/\d{2}\s\d{2}:\d{2}:\d{2}'
TS = rf'{TS_CORE}\s+'

# Known CS2 chat scope labels across all supported game languages.
# ALL-chat variants per language, plus team scopes (CT/T mostly universal).
_SCOPE = (
    # Latin-script ALL variants
    r"ALL|ALLE|TOUS|TODOS|TUTTI|WSZYSCY|TÜMÜ|HEPSİ|MINDENKI|VŠICHNI"
    # Cyrillic ALL variants (RU, BG, UK)
    r"|ВСИЧКИ|ВСЕ|ВСІ"
    # Greek
    r"|ΟΛΟΙ"
    # CJK / Korean / Thai
    r"|전체|全員|全部|所有|ทุกคน"
    # Team scopes (CT/T consistent across most languages; Cyrillic КТ/Т for RU)
    r"|CT|КТ|AT|T|Т"
)

CHAT_ENTRY_RE = re.compile(
    rf'(?P<dt>{TS_CORE})\s+\[(?P<scope>{_SCOPE})\]\s+(?P<name>[^:：]+?)\s*[:：]\s*(?P<msg>.*?)(?=(?:{TS})|\Z)',
    re.DOTALL
)

_TS_FIND_RE = re.compile(TS_CORE)


def iter_chat_entries(buffer: str):
    for m in CHAT_ENTRY_RE.finditer(buffer):
        yield (
            m.group('dt'),
            m.group('scope'),
            m.group('name').strip(),
            m.group('msg').strip(),
            m.end()
        )


def trim_before_last_ts(buffer: str) -> str:
    """Drop everything before the last timestamp in the buffer.

    Any chat entry starting before the last timestamp already had its
    terminating timestamp available, so it was either matched (and consumed
    via endpos) or it is non-chat output that can never match. Only the
    content from the last timestamp onward can still become a chat entry
    once more data arrives.
    """
    start = -1
    for m in _TS_FIND_RE.finditer(buffer):
        start = m.start()
    return buffer[start:] if start > 0 else buffer
