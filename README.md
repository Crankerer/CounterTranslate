# CounterTranslate

Transparentes Overlay für CS2, das Chat-Nachrichten automatisch in Echtzeit übersetzt — direkt auf deinem Bildschirm, ohne das Spiel auch nur zu berühren.

![HUD Overlay](doc/main.png)

---

## Was ist CounterTranslate?

Wenn Gegner oder Mitspieler auf Russisch, Rumänisch, Chinesisch oder einer anderen Sprache schreiben, erscheint die Übersetzung sofort als halbtransparentes Overlay — Wort für Wort, während die Nachricht noch eingeht. Kein Alt-Tab, kein Copy-Paste, kein separates Fenster.

- Alle Sprachen werden automatisch erkannt und übersetzt
- Übersetzung läuft per Streaming — erscheint Wort für Wort in Echtzeit
- Transparentes Overlay, immer im Vordergrund
- Eigene Sprache wird nicht übersetzt (Standard: Deutsch)
- Bestimmte Spieler können ignoriert werden

---

## Ist das sicher? Werde ich gebannt?

**Nein, du wirst nicht gebannt — und das ist kein Risiko.**

CounterTranslate liest ausschließlich die `console.log`-Datei, die CS2 selbst schreibt. Das Tool greift **nicht** in den Spielprozess ein, verändert keine Spielmechanik, injiziert keinen Code und hat keine Verbindung zu CS2. VAC und andere Anti-Cheat-Systeme erkennen nur Eingriffe in den laufenden Prozess — CounterTranslate ist für sie unsichtbar, weil es schlicht ein Log-Datei-Leser ist.

---

## Voraussetzungen

- Windows 10 oder 11
- CS2 via Steam
- OpenAI API Key

---

## Setup

### Schritt 1 — Steam Startoption setzen

CS2 muss angewiesen werden, eine Log-Datei zu schreiben. Das passiert über eine einmalige Startoption:

1. Steam öffnen → Bibliothek → **Counter-Strike 2** rechtsklick → **Eigenschaften**
2. Im Feld **Startoptionen** folgendes eintragen:
   ```
   -condebug
   ```
3. Fertig — ab dem nächsten CS2-Start wird die Log-Datei automatisch geschrieben.

Die Datei liegt normalerweise hier:
```
C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\game\csgo\console.log
```
Bei einem anderen Steam-Installationspfad (z.B. auf Laufwerk D:) entsprechend anpassen.

---

### Schritt 2 — OpenAI API Key besorgen

CounterTranslate benötigt einen API Key für die Übersetzung:

1. Account anlegen oder einloggen auf [platform.openai.com](https://platform.openai.com)
2. Unter **API Keys** → **Create new secret key**
3. Den Key kopieren und aufbewahren — er wird gleich in CounterTranslate eingetragen

> Wer kein OpenAI nutzen möchte, kann in den Einstellungen jeden OpenAI-kompatiblen Endpunkt eintragen, z.B. ein lokales Modell via LM Studio.

---

### Schritt 3 — CounterTranslate herunterladen und starten

1. Neueste Version von der [Releases-Seite](https://github.com/Crankerer/CounterTranslate/releases) herunterladen
2. ZIP entpacken
3. `CounterTranslate.exe` starten

Beim **ersten Start** fragt CounterTranslate automatisch nach:
- dem **OpenAI API Key**
- dem Pfad zur **console.log** (Ordner auswählen, der Rest wird automatisch ergänzt)

---

## Benutzung

1. `CounterTranslate.exe` starten — das transparente Overlay erscheint
2. CS2 starten und spielen
3. Sobald jemand im Chat schreibt, erscheint die Übersetzung sofort im Overlay

Das Overlay ist klickdurchlässig und stört das Spielen nicht.

**Tastenkürzel:**

| Taste | Funktion |
|-------|----------|
| `Escape` | Overlay schließen |
| `F1` | Overlay ein-/ausblenden |
| `F2` | Transparenz wechseln (60 % → 75 % → 90 %) |

---

## Einstellungen

Über das Zahnrad-Symbol im Overlay öffnet sich der Einstellungsdialog:

![Einstellungen](doc/settings.png)

| Einstellung | Beschreibung |
|-------------|-------------|
| **Translate into** | Zielsprache der Übersetzung (z.B. `German`) |
| **Skip langs** | Sprachen, die nicht übersetzt werden (z.B. `de` für Deutsch) |
| **Ignore players** | Spielernamen, deren Nachrichten übersprungen werden |
| **API URL** | Endpunkt (Standard: OpenAI, anpassbar für lokale Modelle) |
| **Model** | LLM-Modell (z.B. `gpt-4o-mini`, `gpt-4.1-nano`) |
| **API key** | Dein OpenAI API Key |
| **console.log path** | Pfad zur CS2-Log-Datei |

Alle Einstellungen werden sofort gespeichert und ohne Neustart übernommen.

---

## Fehlerbehebung

**Es erscheint nichts im Overlay**
- Prüfen ob `-condebug` als Steam-Startoption gesetzt ist
- Prüfen ob die `console.log` am eingestellten Pfad existiert
- CS2 einmal neu starten, damit die Log-Datei angelegt wird

**Fehler beim Übersetzen / API-Fehler**
- Prüfen ob der API Key korrekt eingetragen ist
- Prüfen ob das OpenAI-Konto über ausreichend Guthaben verfügt
