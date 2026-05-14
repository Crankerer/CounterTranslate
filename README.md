
# CounterTranslate

Transparentes Windows-Overlay, das den CS2-Chat mitliest und Nachrichten in Echtzeit per LLM übersetzt.

```
CounterTranslate/
├─ app/
│  ├─ main.py             # Einstiegspunkt, Config-Bootstrapping, HUD-Start
│  ├─ config.py           # Laden/Speichern der config.json
│  ├─ tailer.py           # Hintergrund-Thread: Log lesen, Übersetzung anstoßen
│  ├─ llm.py              # OpenAI-kompatibler Chat-Call
│  ├─ parser.py           # Regex für CS2-Chatzeilen (ALLE/T/AT)
│  ├─ file_follow.py      # Robustes Tail (Log-Rotation & Truncation)
│  ├─ hud.py              # Transparentes Tkinter-HUD, immer im Vordergrund
│  ├─ settings_ui.py      # Einstellungsdialog
│  ├─ updater.py          # Automatische Updates via GitHub Releases
│  ├─ i18n.py             # Mehrsprachigkeit (en/de)
│  ├─ http_session.py     # Requests-Session mit Retry/Backoff
│  ├─ util.py             # Hilfsfunktionen
│  └─ lang/
│     ├─ lang_en.json
│     └─ lang_de.json
├─ launcher.py            # Starter-EXE (wendet Updates an, startet App)
├─ build.bat              # Nuitka-Build-Skript
├─ requirements.txt
└─ config.json            # wird beim ersten Start automatisch erstellt
```

## Start

1. Abhängigkeiten installieren:
   ```bash
   pip install -r requirements.txt
   ```
2. Starten:
   ```bash
   python -m app.main
   ```

Beim ersten Start wird per Dialog nach dem API-Key und dem CS2-Basisordner gefragt. Die `config.json` wird automatisch angelegt.

## Build

```bat
build.bat
```

Erzeugt `dist\CounterTranslate\CounterTranslate.exe` via Nuitka.
