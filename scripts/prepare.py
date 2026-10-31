"""Step 2 of the pipeline: turn each raw notice into a clean listing card and publish it.

AUTO-PUBLISH (default, AUTO_PUBLISH=1): every listable card from an official board goes live straight away.
A closed GitHub issue labelled "auto-published" is kept as the record; adding the "reject" label to it takes the
notice down, and commenting a fix ("last date is 30 Nov") then adding "approve" rewrites it with your fix.
Only cards the AI itself marks "low" confidence wait for a human (label "review").


For every notice with status "pending_review" and no card yet:
  1. AI writes a card: clean English + Hindi titles, category, last date, short summaries, key facts,
     and whether the notice is worth listing at all (refund notices, scribe guidelines etc. are skipped).
  2. A GitHub issue is opened with the card, so it can be approved from the GitHub phone app
     by adding the "approve" (or "reject") label.
Nothing here publishes anything: publish.py does that after approval.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import time

import requests

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from extract import _json_from, _providers, _throttle  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
NOTICES = ROOT / "data" / "notices"
TEXT = ROOT / "data" / "text"
REPO = os.environ.get("GITHUB_REPOSITORY", "rklokesh/sarkarichart")
TYPES = ["Job", "Result", "Admit card", "Answer key", "Update", "Admission"]

PROMPT = """You prepare Indian government job notices for a calm, trustworthy listing site read by job aspirants.
Read the notice (title, board, link, extracted fields, PDF text) and answer with ONE JSON object:
{
 "list": true|false,            // false for things aspirants do not need on the main list: refund/chargeback notes,
                                 // scribe guidelines, booklets, tenders, internal circulars, court cases, duplicate links
 "skip_reason": "short reason if list is false, else empty",
 "type": "Job"|"Result"|"Admit card"|"Answer key"|"Update"|"Admission",
                                 // Job = new vacancy / application open / corrigendum to an open recruitment
                                 // Update = news about a recruitment that is not a new opening: document verification,
                                 //   exam date/schedule, objections, syllabus, vacancy change after applications closed
                                 // Admission = entrance or course exam (JEE, NEET, CUET, NIFT, SWAYAM), not a job
 "title_en": "Short clear title, max 70 chars, e.g. 'SSC Junior Engineer Examination 2026' or
              'UPPSC Assistant Teacher (Advt A-5/E-1/2025) final result'. No 'Download', no file sizes, no numbering.",
 "title_hi": "The same title in natural Hindi (Devanagari only, no English words; numbers as digits)",
 "posts": "post name(s), short",
 "vacancies": number or null,
 "last_date": "YYYY-MM-DD or null (last date to apply; only for Job)",
 "exam_date": "YYYY-MM-DD or null",
 "summary_en": "1-2 plain sentences: what this is and what the reader should do",
 "summary_hi": "same in Hindi (Devanagari only)",
 "confidence": "high"|"medium"|"low"   // how sure you are about type, title and dates
}
Use only facts present in the notice. Never invent dates or numbers; use null when unsure."""


def ai_card(n: dict) -> tuple[dict | None, str]:
    text = ""
    p = TEXT / f"{n['id']}.txt"
    if p.exists():
        text = p.read_text(errors="ignore")[:7000]
    fields = {k: v.get("value") for k, v in (n.get("fields") or {}).items() if isinstance(v, dict)}
    user = json.dumps({"board": n.get("org"), "title_on_board": n.get("title"), "link": n.get("url"),
                       "guessed_kind": n.get("kind"), "extracted": fields}, ensure_ascii=False) + "\n\nPDF TEXT:\n" + text
    reasons = []
    for prov in _providers():
        headers = {"Authorization": f"Bearer {prov['key']}", "Content-Type": "application/json", **prov.get("headers", {})}
        body = {"model": prov["model"], "temperature": 0, "response_format": {"type": "json_object"},
                "messages": [{"role": "system", "content": PROMPT}, {"role": "user", "content": user}]}
        r = None
        for wait in (0, 15, 45):
            if wait:
                time.sleep(wait)
            _throttle()
            try:
                r = requests.post(prov["url"], timeout=90, headers=headers, json=body)
            except requests.RequestException as e:
                reasons.append(f"{prov['name']}:{type(e).__name__}")
                r = None
                continue
            if r.status_code not in (429, 500, 502, 503):
                break
        if r is None or r.status_code != 200:
            reasons.append(f"{prov['name']}:{getattr(r, 'status_code', 'err')}")
            continue
        try:
            card = _json_from(r.json()["choices"][0]["message"]["content"])
        except Exception:  # noqa: BLE001
            reasons.append(f"{prov['name']}:bad-json")
            continue
        if card.get("type") not in TYPES:
            card["type"] = "Job" if (n.get("kind") == "notification") else "Result"
            card["confidence"] = "low"
        card["provider"] = prov["name"]
        return card, prov["name"]
    return None, ",".join(reasons) or "no-provider"


def gh(method: str, path: str, **kw):
    tok = os.environ.get("GITHUB_TOKEN")
    if not tok:
        return None
    r = requests.request(method, f"https://api.github.com/repos/{REPO}{path}", timeout=30,
                         headers={"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json"}, **kw)
    if r.status_code >= 300:
        print(f"  github {method} {path}: {r.status_code} {r.text[:200]}")
        return None
    return r.json()


AUTO = os.environ.get("AUTO_PUBLISH", "1") == "1"


def ensure_labels():
    for name, color, desc in (("review", "c9b38a", "Waiting for your OK"), ("approve", "2f7d4f", "Publish this notice"),
                              ("reject", "b23a1a", "Do not publish / take down"),
                              ("auto-published", "6f8fb0", "Went live automatically; add reject to take it down")):
        gh("POST", "/labels", json={"name": name, "color": color, "description": desc})


def issue_body(n: dict, c: dict, auto: bool = False) -> str:
    rows = [("Category", c.get("type")), ("Title (English)", c.get("title_en")), ("Title (Hindi)", c.get("title_hi")),
            ("Board", n.get("org")), ("Posts", c.get("posts")), ("Vacancies", c.get("vacancies")),
            ("Last date", c.get("last_date")), ("Exam date", c.get("exam_date")), ("AI confidence", c.get("confidence"))]
    t = "\n".join(f"| {k} | {v if v not in (None, '') else '—'} |" for k, v in rows)
    return (f"**{c.get('summary_en','')}**\n\n{c.get('summary_hi','')}\n\n| Field | Value |\n|---|---|\n{t}\n\n"
            f"Official notice: {n.get('url')}\nBoard page: {n.get('board_url')}\n"
            f"Board's own title: `{n.get('title')}`\n\n"
            + ("---\n**Already live on the site.** To take it down: add the **reject** label. "
               "To fix something: comment in plain words (e.g. `last date is 30 Nov`, `vacancies 1,200`), then add **approve**.\n"
               if auto else
               "---\nTo publish: add the **approve** label. To drop it: add **reject**. "
               "To fix a field, comment e.g. `title_en: ...` or `last_date: 2026-11-30` before approving.\n")
            +
            f"<!-- notice-id: {n['id']} -->")


def go_live(n: dict) -> None:
    n["status"] = "approved"
    n["auto_published"] = True
    n["published_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main():
    files = sorted(NOTICES.glob("*.json"))
    todo, waiting = [], []
    for f in files:
        n = json.loads(f.read_text())
        if n.get("status") == "pending_review" and not n.get("card"):
            todo.append((f, n))
        elif AUTO and n.get("status") == "in_review" and (n.get("card") or {}).get("confidence") != "low":
            waiting.append((f, n))
    print(f"{len(todo)} notices need a card; {len(waiting)} older review cards to auto-publish")
    if todo or waiting:
        ensure_labels()
    published = 0
    # tidy: every auto-published notice's issue must be closed and labelled `auto-published` (retries earlier failures)
    for f in files:
        n = json.loads(f.read_text())
        if n.get("auto_published") and n.get("issue") and not n.get("issue_tidy"):
            ensure_labels()
            a = gh("PUT", f"/issues/{n['issue']}/labels", json={"labels": ["auto-published"]})
            b = gh("PATCH", f"/issues/{n['issue']}", json={"state": "closed", "state_reason": "completed"})
            print(f"  tidy issue #{n['issue']}: labels {'ok' if a is not None else 'FAILED'}, close {'ok' if b else 'FAILED'}")
            if a is not None and b:
                n["issue_tidy"] = True
                f.write_text(json.dumps(n, ensure_ascii=False, indent=2, sort_keys=True))
    # tidy (2): any OPEN issue still labelled `review` whose notice is already live -> relabel + close
    import re as _re
    if AUTO:
        open_rev = gh("GET", "/issues", params={"state": "open", "labels": "review", "per_page": 100}) or []
        print(f"  open review issues: {len(open_rev)}")
        for iss in open_rev:
            m = _re.search(r"notice-id:\s*([0-9a-f]+)", iss.get("body") or "")
            nf = NOTICES / f"{m.group(1)}.json" if m else None
            if not (nf and nf.exists()):
                print(f"  #{iss['number']}: no notice file"); continue
            nn = json.loads(nf.read_text())
            if nn.get("status") == "approved":
                gh("DELETE", f"/issues/{iss['number']}/labels/review")
                gh("POST", f"/issues/{iss['number']}/labels", json={"labels": ["auto-published"]})
                r = gh("PATCH", f"/issues/{iss['number']}", json={"state": "closed", "state_reason": "completed"})
                print(f"  #{iss['number']}: live -> relabelled, closed={bool(r)}")
            else:
                print(f"  #{iss['number']}: notice status {nn.get('status')} (left for review)")
    # cards that were waiting for a human before auto-publish was switched on
    for f, n in waiting:
        go_live(n)
        published += 1
        if n.get("issue"):
            gh("POST", f"/issues/{n['issue']}/comments", json={"body": "Auto-published: live on the site now. "
               "Add **reject** to take it down, or comment a fix and add **approve**."})
            if gh("PUT", f"/issues/{n['issue']}/labels", json={"labels": ["auto-published"]}) is not None and \
                    gh("PATCH", f"/issues/{n['issue']}", json={"state": "closed", "state_reason": "completed"}):
                n["issue_tidy"] = True
        f.write_text(json.dumps(n, ensure_ascii=False, indent=2, sort_keys=True))
        print(f"  {n['id']}: auto-published (was waiting)")
    limit = int(os.environ.get("PREPARE_LIMIT", "40"))
    for f, n in todo[:limit]:
        card, how = ai_card(n)
        if not card:
            print(f"  {n['id']}: no card ({how})")
            continue
        n["card"] = card
        if not card.get("list", True):
            n["status"] = "skipped"
            print(f"  {n['id']}: skipped - {card.get('skip_reason')}")
        else:
            auto = AUTO and card.get("confidence") != "low"
            if auto:
                go_live(n)
                published += 1
            else:
                n["status"] = "in_review"
            iss = gh("POST", "/issues", json={
                "title": f"{n.get('org')} · {card.get('title_en')} ({card.get('type')})",
                "body": issue_body(n, card, auto), "labels": ["auto-published" if auto else "review"]})
            if iss:
                n["issue"] = iss["number"]
                if auto and gh("PATCH", f"/issues/{iss['number']}", json={"state": "closed", "state_reason": "completed"}):
                    n["issue_tidy"] = True
            print(f"  {n['id']}: {card.get('type')} | {card.get('title_en')} | {'LIVE' if auto else 'review'} | issue {n.get('issue')}")
        f.write_text(json.dumps(n, ensure_ascii=False, indent=2, sort_keys=True))
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as fh:
            fh.write(f"published={published}\n")
    print(f"{published} notices went live")


if __name__ == "__main__":
    main()
