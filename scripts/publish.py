"""Step 3: act on your decision and rebuild the homepage list.

  python scripts/publish.py decide <issue-number> <approve|reject>
      Reads the issue (and any "field: value" correction comments), updates the notice file, closes the issue.
  python scripts/publish.py sweep
      Same, for every open issue labelled approve/reject (safe when you label many at once).
  python scripts/publish.py build
      Writes every approved notice into the homepage list (site/index.html, between the ITEMS markers).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import re
import shutil
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
          "RPSC": "आरपीएससी", "MPPSC": "एमपीपीएससी", "DSSSB": "डीएसएसएसबी", "NCS": "एनसीएस",
          "RRB Chandigarh": "आरआरबी चंडीगढ़", "RRB (unified portal)": "आरआरबी", "RBI": "आरबीआई", "NABARD": "नाबार्ड",
          "Indian Army": "भारतीय सेना", "Indian Navy": "भारतीय नौसेना", "Indian Air Force": "भारतीय वायुसेना",
          "Indian Coast Guard": "भारतीय तटरक्षक बल", "BSF": "बीएसएफ", "CRPF": "सीआरपीएफ", "ITBP": "आईटीबीपी", "CISF": "सीआईएसएफ", "India Post": "इंडिया पोस्ट",
          "DRDO": "डीआरडीओ", "RSSB Rajasthan": "आरएसएसबी राजस्थान", "MPESB": "एमपीईएसबी", "UKPSC": "यूकेपीएससी",
          "Employment News": "रोज़गार समाचार", "RRB": "आरआरबी", "UP Police": "यूपी पुलिस", "CSBC Bihar": "सीएसबीसी बिहार",
          "RRC Northern Railway": "आरआरसी उत्तर रेलवे", "RRC Western Railway": "आरआरसी पश्चिम रेलवे",
          "RRC Central Railway": "आरआरसी मध्य रेलवे", "CTET": "सीटेट", "KVS": "केवीएस",
          "WBPSC": "डब्ल्यूबीपीएससी", "HPSC": "एचपीएससी", "HSSC": "एचएसएससी", "MPSC": "एमपीएससी", "TNPSC": "टीएनपीएससी"}


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
        if n.get("status") == "approved":
            # already live (auto-published): re-write its page so your comments are applied; keep its place in the list
            n.pop("page", None)
        else:
            n["published_at"] = now.isoformat().replace("+00:00", "Z")
        n["status"] = "approved"
        msg = "Published. It will be on the site in about a minute." + (f" Corrections applied: {', '.join(fixes)}." if fixes else "")
    else:
        was_live = n.get("status") == "approved"
        n["status"] = "rejected"
        msg = "Taken down: it is no longer on the site." if was_live else "Rejected: it will not be published."
    f.write_text(json.dumps(n, ensure_ascii=False, indent=2, sort_keys=True))
    gh("POST", f"/issues/{number}/comments", json={"body": msg})
    gh("PATCH", f"/issues/{number}", json={"state": "closed"})
    print(f"{n['id']}: {n['status']}")


try:   # state of each board, for the Jobs tab filter (same list as the state pages)
    from hubs import STATES as STATE_BOARDS
except Exception:  # noqa: BLE001
    STATE_BOARDS = []


def build():
    items = []
    for f in sorted(NOTICES.glob("*.json")):
        n = json.loads(f.read_text())
        if n.get("status") != "approved":
            page = ROOT / "site" / "notice" / n["slug"] if n.get("slug") else None
            if page and page.is_dir():   # taken down: remove its page too
                shutil.rmtree(page)
                print(f"removed page {n['slug']}")
            continue
        c = n.get("card") or {}
        pub = n.get("published_at") or n.get("first_seen")
        # "Posted" = the date the board issued the notice (pages.py reads it from the PDF), never our publish date
        posted = n.get("notice_date") or dt.datetime.fromisoformat(n["first_seen"].replace("Z", "+00:00")).astimezone(IST).date().isoformat()
        it = {"type": c.get("type", "Job"), "title": c.get("title_en") or n.get("title"), "hi": c.get("title_hi") or c.get("title_en"),
              "org": n.get("org"), "posted": posted, "publishedAt": pub, "url": n.get("url"), "id": n["id"]}
        if n.get("slug") and (ROOT / "site" / "notice" / n["slug"] / "index.html").exists():
            it["url"], it["page"] = f"/notice/{n['slug']}/", True   # our own clean page (with PDF)
        if it["type"] == "Job" and c.get("last_date"):
            it["last"] = c["last_date"]
        sid = n.get("source_id") or ""
        for st_slug, _en, _hi, prefixes in STATE_BOARDS:
            if any(sid == p_ or sid.startswith(p_ + "-") for p_ in prefixes):
                it["st"] = st_slug
        if it["type"] == "Job" and n.get("qual"):
            it["q"] = n["qual"]
        el = n.get("elig") or {}
        if it["type"] == "Job" and (el.get("age_max") or el.get("age_min") or el.get("qual")):
            it["e"] = {k: v for k, v in {"min": el.get("age_min"), "max": el.get("age_max"), "on": el.get("age_on"), "relax": el.get("relax") or None,
                                         "qual": el.get("qual"), "dom": el.get("domicile")}.items() if v}
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


def sweep():
    """Handle every open review issue that already carries approve/reject, so bulk-labelling many at once never loses one."""
    for label in ("approve", "reject"):
        for iss in gh("GET", "/issues", params={"state": "open", "labels": label, "per_page": 100}):
            try:
                decide(iss["number"], label)
            except Exception as e:  # noqa: BLE001
                print(f"#{iss['number']}: {e}")


if __name__ == "__main__":
    if sys.argv[1] == "decide":
        decide(int(sys.argv[2]), sys.argv[3])
    elif sys.argv[1] == "sweep":
        sweep()
    else:
        build()
