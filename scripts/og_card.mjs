// Share images (1200x630) for every notice: site/notice/<slug>/og.png from og.json, plus site/og.png (brand card).
// Shown as the link preview on WhatsApp/Telegram/X and usable for channel posts. Calm, on brand, readable as a thumbnail.
// Usage: node scripts/og_card.mjs [siteDir]
import { chromium } from "playwright";
import { readdirSync, existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

const SITE = process.argv[2] || "site";
const home = readFileSync(join(SITE, "index.html"), "utf8");
const logo = (home.match(/<svg class="mark"[\s\S]*?<\/svg>/) || [""])[0]
  .replace(/class="mark"/, 'class="mark" style="color:#36322D"').replace(/width="138" height="139"/, 'width="230" height="232"');
const esc = s => String(s || "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

function card(o) {
  const right = o.brand
    ? `<div class="kick">GOVT JOBS · EXAMS · RESULTS</div><h1>Every official notice,<br>clean and on time.</h1><p class="hi">सरकारी नौकरी, परीक्षा और रिज़ल्ट की हर आधिकारिक सूचना</p>`
    : `<div class="kick">${esc(o.org)} · ${esc(o.type_en)}<span class="hik">${esc(o.type_hi)}</span></div>
       <h1>${esc(o.title_en)}</h1>${o.title_hi ? `<p class="hi">${esc(o.title_hi)}</p>` : ""}`;
  const foot = o.brand ? "" : (o.last_en
    ? `<div class="pill"><span>Last date</span><b>${esc(o.last_en)}</b><span class="hid">अंतिम तिथि</span></div>`
    : (o.status_en ? `<div class="pill"><b>${esc(o.status_en)}</b></div>` : ""));
  return `<!doctype html><html><head><meta charset="utf-8"><style>
  *{box-sizing:border-box;margin:0}
  body{width:1200px;height:630px;background:#FBFAF7;color:#36322D;font-family:"Helvetica Neue",Helvetica,Arial,"Noto Sans","Noto Sans Devanagari",sans-serif;
    display:grid;grid-template-columns:300px 1fr;border:14px solid #F1EDE4}
  .l{display:grid;place-items:center;border-right:1px solid #E5E1D8}
  .r{padding:56px 64px 48px 56px;display:flex;flex-direction:column;gap:18px;min-width:0}
  .kick{font-size:24px;letter-spacing:.08em;color:#76726B;text-transform:uppercase;display:flex;gap:18px;align-items:baseline}
  .hik{text-transform:none;letter-spacing:0}
  h1{font-size:${o.brand ? 62 : 54}px;line-height:1.12;font-weight:600;letter-spacing:-.01em;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
  .hi{font-size:32px;line-height:1.35;color:#5E5A53;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
  .bot{margin-top:auto;display:flex;align-items:center;justify-content:space-between;gap:20px}
  .pill{display:flex;gap:14px;align-items:baseline;font-size:28px;padding:12px 20px;border:2px solid #B23A1A;color:#B23A1A;border-radius:8px}
  .pill b{font-weight:700}.pill span,.pill b{white-space:nowrap}.pill .hid{font-size:22px;color:#76726B}
  .url{font-size:26px;color:#76726B;letter-spacing:.02em}
  </style></head><body><div class="l">${logo}</div><div class="r">${right}<div class="bot">${foot}<span class="url">sarkarichart.com</span></div></div></body></html>`;
}

const browser = await chromium.launch(process.env.CHROME ? { executablePath: process.env.CHROME } : {});
const page = await browser.newPage({ viewport: { width: 1200, height: 630 } });
await page.setContent(card({ brand: true }), { waitUntil: "load" });
await page.screenshot({ path: join(SITE, "og.png") });
const dir = join(SITE, "notice");
for (const slug of existsSync(dir) ? readdirSync(dir) : []) {
  const f = join(dir, slug, "og.json");
  if (!existsSync(f)) continue;
  await page.setContent(card(JSON.parse(readFileSync(f, "utf8"))), { waitUntil: "load" });
  await page.screenshot({ path: join(dir, slug, "og.png") });
  console.log("og", slug);
}
await browser.close();
