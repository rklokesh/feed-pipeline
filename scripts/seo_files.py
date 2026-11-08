"""Search-engine files, rebuilt on every publish: site/sitemap.xml, site/robots.txt, site/llms.txt.

Before launch robots.txt keeps every crawler out (LAUNCHED = True). On domain day run scripts/go_live.py, which
flips LAUNCHED, switches the address to the real domain and removes the noindex tags.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
SITE_URL = os.environ.get("SITE_URL", "https://sarkarichart.com")
LAUNCHED = True   # go_live.py sets this to True
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
TYPE_EN = {"Job": "Job", "Result": "Result", "Admit card": "Admit card", "Answer key": "Answer key", "Update": "Update", "Admission": "Admission"}


def notices():
    out = []
    for f in sorted((ROOT / "data" / "notices").glob("*.json")):
        n = json.loads(f.read_text())
        if n.get("status") != "approved" or not n.get("slug") or not (SITE / "notice" / n["slug"] / "index.html").exists():
            continue
        c, pg = n.get("card") or {}, n.get("page") or {}
        posted = n.get("notice_date") or n["first_seen"][:10]
        changed = (n.get("published_at") or n.get("first_seen") or posted)[:10]
        out.append({"slug": n["slug"], "title": pg.get("h1_en") or c.get("title_en") or n.get("title") or "",
                    "type": c.get("type", "Job"), "org": n.get("org") or "", "posted": posted,
                    "lastmod": max(posted, changed), "last": pg.get("last_date") or c.get("last_date")})
    out.sort(key=lambda x: x["posted"], reverse=True)
    return out


def sitemap(items):
    today = dt.datetime.now(IST).date().isoformat()
    urls = [(f"{SITE_URL}/", today, "hourly", "1.0")]
    urls += [(f"{SITE_URL}/{p}/", "2026-10-28", "monthly", "0.3") for p in ("about", "contact", "privacy", "terms", "press")]
    urls += [(f"{SITE_URL}/notice/{i['slug']}/", i["lastmod"], "weekly", "0.8") for i in items]
    urls += [(f"{SITE_URL}/{d.name}/", today, "daily", "0.8") for d in sorted(SITE.iterdir())
             if d.is_dir() and (d.name.endswith("govt-jobs") or d.name in ("railway-jobs", "police-jobs", "bank-jobs", "teacher-jobs", "defence-jobs")) and (d / "index.html").exists()]
    exam_dir = SITE / "exam"
    if exam_dir.exists():
        urls.append((f"{SITE_URL}/exam/", today, "daily", "0.7"))
        urls += [(f"{SITE_URL}/exam/{d.name}/", today, "daily", "0.9") for d in sorted(exam_dir.iterdir()) if (d / "index.html").exists()]
    body = "".join(f"  <url><loc>{html.escape(u)}</loc><lastmod>{m}</lastmod><changefreq>{c}</changefreq><priority>{p}</priority></url>\n"
                   for u, m, c, p in urls)
    (SITE / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n'
                                       '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + body + "</urlset>\n", encoding="utf-8")


def robots():
    if LAUNCHED:
        txt = f"User-agent: *\nAllow: /\nDisallow: /api/\nDisallow: /report/\n\nSitemap: {SITE_URL}/sitemap.xml\n"
    else:
        txt = "# Pre-launch: keep search engines out until the real launch (scripts/go_live.py opens it).\nUser-agent: *\nDisallow: /\n"
    (SITE / "robots.txt").write_text(txt, encoding="utf-8")


def llms(items):
    """A plain guide for AI assistants and AI search: what the site is and where the facts are."""
    lines = ["# SarkariChart (सरकारी चार्ट)", "",
             "> Every new Indian government job, admit card, result and answer key from official websites, "
             "in English and Hindi. Each notice page is written from the official notice PDF and links to it.", "",
             "- Checks about 50 official recruitment boards every 30 minutes (UPSC, SSC, RRB, IBPS, state PSCs, police boards, banks, defence).",
             "- Dates shown are the dates the board issued the notice. If anything differs, the official notice is correct.",
             "- Independent website, not a government website. Free; never asks for money.", "",
             "## Pages", f"- [Home: latest notices]({SITE_URL}/)", f"- [About]({SITE_URL}/about/)",
             f"- [Contact]({SITE_URL}/contact/)", f"- [Sitemap]({SITE_URL}/sitemap.xml)", "",
             "## Latest notices"]
    for i in items[:60]:
        today = dt.datetime.now(IST).date().isoformat()
        extra = f", last date {i['last']}" if i["type"] == "Job" and str(i.get("last") or "") >= today else ""
        lines.append(f"- [{i['title']}]({SITE_URL}/notice/{i['slug']}/): {i['org']} · {TYPE_EN.get(i['type'], i['type'])} · issued {i['posted']}{extra}")
    (SITE / "llms.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    items = notices()
    sitemap(items)
    robots()
    llms(items)
    print(f"seo files: {len(items)} notices in sitemap.xml and llms.txt; robots {'open' if LAUNCHED else 'closed (pre-launch)'}")


if __name__ == "__main__":
    main()
