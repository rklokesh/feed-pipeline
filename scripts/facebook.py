"""Post newly published notices to the SarkariChart Facebook Page (Meta Graph API).

Secrets: FB_PAGE_ID and FB_PAGE_TOKEN (a long-lived Page access token with pages_manage_posts).
Same rules as whatsapp.py: remembers what it posted in data/facebook.json; the first run only records the existing
notices (no flood); at most 5 posts per run and 12 per day; only notices from the last 48 hours.
  python scripts/facebook.py            # post new notices
  python scripts/facebook.py --status   # check the token and page, post nothing
  python scripts/facebook.py --test     # post the newest open job notice not yet posted
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
PAGE = os.environ.get("FB_PAGE_ID", "").strip()
TOKEN = os.environ.get("FB_PAGE_TOKEN", "").strip()
SITE = os.environ.get("SITE_URL", "https://sarkarichart.com")
API = "https://graph.facebook.com/v21.0"
STATE = ROOT / "data/facebook.json"
REPORT = ROOT / "reports/facebook.txt"
PER_RUN, PER_DAY, FRESH_H = 5, 12, 48
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
TYPE_HI = {"Job": "नौकरी", "Result": "रिज़ल्ट", "Admit card": "एडमिट कार्ड", "Answer key": "आंसर की", "Update": "अपडेट", "Admission": "प्रवेश"}
WA = "https://whatsapp.com/channel/0029Vb9M2x930LKIvmiBrY2s"
log: list[str] = []


def caption(n):
    c = n.get("card") or {}
    typ = c.get("type", "Job")
    en = c.get("title_en") or n.get("title")
    hi = c.get("title_hi") or ""
    lines = [en]
    if hi and hi != en:
        lines.append(hi)
    lines += ["", f"{n.get('org') or ''} · {typ} / {TYPE_HI.get(typ, '')}"]
    if typ == "Job" and c.get("last_date"):
        lines.append(f"Last date / अंतिम तिथि: {dt.date.fromisoformat(c['last_date']).strftime('%-d %b %Y')}")
    lines += ["", f"Details and official links: {SITE}/notice/{n['slug']}/", "", f"Free alerts on WhatsApp: {WA}"]
    return "\n".join(lines)


def post(n):
    cap = caption(n)
    img = f"{SITE}/notice/{n['slug']}/og.png"
    r = requests.post(f"{API}/{PAGE}/photos", data={"url": img, "caption": cap, "access_token": TOKEN}, timeout=60)
    if r.status_code >= 300:   # image could not be fetched: post a link instead
        r = requests.post(f"{API}/{PAGE}/feed", data={"message": cap, "link": f"{SITE}/notice/{n['slug']}/", "access_token": TOKEN}, timeout=60)
    ok = r.status_code < 300
    err = "" if ok else str((r.json() if r.headers.get("content-type", "").startswith("application/json") else {}).get("error", {}).get("message", r.status_code))[:140]
    log.append(f"{n['id']} -> {r.status_code} {'ok' if ok else 'failed: ' + err}")
    return ok


def main():
    if not (PAGE and TOKEN):
        log.append("FB_PAGE_ID / FB_PAGE_TOKEN secrets are not set; nothing posted.")
        return finish({})
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    if "--status" in sys.argv:
        r = requests.get(f"{API}/{PAGE}", params={"fields": "name,fan_count,followers_count", "access_token": TOKEN}, timeout=30)
        j = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        log.append(f"page -> {r.status_code} {j.get('name') or j.get('error', {}).get('message', '')[:140]}"
                   + (f" · followers {j.get('followers_count')}" if j.get("followers_count") is not None else ""))
        return finish(state)
    notices = [json.loads(f.read_text()) for f in (ROOT / "data/notices").glob("*.json")]
    live = [n for n in notices if n.get("status") == "approved" and n.get("slug")]
    done = set(state.get("posted", []))
    if "--test" in sys.argv:
        today = dt.date.today().isoformat()
        jobs = sorted([n for n in live if (n.get("card") or {}).get("type", "Job") == "Job" and n["id"] not in done
                       and ((n.get("card") or {}).get("last_date") or "9999") >= today], key=lambda n: n.get("published_at") or "", reverse=True)
        if jobs and post(jobs[0]):
            done.add(jobs[0]["id"]); state["posted"] = sorted(done | set(state.get("posted", [])))
        elif not jobs:
            log.append("test: no open job notice left to post")
        return finish(state)
    if "posted" not in state:
        state["posted"] = sorted(n["id"] for n in live)
        log.append(f"first run: recorded {len(live)} existing notices, posted none")
        return finish(state)
    now = dt.datetime.now(dt.timezone.utc)
    day = now.astimezone(IST).date().isoformat()
    if state.get("day") != day:
        state["day"], state["today"] = day, 0
    sent = 0
    for n in sorted([n for n in live if n["id"] not in done], key=lambda n: n.get("published_at") or ""):
        pub = n.get("published_at") or n.get("first_seen") or ""
        try:
            age_h = (now - dt.datetime.fromisoformat(pub.replace("Z", "+00:00"))).total_seconds() / 3600
        except ValueError:
            age_h = 999
        if age_h > FRESH_H:
            done.add(n["id"]); continue
        if sent >= PER_RUN or state["today"] >= PER_DAY:
            break
        if post(n):
            done.add(n["id"]); sent += 1; state["today"] += 1
        time.sleep(10)
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
