# SarkariChart

Automated, human-approved government job alerts for India.

## Step 2 — Watcher + extraction (current step)

`Watch official sources` runs every 30 minutes: it checks each official board,
finds new notice links, downloads the PDF, extracts key fields (rule-based,
then OCR for scans, then a free AI fallback) and lists them in
`data/review-queue.md` for approval. First run on a source only samples its
5 newest links and marks the rest as already seen.

## Step 1 — Probe official sources (done)

Checks which official notice boards load from GitHub's servers, and whether
their PDFs are real text or scans.

**Run it:** Actions tab → "Probe official sources" → Run workflow.
The report appears on the run's Summary page; full JSON is in the
`probe-results` artifact.

Run locally: `pip install -r requirements.txt && python scripts/probe.py`

Sources live in `sources/sources.yaml`.

## Roadmap

1. Probe sources (done: 7/32 reachable from GitHub)
2. Watcher + extraction ← here
3. Review screen + site on Cloudflare Pages
4. Alerts + email sign-up
5. More sources, group by group
