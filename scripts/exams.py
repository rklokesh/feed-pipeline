"""Exam pages: one permanent page per exam (e.g. /exam/ssc-cgl-2026/) with every official update for it, newest first.

  python scripts/exams.py tag     # before pages.py: AI tags new notices with their exam (one batched call per ~60 notices)
  python scripts/exams.py build   # after pages.py: writes site/exam/<key>/, the homepage "Exams" tab rows, site/exam/index.html

A notice belongs to one exam: board + exam/post + cycle year ("ssc-cgl-2026"). Notification, date changes, admit card,
answer key and result of the same cycle share the key. An exam page is made once it has 2+ live notices (a single
notice already has its own page; thin one-item pages would only add noise for Google).
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
MIN_NOTICES = 2
MONTHS_HI = ["जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर", "अक्तूबर", "नवंबर", "दिसंबर"]
TYPE = {"Job": ("Notification", "अधिसूचना"), "Admit card": ("Admit card", "एडमिट कार्ड"), "Result": ("Result", "रिज़ल्ट"),
        "Answer key": ("Answer key", "आंसर की")}
KEY_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

PROMPT = """You group Indian government recruitment notices by the exam / recruitment they belong to.
For each notice return an exam key: lowercase words joined by hyphens = board short name + exam or post short name + cycle year,
e.g. "ssc-cgl-2026", "rrb-station-master-2026", "uppsc-dental-surgeon-2025", "rpsc-senior-teacher-2025", "ugc-net-dec-2026".
- The year is the cycle year the notice itself names (advertisement / exam year), not the date it was published.
- Every stage of the same recruitment (notification, last date extended, corrigendum, admit card, answer key, result,
  cut-off, DV, interview) MUST get the SAME key. Reuse a key from KNOWN_EXAMS whenever the notice belongs to it.
- Different posts with separate advertisements are different exams (rpsc-lecturer-panchkarma-2025 vs rpsc-lecturer-kayachikitsa-2025).
- null for notices not tied to one recruitment (fraud warnings, general circulars, forms, calendars).
name_en: short name people search, e.g. "SSC CGL 2026", "RRB Station Master 2026". name_hi: same in Hindi (एसएससी सीजीएल 2026).
Answer with JSON: {"tags": [{"id": "...", "key": "... or null", "name_en": "...", "name_hi": "..."}]}"""


def load():
    out = []
    for f in sorted(NOTICES.glob("*.json")):
        n = json.loads(f.read_text())
        if n.get("status") == "approved":
            out.append((f, n))
    return out


def title(n):
    c, pg = n.get("card") or {}, n.get("page") or {}
    return pg.get("h1_en") or c.get("title_en") or n.get("title") or ""


def title_hi(n):
    c, pg = n.get("card") or {}, n.get("page") or {}
    return pg.get("h1_hi") or c.get("title_hi") or title(n)


def ai(user: str) -> dict | None:
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
    notices = load()
    known = {}
    for _, n in notices:
        e = n.get("exam")
        if e and e.get("key"):
            known[e["key"]] = e.get("name_en", "")
    todo = [(f, n) for f, n in notices if "exam" not in n]
    if not todo:
        print("exams: nothing to tag")
        return
    for i in range(0, len(todo), 60):
        batch = todo[i:i + 60]
        user = json.dumps({"KNOWN_EXAMS": [{"key": k, "name_en": v} for k, v in sorted(known.items())],
                           "notices": [{"id": n["id"], "board": n.get("org"), "title": title(n), "type": (n.get("card") or {}).get("type"),
                                        "issued": n.get("notice_date")} for _, n in batch]}, ensure_ascii=False)
        res = ai(user)
        if not res:
            print("exams: AI unavailable, will tag next run")
            return
        tags = {t.get("id"): t for t in res.get("tags", []) if isinstance(t, dict)}
        for f, n in batch:
            t = tags.get(n["id"])
            if t is None:
                continue          # not answered: try again next run
            key = str(t.get("key") or "").strip().lower()
            if key and KEY_RE.match(key) and len(key) <= 60:
                n["exam"] = {"key": key, "name_en": str(t.get("name_en") or key).strip()[:60],
                             "name_hi": str(t.get("name_hi") or t.get("name_en") or key).strip()[:60]}
                known[key] = n["exam"]["name_en"]
            else:
                n["exam"] = {}    # checked: not part of an exam
            f.write_text(json.dumps(n, ensure_ascii=False, indent=2, sort_keys=True))
        print(f"exams: tagged {len(batch)} notices")


def groups(notices=None) -> dict:
    """exam key -> {name_en, name_hi, items[...]} for exams with enough live notices (used by pages.py for the link too)."""
    notices = notices if notices is not None else [n for _, n in load()]
    g = {}
    for n in notices:
        e = n.get("exam") or {}
        if n.get("status") != "approved" or not e.get("key") or not n.get("slug"):
            continue
        x = g.setdefault(e["key"], {"key": e["key"], "name_en": e.get("name_en") or e["key"], "name_hi": e.get("name_hi") or "", "items": []})
        x["items"].append(n)
    for x in g.values():
        x["items"].sort(key=lambda n: (n.get("notice_date") or "", n.get("first_seen") or ""), reverse=True)
        x["latest"] = x["items"][0].get("notice_date") or ""
    return {k: v for k, v in g.items() if len(v["items"]) >= MIN_NOTICES}


def d_en(iso):
    d = dt.date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%b')} {d.year}"


def d_hi(iso):
    d = dt.date.fromisoformat(iso)
    return f"{d.day} {MONTHS_HI[d.month - 1]} {d.year}"


def stage(n):
    """Short stage label (Recruitment / Last Date Extended / Admit Card / Cut-Off …), same words as the share card."""
    try:
        from share_card import share_data
        vd = lambda v: str(v)[:10] if v else None
        sc = share_data(n, d_en, d_hi, vd)
        return re.sub(r"\s*\b20\d\d\b", "", sc["en"]["headline"]).strip(), re.sub(r"\s*\b20\d\d\b", "", sc["hi"]["headline"]).strip()
    except Exception:  # noqa: BLE001
        return TYPE.get((n.get("card") or {}).get("type", "Job"), TYPE["Job"])


def render(x: dict, board_exams: list) -> str:
    esc = html.escape
    js = lambda v: json.dumps("" if v is None else str(v), ensure_ascii=False)
    items = x["items"]
    org = items[0].get("org") or ""
    latest = items[0]
    en = {"h1": f'{x["name_en"]}: All Updates', "crumbType": "Exams", "org": org,
          "lead": f'Every official update for {x["name_en"]} in one place, newest first. Latest: {title(latest)} ({d_en(latest["notice_date"])}).',
          "tlH": "All updates", "colDate": "Date", "colStage": "Update", "glH": "Key facts (from the notification)", "relH": f"More {org} exams",
          "note": "Details come from the official notices. If anything differs, the official notice is correct."}
    hi = {"h1": f'{x["name_hi"] or x["name_en"]}: सभी अपडेट', "crumbType": "परीक्षाएँ", "org": org,
          "lead": f'{x["name_hi"] or x["name_en"]} की हर आधिकारिक सूचना एक जगह, नई सबसे ऊपर। ताज़ा: {title_hi(latest)} ({d_hi(latest["notice_date"])})।',
          "tlH": "सभी अपडेट", "colDate": "तिथि", "colStage": "अपडेट", "glH": "मुख्य जानकारी (अधिसूचना से)", "relH": f"{org} की और परीक्षाएँ",
          "note": "जानकारी आधिकारिक सूचनाओं से ली गई है। कोई बात अलग हो, तो आधिकारिक सूचना को ही सही मानें।"}
    rows = ""
    for k, n in enumerate(items):
        te, th = stage(n)
        en[f"i{k}"], hi[f"i{k}"] = title(n), title_hi(n)
        en[f"t{k}"], hi[f"t{k}"] = te, th
        en[f"d{k}"], hi[f"d{k}"] = d_en(n["notice_date"]), d_hi(n["notice_date"])
        rows += (f'      <a class="r" href="/notice/{n["slug"]}/"><span class="num" data-t="d{k}">{esc(en[f"d{k}"])}</span>'
                 f'<span class="v"><span data-t="i{k}">{esc(en[f"i{k}"])}</span> <small class="g" data-t="t{k}">{esc(te)}</small></span></a>\n')
    main = [f'''    <div class="title">
      <nav class="crumb" aria-label="Breadcrumb"><a href="/exam/" data-t="crumbType">Exams</a><span class="sep" aria-hidden="true">/</span><span class="here" aria-current="page" data-t="org">{esc(org)}</span></nav>
      <h1 data-t="h1">{esc(en["h1"])}</h1>
      <p class="lead" data-t="lead">{esc(en["lead"])}</p>
      <span id="state" hidden></span><span id="left" hidden></span><span id="views" hidden></span>
    </div>''',
            f'    <section class="kv tl" id="updates" data-t-aria="tlH">\n      <div class="h" data-t="tlH">All updates</div>\n{rows}    </section>']
    job = next((n for n in items if (n.get("card") or {}).get("type") == "Job" and (n.get("page") or {}).get("rows")), None)
    if job:
        body = ""
        for k, r in enumerate((job["page"].get("rows") or [])[:10]):
            if not (r.get("label_en") and r.get("value_en")):
                continue
            en[f"g{k}l"], hi[f"g{k}l"] = r["label_en"], r.get("label_hi") or r["label_en"]
            en[f"g{k}v"], hi[f"g{k}v"] = r["value_en"], r.get("value_hi") or r["value_en"]
            body += f'      <div class="r"><span data-t="g{k}l">{esc(r["label_en"])}</span><span class="v" data-t="g{k}v">{esc(r["value_en"])}</span></div>\n'
        if body:
            main.append(f'    <section class="kv" data-t-aria="glH">\n      <div class="h" data-t="glH">Key facts (from the notification)</div>\n{body}    </section>')
    others = [b for b in board_exams if b["key"] != x["key"]][:6]
    if others:
        body = ""
        for k, o in enumerate(others):
            en[f"o{k}"], hi[f"o{k}"] = o["name_en"], o["name_hi"] or o["name_en"]
            body += f'      <a class="r" href="/exam/{o["key"]}/"><span data-t="o{k}">{esc(o["name_en"])}</span><span class="v g num">{esc(d_en(o["latest"]))}</span></a>\n'
        main.append(f'    <section class="kv rel" data-t-aria="relH">\n      <div class="h" data-t="relH">{esc(en["relH"])}</div>\n{body}    </section>')
    main.append(f'    <div class="note"><p class="g" data-t="note">{esc(en["note"])}</p></div>\n    <a id="dlPdf" hidden></a><a id="share" hidden></a>')
    url = f'{SITE_URL}/exam/{x["key"]}/'
    ld = [{"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
              {"@type": "ListItem", "position": 1, "name": "SarkariChart", "item": f"{SITE_URL}/"},
              {"@type": "ListItem", "position": 2, "name": "Exams", "item": f"{SITE_URL}/exam/"},
              {"@type": "ListItem", "position": 3, "name": x["name_en"], "item": url}]},
          {"@context": "https://schema.org", "@type": "ItemList", "name": en["h1"], "url": url, "itemListOrder": "https://schema.org/ItemListOrderDescending",
           "itemListElement": [{"@type": "ListItem", "position": i + 1, "url": f'{SITE_URL}/notice/{n["slug"]}/', "name": title(n)} for i, n in enumerate(items)]}]
    main.append('    <script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False).replace("</", "<\\/") + "</script>")
    en["title"], hi["title"] = f'{x["name_en"]}: Notification, Admit Card, Result | SarkariChart', f'{x["name_hi"] or x["name_en"]}: सभी अपडेट | सरकारी चार्ट'
    tpl = TPL.read_text(encoding="utf-8")
    return (tpl.replace("{{TITLE}}", esc(en["title"])).replace("{{DESC}}", esc(en["lead"][:158])).replace("{{MAIN}}", "\n".join(main))
            .replace("{{T_EN}}", "\n".join(f"      {k}: {js(v)}," for k, v in en.items()))
            .replace("{{T_HI}}", "\n".join(f"      {k}: {js(v)}," for k, v in hi.items()))
            .replace("{{SLUG}}", "exam-" + x["key"]).replace("{{OGIMG}}", f'{SITE_URL}/notice/{latest["slug"]}/og.png')
            .replace("{{OGALT}}", esc(f'{x["name_en"]} — all updates on SarkariChart')).replace("{{URL}}", url).replace("{{LAST}}", "null"))


def render_index(g: dict) -> str:
    esc = html.escape
    js = lambda v: json.dumps("" if v is None else str(v), ensure_ascii=False)
    en = {"h1": "Exams", "lead": "Every exam with more than one official update, newest activity first.", "crumbType": "Home", "org": "Exams"}
    hi = {"h1": "परीक्षाएँ", "lead": "हर परीक्षा जिसकी एक से ज़्यादा आधिकारिक सूचना आई है, ताज़ा पहले।", "crumbType": "होम", "org": "परीक्षाएँ"}
    rows = ""
    for k, x in enumerate(sorted(g.values(), key=lambda x: x["latest"], reverse=True)):
        en[f"x{k}"], hi[f"x{k}"] = x["name_en"], x["name_hi"] or x["name_en"]
        en[f"n{k}"], hi[f"n{k}"] = f'{len(x["items"])} updates · {d_en(x["latest"])}', f'{len(x["items"])} अपडेट · {d_hi(x["latest"])}'
        rows += f'      <a class="r" href="/exam/{x["key"]}/"><span data-t="x{k}">{esc(x["name_en"])}</span><span class="v g" data-t="n{k}">{esc(en[f"n{k}"])}</span></a>\n'
    main = f'''    <div class="title">
      <h1 data-t="h1">Exams</h1>
      <p class="lead" data-t="lead">{esc(en["lead"])}</p>
      <span id="state" hidden></span><span id="left" hidden></span><span id="views" hidden></span>
    </div>
    <section class="kv rel">
{rows}    </section>
    <a id="dlPdf" hidden></a><a id="share" hidden></a>'''
    en["title"], hi["title"] = "Exams: all updates by exam | SarkariChart", "परीक्षाएँ | सरकारी चार्ट"
    tpl = TPL.read_text(encoding="utf-8")
    return (tpl.replace("{{TITLE}}", esc(en["title"])).replace("{{DESC}}", esc(en["lead"])).replace("{{MAIN}}", main)
            .replace("{{T_EN}}", "\n".join(f"      {k}: {js(v)}," for k, v in en.items()))
            .replace("{{T_HI}}", "\n".join(f"      {k}: {js(v)}," for k, v in hi.items()))
            .replace("{{SLUG}}", "exams").replace("{{OGIMG}}", f"{SITE_URL}/og.png").replace("{{OGALT}}", "SarkariChart exams")
            .replace("{{URL}}", f"{SITE_URL}/exam/").replace("{{LAST}}", "null"))


def homepage_data(g: dict):
    """Rows for the homepage "Exams" tab: written into site/index.html between /*EXAMS:START*/ and /*EXAMS:END*/."""
    rows = []
    for x in sorted(g.values(), key=lambda x: x["latest"], reverse=True):
        se, sh = TYPE.get((x["items"][0].get("card") or {}).get("type", "Job"), TYPE["Job"])   # short, fits the column
        rows.append({"key": x["key"], "en": x["name_en"], "hi": x["name_hi"] or x["name_en"], "org": x["items"][0].get("org") or "",
                     "n": len(x["items"]), "latest": x["latest"], "st_en": se, "st_hi": sh})
    p = SITE / "index.html"
    s = p.read_text(encoding="utf-8")
    data = json.dumps(rows, ensure_ascii=False).replace("</", "<\\/")
    s = re.sub(r"/\*EXAMS:START\*/.*?/\*EXAMS:END\*/", lambda m: "/*EXAMS:START*/" + data + "/*EXAMS:END*/", s, count=1, flags=re.S)
    p.write_text(s, encoding="utf-8")


def build():
    g = groups()
    out = SITE / "exam"
    out.mkdir(parents=True, exist_ok=True)
    live = set()
    by_board = {}
    for x in g.values():
        by_board.setdefault(x["items"][0].get("org"), []).append(x)
    for v in by_board.values():
        v.sort(key=lambda x: x["latest"], reverse=True)
    for x in g.values():
        d = out / x["key"]
        d.mkdir(exist_ok=True)
        (d / "index.html").write_text(render(x, by_board.get(x["items"][0].get("org"), [])), encoding="utf-8")
        live.add(x["key"])
    for d in out.iterdir():          # exams that dropped below the threshold (e.g. a notice was rejected)
        if d.is_dir() and d.name not in live:
            for f in d.iterdir():
                f.unlink()
            d.rmdir()
    (out / "index.html").write_text(render_index(g), encoding="utf-8")
    homepage_data(g)
    print(f"exams: {len(g)} exam pages")


if __name__ == "__main__":
    {"tag": tag, "build": build}.get(sys.argv[1] if len(sys.argv) > 1 else "build", build)()
