"""Standalone SEO landing pages by job type: /central-govt-jobs/, /railway-jobs/, /police-jobs/, /bank-jobs/, /teacher-jobs/, /defence-jobs/.

Each page is a calm article built from the live notice list (site/index.html ITEMS), so it is never stale:
  heading + short intro, "open now" jobs with last dates, latest admit cards / results / updates for that field,
  a few plain FAQs, and links to the other pages. English + Hindi on the same URL (like every page).
Run after publish.py build (it reads the freshly written homepage list): python3 scripts/seo_pages.py
"""
from __future__ import annotations

import datetime as dt
import html
import json
import os
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
TPL = (ROOT / "templates/notice.html").read_text(encoding="utf-8")
SITE_URL = os.environ.get("SITE_URL", "https://sarkarichart.com")
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
YEAR = dt.datetime.now(IST).year

# slug, (name EN, HI), match(item) -> bool, (intro EN, HI), [(q EN, a EN, q HI, a HI)]
def rx(p):
    r = re.compile(p, re.I)
    return lambda i: bool(r.search(f'{i.get("title", "")} {i.get("org", "")}'))

PAGES = [
    ("central-govt-jobs", ("Central Govt Jobs", "केंद्र सरकार की नौकरियाँ"), lambda i: not i.get("st"),
     ("Every open central government job in one list: UPSC, SSC, railways, banks, defence, central police forces, NTA and central ministries. Last dates and official links on every notice.",
      "केंद्र सरकार की हर खुली भर्ती एक जगह: यूपीएससी, एसएससी, रेलवे, बैंक, रक्षा, केंद्रीय पुलिस बल, एनटीए और केंद्रीय मंत्रालय। हर सूचना पर अंतिम तिथि और आधिकारिक लिंक।"),
     [("Who can apply for central government jobs?", "Any Indian citizen who meets the age and qualification printed in that notice. Most central jobs are open to candidates from every state.",
       "केंद्र सरकार की नौकरियों के लिए कौन आवेदन कर सकता है?", "हर वह भारतीय नागरिक जो उस सूचना में दी गई आयु और योग्यता पूरी करता है। ज़्यादातर केंद्रीय नौकरियाँ हर राज्य के उम्मीदवारों के लिए खुली होती हैं।"),
      ("Where do I apply?", "Only on the official website named in the notice. Each notice on SarkariChart links to it directly.",
       "आवेदन कहाँ करें?", "सिर्फ़ सूचना में दी गई आधिकारिक वेबसाइट पर। सरकारी चार्ट पर हर सूचना में उसका सीधा लिंक है।")]),
    ("railway-jobs", ("Railway Jobs", "रेलवे भर्ती"), rx(r"\bRRB\b|\bRRC\b|railway|रेलवे"),
     ("All open railway recruitment from RRB and RRC: NTPC, Group D, ALP, JE, apprentices and more, with last dates, admit cards and results.",
      "आरआरबी और आरआरसी की सभी खुली रेलवे भर्तियाँ: एनटीपीसी, ग्रुप डी, एएलपी, जेई, अप्रेंटिस और अन्य, अंतिम तिथि, एडमिट कार्ड और रिज़ल्ट के साथ।"),
     [("How are railway jobs filled?", "Most posts are filled by the Railway Recruitment Boards (RRB) through a common notice (CEN), and some posts and apprentices by the Railway Recruitment Cells (RRC) of each zone.",
       "रेलवे की नौकरियाँ कैसे भरी जाती हैं?", "ज़्यादातर पद रेलवे भर्ती बोर्ड (आरआरबी) एक साझा सूचना (सीईएन) से भरते हैं, और कुछ पद व अप्रेंटिस हर ज़ोन के रेलवे भर्ती प्रकोष्ठ (आरआरसी) भरते हैं।"),
      ("Can I apply to more than one RRB?", "For an RRB notice you choose one RRB. Applying to more than one usually leads to rejection; the notice says this clearly.",
       "क्या मैं एक से ज़्यादा आरआरबी में आवेदन कर सकता हूँ?", "आरआरबी की सूचना में आप एक ही आरआरबी चुनते हैं। एक से ज़्यादा में आवेदन करने पर आमतौर पर आवेदन रद्द हो जाता है; सूचना में यह साफ़ लिखा होता है।")]),
    ("police-jobs", ("Police Jobs", "पुलिस भर्ती"), rx(r"police|constable|sub[- ]?inspector|\bSI\b|warder|prahari|home guard|\bCAPF\b|\bBSF\b|\bCRPF\b|\bCISF\b|\bITBP\b|\bSSB\b|पुलिस|सिपाही"),
     ("Open police and armed police recruitment from state police boards and central forces (BSF, CRPF, CISF, ITBP, SSB): constable, SI, head constable and more.",
      "राज्य पुलिस भर्ती बोर्ड और केंद्रीय बलों (बीएसएफ, सीआरपीएफ, सीआईएसएफ, आईटीबीपी, एसएसबी) की खुली पुलिस भर्तियाँ: कांस्टेबल, एसआई, हेड कांस्टेबल और अन्य।"),
     [("Is there a physical test?", "Almost always: police and armed police jobs usually include a physical standards test (height, chest) and a physical efficiency test (running). The exact standards are in each notice.",
       "क्या शारीरिक परीक्षा होती है?", "लगभग हमेशा: पुलिस भर्ती में आमतौर पर शारीरिक मानक परीक्षा (लंबाई, सीना) और शारीरिक दक्षता परीक्षा (दौड़) होती है। सही मानक हर सूचना में दिए होते हैं।"),
      ("Do state police jobs need state domicile?", "Many state police notices give reservation or eligibility only to residents of that state. Check the domicile line in the notice.",
       "क्या राज्य पुलिस भर्ती के लिए उसी राज्य का निवासी होना ज़रूरी है?", "कई राज्य पुलिस सूचनाओं में आरक्षण या पात्रता सिर्फ़ उसी राज्य के निवासियों को मिलती है। सूचना में निवास वाली पंक्ति देखें।")]),
    ("bank-jobs", ("Bank Jobs", "बैंक भर्ती"), rx(r"\bbank\b|\bIBPS\b|\bSBI\b|\bRBI\b|NABARD|SIDBI|gramin|co-?operative bank|बैंक"),
     ("Open bank recruitment from IBPS, SBI, RBI, NABARD, regional rural banks and cooperative banks: PO, clerk, specialist officer and more.",
      "आईबीपीएस, एसबीआई, आरबीआई, नाबार्ड, क्षेत्रीय ग्रामीण बैंक और सहकारी बैंकों की खुली भर्तियाँ: पीओ, क्लर्क, स्पेशलिस्ट ऑफ़िसर और अन्य।"),
     [("What qualification do bank jobs need?", "Most PO and clerk posts need a graduate degree. Specialist officer posts ask for the subject degree printed in the notice.",
       "बैंक की नौकरियों के लिए कौन-सी योग्यता चाहिए?", "ज़्यादातर पीओ और क्लर्क पदों के लिए स्नातक डिग्री चाहिए। स्पेशलिस्ट ऑफ़िसर पदों के लिए सूचना में दी गई विषय की डिग्री चाहिए।")]),
    ("teacher-jobs", ("Teacher Jobs", "शिक्षक भर्ती"), rx(r"teacher|\bTGT\b|\bPGT\b|\bPRT\b|lecturer|professor|\bKVS\b|\bNVS\b|shikshak|\bTET\b|CTET|instructor|principal|शिक्षक|अध्यापक|प्रवक्ता"),
     ("Open teaching jobs: school teachers (PRT, TGT, PGT), lecturers and professors from KVS, NVS, state boards and public service commissions, plus TET and CTET updates.",
      "खुली शिक्षक भर्तियाँ: केवीएस, एनवीएस, राज्य बोर्ड और लोक सेवा आयोगों से स्कूल शिक्षक (पीआरटी, टीजीटी, पीजीटी), प्रवक्ता और प्रोफ़ेसर, साथ में टीईटी और सीटीईटी अपडेट।"),
     [("Do I need TET or CTET?", "Most school teacher jobs ask for a TET or CTET pass along with the teaching qualification (D.El.Ed or B.Ed). The notice lists exactly which.",
       "क्या टीईटी या सीटीईटी ज़रूरी है?", "ज़्यादातर स्कूल शिक्षक भर्ती में शिक्षण योग्यता (डी.एल.एड या बी.एड) के साथ टीईटी या सीटीईटी पास होना माँगा जाता है। सूचना में सटीक जानकारी होती है।")]),
    ("defence-jobs", ("Defence Jobs", "रक्षा भर्ती"), rx(r"\barmy\b|\bnavy\b|air force|agniveer|coast guard|defence|\bDRDO\b|AFCAT|\bNDA\b|\bCDS\b|territorial|military|ordnance|सेना|नौसेना|वायुसेना|अग्निवीर"),
     ("Open defence recruitment: Army, Navy, Air Force, Agniveer, Coast Guard, NDA/CDS and civilian posts in defence organisations like DRDO.",
      "खुली रक्षा भर्तियाँ: थल सेना, नौसेना, वायुसेना, अग्निवीर, तटरक्षक, एनडीए/सीडीएस और डीआरडीओ जैसे रक्षा संगठनों के सिविलियन पद।"),
     [("Are there civilian jobs in defence?", "Yes. Defence organisations also hire civilians (clerks, technicians, scientists) through their own notices; these have no physical test unless the notice says so.",
       "क्या रक्षा क्षेत्र में सिविलियन नौकरियाँ भी हैं?", "हाँ। रक्षा संगठन अपनी सूचनाओं से सिविलियन (क्लर्क, तकनीशियन, वैज्ञानिक) भी भर्ती करते हैं; इनमें शारीरिक परीक्षा नहीं होती जब तक सूचना में न लिखा हो।")]),
]

# One page per kind of notice (the sections Google can show as sitelinks under the site's result).
# (slug, (name EN, HI), type, (lead EN, HI), faq, (title EN, title HI))
TYPE_PAGES = [
    ("latest-jobs", ("Latest Govt Jobs", "नई सरकारी नौकरी"), "Job",
     ("Every open government job from official notices, closing soonest first: central, railway, police, bank, teacher, defence and state jobs, with last dates and official apply links.",
      "आधिकारिक सूचनाओं से हर खुली सरकारी नौकरी, सबसे पहले बंद होने वाली ऊपर: केंद्र, रेलवे, पुलिस, बैंक, शिक्षक, रक्षा और राज्य की भर्तियाँ, अंतिम तिथि और आधिकारिक आवेदन लिंक के साथ।"),
     [("How often is this list updated?", "Throughout the day; a new notice appears here soon after the board publishes it.",
       "यह सूची कितनी बार अपडेट होती है?", "पूरे दिन; बोर्ड के सूचना जारी करने के कुछ ही देर बाद नई सूचना यहाँ दिखती है।"),
      ("Where do I apply?", "Only on the official website named in the notice. Each job here links to it directly.",
       "आवेदन कहाँ करें?", "सिर्फ़ सूचना में दी गई आधिकारिक वेबसाइट पर। यहाँ हर नौकरी में उसका सीधा लिंक है।")],
     ("Latest Govt Jobs 2026: Sarkari Naukri, Last Date, Apply Online | SarkariChart", "सरकारी नौकरी 2026: नई भर्ती, अंतिम तिथि | सरकारी चार्ट")),
    ("admit-card", ("Admit Card", "एडमिट कार्ड"), "Admit card",
     ("Latest admit cards and exam city slips from official websites: UPSC, SSC, RRB, IBPS, state PSCs, police boards and more, newest first.",
      "आधिकारिक वेबसाइटों से ताज़ा एडमिट कार्ड और परीक्षा शहर सूचना: यूपीएससी, एसएससी, आरआरबी, आईबीपीएस, राज्य लोक सेवा आयोग, पुलिस बोर्ड और अन्य, सबसे नए ऊपर।"),
     [("How do I download my admit card?", "Open the notice, use the official link and log in with your registration number and date of birth or password. Admit cards are only issued on the official website.",
       "एडमिट कार्ड कैसे डाउनलोड करें?", "सूचना खोलें, आधिकारिक लिंक पर जाएँ और अपने पंजीकरण नंबर और जन्मतिथि या पासवर्ड से लॉग इन करें। एडमिट कार्ड सिर्फ़ आधिकारिक वेबसाइट पर जारी होते हैं।")],
     ("Admit Card 2026: Download Latest Sarkari Admit Card | SarkariChart", "एडमिट कार्ड 2026: नए एडमिट कार्ड डाउनलोड करें | सरकारी चार्ट")),
    ("result", ("Sarkari Result", "सरकारी रिज़ल्ट"), "Result",
     ("Latest government exam results, merit lists and cut-offs from official websites, newest first.",
      "आधिकारिक वेबसाइटों से ताज़ा सरकारी परीक्षा रिज़ल्ट, मेरिट सूची और कट-ऑफ, सबसे नए ऊपर।"),
     [("Where is the official result?", "On the board's own website. Each result here links to the official PDF or result page.",
       "आधिकारिक रिज़ल्ट कहाँ है?", "भर्ती बोर्ड की अपनी वेबसाइट पर। यहाँ हर रिज़ल्ट में आधिकारिक पीडीएफ़ या रिज़ल्ट पेज का लिंक है।")],
     ("Sarkari Result 2026: Latest Exam Results, Merit List | SarkariChart", "सरकारी रिज़ल्ट 2026: नए परीक्षा रिज़ल्ट, मेरिट सूची | सरकारी चार्ट")),
    ("answer-key", ("Answer Key", "आंसर की"), "Answer key",
     ("Latest official answer keys and objection windows for government exams, newest first.",
      "सरकारी परीक्षाओं की ताज़ा आधिकारिक आंसर की और आपत्ति की तिथियाँ, सबसे नई ऊपर।"),
     [("Can I object to an answer?", "Usually yes, within the dates in the notice and often for a fee per question. Objections are filed only on the official website.",
       "क्या किसी उत्तर पर आपत्ति कर सकते हैं?", "आमतौर पर हाँ, सूचना में दी गई तिथियों में और अक्सर प्रति प्रश्न शुल्क के साथ। आपत्ति सिर्फ़ आधिकारिक वेबसाइट पर दर्ज होती है।")],
     ("Answer Key 2026: Latest Official Answer Keys | SarkariChart", "आंसर की 2026: नई आधिकारिक आंसर की | सरकारी चार्ट")),
]

import sys
sys.path.insert(0, str(ROOT / "scripts"))
from hubs import STATES, QUALS  # noqa: E402


def state_page(slug, en_name, hi_name, boards):
    b = ", ".join(x.upper() for x in boards)
    return (f"{slug}-govt-jobs", (f"{en_name} Govt Jobs", f"{hi_name} सरकारी नौकरी"), lambda i, s=slug: i.get("st") == s,
            (f"Every open {en_name} government job in one list: {b} and other {en_name} departments, with last dates, admit cards, results and official links.",
             f"{hi_name} की हर खुली सरकारी भर्ती एक जगह: {b} और {hi_name} के अन्य विभाग, अंतिम तिथि, एडमिट कार्ड, रिज़ल्ट और आधिकारिक लिंक के साथ।"),
            [(f"Do I need to be a resident of {en_name}?", f"Many {en_name} state jobs give reservation, and sometimes eligibility, only to residents (domicile). Check the domicile line in each notice. Central government jobs are open to every state.",
              f"क्या {hi_name} का निवासी होना ज़रूरी है?", f"{hi_name} की कई राज्य भर्तियों में आरक्षण, और कभी-कभी पात्रता, सिर्फ़ निवासियों (डोमिसाइल) को मिलती है। हर सूचना में निवास वाली पंक्ति देखें। केंद्र सरकार की नौकरियाँ हर राज्य के लिए खुली हैं।"),
             (f"Where do I apply for {en_name} government jobs?", "Only on the official website named in the notice. Each notice on SarkariChart links to it directly.",
              f"{hi_name} की सरकारी नौकरियों के लिए आवेदन कहाँ करें?", "सिर्फ़ सूचना में दी गई आधिकारिक वेबसाइट पर। सरकारी चार्ट पर हर सूचना में उसका सीधा लिंक है।")])


def qual_page(slug, tag, en_name, hi_name):
    return (f"{slug}-govt-jobs", (f"{en_name} Govt Jobs", f"{hi_name} सरकारी नौकरी"), lambda i, t=tag: t in (i.get("q") or []),
            (f"Open government jobs where the minimum qualification is {en_name}, from central and state boards, with last dates and official apply links.",
             f"वे खुली सरकारी नौकरियाँ जिनमें न्यूनतम योग्यता {hi_name} है, केंद्र और राज्य बोर्डों से, अंतिम तिथि और आधिकारिक आवेदन लिंक के साथ।"),
            [(f"Can someone with a higher qualification apply for {en_name} jobs?", "In most notices yes, unless the notice sets a maximum qualification. Check the eligibility section of each notice.",
              f"क्या ज़्यादा योग्यता वाले {hi_name} वाली नौकरियों में आवेदन कर सकते हैं?", "ज़्यादातर सूचनाओं में हाँ, जब तक सूचना में अधिकतम योग्यता तय न हो। हर सूचना का पात्रता वाला भाग देखें।"),
             ("How is the qualification on this page decided?", "From the minimum qualification printed in each official notice. If a notice has posts at different levels, it appears on each matching page.",
              "इस पेज पर योग्यता कैसे तय होती है?", "हर आधिकारिक सूचना में छपी न्यूनतम योग्यता से। अगर एक सूचना में अलग-अलग स्तर के पद हैं, तो वह हर मिलते पेज पर दिखती है।")])


STATE_PAGES = [state_page(s[0], s[1], s[2], s[3]) for s in STATES]
QUAL_PAGES = [qual_page(q[0], q[1], q[2], q[3]) for q in QUALS]

MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONH = ["जन", "फ़र", "मार्च", "अप्रै", "मई", "जून", "जुला", "अग", "सित", "अक्तू", "नव", "दिस"]
TYPE_HI = {"Job": "नौकरी", "Admit card": "एडमिट कार्ड", "Result": "रिज़ल्ट", "Answer key": "आंसर की", "Update": "अपडेट", "Admission": "प्रवेश"}

STYLE = """<style>
      .sp { display: grid; gap: 34px; max-width: 46rem; margin: 0 auto; }
      .sp h1 { font-size: clamp(2rem, 1.3rem + 2.4vw, 2.75rem); font-weight: 800; line-height: 1.12; letter-spacing: -0.02em; text-align: left !important; margin: 0 !important; max-width: none !important; }
      .sp .lead { margin: 10px 0 0 !important; text-align: left !important; color: var(--grey); font-size: 1.06rem; line-height: 1.55; max-width: none !important; }
      .sp .stats { margin: 12px 0 0; display: flex; flex-wrap: wrap; gap: 6px 18px; font-size: .9375rem; }
      .sp .stats b { font-weight: 600; }
      .sp section { display: grid; gap: 10px; }
      .sp h2 { font-size: 1.2rem; font-weight: 700; margin: 0; }
      .sp .jl { display: grid; }
      .sp .jl a { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 2px 16px; padding: 12px 0; border-top: 1px solid var(--line); color: var(--ink); }
      .sp .jl a:last-child { border-bottom: 1px solid var(--line); }
      .sp .jl a:hover { text-decoration: none; }
      .sp .jl a:hover .t { text-decoration: underline; text-underline-offset: 4px; }
      .sp .jl .t { font-weight: 500; line-height: 1.35; }
      .sp .jl .m { grid-column: 1; color: var(--grey); font-size: .875rem; }
      .sp .jl .d { grid-column: 2; grid-row: 1 / span 2; align-self: center; text-align: right; font-size: .9rem; white-space: nowrap; }
      .sp .jl .d.hot { color: var(--hot); } .sp .jl .d small { display: block; color: var(--grey); font-size: .75rem; }
      .sp .none { color: var(--grey); }
      .sp .qa h3 { font: inherit; font-weight: 600; margin: 6px 0 2px; } .sp .qa p { margin: 0; color: var(--grey); line-height: 1.55; }
      .sp .more { display: flex; flex-wrap: wrap; gap: 8px; }
      .sp .more a { padding: 6px 12px; border: 1px solid var(--line); border-radius: 999px; color: var(--ink); font-size: .9rem; }
      .sp .more a:hover { background: var(--soft); text-decoration: none; }
      .sp .all { color: var(--ink); text-decoration: underline; text-underline-offset: 5px; text-decoration-thickness: 1px; }
    </style>"""


def items():
    s = (SITE / "index.html").read_text(encoding="utf-8")
    a = s.index("/*ITEMS:START*/") + len("/*ITEMS:START*/")
    b = s.index("/*ITEMS:END*/")
    raw = s[a:b].strip().rstrip(",")
    return json.loads("[" + raw.strip("[]") + "]") if not raw.startswith("[") else json.loads(raw)


def fd(iso, hi=False):
    d = dt.date.fromisoformat(iso)
    return f"{d.day} {(MONH if hi else MON)[d.month - 1]}"


def build(slug, name, match, intro, faq, all_items, links, links2=(), kind=None, titles=None, noyear=False, crumb=None):
    esc = html.escape
    today = dt.datetime.now(IST).date()
    mine = [i for i in all_items if i.get("page") and match(i)]
    open_jobs = [i for i in mine if i["type"] == "Job" and (not i.get("last") or dt.date.fromisoformat(i["last"]) >= today)]
    open_jobs.sort(key=lambda i: (i.get("last") or "9999", ))
    open_jobs = [i for i in open_jobs if i.get("last")][:40] + [i for i in open_jobs if not i.get("last")][:10]
    other = sorted([i for i in mine if i["type"] != "Job"], key=lambda i: i.get("posted", ""), reverse=True)[:50 if kind else 12]
    if kind and kind != "Job":
        open_jobs = []
    soon = sum(1 for i in open_jobs if i.get("last") and (dt.date.fromisoformat(i["last"]) - today).days <= 7)
    if kind and kind != "Job":
        n30 = sum(1 for i in mine if i.get("posted", "") >= (today - dt.timedelta(days=30)).isoformat())
    en = {"h1": f"{name[0]} {YEAR}", "lead": intro[0], "openH": "Open now", "otherH": "Latest admit cards, results and updates",
          "faqH": "Common questions", "moreH": "More job pages", "allL": "See every notice on the homepage →",
          "stat1": f"{len(open_jobs)} open {'job' if len(open_jobs) == 1 else 'jobs'}", "stat2": f"{soon} closing this week",
          "none": "No open jobs right now. New notices appear here soon after they are published."}
    hi = {"h1": f"{name[1]} {YEAR}", "lead": intro[1], "openH": "अभी खुली भर्तियाँ", "otherH": "ताज़ा एडमिट कार्ड, रिज़ल्ट और अपडेट",
          "faqH": "आम सवाल", "moreH": "और नौकरी पेज", "allL": "होमपेज पर सभी सूचनाएँ देखें →",
          "stat1": f"{len(open_jobs)} खुली भर्तियाँ", "stat2": f"{soon} इस हफ़्ते बंद होंगी",
          "none": "अभी कोई खुली भर्ती नहीं। नई सूचनाएँ जारी होने के कुछ ही देर बाद यहाँ दिखती हैं।"}
    if kind and kind != "Job":   # a plain newest-first list: "Latest admit cards", no "open now" section
        en.update(otherH=f"Latest {name[0].lower()}s" if not name[0].endswith("Result") else "Latest results", stat1=f"{n30} in the last 30 days", stat2="")
        hi.update(otherH=f"ताज़ा {name[1]}", stat1=f"पिछले 30 दिनों में {n30}", stat2="")
    if noyear:
        en["h1"], hi["h1"] = name

    def row(k, i, pre):
        en[f"{pre}{k}"], hi[f"{pre}{k}"] = i["title"], i.get("hi") or i["title"]
        typ_en, typ_hi = i["type"], TYPE_HI.get(i["type"], i["type"])
        en[f"{pre}m{k}"], hi[f"{pre}m{k}"] = f'{i.get("org", "")} · {typ_en}', f'{i.get("org", "")} · {typ_hi}'
        if i["type"] == "Job" and i.get("last"):
            days = (dt.date.fromisoformat(i["last"]) - today).days
            en[f"{pre}d{k}"], hi[f"{pre}d{k}"] = fd(i["last"]), fd(i["last"], True)
            d = f'<span class="d{" hot" if days <= 7 else ""}"><span data-t="{pre}d{k}">{esc(en[f"{pre}d{k}"])}</span><small data-t="lastL">Last date</small></span>'
        else:
            en[f"{pre}d{k}"], hi[f"{pre}d{k}"] = fd(i["posted"]), fd(i["posted"], True)
            d = f'<span class="d g" data-t="{pre}d{k}">{esc(en[f"{pre}d{k}"])}</span>'
        return f'<a href="{esc(i["url"])}"><span class="t" data-t="{pre}{k}">{esc(en[f"{pre}{k}"])}</span><span class="m g" data-t="{pre}m{k}">{esc(en[f"{pre}m{k}"])}</span>{d}</a>'

    en["lastL"], hi["lastL"] = "Last date", "अंतिम तिथि"
    rows_open = "".join(row(k, i, "o") for k, i in enumerate(open_jobs)) or f'<p class="none" data-t="none">{esc(en["none"])}</p>'
    rows_other = "".join(row(k, i, "u") for k, i in enumerate(other))
    qa = ""
    for k, (qe, ae, qh, ah) in enumerate(faq):
        en[f"q{k}"], en[f"a{k}"], hi[f"q{k}"], hi[f"a{k}"] = qe, ae, qh, ah
        qa += f'<div class="qa"><h3 data-t="q{k}">{esc(qe)}</h3><p data-t="a{k}">{esc(ae)}</p></div>'
    more = ""
    for k2, (s2, n2) in enumerate(links):
        if s2 != slug:
            en[f"lk{k2}"], hi[f"lk{k2}"] = n2[0], n2[1]
            more += f'<a href="/{s2}/" data-t="lk{k2}">{esc(n2[0])}</a>'
    more2 = ""
    for k2, (s2, n2) in enumerate(links2):
        if s2 != slug:
            en[f"lz{k2}"], hi[f"lz{k2}"] = n2[0], n2[1]
            more2 += f'<a href="/{s2}/" data-t="lz{k2}">{esc(n2[0])}</a>'
    en["more2H"], hi["more2H"] = ("More pages like this", "ऐसे और पेज")
    url = f"{SITE_URL}/{slug}/"
    ld = [{"@context": "https://schema.org", "@type": "CollectionPage", "name": en["h1"], "description": intro[0], "url": url,
           "mainEntity": {"@type": "ItemList", "itemListElement": [{"@type": "ListItem", "position": n + 1, "url": SITE_URL + i["url"], "name": i["title"]} for n, i in enumerate(open_jobs[:20])]}},
          {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a, _, _ in faq]},
          {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [{"@type": "ListItem", "position": 1, "name": "SarkariChart", "item": SITE_URL + "/"},
                                                                                          *([{"@type": "ListItem", "position": 2, "name": crumb[0], "item": SITE_URL + crumb[1]}] if crumb else []),
                                                                                          {"@type": "ListItem", "position": 3 if crumb else 2, "name": en["h1"], "item": url}]}]
    main = (STYLE + '\n    <article class="sp">\n'
            f'      <div><h1 data-t="h1">{esc(en["h1"])}</h1><p class="lead" data-t="lead">{esc(intro[0])}</p>'
            f'<p class="stats"><b data-t="stat1">{esc(en["stat1"])}</b><span class="g" data-t="stat2">{esc(en["stat2"])}</span></p></div>\n'
            + ("" if kind and kind != "Job" else f'      <section><h2 data-t="openH">{esc(en["openH"])}</h2><div class="jl">{rows_open}</div></section>\n')
            + (f'      <section><h2 data-t="otherH">{esc(en["otherH"])}</h2><div class="jl">{rows_other}</div></section>\n' if rows_other else "")
            + f'      <section><h2 data-t="faqH">{esc(en["faqH"])}</h2>{qa}</section>\n'
            + (f'      <section><h2 data-t="more2H">{esc(en["more2H"])}</h2><p class="more">{more2}</p></section>\n' if more2 else "")
            + f'      <section><h2 data-t="moreH">{esc(en["moreH"])}</h2><p class="more">{more}</p><p><a class="all" href="/" data-t="allL">{esc(en["allL"])}</a></p></section>\n'
            '    </article>\n'
            '    <script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False).replace("</", "<\\/") + "</script>\n"
            '    <span id="state" hidden></span><span id="left" hidden></span><span id="views" hidden></span><a id="dlPdf" hidden></a>')
    title_en = f"{name[0]} {YEAR}: Latest Vacancy, Last Date, Apply Online | SarkariChart"
    title_hi = f"{name[1]} {YEAR} | सरकारी चार्ट"
    if titles:
        title_en, title_hi = titles
    en["title"], hi["title"] = title_en, title_hi
    desc = f"{len(open_jobs)} open {name[0].lower()} {YEAR} with last dates and official apply links. {intro[0]}"[:158]
    if kind and kind != "Job":
        desc = intro[0][:158]
    js = lambda v: json.dumps(v, ensure_ascii=False)
    out = (TPL.replace("{{TITLE}}", esc(title_en)).replace("{{DESC}}", esc(desc)).replace("{{MAIN}}", main)
           .replace("{{T_EN}}", "\n".join(f"      {k}: {js(v)}," for k, v in en.items()))
           .replace("{{T_HI}}", "\n".join(f"      {k}: {js(v)}," for k, v in hi.items()))
           .replace("{{SLUG}}", slug).replace("{{OGIMG}}", f"{SITE_URL}/og.png").replace("{{URL}}", url)
           .replace("{{OGALT}}", esc(f"SarkariChart — {en['h1']}")).replace("{{LAST}}", "null"))
    if not open_jobs and not other:   # nothing to show yet: keep it out of Google until it has notices (no thin pages)
        out = re.sub(r'<meta name="robots" content="[^"]*">', '<meta name="robots" content="noindex, follow">', out, count=1)
    d = SITE / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "index.html").write_text(out, encoding="utf-8")
    return len(open_jobs), len(other)


EXAM_MIN = 3   # an exam page only once the exam has 3+ notices on the site (no thin pages)


def exam_pages(all_items, links):
    """One permanent page per exam at /exam/<exam>/ (no year in the address, so it keeps its Google rank every cycle):
    the latest cycle's name as heading, open jobs, then every admit card / answer key / result / update, newest first."""
    import shutil
    sys.path.insert(0, str(ROOT / "scripts"))
    from exams import series
    ex = {}
    for f in (ROOT / "data/notices").glob("*.json"):
        n = json.loads(f.read_text(encoding="utf-8"))
        e = n.get("exam") or {}
        if n.get("status") == "approved" and e.get("key"):
            ex[n["id"]] = (series(e["key"]), e.get("name_en") or e["key"], e.get("name_hi") or e.get("name_en") or e["key"], e["key"])
    groups = {}
    for i in all_items:
        if i.get("page") and i["id"] in ex:
            groups.setdefault(ex[i["id"]][0], []).append(i)
    out = SITE / "exam"
    if out.exists():
        shutil.rmtree(out)
    made = []
    for key, its in groups.items():
        if len(its) < EXAM_MIN:
            continue
        newest = max(its, key=lambda i: i.get("publishedAt") or "")
        _, en_name, hi_name, _ = ex[newest["id"]]
        ids = {i["id"] for i in its}
        intro = (f"Every official update for {en_name} in one place: notification, important dates, admit card, answer key and result, newest first, each with the official link.",
                 f"{hi_name} का हर आधिकारिक अपडेट एक जगह: अधिसूचना, ज़रूरी तिथियाँ, एडमिट कार्ड, आंसर की और रिज़ल्ट, सबसे नया पहले, हर एक आधिकारिक लिंक के साथ।")
        faq = [(f"When will the {en_name} admit card or result come?", "Only the board decides the date. It appears on this page within minutes of the board publishing it, and on our free WhatsApp and Telegram channels.",
                f"{hi_name} का एडमिट कार्ड या रिज़ल्ट कब आएगा?", "तारीख़ सिर्फ़ बोर्ड तय करता है। बोर्ड के जारी करते ही कुछ मिनटों में यह इस पेज पर और हमारे मुफ़्त व्हाट्सऐप और टेलीग्राम चैनल पर आ जाता है।"),
               (f"Where do I apply or download for {en_name}?", "Only on the official website named in the notice. Each update here links to it directly.",
                f"{hi_name} के लिए आवेदन या डाउनलोड कहाँ करें?", "सिर्फ़ सूचना में दी गई आधिकारिक वेबसाइट पर। यहाँ हर अपडेट में उसका सीधा लिंक है।")]
        titles = (f"{en_name}: Notification, Admit Card, Result, Answer Key | SarkariChart",
                  f"{hi_name}: अधिसूचना, एडमिट कार्ड, रिज़ल्ट, आंसर की | सरकारी चार्ट")
        build(f"exam/{key}", (en_name, hi_name), lambda i, s=ids: i["id"] in s, intro, faq, all_items, links,
              titles=titles, noyear=True, crumb=("Exams", "/exam/"))
        made.append((key, en_name, hi_name, len(its), newest.get("publishedAt") or ""))
    made.sort(key=lambda m: m[4], reverse=True)
    # /exam/ index: every exam page, latest activity first
    esc = html.escape
    en, hi = {"h1": "Exams", "lead": "Every exam with its full timeline: notification, admit card, answer key and result, from official notices."}, {"h1": "परीक्षाएँ", "lead": "हर परीक्षा की पूरी टाइमलाइन: अधिसूचना, एडमिट कार्ड, आंसर की और रिज़ल्ट, आधिकारिक सूचनाओं से।"}
    rows = ""
    for k, (key, en_name, hi_name, cnt, _) in enumerate(made):
        en[f"x{k}"], hi[f"x{k}"] = en_name, hi_name
        en[f"n{k}"], hi[f"n{k}"] = f"{cnt} updates", f"{cnt} अपडेट"
        rows += f'<a href="/exam/{key}/"><span class="t" data-t="x{k}">{esc(en_name)}</span><span class="d g" data-t="n{k}">{esc(en[f"n{k}"])}</span></a>'
    main = (STYLE + '\n    <article class="sp">\n'
            f'      <div><h1 data-t="h1">{esc(en["h1"])}</h1><p class="lead" data-t="lead">{esc(en["lead"])}</p></div>\n'
            f'      <section><div class="jl">{rows}</div></section>\n    </article>\n'
            '    <span id="state" hidden></span><span id="left" hidden></span><span id="views" hidden></span><a id="dlPdf" hidden></a>')
    en["title"], hi["title"] = f"All Exams {YEAR}: Admit Card, Result, Answer Key | SarkariChart", f"सभी परीक्षाएँ {YEAR}: एडमिट कार्ड, रिज़ल्ट, आंसर की | सरकारी चार्ट"
    js = lambda v: json.dumps(v, ensure_ascii=False)
    page = (TPL.replace("{{TITLE}}", esc(en["title"])).replace("{{DESC}}", esc(en["lead"])).replace("{{MAIN}}", main)
            .replace("{{T_EN}}", "\n".join(f"      {k}: {js(v)}," for k, v in en.items()))
            .replace("{{T_HI}}", "\n".join(f"      {k}: {js(v)}," for k, v in hi.items()))
            .replace("{{SLUG}}", "exam").replace("{{OGIMG}}", f"{SITE_URL}/og.png").replace("{{URL}}", f"{SITE_URL}/exam/")
            .replace("{{OGALT}}", "SarkariChart — Exams").replace("{{LAST}}", "null"))
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(page, encoding="utf-8")
    print(f"seo: {len(made)} exam pages + /exam/")


def main():
    all_items = items()
    links = [(p[0], p[1]) for p in PAGES]
    groups = [(PAGES, ()), (STATE_PAGES, [(p[0], p[1]) for p in STATE_PAGES]), (QUAL_PAGES, [(p[0], p[1]) for p in QUAL_PAGES])]
    tlinks = [(p[0], p[1]) for p in TYPE_PAGES]
    for slug, name, typ, intro, faq, titles in TYPE_PAGES:
        n, m = build(slug, name, lambda i, t=typ: i["type"] == t, intro, faq, all_items, links, tlinks, kind=typ, titles=titles)
        print(f"seo: /{slug}/ {n} open, {m} listed")
    for pages, links2 in groups:
        for slug, name, match, intro, faq in pages:
            n, m = build(slug, name, match, intro, faq, all_items, links, links2)
            print(f"seo: /{slug}/ {n} open, {m} updates")
    exam_pages(all_items, links)


if __name__ == "__main__":
    main()
