"""Daily health report: one comment on the pinned "Daily health report" issue (GitHub app notifies the owner).

Says: what went live in the last 24 h, what waits for review, which boards worked / found nothing / failed,
and whether the Mac mini (India boards) checked in recently.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib

import requests
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
REPO = os.environ.get("GITHUB_REPOSITORY", "rklokesh/sarkarichart")
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
NOW = dt.datetime.now(dt.timezone.utc)


def gh(method, path, **kw):
    r = requests.request(method, f"https://api.github.com/repos/{REPO}{path}", timeout=30,
                         headers={"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
                                  "Accept": "application/vnd.github+json"}, **kw)
    if r.status_code >= 300:
        print(method, path, r.status_code, r.text[:200])
        return None
    return r.json() if r.text else {}


def ts(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def ago(t):
    h = (NOW - t).total_seconds() / 3600
    return f"{int(h * 60)} min ago" if h < 1 else f"{h:.0f} h ago" if h < 48 else f"{h / 24:.0f} days ago"


def main():
    sources = yaml.safe_load((ROOT / "sources/sources.yaml").read_text())
    sources = sources["sources"] if isinstance(sources, dict) else sources
    health = json.loads((ROOT / "data/health.json").read_text())
    notices = [json.loads(f.read_text()) for f in (ROOT / "data/notices").glob("*.json")]

    live24 = [n for n in notices if n.get("status") == "approved" and ts(n.get("published_at")) and NOW - ts(n["published_at"]) < dt.timedelta(hours=24)]
    waiting = [n for n in notices if n.get("status") == "in_review"]
    total_live = sum(n.get("status") == "approved" for n in notices)

    ok, empty, bad = [], [], []
    india_last = None
    for s in sources:
        if not s.get("enabled", True):
            continue
        h = health.get(s["id"], {})
        name = f"{s.get('org')} ({s['id']})"
        last_ok = ts(h.get("last_ok"))
        if s.get("runner") == "india" and last_ok and (india_last is None or last_ok > india_last):
            india_last = last_ok
        if h.get("consecutive_failures"):
            bad.append(f"- {name}: failing {h['consecutive_failures']}x — {(h.get('last_error') or '')[-120:]}")
        elif not h:
            bad.append(f"- {name}: never checked")
        elif not h.get("last_links"):
            empty.append(name)
        else:
            ok.append(name)

    mac = ("✅ Mac mini checked in " + ago(india_last)) if india_last and NOW - india_last < dt.timedelta(hours=3) else \
          ("⚠️ Mac mini has NOT checked in for " + (ago(india_last) if india_last else "a long time") +
           " — is it on, awake and logged in? India boards are paused until it is.")
    day = NOW.astimezone(IST).strftime("%a %d %b %Y")
    lines = [f"## Daily health — {day}", "", mac, "",
             f"**Live on the site:** {total_live} notices · **went live in the last 24 h:** {len(live24)} · "
             f"**waiting for you (low-confidence):** {len(waiting)}", ""]
    if live24:
        lines += ["<details><summary>Went live in the last 24 h</summary>", ""] + \
                 [f"- {(n.get('card') or {}).get('type', '')}: {(n.get('card') or {}).get('title_en') or n.get('title')} (#{n.get('issue')})" for n in live24] + ["", "</details>", ""]
    if waiting:
        lines += ["**Please check:**"] + [f"- #{n.get('issue')} {(n.get('card') or {}).get('title_en')}" for n in waiting] + [""]
    lines += [f"**Boards working:** {len(ok)} · **reached but nothing found:** {len(empty)} · **failing:** {len(bad)}", ""]
    if bad:
        lines += ["**Failing boards:**"] + bad + [""]
    if empty:
        lines += ["**Nothing found (may need tuning):** " + ", ".join(empty), ""]
    body = "\n".join(lines)
    print(body)

    if not os.environ.get("GITHUB_TOKEN"):
        return
    gh("POST", "/labels", json={"name": "health", "color": "8a8a8a", "description": "Daily health report"})
    found = gh("GET", "/issues", params={"state": "open", "labels": "health", "per_page": 5}) or []
    if found:
        num = found[0]["number"]
    else:
        iss = gh("POST", "/issues", json={"title": "Daily health report", "labels": ["health"],
                                          "body": "One comment per day: what went live, what failed, whether the Mac mini is online. "
                                                  "Subscribe to this issue (or keep notifications on) to get it on your phone."})
        num = iss["number"]
    gh("POST", f"/issues/{num}/comments", json={"body": body})


if __name__ == "__main__":
    main()
