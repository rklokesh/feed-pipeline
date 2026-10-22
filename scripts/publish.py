"""Step 3: act on your decision and rebuild the homepage list.

  python scripts/publish.py decide <issue-number> <approve|reject>
      Reads the issue (and any "field: value" correction comments), updates the notice file, closes the issue.
  python scripts/publish.py build
      Writes every approved notice into the homepage list (site/index.html, between the ITEMS markers).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import re
import sys

import requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
NOTICES = ROOT / "data" / "notices"
INDEX = ROOT / "site" / "index.html"
REPO = os.environ.get("GITHUB_REPOSITORY", "rklokesh/sarkarichart")
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
EDITABLE = {"title_en", "title_hi", "type", "last_date", "exam_date", "posts", "vacancies", "summary_en", "summary_hi"}
TYPES = {"job": "Job", "result": "Result", "admit card": "Admit card", "answer key": "Answer key"}
ORG_HI = {"NTA": "एनटीए", "SSC": "एसएससी", "UPPSC": "यूपीपीएससी", "BPSC": "बीपीएससी", "SBI": "एसबीआई", "IBPS": "आईबीपीएस",
          "ISRO": "इसरो", "UPSC": "यूपीएससी", "RRB": "आरआरबी", "LIC": "एलआईसी", "BSSC": "बीएसएससी", "UPSSSC": "यूपीएसएसएससी",
          "RPSC": "आरपीएससी", "MPPSC": "एमपीपीएससी", "DSSSB": "डीएसएसएसबी", "NCS": "एनसीएस"}


def gh(method, path, **kw):
    r = requests.request(method, f"https://api.github.com/repos/{REPO}{path}", timeout=30,
                         headers={"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
                                  "Accept": "application/vnd.github+json"}, **kw)
    r.raise_for_status()
    return r.json() if r.text else {}


def find_notice(issue: dict) -> tuple[pathlib.Path, dict] | None:
    m = re.search(r"notice-id:\s*([0-9a-f]+)", issue.get("body") or "")
    if not m:
        return None
    f = NOTICES / f"{m.group(1)}.json"
    return (f, json.loads(f.read_text())) if f.exists() else None


def corrections(number: int) -> dict:
    out = {}
    for c in gh("GET", f"/issues/{number}/comments"):
        for line in (c.get("body") or "").splitlines():
            m = re.match(r"\s*([a-z_]+)\s*:\s*(.+?)\s*$", line)
            if m and m.group(1) in EDITABLE:
                k, v = m.group(1), m.group(2)
                if k == "type":
                    v = TYPES.get(v.lower(), v)
                if v.lower() in ("none", "null", "-"):
                    v = None
                out[k] = v
    return out


def decide(number: int, action: str):
    issue = gh("GET", f"/issues/{number}")
    hit = find_notice(issue)
    if not hit:
        print("no notice id in issue"); return
    f, n = hit
    fixes = corrections(number)
    n.setdefault("card", {}).update(fixes)
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    if action == "approve":
        n["status"] = "approved"
        n["published_at"] = now.isoformat().replace("+00:00", "Z")
        msg = "Published. It will be on the site in about a minute." + (f" Corrections applied: {', '.join(fixes)}." if fixes else "")
    else:
        n["status"] = "rejected"
        msg = "Rejected: it will not be published."
    f.write_text(json.dumps(n, ensure_ascii=False, indent=2, sort_keys=True))
    gh("POST", f"/issues/{number}/comments", json={"body": msg})
    gh("PATCH", f"/issues/{number}", json={"state": "closed"})
    print(f"{n['id']}: {n['status']}")


def build():
    items = []
    for f in sorted(NOTICES.glob("*.json")):
        n = json.loads(f.read_text())
        if n.get("status") != "approved":
            continue
        c = n.get("card") or {}
        pub = n.get("published_at") or n.get("first_seen")
        posted = dt.datetime.fromisoformat(pub.replace("Z", "+00:00")).astimezone(IST).date().isoformat()
        it = {"type": c.get("type", "Job"), "title": c.get("title_en") or n.get("title"), "hi": c.get("title_hi") or c.get("title_en"),
              "org": n.get("org"), "posted": posted, "publishedAt": pub, "url": n.get("url"), "id": n["id"]}
        if it["type"] == "Job" and c.get("last_date"):
            it["last"] = c["last_date"]
        items.append(it)
    items.sort(key=lambda i: i["publishedAt"], reverse=True)
    html = INDEX.read_text(encoding="utf-8")
    if not items:
        print("no approved notices yet: homepage keeps its sample list"); return
    body = ",\n".join("    " + json.dumps(i, ensure_ascii=False) for i in items)
    html, k = re.subn(r"/\*ITEMS:START\*/.*?/\*ITEMS:END\*/", lambda m: "/*ITEMS:START*/\n" + body + "\n    /*ITEMS:END*/", html, flags=re.S)
    if k != 1:
        sys.exit("ITEMS markers not found in site/index.html")
    hi = dict(ORG_HI)
    html = re.sub(r"/\*ORGHI:START\*/.*?/\*ORGHI:END\*/", lambda m: "/*ORGHI:START*/" + json.dumps(hi, ensure_ascii=False) + "/*ORGHI:END*/", html, flags=re.S)
    INDEX.write_text(html, encoding="utf-8")
    print(f"homepage now lists {len(items)} approved notices")


if __name__ == "__main__":
    if sys.argv[1] == "decide":
        decide(int(sys.argv[2]), sys.argv[3])
    else:
        build()
