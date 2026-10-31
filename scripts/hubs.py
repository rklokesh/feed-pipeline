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
For an admit card, result, answer key or exam schedule, give the qualification asked for the posts of that exam (the
recruitment it belongs to), using the notice and your knowledge of that recruitment only when the posts are clearly named
(e.g. SSC CGL -> graduate, RRB Group D -> 10th, ITI). Use [] when unsure.
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
    todo = [(f, n) for f, n in load() if n.get("status") == "approved" and "qual" not in n]
    todo.sort(key=lambda fn: not is_job(fn[1]))   # jobs first
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
            items.append({"id": n["id"], "type": (n.get("card") or {}).get("type"), "title": title(n), "posts": (n.get("card") or {}).get("posts"), "education": (elig + rows)[:6]})
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
        print(f"hubs: tagged {len(batch)} notices")


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


def build():
    """Each browse page is the homepage itself, opened on the Jobs tab with one filter set (same look everywhere).
    Run after publish.py build so the copies carry the current notice list."""
    import shutil
    home = (SITE / "index.html").read_text(encoding="utf-8")
    if (SITE / "govt-jobs").exists():                # the old boxed index page
        shutil.rmtree(SITE / "govt-jobs")
    hubs = []
    pages = [(f"{slug}-govt-jobs", en, hi, {"st": slug}, [en.lower(), hi, slug.replace("-", " ")], "state") for slug, en, hi, _ in STATES]
    pages += [(f"{slug}-govt-jobs", en, hi, {"q": tagv}, words, "qual") for slug, tagv, en, hi, words in QUALS]
    for s_, en, hi, preset, words, kind in pages:
        title = f"{en} Govt Jobs {YEAR}: Latest Vacancy, Notification, Last Date | SarkariChart"
        desc = (f"Latest {en} government jobs {YEAR} from official notices: open vacancies with last dates, eligibility and direct "
                f"official links, in English and Hindi.")
        url = f"{SITE_URL}/{s_}/"
        h = home
        h = re.sub(r"<title>.*?</title>", f"<title>{html.escape(title)}</title>", h, count=1, flags=re.S)
        h = re.sub(r'<meta name="description" content="[^"]*">', f'<meta name="description" content="{html.escape(desc)}">', h, count=1)
        h = re.sub(r'<link rel="canonical" href="[^"]*">', f'<link rel="canonical" href="{url}">', h, count=1)
        h = re.sub(r'<meta property="og:url" content="[^"]*">', f'<meta property="og:url" content="{url}">', h, count=1)
        h = re.sub(r'<meta property="og:title" content="[^"]*">', f'<meta property="og:title" content="{html.escape(title)}">', h, count=1)
        hi_title = f"{hi} सरकारी नौकरी {YEAR} | सरकारी चार्ट"
        h = h.replace('document.title = t("title");', f'document.title = lang === "hi" ? {json.dumps(hi_title, ensure_ascii=False)} : {json.dumps(title)};', 1)
        h = h.replace("</head>", f"<script>window.SC_PRESET = {json.dumps(preset)};</script>\n</head>", 1)
        h = h.replace("  <main>\n", f'  <main>\n    <h1 class="hubh"><span class="x-en">{html.escape(en)} govt jobs {YEAR}</span><span class="x-hi" lang="hi">{html.escape(hi)} सरकारी नौकरी {YEAR}</span></h1>\n', 1)
        d = SITE / s_
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(h, encoding="utf-8")
        hubs.append({"kind": kind, "slug": s_, "en": en, "hi": hi, "n": 0, "words": words})
    homepage_hints(hubs)
    print(f"hubs: {len(hubs)} browse pages (homepage with a filter set)")


def homepage_hints(hubs):
    """Search words that point to a browse page: typing "10th pass" or "UP" on the homepage shows one quiet link line."""
    p = SITE / "index.html"
    s = p.read_text(encoding="utf-8")
    data = json.dumps([{"slug": h["slug"], "en": h["en"], "hi": h["hi"], "kind": h["kind"], "words": h["words"]} for h in hubs], ensure_ascii=False).replace("</", "<\\/")
    s = re.sub(r"/\*HUBS:START\*/.*?/\*HUBS:END\*/", lambda m: "/*HUBS:START*/" + data + "/*HUBS:END*/", s, count=1, flags=re.S)
    p.write_text(s, encoding="utf-8")


if __name__ == "__main__":
    {"tag": tag, "build": build}.get(sys.argv[1] if len(sys.argv) > 1 else "build", build)()
