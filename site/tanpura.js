/* Calm music, off by default: a tanpura drone made in the browser (nothing is downloaded, no copyright).
   A small note button in the header starts and stops it. If a visitor turned it on, it starts again on their first
   tap or key press on the next page (browsers never allow sound before that). */
(function () {
  var nav = document.querySelector(".top .nav-r"), theme = document.getElementById("theme");
  if (!nav || !(window.AudioContext || window.webkitAudioContext)) return;
  var KEY = "sc-music", ctx = null, master = null, timer = null, on = false, next = 0;
  var NOTE = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M9 18V5l11-2v13" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><circle cx="6.5" cy="18" r="2.5" stroke="currentColor" stroke-width="1.5"/><circle cx="17.5" cy="16" r="2.5" stroke="currentColor" stroke-width="1.5"/></svg>';
  var MUTE = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M9 18V5l11-2v13" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" opacity=".45"/><circle cx="6.5" cy="18" r="2.5" stroke="currentColor" stroke-width="1.5" opacity=".45"/><circle cx="17.5" cy="16" r="2.5" stroke="currentColor" stroke-width="1.5" opacity=".45"/><path d="M3 3l18 18" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>';
  var btn = document.createElement("button");
  btn.type = "button"; btn.id = "music"; btn.className = "themeb";
  nav.insertBefore(btn, theme || null);
  function hi() { return document.documentElement.lang === "hi"; }
  function paint() {
    btn.innerHTML = on ? NOTE : MUTE;
    var l = on ? (hi() ? "संगीत बंद करें" : "Turn off calm music") : (hi() ? "शांत संगीत चलाएँ" : "Play calm music");
    btn.setAttribute("aria-label", l); btn.title = l; btn.setAttribute("aria-pressed", String(on));
  }
  function setup() {
    ctx = new (window.AudioContext || window.webkitAudioContext)();
    master = ctx.createGain(); master.gain.value = 0;
    var verb = ctx.createConvolver(), len = ctx.sampleRate * 3.2, ir = ctx.createBuffer(2, len, ctx.sampleRate);
    for (var ch = 0; ch < 2; ch++) { var d = ir.getChannelData(ch); for (var i = 0; i < len; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / len, 2.6); }
    verb.buffer = ir;
    var wet = ctx.createGain(); wet.gain.value = 0.55;
    master.connect(ctx.destination); master.connect(verb); verb.connect(wet); wet.connect(ctx.destination);
  }
  // one string: rich harmonics (the tanpura's buzzing "jawari"), a filter that opens and slowly closes, a long fade
  var real = new Float32Array(24), imag = new Float32Array(24);
  for (var h = 1; h < 24; h++) imag[h] = (h % 2 ? 1 : 0.8) / Math.pow(h, 0.85);
  function pluck(f, t, v) {
    var wave = ctx.createPeriodicWave(real, imag), g = ctx.createGain(), lp = ctx.createBiquadFilter();
    lp.type = "lowpass"; lp.Q.value = 2.2;
    lp.frequency.setValueAtTime(f * 3, t); lp.frequency.linearRampToValueAtTime(f * 14, t + 0.9); lp.frequency.exponentialRampToValueAtTime(f * 2.2, t + 7);
    g.gain.setValueAtTime(0.0001, t); g.gain.linearRampToValueAtTime(v, t + 0.04); g.gain.exponentialRampToValueAtTime(0.0001, t + 7.5);
    [-2.5, 2.5].forEach(function (cents) {
      var o = ctx.createOscillator(); o.setPeriodicWave(wave); o.frequency.value = f; o.detune.value = cents;
      o.connect(lp); o.start(t); o.stop(t + 7.6);
    });
    lp.connect(g); g.connect(master);
  }
  var SA = 130.81;   // C3, a comfortable tanpura pitch
  var CYCLE = [[SA * 0.75, 0.16], [SA, 0.13], [SA, 0.13], [SA / 2, 0.2]];   // Pa, Sa, Sa, low Sa
  function schedule() {
    while (next < ctx.currentTime + 1.5) {
      CYCLE.forEach(function (n, k) { pluck(n[0], next + k * 1.25, n[1]); });
      next += CYCLE.length * 1.25 + 0.3;
    }
  }
  function start() {
    if (!ctx) setup();
    ctx.resume();
    next = Math.max(next, ctx.currentTime + 0.1);
    master.gain.cancelScheduledValues(ctx.currentTime);
    master.gain.setValueAtTime(master.gain.value, ctx.currentTime);
    master.gain.linearRampToValueAtTime(0.12, ctx.currentTime + 2.5);
    schedule(); clearInterval(timer); timer = setInterval(schedule, 500);
  }
  function stop() {
    if (!ctx) return;
    master.gain.cancelScheduledValues(ctx.currentTime);
    master.gain.setValueAtTime(master.gain.value, ctx.currentTime);
    master.gain.linearRampToValueAtTime(0, ctx.currentTime + 0.8);
    clearInterval(timer); timer = null;
    setTimeout(function () { if (!on && ctx) ctx.suspend(); }, 900);
  }
  function set(v) { on = v; try { localStorage.setItem(KEY, v ? "on" : "off"); } catch (e) {} paint(); v ? start() : stop(); }
  btn.addEventListener("click", function () { set(!on); });
  document.addEventListener("visibilitychange", function () { if (!ctx || !on) return; document.hidden ? ctx.suspend() : ctx.resume(); });
  new MutationObserver(paint).observe(document.documentElement, { attributes: true, attributeFilter: ["lang"] });
  paint();
  // turned on earlier: start again on the first tap or key press on this page
  var want = false; try { want = localStorage.getItem(KEY) === "on"; } catch (e) {}
  if (want) {
    var go = function (e) {
      if (e && e.target && e.target.closest && e.target.closest("#music")) return;   // the button handles itself
      ["pointerdown", "keydown"].forEach(function (ev) { removeEventListener(ev, go, true); });
      if (!on) { on = true; paint(); start(); }
    };
    ["pointerdown", "keydown"].forEach(function (ev) { addEventListener(ev, go, true); });
  }
})();
