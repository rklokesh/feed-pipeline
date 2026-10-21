// Prints every notice page (site/notice/<slug>/index.html) to PDF, in English and Hindi.
// Output: site/notice/<slug>/sarkarichart-<slug>-en.pdf and -hi.pdf
// Usage: node scripts/make_pdfs.mjs [siteDir]   (needs the `playwright` package and Chromium)
import { chromium } from "playwright";
import { createServer } from "node:http";
import { readdirSync, existsSync, readFileSync } from "node:fs";
import { join, extname, normalize } from "node:path";

const SITE = process.argv[2] || "site";
const TYPES = { ".html": "text/html; charset=utf-8", ".png": "image/png", ".css": "text/css", ".js": "text/javascript", ".pdf": "application/pdf" };

const server = createServer((req, res) => {
  let p = decodeURIComponent(new URL(req.url, "http://x").pathname);
  if (p.endsWith("/")) p += "index.html";
  const file = normalize(join(SITE, p));
  if (!file.startsWith(normalize(SITE)) || !existsSync(file)) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { "content-type": TYPES[extname(file)] || "application/octet-stream" });
  res.end(readFileSync(file));
}).listen(0);
const port = server.address().port;

const dir = join(SITE, "notice");
const slugs = existsSync(dir) ? readdirSync(dir).filter(d => existsSync(join(dir, d, "index.html"))) : [];
const browser = await chromium.launch();
for (const slug of slugs) {
  for (const lang of ["en", "hi"]) {
    const page = await browser.newPage();
    await page.addInitScript(l => { try { localStorage.setItem("sc-lang", l); } catch (e) {} }, lang);
    await page.goto(`http://127.0.0.1:${port}/notice/${slug}/`, { waitUntil: "networkidle" });
    await page.emulateMedia({ media: "print" });
    const out = join(dir, slug, `sarkarichart-${slug}-${lang}.pdf`);
    await page.pdf({ path: out, format: "A4", printBackground: true, margin: { top: "16mm", bottom: "16mm", left: "14mm", right: "14mm" } });
    console.log("made", out);
    await page.close();
  }
}
await browser.close();
server.close();
