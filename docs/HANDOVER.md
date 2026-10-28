# SarkariChart — Handover

Everything needed to continue this project from any Claude account (or by a person).
Last updated: 28 Oct 2026 (early morning IST). Owner: the site owner.

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
- **Lead list:** Telegram channel **@sarkarichart** (https://t.me/sarkarichart) — in the top strip, posted to
  automatically after every deploy. WhatsApp is kept only for the reader's "Share on WhatsApp" button (channel posting
  can't be automated safely). Later: email sign-up (the list we own; Cloudflare D1).
- Full research, competitors, revenue model, legal notes: **docs/PLAN.md**.

## 2. Where everything lives (all owned by the owner)

| Thing | Where |
|---|---|
| Code + data | GitHub `rklokesh/sarkarichart` (private); Mac copy: `/Volumes/Workspace/App idea/Sarkari Chart/sarkarichart` |
| Live site | Cloudflare Pages project `sarkarichart` → https://sarkarichart.pages.dev |
| Test views | `?preview=returning` (returning-visitor view + demo rows), `?demo` (demo rows) |
| GitHub secrets | `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, `GEMINI_API_KEY`, `TELEGRAM_BOT_TOKEN` (never ask for it in chat), `REPORT_GH_TOKEN` |
| Personal GitHub token (pushes + API from the Mac) | `Sarkari Chart/.github-token` — outside the repo, never paste/print it. Has Contents, Actions, Administration (R/W). Cannot read Issues. |
| Self-hosted runner | Mac mini, runner name `mac-mini-india`, labels `self-hosted, india`; installed by `Sarkari Chart/setup-runner.sh`; runs as a LaunchAgent (starts when the owner is logged in) |
| Site logo | The original red eagle badge `Sarkari Chart/sarkarichart-logo.png` = `site/sarkarichart-logo.png` (byte-identical). **Never modify it** (no crop/mask/recolour); only scaled copies: `-276.webp`, `-64.png`, `-180.png`. |
| Board logos | Originals: `~/Desktop/Logos` (the owner's). Repo: `assets/org/<key>.png` (≤400px, only blank margins trimmed) for share cards; `site/org/<key>.webp` (152px) for notice pages. Board → key map: `BOARDS` in `scripts/share_card.py`. |
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


## 3c. Check schedule (23 Oct)

- **Mac timer (main):** launchd job `com.sarkarichart.poke` (installed by `Sarkari Chart/setup-timer.sh`) dispatches
  `watch-india.yml` every 30 min. Files: `~/.sarkarichart/{poke.sh,token,poke.log}` (external drives are off-limits to
  background jobs on macOS, so they live in the home folder). Undo command is at the top of setup-timer.sh.
- `watch-india.yml` now checks ALL boards (runner india + github) on the Mac; `prepare.yml` runs on the Mac after a Mac
  check (dynamic runs-on), on GitHub after the backup check. `watch.yml` (GitHub) is a 3-hourly backup.
  Both watchers share concurrency group `watch-data`.
- GitHub's free cron was skipping runs (gaps of 3–6 h) — that is why the Mac timer exists.
- "New" tag rule (final): officially issued today or yesterday (IST), same for everyone; list strictly newest official
  date first; "N new since your last visit" line retired.

## 3d. Added 24–28 Oct

- **Telegram:** `scripts/telegram.py` + `telegram.yml` (after each deploy) posts new notices to @sarkarichart with the
  share image (`sendPhoto`, falls back to text). Remembers what it posted in `data/telegram.json`.
- **SEO:** JSON-LD on notice pages (BreadcrumbList, WebPage, FAQPage, JobPosting only when a last date exists) and
  homepage (Organization, WebSite + SearchAction `?q=`); og/twitter tags with alt text. Still noindex until launch.
- **Share cards (approved design):** `scripts/og_card.mjs` draws `og.png` (English) + `og-hi.png` (Hindi), 1200×675, at
  deploy from each notice's `og.json`. Bands: blue SARKARI | logo | CHART · red tag pairs curved around our logo · white
  board logo + board name (maroon #7B1113, Poppins 900) · red post/exam line (+ yellow "N Posts" / exam date) · yellow
  headline · blue call to action. Words per kind (job/admit/result/answer/corr/sched) and fallbacks live in
  `scripts/share_card.py`; AI adds a `share_card` block to each page. Past last date → "APPLICATIONS CLOSED".
  Fonts (OFL) in `scripts/fonts/`. Deploy cache key `pdfs-og2-…` includes fonts + logos.
- **Notice page = full article** (`pages.py` PROMPT + render, `templates/notice.html`): board logo above the breadcrumb,
  big bold heading, "Updated · Source" line, **At a glance** box, collapsible **On this page** contents, then About, What
  changed (corrigenda), Who should read / Who cannot apply, Dates, Fee, Age, Vacancies (with Total row), Eligibility,
  Physical standards, Pay, Exam pattern table, Selection, How to apply, Documents, Common mistakes, Good to know,
  What happens next, Other details, Official links, FAQ (up to 12, always open), Final checklist, Hindi summary (hidden in
  Hindi mode), More notices. Facts only from the PDF — missing facts mean the section is left out.
  Older pages are upgraded by the AI 6 per run (`PAGE_BACKFILL`; marker: page has no `share_card`).
  Research behind it: competitor pages (SahiSarkariJobs ~4,000 words with tables; SarkariJobNews ~1,300 words, weak).
- **Homepage:** tabs left-aligned; ← / → switch tabs (outside the search box); ↑/↓ + Enter open rows from anywhere;
  **Closing soon** leads with the Last date column (nearest first), Posted moves to the right (phones keep last date
  on the right); every other tab: newest official date first. Search hint shows newest open jobs + popular exams.

## 4. Board status (28 Oct 2026)

- Working (47 sources): UPSC, SSC, NTA, RRB unified (follow mode), RRC NR/WR/CR, SBI, RBI, NABARD, Navy, BSF, ITBP,
  ISRO, UPPSC, UP Police, BPSC, CSBC, RPSC, RSSB, MPPSC, DSSSB, UKPSC, HPSC, HSSC, TNPSC, CTET, KVS, plus (fixed 28 Oct):
  - **IBPS** — Mac runner (GitHub gets a TLS error); follows the running CRP pages (`specialist-officers-xvi` etc.),
    reads PDFs under wp-content/uploads. Score/call-letter items are login links and can't be read.
  - **LIC** — follows `licindia.in/recruitment-of-…` pages; documents are `/documents/d/guest/<name>`.
  - **UPSSSC** — `AllNotifications.aspx` (js), PDFs via `ViewPdf.aspx?…`.
  - **BSSC** — `NoticeBoard.htm` (direct PDFs).
  - **WBPSC** — links are `Download?param1=…pdf&param2=…`; html.parser turned `&param` into `¶m` → fixed in
    `links_from_html`; PDF_HINTS now accepts `.pdf&`.
  Each got a fresh baseline (seen.json entry removed → first run records old notices, publishes only 5 samples).
- Not working: **MPSC** (list loads from a JSON feed, needs its own reader), MP ESB (certificate chain),
  RRB Chandigarh (certificate hostname mismatch — don't bypass), CRPF/DRDO/IAF (URLs dead or down).
- Added 28 Oct: **India Post** (`/vacancies`, documents `/api/documents/file/…`), **Coast Guard** (now the CGCAT page),
  **CISF** (`file_open.php?fnm=…`; site gave 502 on its first check — retried every run).
- Not possible yet (checked 28 Oct): India Post GDS site, GPSC, KPSC, CG Vyapam (time out even from India), SSB (DNS
  gone), JSSC (times out), OPSC (inner pages bounce to home without a session), Army (login portal only), NVS, Assam
  Rifles and Employment News (pages are JS apps with no document links — would need their data feeds).

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
- "New": officially issued today or yesterday (IST), same for everyone (red arrow image `new-en/hi.png`).
- Search: typewriter hint "Search : <newest notices>"; Hindi + synonyms + typos; picks the tab; Esc keycap clears; `?q=`.
- Top strip: sticky frosted glass, Telegram icon, underlined link (no button shape; text + underline fade together
  on hover), × close (remembered per `data-id`). Underline offset 5px site-wide.
- Our own pages open in the same tab; official sites/PDFs in a new tab. NOT installable as an app (manifest removed,
  service worker self-unregisters).
- Full Hindi mode (not one English word except the Esc key). Back-to-top button bottom-right.
- Rejected (don't redo): command palette, boxed search, pillars/elephants in margins, click sounds, purple/charcoal
  strip, emoji siren, recent-search chips and bookmark pop-up (both parked; reminders set for Sun 25 Oct).

## 6. Where we are / next steps (in order)

1. **MPSC** reader (JSON feed) — the other broken boards were fixed on 28 Oct (section 4).
2. **Add boards:** India Post GDS, Army, Navy/Air Force Agniveer, Coast Guard, CRPF, CISF, DRDO, Employment News,
   SSB, NVS, Assam Rifles, GPSC, KPSC, OPSC, CG Vyapam (logos for most are already in `assets/org`).
3. Trust pages are live (28 Oct): /about/, /privacy/, /terms/, /contact/ — built by `scripts/info_pages.py` (edit text there; runs in prepare/publish workflows). Press kit page still to do.
4. **Launch for search — ready, waiting for the domain.** `scripts/seo_files.py` builds sitemap.xml, robots.txt (closed
   while `LAUNCHED = False`) and llms.txt on every publish. Domain day: connect sarkarichart.com in Cloudflare Pages →
   `python3 scripts/go_live.py https://sarkarichart.com` (switches every address, removes noindex, opens robots, rebuilds;
   tested on a copy 28 Oct) → commit + push → Search Console + Bing, submit /sitemap.xml → contact@ email via Cloudflare
   Email Routing. Reader profile + search words: `docs/KEYWORDS.md` (titles now follow it: "<board> <post> <search word>
   <year> – <hook>", browser title adds " | SarkariChart" when it fits).
5. **Exam pages are live (28 Oct)** — `scripts/exams.py`: `tag` (before pages.py; one batched AI call tags each notice with
   `exam: {key: "ssc-cgl-2026", name_en, name_hi}`, `{}` = not part of an exam; reuses known keys) and `build` (after
   pages.py): `/exam/<key>/` for exams with 2+ live notices (timeline with stage labels from share_card headlines, key
   facts from the notification, more exams from the same board, ItemList schema), `/exam/` index, homepage **Exams tab** (rows written into
   index.html between `/*EXAMS:START*/` markers; one row per exam: updated date, name, board, latest type, N updates), "All updates for <exam> →" link under each notice heading, sitemap entries.
   First run: 113 notices tagged, 29 exam pages. To fix a wrong grouping, edit the notice's `exam` in data/notices.
6. After launch: Google Discover follow link, parked bookmark pop-up and recent searches; MPSC/NVS/Employment News feed
   readers; press kit page.
6. Owner to-do: buy the domain (Telegram channel photo is set). On domain day also set up Cloudflare Email Routing for contact@sarkarichart.com and add it to /contact/. Never put the owner's name or company on the site.

## 7. Mac mini notes

- Keep "Prevent automatic sleeping when the display is off" ON (System Settings → Energy). FileVault is on, so
  automatic login is impossible: after a power cut, log in once and the runner restarts by itself.
  Planned restarts: `sudo fdesetup authrestart`. A small UPS is the cheap fix for outages.
- If the Mac is off, India-board checks wait in the queue; the GitHub boards keep running.
- Budget alternatives to the Mac (not set up): Oracle Cloud Always Free (Mumbai/Hyderabad) or AWS Lightsail Mumbai.

## 8. Working conventions

- Commit as `rklokesh <rklokesh@users.noreply.github.com>`; push from the Mac with an `http.extraheader` built from
  `../.github-token` (never print the token; mask output with `sed "s/$T/***/g"`). Working recipe:
  `B=$(printf 'x-access-token:%s' "$T" | base64 | tr -d '\n')` then `git -c http.extraheader="AUTHORIZATION: basic $B" …`
  (without `tr -d '\n'` long tokens wrap and GitHub answers 400). For rebases set `GIT_COMMITTER_NAME/EMAIL`.
- Claude's Mac shell is a Linux VM: `sed -i` (not `sed -i ''`), no `~/.sarkarichart-venv`; system `python3` has
  requests, yaml and Pillow, so `PAGE_BACKFILL=0 python3 scripts/pages.py` rebuilds pages without AI.
- **Always `git pull` first.** Bots commit data and `site/index.html` (the notice list between `/*ITEMS:START*/` and
  `/*ITEMS:END*/`) every hour. After hand-replacing `site/index.html`, run `python3 scripts/publish.py build`.
- Claude's remote file tools: git needs delete permission on the folder (lock files); `scripts/publish.py` could only be
  written via file commit (not shell) in one session, and `.github/workflows/*` only via shell — if one way is refused,
  try the other. Verify copies with sha256 (one truncated upload once broke the live page). Image files may be
  re-encoded in transfer (hash changes) — check dimensions/frames instead.
- Test every UI change in a headless browser (desktop + phone, EN + HI, light + dark) before pushing.
- Keep this file current: copy to the Mac folder root (`Sarkari Chart/HANDOVER.md`) AND `docs/HANDOVER.md`.
