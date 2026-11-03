// "Report a mistake" form -> a GitHub issue labelled `user-report` (never mixed with notices; no notice-id,
// so the publish workflow ignores it whatever label it gets). Screenshot is kept in D1 and linked from the issue.
const REPO = "rklokesh/feed-pipeline";
const json = (o, s = 200) => new Response(JSON.stringify(o), { status: s, headers: { "content-type": "application/json", "cache-control": "no-store" } });
const clean = (s, n) => String(s || "").replace(/[\u0000-\u0008\u000b-\u001f]/g, "").slice(0, n);
const md = s => s.replace(/[<>]/g, c => (c === "<" ? "&lt;" : "&gt;")).replace(/@/g, "@​");   // no HTML, no @mentions

export async function onRequestPost({ request, env }) {
  let b; try { b = await request.json(); } catch (e) { return json({ ok: false }, 400); }
  if (b.website) return json({ ok: true });                       // honeypot: bots fill hidden fields
  const message = clean(b.message, 3000).trim();
  if (!message) return json({ ok: false }, 400);
  if (!env.DB || !env.GH_TOKEN) return json({ ok: false, why: "not configured" }, 503);
  // at most 5 reports per visitor per hour
  const ip = request.headers.get("cf-connecting-ip") || "0";
  const h = [...new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(ip + "sc")))].slice(0, 8).map(x => x.toString(16).padStart(2, "0")).join("");
  const now = Date.now();
  const recent = await env.DB.prepare("SELECT COUNT(*) AS c FROM report_rl WHERE ip = ?1 AND ts > ?2").bind(h, now - 3600e3).first();
  if (recent && recent.c >= 5) return json({ ok: false, why: "slow down" }, 429);
  await env.DB.prepare("INSERT INTO report_rl (ip, ts) VALUES (?1, ?2)").bind(h, now).run();

  const page = /^\/notice\/[a-z0-9-]+\/$/.test(b.page || "") ? b.page : "";
  const origin = new URL(request.url).origin;
  let imgLine = "";
  if (typeof b.image === "string" && /^data:image\/jpeg;base64,/.test(b.image) && b.image.length < 2_800_000) {
    const id = crypto.randomUUID().replace(/-/g, "");
    await env.DB.prepare("INSERT INTO report_img (id, data, ts) VALUES (?1, ?2, ?3)").bind(id, b.image.split(",")[1], now).run();
    imgLine = `\n\n**Screenshot:**\n\n![screenshot](${origin}/api/report-img?id=${id})`;
  }
  const name = md(clean(b.name, 80)), email = md(clean(b.email, 120));
  const body = `**Page:** ${page ? origin + page : "General"}\n**From:** ${name || "—"}${email ? " · " + email : ""} · ${b.lang === "hi" ? "Hindi" : "English"}\n\n> ${md(message).replace(/\n/g, "\n> ")}${imgLine}\n\n<!-- user-report -->`;
  const title = `Report: ${page ? page.replace(/^\/notice\/|\/$/g, "") : "general"} — ${message.slice(0, 60).replace(/\s+/g, " ")}`;
  const r = await fetch(`https://api.github.com/repos/${REPO}/issues`, {
    method: "POST",
    headers: { Authorization: `Bearer ${env.GH_TOKEN}`, Accept: "application/vnd.github+json", "User-Agent": "sarkarichart-report", "content-type": "application/json" },
    body: JSON.stringify({ title, body, labels: ["user-report"] }) });
  return json({ ok: r.ok }, r.ok ? 200 : 502);
}
