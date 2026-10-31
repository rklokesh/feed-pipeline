"""Structured eligibility for job notices, used by "Am I eligible?" (site/elig.js).

  python scripts/elig.py tag   # after pages.py: AI turns each job notice's age/eligibility facts into numbers (batched)

Stored on the notice as n["elig"] = {"age_min": 18, "age_max": 27, "age_on": "2027-01-01",
  "relax": {"OBC": 3, "SC": 5, "ST": 5, "EWS": 0, "PwD": 10}, "qual": "graduate", "domicile": "Uttar Pradesh" | null}
Unknown facts stay null; the site then says "can't tell" rather than guessing. {} = checked, nothing usable.
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import re
import sys
import time

import requests

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from extract import _json_from, _providers, _throttle  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
NOTICES = ROOT / "data" / "notices"
TEXT = ROOT / "data" / "text"
QUALS = ["10th", "12th", "iti", "diploma", "graduate", "postgraduate"]

PROMPT = """You turn the age and education rules of an Indian government job notice into numbers. Facts only from the input.
For each notice return:
- age_min, age_max: integers in years for the general / unreserved category (null if not printed). If posts differ, use the
  widest range (lowest minimum, highest maximum).
- age_on: the date on which age is counted, YYYY-MM-DD (null if not printed).
- relax: upper-age relaxation in years per category that the notice prints: keys among OBC, SC, ST, EWS, PwD, ExSM, Women.
  Leave a key out if not printed. Use the plain relaxation for PwD (unreserved PwD), not combined ones.
- qual: the LOWEST education level among the posts: one of "10th","12th","iti","diploma","graduate","postgraduate"; null if not printed.
- domicile: state name if the posts are only for residents of one state, else null.
Answer with JSON: {"tags": [{"id": "...", "age_min": 18, "age_max": 27, "age_on": "2027-01-01", "relax": {"OBC": 3}, "qual": "graduate", "domicile": null}]}"""


LOG = []


def ai(user):
    LOG.append(f"providers: {[p['name'] for p in _providers()]}")
    for prov in _providers():
        headers = {"Authorization": f"Bearer {prov['key']}", "Content-Type": "application/json", **prov.get("headers", {})}
        body = {"model": prov["model"], "temperature": 0, "response_format": {"type": "json_object"},
                "messages": [{"role": "system", "content": PROMPT}, {"role": "user", "content": user}]}
        for wait in (0, 20, 60):
            if wait:
                time.sleep(wait)
            _throttle()
            try:
                r = requests.post(prov["url"], timeout=120, headers=headers, json=body)
            except requests.RequestException:
                continue
            LOG.append(f"{prov['name']}: HTTP {r.status_code} {r.text[:200]!r}" if r.status_code != 200 else f"{prov['name']}: HTTP 200")
            if r.status_code == 200:
                try:
                    return _json_from(r.json()["choices"][0]["message"]["content"])
                except Exception as e:  # noqa: BLE001
                    LOG.append(f"parse failed: {type(e).__name__}: {r.text[:300]!r}")
                    break
            if r.status_code not in (429, 500, 502, 503):
                break
    return None


def age_text(n) -> str:
    """The parts of the PDF that talk about age / relaxation / qualification (kept short for the free AI tier)."""
    p = TEXT / f"{n['id']}.txt"
    if not p.exists():
        return ""
    t = p.read_text(errors="ignore")
    out = []
    for m in re.finditer(r"(?i)(age|relaxation|qualification|domicile|आयु|छूट|योग्यता)", t):
        out.append(t[max(0, m.start() - 200): m.start() + 400])
        if len(out) >= 6:
            break
    return "\n...\n".join(out)[:3000]


def clean(t: dict) -> dict:
    def num(v):
        try:
            v = int(float(v))
            return v if 10 <= v <= 70 else None
        except (TypeError, ValueError):
            return None
    on = str(t.get("age_on") or "")[:10]
    try:
        dt.date.fromisoformat(on)
    except ValueError:
        on = None
    relax = {}
    raw = t.get("relax") if isinstance(t.get("relax"), dict) else {}
    for k, v in raw.items():
        try:
            v = int(float(v))
        except (TypeError, ValueError):
            continue
        if k in ("OBC", "SC", "ST", "EWS", "PwD", "ExSM", "Women") and 0 <= v <= 20:
            relax[k] = v
    out = {"age_min": num(t.get("age_min")), "age_max": num(t.get("age_max")), "age_on": on, "relax": relax,
           "qual": t.get("qual") if t.get("qual") in QUALS else None, "domicile": (str(t["domicile"])[:40] if t.get("domicile") else None)}
    if out["age_min"] and out["age_max"] and out["age_min"] > out["age_max"]:
        out["age_min"] = out["age_max"] = None
    return out


def sane(e: dict, n: dict) -> dict:
    """Drop an as-on date that cannot belong to this notice (e.g. a 2018 date quoted from an old rule)."""
    issued = (n.get("notice_date") or n.get("first_seen") or "")[:10]
    if e.get("age_on") and issued:
        if abs(int(e["age_on"][:4]) - int(issued[:4])) > 1:
            e["age_on"] = None
    return e


def tag():
    files = [(f, json.loads(f.read_text())) for f in sorted(NOTICES.glob("*.json"))]
    today = dt.date.today().isoformat()
    todo = [(f, n) for f, n in files if n.get("status") == "approved" and (n.get("card") or {}).get("type", "Job") == "Job"
            and "elig" not in n and n.get("page")]
    # open jobs first: they are the ones readers check
    todo.sort(key=lambda fn: str((fn[1].get("page") or {}).get("last_date") or "") >= today, reverse=True)
    if not todo:
        print("elig: nothing to tag")
        LOG.append("nothing to tag")
        return
    for i in range(0, len(todo), 8):
        batch = todo[i:i + 8]
        items = []
        for _, n in batch:
            pg = n.get("page") or {}
            items.append({"id": n["id"], "title": pg.get("h1_en"), "age_rows": pg.get("age"), "eligibility": pg.get("eligibility"),
                          "pdf_excerpts": age_text(n)})
        res = ai(json.dumps({"notices": items}, ensure_ascii=False))
        if isinstance(res, list):          # some answers come back as a bare list of tags
            res = {"tags": res}
        if not isinstance(res, dict):
            print("elig: AI unavailable, will continue next run")
            LOG.append("AI unavailable")
            return
        tags = res.get("tags") if isinstance(res.get("tags"), list) else []
        got = {t.get("id"): t for t in tags if isinstance(t, dict)}
        for f, n in batch:
            if n["id"] not in got:
                continue
            try:
                n["elig"] = sane(clean(got[n["id"]]), n)
            except Exception as e:  # noqa: BLE001 — one odd answer must never stop the run
                print(f"  elig: {n['id']} skipped ({type(e).__name__})")
                n["elig"] = {}
            f.write_text(json.dumps(n, ensure_ascii=False, indent=2, sort_keys=True))
        print(f"elig: tagged {len(batch)} job notices")
        if i >= 40:          # at most ~48 per run, so one run never uses up the free AI quota
            break


if __name__ == "__main__":
    try:
        tag()
    finally:   # a short trace of the last run, committed with the data (helps when CI logs can't be read)
        (ROOT / "data" / "debug-elig.txt").write_text(dt.datetime.utcnow().isoformat() + "\n" + "\n".join(LOG[-20:]) + "\n", encoding="utf-8")
