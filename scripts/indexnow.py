"""Tell Bing / Yandex (IndexNow) about new and changed pages right away, instead of waiting for a crawl.
Sends the notice pages published in the last 2 days plus the homepage and landing pages. Run after publish.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import re

import requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE_URL = os.environ.get("SITE_URL", "https://sarkarichart.com")
KEY = "bbee6455312a62ea6c8536bfeed360de"


def main():
    if "pages.dev" in SITE_URL:
        return print("indexnow: skipped (not on the real domain)")
    s = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
    cut = (dt.datetime.utcnow() - dt.timedelta(days=2)).strftime("%Y-%m-%dT%H:%M")
    urls = [SITE_URL + "/"]
    for m in re.finditer(r'"publishedAt": "([^"]+)", "url": "(/notice/[^"]+)"', s):
        if m.group(1) >= cut:
            urls.append(SITE_URL + m.group(2))
            if (ROOT / "site" / "hi" / m.group(2).strip("/") / "index.html").exists():
                urls.append(SITE_URL + "/hi" + m.group(2))
    flag = ROOT / "data" / "indexnow-hi-sent.txt"   # first run after the Hindi pages launched: announce all of them once
    hi_dir = ROOT / "site" / "hi" / "notice"
    if hi_dir.exists() and not flag.exists():
        urls += [f"{SITE_URL}/hi/notice/{d.name}/" for d in sorted(hi_dir.iterdir()) if (d / "index.html").exists()]
        flag.write_text(dt.datetime.utcnow().isoformat() + "\n")
    urls += [f"{SITE_URL}/{d.name}/" for d in sorted((ROOT / "site").iterdir()) if d.is_dir() and (d.name.endswith("-jobs") or d.name in ("admit-card", "result", "answer-key"))]
    body = {"host": SITE_URL.split("//")[1], "key": KEY, "keyLocation": f"{SITE_URL}/{KEY}.txt", "urlList": urls[:10000]}
    try:
        r = requests.post("https://api.indexnow.org/indexnow", json=body, timeout=20)
        print(f"indexnow: {len(urls)} urls -> {r.status_code}")
    except Exception as e:  # noqa: BLE001 - never block publishing
        print(f"indexnow: failed ({e})")


if __name__ == "__main__":
    main()
