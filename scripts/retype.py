"""Keeps each tab honest. The AI sometimes files everything about a recruitment as "Job". After it answers, these plain rules
correct the type:
  Admission  - entrance / course exams (JEE, NEET, CUET, NIFT, SWAYAM ...): not govt jobs, shown only under All
  Update     - news about a recruitment that is not a new opening (document verification, exam dates, objections,
               correction window, syllabus, vacancy changes after applications closed): shown only under All
  Result     - "final result" notices filed as Job
Jobs keeps new openings and anything you can still apply for.

  python scripts/retype.py          # re-check every approved notice, report changes in reports/retype.txt
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
NOTICES = ROOT / "data" / "notices"

ADMISSION = re.compile(r"\b(JEE|NEET|CUET|NIFT|NIFTEE|SWAYAM|NCHM|CLAT|NCET|PTET|NIOS|Polytechnic Entrance|B\.?Ed\.? Entrance|"
                       r"Sainik School|JNVST|Navodaya Vidyalaya Selection Test|Entrance (Exam|Test|Examination))\b", re.I)
RESULT = re.compile(r"\bfinal result\b|\bresult notice\b|\bselect(ed|ion) list\b|\bmerit list\b", re.I)
STRONG = re.compile(r"\bDV\b|document verification|document submission|objection|exam (date|schedule|city)|revised dates|"
                    r"schedule notice|correction window|syllabus|exam pattern|willingness|re-?exam|interview (schedule|date|notice)|"
                    r"ineligible|rejected candidates", re.I)
WEAK = re.compile(r"corrigendum|amendment|amended|vacanc(y|ies) (reduction|revised|increased|update|amendment)|tentative vacanc|"
                  r"vacancies (increased|revised|reduced)|(exam|examination) notice|notice released", re.I)


def title(n):
    c, pg = n.get("card") or {}, n.get("page") or {}
    return " ".join(x for x in [pg.get("h1_en"), c.get("title_en"), n.get("title")] if x)


def last_ahead(n, today=None):
    c, pg = n.get("card") or {}, n.get("page") or {}
    v = str(pg.get("last_date") or c.get("last_date") or "")[:10]
    today = today or dt.date.today().isoformat()
    return bool(re.fullmatch(r"\d{4}-\d\d-\d\d", v)) and v >= today


def fix(n) -> str:
    """The type this notice should have."""
    c = n.get("card") or {}
    typ, t = c.get("type") or "Job", title(n)
    if ADMISSION.search(t):
        return "Admission"
    if typ == "Admission":                     # the AI sometimes files eligibility tests (UGC-NET, CTET) here:
        typ = "Job"                            # judge them by the job rules below
    if typ != "Job":
        return typ
    if RESULT.search(t):
        return "Result"
    if STRONG.search(t):
        return "Update"
    if WEAK.search(t) and not last_ahead(n):
        return "Update"
    return "Job"


def main():
    report = []
    for f in sorted(NOTICES.glob("*.json")):
        n = json.loads(f.read_text())
        c = n.get("card")
        if n.get("status") != "approved" or not c:
            continue
        new = fix(n)
        if new != c.get("type"):
            report.append(f"{c.get('type')} -> {new}: {title(n).split('  ')[0][:90]}")
            c["type"] = new
            f.write_text(json.dumps(n, ensure_ascii=False, indent=2, sort_keys=True))
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / "retype.txt").write_text("\n".join(report) + "\n")
    print(f"retype: {len(report)} changed")
    print("\n".join(report))


if __name__ == "__main__":
    main()
