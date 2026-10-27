// Share images for every notice: site/notice/<slug>/og.png (English) and og-hi.png (Hindi), from og.json (written
// by scripts/pages.py), plus the brand card site/og.png. 1200x675, big bold bands: brand + our logo · tags ·
// organisation logo + name · post/exam line · headline · call to action. Shown as the link preview on
// WhatsApp/Telegram/X and posted to the Telegram channel. Usage: node scripts/og_card.mjs [siteDir]
import { chromium } from "playwright";
import { readdirSync, existsSync, readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const SITE = process.argv[2] || "site";
const HERE = dirname(fileURLToPath(import.meta.url));
const ORG = join(HERE, "..", "assets", "org");
const b64 = p => readFileSync(p).toString("base64");
const FONT = f => b64(join(HERE, "fonts", f));
const P7 = FONT("poppins-latin-700-normal.woff2"), P9 = FONT("poppins-latin-900-normal.woff2"), D9 = FONT("noto-sans-devanagari-devanagari-900-normal.woff2");
// our logo exactly as provided
const LOGO = b64(join(SITE, "sarkarichart-logo.png"));
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const logoCache = {};
const orgLogo = k => k && existsSync(join(ORG, k + ".png")) ? (logoCache[k] ??= b64(join(ORG, k + ".png"))) : "";

function card(t, o, hi) {
  const ol = orgLogo(o.logo);
  const posts = o.posts ? `&nbsp;–&nbsp;<span class="y">${o.posts.toLocaleString("en-IN")} ${hi ? "पद" : (o.posts === 1 ? "Post" : "Posts")}</span>` : "";
  const exam = t.exam ? `&nbsp;·&nbsp;<span class="y">${hi ? "परीक्षा" : "Exam"} ${esc(t.exam)}</span>` : "";
  const line = (t.line ? `<span class="t">${esc(t.line)}</span>` : "") + posts + exam;
  return `<!doctype html><html><head><meta charset="utf-8"><style>
@font-face{font-family:P;src:url(data:font/woff2;base64,${P7})}
@font-face{font-family:P9;src:url(data:font/woff2;base64,${P9})}
@font-face{font-family:D;src:url(data:font/woff2;base64,${D9})}
*{box-sizing:border-box;margin:0}
body{width:1200px;height:675px;font-family:P,D,sans-serif;font-weight:800;background:#fff;position:relative;overflow:hidden}
.b{position:absolute;left:0;width:1200px;display:flex;align-items:center;white-space:nowrap}
.b1,.b2{justify-content:space-around;color:#fff}
.b1{top:0;height:100px;background:#1A3E8C;font-size:72px;letter-spacing:2px;-webkit-mask:radial-gradient(circle 104px at 600px 98px,transparent 99%,#000 100%)}
.b2{top:100px;height:96px;background:#D32F2F;border-bottom:6px solid #fff;-webkit-mask:radial-gradient(circle 104px at 600px -2px,transparent 99%,#000 100%)}
.h{width:420px;text-align:center;display:block;overflow:hidden}
.b2 .h{font-size:${hi ? 46 : 42}px}
.logo{position:absolute;left:508px;top:6px;width:184px;height:184px}
.w{top:202px;height:205px;justify-content:center;gap:40px;padding:0 40px}
.olimg{width:190px;height:190px;object-fit:contain;flex:none}
.org{font-family:P9,D,sans-serif;font-weight:900;font-size:${hi ? 176 : 215}px;color:#7B1113;letter-spacing:2px;line-height:1.15;-webkit-text-stroke:3px #7B1113;${hi ? "padding-top:18px;" : ""}}
.b3{top:410px;height:84px;background:#D32F2F;color:#fff;font-size:${hi ? 52 : 50}px;justify-content:center;padding:0 30px}
.b3 .y{color:#FFD400}
.b4{top:494px;height:112px;background:#FFD400;color:#111;font-size:${hi ? 86 : 82}px;justify-content:center;padding:0 30px}
.b5{top:606px;height:69px;background:#1A3E8C;color:#fff;font-size:42px;justify-content:center;letter-spacing:1px;padding:0 30px}
</style></head><body>
<div class="b b1"><span class="h">${hi ? "सरकारी" : "SARKARI"}</span><span class="h">${hi ? "चार्ट" : "CHART"}</span></div>
<div class="b b2"><span class="h"><span class="fit" data-max="370">${esc(t.tagL)}</span></span><span class="h"><span class="fit" data-max="370">${esc(t.tagR)}</span></span></div>
<img class="logo" src="data:image/png;base64,${LOGO}" alt="">
<div class="b w">${ol ? `<img class="olimg" src="data:image/png;base64,${ol}" alt="">` : ""}<div class="org fit" data-max="${ol ? 870 : 1100}">${esc(t.org)}</div></div>
<div class="b b3"><div class="fit" data-max="1140">${line}</div></div>
<div class="b b4"><div class="fit" data-max="1140">${esc(t.headline)}</div></div>
<div class="b b5"><div class="fit" data-max="1140">${esc(t.cta)}</div></div>
<script>
// shrink any text that would not fit its band (never grow)
for (const e of document.querySelectorAll(".fit")) {
  const max = +e.dataset.max || e.clientWidth || 400;
  e.style.display = "inline-block";
  let s = parseFloat(getComputedStyle(e).fontSize);
  while (e.scrollWidth > max && s > 18) { s -= 2; e.style.fontSize = s + "px"; }
}
</script></body></html>`;
}

const BRAND = {
  en: { org: "", tagL: "JOBS | ADMIT CARDS", tagR: "RESULTS | ANSWER KEYS", line: "Every official notice, clean and on time", headline: "Govt Jobs · Exams · Results", cta: "SARKARICHART.COM" },
  hi: { org: "", tagL: "नौकरी | एडमिट कार्ड", tagR: "रिज़ल्ट | आंसर की", line: "हर आधिकारिक सूचना, साफ़ और समय पर", headline: "सरकारी नौकरी · परीक्षा · रिज़ल्ट", cta: "SARKARICHART.COM" },
};

const browser = await chromium.launch(process.env.CHROME ? { executablePath: process.env.CHROME } : {});
const page = await browser.newPage({ viewport: { width: 1200, height: 675 } });
async function shot(html, path) {
  await page.setContent(html, { waitUntil: "load" });
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path });
}
await shot(card({ ...BRAND.en, org: "सरकारी चार्ट" }, {}, false), join(SITE, "og.png"));
const dir = join(SITE, "notice");
let made = 0;
for (const slug of existsSync(dir) ? readdirSync(dir) : []) {
  const f = join(dir, slug, "og.json");
  if (!existsSync(f)) continue;
  const o = JSON.parse(readFileSync(f, "utf8"));
  if (!o.en) continue;               // og.json from before the new cards: rewritten by pages.py on its next run
  try {
    await shot(card(o.en, o, false), join(dir, slug, "og.png"));
    await shot(card(o.hi, o, true), join(dir, slug, "og-hi.png"));
    made++;
  } catch (e) { console.log("og failed", slug, e.message); }
}
console.log("share cards:", made);
await browser.close();
