"""The homepage top (since 11 Nov 2026): the compact header, the search box, then the tabs and list.

Instead of the big hero: the compact header, the search box, then the same tabs and list straight away.
(A "Today" strip and popular-search chips were tried on 10 Nov and cut on 11 Nov as noise.)
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
/* Linear-style search: one hairline under the field, no box, small crisp icons, no shadow */
.v3top .search input { height: 48px; box-sizing: border-box; font-size: .9375rem !important; letter-spacing: -.005em;
  background: transparent !important; border: 0 !important; border-bottom: 1px solid color-mix(in srgb, var(--ink) 12%, transparent) !important;
  border-radius: 0 !important; padding: 0 84px 0 26px !important; box-shadow: none !important; transition: border-color .15s ease; }
.v3top .search input:hover { border-bottom-color: color-mix(in srgb, var(--ink) 22%, transparent) !important; }
.v3top .search input:focus { background: transparent !important; border-bottom-color: color-mix(in srgb, var(--ink) 55%, transparent) !important; box-shadow: none !important; }
.v3top .search .ph { color: color-mix(in srgb, var(--ink) 42%, transparent) !important; font-size: .9375rem !important; }
/* the Esc key hint is for keyboards only */
@media (max-width: 640px), (hover: none) { .v3top .search .sx .kc { display: none !important; } }
.v3top .search .sicon { left: 0 !important; width: 15px !important; height: 15px !important; stroke-width: 2 !important; color: color-mix(in srgb, var(--ink) 55%, transparent); }
.v3top .search .ph { left: 26px !important; right: 84px !important; }
/* filter: a small round button with a hairline ring, 16px icon (like Linear's view controls) */
.v3top .search .sf { right: 0 !important; width: 30px !important; height: 30px !important; border-radius: 50% !important;
  border: 1px solid color-mix(in srgb, var(--ink) 12%, transparent) !important; background: var(--page) !important; box-sizing: border-box; }
.v3top .search .sf svg { width: 16px !important; height: 16px !important; }
.v3top .search .sf svg path, .v3top .search .sf svg circle, .v3top .search .sf svg line { stroke-width: 1.75; }
.v3top .search .sx { right: 40px !important; font-size: .875rem; }
.v3top .search .sf .fn:not(:empty) { top: -5px !important; right: -5px !important; }
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


BG_CSS = '''
/* faint board names behind the header and search (not behind the list); a few light up now and then */
.sheet { position: relative; isolation: isolate; }
body { overflow-x: clip; }
.v3bg { position: absolute; z-index: -1; top: 0; left: 50%; width: 100vw; height: 300px; transform: translateX(-50%); overflow: hidden; contain: strict;
  pointer-events: none; user-select: none; -webkit-user-select: none; padding: 6px 10px; box-sizing: border-box; text-align: left;
  font: 12px/24px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; letter-spacing: .02em; word-spacing: 16px;
  /* clear around the logo and search in the middle, fading out at the bottom and the sides */
  -webkit-mask-image: radial-gradient(ellipse 34% 46% at 50% 46%, transparent 0, transparent 55%, #000 100%), linear-gradient(to bottom, #000 0, #000 62%, transparent 100%), linear-gradient(to right, transparent 0, #000 8%, #000 92%, transparent 100%);
  -webkit-mask-composite: source-in, source-in;
  mask-image: radial-gradient(ellipse 34% 46% at 50% 46%, transparent 0, transparent 55%, #000 100%), linear-gradient(to bottom, #000 0, #000 62%, transparent 100%), linear-gradient(to right, transparent 0, #000 8%, #000 92%, transparent 100%);
  mask-composite: intersect, intersect; }
/* the header words and tabs keep a soft page-coloured halo so they always read clearly over the names */
.top .g, .top .nav-r a, .top .nav-r button, .tabs button { text-shadow: 0 0 2px var(--page), 0 0 6px var(--page), 0 0 10px var(--page); }
.v3bg span { color: color-mix(in srgb, var(--grey) 22%, transparent); transition: color 1.1s ease, opacity 1.1s ease; }
.v3bg span.on { color: color-mix(in srgb, #E8312F 70%, transparent); transition-duration: .2s; }
.v3bg span.dim { opacity: .25; transition-duration: .35s; }
@media (max-width: 640px) { .v3bg { font-size: 10px; line-height: 22px; word-spacing: 12px; -webkit-mask-image: linear-gradient(to bottom, #000 0, #000 60%, transparent 100%); mask-image: linear-gradient(to bottom, #000 0, #000 60%, transparent 100%); } .v3bg span { color: color-mix(in srgb, var(--grey) 20%, transparent); } }
'''
BG_JS = '''<script>
/* board-name background: sized to the header + search (+ a little of the tab row), a couple of names flicker at a time;
   paused when off screen or in a background tab; still for reduced motion */
addEventListener("DOMContentLoaded", function () {
  var bg = document.querySelector(".v3bg"), sheet = document.querySelector(".sheet"), tr = document.querySelector(".tabrow");
  if (!bg || !sheet || !tr) return;
  function size() { bg.style.height = Math.round(tr.getBoundingClientRect().top - sheet.getBoundingClientRect().top + 44) + "px"; }
  size(); addEventListener("resize", size);
  var B = bg.clientHeight + 24; [].slice.call(bg.children).forEach(function (s) { if (s.offsetTop > B) s.remove(); });
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  var ws = bg.children, vis = true, phone = matchMedia("(max-width: 640px)").matches;
  if ("IntersectionObserver" in window) new IntersectionObserver(function (e) { vis = e[0].isIntersecting; }).observe(bg);
  setInterval(function () {
    if (!vis || document.hidden || !ws.length) return;
    var n = phone ? 1 : 1 + (Math.random() < .5);
    for (var k = 0; k < n; k++) {
      var w = ws[Math.random() * ws.length | 0], c = Math.random() < .7 ? "on" : "dim";
      w.classList.add(c);
      (function (w, c) { setTimeout(function () { w.classList.remove(c); }, 300 + Math.random() * 1000); })(w, c);
    }
  }, phone ? 420 : 260);
});
</script>'''


def main() -> None:
    s = (SITE / "index.html").read_text(encoding="utf-8")
    # rebuildable: undo an earlier run first
    s = re.sub(r'<!--V3:START-->.*?<!--V3:END-->\n?', "", s, flags=re.S)
    prev = re.search(r'    <section class="v3top".*?</section>\n', s, flags=re.S)
    search = ""
    if prev:
        m0 = re.search(r'  <label class="search" for="q">.*?</label>\n', prev.group(0), flags=re.S)
        search = m0.group(0) if m0 else ""
        s = s.replace(prev.group(0), "", 1)
    # take the hero out (hubs.py still builds it; the homepage no longer shows it)
    old = re.search(r'    <section class="hero".*?</section>\n', s, flags=re.S)
    if old:
        lab = re.search(r'      <label class="search" for="q">.*?</label>\n', old.group(0), flags=re.S)
        if lab:
            search = "\n".join(("  " + x[6:] if x.startswith("      ") else x) for x in lab.group(0).split("\n"))
        s = s.replace(old.group(0), "", 1)
    s = re.sub(r'<!--HERO:START-->.*?<!--HERO:END-->\n?', "", s, flags=re.S)
    m = re.search(r'    <label class="search" for="q">.*?</label>\n', s, flags=re.S)
    if m:   # a homepage that never had the hero keeps its search line here
        search = m.group(0); s = s.replace(search, "", 1)
    if not search:
        raise SystemExit("home: search box not found")
    # one main heading for Google and screen readers (not shown: the list is the page)
    h1 = ('      <h1 class="vh"><span class="x-en">Sarkari Naukri 2026: latest govt jobs, admit cards and results</span>'
          '<span class="x-hi" lang="hi">सरकारी नौकरी 2026: नई भर्तियाँ, एडमिट कार्ड और रिज़ल्ट</span></h1>\n')
    top = '    <section class="v3top" aria-label="Search">\n' + h1 + search + '    </section>\n'
    s = s.replace("  <main>\n", "  <main>\n" + top, 1)
    css = CSS.replace("<style>", "<style>\n.vh { position: absolute !important; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; margin: 0; }", 1)
    BOARD_NAMES = False   # 11 Nov: the board-name background was tried again and judged distracting
    if BOARD_NAMES:
        css = css.replace("</style>", BG_CSS + "</style>", 1) + BG_JS
    # the board names (fixed order, so the page does not change between builds)
    import random
    boards = ("SSC UPSC RRB IBPS SBI UPPSC BPSC RPSC MPPSC HPSC UKPSC JPSC CGPSC WBPSC PSSSB HSSC UPSSSC BSSC RSSB DSSSB NTA CTET "
              "KVS NVS BSF CRPF CISF ITBP AIIMS ESIC ISRO NIA RRC LIC NABARD RBI JKSSB UKSSSC BPSSC JSSC UPESSC Railway Police "
              "Teacher Clerk Constable Patwari Lekhpal Bank PO SI ASI Driver Nurse Anganwadi Steno Typist JE GD CHSL CGL MTS NTPC Group-D").split()
    rnd = random.Random(7)
    words = " ".join(f"<span>{rnd.choice(boards)}</span>" for _ in range(460))
    s = re.sub(r'  <div class="v3bg" aria-hidden="true">.*?</div>\n', "", s, flags=re.S)
    if BOARD_NAMES:
        s = s.replace('<div class="sheet">\n', '<div class="sheet">\n  <div class="v3bg" aria-hidden="true">' + words + '</div>\n', 1)
    s = s.replace("</head>", "<!--V3:START-->" + css + "<!--V3:END-->\n</head>", 1)
    (SITE / "index.html").write_text(s, encoding="utf-8")
    print("home: simple top (search, then the list)")


if __name__ == "__main__":
    main()
