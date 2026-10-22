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
     // ordered, only rows you know: Posts, Total vacancies, Apply online (start to last date), Last date for fee,
     // Exam date, Educational qualification, Age limit (with as-on date), Selection process, Advertisement number,
     // for results/admit cards: how to download, roll-number/district info, etc. Values short; dates like '14 Dec 2026'.
 "fees": [ {"cat_en": "General / OBC", "cat_hi": "सामान्य / अन्य पिछड़ा वर्ग", "amount": "₹100"} ],
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


CAT_SLUG = {"Job": "jobs", "Result": "results", "Admit card": "admit-cards", "Answer key": "answer-keys"}


def render(n: dict, slug: str) -> str:
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
    main.append('    <section class="kv" data-t-aria="links">\n      <div class="h" data-t="links">Official links</div>\n' +
                "".join(f'      <a class="r" href="{esc(u)}" target="_blank" rel="noopener"><span data-t="{k}">{esc(en[k])}</span><span class="v">{esc(host(u))}</span></a>\n'
                        for k, u in links if u) + "    </section>")
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
           .replace("{{LAST}}", f'new Date("{last}T23:59:59+05:30")' if last else "null"))
    return out


def main():
    rebuild_all = "--all" in sys.argv
    files = sorted(NOTICES.glob("*.json"))
    notices = [(f, json.loads(f.read_text())) for f in files]
    taken = {n["slug"]: n["id"] for _, n in notices if n.get("slug")}
    for f, n in notices:
        if n.get("status") != "approved":
            continue
        need_ai = rebuild_all or not n.get("page")
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
        out.write_text(render(n, slug), encoding="utf-8")
        f.write_text(json.dumps(n, ensure_ascii=False, indent=2, sort_keys=True))
        print(f"  {n['id']}: /notice/{slug}/ {('(notes: ' + n['page'].get('changes_from_notes', '') + ')') if n.get('editor_notes') else ''}")


if __name__ == "__main__":
    main()
