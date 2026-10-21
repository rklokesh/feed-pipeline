"""Turn a notice PDF into structured fields.

Order: PDF text (pdfplumber) -> OCR for scans (tesseract, Hindi+English)
-> rule-based field extraction -> free AI fallback only for what's missing.
Every field records where it came from ("rule" or "ai") and the snippet it
was read from, so the reviewer can check it against the PDF in seconds.
"""
from __future__ import annotations

import io
import json
import os
import re
import shutil
import subprocess
import tempfile
from datetime import date

import requests

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}

# ---------- text ----------

def pdf_text(data: bytes, max_pages: int = 8) -> tuple[str, str, int]:
    """Return (text, kind, pages). kind = text | ocr | scanned | failed."""
    import pdfplumber

    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            pages = len(pdf.pages)
            text = "\n".join((p.extract_text() or "") for p in pdf.pages[:max_pages])
    except Exception:  # noqa: BLE001
        return "", "failed", 0
    if len(text.strip()) >= 200:
        return text, "text", pages
    ocr = ocr_pdf(data, pages=2)
    return (ocr, "ocr", pages) if len(ocr.strip()) >= 200 else (text, "scanned", pages)


def ocr_pdf(data: bytes, pages: int = 2) -> str:
    if not (shutil.which("pdftoppm") and shutil.which("tesseract")):
        return ""
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "in.pdf")
        open(src, "wb").write(data)
        subprocess.run(["pdftoppm", "-r", "200", "-l", str(pages), "-png", src, os.path.join(d, "p")],
                       check=False, capture_output=True, timeout=120)
        out = []
        for img in sorted(f for f in os.listdir(d) if f.endswith(".png")):
            r = subprocess.run(["tesseract", os.path.join(d, img), "-", "-l", "eng+hin"],
                               capture_output=True, text=True, timeout=120)
            out.append(r.stdout)
        return "\n".join(out)


# ---------- dates ----------

_DATE_RX = [
    re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{4})\b"),
    re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?[\s.-]*([A-Za-z]{3,9})[,.\s-]*(\d{4})\b"),
    re.compile(r"\b([A-Za-z]{3,9})\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b"),
]


def parse_dates(s: str) -> list[str]:
    found = []
    for rx_i, rx in enumerate(_DATE_RX):
        for m in rx.finditer(s):
            try:
                if rx_i == 0:
                    d, mo, y = int(m[1]), int(m[2]), int(m[3])
                elif rx_i == 1:
                    d, mo, y = int(m[1]), MONTHS[m[2][:3].lower()], int(m[3])
                else:
                    mo, d, y = MONTHS[m[1][:3].lower()], int(m[2]), int(m[3])
                found.append((m.start(), date(y, mo, d).isoformat()))
            except (KeyError, ValueError):
                continue
    return [iso for _, iso in sorted(found)]


DATE_LABELS = {
    "apply_start": r"(?:opening|start(?:ing)?|commencement)\s+(?:date\s+)?(?:of|for)?\s*(?:online\s+)?(?:application|registration|submission)",
    "apply_last": r"(?:last|closing|end)\s+date\s+(?:of|for)?\s*(?:online\s+)?(?:application|registration|submission|receipt|apply)?|last\s+date",
    "fee_last": r"last\s+date\s+(?:of|for)\s+(?:online\s+)?(?:fee|payment)",
    "exam_date": r"(?:date\s+of\s+(?:the\s+)?(?:examination|exam|cbt|test))|(?:exam(?:ination)?\s+date)",
    "admit_card": r"admit\s+card|e-?admit|call\s+letter",
}


def _snip(text: str, i: int, j: int) -> str:
    return re.sub(r"\s+", " ", text[max(0, i - 60): j + 80]).strip()


def rule_extract(text: str) -> dict:
    f: dict[str, dict] = {}
    low = text.lower()

    for key, pat in DATE_LABELS.items():
        m = re.search(pat, low)
        if m:
            window = text[m.end(): m.end() + 160]
            ds = parse_dates(window)
            if ds:
                f[key] = {"value": ds[0], "source": "rule", "evidence": _snip(text, m.start(), m.end() + 60)}

    m = re.search(r"(?:advt\.?|advertisement|notification)\s*(?:no\.?|number)\s*[:.\-]?\s*([A-Z0-9][A-Z0-9/().\-\s]{2,40})", text, re.I)
    if m:
        f["advt_no"] = {"value": m[1].strip(" .-"), "source": "rule", "evidence": _snip(text, m.start(), m.end())}

    m = re.search(r"(\d{1,3}(?:,\d{3})+|\d{1,6})\s*(?:\(.*?\)\s*)?(?:posts|vacancies|vacancy)\b", text, re.I)
    if m:
        f["total_vacancies"] = {"value": int(m[1].replace(",", "")), "source": "rule", "evidence": _snip(text, m.start(), m.end())}

    m = re.search(r"(\d{2})\s*(?:years?)?\s*(?:to|-|–)\s*(\d{2})\s*years", text, re.I)
    if m and 14 <= int(m[1]) < int(m[2]) <= 65:
        f["age_limit"] = {"value": {"min": int(m[1]), "max": int(m[2])}, "source": "rule", "evidence": _snip(text, m.start(), m.end())}

    fee_ctx = re.search(r"(?:application\s+)?fee", low)
    if fee_ctx:
        window = text[fee_ctx.start(): fee_ctx.start() + 400]
        amts = re.findall(r"(?:rs\.?|₹|inr)\s*([0-9][0-9,]{0,6})", window, re.I)
        if amts:
            f["fee_amounts"] = {"value": sorted({int(a.replace(",", "")) for a in amts}), "source": "rule",
                                "evidence": _snip(text, fee_ctx.start(), fee_ctx.start() + 200)}

    m = re.search(r"https?://[^\s)>\]]+", text)
    if m:
        f["apply_or_official_url"] = {"value": m[0].rstrip(".,;"), "source": "rule", "evidence": _snip(text, m.start(), m.end())}
    return f


KEY_FIELDS = ["apply_last", "total_vacancies", "age_limit", "fee_amounts", "apply_start"]


# ---------- AI fallback (free tiers) ----------

AI_PROMPT = """You extract facts from an official Indian government recruitment notice.
Return ONLY JSON with these keys (use null when the notice does not state it; never guess):
post_names (list of strings), total_vacancies (int), apply_start (YYYY-MM-DD), apply_last (YYYY-MM-DD),
fee_last (YYYY-MM-DD), exam_date (YYYY-MM-DD or text), age_limit ({"min":int,"max":int,"as_on":"YYYY-MM-DD"}),
fee ({"general":int,"obc":int,"sc_st":int,"female":int,"pwd":int} in rupees), qualification (short text),
apply_url (string), advt_no (string).
For each non-null key also give an "evidence" object mapping the key to the exact short quote you read it from."""


def _providers() -> list[dict]:
    out = []
    if os.environ.get("GITHUB_TOKEN") and os.environ.get("AI_DISABLE_GITHUB") != "1":
        out.append({"name": "github-models", "url": "https://models.github.ai/inference/chat/completions",
                    "key": os.environ["GITHUB_TOKEN"], "model": os.environ.get("GITHUB_MODEL", "openai/gpt-4o-mini")})
    if os.environ.get("GEMINI_API_KEY"):
        out.append({"name": "gemini", "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                    "key": os.environ["GEMINI_API_KEY"], "model": os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")})
    return out


def ai_extract(text: str) -> tuple[dict, str]:
    """Try each free provider in turn; returns (fields, provider) or ({}, reason)."""
    reasons = []
    for p in _providers():
        try:
            r = requests.post(p["url"], timeout=90, headers={"Authorization": f"Bearer {p['key']}"}, json={
                "model": p["model"], "temperature": 0, "response_format": {"type": "json_object"},
                "messages": [{"role": "system", "content": AI_PROMPT},
                             {"role": "user", "content": text[:14000]}]})
            if r.status_code != 200:
                reasons.append(f"{p['name']}:{r.status_code}")
                continue
            data = json.loads(r.json()["choices"][0]["message"]["content"])
            ev = data.pop("evidence", {}) or {}
            fields = {k: {"value": v, "source": "ai", "provider": p["name"], "evidence": ev.get(k, "")}
                      for k, v in data.items() if v not in (None, "", [], {})}
            return fields, p["name"]
        except Exception as e:  # noqa: BLE001
            reasons.append(f"{p['name']}:{type(e).__name__}")
    return {}, ",".join(reasons) or "no-provider"


def extract(text: str, kind: str, allow_ai: bool) -> tuple[dict, dict]:
    fields = rule_extract(text)
    meta = {"ai": None}
    if kind == "notification" and allow_ai and any(k not in fields for k in KEY_FIELDS) and text.strip():
        ai_fields, who = ai_extract(text)
        meta["ai"] = who
        for k, v in ai_fields.items():
            if k not in fields:
                fields[k] = v
            elif k in ("apply_last", "apply_start") and fields[k]["value"] != v["value"]:
                fields[k]["conflict"] = v  # rule and AI disagree: reviewer must look
    return fields, meta


# ---------- classification ----------

KIND_RULES = [
    ("noise", r"tender|\brti\b|auction|quotation|e-?procurement|empanelment|annual\s+report"),
    ("answer_key", r"answer\s*key|उत्तर\s*कुंजी|provisional\s+key|final\s+key"),
    ("admit_card", r"admit\s*card|e-?admit|call\s*letter|प्रवेश\s*पत्र|hall\s*ticket"),
    ("result", r"\bresult|merit\s+list|select(?:ed|ion)\s+list|परिणाम|final\s+list|marks"),
    ("syllabus", r"syllabus|scheme\s+of\s+exam|पाठ्यक्रम"),
    ("update", r"corrigendum|addendum|extension|extended|revised|modification|शुद्धि"),
    ("notification", r"recruit|vacanc|advertisement|advt|notification|notice\s+of\s+exam|online\s+application|भर्ती|विज्ञापन|apply"),
]


def classify(title: str) -> str:
    t = title.lower()
    for kind, rx in KIND_RULES:
        if re.search(rx, t):
            return kind
    return "other"
