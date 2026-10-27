"""Builds site/report/index.html (the "Report a mistake" form) from the notice-page template."""
from __future__ import annotations

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
TPL = (ROOT / "templates/notice.html").read_text(encoding="utf-8")

EN = {"title": "Report a mistake · SarkariChart", "h1": "Report a mistake",
      "lead": "Tell us what is wrong and we will check it against the official notice. Thank you for helping.",
      "fPage": "Page", "fPageNone": "General (not about one page)", "fName": "Your name", "fEmail": "Email (optional, only if you want a reply)",
      "fMsg": "What is wrong?", "fMsgPh": "e.g. The last date is 30 November, not 25 November.",
      "fShot": "Screenshot (optional)", "fShotBtn": "Choose image", "fShotNone": "No image chosen", "send": "Send report",
      "sending": "Sending…", "ok": "Thank you. Your report has reached us and we will check it soon.",
      "err": "Sorry, it did not send. Please try again in a minute.", "tooBig": "That image is too large. Please choose one under 8 MB.",
      "need": "Please write what is wrong.", "statusV": ""}
HI = {"title": "गलती बताएँ · सरकारी चार्ट", "h1": "गलती बताएँ",
      "lead": "बताइए क्या गलत है, हम उसे आधिकारिक सूचना से मिलाकर जाँचेंगे। मदद के लिए धन्यवाद।",
      "fPage": "पेज", "fPageNone": "सामान्य (किसी एक पेज के बारे में नहीं)", "fName": "आपका नाम", "fEmail": "ईमेल (वैकल्पिक, जवाब चाहिए तो)",
      "fMsg": "क्या गलत है?", "fMsgPh": "जैसे: अंतिम तिथि 25 नवंबर नहीं, 30 नवंबर है।",
      "fShot": "स्क्रीनशॉट (वैकल्पिक)", "fShotBtn": "तस्वीर चुनें", "fShotNone": "कोई तस्वीर नहीं चुनी", "send": "रिपोर्ट भेजें",
      "sending": "भेजा जा रहा है…", "ok": "धन्यवाद। आपकी रिपोर्ट हमें मिल गई है, हम जल्द जाँचेंगे।",
      "err": "माफ़ कीजिए, रिपोर्ट नहीं गई। एक मिनट बाद फिर कोशिश करें।", "tooBig": "यह तस्वीर बहुत बड़ी है। 8 MB से छोटी तस्वीर चुनें।",
      "need": "कृपया लिखें कि क्या गलत है।", "statusV": ""}

MAIN = r'''    <style>
      .rp { display: grid; gap: 28px; max-width: 40rem; }
      .rp .crumb { margin-bottom: 0; }
      .rp h1 { margin-top: 10px; }
      .rp .lead { margin-top: 8px; }
      .rp form { display: grid; gap: 22px; }
      .rp label, .rp .fl { display: grid; gap: 6px; color: var(--grey); }
      .rp input[type=text], .rp input[type=email], .rp textarea { font: inherit; color: var(--ink); background: transparent; border: 0;
        border-bottom: 1px solid var(--line); padding: 6px 0; outline: none; border-radius: 0; width: 100%; }
      .rp textarea { min-height: 7.5rem; resize: vertical; line-height: 1.4; }
      .rp input:focus, .rp textarea:focus { border-bottom-color: var(--ink); }
      .rp ::placeholder { color: color-mix(in srgb, var(--grey) 70%, transparent); }
      .rp .pg { color: var(--ink); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .rp .file { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; color: var(--ink); }
      .rp .file input { position: absolute; width: 1px; height: 1px; opacity: 0; }
      .rp .pick { text-decoration: underline; text-underline-offset: 5px; text-decoration-thickness: 1px; cursor: pointer; }
      .rp .fname { color: var(--grey); }
      .rp .thumb { max-height: 72px; border: 1px solid var(--line); border-radius: 4px; }
      .rp .hp { position: absolute; left: -9999px; }
      .rp button { all: unset; cursor: pointer; justify-self: start; color: var(--ink); text-decoration: underline; text-underline-offset: 5px; text-decoration-thickness: 1px; position: relative; }
      .rp button::after { content: ""; position: absolute; inset: -12px -9px; }
      .rp button:disabled { color: var(--grey); cursor: default; }
      .rp .msg { min-height: 1.4em; }
      .rp .msg.ok { color: var(--calm); } .rp .msg.bad { color: var(--hot); }
    </style>
    <div class="rp">
      <div>
        <h1 data-t="h1">Report a mistake</h1>
        <p class="lead" data-t="lead"></p>
      </div>
      <form id="rf" novalidate>
        <div class="fl"><span data-t="fPage">Page</span><a class="pg" id="pg" href="/"></a></div>
        <label><span data-t="fMsg">What is wrong?</span><textarea id="msg" maxlength="3000" required data-t-ph="fMsgPh"></textarea></label>
        <label><span data-t="fName">Your name</span><input type="text" id="name" maxlength="80" autocomplete="name"></label>
        <label><span data-t="fEmail">Email</span><input type="email" id="email" maxlength="120" autocomplete="email"></label>
        <div class="fl"><span data-t="fShot">Screenshot (optional)</span>
          <span class="file"><label class="pick" for="shot"><span data-t="fShotBtn">Choose image</span></label><input type="file" id="shot" accept="image/*"><span class="fname" id="fname" data-t="fShotNone"></span><img class="thumb" id="thumb" alt="" hidden></span></div>
        <input class="hp" type="text" id="website" tabindex="-1" autocomplete="off" aria-hidden="true">
        <button type="submit" id="send" data-t="send">Send report</button>
        <p class="msg" id="out" role="status" aria-live="polite"></p>
      </form>
    </div>
    <span id="state" hidden></span><span id="left" hidden></span><span id="views" hidden></span><a id="dlPdf" hidden></a><a id="share" hidden></a>
    <script>
    (() => {
      const $ = id => document.getElementById(id);
      const L = () => (document.documentElement.lang === "hi" ? "hi" : "en");
      const S = { en: %EN%, hi: %HI% };
      const tx = k => S[L()][k];
      const page = new URLSearchParams(location.search).get("page") || "";
      const safe = /^\/notice\/[a-z0-9-]+\/$/.test(page) ? page : "";
      function paint() {
        $("pg").textContent = safe ? location.origin + safe : tx("fPageNone"); $("pg").href = safe || "/";
        $("msg").placeholder = tx("fMsgPh");
        if (!img) $("fname").textContent = tx("fShotNone");
      }
      new MutationObserver(paint).observe(document.documentElement, { attributes: true, attributeFilter: ["lang"] });
      let img = null;
      $("shot").addEventListener("change", async e => {
        const f = e.target.files[0]; img = null; $("thumb").hidden = true; $("out").textContent = "";
        if (!f) return paint();
        if (f.size > 8e6) { $("out").className = "msg bad"; $("out").textContent = tx("tooBig"); e.target.value = ""; return paint(); }
        // shrink to at most 1600px wide JPEG so it uploads fast on mobile data
        const bmp = await createImageBitmap(f); const k = Math.min(1, 1600 / bmp.width);
        const c = document.createElement("canvas"); c.width = Math.round(bmp.width * k); c.height = Math.round(bmp.height * k);
        c.getContext("2d").drawImage(bmp, 0, 0, c.width, c.height);
        img = c.toDataURL("image/jpeg", 0.82);
        $("thumb").src = img; $("thumb").hidden = false; $("fname").textContent = f.name;
      });
      $("rf").addEventListener("submit", async e => {
        e.preventDefault();
        const out = $("out"), msg = $("msg").value.trim();
        if (!msg) { out.className = "msg bad"; out.textContent = tx("need"); $("msg").focus(); return; }
        $("send").disabled = true; out.className = "msg"; out.textContent = tx("sending");
        try {
          const r = await fetch("/api/report", { method: "POST", headers: { "content-type": "application/json" },
            body: JSON.stringify({ page: safe, message: msg, name: $("name").value.trim(), email: $("email").value.trim(), image: img, website: $("website").value, lang: L() }) });
          if (!r.ok) throw 0;
          out.className = "msg ok"; out.textContent = tx("ok"); $("rf").reset(); img = null; $("thumb").hidden = true; paint();
        } catch (err) { out.className = "msg bad"; out.textContent = tx("err"); }
        $("send").disabled = false;
      });
      paint();
    })();
    </script>'''


def main():
    main_html = MAIN.replace("%EN%", json.dumps(EN, ensure_ascii=False)).replace("%HI%", json.dumps(HI, ensure_ascii=False))
    js = lambda v: json.dumps(v, ensure_ascii=False)
    t_en = "\n".join(f"      {k}: {js(v)}," for k, v in EN.items())
    t_hi = "\n".join(f"      {k}: {js(v)}," for k, v in HI.items())
    out = (TPL.replace("{{TITLE}}", EN["title"]).replace("{{DESC}}", "Report a mistake on SarkariChart").replace("{{MAIN}}", main_html)
           .replace("{{T_EN}}", t_en).replace("{{T_HI}}", t_hi).replace("{{SLUG}}", "report").replace("{{OGIMG}}", "https://sarkarichart.pages.dev/og.png").replace("{{URL}}", "https://sarkarichart.pages.dev/report/").replace("{{OGALT}}", "SarkariChart — report a mistake").replace("{{LAST}}", "null"))
    d = ROOT / "site/report"
    d.mkdir(parents=True, exist_ok=True)
    (d / "index.html").write_text(out, encoding="utf-8")
    print("wrote site/report/index.html")


if __name__ == "__main__":
    main()
