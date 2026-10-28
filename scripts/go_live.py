"""Domain day, in one command: python3 scripts/go_live.py https://sarkarichart.com

1. Replaces https://sarkarichart.pages.dev with the new address in scripts, templates and site pages.
2. Removes the pre-launch noindex (HTML meta tags and the X-Robots-Tag header) and opens robots.txt.
3. Rebuilds pages, trust pages and search files so every link, canonical tag and schema uses the new address.
Then commit + push; after the deploy, add the domain in Google Search Console and Bing Webmaster Tools and submit
<domain>/sitemap.xml. Safe to run twice.
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OLD = "https://sarkarichart.pages.dev"


def main():
    if len(sys.argv) != 2 or not re.fullmatch(r"https://[a-z0-9.-]+", sys.argv[1]):
        sys.exit("usage: python3 scripts/go_live.py https://sarkarichart.com")
    new = sys.argv[1].rstrip("/")
    files = [*ROOT.glob("scripts/*.py"), *ROOT.glob("scripts/*.mjs"), *ROOT.glob("templates/*.html"),
             *ROOT.glob("site/*.html"), *ROOT.glob("site/*/index.html"), *ROOT.glob("site/*/*/index.html"), *ROOT.glob("functions/**/*.js")]
    changed = 0
    for f in files:
        if f.name == "go_live.py":
            continue
        s = f.read_text(encoding="utf-8")
        t = s.replace(OLD, new).replace('<meta name="robots" content="noindex, nofollow">\n', "")
        if f.name == "seo_files.py":
            t = t.replace("LAUNCHED = False", "LAUNCHED = True")
        if t != s:
            f.write_text(t, encoding="utf-8")
            changed += 1
    h = ROOT / "site" / "_headers"
    s = h.read_text(encoding="utf-8")
    h.write_text(s.replace("  X-Robots-Tag: noindex, nofollow\n", ""), encoding="utf-8")
    print(f"address switched in {changed} files; noindex removed")
    env = {"SITE_URL": new, "PAGE_BACKFILL": "0", "GEMINI_API_KEY": "", "GITHUB_TOKEN": "", "PATH": "/usr/bin:/bin:/usr/local/bin"}
    for cmd in (["scripts/pages.py"], ["scripts/exams.py", "build"], ["scripts/hubs.py", "build"], ["scripts/publish.py", "build"], ["scripts/report_page.py"], ["scripts/info_pages.py"], ["scripts/seo_files.py"]):
        subprocess.run([sys.executable, *cmd], cwd=ROOT, env=env, check=True)
    print("rebuilt. Now: git add -A site scripts templates functions && commit && push; then Search Console + Bing.")


if __name__ == "__main__":
    main()
