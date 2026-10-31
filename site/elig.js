/* "Am I eligible?" — the reader's date of birth, category and qualification are kept only in this browser
   (localStorage "sc-me"); nothing is sent anywhere. Each job's rules come from its official notice (scripts/elig.py).
   Homepage: open jobs that fit get a small ✓. Notice page: a direct answer in the At a glance box. */
(function () {
  const KEY = "sc-me";
  const LV = { "10th": 1, "12th": 2, iti: 2, diploma: 3, graduate: 4, postgraduate: 5 };
  const QN = { "10th": ["10th pass", "10वीं पास"], "12th": ["12th pass", "12वीं पास"], iti: ["ITI", "आईटीआई"], diploma: ["Diploma", "डिप्लोमा"],
               graduate: ["Graduate", "स्नातक"], postgraduate: ["Post graduate", "स्नातकोत्तर"] };
  const CATS = ["GEN", "OBC", "SC", "ST", "EWS"];
  const CN = { GEN: ["General", "सामान्य"], OBC: ["OBC", "ओबीसी"], SC: ["SC", "एससी"], ST: ["ST", "एसटी"], EWS: ["EWS", "ईडब्ल्यूएस"] };
  const hi = () => document.documentElement.lang === "hi";
  const L = (en, h) => (hi() ? h : en);
  const MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const MONH = ["जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर", "अक्तूबर", "नवंबर", "दिसंबर"];
  const fd = iso => { const [y, m, d] = iso.split("-").map(Number); return hi() ? `${d} ${MONH[m - 1]} ${y}` : `${d} ${MON[m - 1]} ${y}`; };

  // styles live here so the homepage and every notice page look the same (site colour tokens)
  const css = document.createElement("style");
  css.textContent = `
    .eligbtn { all: unset; cursor: pointer; color: var(--grey); text-decoration: underline; text-underline-offset: 5px; text-decoration-thickness: 1px; white-space: nowrap; padding: 2px 0; }
    .eligbtn:hover { color: var(--ink); }
    .eok { display: inline-block; margin-right: 6px; color: var(--calm, #2E7D4F); font-weight: 600; }
    #elig { display: flex; flex-wrap: wrap; gap: 2px 10px; align-items: baseline; }
    #elig .er.yes { color: var(--calm, #2E7D4F); font-weight: 600; } #elig .er.no { color: var(--hot, #B23A1A); font-weight: 600; } #elig .er.maybe { font-weight: 600; }
    #elig small { display: block; width: 100%; font-size: .92em; }
    #elig .elink { all: unset; cursor: pointer; color: var(--ink); text-decoration: underline; text-underline-offset: 5px; text-decoration-thickness: 1px; }
    .eligdlg { border: 1px solid var(--line); border-radius: 10px; padding: 22px 24px; background: var(--page); color: var(--ink); max-width: 24rem; width: calc(100% - 32px); }
    .eligdlg::backdrop { background: rgba(0,0,0,.35); }
    .eligdlg form { position: relative; }
    .eligdlg .x { all: unset; cursor: pointer; position: absolute; top: -10px; right: -10px; width: 32px; height: 32px; display: grid; place-items: center; font-size: 22px; color: var(--grey); border-radius: 6px; }
    .eligdlg .x:hover { color: var(--ink); background: var(--soft); }
    .eligdlg h2 { font-size: 1.25rem; font-weight: 700; margin: 0 0 6px; padding-right: 28px; }
    .eligdlg p.g { margin: 0 0 16px; color: var(--grey); font-size: .95rem; }
    .eligdlg label { display: grid; gap: 4px; margin-bottom: 14px; color: var(--grey); }
    .eligdlg label.ck { display: flex; gap: 8px; align-items: center; color: var(--ink); }
    .eligdlg input[type=date], .eligdlg select { font: inherit; color: var(--ink); background: var(--page); border: 1px solid var(--line); border-radius: 6px; padding: 7px 9px; }
    .eligdlg .btns { display: flex; gap: 18px; margin: 6px 0 0; }
    .eligdlg .btns button { all: unset; cursor: pointer; text-decoration: underline; text-underline-offset: 5px; text-decoration-thickness: 1px; color: var(--ink); }
    .eligdlg .btns button.g { color: var(--grey); }`;
  document.head.appendChild(css);

  function load() { try { const v = JSON.parse(localStorage.getItem(KEY) || "null"); return v && v.dob ? v : null; } catch (e) { return null; } }
  function save(v) { try { v ? localStorage.setItem(KEY, JSON.stringify(v)) : localStorage.removeItem(KEY); } catch (e) {} }
  function ageOn(dob, on) {
    const [y1, m1, d1] = dob.split("-").map(Number), [y2, m2, d2] = on.split("-").map(Number);
    return y2 - y1 - ((m2 < m1 || (m2 === m1 && d2 < d1)) ? 1 : 0);
  }

  // e = {min, max, on, relax:{OBC:3…}, qual, dom}; me = {dob, cat, pwd, qual}
  // → {s: "yes"|"no"|"maybe", why: text}
  function check(e, me) {
    if (!e || !me) return null;
    const notes = [];
    let s = "yes";
    if (e.qual && me.qual) {
      const need = LV[e.qual], have = LV[me.qual];
      if (have < need) return { s: "no", why: L(`Needs ${QN[e.qual][0]} (you: ${QN[me.qual][0]})`, `${QN[e.qual][1]} चाहिए (आप: ${QN[me.qual][1]})`) };
      if ((e.qual === "iti" || e.qual === "diploma") && me.qual !== e.qual && have <= LV.diploma) {
        s = "maybe"; notes.push(L(`needs ${QN[e.qual][0]}`, `${QN[e.qual][1]} चाहिए`));
      }
    } else if (e.qual) { s = "maybe"; }
    if (e.min || e.max) {
      if (!e.on) { s = "maybe"; notes.push(L("age date not given in the notice", "सूचना में आयु की तिथि नहीं दी गई")); }
      else {
        const a = ageOn(me.dob, e.on);
        let extra = 0, known = true;
        if (me.cat && me.cat !== "GEN") { if (e.relax && me.cat in e.relax) extra += e.relax[me.cat]; else known = false; }
        if (me.pwd && e.relax && e.relax.PwD) extra += e.relax.PwD;
        const top = e.max ? e.max + extra : null;
        const range = L(`limit ${e.min || "–"}–${e.max || "–"}${extra ? ` +${extra} ${me.cat !== "GEN" ? me.cat : ""}${me.pwd && e.relax && e.relax.PwD ? " PwD" : ""}` : ""}`,
                        `सीमा ${e.min || "–"}–${e.max || "–"}${extra ? ` +${extra}` : ""}`);
        const youAre = L(`You are ${a} on ${fd(e.on)}`, `${fd(e.on)} को आपकी आयु ${a} वर्ष`);
        if (e.min && a < e.min) return { s: "no", why: L(`${youAre}: under the minimum age (${range})`, `${youAre}: न्यूनतम आयु से कम (${range})`) };
        if (top && a > top) {
          if (!known) { s = "maybe"; notes.push(L(`${youAre}, over the general limit (${range}); ${me.cat} relaxation not listed: check the notice`, `${youAre}, सामान्य सीमा से अधिक (${range}); ${CN[me.cat][1]} छूट की जानकारी सूचना में देखें`)); }
          else return { s: "no", why: L(`${youAre}: over the age limit (${range})`, `${youAre}: आयु सीमा से अधिक (${range})`) };
        } else notes.unshift(L(`${youAre} (${range})`, `${youAre} (${range})`));
      }
    } else if (s === "yes") { s = "maybe"; notes.push(L("age limit not given in the notice", "सूचना में आयु सीमा नहीं दी गई")); }
    if (e.dom) notes.push(L(`only for residents of ${e.dom}`, `केवल ${e.dom} के निवासियों के लिए`));
    return { s, why: notes.join(" · ") };
  }

  // ---------- the small form (one native dialog, shared by every page) ----------
  let dlg;
  function form(onDone) {
    if (!dlg) {
      dlg = document.createElement("dialog");
      dlg.className = "eligdlg";
      document.body.appendChild(dlg);
      dlg.addEventListener("click", ev => {
        if (ev.target !== dlg) return;            // clicks inside the form land on its children
        const r = dlg.getBoundingClientRect();
        if (ev.clientX < r.left || ev.clientX > r.right || ev.clientY < r.top || ev.clientY > r.bottom) dlg.close("cancel");
      });
    }
    dlg.returnValue = "";
    const me = load() || {};
    dlg.innerHTML = `<form method="dialog">
      <button value="cancel" class="x" formnovalidate aria-label="${L("Close", "बंद करें")}">×</button>
      <h2>${L("Am I eligible?", "क्या मैं योग्य हूँ?")}</h2>
      <p class="g">${L("Saved only on this device. We check age and qualification against each official notice.", "सिर्फ़ इसी डिवाइस पर सेव होता है। हम हर आधिकारिक सूचना से आयु और योग्यता मिलाते हैं।")}</p>
      <label>${L("Date of birth", "जन्म तिथि")}<input type="date" name="dob" required value="${me.dob || ""}" min="1950-01-01" max="2015-12-31"></label>
      <label>${L("Category", "श्रेणी")}<select name="cat">${CATS.map(c => `<option value="${c}"${me.cat === c ? " selected" : ""}>${L(CN[c][0], CN[c][1])}</option>`).join("")}</select></label>
      <label>${L("Highest qualification", "सबसे ऊँची योग्यता")}<select name="qual">${Object.keys(QN).map(q => `<option value="${q}"${me.qual === q ? " selected" : ""}>${L(QN[q][0], QN[q][1])}</option>`).join("")}</select></label>
      <label class="ck"><input type="checkbox" name="pwd"${me.pwd ? " checked" : ""}> ${L("Person with disability (PwD)", "दिव्यांग (PwD)")}</label>
      <p class="btns"><button value="save">${L("Save", "सेव करें")}</button>${me.dob ? `<button value="clear" class="g" formnovalidate>${L("Forget me", "मेरी जानकारी हटाएँ")}</button>` : ""}<button value="cancel" class="g" formnovalidate>${L("Cancel", "रद्द करें")}</button></p>
    </form>`;
    dlg.onclose = () => {
      if (dlg.returnValue === "save") {
        const f = dlg.querySelector("form");
        if (!f.dob.value) return;
        save({ dob: f.dob.value, cat: f.cat.value, qual: f.qual.value, pwd: f.pwd.checked });
      } else if (dlg.returnValue === "clear") save(null);
      onDone && onDone();
    };
    dlg.showModal();
  }

  // ---------- homepage: ✓ on open jobs that fit, and the link that opens the form ----------
  function markList() {
    const me = load(), btn = document.getElementById("eligBtn");
    let n = 0;
    document.querySelectorAll("#list li.lr[data-e]").forEach(li => {
      const old = li.querySelector(".eok"); if (old) old.remove();
      if (!me) return;
      let e; try { e = JSON.parse(li.dataset.e); } catch (x) { return; }
      const r = check(e, me);
      if (r && r.s === "yes") {
        n++;
        const t = li.querySelector(".t");
        if (t) t.insertAdjacentHTML("afterbegin", `<span class="eok" title="${L("You are eligible: ", "आप योग्य हैं: ")}${r.why.replace(/"/g, "&quot;")}" aria-label="${L("You are eligible", "आप योग्य हैं")}">✓</span>`);
      }
    });
    if (btn) btn.textContent = me ? L("Eligibility: on · edit", "योग्यता: चालू · बदलें") : L("Am I eligible?", "क्या मैं योग्य हूँ?");
  }
  function initHome() {
    const btn = document.getElementById("eligBtn"), list = document.getElementById("list");
    if (!list) return;
    if (btn) btn.addEventListener("click", () => form(markList));
    // the list is re-drawn on every tab / search change: mark again (the ✓ goes inside rows, so this does not loop)
    new MutationObserver(markList).observe(list, { childList: true });
    new MutationObserver(markList).observe(document.documentElement, { attributes: true, attributeFilter: ["lang"] });
    markList();
  }

  // ---------- notice page: answer in the At a glance box ----------
  function initNotice() {
    const box = document.getElementById("elig");
    if (!box) return;
    let e; try { e = JSON.parse(box.dataset.e); } catch (x) { return; }
    function paint() {
      const me = load();
      if (!me) { box.innerHTML = `<button type="button" class="elink">${L("Check with your date of birth →", "अपनी जन्म तिथि से जाँचें →")}</button>`; }
      else {
        const r = check(e, me);
        const head = { yes: L("✓ Yes, you are eligible", "✓ हाँ, आप योग्य हैं"), no: L("✗ Not eligible", "✗ योग्य नहीं"), maybe: L("Probably — check the notice", "शायद — सूचना देखें") }[r.s];
        box.innerHTML = `<span class="er ${r.s}">${head}</span>${r.why ? `<small class="g">${r.why}</small>` : ""}<button type="button" class="elink">${L("edit", "बदलें")}</button>`;
      }
      const b = box.querySelector(".elink"); if (b) b.addEventListener("click", () => form(paint));
    }
    new MutationObserver(paint).observe(document.documentElement, { attributes: true, attributeFilter: ["lang"] });
    paint();
  }
  window.scElig = { check, load, form };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", () => { initHome(); initNotice(); });
  else { initHome(); initNotice(); }
})();
