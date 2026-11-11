"""Post newly published notices to the WhatsApp Channel "Sarkari Chart" through Whapi.Cloud (secret WHAPI_TOKEN).

Same idea as telegram.py: runs after each deploy, remembers what it posted in data/whatsapp.json, and the first run
only records the existing notices (no flood). Kept gentle for WhatsApp and the free plan:
  - at most 5 posts per run and 15 per day (IST);
  - only notices published in the last 48 hours are posted one by one; anything older (e.g. after the Mac was off)
    is marked as done without posting.
  python scripts/whatsapp.py            # post new notices
  python scripts/whatsapp.py --test     # find the channel and send one test post
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import sys
import time

import requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOKEN = os.environ.get("WHAPI_TOKEN", "").strip()
CHANNEL_NAME = os.environ.get("WHATSAPP_CHANNEL", "Sarkari Chart")
SITE = os.environ.get("SITE_URL", "https://sarkarichart.com")
API = "https://gate.whapi.cloud"
STATE = ROOT / "data/whatsapp.json"
REPORT = ROOT / "reports/whatsapp.txt"
PER_RUN, PER_DAY, FRESH_H = 5, 15, 48
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
TYPE_HI = {"Job": "नौकरी", "Result": "रिज़ल्ट", "Admit card": "एडमिट कार्ड", "Answer key": "आंसर की", "Update": "अपडेट", "Admission": "प्रवेश"}
EMOJI = {"Job": "🆕", "Result": "📊", "Admit card": "🎫", "Answer key": "🔑", "Update": "📢", "Admission": "🎓"}
H = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/json", "Content-Type": "application/json"}
log: list[str] = []


def call(method, path, **kw):
    r = requests.request(method, API + path, headers=H, timeout=40, **kw)
    try:
        j = r.json()
    except ValueError:
        j = {}
    return r.status_code, j


def find_channel(state):
    if state.get("channel_id"):
        return state["channel_id"]
    code, j = call("GET", "/newsletters", params={"count": 100})
    items = j.get("newsletters") if isinstance(j, dict) else j
    items = items or []
    names = []
    for n in items:
        name = (n.get("name") or (n.get("metadata") or {}).get("name") or "")
        names.append(name)
        if name.strip().lower() == CHANNEL_NAME.lower():
            state["channel_id"] = n.get("id")
            return n.get("id")
    log.append(f"channel '{CHANNEL_NAME}' not found (HTTP {code}); channels this number manages: {names}"[:600])
    return None


def caption(n):
    c = n.get("card") or {}
    typ = c.get("type", "Job")
    en = c.get("title_en") or n.get("title")
    hi = c.get("title_hi") or ""
    url = f"{SITE}/notice/{n['slug']}/"
    lines = [f"{EMOJI.get(typ, '🆕')} *{en}*"]
    if hi and hi != en:
        lines.append(hi)
    lines += ["", f"🏛 {n.get('org') or ''} · {typ} / {TYPE_HI.get(typ, '')}"]
    if typ == "Job" and c.get("last_date"):
        lines.append(f"⏳ Last date / अंतिम तिथि: *{dt.date.fromisoformat(c['last_date']).strftime('%-d %b %Y')}*")
    lines += ["", f"👉 Details & official PDF: {url}"]
    return "\n".join(lines), url


def post(chan, n):
    text, _ = caption(n)
    img = f"{SITE}/notice/{n['slug']}/og.png"
    code, j = call("POST", "/messages/image", json={"to": chan, "media": img, "caption": text})
    if code >= 300 or not (j.get("sent") or j.get("message")):
        code, j = call("POST", "/messages/text", json={"to": chan, "body": text})
    ok = code < 300 and bool(j.get("sent") or j.get("message"))
    log.append(f"{n['id']} -> {code} {'ok' if ok else 'failed: ' + str(j.get('error') or '')[:120]}")   # never log full replies: they hold the phone number
    return ok


def main():
    if not TOKEN:
        log.append("WHAPI_TOKEN secret is missing in GitHub; nothing posted.")
        return finish({})
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    chan = find_channel(state)
    if not chan:
        return finish(state)
    if "--test" in sys.argv:
        code, j = call("POST", "/messages/text", json={"to": chan, "body":
            "✅ SarkariChart alerts are connected. New govt job notices will appear here automatically.\n"
            "सरकारी चार्ट अलर्ट जुड़ गए हैं। नई सरकारी नौकरी की सूचनाएँ यहाँ अपने-आप आएँगी।\n\nhttps://sarkarichart.com"})
        log.append(f"test -> {code} {'sent' if j.get('sent') else 'not sent: ' + str(j.get('error') or '')[:120]}")
        return finish(state)
    notices = [json.loads(f.read_text()) for f in (ROOT / "data/notices").glob("*.json")]
    live = [n for n in notices if n.get("status") == "approved" and n.get("slug")]
    done = set(state.get("posted", []))
    if "posted" not in state:   # first run: remember what is already live, post nothing
        state["posted"] = sorted(n["id"] for n in live)
        log.append(f"first run: recorded {len(live)} existing notices, posted none")
        return finish(state)
    now = dt.datetime.now(dt.timezone.utc)
    today = now.astimezone(IST).date().isoformat()
    if state.get("day") != today:
        state["day"], state["today"] = today, 0
    new = sorted([n for n in live if n["id"] not in done], key=lambda n: n.get("published_at") or "")
    sent = 0
    for n in new:
        pub = n.get("published_at") or n.get("first_seen") or ""
        try:
            age_h = (now - dt.datetime.fromisoformat(pub.replace("Z", "+00:00"))).total_seconds() / 3600
        except ValueError:
            age_h = 999
        if age_h > FRESH_H:   # missed while away: too old to post now
            done.add(n["id"]); continue
        if sent >= PER_RUN or state["today"] >= PER_DAY:
            break
        if post(chan, n):
            done.add(n["id"]); sent += 1; state["today"] += 1
        time.sleep(8)
    state["posted"] = sorted(done)
    log.append(f"posted {sent}; {state['today']} today")
    finish(state)


def finish(state):
    if state:
        STATE.write_text(json.dumps(state, indent=1))
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text("\n".join(log) or "nothing new")
    print("\n".join(log) or "nothing new")


if __name__ == "__main__":
    main()
