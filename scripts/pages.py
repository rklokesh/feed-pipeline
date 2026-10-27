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
Hindi must be natural Devanagari with no English words (proper nouns transliterated, numbers as digits, ₹ for money).
Answer with ONE JSON object:
{
 "h1_en": "page title, max 70 chars", "h1_hi": "same in Hindi",
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
 "intro_en": "3-4 sentence introduction for the page: which board, which posts/exam and year, how many vacancies, the key dates, and who should read it. Plain, factual, no hype.",
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
 "faq": [ {"q_en": "What is the last date to apply for ...?", "a_en": "...", "q_hi": "", "a_hi": ""} ],
     // 4-6 questions people actually search for THIS notice (last date, fee, age, eligibility, how to apply/download, vacancies),
     // each answered in 1-2 sentences from the notice. Skip questions the notice does not answer.
 "notice_date": "YYYY-MM-DD: the date the board issued THIS notice (e.g. 'Dated: 08.10.2026', 'Date of publication', the date
                 printed at the top or bottom of the notice / press note). Not the exam date, not the last date. null if not printed.",
 "apply_start": "YYYY-MM-DD or null", "last_date": "YYYY-MM-DD or null (last date to apply)", "exam_date": "YYYY-MM-DD or null",
 "apply_url": "official application URL or null", "official_site": "official website URL or null",
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
    d = valid_date((n.get("page") or {}).get("notice_date"))
    if d:
        dd = dt.date.fromisoformat(d)
        if seen - dt.timedelta(days=400) <= dd <= seen:   # sane: issued before we saw it, not ancient
            return d
    return seen.isoformat()


SITE_URL = os.environ.get("SITE_URL", "https://sarkarichart.pages.dev")   # change to https://sarkarichart.com at launch
CAT_SLUG = {"Job": "jobs", "Result": "results", "Admit card": "admit-cards", "Answer key": "answer-keys"}


def render(n: dict, slug: str, related: list | None = None) -> str:
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
    en["key"], hi["key"] = "Key details", "मुख्य जानकारी"
    en["fee"], hi["fee"] = "Application fee", "आवेदन शुल्क"
    en["links"], hi["links"] = "Official links", "आधिकारिक लिंक"
    en["lNotice"], hi["lNotice"] = "Official notice", "आधिकारिक सूचना"
    en["lApply"], hi["lApply"] = "Apply online", "ऑनलाइन आवेदन"
    en["lSite"], hi["lSite"] = "Official website", "आधिकारिक वेबसाइट"
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

    esc = html.escape
    main = [f'''    <div class="title">
      <nav class="crumb" aria-label="Breadcrumb"><a href="/?cat={CAT_SLUG.get(typ, "jobs")}" data-t="crumbType">{esc(en["crumbType"])}</a><span class="sep" aria-hidden="true">/</span><span class="here" aria-current="page" data-t="org">{esc(en["org"])}</span></nav>
      <h1 data-t="h1">{esc(en["h1"])}</h1>
      <p class="status"><span id="state">{esc(en["statusV"])}</span><span id="left"></span><span id="views" class="g" hidden></span></p>
      {f'<p class="lead" data-t="summary">{esc(en["summary"])}</p>' if en["summary"] else ""}
    </div>''',
            '    <section class="kv" data-t-aria="key">\n      <div class="h" data-t="key">Key details</div>\n' +
            "".join(f'      <div class="r"><span data-t="{lk}">{esc(en[lk])}</span><span class="v" data-t="{vk}">{esc(en[vk])}</span></div>\n'
                    for lk, vk in rows) + "    </section>"]
    if fees:
        main.append('    <section class="kv" data-t-aria="fee">\n      <div class="h" data-t="fee">Application fee</div>\n' +
                    "".join(f'      <div class="r"><span data-t="{k}">{esc(en[k])}</span><span class="v num">{amt}</span></div>\n' for k, amt in fees) +
                    "    </section>")
    S = lambda v: "" if v is None else (", ".join(S(x) for x in v) if isinstance(v, list) else str(v)).strip()

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
        main.append(f'    <section class="kv" data-t-aria="{key}">\n      <div class="h" data-t="{key}">{esc(label_en)}</div>\n{body}    </section>')

    def sec_list(key, label_en, label_hi, items_en, items_hi):
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
        main.append(f'    <section class="kv" data-t-aria="{key}">\n      <div class="h" data-t="{key}">{esc(label_en)}</div>\n      <ol class="steps">{lis}</ol>\n    </section>')

    g = lambda k: [x for x in (pg.get(k) or []) if isinstance(x, dict)] if isinstance(pg.get(k), list) else []
    if S(pg.get("intro_en")):
        pg["intro_en"], pg["intro_hi"] = S(pg.get("intro_en")), S(pg.get("intro_hi"))
        en["aboutH"], hi["aboutH"] = "About this notice", "इस सूचना के बारे में"
        en["intro"], hi["intro"] = pg["intro_en"], pg.get("intro_hi") or pg["intro_en"]
        main.insert(1, '    <section class="kv" data-t-aria="aboutH">\n      <div class="h" data-t="aboutH">About this notice</div>\n'
                       f'      <p class="p" data-t="intro">{esc(en["intro"])}</p>\n    </section>')
    sec_kv("datesH", "Important dates", "महत्वपूर्ण तिथियाँ", [(d.get("label_en"), d.get("label_hi"), d.get("value_en"), d.get("value_hi")) for d in g("dates")])
    sec_kv("ageH", "Age limit", "आयु सीमा", [(d.get("label_en"), d.get("label_hi"), d.get("value_en"), d.get("value_hi")) for d in g("age")])
    vac = [(v.get("post_en"), v.get("post_hi"), " · ".join(x for x in [str(v.get("total") or ""), v.get("detail_en") or ""] if x),
            " · ".join(x for x in [str(v.get("total") or ""), v.get("detail_hi") or v.get("detail_en") or ""] if x)) for v in g("vacancies")]
    sec_kv("vacH", "Vacancy details", "रिक्तियों का विवरण", vac)
    sec_kv("eligH", "Eligibility", "पात्रता", [(d.get("label_en"), d.get("label_hi"), d.get("value_en"), d.get("value_hi")) for d in g("eligibility")])
    sec_list("selH", "Selection process", "चयन प्रक्रिया", pg.get("selection_en"), pg.get("selection_hi"))
    sec_list("howH", "How to apply" if typ == "Job" else "How to download", "आवेदन कैसे करें" if typ == "Job" else "कैसे डाउनलोड करें", pg.get("how_en"), pg.get("how_hi"))
    sec_kv("extraH", "Other details", "अन्य जानकारी", [(d.get("label_en"), d.get("label_hi"), d.get("value_en"), d.get("value_hi")) for d in g("extra")])
    main.append('    <section class="kv" data-t-aria="links">\n      <div class="h" data-t="links">Official links</div>\n' +
                "".join(f'      <a class="r" href="{esc(u)}" target="_blank" rel="noopener"><span data-t="{k}">{esc(en[k])}</span><span class="v">{esc(host(u))}</span></a>\n'
                        for k, u in links if u) + "    </section>")
    faq = [{k: S(v) for k, v in q.items()} for q in g("faq")]
    faq = [q for q in faq if q.get("q_en") and q.get("a_en")][:6]
    if faq:
        en["faqH"], hi["faqH"] = "Frequently asked questions", "अक्सर पूछे जाने वाले सवाल"
        body = ""
        for k, q in enumerate(faq):
            en[f"q{k}"], hi[f"q{k}"] = q["q_en"], q.get("q_hi") or q["q_en"]
            en[f"a{k}"], hi[f"a{k}"] = q["a_en"], q.get("a_hi") or q["a_en"]
            body += f'      <details class="qa"><summary data-t="q{k}">{esc(q["q_en"])}</summary><p data-t="a{k}">{esc(q["a_en"])}</p></details>\n'
        main.append(f'    <section class="kv faq" data-t-aria="faqH">\n      <div class="h" data-t="faqH">Frequently asked questions</div>\n{body}    </section>')
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
           "isBasedOn": n.get("url"), "publisher": {"@type": "Organization", "name": "SarkariChart", "url": f"{SITE_URL}/"},
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
    t_en = "\n".join(f"      {k}: {js(v)}," for k, v in en.items())
    t_hi = "\n".join(f"      {k}: {js(v)}," for k, v in hi.items())
    desc = (en["summary"] or en["h1"])[:155]
    out = (tpl.replace("{{TITLE}}", esc(en["title"])).replace("{{DESC}}", esc(desc)).replace("{{MAIN}}", "\n".join(main))
           .replace("{{T_EN}}", t_en).replace("{{T_HI}}", t_hi).replace("{{SLUG}}", slug)
           .replace("{{OGIMG}}", f"{SITE_URL}/notice/{slug}/og.png").replace("{{URL}}", f"{SITE_URL}/notice/{slug}/")
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
        out.append({"slug": x["slug"], "en": xc.get("title_en") or x.get("title"), "hi": xc.get("title_hi") or "",
                    "posted": x.get("notice_date") or x["first_seen"][:10]})
    return out


def main():
    rebuild_all = "--all" in sys.argv
    backfill = [int(os.environ.get("PAGE_BACKFILL", "6"))]
    files = sorted(NOTICES.glob("*.json"))
    notices = [(f, json.loads(f.read_text())) for f in files]
    taken = {n["slug"]: n["id"] for _, n in notices if n.get("slug")}
    for f, n in notices:
        if n.get("status") != "approved":
            continue
        # pages written before the full layout (no FAQ/intro) are upgraded a few per run, so the free AI quota
        # is never exhausted in one go; every 30-minute check upgrades the next few until all are done
        old_layout = n.get("page") and not ({"faq", "intro_en"} & set(n["page"]))
        need_ai = rebuild_all or not n.get("page") or (old_layout and backfill[0] > 0)
        if old_layout and not rebuild_all and need_ai:
            backfill[0] -= 1
        if need_ai:
            notes = gh_comments(n.get("issue"))
            page = ai_page(n, notes)
            if not page:
                print(f"  {n['id']}: AI unavailable, page skipped this run")
                continue
            n["page"] = page
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
            out.write_text(render(n, slug, related_for(n, notices)), encoding="utf-8")
        except Exception as e:  # noqa: BLE001 — keep going; this page keeps its previous version
            print(f"  {n['id']}: render failed ({type(e).__name__}: {e})"[:300])
            continue
        # data for the share image (site/notice/<slug>/og.png, drawn by scripts/make_pdfs.mjs at deploy)
        c, pg = n.get("card") or {}, n.get("page") or {}
        typ = c.get("type", "Job")
        last = valid_date(pg.get("last_date") or c.get("last_date")) if typ == "Job" else None
        og = {"title_en": pg.get("h1_en") or c.get("title_en") or n.get("title"), "title_hi": pg.get("h1_hi") or c.get("title_hi") or "",
              "org": n.get("org") or "", "type_en": typ, "type_hi": {"Job": "नौकरी", "Result": "रिज़ल्ट", "Admit card": "एडमिट कार्ड", "Answer key": "आंसर की"}.get(typ, ""),
              "last_en": d_en(last) if last else "", "last_hi": d_hi(last) if last else "",
              "status_en": pg.get("status_en") or "", "status_hi": pg.get("status_hi") or ""}
        (out.parent / "og.json").write_text(json.dumps(og, ensure_ascii=False), encoding="utf-8")
        f.write_text(json.dumps(n, ensure_ascii=False, indent=2, sort_keys=True))
        print(f"  {n['id']}: /notice/{slug}/ {('(notes: ' + n['page'].get('changes_from_notes', '') + ')') if n.get('editor_notes') else ''}")


if __name__ == "__main__":
    main()
