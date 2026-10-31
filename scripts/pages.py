"""Step 4: a clean SarkariChart page for every approved notice (English + Hindi), at /notice/<slug>/.

For each approved notice without a page (or with --all):
  1. Read the official PDF text, the review card, and your review comments on GitHub (plain words are fine:
     "vacancies missing, it's 1,200" / "exam is on 14 Dec"). Your comments win over the PDF.
  2. AI writes the page facts in both languages: summary, key details, fees, dates, links. Facts only from the notice.
  3. Render templates/notice.html into site/notice/<slug>/index.html.
publish.py build then links the homepage row to this page.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import os
import pathlib
import re
import sys
import time
import urllib.parse

import requests

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from extract import _json_from, _providers, _throttle  # noqa: E402
from share_card import share_data  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
NOTICES = ROOT / "data" / "notices"
TEXT = ROOT / "data" / "text"
SITE = ROOT / "site"
TEMPLATE = ROOT / "templates" / "notice.html"
REPO = os.environ.get("GITHUB_REPOSITORY", "rklokesh/sarkarichart")
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
MONTHS_HI = ["जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर", "अक्तूबर", "नवंबर", "दिसंबर"]
TYPE_LABEL = {"Job": ("Jobs", "नौकरियाँ"), "Result": ("Results", "रिज़ल्ट"), "Admit card": ("Admit cards", "एडमिट कार्ड"),
              "Answer key": ("Answer keys", "आंसर की")}

PROMPT = """You write the facts section of a calm, trustworthy Indian government-job notice page, in English AND Hindi.
Input: the board, our review card, the official PDF text, and EDITOR NOTES from the site owner.
EDITOR NOTES are corrections or additions by a human who checked the notice: apply them and prefer them over the PDF.
Use only facts from the notice or the editor notes. Never invent dates, numbers, fees or links. Leave out what is unknown.
Be thorough: a reader should not need to open the PDF for the basics. Detail comes from the notice's facts, never from filler or hype;
general guidance (documents, mistakes, what happens next) must stay true for this kind of notice. Empty lists for anything that does not apply.
Hindi must be natural Devanagari with no English words (proper nouns transliterated, numbers as digits, ₹ for money).
Answer with ONE JSON object:
{
 "h1_en": "page title in the words people search, max 65 chars: board short name + post/exam + search word + year + one hook,
           e.g. 'RRB Station Master Recruitment 2026 – Apply Online for 1,215 Posts', 'SSC GD Admit Card 2026 Out – Exam City Slip Link',
           'UPSC CSE Result 2026 – Cut Off and Final List'. Search words: Recruitment, Notification, Vacancy, Online Form, Admit Card,
           Answer Key, Result, Cut Off, Merit List, Last Date Extended. No 'expected', no hype.",
 "h1_hi": "same in Hindi with Hindi search words (भर्ती, वैकेंसी, एडमिट कार्ड, आंसर की, रिज़ल्ट, कट ऑफ, अंतिम तिथि)",
 "summary_en": "2-3 plain sentences: what this is, who it is for, what to do next",
 "summary_hi": "same in Hindi",
 "status_en": "one short status line for non-job notices, e.g. 'Final result declared' / 'District information slip released' / 'Answer key released, objections open till 30 Oct 2026'; for jobs: empty",
 "status_hi": "same in Hindi",
 "conducted_by_en": "full name of the organisation (short form in brackets)", "conducted_by_hi": "same in Hindi",
 "rows": [ {"label_en": "", "label_hi": "", "value_en": "", "value_hi": ""} ],
     // KEY DETAILS at a glance (short; the full dates/age/eligibility go in their own sections below). Ordered, only rows you know: Posts, Total vacancies, Apply online (start to last date), Last date for fee,
     // Exam date, Educational qualification, Age limit (with as-on date), Selection process, Advertisement number,
     // for results/admit cards: how to download, roll-number/district info, etc. Values short; dates like '14 Dec 2026'.
 "fees": [ {"cat_en": "General / OBC", "cat_hi": "सामान्य / अन्य पिछड़ा वर्ग", "amount": "₹100"} ],
 "intro_en": "4-6 sentence introduction for the page: which board, which posts/exam and year, how many vacancies, the key dates, and who should read it. Plain, factual, no hype.",
 "intro_hi": "same in Hindi",
 "dates": [ {"label_en": "Online application starts", "label_hi": "", "value_en": "03 Oct 2026", "value_hi": ""} ],
     // every stage printed in the notice, in order: notification, apply start, last date, fee last date, correction window,
     // admit card, exam, answer key, result. Only those printed.
 "age": [ {"label_en": "Minimum age", "label_hi": "", "value_en": "18 years", "value_hi": ""} ],
     // minimum, maximum, as-on date, and each category relaxation printed in the notice
 "vacancies": [ {"post_en": "Constable (GD)", "post_hi": "", "total": "126", "detail_en": "UR 52, OBC 34, SC 19, ST 9, EWS 12", "detail_hi": ""} ],
 "eligibility": [ {"label_en": "Education", "label_hi": "", "value_en": "", "value_hi": ""} ],   // education, experience, physical standards, nationality
 "selection_en": ["step 1", "step 2"], "selection_hi": ["", ""],   // selection process stages, in order
 "how_en": ["step 1", "step 2"], "how_hi": ["", ""],                // how to apply / how to download, short imperative steps
 "extra": [ {"label_en": "", "label_hi": "", "value_en": "", "value_hi": ""} ],   // other useful facts: exam pattern, salary/pay level, documents needed, centres
 "who_en": ["who should read/apply, one short line each, e.g. 'Graduates aged 18-30 who want a railway job'"], "who_hi": [""],
 "not_en": ["who cannot apply / common reasons people are not eligible, from the notice"], "not_hi": [""],
 "changes": [ {"what_en": "Last date to apply", "what_hi": "", "old_en": "30 Oct 2026", "old_hi": "", "new_en": "15 Nov 2026", "new_hi": ""} ],
     // ONLY for corrigendum / extension / postponement / revised notices: each changed item with old and new value
 "salary": [ {"label_en": "Pay level", "label_hi": "", "value_en": "Level 6 (₹35,400–1,12,400)", "value_hi": ""} ],   // only if printed
 "exam_pattern": [ {"part_en": "General Awareness", "part_hi": "", "questions": "25", "marks": "50", "time": ""} ],
     // subjects/papers with questions, marks, time; add a row 'Negative marking' in part_en with the rule in marks if printed
 "physical": [ {"label_en": "Height (male)", "label_hi": "", "value_en": "170 cm", "value_hi": ""} ],   // police/defence physical standards
 "documents_en": ["documents to keep ready / carry"], "documents_hi": [""],
 "mistakes_en": ["common mistakes to avoid for THIS notice, practical, from its instructions"], "mistakes_hi": [""],
 "explain": [ {"q_en": "What is <exam/post>?", "a_en": "2-3 plain sentences for a first-time reader", "q_hi": "", "a_hi": ""} ],   // 1-2 items
 "after_en": ["what happens next after this notice: next stage, document verification, joining"], "after_hi": [""],
 "checklist_en": ["final checklist before applying/downloading, short imperative lines"], "checklist_hi": [""],
 "faq": [ {"q_en": "What is the last date to apply for ...?", "a_en": "...", "q_hi": "", "a_hi": ""} ],
     // 8-12 questions people actually search for THIS notice (last date, fee, age, eligibility, how to apply/download, vacancies),
     // each answered in 1-2 sentences from the notice. Skip questions the notice does not answer.
 "notice_date": "YYYY-MM-DD: the date the board issued THIS notice (e.g. 'Dated: 08.10.2026', 'Date of publication', the date
                 printed at the top or bottom of the notice / press note). Not the exam date, not the last date. null if not printed.",
 "apply_start": "YYYY-MM-DD or null", "last_date": "YYYY-MM-DD or null (last date to apply)", "exam_date": "YYYY-MM-DD or null",
 "apply_url": "official application URL or null", "official_site": "official website URL or null",
 "hindi_notice_url": "URL of the official Hindi version of this notice if it is printed in the text, else null",
 "video_url": "URL of an official how-to-apply / instructions video if it is printed in the text, else null",
 "share_card": {"kind": "job | admit | result | answer | corr (corrigendum, date extended, exam postponed) | sched (DV / interview schedule)",
                "line_en": "post or exam name for the share image, max 32 chars, e.g. 'Station Master', 'CHSL Tier-II Exam'",
                "line_hi": "same in Hindi", "headline_en": "max 22 chars, e.g. 'Recruitment 2026', 'Admit Card 2026', 'Last Date Extended'",
                "headline_hi": "same in Hindi", "posts": "total vacancies as a number for job notices, else null"},
 "changes_from_notes": "one line: what you changed because of the editor notes, or empty"
}"""


def gh_comments(issue: int | None) -> list[str]:
    tok = os.environ.get("GITHUB_TOKEN")
    if not tok or not issue:
        return []
    try:
        r = requests.get(f"https://api.github.com/repos/{REPO}/issues/{issue}/comments", timeout=30,
                         headers={"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json"})
        if r.status_code != 200:
            return []
        return [c["body"].strip() for c in r.json()
                if c.get("user", {}).get("type") != "Bot" and (c.get("body") or "").strip()]
    except requests.RequestException:
        return []


def ai_page(n: dict, notes: list[str]) -> dict | None:
    text = ""
    p = TEXT / f"{n['id']}.txt"
    if p.exists():
        text = p.read_text(errors="ignore")[:12000]
    fields = {k: v.get("value") for k, v in (n.get("fields") or {}).items() if isinstance(v, dict)}
    user = json.dumps({"board": n.get("org"), "board_title": n.get("title"), "notice_pdf": n.get("url"),
                       "board_page": n.get("board_url"), "card": n.get("card"), "extracted": fields,
                       "editor_notes": notes}, ensure_ascii=False) + "\n\nOFFICIAL PDF TEXT:\n" + text
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
                r = requests.post(prov["url"], timeout=120, headers=headers, json=body)
            except requests.RequestException:
                r = None
                continue
            if r.status_code not in (429, 500, 502, 503):
                break
        if r is None or r.status_code != 200:
            continue
        try:
            page = _json_from(r.json()["choices"][0]["message"]["content"])
        except Exception:  # noqa: BLE001
            continue
        page["provider"] = prov["name"]
        return page
    return None


def slugify(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:64].rstrip("-") or "notice"


def unique_slug(n: dict, taken: dict) -> str:
    if n.get("slug"):
        return n["slug"]
    base = slugify((n.get("card") or {}).get("title_en") or n.get("title") or n["id"])
    slug = base if taken.get(base, n["id"]) == n["id"] else f"{base}-{n['id'][:4]}"
    taken[slug] = n["id"]
    return slug


def d_en(iso: str) -> str:
    d = dt.date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%b')} {d.year}"


def d_hi(iso: str) -> str:
    d = dt.date.fromisoformat(iso)
    return f"{d.day} {MONTHS_HI[d.month - 1]} {d.year}"


def host(url: str) -> str:
    try:
        return urllib.parse.urlparse(url).netloc.replace("www.", "")
    except Exception:  # noqa: BLE001
        return url


def js(s) -> str:
    return json.dumps("" if s is None else str(s), ensure_ascii=False)


def valid_date(v) -> str | None:
    try:
        return dt.date.fromisoformat(str(v)[:10]).isoformat() if v else None
    except ValueError:
        return None


def official_date(n: dict) -> str:
    """The date the board issued the notice; falls back to the day our watcher first saw it on the board's site."""
    seen = dt.datetime.fromisoformat(n["first_seen"].replace("Z", "+00:00")).astimezone(IST).date()
    pg, c = n.get("page") or {}, n.get("card") or {}
    d = valid_date(pg.get("notice_date"))
    if d:
        dd = dt.date.fromisoformat(d)
        if seen - dt.timedelta(days=800) <= dd <= seen:   # issued before we saw it; old notices keep their old date
            return d
    # No date printed: a notice whose last date had already passed when we first saw it is old, not new —
    # it was issued on or before that last date (e.g. a board added to our watch list later). Never show it as "New".
    last = valid_date(pg.get("last_date") or c.get("last_date"))
    if last and dt.date.fromisoformat(last) < seen:
        return last
    return seen.isoformat()


SITE_URL = os.environ.get("SITE_URL", "https://sarkarichart.pages.dev")   # change to https://sarkarichart.com at launch
CAT_SLUG = {"Job": "jobs", "Result": "results", "Admit card": "admit-cards", "Answer key": "answer-keys"}


def render(n: dict, slug: str, related: list | None = None, exam_groups: dict | None = None) -> str:
    c, pg = n.get("card") or {}, n.get("page") or {}
    typ = c.get("type", "Job")
    en, hi = {}, {}
    en["title"] = en["h1"] = pg.get("h1_en") or c.get("title_en") or n.get("title")
    hi["title"] = hi["h1"] = pg.get("h1_hi") or c.get("title_hi") or en["h1"]
    en["crumbType"], hi["crumbType"] = TYPE_LABEL.get(typ, TYPE_LABEL["Job"])
    en["org"] = n.get("org") or ""
    hi["org"] = {"NTA": "एनटीए", "SSC": "एसएससी", "UPPSC": "यूपीपीएससी", "BPSC": "बीपीएससी", "SBI": "एसबीआई", "IBPS": "आईबीपीएस",
                 "ISRO": "इसरो", "UPSC": "यूपीएससी", "RRB": "आरआरबी"}.get(en["org"], en["org"])
    en["summary"], hi["summary"] = pg.get("summary_en") or c.get("summary_en") or "", pg.get("summary_hi") or c.get("summary_hi") or ""
    en["statusV"] = pg.get("status_en") or {"Result": "Result declared", "Admit card": "Admit card released",
                                              "Answer key": "Answer key released"}.get(typ, "Notice published")
    hi["statusV"] = pg.get("status_hi") or {"Result": "रिज़ल्ट जारी", "Admit card": "एडमिट कार्ड जारी",
                                              "Answer key": "आंसर की जारी"}.get(typ, "सूचना जारी")
    last = valid_date(pg.get("last_date") or c.get("last_date")) if typ == "Job" else None
    if last:
        en["lastDate"], hi["lastDate"] = f"Last date {d_en(last)}", f"अंतिम तिथि {d_hi(last)}"
    en["key"], hi["key"] = "At a glance", "एक नज़र में"
    en["fee"], hi["fee"] = "Application fee", "आवेदन शुल्क"
    en["links"], hi["links"] = "Official links", "आधिकारिक लिंक"
    en["lNotice"], hi["lNotice"] = "Official notice", "आधिकारिक सूचना"
    en["lApply"], hi["lApply"] = "Apply online", "ऑनलाइन आवेदन"
    en["lSite"], hi["lSite"] = "Official website", "आधिकारिक वेबसाइट"
    en["lHindi"], hi["lHindi"] = "Official notice in Hindi", "आधिकारिक सूचना (हिंदी)"
    en["lVideo"], hi["lVideo"] = "Official how-to video", "आधिकारिक वीडियो"
    en["by"], hi["by"] = "Conducted by", "आयोजक"
    en["byV"] = pg.get("conducted_by_en") or en["org"]
    hi["byV"] = pg.get("conducted_by_hi") or hi["org"]
    checked = dt.datetime.fromisoformat((n.get("published_at") or n.get("first_seen")).replace("Z", "+00:00")).astimezone(IST).date().isoformat()
    en["checked"] = (f"Details are taken from the official notice. Checked on {d_en(checked)}. "
                     "If anything here differs from the official notice, the official notice is correct.")
    hi["checked"] = (f"यह जानकारी आधिकारिक सूचना से ली गई है। {d_hi(checked)} को जाँची गई। "
                     "यहाँ दी गई कोई जानकारी आधिकारिक सूचना से अलग हो, तो आधिकारिक सूचना को ही सही मानें।")

    posted = official_date(n)
    en["postedL"], hi["postedL"] = "Notice date", "सूचना की तिथि"
    en["postedV"], hi["postedV"] = d_en(posted), d_hi(posted)
    rows = [("by", "byV"), ("postedL", "postedV")]
    for k, r in enumerate(pg.get("rows") or []):
        if not (r.get("label_en") and r.get("value_en")):
            continue
        en[f"r{k}l"], en[f"r{k}v"] = r["label_en"], r["value_en"]
        hi[f"r{k}l"], hi[f"r{k}v"] = r.get("label_hi") or r["label_en"], r.get("value_hi") or r["value_en"]
        rows.append((f"r{k}l", f"r{k}v"))
    # The essentials always appear At a glance when the notice gives them, even if the AI left them out of its rows:
    # total posts (with the category split), minimum qualification, selection stages.
    labels = " ".join(str(r.get("label_en") or "").lower() for r in (pg.get("rows") or []) if isinstance(r, dict))
    vac = [v for v in (pg.get("vacancies") or []) if isinstance(v, dict)]
    nums = [re.sub(r"[^0-9]", "", str(v.get("total") or "")) for v in vac]
    total = sum(int(x) for x in nums if x) if vac and all(nums) else None
    total = total or (c.get("vacancies") if isinstance(c.get("vacancies"), int) and c.get("vacancies") > 0 else None)
    if total and not re.search(r"vacanc|total post|no\.? of post|number of post", labels):
        split_en = vac[0].get("detail_en") if len(vac) == 1 and vac[0].get("detail_en") else ""
        split_hi = vac[0].get("detail_hi") if len(vac) == 1 and vac[0].get("detail_hi") else split_en
        en["gTot"], hi["gTot"] = "Total vacancies", "कुल पद"
        en["gTotV"], hi["gTotV"] = f"{total:,}" + (f" ({split_en})" if split_en else ""), f"{total:,}" + (f" ({split_hi})" if split_hi else "")
        rows.insert(2, ("gTot", "gTotV"))
    QN = {"10th": ("10th pass", "10वीं पास"), "12th": ("12th pass", "12वीं पास"), "iti": ("ITI", "आईटीआई"), "diploma": ("Diploma", "डिप्लोमा"),
          "graduate": ("Graduate (any degree, see notice)", "स्नातक (सूचना देखें)"), "postgraduate": ("Post graduate", "स्नातकोत्तर")}
    edu = next((e for e in (pg.get("eligibility") or []) if isinstance(e, dict) and re.search(r"educat|qualif", str(e.get("label_en")), re.I) and e.get("value_en")), None)
    if not re.search(r"qualif|educat", labels):
        if edu:
            en["gQ"], hi["gQ"] = "Qualification", "योग्यता"
            en["gQV"], hi["gQV"] = edu["value_en"], edu.get("value_hi") or edu["value_en"]
            rows.append(("gQ", "gQV"))
        elif (n.get("elig") or {}).get("qual") or (n.get("qual") or []):
            q = (n.get("elig") or {}).get("qual") or n["qual"][0]
            if q in QN:
                en["gQ"], hi["gQ"] = "Minimum qualification", "न्यूनतम योग्यता"
                en["gQV"], hi["gQV"] = QN[q]
                rows.append(("gQ", "gQV"))
    sel_en = [str(x).strip() for x in (pg.get("selection_en") or []) if str(x).strip()]
    sel_hi = [str(x).strip() for x in (pg.get("selection_hi") or []) if str(x).strip()]
    if sel_en and not re.search(r"selection", labels):
        en["gSel"], hi["gSel"] = "Selection process", "चयन प्रक्रिया"
        short = lambda xs: " → ".join(re.sub(r"\s*[:(].*$", "", x)[:40] for x in xs[:6])
        en["gSelV"], hi["gSelV"] = short(sel_en), short(sel_hi) if len(sel_hi) == len(sel_en) else short(sel_en)
        rows.append(("gSel", "gSelV"))
    fees = []
    for k, f in enumerate(pg.get("fees") or []):
        if f.get("cat_en") and f.get("amount"):
            en[f"f{k}"], hi[f"f{k}"] = f["cat_en"], f.get("cat_hi") or f["cat_en"]
            fees.append((f"f{k}", html.escape(str(f["amount"]))))

    links = [("lNotice", n.get("url"))]
    if pg.get("apply_url"):
        links.append(("lApply", pg["apply_url"]))
    site = pg.get("official_site") or n.get("board_url")
    if site:
        links.append(("lSite", site))
    # extra official links: shown only when the exact link is printed in the official text (never an AI guess)
    src_text = ""
    tp = TEXT / f"{n['id']}.txt"
    if tp.exists():
        src_text = tp.read_text(errors="ignore")
    for key, field in (("lHindi", "hindi_notice_url"), ("lVideo", "video_url")):
        u = str(pg.get(field) or "").strip()
        if u.startswith("http") and u.split("://", 1)[1].rstrip("/") in src_text:
            links.append((key, u))

    esc = html.escape
    # "Am I eligible?" row (filled in the browser by /elig.js from the reader's own details; nothing is sent anywhere)
    el, elig_row = n.get("elig") or {}, ""
    if typ == "Job" and (el.get("age_max") or el.get("age_min") or el.get("qual")):
        e = {k: v for k, v in {"min": el.get("age_min"), "max": el.get("age_max"), "on": el.get("age_on"), "relax": el.get("relax") or None,
                               "qual": el.get("qual"), "dom": el.get("domicile")}.items() if v}
        en["eligL"], hi["eligL"] = "Are you eligible?", "क्या आप योग्य हैं?"
        elig_row = f'      <div class="r"><span data-t="eligL">Are you eligible?</span><span class="v" id="elig" data-e="{esc(json.dumps(e, ensure_ascii=False))}"></span></div>\n'
    from share_card import board as _board
    logo_key = _board(n.get("source_id", ""))[0]
    logo_img = (f'<img class="olg" src="/org/{logo_key}.webp" width="64" height="64" alt="{esc(en["byV"])} logo" decoding="async">'
                if logo_key and (SITE / "org" / f"{logo_key}.webp").exists() else "")
    src_host = host(n.get("board_url") or site or n.get("url") or "")   # the board's own site, not a PDF mirror (e.g. cloudfront)
    en["metaV"] = f"Updated {d_en(checked)}" + (f" · Source: {src_host}" if src_host else "")
    hi["metaV"] = f"अपडेट {d_hi(checked)}" + (f" · स्रोत: {src_host}" if src_host else "")
    exam_g = (exam_groups or {}).get(((n.get("exam") or {}).get("key")) or "")
    main = [f'''    <div class="title">
      <nav class="crumb" aria-label="Breadcrumb"><a href="/?cat={CAT_SLUG.get(typ, "jobs")}" data-t="crumbType">{esc(en["crumbType"])}</a><span class="sep" aria-hidden="true">/</span><span class="here" aria-current="page" data-t="org">{esc(en["org"])}</span></nav>
      <h1 data-t="h1">{esc(en["h1"])}</h1>
      <p class="meta g" data-t="metaV">{esc(en["metaV"])}</p>
      <p class="status"><span id="state">{esc(en["statusV"])}</span><span id="left"></span><span id="views" class="g" hidden></span></p>
      {f'<p class="lead" data-t="summary">{esc(en["summary"])}</p>' if en["summary"] else ""}
      <img class="ogimg" id="ogimg" src="/notice/{slug}/og.png" data-en="/notice/{slug}/og.png" data-hi="/notice/{slug}/og-hi.png" width="1200" height="675" alt="{esc(en["h1"])} — summary card" decoding="async" onerror="this.hidden=true">
      <script>(function(){{var i=document.getElementById("ogimg");function s(){{var h=document.documentElement.lang==="hi";var u=i.dataset[h?"hi":"en"];if(i.getAttribute("src")!==u){{i.hidden=false;i.src=u;}}}}s();new MutationObserver(s).observe(document.documentElement,{{attributes:true,attributeFilter:["lang"]}});}})();</script>
    </div>''',
            '    <section class="kv glance" id="glance" data-t-aria="key">\n      <div class="h" data-t="key">At a glance</div>\n' +
            "".join(f'      <div class="r"><span data-t="{lk}">{esc(en[lk])}</span><span class="v" data-t="{vk}">{esc(en[vk])}</span></div>\n'
                    for lk, vk in rows) + elig_row + "    </section>"]
    def fee_section():
        if not fees:
            return
        toc.append(("fee", "fee"))
        main.append('    <section class="kv" id="fee" data-t-aria="fee">\n      <div class="h" data-t="fee">Application fee</div>\n' +
                    "".join(f'      <div class="r"><span data-t="{k}">{esc(en[k])}</span><span class="v num">{amt}</span></div>\n' for k, amt in fees) +
                    "    </section>")
    S = lambda v: "" if v is None else (", ".join(S(x) for x in v) if isinstance(v, list) else str(v)).strip()

    toc = []

    def sec_kv(key, label_en, label_hi, items):
        """items: (label_en, label_hi, value_en, value_hi); returns a table-like section"""
        items = [tuple(S(y) for y in x) for x in items]
        items = [x for x in items if x[0] and x[2]]
        if not items:
            return
        en[key], hi[key] = label_en, label_hi
        body = ""
        for k, (le, lh, ve, vh) in enumerate(items):
            en[f"{key}{k}l"], hi[f"{key}{k}l"] = le, lh or le
            en[f"{key}{k}v"], hi[f"{key}{k}v"] = ve, vh or ve
            body += f'      <div class="r"><span data-t="{key}{k}l">{esc(le)}</span><span class="v" data-t="{key}{k}v">{esc(ve)}</span></div>\n'
        toc.append((key, key))
        main.append(f'    <section class="kv" id="{key}" data-t-aria="{key}">\n      <div class="h" data-t="{key}">{esc(label_en)}</div>\n{body}    </section>')

    def sec_list(key, label_en, label_hi, items_en, items_hi, ordered=True):
        items_en = [S(x) for x in (items_en if isinstance(items_en, list) else [items_en] if items_en else [])]
        items_hi = [S(x) for x in (items_hi if isinstance(items_hi, list) else [])]
        items = [(e, (items_hi[k] if k < len(items_hi) and items_hi[k] else e)) for k, e in enumerate(items_en) if e]
        if not items:
            return
        en[key], hi[key] = label_en, label_hi
        lis = ""
        for k, (e, h) in enumerate(items):
            en[f"{key}{k}"], hi[f"{key}{k}"] = e, h
            lis += f'<li data-t="{key}{k}">{esc(e)}</li>'
        toc.append((key, key))
        tag = "ol" if ordered else "ul"
        main.append(f'    <section class="kv" id="{key}" data-t-aria="{key}">\n      <div class="h" data-t="{key}">{esc(label_en)}</div>\n      <{tag} class="steps{"" if ordered else " dots"}">{lis}</{tag}>\n    </section>')

    g = lambda k: [x for x in (pg.get(k) or []) if isinstance(x, dict)] if isinstance(pg.get(k), list) else []
    kv4 = lambda k: [(d.get("label_en"), d.get("label_hi"), d.get("value_en"), d.get("value_hi")) for d in g(k)]
    if S(pg.get("intro_en")):
        pg["intro_en"], pg["intro_hi"] = S(pg.get("intro_en")), S(pg.get("intro_hi"))
        en["aboutH"], hi["aboutH"] = "About this notice", "इस सूचना के बारे में"
        en["intro"], hi["intro"] = pg["intro_en"], pg.get("intro_hi") or pg["intro_en"]
        toc.append(("about", "aboutH"))
        main.append('    <section class="kv" id="about" data-t-aria="aboutH">\n      <div class="h" data-t="aboutH">About this notice</div>\n'
                    f'      <p class="p" data-t="intro">{esc(en["intro"])}</p>\n    </section>')
    ch = [(d.get("what_en"), d.get("what_hi"), f"{S(d.get('old_en')) or '—'} → {S(d.get('new_en'))}",
           f"{S(d.get('old_hi') or d.get('old_en')) or '—'} → {S(d.get('new_hi') or d.get('new_en'))}") for d in g("changes") if S(d.get("new_en"))]
    sec_kv("chgH", "What changed", "क्या बदला", ch)
    sec_list("whoH", "Who should read this", "यह किसके लिए है", pg.get("who_en"), pg.get("who_hi"), ordered=False)
    sec_list("notH", "Who cannot apply", "कौन आवेदन नहीं कर सकता", pg.get("not_en"), pg.get("not_hi"), ordered=False)
    sec_kv("datesH", "Important dates", "महत्वपूर्ण तिथियाँ", kv4("dates"))
    fee_section()
    sec_kv("ageH", "Age limit", "आयु सीमा", kv4("age"))
    vac = [(v.get("post_en"), v.get("post_hi"), " · ".join(x for x in [S(v.get("total")), S(v.get("detail_en"))] if x),
            " · ".join(x for x in [S(v.get("total")), S(v.get("detail_hi") or v.get("detail_en"))] if x)) for v in g("vacancies")]
    nums = [re.fullmatch(r"[\d,]+", S(v.get("total"))) for v in g("vacancies")]
    if len(nums) > 1 and all(nums):
        tot = f'{sum(int(m.group(0).replace(",", "")) for m in nums):,}'
        vac.append(("Total", "कुल", tot, tot))
    sec_kv("vacH", "Vacancy details", "रिक्तियों का विवरण", vac)
    sec_kv("eligH", "Eligibility", "पात्रता", kv4("eligibility"))
    sec_kv("physH", "Physical standards", "शारीरिक मानक", kv4("physical"))
    sec_kv("payH", "Salary and pay level", "वेतन और पे लेवल", kv4("salary"))
    pat = [d for d in g("exam_pattern") if S(d.get("part_en"))]
    if pat:
        en["patH"], hi["patH"] = "Exam pattern", "परीक्षा पैटर्न"
        en["patC1"], hi["patC1"] = "Part / subject", "भाग / विषय"
        en["patC2"], hi["patC2"] = "Questions", "प्रश्न"
        en["patC3"], hi["patC3"] = "Marks", "अंक"
        en["patC4"], hi["patC4"] = "Time", "समय"
        has_t = any(S(d.get("time")) for d in pat)
        rows_h = ""
        for k, d in enumerate(pat):
            en[f"pat{k}"], hi[f"pat{k}"] = S(d.get("part_en")), S(d.get("part_hi")) or S(d.get("part_en"))
            rows_h += (f'<tr><td data-t="pat{k}">{esc(en[f"pat{k}"])}</td><td class="num">{esc(S(d.get("questions")))}</td>'
                       f'<td class="num">{esc(S(d.get("marks")))}</td>' + (f'<td>{esc(S(d.get("time")))}</td>' if has_t else "") + "</tr>")
        toc.append(("patH", "patH"))
        main.append('    <section class="kv" id="patH" data-t-aria="patH">\n      <div class="h" data-t="patH">Exam pattern</div>\n'
                    '      <div class="tw"><table class="tbl"><thead><tr><th data-t="patC1">Part / subject</th><th data-t="patC2">Questions</th><th data-t="patC3">Marks</th>'
                    + ('<th data-t="patC4">Time</th>' if has_t else "") + f'</tr></thead><tbody>{rows_h}</tbody></table></div>\n    </section>')
    sec_list("selH", "Selection process", "चयन प्रक्रिया", pg.get("selection_en"), pg.get("selection_hi"))
    sec_list("howH", "How to apply" if typ == "Job" else "How to download", "आवेदन कैसे करें" if typ == "Job" else "कैसे डाउनलोड करें", pg.get("how_en"), pg.get("how_hi"))
    sec_list("docH", "Documents to keep ready", "ज़रूरी दस्तावेज़", pg.get("documents_en"), pg.get("documents_hi"), ordered=False)
    sec_list("mistH", "Common mistakes to avoid", "इन गलतियों से बचें", pg.get("mistakes_en"), pg.get("mistakes_hi"), ordered=False)
    exp = [{k: S(v) for k, v in q.items()} for q in g("explain")]
    exp = [q for q in exp if q.get("q_en") and q.get("a_en")][:2]
    if exp:
        en["expH"], hi["expH"] = "Good to know", "जानने योग्य"
        body_e = ""
        for k, q in enumerate(exp):
            en[f"eq{k}"], hi[f"eq{k}"] = q["q_en"], q.get("q_hi") or q["q_en"]
            en[f"ea{k}"], hi[f"ea{k}"] = q["a_en"], q.get("a_hi") or q["a_en"]
            body_e += f'      <div class="qa"><h3 data-t="eq{k}">{esc(q["q_en"])}</h3><p data-t="ea{k}">{esc(q["a_en"])}</p></div>\n'
        toc.append(("expH", "expH"))
        main.append(f'    <section class="kv faq" id="expH" data-t-aria="expH">\n      <div class="h" data-t="expH">Good to know</div>\n{body_e}    </section>')
    sec_list("aftH", "What happens next", "आगे क्या होगा", pg.get("after_en"), pg.get("after_hi"))
    sec_kv("extraH", "Other details", "अन्य जानकारी", kv4("extra"))
    toc.append(("links", "links"))
    main.append('    <section class="kv" id="links" data-t-aria="links">\n      <div class="h" data-t="links">Official links</div>\n' +
                "".join(f'      <a class="r" href="{esc(u)}" target="_blank" rel="noopener"><span data-t="{k}">{esc(en[k])}</span><span class="v">{esc(host(u))}</span></a>\n'
                        for k, u in links if u) + "    </section>")
    faq = [{k: S(v) for k, v in q.items()} for q in g("faq")]
    faq = [q for q in faq if q.get("q_en") and q.get("a_en")][:12]
    if faq:
        en["faqH"], hi["faqH"] = "Frequently asked questions", "अक्सर पूछे जाने वाले सवाल"
        body = ""
        for k, q in enumerate(faq):
            en[f"q{k}"], hi[f"q{k}"] = q["q_en"], q.get("q_hi") or q["q_en"]
            en[f"a{k}"], hi[f"a{k}"] = q["a_en"], q.get("a_hi") or q["a_en"]
            body += f'      <div class="qa"><h3 data-t="q{k}">{esc(q["q_en"])}</h3><p data-t="a{k}">{esc(q["a_en"])}</p></div>\n'
        toc.append(("faq", "faqH"))
        main.append(f'    <section class="kv faq" id="faq" data-t-aria="faqH">\n      <div class="h" data-t="faqH">Frequently asked questions</div>\n{body}    </section>')
    sec_list("chkH", "Final checklist", "अंतिम चेकलिस्ट", pg.get("checklist_en"), pg.get("checklist_hi"), ordered=False)
    if S(pg.get("intro_hi")) or S(pg.get("summary_hi")):
        # for readers on the English page who are more at home in Hindi; hidden when the page is already in Hindi
        hs = " ".join(x for x in [S(pg.get("summary_hi")), S(pg.get("intro_hi"))] if x)
        main.append(f'    <section class="kv hisum" lang="hi">\n      <div class="h">हिंदी में सारांश</div>\n      <p class="p">{esc(hs)}</p>\n    </section>')
    if len(toc) >= 4:
        en["tocH"], hi["tocH"] = "On this page", "इस पेज पर"
        items = "".join(f'<li><a href="#{a_}" data-t="{k_}">{esc(en[k_])}</a></li>' for a_, k_ in toc)
        main.insert(2, f'    <details class="toc"><summary data-t="tocH">On this page</summary><ol>{items}</ol></details>')
    others = [x for x in (exam_g["items"] if exam_g else []) if x["id"] != n["id"]]
    if others:   # every other official update for the same exam, newest first (replaces separate exam pages)
        from exams import stage as _stage
        en["exH"], hi["exH"] = f'All updates for {exam_g["name_en"]}', f'{exam_g["name_hi"] or exam_g["name_en"]} के सभी अपडेट'
        body = ""
        for k, x in enumerate(others[:12]):
            xe, xh = _stage(x)
            xc, xp = x.get("card") or {}, x.get("page") or {}
            en[f"ex{k}"], hi[f"ex{k}"] = xp.get("h1_en") or xc.get("title_en") or x.get("title"), xp.get("h1_hi") or xc.get("title_hi") or xp.get("h1_en") or ""
            en[f"exs{k}"], hi[f"exs{k}"] = xe, xh
            xd = x.get("notice_date") or (x.get("first_seen") or "")[:10]
            body += (f'      <a class="r" href="/notice/{x["slug"]}/"><span><span data-t="ex{k}">{esc(en[f"ex{k}"])}</span> <small class="g" data-t="exs{k}">{esc(xe)}</small></span>'
                     f'<span class="v g num">{esc(d_en(xd))}</span></a>\n')
        main.append(f'    <section class="kv rel" id="exam" data-t-aria="exH">\n      <div class="h" data-t="exH">{esc(en["exH"])}</div>\n{body}    </section>')
        rel_ids = {x["id"] for x in others}
        related = [r for r in (related or []) if r.get("id") not in rel_ids]
    if related:
        en["relH"], hi["relH"] = "More notices", "और सूचनाएँ"
        body = ""
        for k, r in enumerate(related[:6]):
            en[f"rel{k}"], hi[f"rel{k}"] = r["en"], r["hi"] or r["en"]
            body += f'      <a class="r" href="/notice/{r["slug"]}/"><span data-t="rel{k}">{esc(r["en"])}</span><span class="v g num">{esc(d_en(r["posted"]))}</span></a>\n'
        main.append(f'    <section class="kv rel" data-t-aria="relH">\n      <div class="h" data-t="relH">More notices</div>\n{body}    </section>')
    # structured data for Google and AI search
    url = f"{SITE_URL}/notice/{slug}/"
    ld = [{"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
              {"@type": "ListItem", "position": 1, "name": "SarkariChart", "item": f"{SITE_URL}/"},
              {"@type": "ListItem", "position": 2, "name": en["crumbType"], "item": f"{SITE_URL}/?cat={CAT_SLUG.get(typ, 'jobs')}"},
              {"@type": "ListItem", "position": 3, "name": en["h1"], "item": url}]},
          {"@context": "https://schema.org", "@type": "WebPage", "name": en["h1"], "url": url, "inLanguage": ["en-IN", "hi-IN"],
           "description": en.get("intro") or en["summary"], "datePublished": posted,
           "dateModified": (n.get("published_at") or "")[:10] or posted,
           "isBasedOn": n.get("url"), "publisher": {"@type": "Organization", "name": "SarkariChart", "url": f"{SITE_URL}/", "logo": f"{SITE_URL}/sarkarichart-logo.png"},
           "primaryImageOfPage": f"{SITE_URL}/notice/{slug}/og.png",
           "about": {"@type": "GovernmentOrganization", "name": en["byV"]}}]
    if faq:
        ld.append({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q["q_en"], "acceptedAnswer": {"@type": "Answer", "text": q["a_en"]}} for q in faq]})
    if typ == "Job" and last:
        total = sum(int(re.sub(r"\D", "", str(v.get("total") or "")) or 0) for v in g("vacancies"))
        jp = {"@context": "https://schema.org", "@type": "JobPosting", "title": en["h1"],
              "description": "<p>" + esc(en.get("intro") or en["summary"]) + "</p>",
              "datePosted": posted, "validThrough": f"{last}T23:59:59+05:30", "employmentType": "FULL_TIME",
              "hiringOrganization": {"@type": "Organization", "name": en["byV"], **({"sameAs": site} if site else {})},
              "jobLocation": {"@type": "Place", "address": {"@type": "PostalAddress", "addressCountry": "IN"}},
              "applicantLocationRequirements": {"@type": "Country", "name": "India"},
              "directApply": False, "url": url}
        if total:
            jp["totalJobOpenings"] = total
        ld.append(jp)
    main.append('    <script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False).replace("</", "<\\/") + "</script>")
    wa = ('<svg width="17" height="17" viewBox="0 0 24 24" aria-hidden="true"><path fill="#00E676" d="M12 .9a11 11 0 0 0-9.6 16.4L.9 23.1l6-1.6A11 11 0 1 0 12 .9z"/><path fill="#F5FFF9" transform="translate(12 11.6) scale(1.32) translate(-12 -12)" d="M16.6 13.9c-.3-.1-1.6-.8-1.8-.9-.2-.1-.4-.1-.6.1-.2.3-.7.9-.8 1.1-.2.2-.3.2-.6.1-.3-.1-1.1-.4-2.1-1.3-.8-.7-1.3-1.5-1.5-1.8-.2-.3 0-.4.1-.6l.4-.5c.1-.2.2-.3.3-.5.1-.2 0-.4 0-.5l-.8-1.9c-.2-.5-.4-.4-.6-.4h-.5c-.2 0-.5.1-.7.3-.2.3-.9.9-.9 2.2s.9 2.6 1.1 2.7c.1.2 1.8 2.8 4.4 3.9 2.2.9 2.6.7 3.1.7.5-.1 1.6-.6 1.8-1.3.2-.6.2-1.2.2-1.3-.1-.1-.3-.2-.6-.3z"/></svg>')
    main.append(f'''    <div class="note">
      <p class="g" data-t="checked">{esc(en["checked"])}</p>
      <p class="actions"><a class="share" id="share" href="#">{wa}<span data-t="share">Share on WhatsApp</span></a><a class="act" id="dlPdf" href="#" download><svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 4v11M7 10l5 5 5-5M5 20h14"/></svg><span data-t="dlPdf">Download this page as PDF</span></a><a class="act" href="/report/?page=/notice/{slug}/"><svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 21V4M5 4h11l-2 4 2 4H5"/></svg><span data-t="reportPage">Report a mistake on this page</span></a></p>
    </div>''')

    tpl = TEMPLATE.read_text(encoding="utf-8")
    for d_, brand in ((en, "SarkariChart"), (hi, "सरकारी चार्ट")):   # browser tab / Google title: heading + brand when it fits
        if len(f'{d_["title"]} | {brand}') <= 72:
            d_["title"] = f'{d_["title"]} | {brand}'
    t_en = "\n".join(f"      {k}: {js(v)}," for k, v in en.items())
    t_hi = "\n".join(f"      {k}: {js(v)}," for k, v in hi.items())
    desc = (en["summary"] or en["h1"])
    if len(desc) > 158:
        desc = desc[:155].rsplit(" ", 1)[0] + "…"
    out = (tpl.replace("{{TITLE}}", esc(en["title"])).replace("{{DESC}}", esc(desc)).replace("{{MAIN}}", "\n".join(main))
           .replace("{{T_EN}}", t_en).replace("{{T_HI}}", t_hi).replace("{{SLUG}}", slug)
           .replace("{{OGIMG}}", f"{SITE_URL}/notice/{slug}/og.png").replace("{{OGALT}}", esc(f"{en['h1']} — {en['org']} {typ} notice summary card by SarkariChart")).replace("{{URL}}", f"{SITE_URL}/notice/{slug}/")
           .replace("{{LAST}}", f'new Date("{last}T23:59:59+05:30")' if last else "null"))
    return out


def related_for(n: dict, notices: list) -> list:
    """Up to 6 other live notices: same board first, then same category; newest first."""
    me, c = n["id"], (n.get("card") or {})
    pool = [x for _, x in notices if x.get("status") == "approved" and x.get("slug") and x["id"] != me]
    key = lambda x: (x.get("org") == n.get("org"), (x.get("card") or {}).get("type") == c.get("type"), x.get("notice_date") or "")
    out = []
    for x in sorted(pool, key=key, reverse=True)[:6]:
        xc = x.get("card") or {}
        out.append({"id": x["id"], "slug": x["slug"], "en": xc.get("title_en") or x.get("title"), "hi": xc.get("title_hi") or "",
                    "posted": x.get("notice_date") or x["first_seen"][:10]})
    return out


def main():
    rebuild_all = "--all" in sys.argv
    backfill = [int(os.environ.get("PAGE_BACKFILL", "6"))]
    files = sorted(NOTICES.glob("*.json"))
    notices = [(f, json.loads(f.read_text())) for f in files]
    taken = {n["slug"]: n["id"] for _, n in notices if n.get("slug")}
    try:
        from exams import groups as _exam_groups
        exam_groups = _exam_groups([x for _, x in notices])
    except Exception as e:  # noqa: BLE001 — an exam-page problem must never stop notice pages
        print(f"  exam groups unavailable: {e}")
        exam_groups = {}
    for f, n in notices:
        if n.get("status") != "approved":
            continue
        # pages written before the full layout (no FAQ/intro) are upgraded a few per run, so the free AI quota
        # is never exhausted in one go; every 30-minute check upgrades the next few until all are done
        old_layout = n.get("page") and "share_card" not in n["page"]   # before the full article layout (Oct 2026)
        need_ai = rebuild_all or not n.get("page") or (old_layout and backfill[0] > 0) or bool(n.get("rewrite"))
        if old_layout and not rebuild_all and need_ai:
            backfill[0] -= 1
        if need_ai:
            notes = gh_comments(n.get("issue"))
            page = ai_page(n, notes)
            if not page:
                print(f"  {n['id']}: AI unavailable, page skipped this run")
                continue
            n["page"] = page
            if n.pop("rewrite", None):   # text was re-read: qualification and eligibility are tagged again too
                n.pop("qual", None); n.pop("elig", None)
            n["editor_notes"] = notes
            for k in ("last_date", "exam_date"):
                if page.get(k) and n.get("card") is not None:
                    n["card"][k] = valid_date(page[k]) or n["card"].get(k)
            if page.get("h1_en"):
                n["card"]["title_en"], n["card"]["title_hi"] = page["h1_en"], page.get("h1_hi") or n["card"].get("title_hi")
        n["notice_date"] = official_date(n)
        slug = unique_slug(n, taken)
        n["slug"] = slug
        out = SITE / "notice" / slug / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            out.write_text(render(n, slug, related_for(n, notices), exam_groups), encoding="utf-8")
        except Exception as e:  # noqa: BLE001 — keep going; this page keeps its previous version
            print(f"  {n['id']}: render failed ({type(e).__name__}: {e})"[:300])
            continue
        # data for the share images (site/notice/<slug>/og.png + og-hi.png, drawn by scripts/og_card.mjs at deploy)
        og = share_data(n, d_en, d_hi, valid_date)
        (out.parent / "og.json").write_text(json.dumps(og, ensure_ascii=False), encoding="utf-8")
        f.write_text(json.dumps(n, ensure_ascii=False, indent=2, sort_keys=True))
        print(f"  {n['id']}: /notice/{slug}/ {('(notes: ' + n['page'].get('changes_from_notes', '') + ')') if n.get('editor_notes') else ''}")


if __name__ == "__main__":
    main()
