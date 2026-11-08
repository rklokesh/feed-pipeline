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
    ("bihar", "Bihar", "बिहार", ["bpsc", "bssc", "csbc", "bpssc"]),
    ("rajasthan", "Rajasthan", "राजस्थान", ["rpsc", "rssb"]),
    ("mp", "MP", "एमपी", ["mppsc", "mpesb"]),
    ("haryana", "Haryana", "हरियाणा", ["hpsc", "hssc"]),
    ("delhi", "Delhi", "दिल्ली", ["dsssb"]),
    ("punjab", "Punjab", "पंजाब", ["psssb", "ppsc"]),
    ("jammu-kashmir", "J&K", "जम्मू-कश्मीर", ["jkssb", "jkpsc"]),
    ("jharkhand", "Jharkhand", "झारखंड", ["jpsc", "jssc"]),
    ("chhattisgarh", "Chhattisgarh", "छत्तीसगढ़", ["cgpsc", "cgvyapam"]),
    ("uttarakhand", "Uttarakhand", "उत्तराखंड", ["ukpsc", "uksssc"]),
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
    # Desktop A/B: version B (phone-style chrome) at /v2/ - same homepage, never indexed, canonical to /.
    v2 = re.sub(r'<link rel="canonical" href="[^"]*">', f'<link rel="canonical" href="{SITE_URL}/">', home, count=1)
    v2 = re.sub(r'<meta name="robots" content="[^"]*">', '<meta name="robots" content="noindex, follow">', v2, count=1)
    (SITE / "v2").mkdir(exist_ok=True)
    (SITE / "v2" / "index.html").write_text(v2, encoding="utf-8")
    # Homepage A/B, version "hero" at /b/ (never indexed, canonical to /): a calm search-first top - a big line, one search box,
    # a faint background of board names - then the same tabs and list. The live homepage is not touched.
    hv = re.sub(r'<link rel="canonical" href="[^"]*">', f'<link rel="canonical" href="{SITE_URL}/">', home, count=1)
    hv = re.sub(r'<meta name="robots" content="[^"]*">', '<meta name="robots" content="noindex, follow">', hv, count=1)
    m = re.search(r'    <label class="search" for="q">.*?</label>\n', hv, flags=re.S)
    if m and "  <main>\n" in hv:
        search = m.group(0)
        hv = hv.replace(search, "", 1)
        boards = ("SSC UPSC RRB IBPS SBI UPPSC BPSC RPSC MPPSC HPSC UKPSC JPSC CGPSC OSSC WBPSC PSSSB HSSC UPSSSC BSSC RSSB "
                  "DSSSB NTA CTET KVS NVS BSF CRPF CISF ITBP SSB AIIMS ESIC DRDO ISRO BARC NIA CWC RRC LIC NABARD RBI SEBI "
                  "JKSSB UKSSSC BPSSC JSSC HPRCA MPESB UPPRPB BPSSC Railway Police Teacher Clerk Constable Patwari Lekhpal "
                  "Bank PO Clerk SI ASI Driver Nurse Pharmacist Anganwadi Steno Typist JE AE GD CHSL CGL MTS NTPC Group-D").split()
        import random
        rnd = random.Random(7)
        words = " ".join(f"<span>{rnd.choice(boards)}</span>" for _ in range(900))
        stamps = re.findall(r'"publishedAt": "([^"]+)"', hv)
        latest = max(stamps) if stamps else ""
        count = len(re.findall(r'\{"type": "', hv)) // 50 * 50 or len(re.findall(r'\{"type": "', hv))
        hero = ('    <section class="hero" aria-label="Search">\n'
                f'      <div class="hero-bg" aria-hidden="true">{words}</div>\n'
                '      <p class="hero-live"><span class="dot" aria-hidden="true"></span><span class="x-en">Live · watching 50+ official boards</span>'
                '<span class="x-hi" lang="hi">लाइव · 50+ आधिकारिक बोर्ड पर नज़र</span></p>\n'
                '      <h2 class="hero-h"><span class="x-en" aria-label="Govt jobs, admit cards and results, without the clutter">'
                '<span aria-hidden="true">Govt <span class="rx" data-alt="नौकरी">jobs</span>, admit cards and <span class="rx" data-alt="रिज़ल्ट">results</span>, <br>'
                'without the <span class="rx" data-alt="झंझट">clutter</span></span></span>'
                '<span class="x-hi" lang="hi" aria-label="सरकारी नौकरी, एडमिट कार्ड और रिज़ल्ट, बिना किसी झंझट के"><span aria-hidden="true">'
                'सरकारी <span class="rx" data-alt="jobs">नौकरी</span>, एडमिट कार्ड और <span class="rx" data-alt="results">रिज़ल्ट</span>, <br>'
                'बिना किसी <span class="rx" data-alt="clutter">झंझट</span> के</span></span></h2>\n'
                + search.replace("    <label", "      <label", 1) +
                f'      <p class="hero-sub g" id="heroSub" data-ts="{latest}" data-n="{count}"><span class="x-en">{count}+ notices · free, no sign-up</span>'
                f'<span class="x-hi" lang="hi">{count}+ सूचनाएँ · मुफ़्त, बिना साइन-अप</span></p>\n'
                '    </section>\n')
        hv = hv.replace("  <main>\n", "  <main>\n" + hero, 1)
        css = """<style>
html.hv body { overflow-x: clip; }
html.hv .hero { position: relative; margin: 0 calc(50% - 50vw) 30px; padding: 88px 16px 72px; text-align: center; }
html.hv .hero-bg { position: absolute; inset: 0; padding: 10px; overflow: hidden; pointer-events: none; user-select: none; -webkit-user-select: none; text-align: left;
  font: 12px/24px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; letter-spacing: .02em; word-spacing: 16px;
  /* one soft fade: clear in the middle, easing out to every edge (no hard top, bottom or side) */
  -webkit-mask-image: radial-gradient(ellipse 62% 58% at 50% 50%, transparent 0, transparent 40%, rgba(0,0,0,.25) 58%, rgba(0,0,0,.7) 78%, #000 100%),
                      linear-gradient(to bottom, transparent 0, #000 22%, #000 72%, transparent 100%),
                      linear-gradient(to right, transparent 0, #000 12%, #000 88%, transparent 100%);
  -webkit-mask-composite: source-in, source-in;
          mask-image: radial-gradient(ellipse 62% 58% at 50% 50%, transparent 0, transparent 40%, rgba(0,0,0,.25) 58%, rgba(0,0,0,.7) 78%, #000 100%),
                      linear-gradient(to bottom, transparent 0, #000 22%, #000 72%, transparent 100%),
                      linear-gradient(to right, transparent 0, #000 12%, #000 88%, transparent 100%);
          mask-composite: intersect, intersect; }
html.hv .hero-bg span { color: color-mix(in srgb, var(--grey) 30%, transparent); transition: color 1.1s ease, opacity 1.1s ease; }
html.hv .hero-bg span.on { color: color-mix(in srgb, #E8312F 75%, transparent); transition-duration: .2s; }
html.hv .hero-bg span.dim { opacity: .25; transition-duration: .35s; }
html.hv .hero-h { position: relative; margin: 0 auto 30px; max-width: 22em; font-size: clamp(1.6rem, 1rem + 3.2vw, 3.25rem); font-weight: 600; line-height: 1.06; letter-spacing: -0.03em; color: var(--ink); text-wrap: balance; }
html.hv .hero-live { position: relative; display: inline-flex; align-items: center; gap: 9px; margin: 0 0 22px; padding: 6px 14px 6px 12px; border-radius: 999px;
  background: color-mix(in srgb, var(--page) 85%, transparent); border: 1px solid var(--line); font-size: .875rem; color: var(--ink); }
html.hv .hero-live .dot { position: relative; width: 8px; height: 8px; border-radius: 50%; background: #1FA855; flex: none; }
html.hv .hero-live .dot::after { content: ""; position: absolute; inset: 0; border-radius: 50%; background: #1FA855; animation: hv-ping 1.8s cubic-bezier(0, 0, .2, 1) infinite; }
@keyframes hv-ping { 0% { transform: scale(1); opacity: .6; } 80%, 100% { transform: scale(2.8); opacity: 0; } }
@media (prefers-reduced-motion: reduce) { html.hv .hero-live .dot::after { animation: none; } }
@media (max-width: 640px) { html.hv .hero-live { font-size: .8125rem; margin-bottom: 16px; padding: 5px 12px 5px 10px; } }
html.hv .rx { position: relative; display: inline-block; }
html.hv .rx .o { visibility: hidden; }
html.hv .rx .a { position: absolute; left: 50%; top: 0; transform: translateX(-50%); white-space: nowrap; color: #E8312F; transition: color .8s ease; }
html.hv .hero .search { position: relative; max-width: 560px; margin: 0 auto !important; text-align: left; }
html.hv .hero .search input { background: var(--page) !important; border: 1px solid color-mix(in srgb, var(--ink) 28%, transparent) !important; border-radius: 10px !important;
  padding: 13px 92px 13px 44px !important; box-shadow: 0 1px 2px rgba(0,0,0,.04), 0 8px 24px -12px rgba(0,0,0,.18); }
html.hv .hero .search input:focus { border-color: var(--ink) !important; }
html.hv .hero .sicon { left: 14px !important; } html.hv .hero .ph { left: 44px !important; right: 92px !important; } html.hv .hero .sx { right: 14px !important; }
html.hv .hero-sub { position: relative; margin: 16px 0 0; font-size: .875rem; }
html.hv .tabrow { margin-top: 0; }
@media (max-width: 640px) { html.hv .hero { padding: 52px 16px 44px; margin-bottom: 18px; } html.hv .hero-h { margin-bottom: 22px; } html.hv .hero-h br { display: none; } html.hv .hero-bg { font-size: 10px; line-height: 20px; word-spacing: 10px; } html.hv .hero-bg span { color: color-mix(in srgb, var(--grey) 22%, transparent); } }
</style>
<script>document.documentElement.classList.add("hv")</script>
<script>addEventListener("DOMContentLoaded",function(){var p=document.getElementById("heroSub");if(!p||!p.dataset.ts)return;
function paint(){var m=Math.max(1,Math.round((Date.now()-Date.parse(p.dataset.ts))/6e4)),n=p.dataset.n,
en=m<60?m+" min ago":Math.round(m/60)+" h ago",hi=m<60?m+" मिनट पहले":Math.round(m/60)+" घंटे पहले";if(m>=1440)return;
p.children[0].textContent="Updated "+en+" · "+n+"+ notices · free, no sign-up";p.children[1].textContent=hi+" अपडेट · "+n+"+ सूचनाएँ · मुफ़्त, बिना साइन-अप"}
paint();setInterval(paint,60000)});</script>
<script>/* Heading "remix": now and then one word scrambles through Devanagari / Latin letters into its other-language twin
   (jobs -> नौकरी), holds a moment in the logo red, then scrambles back. The line never moves (the twin is drawn over the
   word's own space). One word at a time; off when motion is off. */
addEventListener("DOMContentLoaded",function(){if(matchMedia("(prefers-reduced-motion: reduce)").matches)return;
var POOL="कखगघचजटडतदनपबमयरलवशसहअआइउएओ".split("").concat("ABCDEFGHJKLMNPRSTUVWXYZ".split("")),
SEG=window.Intl&&Intl.Segmenter?new Intl.Segmenter(undefined,{granularity:"grapheme"}):null,
G=function(w){return SEG?Array.from(SEG.segment(w),function(x){return x.segment}):Array.from(w)};
function scramble(a,to,done){var g=G(to),n=0,steps=9;var iv=setInterval(function(){n++;var k=Math.floor(g.length*n/steps),s="";
for(var i=0;i<g.length;i++)s+=i<k?g[i]:POOL[Math.random()*POOL.length|0];a.textContent=s;if(n>=steps){clearInterval(iv);a.textContent=to;done&&done()}},50)}
var h=document.querySelector(".hero-h");if(!h)return;var vis=true,busy=false;
if("IntersectionObserver"in window)new IntersectionObserver(function(e){vis=e[0].isIntersecting}).observe(h);
function tick(){if(busy||!vis||document.hidden)return;var ws=[].filter.call(h.querySelectorAll(".rx"),function(e){return e.offsetParent});if(!ws.length)return;
var el=ws[Math.random()*ws.length|0],orig=el.dataset.orig||(el.dataset.orig=el.textContent);busy=true;
el.innerHTML='<span class="o"></span><span class="a"></span>';el.firstChild.textContent=orig;var a=el.lastChild;
scramble(a,el.dataset.alt,function(){setTimeout(function(){scramble(a,orig,function(){a.style.color="inherit";setTimeout(function(){el.textContent=orig;busy=false},800)})},1700)})}
setTimeout(function(){tick();setInterval(tick,5600)},1500)});</script>
<script>addEventListener("DOMContentLoaded",function(){var bg=document.querySelector(".hero-bg");if(!bg||matchMedia("(prefers-reduced-motion: reduce)").matches)return;
var ws=bg.children,vis=true;if("IntersectionObserver"in window)new IntersectionObserver(function(e){vis=e[0].isIntersecting}).observe(bg);
setInterval(function(){if(!vis||document.hidden)return;var n=2+(Math.random()*3|0);for(var k=0;k<n;k++){var w=ws[Math.random()*ws.length|0],c=Math.random()<.7?"on":"dim";
w.classList.add(c);(function(w,c){setTimeout(function(){w.classList.remove(c)},250+Math.random()*1100)})(w,c)}},150)});</script>
"""
        hv = hv.replace("</head>", css + "</head>", 1)
    (SITE / "b").mkdir(exist_ok=True)
    (SITE / "b" / "index.html").write_text(hv, encoding="utf-8")
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
