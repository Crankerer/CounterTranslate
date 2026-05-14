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

The app is a Windows-only overlay that tails the CS2 `console.log`, parses chat messages, translates them via an OpenAI-compatible LLM API, and displays the result in a transparent Tkinter HUD.

**Data flow:**

```
console.log  →  file_follow.py  →  tailer.py  →  llm.py  →  hud.py
(CS2 log)       (robust tail)      (worker thread  (OpenAI API   (Tkinter
                                    + rate limit)   call)          overlay)
```

**Key modules:**

- `app/main.py` — Entry point. Handles config bootstrapping (API key dialog, log path picker), wires up the `Queue` between `tailer` and `hud`, and launches both.
- `app/tailer.py` — Background daemon thread. Reads chunks from `file_follow`, calls `iter_chat_entries`, submits each message to the `ThreadPoolExecutor` (3 workers), and delivers translated results via `emit_structured` callback.
- `app/llm.py` — Stateless LLM caller. Builds a system prompt with `no_translate_langs` skip list, sends a JSON payload `{name, message}` to the configured API endpoint, and returns the translated string.
- `app/parser.py` — Regex (`CHAT_ENTRY_RE`) that matches CS2 chat lines with scopes `ALLE`, `T`, or `AT`.
- `app/file_follow.py` — Tail implementation that handles log rotation and truncation by reopening the file.
- `app/hud.py` — Transparent, always-on-top Tkinter window that reads from a `Queue` and renders chat lines.
- `app/config.py` — `load_config` / `save_config` around `config.json`. Merges `DEFAULTS` for backward compatibility. Supports an `open_ai_api_key_file` pointer as an alternative to embedding the key.
- `app/i18n.py` — Loads `app/lang/lang_<code>.json`; `t("key", **kwargs)` does string substitution.
- `app/updater.py` — Checks GitHub releases (repo `Crankerer/CounterTranslate`) on startup when running as frozen EXE, stages the update in `update_pending/`, then restarts via the launcher which applies it.
- `launcher.py` — Thin starter EXE: applies any pending update (`update_pending/` → `current/`), then launches `CounterTranslate_app.exe`.

## config.json Keys

| Key | Default | Description |
|-----|---------|-------------|
| `log_path` | `""` | Absolute path to `console.log` |
| `gpt_api` | OpenAI endpoint | OpenAI-compatible chat completions URL |
| `gpt_model` | `gpt-4o-mini` | Model name |
| `open_ai_api_key` | `""` | API key (or set via `OPENAI_API_KEY` env var) |
| `open_ai_api_key_file` | _(optional)_ | Path to a file containing the API key |
| `temperature` | `0.2` | LLM temperature |
| `no_translate_langs` | `["de"]` | ISO 639-1 codes — messages in these languages are skipped |
| `ignore_names` | `[]` | Player names to ignore |
| `poll_interval_ms` | `100` | Log polling interval |
| `lang` | `"en"` | UI language (`en` or `de`) |

## Internationalization

UI strings live in `app/lang/lang_en.json` and `app/lang/lang_de.json`. The `t` function is threaded through every module that needs it; add new keys to both files when adding user-visible strings.
