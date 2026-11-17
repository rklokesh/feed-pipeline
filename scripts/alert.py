"""Tell the owner when something needs them: a Telegram message from the SarkariChart bot (secret OWNER_CHAT_ID),
plus a comment on the "Daily health report" issue. The same alert (same key) is sent at most once every 6 hours.
  python scripts/alert.py <key> "<message>"
"""
from __future__ import annotations

import datetime as dt
import os
import sys

import requests

from health import NOW, gh

QUIET_H = 6


def send(key: str, text: str) -> None:
    found = gh("GET", "/issues", params={"state": "open", "labels": "health", "per_page": 1}) or []
    num = found[0]["number"] if found else None
    tag = f"<!-- alert:{key} -->"
    if num:
        since = (NOW - dt.timedelta(hours=QUIET_H)).isoformat()
        recent = gh("GET", f"/issues/{num}/comments", params={"since": since, "per_page": 50}) or []
        if any(tag in (c.get("body") or "") for c in recent):
            print("already alerted recently:", key)
            return
        gh("POST", f"/issues/{num}/comments", json={"body": f"{tag}\n🚨 **{text}**"})
    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN", ""), os.environ.get("OWNER_CHAT_ID", "").strip()
    if tok and chat:
        r = requests.post(f"https://api.telegram.org/bot{tok}/sendMessage", timeout=30,
                          data={"chat_id": chat, "text": "🚨 SarkariChart: " + text + "\n\nOpen Claude and say: fix SarkariChart alert."})
        print("telegram:", r.status_code)
    else:
        print("OWNER_CHAT_ID not set: alert only on the health issue")


if __name__ == "__main__":
    send(sys.argv[1], sys.argv[2])
