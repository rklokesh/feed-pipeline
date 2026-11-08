"""Builds the trust pages from the notice-page template: /about/, /privacy/, /terms/, /contact/ (English + Hindi).

Plain words, no legal padding. Edit the text below and run: python3 scripts/info_pages.py
"""
from __future__ import annotations

import html
import json
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
TPL = (ROOT / "templates/notice.html").read_text(encoding="utf-8")
SITE_URL = os.environ.get("SITE_URL", "https://sarkarichart.com")
UPDATED = ("28 Oct 2026", "28 अक्तूबर 2026")

# each page: slug, (title EN, HI), (lead EN, HI), sections [(heading EN, HI, [items EN], [items HI], list?)]
PAGES = [
    ("about", ("About SarkariChart", "सरकारी चार्ट के बारे में"),
     ("SarkariChart lists every new government job, admit card, result and answer key from official websites, in English and Hindi, as soon as it is published.",
      "सरकारी चार्ट आधिकारिक वेबसाइटों से हर नई सरकारी नौकरी, एडमिट कार्ड, रिज़ल्ट और आंसर की को, जारी होते ही, हिंदी और अंग्रेज़ी में दिखाता है।"),
     [("How it works", "यह कैसे काम करता है",
       ["Every 30 minutes we check the official websites of about 50 recruitment boards and commissions, such as UPSC, SSC, RRB, IBPS, state public service commissions and police boards.",
        "When a new notice appears, we read the official PDF and write a short, clear page: key dates, fees, age limit, vacancies, eligibility and how to apply.",
        "Every page links to the official notice and the official website, so you can always check the source yourself.",
        "The date shown is the date the board issued the notice, not the date we added it."],
       ["हर 30 मिनट में हम लगभग 50 भर्ती बोर्ड और आयोगों की आधिकारिक वेबसाइट देखते हैं, जैसे यूपीएससी, एसएससी, आरआरबी, आईबीपीएस, राज्य लोक सेवा आयोग और पुलिस भर्ती बोर्ड।",
        "नई सूचना आते ही हम आधिकारिक पीडीएफ़ पढ़कर एक छोटा, साफ़ पेज बनाते हैं: मुख्य तिथियाँ, शुल्क, आयु सीमा, पद, पात्रता और आवेदन का तरीका।",
        "हर पेज पर आधिकारिक सूचना और आधिकारिक वेबसाइट का लिंक होता है, ताकि आप स्रोत ख़ुद देख सकें।",
        "दिखाई गई तिथि वह है जिस दिन बोर्ड ने सूचना जारी की, न कि जिस दिन हमने उसे जोड़ा।"], True),
      ("What we promise", "हमारा वादा",
       ["Official sources only. No rumours, no \"expected\" vacancies.",
        "Free to use. We never ask for money, and we never sell jobs or \"guaranteed selection\".",
        "No pop-ups and no ads for now. A clean page that loads fast on any phone.",
        "Full Hindi. Switch language at the top of any page."],
       ["सिर्फ़ आधिकारिक स्रोत। कोई अफ़वाह नहीं, कोई \"संभावित\" भर्ती नहीं।",
        "पूरी तरह मुफ़्त। हम कभी पैसे नहीं माँगते और \"पक्की नौकरी\" जैसा कुछ नहीं बेचते।",
        "अभी कोई पॉप-अप और कोई विज्ञापन नहीं। हर फ़ोन पर जल्दी खुलने वाला साफ़ पेज।",
        "पूरी साइट हिंदी में। किसी भी पेज के ऊपर भाषा बदलें।"], False),
      ("If something is wrong", "अगर कुछ गलत हो",
       ["Our pages are written from the official notice, but mistakes can happen. If anything differs, the official notice is correct.",
        "Please tell us using the Report a mistake link on any page. We check every report against the official notice."],
       ["हमारे पेज आधिकारिक सूचना से बनते हैं, फिर भी गलती हो सकती है। कोई बात अलग हो, तो आधिकारिक सूचना को ही सही मानें।",
        "किसी भी पेज पर \"गलती बताएँ\" लिंक से हमें बताइए। हम हर रिपोर्ट को आधिकारिक सूचना से मिलाकर जाँचते हैं।"], False),
      ("Not a government website", "यह सरकारी वेबसाइट नहीं है",
       ["SarkariChart is an independent website. It is not run by, or connected to, any government department or recruitment board. Organisation names and logos are shown only to identify who issued a notice."],
       ["सरकारी चार्ट एक स्वतंत्र वेबसाइट है। यह किसी सरकारी विभाग या भर्ती बोर्ड द्वारा नहीं चलाई जाती और न ही उनसे जुड़ी है। संस्थाओं के नाम और लोगो सिर्फ़ यह बताने के लिए दिखाए जाते हैं कि सूचना किसने जारी की।"], False)]),
    ("privacy", ("Privacy", "गोपनीयता"),
     ("We collect as little as possible. You can use SarkariChart without an account, and we do not use advertising or tracking cookies.",
      "हम कम से कम जानकारी लेते हैं। सरकारी चार्ट बिना खाते के इस्तेमाल होता है, और हम विज्ञापन या ट्रैकिंग कुकी का इस्तेमाल नहीं करते।"),
     [("Stored in your own browser", "आपके अपने ब्राउज़र में",
       ["Your language, light or dark theme, whether you closed the top banner, and the day you last viewed a page (so a view is counted once a day). These stay on your device and you can clear them any time from your browser settings."],
       ["आपकी भाषा, लाइट या डार्क थीम, ऊपर की पट्टी बंद की या नहीं, और आपने आख़िरी बार पेज किस दिन देखा (ताकि एक दिन में एक ही बार गिना जाए)। ये आपके डिवाइस पर ही रहते हैं, और आप इन्हें कभी भी ब्राउज़र की सेटिंग से मिटा सकते हैं।"], False),
      ("View counts", "पेज कितनी बार देखा गया",
       ["We count how many times each notice page is viewed. Only the number is stored, never who viewed it."],
       ["हम गिनते हैं कि हर सूचना पेज कितनी बार देखा गया। सिर्फ़ संख्या रखी जाती है, देखने वाले की पहचान कभी नहीं।"], False),
      ("When you report a mistake", "जब आप गलती बताते हैं",
       ["We receive your message, the page you were on, and anything you choose to add: your name, email and a screenshot. We use these only to check and fix the page, and to reply if you gave an email.",
        "To stop spam we keep a scrambled code made from your internet address for one hour. It cannot be turned back into the address."],
       ["हमें आपका संदेश, वह पेज जिस पर आप थे, और जो आप जोड़ना चाहें वह मिलता है: नाम, ईमेल और स्क्रीनशॉट। इनका इस्तेमाल सिर्फ़ पेज जाँचने और सुधारने के लिए, और ईमेल दिया हो तो जवाब देने के लिए होता है।",
        "स्पैम रोकने के लिए हम आपके इंटरनेट पते से बना एक बदला हुआ कोड एक घंटे तक रखते हैं। इससे असली पता वापस नहीं निकाला जा सकता।"], False),
      ("Hosting and other sites", "होस्टिंग और दूसरी साइटें",
       ["The site is hosted on Cloudflare, which keeps standard technical logs to keep the site safe and working.",
        "Links to official websites, PDFs, Telegram and WhatsApp take you to those services, which have their own privacy rules."],
       ["साइट क्लाउडफ़्लेयर पर चलती है, जो साइट को सुरक्षित और चालू रखने के लिए सामान्य तकनीकी लॉग रखता है।",
        "आधिकारिक वेबसाइट, पीडीएफ़, टेलीग्राम और व्हाट्सऐप के लिंक आपको उन सेवाओं पर ले जाते हैं, जिनके अपने निजता नियम हैं।"], False),
      ("Questions or removal", "सवाल या जानकारी हटवाना",
       ["To ask about your data or have a report you sent deleted, use the Report a mistake form and say so. We will act on it."],
       ["अपनी जानकारी के बारे में पूछने या भेजी गई रिपोर्ट हटवाने के लिए \"गलती बताएँ\" फ़ॉर्म से हमें लिखें। हम ज़रूर करेंगे।"], False)]),
    ("terms", ("Terms and disclaimer", "नियम और अस्वीकरण"),
     ("Please read this once. In short: we help you find official notices quickly, but the official notice is always the final word.",
      "कृपया एक बार पढ़ लें। संक्षेप में: हम आपको आधिकारिक सूचनाएँ जल्दी ढूँढने में मदद करते हैं, पर अंतिम बात हमेशा आधिकारिक सूचना की होती है।"),
     [("The official notice is final", "आधिकारिक सूचना ही अंतिम है",
       ["Our pages summarise official notices. Dates, fees, vacancies and rules can change through corrigenda. Always read the official notice and apply only on the official website before you act.",
        "We are not responsible for any loss caused by relying on our pages instead of the official notice."],
       ["हमारे पेज आधिकारिक सूचनाओं का सारांश हैं। तिथियाँ, शुल्क, पद और नियम शुद्धि पत्र से बदल सकते हैं। कुछ भी करने से पहले आधिकारिक सूचना ज़रूर पढ़ें और आवेदन सिर्फ़ आधिकारिक वेबसाइट पर करें।",
        "आधिकारिक सूचना के बजाय हमारे पेज पर भरोसा करने से हुए किसी नुकसान के लिए हम ज़िम्मेदार नहीं हैं।"], False),
      ("Independent website", "स्वतंत्र वेबसाइट",
       ["SarkariChart is not a government website and is not linked to any recruitment board. We never take applications, fees or documents, and we never promise selection. Anyone asking you for money in our name is a fraud."],
       ["सरकारी चार्ट सरकारी वेबसाइट नहीं है और किसी भर्ती बोर्ड से जुड़ी नहीं है। हम न आवेदन लेते हैं, न शुल्क, न दस्तावेज़, और न ही चयन का वादा करते हैं। हमारे नाम पर पैसे माँगने वाला धोखेबाज़ है।"], False),
      ("Names, logos and documents", "नाम, लोगो और दस्तावेज़",
       ["Organisation names and logos belong to their owners and are shown only to identify who issued a notice. Official PDFs are linked or kept as copies so you can read them; they belong to the issuing body.",
        "If you represent an organisation and want a logo or document removed, tell us through the Report a mistake form and we will remove it."],
       ["संस्थाओं के नाम और लोगो उनके मालिकों के हैं और सिर्फ़ यह बताने के लिए दिखाए जाते हैं कि सूचना किसने जारी की। आधिकारिक पीडीएफ़ का लिंक या प्रति पढ़ने के लिए दी जाती है; वे जारी करने वाली संस्था के हैं।",
        "अगर आप किसी संस्था की ओर से कोई लोगो या दस्तावेज़ हटवाना चाहते हैं, तो \"गलती बताएँ\" फ़ॉर्म से बताइए, हम हटा देंगे।"], False),
      ("Using the site", "साइट का इस्तेमाल",
       ["You are welcome to read, share and link to our pages. Please do not copy our pages in bulk or use automated tools that overload the site."],
       ["आप हमारे पेज पढ़ सकते हैं, शेयर कर सकते हैं और उनका लिंक दे सकते हैं। कृपया पेज थोक में कॉपी न करें और ऐसे ऑटोमेटेड टूल न चलाएँ जो साइट पर बोझ डालें।"], False)]),
    ("press", ("Press kit", "प्रेस किट"),
     ("Everything you need to write about SarkariChart: a short description, key facts and the logo.",
      "सरकारी चार्ट के बारे में लिखने के लिए ज़रूरी सब कुछ: छोटा परिचय, मुख्य तथ्य और लोगो।"),
     [("In one line", "एक पंक्ति में",
       ["SarkariChart is a free, ad-free website that lists every new Indian government job, admit card, result and answer key straight from official notices, in English and Hindi."],
       ["सरकारी चार्ट एक मुफ़्त, बिना विज्ञापन वाली वेबसाइट है जो हर नई सरकारी नौकरी, एडमिट कार्ड, रिज़ल्ट और आंसर की को सीधे आधिकारिक सूचनाओं से, हिंदी और अंग्रेज़ी में दिखाती है।"], False),
      ("Key facts", "मुख्य तथ्य",
       ["Checks about 45 official recruitment boards every 30 minutes: UPSC, SSC, RRB, IBPS, SBI, state public service commissions, police and defence boards.",
        "Every notice page is written from the official PDF and links to it. Dates are the dates the board issued the notice.",
        "Full Hindi on every page, a calm design with no pop-ups or ads, and free alerts on Telegram (@sarkarichart).",
        "\"Am I eligible?\": readers can check their age and qualification against each job; the details stay on their own device.",
        "Independent website, not run by or connected to any government department."],
       ["लगभग 45 आधिकारिक भर्ती बोर्ड हर 30 मिनट में जाँचे जाते हैं: यूपीएससी, एसएससी, आरआरबी, आईबीपीएस, एसबीआई, राज्य लोक सेवा आयोग, पुलिस और रक्षा भर्ती बोर्ड।",
        "हर सूचना पेज आधिकारिक पीडीएफ़ से बनता है और उसका लिंक देता है। तिथियाँ वही हैं जिस दिन बोर्ड ने सूचना जारी की।",
        "हर पेज पूरी तरह हिंदी में, बिना पॉप-अप या विज्ञापन का शांत डिज़ाइन, और टेलीग्राम (@sarkarichart) पर मुफ़्त अलर्ट।",
        "\"क्या मैं योग्य हूँ?\": पाठक हर नौकरी से अपनी आयु और योग्यता मिला सकते हैं; जानकारी उनके अपने डिवाइस पर ही रहती है।",
        "स्वतंत्र वेबसाइट, किसी सरकारी विभाग द्वारा नहीं चलाई जाती और न ही उससे जुड़ी है।"], False),
      ("Logo", "लोगो",
       ["Please use the logo as it is: do not crop, recolour or change it. Download it with the link below."],
       ["कृपया लोगो को जैसा है वैसा ही इस्तेमाल करें: काटें, रंग या बदलाव न करें। नीचे दिए लिंक से डाउनलोड करें।"], False),
      ("Contact for press", "प्रेस के लिए संपर्क",
       ["Write to us through the Report a mistake form and say it is a press request. We usually reply within two days."],
       ["\"गलती बताएँ\" फ़ॉर्म से लिखें और बताएँ कि यह प्रेस के लिए है। हम आम तौर पर दो दिन में जवाब देते हैं।"], False)]),
    ("contact", ("Contact", "संपर्क"),
     ("We read every message. The quickest way to reach us is the form below.",
      "हम हर संदेश पढ़ते हैं। हम तक पहुँचने का सबसे तेज़ तरीका नीचे दिया फ़ॉर्म है।"),
     [("Write to us", "हमें लिखें",
       ["Found a mistake, a missing notice, a broken link, or have a suggestion? Use the Report a mistake form. Add your email if you would like a reply.",
        "Organisations can use the same form to ask for a correction or for a logo or document to be removed."],
       ["कोई गलती, छूटी हुई सूचना, टूटा लिंक मिला, या कोई सुझाव है? \"गलती बताएँ\" फ़ॉर्म से लिखें। जवाब चाहिए तो अपना ईमेल जोड़ दें।",
        "संस्थाएँ भी इसी फ़ॉर्म से सुधार, या किसी लोगो या दस्तावेज़ को हटाने के लिए कह सकती हैं।"], False),
      ("Get every new notice", "हर नई सूचना पाएँ",
       ["Join our Telegram channel @sarkarichart for every new job alert, free."],
       ["हर नई नौकरी की सूचना मुफ़्त पाने के लिए हमारे टेलीग्राम चैनल @sarkarichart से जुड़ें।"], False)]),
]

LINKS = {"press": [("/sarkarichart-logo.png", "Download the logo (PNG) →", "लोगो डाउनलोड करें (PNG) →"),
                   ("/report/", "Press request form →", "प्रेस अनुरोध फ़ॉर्म →")],
         "contact": [("/report/", "Report a mistake form →", "गलती बताएँ फ़ॉर्म →"),
                     ("https://t.me/sarkarichart", "Join on Telegram →", "टेलीग्राम पर जुड़ें →")]}

STYLE = """    <style>
      .ip { display: grid; gap: 30px; max-width: 42rem; margin: 0 auto; }
      .ip h1 { font-size: clamp(1.9rem, 1.3rem + 2vw, 2.5rem); font-weight: 800; line-height: 1.15; letter-spacing: -0.02em; text-align: left; margin: 0; }
      .ip .lead { margin: 10px 0 0; text-align: left; color: var(--grey); font-size: 1.06rem; }
      .ip .upd { color: var(--grey); font-size: .9rem; margin-top: 8px; }
      .ip section { display: grid; gap: 10px; }
      .ip h2 { font-size: 1.2rem; font-weight: 700; }
      .ip p, .ip li { line-height: 1.55; }
      .ip ol { list-style: decimal; padding-left: 1.4rem; display: grid; gap: 8px; }
      .ip ul { list-style: disc; padding-left: 1.4rem; display: grid; gap: 8px; }
      .ip .go { display: flex; flex-wrap: wrap; gap: 10px 26px; }
      .ip .go a { text-decoration: underline; text-underline-offset: 5px; text-decoration-thickness: 1px; }
      .ip .more { color: var(--grey); display: flex; flex-wrap: wrap; gap: 6px 18px; border-top: 1px solid var(--line); padding-top: 16px; }
    </style>"""

NAV = [("about", "About", "परिचय"), ("privacy", "Privacy", "गोपनीयता"), ("terms", "Terms", "नियम"), ("contact", "Contact", "संपर्क"), ("press", "Press kit", "प्रेस किट")]


def build(slug, title, lead, sections):
    esc = html.escape
    en, hi = {"h1": title[0], "lead": lead[0], "upd": f"Last updated {UPDATED[0]}"}, {"h1": title[1], "lead": lead[1], "upd": f"अपडेट {UPDATED[1]}"}
    body = []
    for k, (he, hh, ie, ih, ordered) in enumerate(sections):
        en[f"s{k}"], hi[f"s{k}"] = he, hh
        tag = "ol" if ordered else "ul"
        if len(ie) == 1:
            en[f"s{k}p0"], hi[f"s{k}p0"] = ie[0], ih[0]
            inner = f'<p data-t="s{k}p0">{esc(ie[0])}</p>'
        else:
            lis = ""
            for j, (a, b) in enumerate(zip(ie, ih)):
                en[f"s{k}p{j}"], hi[f"s{k}p{j}"] = a, b
                lis += f'<li data-t="s{k}p{j}">{esc(a)}</li>'
            inner = f"<{tag}>{lis}</{tag}>"
        body.append(f'      <section><h2 data-t="s{k}">{esc(he)}</h2>{inner}</section>')
    go = ""
    for j, (href, a, b) in enumerate(LINKS.get(slug, [])):
        en[f"go{j}"], hi[f"go{j}"] = a, b
        ext = ' target="_blank" rel="noopener"' if href.startswith("http") else ""
        go += f'<a href="{href}"{ext} data-t="go{j}">{esc(a)}</a>'
    more = ""
    for s, a, b in NAV:
        if s != slug:
            en[f"nav_{s}"], hi[f"nav_{s}"] = a, b
            more += f'<a href="/{s}/" data-t="nav_{s}">{esc(a)}</a>'
    main = (STYLE + '\n    <article class="ip">\n      <div><h1 data-t="h1">' + esc(title[0]) + '</h1><p class="lead" data-t="lead">' + esc(lead[0])
            + '</p><p class="upd" data-t="upd">' + esc(en["upd"]) + "</p></div>\n" + "\n".join(body)
            + (f'\n      <p class="go">{go}</p>' if go else "") + f'\n      <p class="more">{more}</p>\n    </article>\n'
            '    <span id="state" hidden></span><span id="left" hidden></span><span id="views" hidden></span><a id="dlPdf" hidden></a><a id="share" hidden></a>')
    en["title"], hi["title"] = f"{title[0]} · SarkariChart", f"{title[1]} · सरकारी चार्ट"
    js = lambda v: json.dumps(v, ensure_ascii=False)
    url = f"{SITE_URL}/{slug}/"
    out = (TPL.replace("{{TITLE}}", esc(en["title"])).replace("{{DESC}}", esc(lead[0][:155])).replace("{{MAIN}}", main)
           .replace("{{T_EN}}", "\n".join(f"      {k}: {js(v)}," for k, v in en.items()))
           .replace("{{T_HI}}", "\n".join(f"      {k}: {js(v)}," for k, v in hi.items()))
           .replace("{{SLUG}}", slug).replace("{{OGIMG}}", f"{SITE_URL}/og.png").replace("{{URL}}", url)
           .replace("{{OGALT}}", esc(f"SarkariChart — {title[0]}")).replace("{{LAST}}", "null"))
    d = ROOT / "site" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "index.html").write_text(out, encoding="utf-8")
    print(f"wrote site/{slug}/index.html")


def main():
    for p in PAGES:
        build(*p)


if __name__ == "__main__":
    main()
