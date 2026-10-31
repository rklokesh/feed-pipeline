"""Re-read notices whose PDF text came out as gibberish (Hindi PDFs in old non-Unicode fonts, e.g. many MPPSC, UKPSC, RPSC
notices). Downloads the PDF again, reads it with OCR (Hindi + English), saves the text and asks for the page to be written
again on the next pages.py run. Notices that were skipped only because the text was unreadable get a fresh AI card.

  python scripts/reextract.py            # all garbled notices (at most 25 per run)
  python scripts/reextract.py <id> ...   # just these
Writes a short report to reports/reextract.txt.
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import download  # noqa: E402
from extract import looks_garbled, ocr_pdf  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
NOTICES = ROOT / "data" / "notices"
TEXT = ROOT / "data" / "text"


def main():
    langs = ""
    if shutil.which("tesseract"):
        langs = subprocess.run(["tesseract", "--list-langs"], capture_output=True, text=True).stdout
    report = [f"tesseract: {shutil.which('tesseract')}, hindi: {'hin' in langs.split()}"]
    if "hin" not in langs.split():
        report.append("Hindi OCR not installed on this runner: nothing done")
        (ROOT / "reports" / "reextract.txt").write_text("\n".join(report) + "\n")
        print("\n".join(report))
        return
    ids = set(sys.argv[1:])
    done = 0
    for f in sorted(NOTICES.glob("*.json")):
        n = json.loads(f.read_text())
        t = TEXT / f"{n['id']}.txt"
        if ids and n["id"] not in ids:
            continue
        if not ids and not (t.exists() and looks_garbled(t.read_text(errors="ignore"))):
            continue
        if n.get("status") not in ("approved", "skipped") or not str(n.get("url", "")).lower().split("?")[0].endswith(".pdf"):
            continue
        try:
            data = download(n["url"], referer=n.get("board_url") or "")
        except Exception as e:  # noqa: BLE001
            report.append(f"{n['id']} {n.get('org')}: download failed ({type(e).__name__})")
            continue
        text = ocr_pdf(data, pages=4)
        if len(text.strip()) < 200 or looks_garbled(text):
            report.append(f"{n['id']} {n.get('org')}: OCR gave too little text")
            continue
        t.write_text(text)
        n.setdefault("pdf", {})["text_kind"] = "ocr-legacy-font"
        if n.get("status") == "approved":
            n["rewrite"] = True                   # pages.py writes the page again from the readable text
        else:                                     # skipped only because it was unreadable: let the AI look again
            n["status"], n["card"] = "pending_review", None
        f.write_text(json.dumps(n, ensure_ascii=False, indent=2, sort_keys=True))
        report.append(f"{n['id']} {n.get('org')}: re-read ({len(text)} chars), {'page will be rewritten' if n.get('rewrite') else 'sent back for a new card'}")
        done += 1
        if done >= 25:
            break
    report.append(f"done: {done}")
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / "reextract.txt").write_text("\n".join(report) + "\n")
    print("\n".join(report))


if __name__ == "__main__":
    main()
