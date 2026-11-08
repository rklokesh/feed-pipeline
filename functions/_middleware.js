// One address for everyone: www.sarkarichart.com and the old sarkarichart.pages.dev go to https://sarkarichart.com (same path).
export async function onRequest({ request, next }) {
  const url = new URL(request.url);
  if (url.hostname === "www.sarkarichart.com" || url.hostname === "sarkarichart.pages.dev") {
    url.hostname = "sarkarichart.com";
    url.protocol = "https:";
    return Response.redirect(url.toString(), 301);
  }
  return next();
}
