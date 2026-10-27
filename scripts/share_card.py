"""What goes on a notice's share image (og.png / og-hi.png, drawn by scripts/og_card.mjs).

Six bands: brand · two tag pairs · organisation logo + name · post/exam line · headline · call to action.
The words depend on the notice kind (job, admit card, result, answer key, corrigendum). Facts only from the
notice data; when something is unknown it is simply left out (no count → just the post name; no logo → name only).
"""
from __future__ import annotations

import datetime as dt
import re

# source id prefix → (logo file in assets/org/, short name EN, short name HI). Logos are the boards' own, unmodified
# (only blank margins trimmed and scaled down); add a board by dropping <key>.png in assets/org/ and a line here.
BOARDS = [
    ("upsc", "upsc", "UPSC", "यूपीएससी"), ("ssc", "ssc", "SSC", "एसएससी"), ("ibps", "ibps", "IBPS", "आईबीपीएस"),
    ("nta", "nta", "NTA", "एनटीए"), ("rrb", "rrb", "RRB", "आरआरबी"), ("rrc", "rrb", "RRC", "आरआरसी"),
    ("sbi", "sbi", "SBI", "एसबीआई"), ("rbi", "rbi", "RBI", "आरबीआई"), ("nabard", "nabard", "NABARD", "नाबार्ड"),
    ("lic", "lic", "LIC", "एलआईसी"), ("army", "army", "Indian Army", "भारतीय सेना"), ("navy", "navy", "Indian Navy", "भारतीय नौसेना"),
    ("iaf", "iaf", "Air Force", "वायु सेना"), ("coast-guard", "coastguard", "Coast Guard", "तटरक्षक बल"),
    ("bsf", "bsf", "BSF", "बीएसएफ"), ("crpf", "crpf", "CRPF", "सीआरपीएफ"), ("itbp", "itbp", "ITBP", "आईटीबीपी"),
    ("cisf", "cisf", "CISF", "सीआईएसएफ"), ("drdo", "drdo", "DRDO", "डीआरडीओ"), ("isro", "isro", "ISRO", "इसरो"),
    ("uppsc", "uppsc", "UPPSC", "यूपीपीएससी"), ("upsssc", "upsssc", "UPSSSC", "यूपीएसएसएससी"),
    ("uppbpb", "uppolice", "UP Police", "यूपी पुलिस"), ("bpsc", "bpsc", "BPSC", "बीपीएससी"), ("bssc", "bssc", "BSSC", "बीएसएससी"),
    ("csbc", "csbc", "CSBC", "सीएसबीसी"), ("rpsc", "rpsc", "RPSC", "आरपीएससी"), ("rssb", "rssb", "RSSB", "आरएसएसबी"),
    ("mppsc", "mppsc", "MPPSC", "एमपीपीएससी"), ("mpesb", "mpesb", "MPESB", "एमपीईएसबी"), ("dsssb", "dsssb", "DSSSB", "डीएसएसएसबी"),
    ("ukpsc", "ukpsc", "UKPSC", "यूकेपीएससी"), ("hpsc", "hpsc", "HPSC", "एचपीएससी"), ("hssc", "hssc", "HSSC", "एचएसएससी"),
    ("wbpsc", "wbpsc", "WBPSC", "डब्ल्यूबीपीएससी"), ("mpsc", "mpsc", "MPSC", "एमपीएससी"), ("tnpsc", "tnpsc", "TNPSC", "टीएनपीएससी"),
    ("ctet", "ctet", "CTET", "सीटीईटी"), ("kvs", "kvs", "KVS", "केवीएस"), ("indiapost", "indiapost", "India Post", "इंडिया पोस्ट"),
    ("employment-news", "", "Employment News", "रोज़गार समाचार"), ("ncs", "", "NCS", "एनसीएस"),
]

# (pattern on the English title, headline EN, headline HI, kind override). First match wins; {y} = year.
HEADLINES = [
    (r"extend|extension", "Last Date Extended", "अंतिम तिथि बढ़ी", "corr"),
    (r"postpone|reschedul|revised date|date change|dates? revised", "Exam Date Changed", "परीक्षा तिथि बदली", "corr"),
    (r"vacanc\w* (reduction|deleted|reduced|increase)|reduction", "Vacancies Changed", "पदों में बदलाव", "corr"),
    (r"corrigendum|amendment|addendum|errata", "Corrigendum {y}", "शुद्धि पत्र {y}", "corr"),
    (r"tentative vacanc", "Tentative Vacancies {y}", "संभावित रिक्तियाँ {y}", None),
    (r"document verification|\bdv\b", "DV Schedule {y}", "दस्तावेज़ सत्यापन {y}", "sched"),
    (r"interview", "Interview Schedule {y}", "साक्षात्कार कार्यक्रम {y}", "sched"),
    (r"cut-?\s?off", "Cut-Off {y}", "कट-ऑफ {y}", None),
    (r"final answer key", "Final Answer Key {y}", "अंतिम उत्तर कुंजी {y}", None),
    (r"answer key", "Answer Key {y}", "उत्तर कुंजी {y}", None),
    (r"reserve list", "Reserve List {y}", "आरक्षित सूची {y}", None),
    (r"disqualif", "Disqualified List {y}", "अयोग्य सूची {y}", None),
    (r"final (result|selection)|selection list", "Final Result {y}", "अंतिम परिणाम {y}", None),
    (r"\bmarks\b", "Marks Released {y}", "अंक जारी {y}", None),
    (r"city|intimation slip", "Exam City Slip {y}", "परीक्षा शहर सूचना {y}", None),
    (r"online form|application form", "Apply Online {y}", "ऑनलाइन आवेदन {y}", None),
]
DEFAULT = {"Job": ("Recruitment {y}", "भर्ती {y}"), "Admit card": ("Admit Card {y}", "एडमिट कार्ड {y}"),
           "Result": ("Result {y}", "परिणाम {y}"), "Answer key": ("Answer Key {y}", "उत्तर कुंजी {y}")}
KIND = {"Job": "job", "Admit card": "admit", "Result": "result", "Answer key": "answer"}
TAGS = {  # band 2: left pair | right pair
    "job": (("LAST DATE | FEE", "ELIGIBILITY | APPLY"), ("अंतिम तिथि | शुल्क", "पात्रता | आवेदन")),
    "admit": (("EXAM DATE | CENTRE", "DOWNLOAD | GUIDE"), ("परीक्षा तिथि | केंद्र", "डाउनलोड | निर्देश")),
    "result": (("CUT-OFF | MERIT", "DOWNLOAD | NEXT"), ("कट-ऑफ | मेरिट", "डाउनलोड | आगे क्या")),
    "answer": (("OBJECTION | DATES", "DOWNLOAD | PDF"), ("आपत्ति | तिथियाँ", "डाउनलोड | पीडीएफ")),
    "corr": (("WHAT CHANGED", "NEW DATES"), ("क्या बदला", "नई तिथियाँ")),
    "sched": (("DATE | VENUE", "DOCUMENTS | DETAILS"), ("तिथि | स्थान", "दस्तावेज़ | जानकारी")),
}
CTA = {
    "job": ("APPLY ONLINE · FULL DETAILS", "ऑनलाइन आवेदन · पूरी जानकारी"),
    "admit": ("DOWNLOAD ADMIT CARD · DIRECT LINK", "एडमिट कार्ड डाउनलोड · सीधा लिंक"),
    "result": ("CHECK RESULT · DIRECT LINK", "रिज़ल्ट देखें · सीधा लिंक"),
    "answer": ("DOWNLOAD ANSWER KEY · RAISE OBJECTION", "आंसर की डाउनलोड · आपत्ति दर्ज करें"),
    "corr": ("CHECK REVISED DETAILS · FULL INFO", "बदली हुई जानकारी देखें · पूरी जानकारी"),
    "sched": ("CHECK SCHEDULE · FULL DETAILS", "कार्यक्रम देखें · पूरी जानकारी"),
}
DEVANAGARI = re.compile(r"[\u0900-\u097F]")
# board names and notice-type words that repeat what the card already shows elsewhere
HI_NOISE = re.compile(r"(कर्मचारी चयन आयोग|लोक सेवा आयोग|रेलवे भर्ती बोर्ड|हरियाणा|उत्तर प्रदेश पुलिस|उत्तर प्रदेश|मध्य प्रदेश|उत्तराखंड|"
                      r"मप्रलोसे|आरपीएससी|नाबार्ड|बीएसएफ|आईटीबीपी|आईबीपीएस|आरआरसी|एसएससी|पश्चिमी रेलवे|पश्चिम रेलवे|"
                      r"एडमिट कार्ड|परिणाम|उत्तर कुंजी|आंसर की|भर्ती|अंतिम|अधिसूचना|सूचना|जारी)")
EN_NOISE = re.compile(r"\b(recruitment|notification|notice|result|results|admit card|answer key|final|released|declared|exam|"
                      r"examination|online form|corrigendum|20\d\d(-\d\d)?)\b", re.I)


def board(source_id: str):
    s = source_id or ""
    for pre, logo, en, hi in BOARDS:
        if s == pre or s.startswith(pre + "-"):
            return logo, en, hi
    return "", "", ""


def count(v) -> int | None:
    m = re.fullmatch(r"\s*([\d,]+)\s*", str(v or ""))
    if not m:
        return None
    n = int(m.group(1).replace(",", ""))
    return n if n > 0 else None


def short(s: str, limit: int = 44) -> str:
    """A post/exam name short enough for one line: first item of a list, no trailing brackets when long."""
    s = re.sub(r"\s+", " ", str(s or "")).strip(" ,;-–")
    if len(s) > limit and "," in s:
        s = s.split(",")[0].strip()
    if len(s) > limit:
        s = re.sub(r"\s*\([^)]*\)\s*$", "", s)
    if len(s) > limit:
        s = s[:limit].rsplit(" ", 1)[0].rstrip(" ,&-–(")
    return s


def share_data(n: dict, d_en, d_hi, valid_date) -> dict:
    c, pg = n.get("card") or {}, n.get("page") or {}
    sc = pg.get("share_card") or {}          # written by the AI for pages built after Oct 2026
    typ = c.get("type") or "Job"
    title = pg.get("h1_en") or c.get("title_en") or n.get("title") or ""
    years = re.findall(r"\b(20\d\d)\b", title)
    y = years[-1] if years else (n.get("notice_date") or "")[:4]
    kind = KIND.get(typ, "job")
    head_en, head_hi = DEFAULT.get(typ, DEFAULT["Job"])
    for pat, en, hi, k in HEADLINES:
        if re.search(pat, title, re.I):
            head_en, head_hi = en, hi
            kind = k or kind
            break
    if sc.get("kind") in TAGS:
        kind = sc["kind"]
    head_en = sc.get("headline_en") or head_en.format(y=y).strip()
    head_hi = sc.get("headline_hi") or head_hi.format(y=y).strip()

    vac = pg.get("vacancies") or []
    line_en = sc.get("line_en") or short(c.get("posts") or (vac[0].get("post_en") if vac else "") or "")
    if not line_en or DEVANAGARI.search(line_en):  # no English post name: the title without board and type words
        line_en = short(re.sub(r"\s+", " ", EN_NOISE.sub("", title.replace(board(n.get("source_id", ""))[1] or "\0", ""))))
    line_hi = sc.get("line_hi") or ""
    if not line_hi and vac:
        line_hi = short(vac[0].get("post_hi") or "", 40)
    if not line_hi or not DEVANAGARI.search(line_hi):  # last resort: the Hindi title without board, type words and year
        t = HI_NOISE.sub("", re.sub(r"\b20\d\d\b", "", pg.get("h1_hi") or c.get("title_hi") or ""))
        line_hi = short(re.sub(r"\s+", " ", t), 40)
    posts = count(sc.get("posts")) if sc.get("posts") is not None else None
    if posts is None and kind == "job":
        posts = count(c.get("vacancies"))
        if posts is None and vac:
            nums = [count(v.get("total")) for v in vac]
            posts = sum(nums) if nums and all(nums) else None

    logo, org_en, org_hi = board(n.get("source_id", ""))
    org_en = org_en or (n.get("org") or "")
    org_hi = org_hi or org_en
    last = valid_date(pg.get("last_date") or c.get("last_date")) if kind == "job" else None
    exam = valid_date(pg.get("exam_date") or c.get("exam_date")) if kind == "admit" else None
    cta_en, cta_hi = CTA[kind]
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30))).date().isoformat()
    if last and str(last) < today:  # applications closed: never invite people to apply
        cta_en, cta_hi = "APPLICATIONS CLOSED · FULL DETAILS", "आवेदन बंद · पूरी जानकारी"
    elif last:
        cta_en, cta_hi = f"APPLY ONLINE · LAST DATE {d_en(last).upper()}", f"ऑनलाइन आवेदन · अंतिम तिथि {d_hi(last)}"
    (tl_en, tr_en), (tl_hi, tr_hi) = TAGS[kind]
    return {"logo": logo, "kind": kind, "posts": posts,
            "en": {"org": org_en, "tagL": tl_en, "tagR": tr_en, "line": line_en, "headline": head_en, "cta": cta_en,
                   "exam": d_en(exam) if exam else ""},
            "hi": {"org": org_hi, "tagL": tl_hi, "tagR": tr_hi, "line": line_hi, "headline": head_hi, "cta": cta_hi,
                   "exam": d_hi(exam) if exam else ""}}
