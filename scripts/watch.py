#!/usr/bin/env python3
"""SarkariChart watcher: find new notices on official boards, extract them,
and queue them for human review.

  python scripts/watch.py --runner github          # sources reachable from GitHub
  python scripts/watch.py --runner india           # sources needing an Indian IP

State lives in data/:
  data/seen.json             every link already seen, per source
  data/notices/<id>.json     one file per new notice (fields + status)
  data/text/<id>.txt         extracted PDF text, for review
  data/review-queue.md       human-readable list of notices awaiting review
  data/health.json           per-source health (alerts when a board goes quiet/breaks)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import yaml
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(__file__))
from common import USER_AGENT, download, get, last_repair_error  # noqa: E402
from extract import classify, extract, pdf_text  # noqa: E402

DATA = "data"
PDF_HINTS = re.compile(r"(\.pdf($|\?))|open_pdf|/api/attachment/|writereaddata|/uploads?/", re.I)
GENERIC = re.compile(r"^(click\s*here|view|download|read\s*more|details?|pdf|new|link|open|here|more)\W*$", re.I)
FRAGMENT = re.compile(r"\(\s*\d+(\.\d+)?\s*[KM]B\s*\)|^[a-z]", re.I)
NOW = datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def save(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False, sort_keys=True)
        f.write("\n")


def nid(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:12]


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def links_from_html(html: str, base: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    out, seen = [], set()
    for a in soup.find_all("a", href=True):
        url = urljoin(base, a["href"].strip())
        if not url.startswith("http") or url in seen or not PDF_HINTS.search(url):
            continue
        seen.add(url)
        title = clean(a.get_text(" ")) or clean(a.get("title", ""))
        if len(title) < 25 or GENERIC.match(title) or FRAGMENT.search(title) or not title[:1].isalnum():
            # "Click here", "English) (959 KB)" -> use the whole row/item text instead
            parent = a.find_parent(["tr", "li", "p", "div"])
            title = clean(parent.get_text(" ")) if parent else title
        out.append({"url": url, "title": title[:300] or os.path.basename(urlparse(url).path)})
    return out


def links_with_browser(url: str, prefix: str = "") -> list[dict]:
    """For JS-rendered boards (e.g. SSC): render the page and also read JSON the page loads."""
    from playwright.sync_api import sync_playwright

    found: list[dict] = []

    def walk(obj, ctx=""):
        if isinstance(obj, dict):
            label = clean(str(obj.get("title") or obj.get("name") or obj.get("headline") or obj.get("subject") or ctx))
            for v in obj.values():
                walk(v, label)
        elif isinstance(obj, list):
            for v in obj:
                walk(v, ctx)
        elif isinstance(obj, str) and PDF_HINTS.search(obj):
            path = obj.replace("\\", "/")
            if path.startswith("http"):
                full = path
            elif prefix and "/" in path:
                full = prefix + path.lstrip("/")
            elif "/" in path:
                full = urljoin(url, path)
            else:
                return  # a bare file name with no folder can't be resolved reliably
            found.append({"url": full, "title": ctx[:300]})

    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(user_agent=USER_AGENT)

        def on_response(resp):
            if "json" in (resp.headers.get("content-type") or ""):
                try:
                    walk(resp.json())
                except Exception:  # noqa: BLE001
                    pass

        page.on("response", on_response)
        page.goto(url, timeout=90_000, wait_until="networkidle")
        html = page.content()
        b.close()
    merged, seen = [], set()
    html_links = [i for i in links_from_html(html, url) if not (prefix and "\\" in i["url"])]
    for item in found + html_links:
        if item["url"] not in seen:
            seen.add(item["url"])
            merged.append(item)
    return merged


def links_following(src: dict) -> list[dict]:
    """Boards that list each recruitment on its own sub-page (e.g. RRB: getdata?cennum=07/2026&loc=...).
    Open the board in a real browser session, then visit each matching sub-page from there (the site rejects
    direct visits), and collect the notice links on every sub-page."""
    from playwright.sync_api import sync_playwright
    from common import BROWSER_UA

    pat = re.compile(src["follow"])
    key = re.compile(src.get("follow_key", src["follow"]))   # one sub-page per key (e.g. per CEN number)
    limit = int(src.get("follow_limit", 12))
    out, seen = [], set()
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(user_agent=BROWSER_UA)
        page = ctx.new_page()
        page.set_default_timeout(45_000)
        page.goto(src["url"], wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        home = page.url
        subs, keys = [], set()
        for a in page.eval_on_selector_all("a[href]", "els => els.map(e => [e.href, e.innerText])"):
            href = a[0]
            if pat.search(href):
                k = key.search(href).group(0)
                if k not in keys:
                    keys.add(k)
                    subs.append(href)
        dbg = [f"home {home} title={page.title()!r} subs={len(subs)}"]
        for href in subs[:limit]:
            try:
                page.goto(href, wait_until="domcontentloaded", referer=home)
                page.wait_for_timeout(1500)
                html_ = page.content()
                found = links_from_html(html_, page.url)
                dbg.append("   pdf-ish: " + " | ".join(sorted(set(re.findall(r"[^\"'\\s<>()]*(?:\\.pdf|/documents/|/-/image/|getfile|download)[^\"'\\s<>()]*", html_, re.I)))[:40]))
                dbg.append("   text: " + re.sub(r"\\s+", " ", page.inner_text("body"))[:1500])
                dbg.append(f"{href} -> {page.title()!r} {len(html_)} chars, {len(found)} links; "
                           + " | ".join(f"{t[1][:80]}={t[0]}" for t in page.eval_on_selector_all("a[href]", "els => els.map(e => [e.href, e.innerText.replace(/\\s+/g, ' ')])")
                                       if re.search(r"pdf|/-/|document|download|notice|cen", t[0], re.I) and "getdata" not in t[0])[:60])
                # RRB-style document links live in scripts/attributes as /-/image/<id><File name>.pdf/<x>
                for m in re.finditer(r"/-/image/(\d{6,})([^\"'<>]+?)(?:\.pdf)?(?:/[^\"'<>\s]*)?(?=[\"'<>])", html_):
                    name = re.sub(r"[_\s]+", " ", m.group(2)).strip(" -.")
                    if re.search(r"hindi|हिंदी|हिन्दी", name, re.I) or len(name) < 3:
                        continue   # the English copy is enough; the AI writes the Hindi card
                    u = urljoin(page.url, m.group(0))
                    if u not in seen:
                        seen.add(u)
                        cen = (re.search(r"cennum=([\d/]+)", href) or [None, ""])[1]
                        out.append({"url": u, "title": f"RRB CEN {cen}: {name}"[:300]})
                for item in found:
                    if item["url"] not in seen:
                        seen.add(item["url"])
                        out.append(item)
            except Exception as e:  # noqa: BLE001
                dbg.append(f"{href}: {e}"[:300])
        b.close()
    os.makedirs(DATA, exist_ok=True)
    with open(f"{DATA}/debug-{src['id']}.txt", "w") as fh:
        fh.write("\n".join(dbg))
    return out


def browser_download(board: str, url: str) -> bytes | None:
    """Fetch a file the way a visitor would: open the board first, then the file, in one browser session."""
    from playwright.sync_api import sync_playwright

    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            ctx = b.new_context(user_agent=USER_AGENT, accept_downloads=True)
            page = ctx.new_page()
            page.goto(board, timeout=90_000, wait_until="domcontentloaded")
            resp = ctx.request.get(url, headers={"Referer": board}, timeout=90_000)
            body = resp.body()
            if not body.startswith(b"%PDF"):
                page.goto(url, timeout=90_000, wait_until="networkidle")
                for frame in page.frames:
                    if ".pdf" in frame.url.lower():
                        body = ctx.request.get(frame.url).body()
                        break
            b.close()
            return body
    except Exception:  # noqa: BLE001
        return None


def embedded_pdf(data: bytes, base: str) -> str | None:
    """If a 'PDF' link returned an HTML viewer page, find the real PDF inside it."""
    try:
        soup = BeautifulSoup(data[:500_000].decode("utf-8", "replace"), "html.parser")
    except Exception:  # noqa: BLE001
        return None
    for tag, attr in (("iframe", "src"), ("embed", "src"), ("object", "data"), ("a", "href")):
        for el in soup.find_all(tag):
            v = (el.get(attr) or "").strip()
            if v and (".pdf" in v.lower() or tag != "a"):
                return urljoin(base, v)
    m = re.search(rb"""["']([^"']+\.pdf[^"']*)["']""", data, re.I)
    return urljoin(base, m.group(1).decode("utf-8", "replace")) if m else None


def known_hashes() -> dict:
    out = {}
    d = f"{DATA}/notices"
    for fn in os.listdir(d) if os.path.isdir(d) else []:
        r = load(os.path.join(d, fn), {})
        h = (r.get("pdf") or {}).get("sha256")
        if h and r.get("status") != "duplicate":
            out.setdefault(h, r["id"])
    return out


def process(src: dict, item: dict, ai_budget: list[int], hashes: dict) -> dict:
    kind = classify(item["title"])
    rec = {"id": nid(item["url"]), "source_id": src["id"], "org": src["org"], "title": item["title"],
           "url": item["url"], "board_url": src["url"], "kind": kind, "first_seen": NOW,
           "status": "pending_review", "fields": {}, "pdf": {}}
    if kind == "noise":
        rec["status"] = "ignored"
        return rec
    try:
        data = download(item["url"], referer=src["url"])
        if not data.startswith(b"%PDF") and src.get("download") == "browser":
            data = browser_download(src["url"], item["url"]) or data
        if not data.startswith(b"%PDF"):
            inner = embedded_pdf(data, item["url"])  # e.g. UPPSC's Open_PDF_DB viewer page
            if inner:
                rec["pdf"]["via"] = inner
                data = download(inner)
        rec["pdf"]["sha256"] = hashlib.sha256(data).hexdigest()
        if rec["pdf"]["sha256"] in hashes:
            rec["status"], rec["duplicate_of"] = "duplicate", hashes[rec["pdf"]["sha256"]]
            return rec
        rec["pdf"]["bytes"] = len(data)
        if data.startswith(b"%PDF"):
            text, tkind, pages = pdf_text(data)
            rec["pdf"].update({"text_kind": tkind, "pages": pages})
            if kind in ("other", "notification"):
                kind = rec["kind"] = classify(item["title"], text)
            allow_ai = ai_budget[0] > 0
            fields, meta = extract(text, kind, allow_ai)
            if meta.get("ai"):
                ai_budget[0] -= 1
            rec["fields"], rec["extraction"] = fields, meta
            if text.strip():
                os.makedirs(f"{DATA}/text", exist_ok=True)
                open(f"{DATA}/text/{rec['id']}.txt", "w", encoding="utf-8").write(text[:20000])
        else:
            rec["pdf"]["text_kind"] = "not-pdf"
            rec["pdf"]["head"] = data[:120].decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        rec["pdf"]["error"] = f"{type(e).__name__}: {e}"[:200]
    return rec


def review_queue():
    rows = []
    d = f"{DATA}/notices"
    for fn in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        r = load(os.path.join(d, fn), {})
        if r.get("status") == "pending_review":
            rows.append(r)
    rows.sort(key=lambda r: r["first_seen"], reverse=True)

    def v(r, k):
        f = r["fields"].get(k)
        if not f:
            return "—"
        val = f["value"]
        if isinstance(val, dict) and "min" in val:
            val = f"{val.get('min')}–{val.get('max')}"
        elif isinstance(val, dict):
            val = ", ".join(f"{k} {x}" for k, x in val.items() if x is not None)
        elif isinstance(val, list):
            val = ", ".join(map(str, val))[:40]
        flag = " ⚠" if f.get("conflict") else (" (AI)" if f.get("source") == "ai" else "")
        return f"{val}{flag}"

    lines = [f"# Review queue — {len(rows)} pending", "", f"_Updated {NOW}_", "",
             "| Seen | Org | Type | Title | Last date | Vacancies | Age | Fee (₹) | PDF |",
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in rows:
        title = r["title"].replace("|", "/")[:90]
        lines.append(f"| {r['first_seen'][:10]} | {r['org']} | {r['kind']} | {title} | {v(r,'apply_last')} | "
                     f"{v(r,'total_vacancies')} | {v(r,'age_limit')} | {v(r,'fee_amounts') if 'fee_amounts' in r['fields'] else v(r,'fee')} | "
                     f"[open]({r['url']}) |")
    open(f"{DATA}/review-queue.md", "w", encoding="utf-8").write("\n".join(lines) + "\n")
    return len(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runner", default="github")
    ap.add_argument("--sources", default="sources/sources.yaml")
    ap.add_argument("--only", help="comma-separated source ids")
    ap.add_argument("--baseline-sample", type=int, default=int(os.environ.get("BASELINE_SAMPLE", "5")),
                    help="on a source's first run, mark all links seen but process this many newest as samples")
    ap.add_argument("--max-new", type=int, default=25, help="cap new notices processed per source per run")
    ap.add_argument("--reextract", action="store_true",
                    help="re-run extraction on pending notifications that are missing key fields")
    ap.add_argument("--ai-budget", type=int, default=int(os.environ.get("AI_BUDGET", "15")))
    a = ap.parse_args()

    sources = yaml.safe_load(open(a.sources, encoding="utf-8"))["sources"]
    sources = [s for s in sources if s.get("runner", "india") == a.runner and s.get("enabled", True)]
    if a.only:
        keep = set(a.only.split(","))
        sources = [s for s in sources if s["id"] in keep]

    seen = load(f"{DATA}/seen.json", {})
    health = load(f"{DATA}/health.json", {})
    ai_budget = [a.ai_budget]
    hashes = known_hashes()
    summary = []

    if a.reextract:
        by_id = {s["id"]: s for s in sources}
        for fn in sorted(os.listdir(f"{DATA}/notices")):
            rec = load(f"{DATA}/notices/{fn}", {})
            src = by_id.get(rec.get("source_id"))
            if src and rec.get("status") == "pending_review" and rec.get("kind") == "notification":
                new_rec = process(src, {"url": rec["url"], "title": rec["title"]}, ai_budget, {})
                new_rec["first_seen"] = rec["first_seen"]
                save(f"{DATA}/notices/{fn}", new_rec)
                summary.append(f"- re-extracted {rec['id']} ({src['org']}): ai={new_rec.get('extraction', {}).get('ai')}"[:200])
        sources = []  # re-extract only

    for src in sources:
        h = health.setdefault(src["id"], {})
        try:
            if src.get("follow"):
                items = links_following(src)
            elif src.get("render") == "js":
                items = links_with_browser(src["url"], src.get("attachment_prefix", ""))
            else:
                r = get(src["url"])
                r.raise_for_status()
                items = links_from_html(r.text, r.url)
            h.update({"last_ok": NOW, "last_links": len(items), "consecutive_failures": 0, "last_error": ""})
            if not items:
                h["warning"] = "page loaded but no notice links found — layout may have changed"
            else:
                h.pop("warning", None)
        except Exception as e:  # noqa: BLE001
            h["consecutive_failures"] = h.get("consecutive_failures", 0) + 1
            h["last_error"] = f"{type(e).__name__}: {e}"[-200:]
            host = urlparse(src["url"]).hostname
            if host in last_repair_error:
                h["cert_repair"] = last_repair_error[host]
            summary.append(f"- {src['org']}: FAILED ({h['last_error'][:80]})")
            continue

        known = set(seen.get(src["id"], []))
        first_run = src["id"] not in seen
        new = [i for i in items if i["url"] not in known]
        if first_run:
            to_process = new[: a.baseline_sample]
        else:
            to_process = new[: a.max_new]

        for item in to_process:
            rec = process(src, item, ai_budget, hashes)
            if rec.get("pdf", {}).get("sha256") and rec["status"] != "duplicate":
                hashes.setdefault(rec["pdf"]["sha256"], rec["id"])
            if first_run:
                rec["baseline_sample"] = True
            save(f"{DATA}/notices/{rec['id']}.json", rec)

        seen[src["id"]] = sorted(known | {i["url"] for i in items})
        summary.append(f"- {src['org']}: {len(items)} links, {len(new)} new"
                       f"{' (first run: baseline, ' + str(len(to_process)) + ' sampled)' if first_run else ''}")

    save(f"{DATA}/seen.json", seen)
    save(f"{DATA}/health.json", health)
    pending = review_queue()
    report = "\n".join([f"## Watch run {NOW} ({a.runner})", *summary, "",
                        f"Pending review: **{pending}** · AI calls left this run: {ai_budget[0]}"])
    print(report)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8").write(report + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
