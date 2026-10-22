# SarkariChart — Handover

Everything needed to continue this project from any Claude account (or by a person).
Last updated: 22 Oct 2026. Owner: the site owner.

**To continue with a new Claude account:** connect your Mac folder `Sarkari Chart` (or give it the GitHub repo),
then say: *"Read docs/HANDOVER.md and docs/PLAN.md in the sarkarichart repo and continue from 'Next steps'."*

---

## 1. What we are building

A calm, fast, trustworthy Indian govt-job alert site — a 10x better SarkariResult.
- **Goal:** go viral; heavy on trust; the site just works; quick and fast; reliable. Avoid over-designed extras.
- **Moat:** clean doc-like "craigslist of govt jobs" UX, speed, no ads for now, Google + AI-search friendly, full Hindi.
- **Money later:** email list (alerts) → affiliate test-prep, coaching leads, direct-sold quiet sponsor slots
  (side margins on desktop; on phones after the 5th row and above the footer; always labelled "Sponsored").
- **Domain:** `sarkarichart.com` is available; buy it at public launch. Until then the site is
  `https://sarkarichart.pages.dev` and stays **noindex**.
- Full research, competitors, revenue model and legal notes: **docs/PLAN.md**.

## 2. Where everything lives (all owned by the owner, none tied to a Claude account)

| Thing | Where |
|---|---|
| Code + data (source of truth) | GitHub `rklokesh/sarkarichart` (private); local copy: Mac `/Volumes/Workspace/App idea/Sarkari Chart/sarkarichart` |
| Live site | Cloudflare Pages project `sarkarichart` → https://sarkarichart.pages.dev |
| Test views | `?preview=returning` (returning-visitor view + ~130 demo rows), `?demo` (demo rows) |
| Secrets (GitHub → Settings → Secrets) | `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, `GEMINI_API_KEY` |
| Personal GitHub token for pushes from the Mac | `Sarkari Chart/.github-token` (outside the repo; never paste it in chat) |
| Logo source files | `Sarkari Chart/sarkarichart-6b-stacked.svg` (current), earlier concepts in the same folder |
| Design preview (old Claude artifact) | copy saved as `docs/design-preview.html` |
| Self-hosted runner script (for India-only sites, later) | `Sarkari Chart/setup-runner.sh` |

## 3. How the system works (all free tiers)

```
official notice boards ──(watch.yml, every 30 min, GitHub Actions)──▶ data/notices/<id>.json + PDF text
        └─ prepare.yml (after each watch): Gemini writes a clean card (EN+HI title, category, dates, summary)
           ├─ junk (refund notes, booklets…) → status "skipped"
           └─ real notices → status "in_review" + a GitHub issue labelled `review`
You: open the issue in the GitHub app → add label `approve` (or `reject`). Fix a field first by commenting
     e.g. `title_en: SSC CGL 2026` or `last_date: 2026-11-30`.
        └─ publish.yml: records decisions (sweeps all labelled issues), rebuilds the homepage list
           (site/index.html between /*ITEMS:START*/ … /*ITEMS:END*/), then calls deploy.yml
deploy.yml: builds notice-page PDFs (cached; only rebuilt when notice pages change) → Cloudflare Pages
```

- Sources: `sources/sources.yaml` — `runner: github` (works from GitHub's US servers, 9 boards) or
  `runner: india` (needs an Indian connection: UPSC, RRB, defence, most states → later via the Mac mini runner).
- AI: Gemini `gemini-flash-lite-latest` via its OpenAI-compatible endpoint, free tier, throttled (7 s gap, retries).
- Scripts: `scripts/watch.py`, `extract.py`, `common.py` (fetch + cert repair), `prepare.py`, `publish.py`, `make_pdfs.mjs`.

## 4. Design rules (agreed — keep them)

- Look: calm, warm, document-like; one sans typeface (Helvetica Neue/system, Noto Sans Devanagari for Hindi);
  ink `#36322D` (warm charcoal, never pure black); greys from the theme; no boxes, no clutter.
- Page width 1000px; header = tagline · logo (stacked mark + "सरकारी चार्ट" in Tiro Devanagari Hindi) · About / हिंदी / light-dark toggle.
- Tabs: All · Jobs · Closing soon (jobs closing ≤ 7 days, soonest first, count always shown) · Admit cards · Results · Answer keys;
  sliding underline; switching tabs never moves the page or the footer.
- Table: Posted (date + fixed slot for a red blinking "New" tag) · Notice (only dark text) · Organisation · Type ·
  Last date (date; orange ≤ 7 days, red ≤ 3 days; quick grey tooltip "N days left"; NIL in light grey when none) · PDF.
  Newest first everywhere. 25 rows, then "Show 25 more". Whole row clickable; big invisible tap areas everywhere.
- "New": newest 3 for first-time visitors (last 24 h); afterwards "new since your last visit" (a visit ends after 30 min away);
  line "N new since your last visit" keeps its space so nothing shifts.
- Search: typewriter hint cycling newest notices ("Search : …"); synonyms + Hindi + typo tolerance; picks the tab
  (matches in one category → that tab, several → All); ↑/↓/Enter; Esc keycap clears; `?q=` shareable.
- Full Hindi mode: not one English word left (except the Esc key).
- Every link to official sites/PDFs opens in a new tab. Our notice page can be downloaded as our own PDF (logo, both languages).
- Speed: hover/touch prefetch of our own pages; no images except tiny SVGs; back-to-top button.
- Rejected ideas (don't redo): Press-K command palette, boxed search, tag frames on tabs, pillars/elephants in margins,
  click sounds, recent-search chips (parked — a reminder exists), bookmark pop-up (parked).

## 5. Next steps (in order)

1. **Approve the 21 waiting review cards** (GitHub app → Issues). First real notices go live. ← we are here
2. **Notice page per approved notice** (template = `site/notice/ugc-net-december-2026/`), so rows open our page
   (key dates, fees, eligibility, official links, our PDF) instead of the raw official PDF.
3. **Trust details:** "Checked on <time>" + official source link on each notice; corrections note.
4. **Mac mini self-hosted runner** (`setup-runner.sh`, label `india`) to cover UPSC, RRB, defence, states.
5. **Daily health message** (what was checked, what failed, what awaits approval).
6. **Launch:** buy sarkarichart.com, connect to Cloudflare Pages, remove noindex, sitemap, JobPosting schema,
   Search Console + Bing, WhatsApp share button.
7. Later: email/WhatsApp alerts + sign-up, Telegram channel, sponsor slots, eligibility profile.

## 6. Working conventions used so far

- Commit as `rklokesh <rklokesh@users.noreply.github.com>`; pushes from the Mac use the token file via an
  `http.extraheader` (never print the token).
- Verify every change in a headless browser (desktop + phone widths, English + Hindi, light + dark) before deploying.
- When copying files to the Mac, check a sha256 — one truncated upload once broke the live page.
- The preview (old Claude artifact) and live site were kept identical except for preview-only demo rows.
