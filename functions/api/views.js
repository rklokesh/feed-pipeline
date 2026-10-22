// View counter for notice pages (Cloudflare Pages Function + free D1 database).
// POST /api/views?slug=<slug>  -> counts one view, returns {n}
// GET  /api/views?slug=<slug>  -> returns {n}
const SLUG = /^[a-z0-9-]{3,120}$/;
const BOT = /bot|crawl|spider|slurp|preview|headless|lighthouse|facebookexternalhit|whatsapp/i;

export async function onRequest({ request, env }) {
  const url = new URL(request.url);
  const slug = url.searchParams.get("slug") || "";
  const json = (o, s = 200) => new Response(JSON.stringify(o), { status: s, headers: { "content-type": "application/json", "cache-control": "no-store" } });
  if (!SLUG.test(slug) || !env.DB) return json({ n: null }, 400);
  if (request.method === "POST" && !BOT.test(request.headers.get("user-agent") || "")) {
    const row = await env.DB.prepare("INSERT INTO views (slug, n) VALUES (?1, 1) ON CONFLICT(slug) DO UPDATE SET n = n + 1 RETURNING n").bind(slug).first();
    return json({ n: row ? row.n : null });
  }
  const row = await env.DB.prepare("SELECT n FROM views WHERE slug = ?1").bind(slug).first();
  return json({ n: row ? row.n : 0 });
}
