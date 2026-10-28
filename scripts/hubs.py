"""Browse pages: govt jobs by state (/up-govt-jobs/ …) and by qualification (/10th-pass-govt-jobs/ …), plus /govt-jobs/.

  python scripts/hubs.py tag     # before pages.py: AI tags each job notice's minimum qualification (batched)
  python scripts/hubs.py build   # after pages.py: writes the browse pages and the homepage search hints

Same calm list as everywhere else: no new widgets. State pages list every live notice from that state's own
boards (central exams are open to everyone and live on the homepage). Qualification pages list open jobs only.
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

import requests

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from extract import _json_from, _providers, _throttle  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
NOTICES = ROOT / "data" / "notices"
SITE = ROOT / "site"
TPL = ROOT / "templates" / "notice.html"
SITE_URL = os.environ.get("SITE_URL", "https://sarkarichart.pages.dev")
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
YEAR = dt.datetime.now(IST).year
MONTHS_HI = ["जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर", "अक्तूबर", "नवंबर", "दिसंबर"]

# slug, EN name, HI name, source-id prefixes (the state's own boards)
STATES = [
    ("up", "UP", "यूपी", ["uppsc", "upsssc", "uppbpb"]),
    ("bihar", "Bihar", "बिहार", ["bpsc", "bssc", "csbc"]),
    ("rajasthan", "Rajasthan", "राजस्थान", ["rpsc", "rssb"]),
    ("mp", "MP", "एमपी", ["mppsc", "mpesb"]),
    ("haryana", "Haryana", "हरियाणा", ["hpsc", "hssc"]),
    ("delhi", "Delhi", "दिल्ली", ["dsssb"]),
    ("uttarakhand", "Uttarakhand", "उत्तराखंड", ["ukpsc"]),
    ("west-bengal", "West Bengal", "पश्चिम बंगाल", ["wbpsc"]),
    ("maharashtra", "Maharashtra", "महाराष्ट्र", ["mpsc"]),
    ("tamil-nadu", "Tamil Nadu", "तमिलनाडु", ["tnpsc"]),
]
# slug, tag, EN, HI, search words that point to the page
QUALS = [
    ("10th-pass", "10th", "10th Pass", "10वीं पास", ["10th", "10 pass", "10th pass", "matric", "high school", "10वीं", "हाईस्कूल"]),
    ("12th-pass", "12th", "12th Pass", "12वीं पास", ["12th", "12 pass", "12th pass", "inter", "intermediate", "12वीं", "इंटर"]),
    ("iti", "iti", "ITI", "आईटीआई", ["iti", "आईटीआई"]),
    ("diploma", "diploma", "Diploma", "डिप्लोमा", ["diploma", "polytechnic", "डिप्लोमा"]),
    ("graduate", "graduate", "Graduate", "स्नातक", ["graduate", "graduation", "degree", "ba", "bsc", "bcom", "स्नातक", "ग्रेजुएट"]),
    ("post-graduate", "postgraduate", "Post Graduate", "स्नातकोत्तर", ["post graduate", "pg", "postgraduate", "ma", "msc", "mba", "स्नातकोत्तर"]),
]
TAGS = [q[1] for q in QUALS]
TYPE = {"Job": ("Notice", "सूचना"), "Admit card": ("Admit card", "एडमिट कार्ड"), "Result": ("Result", "रिज़ल्ट"), "Answer key": ("Answer key", "आंसर की")}

PROMPT = """For each Indian government job notice, give the minimum educational qualification(s) asked for its posts.
Use only these tags: "10th", "12th", "iti", "diploma", "graduate", "postgraduate". If different posts in one notice need different
levels, list each level (e.g. ["10th","iti"]). 8th-pass posts count as "10th". A degree in any subject or a professional degree
(B.Tech, MBBS, LLB, B.Ed) is "graduate"; a master's/PhD/MD is "postgraduate". Use [] when the notice does not say.
Answer with JSON: {"tags": [{"id": "...", "qual": ["..."]}]}"""


def load():
    return [(f, json.loads(f.read_text())) for f in sorted(NOTICES.glob("*.json"))]


def title(n, hi=False):
    c, pg = n.get("card") or {}, n.get("page") or {}
    en = pg.get("h1_en") or c.get("title_en") or n.get("title") or ""
    return (pg.get("h1_hi") or c.get("title_hi") or en) if hi else en


def is_job(n):
    return (n.get("card") or {}).get("type", "Job") == "Job"


def ai(user):
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
            if r.status_code == 200:
                try:
                    return _json_from(r.json()["choices"][0]["message"]["content"])
                except Exception:  # noqa: BLE001
                    break
            if r.status_code not in (429, 500, 502, 503):
                break
    return None


def tag():
    todo = [(f, n) for f, n in load() if n.get("status") == "approved" and is_job(n) and "qual" not in n]
    if not todo:
        print("hubs: nothing to tag")
        return
    for i in range(0, len(todo), 40):
        batch = todo[i:i + 40]
        items = []
        for _, n in batch:
            pg = n.get("page") or {}
            elig = [f'{e.get("label_en")}: {e.get("value_en")}' for e in (pg.get("eligibility") or []) if isinstance(e, dict)]
            rows = [f'{r.get("label_en")}: {r.get("value_en")}' for r in (pg.get("rows") or []) if isinstance(r, dict) and re.search(r"qualif|educat|eligib", str(r.get("label_en")), re.I)]
            items.append({"id": n["id"], "title": title(n), "posts": (n.get("card") or {}).get("posts"), "education": (elig + rows)[:6]})
        res = ai(json.dumps({"notices": items}, ensure_ascii=False))
        if not res:
            print("hubs: AI unavailable, will tag next run")
            return
        got = {t.get("id"): t for t in res.get("tags", []) if isinstance(t, dict)}
        for f, n in batch:
            if n["id"] not in got:
                continue
            n["qual"] = sorted({q for q in (got[n["id"]].get("qual") or []) if q in TAGS}, key=TAGS.index)
            f.write_text(json.dumps(n, ensure_ascii=False, indent=2, sort_keys=True))
        print(f"hubs: tagged {len(batch)} job notices")


def nd(n):
    return n.get("notice_date") or (n.get("first_seen") or "")[:10]


def last_of(n):
    c, pg = n.get("card") or {}, n.get("page") or {}
    v = str(pg.get("last_date") or c.get("last_date") or "")[:10]
    return v if re.fullmatch(r"\d{4}-\d\d-\d\d", v) else ""


def d_en(iso):
    d = dt.date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%b')} {d.year}"


def d_hi(iso):
    d = dt.date.fromisoformat(iso)
    return f"{d.day} {MONTHS_HI[d.month - 1]} {d.year}"


def page(slug, en, hi, sections, desc):
    """sections: [(key, title_en, title_hi, [notice...], empty_en, empty_hi)] rendered as the usual bordered lists."""
    esc = html.escape
    js = lambda v: json.dumps("" if v is None else str(v), ensure_ascii=False)
    today = dt.datetime.now(IST).date().isoformat()
    main = [f'''    <div class="title">
      <nav class="crumb" aria-label="Breadcrumb"><a href="/govt-jobs/" data-t="crumbType">{esc(en["crumbType"])}</a><span class="sep" aria-hidden="true">/</span><span class="here" aria-current="page" data-t="org">{esc(en["org"])}</span></nav>
      <h1 data-t="h1">{esc(en["h1"])}</h1>
      <p class="lead" data-t="lead">{esc(en["lead"])}</p>
      <span id="state" hidden></span><span id="left" hidden></span><span id="views" hidden></span>
    </div>''']
    all_items = []
    for key, te, th, items, ee, eh in sections:
        en[key], hi[key] = te, th
        body = ""
        for k, n in enumerate(items):
            i = f"{key}{k}"
            en[i], hi[i] = title(n), title(n, True)
            last = last_of(n)
            if is_job(n) and last and last >= today:
                en[i + "s"], hi[i + "s"] = f"Last date {d_en(last)}", f"अंतिम तिथि {d_hi(last)}"
            else:
                t = TYPE.get((n.get("card") or {}).get("type", "Job"), TYPE["Job"])
                en[i + "s"], hi[i + "s"] = t
            en[i + "d"], hi[i + "d"] = d_en(nd(n)), d_hi(nd(n))
            body += (f'      <a class="r" href="/notice/{n["slug"]}/"><span class="num" data-t="{i}d">{esc(en[i + "d"])}</span>'
                     f'<span class="v"><span data-t="{i}">{esc(en[i])}</span> <small class="g" data-t="{i}s">{esc(en[i + "s"])}</small></span></a>\n')
            all_items.append(n)
        if not body:
            en[key + "E"], hi[key + "E"] = ee, eh
            body = f'      <div class="r one"><span class="g" data-t="{key}E">{esc(ee)}</span></div>\n'
        main.append(f'    <section class="kv tl" data-t-aria="{key}">\n      <div class="h" data-t="{key}">{esc(te)}</div>\n{body}    </section>')
    main.append(f'    <div class="note"><p class="g" data-t="note">{esc(en["note"])}</p></div>\n    <a id="dlPdf" hidden></a><a id="share" hidden></a>')
    url = f"{SITE_URL}/{slug}/"
    ld = [{"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
              {"@type": "ListItem", "position": 1, "name": "SarkariChart", "item": f"{SITE_URL}/"},
              {"@type": "ListItem", "position": 2, "name": "Govt jobs", "item": f"{SITE_URL}/govt-jobs/"},
              {"@type": "ListItem", "position": 3, "name": en["org"], "item": url}]},
          {"@context": "https://schema.org", "@type": "ItemList", "name": en["h1"], "url": url,
           "itemListElement": [{"@type": "ListItem", "position": k + 1, "url": f'{SITE_URL}/notice/{n["slug"]}/', "name": title(n)} for k, n in enumerate(all_items[:50])]}]
    main.append('    <script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False).replace("</", "<\\/") + "</script>")
    tpl = TPL.read_text(encoding="utf-8")
    out = (tpl.replace("{{TITLE}}", esc(en["title"])).replace("{{DESC}}", esc(desc)).replace("{{MAIN}}", "\n".join(main))
           .replace("{{T_EN}}", "\n".join(f"      {k}: {js(v)}," for k, v in en.items()))
           .replace("{{T_HI}}", "\n".join(f"      {k}: {js(v)}," for k, v in hi.items()))
           .replace("{{SLUG}}", slug).replace("{{OGIMG}}", f"{SITE_URL}/og.png").replace("{{OGALT}}", esc(en["h1"]))
           .replace("{{URL}}", url).replace("{{LAST}}", "null"))
    d = SITE / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "index.html").write_text(out, encoding="utf-8")


def build():
    notices = [n for _, n in load() if n.get("status") == "approved" and n.get("slug") and (SITE / "notice" / n["slug"]).exists()]
    notices.sort(key=lambda n: (nd(n), n.get("first_seen") or ""), reverse=True)
    today = dt.datetime.now(IST).date().isoformat()
    # open = a job notice with a last date that has not passed (DV notices, syllabus updates etc. have none)
    open_job = lambda n: is_job(n) and last_of(n) >= today
    note = ("Lists are made from official notices and update every 30 minutes. If anything differs, the official notice is correct.",
            "सूचियाँ आधिकारिक सूचनाओं से बनती हैं और हर 30 मिनट में अपडेट होती हैं। कोई बात अलग हो, तो आधिकारिक सूचना को ही सही मानें।")
    hubs = []   # for the index page and the homepage search hints
    for slug, en_name, hi_name, prefixes in STATES:
        mine = [n for n in notices if any((n.get("source_id") or "").split("-")[0] == p or (n.get("source_id") or "").startswith(p + "-") for p in prefixes)]
        if not mine:
            continue
        jobs = [n for n in mine if open_job(n)]
        other = [n for n in mine if not open_job(n)][:30]
        boards = ", ".join(dict.fromkeys(n.get("org") for n in mine if n.get("org")))
        s = f"{slug}-govt-jobs"
        en = {"crumbType": "Govt jobs", "org": en_name, "h1": f"{en_name} Govt Jobs {YEAR}",
              "lead": f"Every official notice from {en_name}'s own recruitment boards ({boards}): jobs you can apply for now, then the latest admit cards, results and other updates. Central exams like SSC, RRB and UPSC are open to everyone and are on the homepage.",
              "note": note[0], "title": f"{en_name} Govt Jobs {YEAR}: Latest Vacancy, Admit Card, Result | SarkariChart"}
        hi = {"crumbType": "सरकारी नौकरी", "org": hi_name, "h1": f"{hi_name} सरकारी नौकरी {YEAR}",
              "lead": f"{hi_name} के अपने भर्ती बोर्ड ({boards}) की हर आधिकारिक सूचना: पहले वे नौकरियाँ जिनमें अभी आवेदन हो सकता है, फिर ताज़ा एडमिट कार्ड, रिज़ल्ट और अपडेट। एसएससी, आरआरबी, यूपीएससी जैसी केंद्रीय परीक्षाएँ सबके लिए हैं और होमपेज पर हैं।",
              "note": note[1], "title": f"{hi_name} सरकारी नौकरी {YEAR} | सरकारी चार्ट"}
        page(s, en, hi, [("jobs", "Open jobs", "खुली नौकरियाँ", jobs, "No open jobs right now. New ones appear here as soon as they are announced.", "अभी कोई खुली नौकरी नहीं है। नई सूचना आते ही यहाँ दिखेगी।"),
                         ("upd", "Latest notices: admit cards, results and updates", "ताज़ा सूचनाएँ: एडमिट कार्ड, रिज़ल्ट और अपडेट", other, "Nothing yet.", "अभी कुछ नहीं।")],
             f"Latest {en_name} government jobs {YEAR} from official boards ({boards}): open vacancies with last dates, admit cards, answer keys and results.")
        hubs.append({"kind": "state", "slug": s, "en": en_name, "hi": hi_name, "n": len(jobs), "words": [en_name.lower(), hi_name, slug.replace("-", " ")]})
    for slug, tagv, en_name, hi_name, words in QUALS:
        jobs = [n for n in notices if open_job(n) and tagv in (n.get("qual") or [])]
        s = f"{slug}-govt-jobs"
        en = {"crumbType": "Govt jobs", "org": en_name, "h1": f"{en_name} Govt Jobs {YEAR}",
              "lead": f"Open government jobs that accept {en_name} as the minimum qualification, newest first, each with its last date. Always check the exact eligibility in the official notice.",
              "note": note[0], "title": f"{en_name} Govt Jobs {YEAR}: Latest Vacancies, Apply Online | SarkariChart"}
        hi = {"crumbType": "सरकारी नौकरी", "org": hi_name, "h1": f"{hi_name} सरकारी नौकरी {YEAR}",
              "lead": f"वे खुली सरकारी नौकरियाँ जिनमें न्यूनतम योग्यता {hi_name} है, नई सबसे ऊपर, अंतिम तिथि के साथ। सही पात्रता हमेशा आधिकारिक सूचना में देखें।",
              "note": note[1], "title": f"{hi_name} सरकारी नौकरी {YEAR} | सरकारी चार्ट"}
        page(s, en, hi, [("jobs", "Open jobs", "खुली नौकरियाँ", jobs, "No open jobs for this qualification right now. New ones appear here as soon as they are announced.", "इस योग्यता की अभी कोई खुली नौकरी नहीं है। नई सूचना आते ही यहाँ दिखेगी।")],
             f"Latest {en_name} government jobs {YEAR}: open vacancies from official notices with last dates and direct links.")
        hubs.append({"kind": "qual", "slug": s, "en": en_name, "hi": hi_name, "n": len(jobs), "words": words})
    index(hubs)
    homepage_hints(hubs)
    print(f"hubs: {len(hubs)} browse pages")


def index(hubs):
    esc = html.escape
    js = lambda v: json.dumps("" if v is None else str(v), ensure_ascii=False)
    en = {"h1": "Browse govt jobs", "lead": "By state and by qualification. Every list is made from official notices.",
          "sH": "By state", "qH": "By qualification", "title": "Govt Jobs by State and Qualification | SarkariChart"}
    hi = {"h1": "सरकारी नौकरी ढूँढें", "lead": "राज्य और योग्यता के अनुसार। हर सूची आधिकारिक सूचनाओं से बनती है।",
          "sH": "राज्य के अनुसार", "qH": "योग्यता के अनुसार", "title": "राज्य और योग्यता के अनुसार सरकारी नौकरी | सरकारी चार्ट"}
    secs = ""
    for kind, key in (("state", "sH"), ("qual", "qH")):
        rows = ""
        for k, h in enumerate(x for x in hubs if x["kind"] == kind):
            i = f"{kind}{k}"
            en[i], hi[i] = f'{h["en"]} govt jobs', f'{h["hi"]} सरकारी नौकरी'
            en[i + "n"], hi[i + "n"] = f'{h["n"]} open', f'{h["n"]} खुली'
            rows += f'      <a class="r" href="/{h["slug"]}/"><span data-t="{i}">{esc(en[i])}</span><span class="v g" data-t="{i}n">{esc(en[i + "n"])}</span></a>\n'
        secs += f'    <section class="kv rel">\n      <div class="h" data-t="{key}">{esc(en[key])}</div>\n{rows}    </section>\n'
    main = f'''    <div class="title">
      <h1 data-t="h1">{esc(en["h1"])}</h1>
      <p class="lead" data-t="lead">{esc(en["lead"])}</p>
      <span id="state" hidden></span><span id="left" hidden></span><span id="views" hidden></span>
    </div>
{secs}    <a id="dlPdf" hidden></a><a id="share" hidden></a>'''
    tpl = TPL.read_text(encoding="utf-8")
    out = (tpl.replace("{{TITLE}}", esc(en["title"])).replace("{{DESC}}", esc(en["lead"])).replace("{{MAIN}}", main)
           .replace("{{T_EN}}", "\n".join(f"      {k}: {js(v)}," for k, v in en.items()))
           .replace("{{T_HI}}", "\n".join(f"      {k}: {js(v)}," for k, v in hi.items()))
           .replace("{{SLUG}}", "govt-jobs").replace("{{OGIMG}}", f"{SITE_URL}/og.png").replace("{{OGALT}}", "SarkariChart")
           .replace("{{URL}}", f"{SITE_URL}/govt-jobs/").replace("{{LAST}}", "null"))
    (SITE / "govt-jobs").mkdir(parents=True, exist_ok=True)
    (SITE / "govt-jobs" / "index.html").write_text(out, encoding="utf-8")


def homepage_hints(hubs):
    """Search words that point to a browse page: typing "10th pass" or "UP" on the homepage shows one quiet link line."""
    p = SITE / "index.html"
    s = p.read_text(encoding="utf-8")
    data = json.dumps([{"slug": h["slug"], "en": h["en"], "hi": h["hi"], "kind": h["kind"], "words": h["words"]} for h in hubs], ensure_ascii=False).replace("</", "<\\/")
    s = re.sub(r"/\*HUBS:START\*/.*?/\*HUBS:END\*/", lambda m: "/*HUBS:START*/" + data + "/*HUBS:END*/", s, count=1, flags=re.S)
    p.write_text(s, encoding="utf-8")


if __name__ == "__main__":
    {"tag": tag, "build": build}.get(sys.argv[1] if len(sys.argv) > 1 else "build", build)()
