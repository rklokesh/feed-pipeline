"""Joins notices that are the same official notice picked up twice (a board re-uploads a file under a new name,
lists it in two places, or CISF changes its links on every visit). Each repeat is marked status "merged" (so no
page, list row, sitemap entry or Telegram post uses it) and its old address redirects to the page that stays.

Only pairs a person has checked go in MERGES: titles alone are not enough (UPPSC and RPSC publish different
results under near-identical titles). Run: python3 scripts/dedupe.py
"""
from __future__ import annotations

import json
import pathlib
import shutil

ROOT = pathlib.Path(__file__).resolve().parent.parent
NOTICES = ROOT / "data" / "notices"
SITE = ROOT / "site"
START, END = "# --- merged notices (scripts/dedupe.py) ---", "# --- end merged notices ---"

# repeat id -> the notice that stays (checked 8 Nov 2026)
MERGES = {
    # CISF CBE notice for CT (Fire), CT (TM), CT (Driver & DCPO) 2024: same notice, new link on every visit
    "cde7332fcdd7": "5336059fb5d0", "71ebc9f52b2b": "5336059fb5d0", "66a6ce1bc90d": "5336059fb5d0",
    "cb40b897f573": "5336059fb5d0", "994310f0f67e": "5336059fb5d0",
    # RRB CEN 09/2026: the 4 Nov and 5 Nov uploads of the same 59-page notification
    "89dd20949a71": "c8927256a847",
    # RRC Northern Railway Scouts & Guides 2026: same notification under two file names
    "022beceeac01": "9eefa7b1371a",
    # MPPSC Assistant Professor Physics 2024 candidature rejection: same notice uploaded twice
    "c8379a67d824": "bcd362bb418c",
    # UPSC CSE Main 2026 written result: roll-number list and the same list with names
    "390c2f1de761": "1dcff634dd12",
    # UPPSC Assistant Professor Microbiology result (Advt D-1/E-1/2026): same list in two sections
    "b2fbec797b22": "823ff34426da",
    # NTA UGC-NET December 2026 last date extended (27 Oct): same notice posted twice
    "df2c17cf988f": "cf2f3d144293",
}


def main() -> None:
    redirects, changed = [], 0
    for drop, keep in MERGES.items():
        f, k = NOTICES / f"{drop}.json", NOTICES / f"{keep}.json"
        if not f.exists() or not k.exists():
            continue
        n, kept = json.loads(f.read_text()), json.loads(k.read_text())
        if kept.get("status") != "approved" or not kept.get("slug"):
            continue
        if n.get("status") != "merged":
            n["status_before_merge"], n["status"], n["merged_into"] = n.get("status"), "merged", keep
            f.write_text(json.dumps(n, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            changed += 1
        if n.get("slug") and n["slug"] != kept["slug"]:
            redirects.append((n["slug"], kept["slug"]))
            for old in (SITE / "notice" / n["slug"], SITE / "hi" / "notice" / n["slug"]):
                if old.is_dir():
                    shutil.rmtree(old)
    # pages whose address changed when their text was rewritten (old address -> current one; null = no longer live)
    ren = ROOT / "data" / "renamed.json"
    live = {json.loads(x.read_text()).get("slug") for x in NOTICES.glob("*.json")}
    for a, b in (json.loads(ren.read_text()).items() if ren.exists() else []):
        if a in live:   # the old address belongs to a notice again: leave it alone
            continue
        if b and (SITE / "notice" / b / "index.html").exists():
            redirects.append((a, b))
        for old in (SITE / "notice" / a, SITE / "hi" / "notice" / a):
            if old.is_dir() and a != b:
                shutil.rmtree(old)
    rf = SITE / "_redirects"
    text = rf.read_text() if rf.exists() else ""
    if START in text:
        text = text[:text.index(START)].rstrip("\n") + "\n" + text[text.index(END) + len(END):].lstrip("\n")
    block = [START] + [f"{L}/notice/{a}{s} {L}/notice/{b}/ 301" for a, b in sorted(redirects) for L in ("", "/hi") for s in ("", "/", "/*")] + [END]
    rf.write_text(text.rstrip("\n") + "\n" + "\n".join(block) + "\n")
    print(f"dedupe: {changed} newly merged, {len(redirects)} old addresses redirect")


if __name__ == "__main__":
    main()
