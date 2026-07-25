
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def make_session() -> requests.Session:
    s = requests.Session()
    # Kept deliberately short: this session serves live chat translation, where
    # a late answer is a useless answer. With the per-attempt timeout in llm.py
    # the worst case is ~31 s (3 attempts + backoff) instead of ~80 s, which
    # used to let one stalled message block a pool worker for over a minute.
    retry = Retry(
        total=2, backoff_factor=0.4,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(['POST'])
    )
    s.mount("http://", HTTPAdapter(max_retries=retry))
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.headers.update({"Content-Type": "application/json"})
    return s

SESSION = make_session()
