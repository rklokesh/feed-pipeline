"""Test homepage /v3/ (Nov 2026): a utility-first top for daily visitors, built from the live homepage.

Instead of the big hero: the compact header, the search box, a row of popular searches, a live "Today" strip
(new today, closing this week, results, admit cards, each one tap to its list) with "updated N min ago", then the
same tabs and list straight away. The live homepage is not touched; /v3/ is noindex and points Google at /.
Run after hubs.py: python3 scripts/home_v3.py
"""
from __future__ import annotations

import collections
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT / "site"

CSS = """<style>
/* v3: utility-first top */
.v3top { display: grid; gap: 14px; margin: 4px 0 26px; }
.v3top .search { margin: 0 !important; }
.v3top .search input { background: var(--page) !important; border: 1px solid color-mix(in srgb, var(--ink) 22%, transparent) !important; border-radius: 12px !important;
  padding: 13px 120px 13px 44px !important; box-shadow: 0 1px 2px rgba(0,0,0,.04); }
.v3top .search input:focus { border-color: color-mix(in srgb, var(--ink) 45%, transparent) !important; box-shadow: 0 0 0 3px color-mix(in srgb, var(--ink) 7%, transparent); }
.v3top .search .sicon { left: 14px !important; } .v3top .search .ph { left: 44px !important; right: 120px !important; }
.v3top .search .sf { right: 6px !important; } .v3top .search .sx { right: 50px !important; }
.v3chips { display: flex; gap: 8px; overflow-x: auto; scrollbar-width: none; margin: -2px 0 0; padding: 2px 0; }
.v3chips::-webkit-scrollbar { display: none; }
.v3chips .lbl { color: var(--grey); font-size: .8125rem; align-self: center; white-space: nowrap; }
.v3chips button { all: unset; cursor: pointer; white-space: nowrap; font-size: .875rem; padding: 6px 12px; border: 1px solid var(--line); border-radius: 999px; color: var(--ink); }
.v3chips button:hover { color: #8E1B1E; border-color: color-mix(in srgb, #8E1B1E 35%, var(--line)); }
.v3fresh { display: flex; align-items: center; gap: 8px; font-size: .8125rem; color: var(--grey); margin: 2px 0 -4px; }
.v3fresh .dot { width: 7px; height: 7px; border-radius: 50%; background: #1FA855; box-shadow: 0 0 0 3px color-mix(in srgb, #1FA855 18%, transparent); }
.v3today { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
.v3today button { all: unset; cursor: pointer; box-sizing: border-box; display: grid; gap: 2px; padding: 12px 14px; border: 1px solid var(--line); border-radius: 12px; background: var(--page); }
.v3today button:hover { border-color: color-mix(in srgb, #8E1B1E 35%, var(--line)); }
.v3today button:hover .n, .v3today button:hover .l { color: #8E1B1E; }
.v3today .n { font-size: 1.5rem; font-weight: 650; line-height: 1.1; color: var(--ink); font-variant-numeric: tabular-nums; }
.v3today .l { font-size: .8125rem; color: var(--grey); line-height: 1.3; }
.v3today .hot .n { color: var(--hot); }
#newline.off { display: none; }
.v3top { margin-top: -16px; }
@media (max-width: 640px) { .v3top { gap: 12px; margin: -26px 0 14px; } .v3today { grid-template-columns: 1fr 1fr; gap: 8px; } .v3today button { padding: 10px 12px; } .v3today .n { font-size: 1.3rem; } }
:root[data-theme="dark"] .v3chips button:hover, :root[data-theme="dark"] .v3today button:hover .n, :root[data-theme="dark"] .v3today button:hover .l { color: #F2A7A1; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) .v3chips button:hover, :root:not([data-theme="light"]) .v3today button:hover .n, :root:not([data-theme="light"]) .v3today button:hover .l { color: #F2A7A1; } }
</style>"""

JS = """<script>
/* v3 "Today" strip: counts from the same notices as the list; each box opens its tab */
addEventListener("DOMContentLoaded", function () {
  var D = window.SC_V3 || [], now = Date.now(), DAY = 864e5;
  var ist = function (t) { return new Date(t + 5.5 * 36e5).toISOString().slice(0, 10); };
  var today = ist(now), wk = ist(now + 7 * DAY), wkAgo = ist(now - 7 * DAY);
  var newToday = D.filter(function (i) { return i.p && ist(Date.parse(i.p)) === today; }).length;
  var closing = D.filter(function (i) { return i.t === "Job" && i.l && i.l >= today && i.l <= wk; }).length;
  var res = D.filter(function (i) { return i.t === "Result" && i.d >= wkAgo; }).length;
  var adm = D.filter(function (i) { return i.t === "Admit card" && i.d >= wkAgo; }).length;
  var last = Math.max.apply(null, D.map(function (i) { return i.p ? Date.parse(i.p) : 0; }).concat([0]));
  var box = document.getElementById("v3today"), fr = document.getElementById("v3fresh");
  function hi() { return document.documentElement.lang === "hi"; }
  function ago() {
    var m = Math.max(1, Math.round((Date.now() - last) / 6e4));
    if (hi()) return m < 60 ? m + " मिनट पहले" : m < 1440 ? Math.round(m / 60) + " घंटे पहले" : Math.round(m / 1440) + " दिन पहले";
    return m < 60 ? m + " min ago" : m < 1440 ? Math.round(m / 60) + " h ago" : Math.round(m / 1440) + " days ago";
  }
  function paint() {
    var H = hi(), tiles = [
      ["all", newToday, H ? "आज नई सूचनाएँ" : "New today", newToday > 0 ? "" : ""],
      ["soon", closing, H ? "इस हफ़्ते अंतिम तिथि" : "Closing this week", closing > 0 ? "hot" : ""],
      ["Result", res, H ? "रिज़ल्ट (7 दिन)" : "Results this week", ""],
      ["Admit card", adm, H ? "एडमिट कार्ड (7 दिन)" : "Admit cards this week", ""]];
    box.innerHTML = tiles.map(function (x) { return '<button type="button" data-go="' + x[0] + '" class="' + x[3] + '"><span class="n">' + x[1] + '</span><span class="l">' + x[2] + "</span></button>"; }).join("");
    if (last) fr.innerHTML = '<span class="dot" aria-hidden="true"></span>' + (H ? "अपडेट " + ago() + " · आधिकारिक वेबसाइटों से" : "Updated " + ago() + " · from official websites");
  }
  box.addEventListener("click", function (e) {
    var b = e.target.closest("button[data-go]"); if (!b) return;
    var tab = document.querySelector('.tabs button[data-cat="' + b.dataset.go + '"]'); if (tab) tab.click();
    var list = document.querySelector(".tabrow") || document.getElementById("list");
    if (list) list.scrollIntoView({ behavior: "smooth", block: "start" });
  });
  document.getElementById("v3chips").addEventListener("click", function (e) {
    var b = e.target.closest("button[data-q]"); if (!b) return;
    var q = document.getElementById("q"); q.value = b.dataset.q; q.dispatchEvent(new Event("input"));
    var list = document.querySelector(".tabrow"); if (list) list.scrollIntoView({ behavior: "smooth", block: "start" });
  });
  new MutationObserver(paint).observe(document.documentElement, { attributes: true, attributeFilter: ["lang"] });
  paint(); setInterval(paint, 60000);
});
</script>"""


def main() -> None:
    s = (SITE / "index.html").read_text(encoding="utf-8")
    # take the hero out, put the search box back at the top of the page
    old = re.search(r'    <section class="hero".*?</section>\n', s, flags=re.S)
    lab = re.search(r'      <label class="search" for="q">.*?</label>\n', old.group(0), flags=re.S) if old else None
    if old:
        s = s.replace(old.group(0), "", 1)
    s = re.sub(r'<!--HERO:START-->.*?<!--HERO:END-->\n?', "", s, flags=re.S)
    search = lab.group(0) if lab else ""
    m = re.search(r'    <label class="search" for="q">.*?</label>\n', s, flags=re.S)
    if m:   # (a homepage without the hero already has it in place)
        search = m.group(0); s = s.replace(search, "", 1)
    search = "\n".join(("  " + x[6:] if x.startswith("      ") else x) for x in search.split("\n"))
    # data for the strip: type, published, issued, last date (small)
    a = s.index("/*ITEMS:START*/") + len("/*ITEMS:START*/"); b = s.index("/*ITEMS:END*/")
    items = json.loads("[" + s[a:b].strip().rstrip(",").strip("[]") + "]")
    data = [{"t": i["type"], "p": i.get("publishedAt") or "", "d": i.get("posted") or "", "l": i.get("last") or ""} for i in items]
    # popular searches: the boards with the most live jobs and trending notices right now
    # what most aspirants look for; a chip shows only when there is something for it right now
    POPULAR = ["SSC", "Railway", "UP Police", "Bank", "Teacher", "UPSC", "CTET", "Bihar", "Rajasthan", "Army", "12th pass"]
    def hits(term):
        t = term.lower()
        return sum(1 for i in items if t in (i.get("title", "") + " " + i.get("org", "") + " " + " ".join(map(str, i.get("q") or [])) if isinstance(i.get("q"), list) else i.get("title", "") + " " + i.get("org", "") + " " + str(i.get("q") or "")).lower())
    chips = [p for p in POPULAR if hits(p) > 0][:8]
    chip_html = '<span class="lbl" data-t="v3pop">Popular:</span>' + "".join(f'<button type="button" data-q="{o}">{o}</button>' for o in chips)
    top = ('    <section class="v3top" aria-label="Search and today">\n' + search +
           f'      <div class="v3chips" id="v3chips">{chip_html}</div>\n'
           '      <p class="v3fresh" id="v3fresh"></p>\n'
           '      <div class="v3today" id="v3today"></div>\n'
           '    </section>\n')
    s = s.replace("  <main>\n", "  <main>\n" + top, 1)
    s = s.replace("</head>", CSS + f"\n<script>window.SC_V3 = {json.dumps(data, separators=(',', ':'))};</script>\n" + JS + "\n</head>", 1)
    s = s.replace('v3pop', 'v3pop', 1)
    s = s.replace('      newTip:', '      v3pop: "Popular:", newTip:', 1)
    s = re.sub(r'(\n\s+hi: \{\n)', r'\1      v3pop: "लोकप्रिय:",\n', s, count=1)
    # a test page: keep it out of Google, point at the real homepage
    s = re.sub(r'<meta name="robots" content="[^"]*">', "", s)
    s = s.replace("<head>", '<head>\n<meta name="robots" content="noindex, follow">', 1)
    s = re.sub(r'\n<link rel="alternate" hreflang="[^"]*" href="[^"]*">', "", s)
    out = SITE / "v3" / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(s, encoding="utf-8")
    print(f"home v3: /v3/ built ({len(data)} notices, chips: {', '.join(chips)})")


if __name__ == "__main__":
    main()
