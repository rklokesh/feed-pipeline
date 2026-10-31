"""Auto-post every newly published notice to the Telegram channel @sarkarichart (free, official Bot API).

Runs after each site deploy (so the share image og.png is live). Remembers what it posted in data/telegram.json.
First run only records the existing notices (no flood); later runs post just the new ones.
  python scripts/telegram.py            # post new notices
  python scripts/telegram.py --test     # send one test message
"""
from __future__ import annotations

import datetime as dt
import html
import json
import os
import pathlib
import sys
import time

import requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
CHANNEL = os.environ.get("TELEGRAM_CHANNEL", "@sarkarichart")
SITE = os.environ.get("SITE_URL", "https://sarkarichart.pages.dev")
STATE = ROOT / "data/telegram.json"
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
REPORT = ROOT / "reports/telegram.txt"
TYPE_HI = {"Job": "नौकरी", "Result": "रिज़ल्ट", "Admit card": "एडमिट कार्ड", "Answer key": "आंसर की", "Update": "अपडेट", "Admission": "प्रवेश"}
EMOJI = {"Job": "🆕", "Result": "📊", "Admit card": "🎫", "Answer key": "🔑", "Update": "📢", "Admission": "🎓"}


def api(method, **data):
    r = requests.post(f"https://api.telegram.org/bot{TOKEN}/{method}", data=data, timeout=30)
    return r.status_code, r.json() if r.headers.get("content-type", "").startswith("application/json") else {}


def d_en(iso):
    return dt.date.fromisoformat(iso).strftime("%-d %b %Y")


def caption(n):
    c = n.get("card") or {}
    typ = c.get("type", "Job")
    en = c.get("title_en") or n.get("title")
    hi = c.get("title_hi") or ""
    url = f"{SITE}/notice/{n['slug']}/" if n.get("slug") else n.get("url")
    lines = [f"{EMOJI.get(typ, '🆕')} <b>{html.escape(en)}</b>"]
    if hi:
        lines.append(html.escape(hi))
    lines.append("")
    lines.append(f"🏛 {html.escape(n.get('org') or '')} · {typ} / {TYPE_HI.get(typ, '')}")
    if typ == "Job" and c.get("last_date"):
        lines.append(f"⏳ Last date / अंतिम तिथि: <b>{d_en(c['last_date'])}</b>")
    lines.append("")
    lines.append(f"👉 Details & official PDF: {url}")
    return "\n".join(lines), url


def main():
    log = []
    if not TOKEN:
        log.append("TELEGRAM_BOT_TOKEN secret is missing in GitHub; nothing posted.")
        REPORT.parent.mkdir(exist_ok=True); REPORT.write_text("\n".join(log)); print(log[-1]); return
    if "--test" in sys.argv:
        code, j = api("sendMessage", chat_id=CHANNEL, text="✅ SarkariChart alerts are connected. New govt job notices will appear here automatically.\nसरकारी चार्ट: हर नई सरकारी नौकरी की सूचना यहाँ अपने आप आएगी।",
                      disable_web_page_preview="true")
        log.append(f"test -> {code} {j.get('ok')} {j.get('description', '')}")
        REPORT.parent.mkdir(exist_ok=True); REPORT.write_text("\n".join(log)); print(log); return
    notices = [json.loads(f.read_text()) for f in (ROOT / "data/notices").glob("*.json")]
    live = [n for n in notices if n.get("status") == "approved" and n.get("slug")]
    first = not STATE.exists()
    state = json.loads(STATE.read_text()) if STATE.exists() else {"posted": []}
    done = set(state["posted"])
    if first:
        state["posted"] = sorted(n["id"] for n in live)
        log.append(f"first run: recorded {len(live)} existing notices, posted none")
    else:
        new = sorted([n for n in live if n["id"] not in done], key=lambda n: n.get("published_at") or "")
        for n in new[:20]:
            text, url = caption(n)
            img = f"{SITE}/notice/{n['slug']}/og.png"
            code, j = api("sendPhoto", chat_id=CHANNEL, photo=img, caption=text, parse_mode="HTML")
            if not j.get("ok"):   # image not reachable yet etc.: send text with link preview instead
                code, j = api("sendMessage", chat_id=CHANNEL, text=text, parse_mode="HTML")
            log.append(f"{n['id']} -> {code} {j.get('ok')} {j.get('description', '')}")
            if j.get("ok"):
                done.add(n["id"])
            time.sleep(4)   # stay well under Telegram's limits
        state["posted"] = sorted(done)
    STATE.write_text(json.dumps(state, indent=1))
    REPORT.parent.mkdir(exist_ok=True); REPORT.write_text("\n".join(log) or "nothing new")
    print("\n".join(log) or "nothing new")


if __name__ == "__main__":
    main()
