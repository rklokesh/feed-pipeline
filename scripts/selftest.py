"""Safety check: runs the whole publishing chain on a throwaway copy of the site and fails loudly if any step breaks.

Run before every push (Push SarkariChart.command does it) and by .github/workflows/check.yml after every push.
Nothing here touches the real site, posts anywhere or calls an AI; it only proves the scripts still run end to end.
  python3 scripts/selftest.py        -> exit 0 = safe to publish, exit 1 = something is broken (the reason is printed)
"""
from __future__ import annotations

import pathlib
import py_compile
import shutil
import subprocess
import sys
import tempfile

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
STEPS = ["dedupe.py", "retype.py", "pages.py", "exams.py build", "publish.py build", "hubs.py build", "seo_pages.py",
         "home_v3.py", "hindi_pages.py", "report_page.py", "info_pages.py", "seo_files.py"]
MUST_EXIST = ["site/index.html", "site/hi/index.html", "site/sitemap.xml", "site/_redirects", "site/exam/index.html"]


def fail(msg: str) -> None:
    print(f"\nSAFETY CHECK FAILED: {msg}\nNothing was published. Ask Claude to fix it.")
    sys.exit(1)


def main() -> None:
    for f in sorted((ROOT / "scripts").glob("*.py")):          # 1. every script still parses
        try:
            py_compile.compile(str(f), doraise=True)
        except py_compile.PyCompileError as e:
            fail(f"{f.name} has a syntax error: {e.msg.strip()[:300]}")
    for f in sorted((ROOT / ".github/workflows").glob("*.yml")):  # 2. every workflow file is valid
        try:
            yaml.safe_load(f.read_text())
        except yaml.YAMLError as e:
            fail(f"{f.name} is not valid YAML: {str(e)[:300]}")
    for f in ["sources/sources.yaml", "data/exam_profiles.json"]:
        p = ROOT / f
        if p.exists():
            try:
                yaml.safe_load(p.read_text())
            except yaml.YAMLError as e:
                fail(f"{f} is broken: {str(e)[:300]}")
    with tempfile.TemporaryDirectory(prefix="sc-selftest-") as tmp:   # 3. the publishing chain runs end to end
        work = pathlib.Path(tmp) / "repo"
        shutil.copytree(ROOT, work, ignore=shutil.ignore_patterns(".git", "*.pdf", "og*.png", "__pycache__", "node_modules"))
        for step in STEPS:
            cmd = [sys.executable, f"scripts/{step.split()[0]}"] + step.split()[1:]
            try:
                r = subprocess.run(cmd, cwd=work, capture_output=True, text=True, timeout=600,
                                   env={"PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": tmp, "SELFTEST": "1"})
            except subprocess.TimeoutExpired:
                fail(f"step '{step}' took longer than 10 minutes")
            if r.returncode != 0:
                tail = "\n".join((r.stderr or r.stdout).strip().splitlines()[-12:])
                fail(f"step '{step}' crashed:\n{tail}")
            print(f"ok  {step}")
        for f in MUST_EXIST:
            p = work / f
            if not p.exists() or p.stat().st_size < 200:
                fail(f"{f} is missing or empty after the build")
        rd = (work / "site/_redirects").read_text()
        if rd.count("# --- merged notices") != rd.count("# --- end merged notices ---"):
            fail("site/_redirects lost a section marker")
        wild = sum(1 for l in rd.splitlines() if l and not l.startswith("#") and "*" in l.split()[0])
        if wild > 90:
            fail(f"site/_redirects has {wild} wildcard rules; Cloudflare ignores everything past 100")
    print("\nSAFETY CHECK PASSED: safe to publish.")


if __name__ == "__main__":
    main()
