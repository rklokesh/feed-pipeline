"""Dump every link on a board page (plain fetch + headless browser) so a board can be tuned by hand.

  python scripts/probe_links.py <id>=<url> [<id>=<url> ...]   ->  reports/links/<id>.txt
"""
from __future__ import annotations

import pathlib
import sys
from urllib.parse import urljoin

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from bs4 import BeautifulSoup  # noqa: E402

import common  # noqa: E402

OUT = pathlib.Path(__file__).resolve().parent.parent / "reports" / "links"
OUT.mkdir(parents=True, exist_ok=True)


def dump(html: str, base: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for a in soup.find_all(["a", "iframe", "frame"]):
        href = a.get("href") or a.get("src") or ""
        if not href or href.startswith(("javascript:void", "#")):
            continue
        rows.append(f"{' '.join(a.get_text(' ').split())[:140]} | {urljoin(base, href.strip())}")
    return rows


for arg in sys.argv[1:]:
    sid, url = arg.split("=", 1)
    lines = [f"# {sid} {url}"]
    try:
        r = common.get(url, attempts=1)
        lines.append(f"## plain fetch: HTTP {r.status_code}, {len(r.content)} bytes, final {r.url}")
        lines += dump(r.text, r.url)
    except Exception as e:  # noqa: BLE001
        lines.append(f"## plain fetch failed: {e}"[:400])
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page(user_agent=common.BROWSER_UA, ignore_https_errors=False)
            pg.goto(url, timeout=90_000, wait_until="networkidle")
            pg.wait_for_timeout(3000)
            html = pg.content()
            lines.append(f"## browser: final {pg.url}, title {pg.title()!r}, {len(html)} chars")
            lines += dump(html, pg.url)
            for fr in pg.frames[1:]:
                try:
                    lines.append(f"## frame {fr.url}")
                    lines += dump(fr.content(), fr.url)
                except Exception:  # noqa: BLE001
                    pass
            b.close()
    except Exception as e:  # noqa: BLE001
        lines.append(f"## browser failed: {e}"[:400])
    (OUT / f"{sid}.txt").write_text("\n".join(lines))
    print(sid, len(lines))
