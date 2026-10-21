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
from common import USER_AGENT, download, get  # noqa: E402
from extract import classify, extract, pdf_text  # noqa: E402

DATA = "data"
PDF_HINTS = re.compile(r"(\.pdf($|\?))|open_pdf|/api/attachment/|writereaddata|/uploads?/", re.I)
GENERIC = re.compile(r"^(click\s*here|view|download|read\s*more|details?|pdf|new|link|open|here|more)\W*$", re.I)
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
        if len(title) < 8 or GENERIC.match(title):  # "Click here", "View" -> use the row/item text
            parent = a.find_parent(["tr", "li", "p", "div"])
            title = clean(parent.get_text(" ")) if parent else title
        out.append({"url": url, "title": title[:300] or os.path.basename(urlparse(url).path)})
    return out


def links_with_browser(url: str) -> list[dict]:
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
            found.append({"url": urljoin(url, obj), "title": ctx[:300]})

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
    for item in links_from_html(html, url) + found:
        if item["url"] not in seen:
            seen.add(item["url"])
            merged.append(item)
    return merged


def process(src: dict, item: dict, ai_budget: list[int]) -> dict:
    kind = classify(item["title"])
    rec = {"id": nid(item["url"]), "source_id": src["id"], "org": src["org"], "title": item["title"],
           "url": item["url"], "board_url": src["url"], "kind": kind, "first_seen": NOW,
           "status": "pending_review", "fields": {}, "pdf": {}}
    if kind == "noise":
        rec["status"] = "ignored"
        return rec
    try:
        data = download(item["url"])
        rec["pdf"]["sha256"] = hashlib.sha256(data).hexdigest()
        rec["pdf"]["bytes"] = len(data)
        if data.startswith(b"%PDF"):
            text, tkind, pages = pdf_text(data)
            rec["pdf"].update({"text_kind": tkind, "pages": pages})
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
    summary = []

    for src in sources:
        h = health.setdefault(src["id"], {})
        try:
            if src.get("render") == "js":
                items = links_with_browser(src["url"])
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
            h["last_error"] = f"{type(e).__name__}: {e}"[:200]
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
            rec = process(src, item, ai_budget)
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
