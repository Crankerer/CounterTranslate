import os, re, time, threading
from concurrent.futures import ThreadPoolExecutor
from .util import ts, normalize
from .parser import iter_chat_entries
from .file_follow import open_follow
from .llm import build_system_prompt, call_chatgpt_stream
from .i18n import t
from . import log_setup as _log_setup

_LANG_PREFIX_RE = re.compile(r'^\[([a-z]{2,3})\]\s*', re.IGNORECASE)


def _parse_lang_prefix(text: str) -> tuple[str, str]:
    m = _LANG_PREFIX_RE.match(text)
    if m:
        return m.group(1).lower(), text[m.end():]
    return "", text


def should_ignore(name: str, ignore_names: list[str]) -> bool:
    n = normalize(name).casefold()
    return any(n == normalize(x).casefold() for x in ignore_names)


def start_tail_thread(
    log_path: str,
    config_path: str,
    ignore_names: list[str],
    poll_ms: int,
    cfg: dict,
    queue,
    pool: ThreadPoolExecutor,
) -> threading.Thread:

    def _worker():
        current_log_path = log_path
        f, st_prev = open_follow(current_log_path)
        last_inode = getattr(st_prev, "st_ino", None)
        buffer = ""

        # Local config snapshot — updated on reload, never shared across threads
        current_cfg = dict(cfg)
        current_ignore = list(ignore_names)
        system_prompt = build_system_prompt(
            current_cfg.get("no_translate_langs", []),
            current_cfg.get("target_lang", "German"),
        )
        last_config_check = time.time()
        CONFIG_CHECK_INTERVAL = 5.0

        print(ts(), t("tail.start"))
        print()

        while True:
            try:
                # --- Config hot-reload ---
                now_check = time.time()
                if now_check - last_config_check >= CONFIG_CHECK_INTERVAL:
                    last_config_check = now_check
                    try:
                        from .config import load_config
                        new_cfg = load_config(config_path)
                        if new_cfg != current_cfg:
                            current_cfg = new_cfg
                            current_ignore = current_cfg.get("ignore_names", [])
                            system_prompt = build_system_prompt(
                                current_cfg.get("no_translate_langs", []),
                                current_cfg.get("target_lang", "German"),
                            )
                            print(ts(), t("tail.config_reloaded"))

                            # Reopen file if log_path changed
                            new_log_path = (current_cfg.get("log_path") or "").strip()
                            if new_log_path and new_log_path != current_log_path:
                                try:
                                    f.close()
                                except Exception:
                                    pass
                                current_log_path = new_log_path
                                buffer = ""
                                f, st_prev = open_follow(current_log_path)
                                last_inode = getattr(st_prev, "st_ino", None)
                                print(ts(), t("tail.log_changed", path=current_log_path))
                    except Exception:
                        pass

                # --- Read new log data ---
                chunk = f.read()
                if chunk:
                    buffer += chunk
                    last_end = 0
                    for dt, scope, name, orig_msg, endpos in iter_chat_entries(buffer):
                        last_end = endpos
                        if should_ignore(name, current_ignore):
                            continue

                        stream_id = str(time.monotonic_ns())[-12:]
                        _log_setup.get().debug(
                            f"[chat] [{scope}] {name}: {orig_msg}"
                        )
                        queue.put(("stream_init", {
                            "id": stream_id, "dt": dt, "scope": scope,
                            "name": name, "orig": orig_msg,
                        }))

                        # Snapshot config for this call so hot-reload doesn't race
                        snap = dict(current_cfg)
                        snap_prompt = system_prompt

                        def _stream_worker(
                            sid=stream_id, dt=dt, scope=scope,
                            name=name, orig=orig_msg,
                            snap=snap, prompt=snap_prompt,
                        ):
                            full_text = ""
                            try:
                                for chunk_text in call_chatgpt_stream(
                                    snap["gpt_api"], snap["gpt_model"],
                                    snap.get("open_ai_api_key", ""),
                                    float(snap.get("temperature", 0.2)),
                                    name, orig, prompt,
                                ):
                                    full_text += chunk_text
                                    queue.put(("stream_update", {"id": sid, "delta": chunk_text}))
                            except Exception as e:
                                print(ts(), t("tail.error", err=e))

                            if full_text:
                                lang, msg_clean = _parse_lang_prefix(full_text)
                                if msg_clean:
                                    _log_setup.get().debug(
                                        f"[llm_response] [{lang}] {name} → {msg_clean}"
                                    )
                                    queue.put(("stream_done", {
                                        "id": sid, "dt": dt, "scope": scope,
                                        "name": name, "orig": orig,
                                        "lang": lang, "msg": msg_clean,
                                    }))
                                else:
                                    queue.put(("stream_remove", {"id": sid}))
                            else:
                                queue.put(("stream_remove", {"id": sid}))

                        pool.submit(_stream_worker)

                    if last_end:
                        buffer = buffer[last_end:]
                    if len(buffer) > 2_000_000:
                        buffer = buffer[-1_000_000:]

                else:
                    # --- Check for rotation / truncation ---
                    try:
                        st_now = os.stat(current_log_path)
                    except FileNotFoundError:
                        try:
                            f.close()
                        except Exception:
                            pass
                        print(ts(), t("tail.log_missing"))
                        f, st_prev = open_follow(current_log_path)
                        last_inode = getattr(st_prev, "st_ino", None)
                        buffer = ""
                        time.sleep(poll_ms / 1000)
                        continue

                    current_inode = getattr(st_now, "st_ino", None)
                    current_size = st_now.st_size
                    pos = f.tell()
                    rotated = current_inode and last_inode and current_inode != last_inode
                    truncated = current_size < pos

                    if rotated or truncated:
                        try:
                            f.close()
                        except Exception:
                            pass
                        print(ts(), t("tail.rotation" if rotated else "tail.truncation"))
                        f, st_prev = open_follow(current_log_path)
                        last_inode = getattr(st_prev, "st_ino", None)
                        buffer = ""
                    else:
                        time.sleep(poll_ms / 1000)

            except KeyboardInterrupt:
                print("\n", ts(), t("tail.terminated"))
                try:
                    f.close()
                except Exception:
                    pass
                break
            except Exception as e:
                print(ts(), t("tail.error", err=e))
                time.sleep(poll_ms / 1000)

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    return thread
