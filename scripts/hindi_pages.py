"""Hindi copies of the homepage and the job-type / state / qualification pages, at /hi/... (notice pages get theirs
from pages.py). Each copy has Hindi text in the HTML itself, a Hindi title and snippet, its own canonical address and
hreflang links both ways; links inside a Hindi page go to the Hindi copy where one exists. Run after hubs.py and
seo_pages.py: python3 scripts/hindi_pages.py
"""
from __future__ import annotations

import html
import json
import os
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
SITE_URL = os.environ.get("SITE_URL", "https://sarkarichart.com")
HOME_TITLE = "सरकारी नौकरी 2026 – नई भर्ती, एडमिट कार्ड, रिज़ल्ट | सरकारी चार्ट"
HOME_DESC = ("सरकारी नौकरी 2026: हर नई सरकारी भर्ती, एडमिट कार्ड, आंसर की और रिज़ल्ट सीधे आधिकारिक वेबसाइटों से, हिंदी में। "
             "अंतिम तिथि, फीस और आवेदन के सीधे लिंक।")


def hi_dict(s: str) -> dict:
    """The page's own Hindi strings (the `hi: {...}` block the page script uses)."""
    i = s.find("hi: {")
    if i < 0:
        return {}
    block = s[i:s.find("\n    },", i)]
    return {k: json.loads(v) for k, v in re.findall(r'(?<![\w.$])(\w+):\s*("(?:[^"\\]|\\.)*")\s*[,\n}]', block)}


def alt_links(en_url: str, hi_url: str, canonical: str) -> str:
    return (f'<link rel="canonical" href="{canonical}">\n<link rel="alternate" hreflang="en" href="{en_url}">\n'
            f'<link rel="alternate" hreflang="hi" href="{hi_url}">\n<link rel="alternate" hreflang="x-default" href="{en_url}">')


def local_links(h: str) -> str:
    """Point links at the Hindi copy of a page when there is one."""
    def fix(m):
        path = m.group(2)
        if path == "/" or (path.startswith("/notice/") or re.fullmatch(r"/[a-z0-9-]+-jobs/", path)) and (SITE / "hi" / path.strip("/") / "index.html").exists():
            return f'{m.group(1)}"/hi{path}"'
        return m.group(0)
    return re.sub(r'(href=)"(/(?:notice/[a-z0-9-]+/|[a-z0-9-]+-jobs/)?)"', fix, h)


def to_hindi(s: str, path: str, title: str, desc: str) -> str:
    en_url, hi_url = f"{SITE_URL}/{path}", f"{SITE_URL}/hi/{path}"
    hi = hi_dict(s)
    h = s.replace('<html lang="en">', '<html lang="hi" data-pl="hi">', 1)
    h = re.sub(r'<link rel="canonical" href="[^"]*">(\n<link rel="alternate" hreflang="[^"]*" href="[^"]*">)*',
               lambda m: alt_links(en_url, hi_url, hi_url), h, 1)
    h = re.sub(r"<title>[^<]*</title>", lambda m: f"<title>{html.escape(title)}</title>", h, 1)
    h = re.sub(r'(<meta (?:name="description"|property="og:description"|name="twitter:description") content=")[^"]*"',
               lambda m: m.group(1) + html.escape(desc) + '"', h)
    h = re.sub(r'(<meta (?:property="og:title"|name="twitter:title") content=")[^"]*"', lambda m: m.group(1) + html.escape(title) + '"', h)
    h = re.sub(r'(<meta property="og:url" content=")[^"]*"', lambda m: m.group(1) + hi_url + '"', h)
    h = re.sub(r'(data-t="([^"]+)"[^>]*>)([^<]*)<',
               lambda m: m.group(1) + (html.escape(hi[m.group(2)]) if isinstance(hi.get(m.group(2)), str) else m.group(3)) + "<", h)
    return local_links(h)


def add_alts(f: pathlib.Path, path: str) -> None:
    """hreflang links on the English page (once)."""
    s = f.read_text(encoding="utf-8")
    if 'hreflang="hi"' in s:
        return
    en_url, hi_url = f"{SITE_URL}/{path}", f"{SITE_URL}/hi/{path}"
    s = re.sub(r'<link rel="canonical" href="[^"]*">', lambda m: alt_links(en_url, hi_url, en_url), s, 1)
    f.write_text(s, encoding="utf-8")


def main() -> None:
    n = 0
    hubs = [d for d in sorted(SITE.iterdir()) if d.is_dir() and d.name.endswith("-jobs") and (d / "index.html").exists()]
    for d in hubs:                      # job-type, state and qualification pages
        s = (d / "index.html").read_text(encoding="utf-8")
        hi = hi_dict(s)
        if not hi.get("h1"):
            continue
        out = SITE / "hi" / d.name / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        title = hi.get("title") or f'{hi["h1"]} | सरकारी चार्ट'
        out.write_text(to_hindi(s, f"{d.name}/", title, (hi.get("lead") or hi["h1"])[:158]), encoding="utf-8")
        add_alts(d / "index.html", f"{d.name}/")
        n += 1
    # the homepage (its list is drawn by the page script; in Hindi it links to the Hindi notice pages)
    s = (SITE / "index.html").read_text(encoding="utf-8")
    (SITE / "hi").mkdir(exist_ok=True)
    (SITE / "hi" / "index.html").write_text(to_hindi(s, "", hi_dict(s).get("title") or HOME_TITLE, HOME_DESC), encoding="utf-8")
    # Hindi notice pages: their links to other notices and to job pages go to the Hindi copies
    for f in (SITE / "hi" / "notice").glob("*/index.html"):
        s = f.read_text(encoding="utf-8")
        t = local_links(s)
        if t != s:
            f.write_text(t, encoding="utf-8")
    print(f"hindi pages: homepage + {n} job pages")


if __name__ == "__main__":
    main()
