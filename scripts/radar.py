"""Coverage radar: which recruiting boards appear on a big aggregator that we do not watch yet?

Reads ONLY the headline list on the aggregator's front page (respecting its robots.txt), pulls out the board
names ("AIIMS Recruitment 2026 ..." -> "AIIMS"), and lists the boards we don't cover. Nothing from the aggregator
is ever published: each gap is a hint to add that board's OFFICIAL site to sources/sources.yaml.
Output: data/radar.json (read by health.py for the daily report).
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import pathlib
import re
import sys
import urllib.robotparser

import requests
import yaml
from bs4 import BeautifulSoup

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITES = ["https://www.freejobalert.com/"]
UA = "SarkariChartRadar/0.1 (+https://sarkarichart.com/bot; coverage check, headlines only)"
KIND = re.compile(r"\b(recruitment|result|admit card|answer key|notification|vacancy|exam date|syllabus|call letter|hall ticket|bharti)\b", re.I)
STOP = {"latest", "new", "govt", "government", "jobs", "job", "online", "apply", "2024", "2025", "2026", "2027", "today", "free", "sarkari"}


def ours() -> list[str]:
    d = yaml.safe_load((ROOT / "sources/sources.yaml").read_text())
    d = d["sources"] if isinstance(d, dict) else d
    names = set()
    for s in d:
        names.add(s.get("org", "").lower())
        names.add(s["id"].split("-")[0].lower())
    return [n for n in names if n]


def board_of(title: str) -> str | None:
    m = KIND.search(title)
    if not m or m.start() < 2:
        return None
    head = re.sub(r"[^A-Za-z0-9&().\- ]", " ", title[: m.start()]).strip()
    words = [w for w in head.split() if w.lower() not in STOP]
    if not words:
        return None
    return " ".join(words[:4])[:40]


def main():
    covered = ours()
    found = collections.Counter()
    notes = []
    for site in SITES:
        rp = urllib.robotparser.RobotFileParser(site.rstrip("/") + "/robots.txt")
        try:
            rp.read()
        except Exception as e:  # noqa: BLE001
            notes.append(f"{site}: robots.txt unreadable ({e}); skipped"); continue
        if not rp.can_fetch(UA, site):
            notes.append(f"{site}: robots.txt disallows; skipped"); continue
        try:
            r = requests.get(site, headers={"User-Agent": UA}, timeout=30)
            r.raise_for_status()
        except Exception as e:  # noqa: BLE001
            notes.append(f"{site}: {e}"[:200]); continue
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a"):
            b = board_of(" ".join(a.get_text(" ").split()))
            if b:
                found[b] += 1
    gaps = []
    for b, n in found.most_common():
        bl = b.lower()
        if any(c and (c in bl or bl.split()[0] == c) for c in covered):
            continue
        gaps.append({"board": b, "mentions": n})
    out = {"checked": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "sites": SITES,
           "boards_seen": len(found), "not_covered": gaps[:40], "notes": notes}
    (ROOT / "data/radar.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(json.dumps(out, ensure_ascii=False, indent=2)[:3000])


if __name__ == "__main__":
    sys.exit(main())
