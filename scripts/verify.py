"""Accuracy check: every date, vacancy count and fee shown on a notice page must appear in the official PDF text.

  python scripts/verify.py            # check all live notices; write reports/verify.txt
  python scripts/verify.py --act      # also act on new failures (run by prepare.yml after pages.py):
        1st failure  -> the page is written again from the PDF on the next run (n["rewrite"] = True)
        still wrong  -> the notice is held back (n["verify"]["held"] = True): publish.py leaves it off the site
                        and it is listed in the daily health report
A fact we cannot check (no readable PDF text) is never a failure: we only flag numbers the PDF clearly does not contain.
"""
from __future__ import annotations

import calendar
import datetime as dt
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from extract import looks_garbled  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
NOTICES = ROOT / "data" / "notices"
TEXT = ROOT / "data" / "text"
DEV = str.maketrans("०१२३४५६७८९", "0123456789")
HI_MONTHS = ["जनवरी", "फरवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"]
HI_ALT = {"फ़रवरी": "फरवरी", "सितम्बर": "सितंबर", "अक्तूबर": "अक्टूबर", "अक्टूम्बर": "अक्टूबर", "नवम्बर": "नवंबर", "दिसम्बर": "दिसंबर"}


def norm(t: str) -> str:
    t = t.translate(DEV)
    t = re.sub(r"(?<=\d)[oO](?=\d|\b)|(?<=\b)[oO](?=\d)", "0", t)     # scanned text: 2O26 -> 2026
    for a, b in HI_ALT.items():
        t = t.replace(a, b)
    t = re.sub(r"(?<=\d),(?=\d{2,3}\b)", "", t)          # 7,680 -> 7680 ; 1,26,000 -> 126000
    t = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", t, flags=re.I)
    return re.sub(r"\s+", " ", t).lower()


def date_forms(d: dt.date) -> list[str]:
    D, M, Y, y = d.day, d.month, d.year, d.year % 100
    mon, month = calendar.month_abbr[M].lower(), calendar.month_name[M].lower()
    out = []
    for dd in {f"{D}", f"{D:02d}"}:
        for mm in {f"{M}", f"{M:02d}"}:
            for yy in (f"{Y}", f"{y:02d}"):
                for sep in "/.-":
                    out.append(rf"\b{dd}\s?{re.escape(sep)}\s?{mm}\s?{re.escape(sep)}\s?{yy}\b")
        for mo in {mon, month, "sept" if M == 9 else mon}:
            out.append(rf"\b{dd}[\s\-.,]*{mo}\.?[\s\-.,']*{Y}")
            out.append(rf"\b{mo}\.?\s*{dd},?\s*{Y}")
        out.append(rf"\b{dd}\s*{HI_MONTHS[M - 1]},?\s*{Y}")
    out.append(rf"\b{Y}-{M:02d}-{D:02d}\b")
    out.append(rf"(?<!\d){D:02d}{M:02d}{Y}(?!\d)")                      # 12072026
    return out


def has_date(text: str, iso: str) -> bool:
    try:
        d = dt.date.fromisoformat(iso[:10])
    except ValueError:
        return True          # not a precise date: nothing to check
    if any(re.search(p, text) for p in date_forms(d)):
        return True
    # ranges and lists: "17th to 18th November, 2026", "2, 3, 4, 5 and 6 June 2026", "14-16/11/2026"
    months = {calendar.month_abbr[d.month].lower(), calendar.month_name[d.month].lower(), HI_MONTHS[d.month - 1]}
    for mo in months:
        if re.search(rf"(?<!\d){d.day}\s*{mo}\b", text):                 # "28th November," (year printed elsewhere)
            return True
        for m in re.finditer(rf"{mo}\.?[\s,'-]*{d.year}", text):
            if re.search(rf"(?<!\d){d.day}(?!\d)", text[max(0, m.start() - 60):m.start()]):
                return True
    for m in re.finditer(rf"[/.-]\s?0?{d.month}\s?[/.-]\s?(?:{d.year}|{d.year % 100:02d})\b", text):
        if re.search(rf"(?<!\d)0?{d.day}(?!\d)", text[max(0, m.start() - 25):m.start() + 1]):
            return True
    return False


def month_only(text: str, iso: str) -> bool:
    d = dt.date.fromisoformat(iso)
    names = (calendar.month_name[d.month].lower(), calendar.month_abbr[d.month].lower(), HI_MONTHS[d.month - 1])
    return not has_date(text, iso) and any(re.search(rf"{m}\.?,?\s*{d.year}", text) for m in names)


def has_number(text: str, v) -> bool:
    if not re.fullmatch(r"\s*(₹|rs\.?)?\s*[\d,]+(\.\d+)?\s*(/-)?\s*", str(v), re.I):
        return True          # "As per CEN 03/2026", "Not specified": not a number to check
    s = re.sub(r"[^\d]", "", str(v).split(".")[0])
    if not s or int(s) < 10:   # tiny numbers appear everywhere; not worth checking
        return True
    return re.search(rf"(?<!\d){s}(?!\d)", text) is not None


MON = {m.lower(): i for i, m in enumerate(calendar.month_abbr) if m}


def parse_shown_date(v: str) -> str | None:
    """'11 Aug 2026' -> 2026-08-11 (only exact day dates; 'September 2026 (Tentative)' is skipped)."""
    m = re.match(r"^\s*(\d{1,2})\s+([A-Za-z]{3})[a-z]*\.?\s+(\d{4})\s*$", v or "")
    if not m or m.group(2).lower() not in MON:
        return None
    try:
        return dt.date(int(m.group(3)), MON[m.group(2).lower()], int(m.group(1))).isoformat()
    except ValueError:
        return None


def facts(n: dict) -> list[tuple[str, str, str]]:
    """(kind, label, value) shown on the page that must be in the PDF."""
    pg, c = n.get("page") or {}, n.get("card") or {}
    out = []
    for k, label in (("last_date", "Last date"), ("apply_start", "Apply from"), ("exam_date", "Exam date")):
        v = str(pg.get(k) or "")[:10]
        if re.fullmatch(r"\d{4}-\d\d-\d\d", v):
            out.append(("date", label, v))
    for r in pg.get("dates") or []:
        if isinstance(r, dict):
            iso = parse_shown_date(r.get("value_en"))
            if iso and ("date", r.get("label_en") or "Date", iso) not in out and all(o[2] != iso for o in out):
                out.append(("date", r.get("label_en") or "Date", iso))
    tot = c.get("vacancies")
    for v in pg.get("vacancies") or []:
        if isinstance(v, dict) and v.get("total"):
            out.append(("number", f"Vacancies: {v.get('post_en') or ''}"[:60], str(v["total"])))
    if tot and all(str(tot) != o[2] for o in out):
        out.append(("number", "Total vacancies", str(tot)))
    for f in pg.get("fees") or []:
        if isinstance(f, dict) and f.get("amount"):
            out.append(("number", f"Fee: {f.get('cat_en') or ''}"[:60], str(f["amount"])))
    return out


COMMON = set("the of and to in for is be on by with as are at will date exam post posts notice candidates online "
             "application last examination result list from this that has have was were its which may shall all".split())
KRUTI = re.compile(r"\b(fnukad|vkosnu|foKkiu|ijh\{kk|vk;ksx|izdk'ku|vfUre|frfFk|lfpo|vH;fFkZ;ksa)\b")


def readable(raw: str) -> bool:
    """Plain English or Hindi text (not an old font that turns Hindi into ASCII junk)."""
    if looks_garbled(raw) or len(KRUTI.findall(raw)) >= 2 or raw.count("(cid:") > 20:
        return False
    dev = len(re.findall(r"[\u0900-\u097F]", raw)) / max(len(raw), 1)
    words = re.findall(r"[A-Za-z]{2,}", raw.lower())
    eng = sum(w in COMMON for w in words) / max(len(words), 1)
    return dev > 0.25 or eng > 0.08


# the notice's own date (taken from the board's list, not always printed in the PDF) is not checked
OWN_DATE = re.compile(r"notice|notification|publication|publish|declar|releas|issue|upload|corrigendum date|amended|result date|final result", re.I)
CRITICAL = re.compile(r"^(Last date|Apply from|Total vacancies|Vacancies)", re.I)


def check(n: dict) -> dict:
    p = TEXT / f"{n['id']}.txt"
    raw = p.read_text(errors="ignore") if p.exists() else ""
    kind = str((n.get("pdf") or {}).get("text_kind") or "")
    if len(raw.strip()) < 300 or kind == "not-pdf" or not readable(raw):
        return {"checked": False, "why": "no readable PDF text"}
    partial = len(raw) >= 19_000 or "ocr" in kind      # only the first pages were kept / read
    text = norm(raw)
    missing = []
    for k, label, v in facts(n):
        if k == "date" and OWN_DATE.search(label):
            continue
        if k == "date" and v.endswith("-01") and month_only(text, v):
            missing.append(f"{label}: shown as {v} but the PDF gives only the month")
            continue
        if partial and k == "number":
            continue
        ok = has_date(text, v) if k == "date" else has_number(text, v)
        if not ok:
            missing.append(f"{label}: {v}")
    return {"checked": True, "missing": missing, "n": len(facts(n))}


def main(act: bool):
    today = dt.date.today().isoformat()
    lines, bad, held, total = [], 0, 0, 0
    for f in sorted(NOTICES.glob("*.json")):
        n = json.loads(f.read_text())
        if n.get("status") not in ("approved", "held") or not n.get("page"):
            continue
        total += 1
        r = check(n)
        v = n.get("verify") or {}
        changed = False
        if r["checked"] and r["missing"]:
            bad += 1
            title = (n.get("page") or {}).get("h1_en") or n.get("title")
            critical = any(CRITICAL.match(m) for m in r["missing"])
            if act and v.get("missing") != r["missing"]:
                if not v.get("tries"):
                    n["rewrite"] = True                    # pages.py writes it again from the PDF
                    v = {"tries": 1, "missing": r["missing"], "at": today}
                else:
                    v = {**v, "missing": r["missing"], "at": today, "held": critical}
                    if critical:
                        n["status"] = "held"               # off the site, Telegram, sitemap until fixed
                changed = True
            tag = " HELD" if n.get("status") == "held" else ""
            held += bool(tag)
            lines.append(f"{n['id']} {n.get('org')} | {title[:70]}{tag}\n    not in the PDF: " + "; ".join(r["missing"]))
        elif v and r["checked"]:
            v, changed = {}, True                          # passes now: release anything held
            if n.get("status") == "held":
                n["status"] = "approved"
        if act and changed:
            if v:
                n["verify"] = v
            else:
                n.pop("verify", None)
            f.write_text(json.dumps(n, ensure_ascii=False, indent=2, sort_keys=True))
    head = f"{today}: {total} live notices checked against their PDFs; {bad} with something the PDF does not show; {held} held back"
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / "verify.txt").write_text(head + "\n\n" + "\n".join(lines) + "\n")
    print(head)
    print("\n".join(lines))


if __name__ == "__main__":
    main("--act" in sys.argv)
