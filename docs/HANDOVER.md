# SarkariChart — Handover

Everything needed to continue this project from any Claude account (or by a person).
Last updated: 23 Oct 2026 (early morning IST). Owner: the site owner.

**To continue with a new Claude account:** in the Claude desktop app, connect the Mac folder
`/Volumes/Workspace/App idea/Sarkari Chart` (it holds the repo, this file and the GitHub token file), then say:
*"Read HANDOVER.md in the Sarkari Chart folder and docs/PLAN.md in the repo, and continue from 'Where we are / next steps'."*
The repo is the source of truth; nothing important lives only inside a Claude account.

---

## 1. What we are building

A calm, fast, trustworthy Indian govt-job alert site — a 10x better SarkariResult.
- **Goal (owner's words):** go viral; heavy on trust; the site just works; quick and fast; reliable. Avoid over-done features.
- **Moat:** clean doc-like UX, speed, no ads for now, Google + AI-search friendly, full Hindi.
- **Money later:** email list → affiliate test-prep, coaching leads, quiet sponsor slots (always labelled "Sponsored").
- **Domain:** `sarkarichart.com` (available; buy at public launch). Until then: `https://sarkarichart.pages.dev`, **noindex**.
- **Lead list:** WhatsApp Channel https://whatsapp.com/channel/0029Vb9M2x930LKIvmiBrY2s (in the top strip).
  Later Telegram (fully automatable), then email sign-up (the list we own; Cloudflare D1).
  WhatsApp Channel posting cannot be automated officially (unofficial APIs risk a ban) → plan: ready-to-paste posts.
- Full research, competitors, revenue model, legal notes: **docs/PLAN.md**.

## 2. Where everything lives (all owned by the owner)

| Thing | Where |
|---|---|
| Code + data | GitHub `rklokesh/sarkarichart` (private); Mac copy: `/Volumes/Workspace/App idea/Sarkari Chart/sarkarichart` |
| Live site | Cloudflare Pages project `sarkarichart` → https://sarkarichart.pages.dev |
| Test views | `?preview=returning` (returning-visitor view + demo rows), `?demo` (demo rows) |
| GitHub secrets | `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, `GEMINI_API_KEY` |
| Personal GitHub token (pushes + API from the Mac) | `Sarkari Chart/.github-token` — outside the repo, never paste/print it. Has Contents, Actions, Administration (R/W). Cannot read Issues. |
| Self-hosted runner | Mac mini, runner name `mac-mini-india`, labels `self-hosted, india`; installed by `Sarkari Chart/setup-runner.sh`; runs as a LaunchAgent (starts when the owner is logged in) |
| Logo source | `Sarkari Chart/sarkarichart-6b-stacked.svg` |
| Issues = record of every notice | GitHub → Issues (labels `auto-published`, `review`, `approve`, `reject`) |
| Plan / research doc | https://claude.ai/artifact/REDXLjETKWT4p4gK773PPJ (old account) — copy in `docs/PLAN.md` |

## 3. How the system works (free tiers + the Mac mini)

```
watch.yml        (GitHub, hourly)  → 9 boards reachable from US servers      ┐ data/notices/<id>.json
watch-india.yml  (Mac mini, hourly at :45) → 22 India-only boards           ┘ + data/text/<id>.txt
   └─ prepare.yml (after either watch): Gemini writes a card (EN+HI title, type, dates, summary, list/skip)
        ├─ junk → "skipped"
        ├─ AI confidence "low" → GitHub issue labelled `review` (waits for the owner)
        └─ everything else → AUTO-PUBLISHED: status "approved", closed issue labelled `auto-published`,
           pages.py writes /notice/<slug>/ (AI reads PDF + issue comments), publish.py build updates the homepage,
           then deploy.yml (PDF copies of notice pages → Cloudflare Pages)
publish.yml (when the owner adds a label to an issue, open or closed):
   `reject`  → taken down (removed from the list, its page deleted)
   `approve` → after a plain-words comment ("last date is 30 Nov"): page re-written with the fix, keeps its place
```
- Sources: `sources/sources.yaml` (`runner: github` or `runner: india`; `render: static` or `js`).
- AI: Gemini `gemini-flash-lite-latest` via OpenAI-compatible endpoint, free tier, throttled with retries.
- Scripts: `watch.py`, `extract.py`, `common.py` (fetch; certificate-chain repair; legacy-TLS fallback for old govt
  servers — certificates still verified; browser User-Agent retry on 403), `prepare.py`, `pages.py`, `publish.py`,
  `make_pdfs.mjs`, `probe_links.py` (+ `probe-india.yml`: dumps every link on given board pages into `reports/links/`).
- "Posted" date = the official notice date read from the PDF (`notice_date`), never our publish date.
- Deploy: PDF-printer steps have timeouts + continue-on-error, so a stuck apt mirror never blocks the site.

## 3b. Added on 22–23 Oct (late)

- **View counter:** `functions/api/views.js` (Cloudflare Pages Function) + free D1 database `sarkarichart-views`
  (binding `DB`, id in `wrangler.toml`). One view per visitor per day; shown on notice pages only from 100 views.
- **Report a mistake:** `/report/` page (built by `scripts/report_page.py` from the notice template) →
  `functions/api/report.js` opens a GitHub issue labelled `user-report` (screenshot stored in D1, served by
  `/api/report-img`; 5 reports/hour/visitor; honeypot). Needs Cloudflare Pages secret `GH_TOKEN` — set from GitHub
  secret `REPORT_GH_TOKEN` (fine-grained, Issues R/W on this repo only) by re-running workflow `setup-views.yml`.
- **Daily health report:** `scripts/health.py` + `health.yml` (08:01 IST) → comment on the open issue labelled `health`.
- Labels on non-notice issues (health, user-report) never publish anything (publish.py only acts on issues with a notice-id).
- `probe-india.yml` + `scripts/probe_links.py`: dump all links of given board pages from the Mac → `reports/links/`.
- RRB: `follow:` mode in `watch.py` (opens each CEN page inside one browser session; reads `/-/image/...pdf` links)
  and `download: browser`. Debug trace in `data/debug-rrb-unified.txt`.
- New boards: UP Police, CSBC Bihar, RRC NR/WR/CR, CTET, KVS, UKPSC recruitment + results pages.
  Not yet: India Post GDS (timeout), SSB (DNS gone), NVS, CISF, Assam Rifles, Army, Coast Guard, Employment News, CRPF, DRDO.
- UI since: red arrow "New" image (`new-en.png`/`new-hi.png`, nudge) — the green GIF was rejected; siren in the New slot
  for jobs closing ≤7 days and beside "N days left" on notice pages; Esc anywhere clears search; centred tabs;
  every list column one line with "…" + tooltip (tooltip detects sub-pixel cut-offs); notice pages: "← All notices"
  top-left (replaces tagline), breadcrumb "Jobs / Board", centred 760px column, key details/links as square bordered
  tables with homepage hover colour, icons on Share/PDF/Report. Ticket design was tried and rejected.

## 4. Board status (22 Oct 2026, India runner)

- Working: UPSC (both pages), NABARD, Navy, BSF, ITBP, RPSC, RSSB, MPPSC, DSSSB, UPSSSC (+ the 9 GitHub boards:
  SSC, IBPS, NTA, SBI, LIC, ISRO, UPPSC, BPSC, BSSC).
- Reached but 0 notices found — need per-board tuning (links point to pages, not PDFs, or JS menus):
  RRB unified, Army, Coast Guard, UKPSC, Employment News, RBI. **← in progress** (probe-india run dispatched;
  read `reports/links/*.txt` after `git pull`, then adjust each source in sources.yaml / watch.py).
- Failing: RRB Chandigarh (certificate doesn't match its hostname — don't bypass), MP ESB (certificate chain),
  CRPF (tried rectt.crpf.gov.in: no DNS), DRDO (tried rac.gov.in: timeout), IAF Agniveer (site was down, 503).

## 5. Design rules (agreed — keep them)

- Calm, warm, document-like; ink `#36322D` (never pure black); Helvetica Neue/system + Noto Sans Devanagari;
  logo = stacked 8-petal mark + "सरकारी चार्ट" (Tiro Devanagari Hindi). Page width 1000px.
- Favicon: mark only; follows the site theme (toggle or system): charcoal in light, white in dark
  (`favicon-light.svg`, `favicon-dark.svg`, `favicon.png`, `favicon-white.png`, swapped by a small head script).
- Tabs: All · Jobs · Closing soon (with a flashing red siren image `siren.webp`, ~1 flash/sec; still image for
  reduced motion) · Admit cards · Results · Answer keys. Switching tabs never moves the page or footer.
- Table: Posted (date + fixed slot for a red blinking "New" tag) · Notice · Organisation · Type · Last date
  (orange ≤7 days, red ≤3; native-style tooltip "N days left"; NIL in light grey) · PDF. Newest first, 25 rows +
  "Show 25 more". Whole row clickable; big invisible tap areas. Cut-off titles show the full title in the same tooltip.
- "New": notice issued within 2 days (IST) AND (first visit OR published after your last visit; a visit ends after
  30 min away). Line "N new since your last visit".
- Search: typewriter hint "Search : <newest notices>"; Hindi + synonyms + typos; picks the tab; Esc keycap clears; `?q=`.
- Top strip: sticky frosted glass, WhatsApp icon, underlined link (no button shape; text + underline fade together
  on hover), × close (remembered per `data-id`). Underline offset 5px site-wide.
- Our own pages open in the same tab; official sites/PDFs in a new tab. NOT installable as an app (manifest removed,
  service worker self-unregisters).
- Full Hindi mode (not one English word except the Esc key). Back-to-top button bottom-right.
- Rejected (don't redo): command palette, boxed search, pillars/elephants in margins, click sounds, purple/charcoal
  strip, emoji siren, recent-search chips and bookmark pop-up (both parked; reminders set for Sun 25 Oct).

## 6. Where we are / next steps (in order)

1. **Boards still missing** (section 3b): India Post GDS first, then Tier 2 state commissions in batches of 5
   (MPSC, TNPSC, KPSC, WBPSC, HSSC/HPSC, GPSC, OPSC/OSSC, JPSC/JSSC, CGPSC, APPSC, TSPSC).
2. Notice detail page: the owner will give design instructions.
3. **Launch for search:** buy sarkarichart.com → connect to Cloudflare Pages → remove noindex (`site/_headers`) →
   sitemap, JobPosting schema, server-rendered notice list (SEO/AEO), Search Console + Bing.
4. **Speed (agreed in principle, not done):** outline the wordmark text into SVG paths + non-blocking Noto font;
   long cache headers for static assets.
5. Ready-to-paste WhatsApp channel posts per notice; Telegram channel automation; email sign-up (D1).
6. Later: sponsor slots, eligibility profile.

## 7. Mac mini notes

- Keep "Prevent automatic sleeping when the display is off" ON (System Settings → Energy). FileVault is on, so
  automatic login is impossible: after a power cut, log in once and the runner restarts by itself.
  Planned restarts: `sudo fdesetup authrestart`. A small UPS is the cheap fix for outages.
- If the Mac is off, India-board checks wait in the queue; the GitHub boards keep running.
- Budget alternatives to the Mac (not set up): Oracle Cloud Always Free (Mumbai/Hyderabad) or AWS Lightsail Mumbai.

## 8. Working conventions

- Commit as `rklokesh <rklokesh@users.noreply.github.com>`; push from the Mac with an `http.extraheader` built from
  `../.github-token` (never print the token; mask output with `sed "s/$T/***/g"`).
- **Always `git pull` first.** Bots commit data and `site/index.html` (the notice list between `/*ITEMS:START*/` and
  `/*ITEMS:END*/`) every hour. After hand-replacing `site/index.html`, run `python3 scripts/publish.py build`.
- Claude's remote file tools: git needs delete permission on the folder (lock files); `scripts/publish.py` could only be
  written via file commit (not shell) in one session, and `.github/workflows/*` only via shell — if one way is refused,
  try the other. Verify copies with sha256 (one truncated upload once broke the live page). Image files may be
  re-encoded in transfer (hash changes) — check dimensions/frames instead.
- Test every UI change in a headless browser (desktop + phone, EN + HI, light + dark) before pushing.
- Keep this file current: copy to the Mac folder root (`Sarkari Chart/HANDOVER.md`) AND `docs/HANDOVER.md`.
