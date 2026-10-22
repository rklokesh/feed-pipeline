// Serves a report screenshot by its random id (linked only from the private GitHub issue).
export async function onRequestGet({ request, env }) {
  const id = new URL(request.url).searchParams.get("id") || "";
  if (!/^[a-f0-9]{32}$/.test(id) || !env.DB) return new Response("not found", { status: 404 });
  const row = await env.DB.prepare("SELECT data FROM report_img WHERE id = ?1").bind(id).first();
  if (!row) return new Response("not found", { status: 404 });
  const bin = Uint8Array.from(atob(row.data), c => c.charCodeAt(0));
  return new Response(bin, { headers: { "content-type": "image/jpeg", "cache-control": "private, max-age=86400", "x-robots-tag": "noindex" } });
}
