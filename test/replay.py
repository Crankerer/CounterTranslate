#!/usr/bin/env python3
"""
Replay test/console.log into test/live.log so CounterTranslate can follow it live.

Usage:
  1. Set log_path in config.json to the absolute path of test/live.log
  2. Start CounterTranslate
  3. In a second terminal: python test/replay.py
"""
import os, sys, time, re, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SRC = os.path.join(os.path.dirname(__file__), "console.log")
DST = os.path.join(os.path.dirname(__file__), "live.log")

CHAT_DELAY = 1.5   # pause after each chat line (seconds)
LINE_DELAY = 0.005 # pause after each non-chat line (seconds)

CHAT_RE = re.compile(r"^\d{2}/\d{2} \d{2}:\d{2}:\d{2}  \[(ALLE|ALL|CT|AT|T)\]")

with open(SRC, "r", encoding="utf-8", errors="ignore") as f:
    lines = f.readlines()

# Truncate/create destination so the app sees a fresh file
with open(DST, "w", encoding="utf-8"):
    pass

print(f"Replaying {len(lines)} lines -> {DST}")
print("Make sure CounterTranslate is already running with log_path set to this file.\n")

chat_count = 0
with open(DST, "a", encoding="utf-8") as out:
    for line in lines:
        out.write(line)
        out.flush()
        if CHAT_RE.match(line):
            chat_count += 1
            print(f"[chat #{chat_count}] {line.rstrip()}")
            time.sleep(CHAT_DELAY)
        else:
            time.sleep(LINE_DELAY)

print(f"\nReplay complete. {chat_count} chat lines sent.")
