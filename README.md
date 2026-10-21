# SarkariChart

Automated, human-approved government job alerts for India.

## Step 1 — Probe official sources (current step)

Checks which official notice boards load from GitHub's servers, and whether
their PDFs are real text or scans.

**Run it:** Actions tab → "Probe official sources" → Run workflow.
The report appears on the run's Summary page; full JSON is in the
`probe-results` artifact.

Run locally: `pip install -r requirements.txt && python scripts/probe.py`

Sources live in `sources/sources.yaml`.

## Roadmap

1. Probe sources ← here
2. Watcher + extraction (SSC, UPSC)
3. Review screen + site on Cloudflare Pages
4. Alerts + email sign-up
5. More sources, group by group
