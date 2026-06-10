# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the App

Requires **Python 3.10+** (uses `str | None` union syntax). Only two pip dependencies (`requests`, `urllib3`); Tkinter is from the stdlib.

```bash
pip install -r requirements.txt
python -m app.main
```

The app requires a `config.json` in the project root (auto-created on first run). On first launch it will prompt via GUI dialogs for a missing API key or CS2 log path.

**Dev shortcut:** set the `OPENAI_API_KEY` environment variable before launching — `config.py` reads it at startup so you don't need to edit `config.json` or open the settings dialog.

## Building the Executable

Run from PowerShell:

```powershell
.\build.bat
```

From Bash (Claude Code), use:

```bash
cmd.exe /c "\"C:\path\to\build.bat\""
```

This uses Nuitka to produce `dist/CounterTranslate/CounterTranslate.exe` (Launcher) and `dist/CounterTranslate/current/CounterTranslate_app.exe` (App). Language files are copied into the `current/lang/` folder. The version string is auto-generated from the current date/time and written to `app/_build_version.py`.

**Build-time dependencies** (not in `requirements.txt`): `nuitka` and `Pillow` (used to convert `app/icon.png` → `app/icon.ico`). Set the `BUILD_VERSION` env var to override the auto-generated version (e.g. from CI: `set BUILD_VERSION=1.2.3`).

## Architecture Overview

The app is a Windows-only overlay that tails the CS2 `console.log`, parses chat messages, translates them via an OpenAI-compatible LLM API, and displays the result in a transparent Tkinter HUD.

**Data flow:**

```
console.log  →  file_follow.py  →  tailer.py  →  llm.py  →  hud.py
(CS2 log)       (robust tail)      (worker thread  (chat         (Tkinter
                                    + hot-reload)   completion)   overlay)
```

**Key modules:**

- `app/main.py` — Entry point. Detects compiled vs. dev mode via `__compiled__` (Nuitka) / `sys.frozen` (PyInstaller): in compiled mode `BASE_DIR` is `current\` (next to the app EXE) and `CONFIG_DIR` is one level up (the install root); in dev mode both equal the project root. Handles config bootstrapping (log path picker if missing/invalid), wires up the `Queue` between `tailer` and `hud`, and launches both. Installs `_HudStream` that tees `sys.stdout` into the HUD queue so `print()` calls appear as overlay lines; lines starting with `[LLM-Error]` or `[Error]` are styled as errors. Also writes every line to the file logger (`log_setup`). No startup API-key prompt — the key is set via the settings dialog. After `TkHud` init, creates `_alpha_var` (shared `tk.IntVar`) and wires `_on_alpha_change` to save alpha and update the var; `save_font` persists font size changes; both are assigned as callbacks on the `hud` object post-construction. `open_settings_dialog` passes `alpha_var=_alpha_var` so the settings slider stays in sync with F2. Starts `status_checker` via `_on_status` callback; maintains `_status` dict with last known `color`/`tooltip`; `_apply_status()` overrides color to `"blue"` when a custom `gpt_api` URL is set, otherwise forwards the checker result. Current status is passed to `open_settings` at dialog open-time so the settings dot reflects live state.
- `app/tailer.py` — Background daemon thread. Reads chunks from `file_follow`, calls `iter_chat_entries`, submits each message to the `ThreadPoolExecutor` (3 workers). Each worker calls `call_chatgpt` (non-streaming) and on success pushes a single `structured` queue message (see HUD Queue Protocol below). Parses the `[lang_code]` prefix from the LLM response and enforces `no_translate_langs` client-side — skips the message if the detected language is in the skip set. Also hot-reloads `config.json` every 5 seconds; only reacts to changes in `_RELOAD_KEYS` (`gpt_api`, `gpt_model`, `temperature`, `no_translate_langs`, `target_lang`, `log_path`, `poll_interval_ms`, `ignore_names`, `open_ai_api_key`) — UI-only keys like `hud_geometry` and `lang` are intentionally ignored to avoid spurious reloads. If `log_path` changes, reopens the file. Logs each detected chat entry, each LLM response, skipped-language messages, and empty responses via `log_setup`. After each chunk, `trim_before_last_ts` (from `parser.py`) discards buffer content before the last timestamp — non-chat console noise that can never match — so the regex never rescans old data; the 2 MB cap (trim to 1 MB) remains as a safety net. `should_ignore(name, ignore_names)` matches by stripping zero-width chars (`normalize()`) then `casefold()` — both the incoming name and each entry in `ignore_names` are normalized before comparison; trailing bracketed suffixes (`[DEAD]`/`[SPEC]`, any language) are additionally stripped for a second comparison so ignored players stay ignored while dead or spectating.
- `app/llm.py` — LLM I/O. `call_chatgpt` performs a non-streaming chat-completions request and returns the response text (empty string on error or empty response). Falls back to `DEFAULT_API_URL` (from `config.py`) when `api_url` is empty. `build_system_prompt` constructs the system prompt from `no_translate_langs` and `target_lang`. Reasoning/o-series models (`_NO_TEMP_MODELS`, matched by `_supports_temperature`) do not receive a `temperature` field. The request body is sent as raw UTF-8-encoded JSON bytes (not `json=` kwarg). Logs each outgoing request via `log_setup`.
- `app/log_setup.py` — File logging singleton. `setup(log_dir)` creates/overwrites `countertranslate.log` in `log_dir` on every startup (mode `'w'`). `get()` returns the `logging.Logger` named `"ct"`. Import `log_setup` and call `get()` from any module that needs to log.
- `app/parser.py` — Exports `CHAT_ENTRY_RE` (regex), `iter_chat_entries(buffer)` (generator), and `trim_before_last_ts(buffer)` (drops buffer content before the last timestamp; used by `tailer.py` to keep the scan buffer small). Matches CS2 chat lines for all supported game languages via an explicit scope alternation (`_SCOPE`): covers ALL-chat variants (`ALL`, `ALLE`, `TOUS`, `TODOS`, `ВСЕ`, `WSZYSCY`, `TUTTI`, `ТÜМÜ`, Cyrillic/CJK variants, etc.) and team scopes (`CT`, `T`, `AT`, `КТ`, `Т`). Accepts both ASCII colon `:` and full-width colon `：` as the name/message separator. `[DEAD]`/`[SPEC]` suffixes after the player name are captured as part of the name field. Uses `re.DOTALL`. Yields `(dt, scope, name, msg, endpos)` tuples.
- `app/file_follow.py` — Tail implementation that handles log rotation and truncation by reopening the file.
- `app/hud.py` — Transparent, always-on-top Tkinter window that reads from a `Queue` at ~30 fps (33 ms poll via `root.after`) and renders chat lines. Two layout modes: **normal** (`_normal_frame`: topbar + text widget + resize handle) and **compact** (`_compact_frame`: scrolling ticker canvas + buttons). The topbar contains a **status dot** (14×14 canvas, top-left), then ⊟ compact-toggle, ⛭ settings, and ✕ close buttons (all `Consolas 12 bold`, `padx=4`). The status dot is present in both normal and compact topbars; hovering shows a tooltip (`_tooltip_show`/`_tooltip_hide` via `Toplevel`). `set_status_color(color, tooltip)` updates both dots and tooltip text thread-safely via `root.after(0, ...)`. `set_status_visible(enabled)` sets the user preference flag; `_update_dot_visibility()` shows the dot when enabled OR when color is `"yellow"`/`"red"` (force-shown regardless of toggle). Status colors: `green=#44dd44`, `yellow=#ffcc00`, `red=#ff4444`, `blue=#4488ff`, gray=`#555555` (initial). Compact mode shows a single scrolling line (delta-time animation at ~60 fps via `_ticker_tick`); speed is configurable via `set_ticker_speed(px)`. Mode switch is purely visual — content is always written to the text widget. `Ctrl+MouseWheel` zooms font size (7–28pt); persisted via `on_font_change` callback. Alpha is set from `cfg["hud_alpha"]`; F2 cycles through 5 steps (1.0→0.8→0.6→0.4→0.2) and calls `on_alpha_change`. `_show_in_taskbar` sets `WS_EX_APPWINDOW` + withdraw/deiconify cycle so the window appears in the taskbar. Icon loaded from `app/icon.ico` (or `icon.png` via PIL). Completed translations arrive as `structured` queue messages and are rendered via `_append_struct`. The text widget trims itself when the line count exceeds 2000 (removes the oldest 200 lines).
- `app/settings_ui.py` — `open_settings(parent_root, cfg, config_path, on_save, base_dir, alpha_var, status_color, status_tooltip)` opens a borderless 620×680 Tkinter `Toplevel` settings dialog. `base_dir` is used for live UI language switching. `alpha_var` is a shared `tk.IntVar` (20–100) passed from `main.py` so F2 key presses update the opacity slider live; the trace is removed on window destroy. Interface section includes compact mode checkbox, ticker speed entry, HUD opacity slider (`field_slider`), a **Proxy-Status row** (colored dot + status text, hover tooltip using `status_color`/`status_tooltip` passed at open-time), and a `show_status_dot` checkbox. `target_lang` uses a styled combobox. `no_translate_langs` uses a checkbox-dropdown popup. The API key field is masked with `•`; an empty key field means "keep the stored key" — the key cannot be cleared via the UI. Widget values are gathered by a single `_collect()` helper shared by Save and the live UI-language switch (which rebuilds the dialog with collected values as the new `cfg`). Saves back via `on_save`; does not write `config.json` itself.
- `app/config.py` — `load_config` / `save_config` around `config.json`. Merges `DEFAULTS` for backward compatibility. Exports `DEFAULT_API_URL` (the built-in proxy endpoint used when `gpt_api` is empty). Supports an `open_ai_api_key_file` pointer as an alternative to embedding the key (config only, not exposed in settings UI). `DEFAULTS` contains legacy keys `llm_api` and `llm_model` (kept for backward compatibility with older config files; not used at runtime).
- `app/status_checker.py` — Polls `GET https://crimson-dog-44043.zap.cloud/status` every 5 minutes (3 s initial delay) in a daemon thread. `_check(key)` returns `(color, tooltip_text)`: `"red"` if unreachable, no `ct_key` in response (no key configured), or key is invalid/expired; `"yellow"` if key is valid but `openai.reachable`/`key_set` is false or `status != "ok"`; `"green"` otherwise. If `open_ai_api_key` starts with `ct-` it is sent as `Authorization: Bearer` so the server validates it and returns a `ct_key` block. Tooltip includes status, key validity + days remaining, OpenAI reachability, and formatted uptime. Does **not** use `http_session.SESSION` (no retries — fail fast for a status probe). `start(on_status_change, get_key, initial_delay)` launches the thread; `get_key` is a callable returning the current key string; callback receives `(color, tooltip)`.
- `app/http_session.py` — Module-level `SESSION`: a shared `requests.Session` with retry/backoff (4 retries, exponential backoff, retries on 429/5xx). Import and reuse this instead of creating new sessions.
- `app/util.py` — Small helpers: `ts()` (HH:MM:SS timestamp string), `normalize(s)` (strips zero-width Unicode characters from chat text), `primary_lang_tag(code)` (extracts the primary subtag from a BCP 47 code).
- `app/i18n.py` — Loads `app/lang/lang_<code>.json`; `t("key", **kwargs)` does string substitution. Call `configure(base_dir, lang_code)` once at startup before any module uses `t()`. Module-level singleton; falls back to `lang_en.json` then `_DEFAULTS` if the JSON is missing. Supported UI language codes: `en`, `de`, `fr`, `pl`, `ru`.
- `app/updater.py` — Checks GitHub releases (repo `Crankerer/CounterTranslate`) on startup when running as frozen EXE (`maybe_update(prereleases=False)`). Only stable (non-draft, non-prerelease) releases are considered. If the first page of the release listing has none, `/releases/latest` is consulted (pagination-proof); only when the repo has no stable release at all does the updater fall back to the newest prerelease (bootstrap phase before the first promoted release). If a newer version is found, shows a yes/no dialog asking the user to confirm before downloading. On confirmation, shows a `_UpdateUI` progress window while downloading. Stages the update in `update_pending/`, then restarts via the launcher which applies it.
- `launcher.py` — Thin starter EXE: applies any pending update (`update_pending/` → `current/`), then launches `CounterTranslate_app.exe` with `cwd=current` so DLL resolution works on fresh installs.
- `app/_build_version.py` — Auto-generated by `build.bat`; contains `CURRENT_VERSION`. Never edit manually.

## Manual Testing Helper

`test/replay.py` replays a recorded `test/console.log` line by line into `test/live.log` with configurable delays so the running app can follow it live. There are no automated tests — verify behavior by running the app against a real or simulated `console.log`.

Usage:
1. Set `log_path` in `config.json` to the absolute path of `test/live.log`
2. Start CounterTranslate
3. In a second terminal: `python test/replay.py`

**Note:** `replay.py`'s internal scope regex only recognises `ALLE|ALL|CT|AT|T`. Lines with other game-language scopes (Russian, CJK, etc.) still replay correctly — the full parser handles them — but they won't increment `replay.py`'s `chat_count` console output.

For testing against a live CS2 installation, CS2 must be launched with the `-condebug` Steam launch option. The log is then written to:
```
C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\game\csgo\console.log
```

## HUD Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Escape` | Close the HUD |
| `F1` | Toggle HUD visibility |
| `F2` | Cycle opacity: five steps — 1.0 → 0.8 → 0.6 → 0.4 → 0.2 → 1.0 (0 % to 80 % transparent). Finds nearest step and advances to next. Saved to config and synced to Settings slider. |
| `Ctrl+MouseWheel` | Zoom font size (7–28 pt, normal mode only). Saved to config immediately. |

## HUD Queue Protocol

`tailer.py` and `main.py` communicate with `hud.py` via a `queue.Queue`. Each item is a `(type, payload)` tuple:

| Type | Payload keys | Description |
|------|-------------|-------------|
| `"line"` | `str` | Plain info/status line |
| `"error"` | `str` | Error line (rendered red) |
| `"structured"` | `dt, scope, name, msg, orig, lang` | Completed translation, rendered via `_append_struct` |

## config.json Keys

| Key | Default | Description |
|-----|---------|-------------|
| `log_path` | `""` | Absolute path to `console.log` |
| `gpt_api` | `""` | OpenAI-compatible chat completions URL; empty = use `DEFAULT_API_URL` |
| `gpt_model` | `gpt-4.1-nano` | Model name (ignored when `gpt_api` is empty — default model is always `gpt-4.1-nano`) |
| `open_ai_api_key` | `""` | API key (or set via `OPENAI_API_KEY` env var) |
| `open_ai_api_key_file` | _(optional)_ | Path to a file containing the API key |
| `temperature` | `0.2` | LLM temperature (omitted for o-series reasoning models) |
| `no_translate_langs` | `["de"]` | ISO 639-1 codes — messages in these languages are skipped |
| `target_lang` | `"German"` | Natural-language name of the target translation language |
| `ignore_names` | `[]` | Player names to ignore |
| `poll_interval_ms` | `100` | Log polling interval |
| `lang` | `"en"` | UI language (`en`, `de`, `fr`, `pl`, or `ru`) |
| `hud_geometry` | _(absent = `800x320+40+720`)_ | Saved HUD window position/size (written automatically on move/resize) |
| `hud_font` | `"Consolas 11"` | Saved HUD font string (written on Ctrl+MouseWheel zoom or settings save) |
| `hud_alpha` | `0.72` | HUD opacity 0.2–1.0 (written on F2 or settings save) |
| `compact_mode` | `false` | Start in compact/ticker mode |
| `ticker_speed` | `2` | Ticker scroll speed in px/frame at 60 fps |
| `show_status_dot` | `true` | Show proxy status dot in HUD topbar; yellow/red always override this and force the dot visible |
| `always_on_top` | `true` | Keep the HUD window above all other windows (`-topmost`); can be toggled in settings |
| `llm_api` | local endpoint | Legacy key kept in `DEFAULTS` for backward compatibility; not used at runtime |
| `llm_model` | `"local-model"` | Legacy key kept in `DEFAULTS` for backward compatibility; not used at runtime |

Config is hot-reloaded by `tailer.py` every 5 seconds while running; changes to most fields take effect immediately without restart.

`open_ai_api_key_file` is used as a fallback only when `open_ai_api_key` is empty (key is read from the file at load time).

## Thread Safety

`tailer.py` snapshots `cfg` and `system_prompt` into local variables before submitting a `_translate_worker` to the pool. When adding new pool-submitted workers, always capture the config you need in default-argument closures (`snap=dict(current_cfg)`) so hot-reloads don't race with in-flight requests.

## Logging

`countertranslate.log` is written to `CONFIG_DIR`. In dev mode `CONFIG_DIR` equals the project root. In compiled builds `CONFIG_DIR` is the install root (one level above `current/` where the EXE lives), so `config.json` and the log survive updates. The log is overwritten on every startup. Use `log_setup.get()` to obtain the logger from any module — do not create new loggers.

| Level | What is logged |
|-------|---------------|
| `INFO` | Startup config summary, all `print()` output (via `_HudStream`) |
| `DEBUG` | `[chat]` every detected CS2 message, `[ignored]` messages from ignored players, `[llm_request]` outgoing API call, `[llm_response]` translated result, `[skipped_lang]` messages suppressed after LLM detected a skip language, `[skipped_empty]` LLM returned empty |
| `ERROR` | Lines starting with `[LLM-Error]` or `[Error]` |

The log file is excluded from git via the existing `*.log` rule in `.gitignore`.

## Versioning and Releases

Version format: `0.<major>.<yyMMddHHmm>`. Releases are built and published by CI (`.github/workflows/release.yml`): pushing any `v*` tag triggers a Windows build with `BUILD_VERSION` set to the tag name (`build.bat` strips the leading `v`), zips `dist\CounterTranslate` into `CounterTranslate-windows-x64.zip`, and creates a GitHub release with `--generate-notes --prerelease`.

To release a new major version (e.g. `0.16` → `0.17`):

1. Update the two occurrences of the old version in `build.bat` (lines with `CURRENT_VERSION` and `WIN_VERSION`)
2. Commit: `chore: bump version to 0.17`
3. Tag with the full version: `git tag v0.17.<yyMMddHHmm>` (use the current date/time for the suffix — the tag itself defines the built version)
4. Push the tag: `git push origin v0.17.<yyMMddHHmm>` — CI does the rest

**Important:** the auto-updater (`maybe_update(prereleases=False)`) ignores prereleases, so a CI-created release is invisible to existing installs until you manually edit it on GitHub and uncheck "pre-release". This is the intended promotion step after verifying the build. Exception: as long as the repo has no stable release at all, the updater falls back to the newest prerelease (bootstrap phase).

`build.bat` without `BUILD_VERSION` set (local dev builds) auto-generates the datetime suffix from the current time.

The `ct-` prefix on `open_ai_api_key` identifies a proxy key (issued by the CounterTranslate proxy). Plain OpenAI keys (`sk-...`) work for direct API access but are not sent to the proxy status endpoint.

## Internationalization

UI strings live in `app/lang/lang_en.json`, `lang_de.json`, `lang_fr.json`, `lang_pl.json`, and `lang_ru.json`. The `t` function is threaded through every module that needs it; add new keys to all language files when adding user-visible strings. The `_DEFAULTS` dict in `i18n.py` acts as a last-resort fallback for any missing key.
