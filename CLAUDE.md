# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the App

```bash
pip install -r requirements.txt
python -m app.main
```

The app requires a `config.json` in the project root (auto-created on first run). On first launch it will prompt via GUI dialogs for a missing API key or CS2 log path.

## Building the Executable

```bat
build.bat
```

This uses Nuitka to produce `dist/CounterTranslate/CounterTranslate.exe` (Launcher) and `dist/CounterTranslate/current/CounterTranslate_app.exe` (App). Language files are copied into the `current/lang/` folder. The version string is auto-generated from the current date/time and written to `app/_build_version.py`.

## Architecture Overview

The app is a Windows-only overlay that tails the CS2 `console.log`, parses chat messages, translates them via an OpenAI-compatible LLM API using streaming, and displays the result in a transparent Tkinter HUD.

**Data flow:**

```
console.log  →  file_follow.py  →  tailer.py  →  llm.py  →  hud.py
(CS2 log)       (robust tail)      (worker thread  (streaming    (Tkinter
                                    + hot-reload)   SSE call)     overlay)
```

**Key modules:**

- `app/main.py` — Entry point. Handles config bootstrapping (API key dialog, log path picker), wires up the `Queue` between `tailer` and `hud`, and launches both. Installs `_HudStream` that tees `sys.stdout` into the HUD queue so `print()` calls appear as overlay lines; lines starting with `[LLM-Error]` or `[Error]` are styled as errors. Also writes every line to the file logger (`log_setup`).
- `app/tailer.py` — Background daemon thread. Reads chunks from `file_follow`, calls `iter_chat_entries`, submits each message to the `ThreadPoolExecutor` (3 workers). Each worker streams via `call_chatgpt_stream` and pushes queue messages directly (see HUD Queue Protocol below). After streaming, parses the `[lang_code]` prefix from the LLM response and enforces `no_translate_langs` client-side — skips the message if the detected language is in the skip set. Also hot-reloads `config.json` every 5 seconds; if `log_path` changes, reopens the file. Logs each detected chat entry, each LLM response, skipped-language messages, and empty responses via `log_setup`.
- `app/llm.py` — LLM I/O. `call_chatgpt_stream` is a generator that yields raw SSE text chunks; `call_chatgpt` wraps it for non-streaming use. `build_system_prompt` constructs the system prompt from `no_translate_langs` and `target_lang`. Reasoning/o-series models (`_NO_TEMP_MODELS`, matched by `_supports_temperature`) do not receive a `temperature` field. Logs each outgoing request via `log_setup`.
- `app/log_setup.py` — File logging singleton. `setup(log_dir)` creates/overwrites `countertranslate.log` in `log_dir` on every startup (mode `'w'`). `get()` returns the `logging.Logger` named `"ct"`. Import `log_setup` and call `get()` from any module that needs to log.
- `app/parser.py` — Regex (`CHAT_ENTRY_RE`) that matches CS2 chat lines with scopes `ALLE`, `ALL`, `T`, `AT`, or `CT`.
- `app/file_follow.py` — Tail implementation that handles log rotation and truncation by reopening the file.
- `app/hud.py` — Transparent, always-on-top Tkinter window that reads from a `Queue` at ~30 fps and renders chat lines. `stream_init` and `stream_update` are no-ops; the completed translation appears on `stream_done` via `_append_struct`.
- `app/settings_ui.py` — `open_settings(parent_root, cfg, config_path, on_save, base_dir)` opens a borderless Tkinter `Toplevel` settings dialog. `base_dir` is used for live UI language switching (calls `i18n.configure` and reopens the dialog). `target_lang` uses a styled combobox (`_TARGET_LANG_OPTIONS`). `no_translate_langs` uses a checkbox-dropdown popup (`field_multicheck`, backed by `_SKIP_LANG_OPTIONS`). When the API URL matches the official OpenAI endpoint, the model is locked to `gpt-4.1-nano` (shown as a non-editable label); for any other URL it is a free text entry. Saves back via the `on_save` callback; does not write `config.json` itself.
- `app/config.py` — `load_config` / `save_config` around `config.json`. Merges `DEFAULTS` for backward compatibility. Supports an `open_ai_api_key_file` pointer as an alternative to embedding the key.
- `app/http_session.py` — Module-level `SESSION`: a shared `requests.Session` with retry/backoff (4 retries, exponential backoff, retries on 429/5xx). Import and reuse this instead of creating new sessions.
- `app/util.py` — Small helpers: `ts()` (HH:MM:SS timestamp string), `normalize(s)` (strips zero-width Unicode characters from chat text), `primary_lang_tag(code)` (extracts the primary subtag from a BCP 47 code).
- `app/i18n.py` — Loads `app/lang/lang_<code>.json`; `t("key", **kwargs)` does string substitution. Call `configure(base_dir, lang_code)` once at startup before any module uses `t()`. Module-level singleton; falls back to `lang_en.json` then `_DEFAULTS` if the JSON is missing. Supported UI language codes: `en`, `de`, `fr`, `pl`, `ru`.
- `app/updater.py` — Checks GitHub releases (repo `Crankerer/CounterTranslate`) on startup when running as frozen EXE, stages the update in `update_pending/`, then restarts via the launcher which applies it.
- `launcher.py` — Thin starter EXE: applies any pending update (`update_pending/` → `current/`), then launches `CounterTranslate_app.exe`.
- `app/_build_version.py` — Auto-generated by `build.bat`; contains `CURRENT_VERSION`. Never edit manually.

## HUD Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Escape` | Close the HUD |
| `F1` | Toggle HUD visibility |
| `F2` | Cycle transparency (0.6 → 0.75 → 0.9) |

## HUD Queue Protocol

`tailer.py` and `main.py` communicate with `hud.py` via a `queue.Queue`. Each item is a `(type, payload)` tuple:

| Type | Payload keys | Description |
|------|-------------|-------------|
| `"line"` | `str` | Plain info/status line |
| `"error"` | `str` | Error line (rendered red) |
| `"structured"` | `dt, scope, name, msg, orig, lang` | Completed non-streamed message |
| `"stream_init"` | `id, dt, scope, name, orig` | No-op in HUD (no placeholder shown) |
| `"stream_update"` | `id, delta` | No-op in HUD |
| `"stream_done"` | `id, dt, scope, name, orig, lang, msg` | Appends completed line via `_append_struct` |
| `"stream_remove"` | `id` | No-op in HUD (LLM returned empty) |

Stream IDs are 12-digit monotonic-ns suffixes.

## config.json Keys

| Key | Default | Description |
|-----|---------|-------------|
| `log_path` | `""` | Absolute path to `console.log` |
| `gpt_api` | OpenAI endpoint | OpenAI-compatible chat completions URL |
| `gpt_model` | `gpt-4o-mini` | Model name |
| `open_ai_api_key` | `""` | API key (or set via `OPENAI_API_KEY` env var) |
| `open_ai_api_key_file` | _(optional)_ | Path to a file containing the API key |
| `temperature` | `0.2` | LLM temperature (omitted for o-series reasoning models) |
| `no_translate_langs` | `["de"]` | ISO 639-1 codes — messages in these languages are skipped |
| `target_lang` | `"German"` | Natural-language name of the target translation language |
| `ignore_names` | `[]` | Player names to ignore |
| `poll_interval_ms` | `100` | Log polling interval |
| `lang` | `"en"` | UI language (`en`, `de`, `fr`, `pl`, or `ru`) |
| `hud_geometry` | _(auto)_ | Saved HUD window position/size (written automatically on move/resize) |

Config is hot-reloaded by `tailer.py` every 5 seconds while running; changes to most fields take effect immediately without restart.

`open_ai_api_key_file` is used as a fallback only when `open_ai_api_key` is empty (key is read from the file at load time).

## Thread Safety

`tailer.py` snapshots `cfg` and `system_prompt` into local variables before submitting a `_stream_worker` to the pool. When adding new pool-submitted workers, always capture the config you need in default-argument closures (`snap=dict(current_cfg)`) so hot-reloads don't race with in-flight requests.

## No Test Suite

There are no automated tests. Verify behavior by running the app against a real or simulated `console.log`.

## Logging

`countertranslate.log` is written to `CONFIG_DIR` (project root in dev, install root in compiled build). It is overwritten on every startup. Use `log_setup.get()` to obtain the logger from any module — do not create new loggers.

| Level | What is logged |
|-------|---------------|
| `INFO` | Startup config summary, all `print()` output (via `_HudStream`) |
| `DEBUG` | `[chat]` every detected CS2 message, `[llm_request]` outgoing API call, `[llm_response]` translated result, `[skipped_lang]` messages suppressed after LLM detected a skip language, `[skipped_empty]` LLM returned empty |
| `ERROR` | Lines starting with `[LLM-Error]` or `[Error]` |

The log file is excluded from git via the existing `*.log` rule in `.gitignore`.

## Internationalization

UI strings live in `app/lang/lang_en.json`, `lang_de.json`, `lang_fr.json`, `lang_pl.json`, and `lang_ru.json`. The `t` function is threaded through every module that needs it; add new keys to all language files when adding user-visible strings. The `_DEFAULTS` dict in `i18n.py` acts as a last-resort fallback for any missing key.
