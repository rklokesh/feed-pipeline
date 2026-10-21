#!/usr/bin/env python3
"""Step 1 probe: can we reach each official notice board from this machine,
and are their PDFs real text or scans?

Usage: python scripts/probe.py [--sources sources/sources.yaml] [--out out/] [--pdfs 3] [--render-js]
Writes out/results.json and out/report.md (and appends the report to
$GITHUB_STEP_SUMMARY when running in GitHub Actions).
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import time
import urllib.robotparser
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from urllib.parse import urljoin, urlparse

import requests
import yaml
from bs4 import BeautifulSoup

USER_AGENT = "SarkariChartBot/0.1 (+https://sarkarichart.com/bot; job-alert indexer)"
TIMEOUT = int(os.environ.get("PROBE_TIMEOUT", "30"))
MAX_PDF_BYTES = 15 * 1024 * 1024
PDF_HINTS = re.compile(r"(\.pdf($|\?))|open_pdf|/api/attachment/|writereaddata|download", re.I)

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en-IN,en;q=0.9,hi;q=0.8"})


@dataclass
class PdfCheck:
    url: str
    ok: bool = False
    kind: str = "unknown"  # text | scanned | not-pdf | failed
    pages: int = 0
    chars_first_pages: int = 0
    bytes: int = 0
    error: str = ""


@dataclass
class SourceResult:
    id: str
    org: str
    url: str
    render: str
    status: int | None = None
    final_url: str = ""
    seconds: float = 0.0
    bytes: int = 0
    content_type: str = ""
    error: str = ""
    attempts: int = 0
    robots_allows: bool | None = None
    links: int = 0
    pdf_links: int = 0
    text_chars: int = 0
    looks_js_rendered: bool = False
    rendered_pdf_links: int | None = None
    verdict: str = ""
    pdfs: list[PdfCheck] = field(default_factory=list)


def robots_ok(url: str) -> bool | None:
    p = urlparse(url)
    rp = urllib.robotparser.RobotFileParser()
    try:
        r = session.get(f"{p.scheme}://{p.netloc}/robots.txt", timeout=15)
        if r.status_code >= 400:
            return True  # no robots file = allowed
        rp.parse(r.text.splitlines())
        return rp.can_fetch(USER_AGENT, url)
    except requests.RequestException:
        return None


def fetch(url: str, attempts: int = 3):
    last_err = ""
    for i in range(1, attempts + 1):
        t0 = time.time()
        try:
            r = session.get(url, timeout=TIMEOUT, allow_redirects=True)
            return r, time.time() - t0, i, ""
        except requests.RequestException as e:
            last_err = f"{type(e).__name__}: {e}"[:300]
            time.sleep(2 ** i)  # back off: official sites are often overloaded
    return None, 0.0, attempts, last_err


def pdf_candidates(html: str, base: str) -> tuple[int, list[str], int]:
    soup = BeautifulSoup(html, "html.parser")
    hrefs = [urljoin(base, a["href"]) for a in soup.find_all("a", href=True)]
    pdfs, seen = [], set()
    for h in hrefs:
        if PDF_HINTS.search(h) and h not in seen and h.startswith("http"):
            seen.add(h)
            pdfs.append(h)
    text = soup.get_text(" ", strip=True)
    return len(hrefs), pdfs, len(text)


def check_pdf(url: str) -> PdfCheck:
    res = PdfCheck(url=url)
    try:
        r = session.get(url, timeout=TIMEOUT, stream=True)
        data = b""
        for chunk in r.iter_content(64 * 1024):
            data += chunk
            if len(data) > MAX_PDF_BYTES:
                break
        res.bytes = len(data)
        if not data.startswith(b"%PDF"):
            res.kind = "not-pdf"
            return res
        import pdfplumber

        with pdfplumber.open(io.BytesIO(data)) as pdf:
            res.pages = len(pdf.pages)
            chars = 0
            for page in pdf.pages[:2]:
                chars += len((page.extract_text() or "").strip())
            res.chars_first_pages = chars
            res.kind = "text" if chars >= 200 else "scanned"
            res.ok = True
    except Exception as e:  # noqa: BLE001 - report everything
        res.kind = "failed"
        res.error = f"{type(e).__name__}: {e}"[:200]
    return res


def render_with_browser(url: str) -> list[str] | None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page(user_agent=USER_AGENT)
            page.goto(url, timeout=60_000, wait_until="networkidle")
            html = page.content()
            b.close()
        _, pdfs, _ = pdf_candidates(html, url)
        return pdfs
    except Exception:  # noqa: BLE001
        return []


def probe(src: dict, n_pdfs: int, render_js: bool) -> SourceResult:
    res = SourceResult(id=src["id"], org=src["org"], url=src["url"], render=src.get("render", "static"))
    res.robots_allows = robots_ok(res.url)
    r, secs, attempts, err = fetch(res.url)
    res.attempts, res.seconds = attempts, round(secs, 2)
    if r is None:
        res.error, res.verdict = err, "UNREACHABLE"
        return res
    res.status, res.final_url = r.status_code, r.url
    res.bytes, res.content_type = len(r.content), r.headers.get("content-type", "")
    if r.status_code >= 400:
        res.verdict = "BLOCKED" if r.status_code in (401, 403, 429, 451) else f"HTTP {r.status_code}"
        return res
    res.links, pdfs, res.text_chars = pdf_candidates(r.text, r.url)
    res.pdf_links = len(pdfs)
    res.looks_js_rendered = res.text_chars < 600 or res.links < 10
    if (res.render == "js" or res.looks_js_rendered) and render_js:
        rendered = render_with_browser(res.url)
        if rendered is not None:
            res.rendered_pdf_links = len(rendered)
            if len(rendered) > len(pdfs):
                pdfs = rendered
    res.pdfs = [check_pdf(u) for u in pdfs[:n_pdfs]]
    if not pdfs:
        res.verdict = "OK, NO PDF LINKS FOUND" if not res.looks_js_rendered else "NEEDS BROWSER"
    else:
        res.verdict = "OK"
    return res


def report(results: list[SourceResult]) -> str:
    ok = [r for r in results if r.verdict.startswith("OK")]
    bad = [r for r in results if not r.verdict.startswith("OK")]
    pdfs = [p for r in results for p in r.pdfs]
    text = sum(p.kind == "text" for p in pdfs)
    scanned = sum(p.kind == "scanned" for p in pdfs)
    lines = [
        "# SarkariChart probe report",
        "",
        f"- Sources reachable: **{len(ok)} / {len(results)}**",
        f"- PDFs sampled: {len(pdfs)} — text: **{text}**, scanned: **{scanned}**, other/failed: {len(pdfs) - text - scanned}",
        f"- robots.txt disallows our bot on: {', '.join(r.id for r in results if r.robots_allows is False) or 'none'}",
        "",
        "| Source | Verdict | HTTP | Time (s) | Links | PDF links | PDFs text/scanned | Note |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in sorted(results, key=lambda x: (x.verdict.startswith("OK"), x.id)):
        ts = f"{sum(p.kind == 'text' for p in r.pdfs)}/{sum(p.kind == 'scanned' for p in r.pdfs)}"
        note = r.error or (f"redirect → {r.final_url}" if r.final_url and r.final_url.rstrip('/') != r.url.rstrip('/') else "")
        if r.rendered_pdf_links is not None:
            note += f" browser found {r.rendered_pdf_links} PDF links"
        lines.append(
            f"| {r.org} (`{r.id}`) | {r.verdict} | {r.status or '-'} | {r.seconds} | {r.links} | {r.pdf_links} | {ts} | {note[:120]} |"
        )
    if bad:
        lines += ["", "**Needs attention:** " + ", ".join(f"`{r.id}`" for r in bad)]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sources", default="sources/sources.yaml")
    ap.add_argument("--out", default="out")
    ap.add_argument("--pdfs", type=int, default=3)
    ap.add_argument("--render-js", action="store_true")
    ap.add_argument("--only", help="comma-separated source ids")
    a = ap.parse_args()

    with open(a.sources, encoding="utf-8") as f:
        sources = yaml.safe_load(f)["sources"]
    if a.only:
        keep = set(a.only.split(","))
        sources = [s for s in sources if s["id"] in keep]

    # Browser rendering is not thread-safe here, so run JS sources after the pool.
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda s: probe(s, a.pdfs, False), sources))
    if a.render_js:
        for i, (s, r) in enumerate(zip(sources, results)):
            if r.verdict in ("NEEDS BROWSER", "OK, NO PDF LINKS FOUND") or s.get("render") == "js":
                results[i] = probe(s, a.pdfs, True)

    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "results.json"), "w", encoding="utf-8") as f:
        json.dump([asdict(r) for r in results], f, indent=2, ensure_ascii=False)
    md = report(results)
    with open(os.path.join(a.out, "report.md"), "w", encoding="utf-8") as f:
        f.write(md)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(md)
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
