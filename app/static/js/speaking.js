/* Speech timers (D-075, D-077): the classroom runner's server-held timer, the bells, keyboard control, and the
   students' own practice timer. Bells as colour and sound: green while speaking, amber after the warning bell (one
   ring), red at time (two rings). The words on screen always name the phase, so colour is never the only signal. */
(function () {
  "use strict";
  if (window.__socSpeaking) return;
  window.__socSpeaking = true;

  function $(sel, root) { return (root || document).querySelector(sel); }
  function csrf() { var m = $('meta[name="csrf-token"]'); return m ? m.content : ""; }
  function say(text) { var a = document.getElementById("live-announcer"); if (a) { a.textContent = ""; setTimeout(function () { a.textContent = text; }, 30); } }
  function clock(rem) {
    var over = rem < 0, s = Math.round(Math.abs(rem));
    return (over ? "+" : "") + Math.floor(s / 60) + ":" + ("0" + (s % 60)).slice(-2);
  }

  // ---------- bells ----------
  var audio = null;
  function bellKey(btn) { return "soc-bell-" + (btn && btn.getAttribute("data-bell-default") === "off" ? "projector" : "teacher"); }
  function bellOn() {
    var btn = $("[data-bell-toggle]");
    if (!btn) return document.querySelector("[data-practice]") ? practiceBell() : false;
    var v = null;
    try { v = localStorage.getItem(bellKey(btn)); } catch (e) { /* private window */ }
    if (v === null) v = btn.getAttribute("data-bell-default") === "off" ? "0" : "1";
    return v === "1";
  }
  function practiceBell() { var c = $("[data-practice-bell]"); return !c || c.checked; }
  function syncBellButtons() {
    document.querySelectorAll("[data-bell-toggle]").forEach(function (b) {
      var on = bellOn();
      b.setAttribute("aria-pressed", on ? "true" : "false");
      b.textContent = on ? "Bell sound on" : "Bell sound off";
    });
  }
  function ring(n) {
    if (!bellOn()) return;
    try {
      audio = audio || new (window.AudioContext || window.webkitAudioContext)();
      if (audio.state === "suspended") audio.resume();
      for (var i = 0; i < n; i++) {
        var t = audio.currentTime + i * 0.45, o = audio.createOscillator(), g = audio.createGain();
        o.type = "sine"; o.frequency.value = 1318.5;
        g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(0.35, t + 0.01); g.gain.exponentialRampToValueAtTime(0.0001, t + 1.3);
        o.connect(g); g.connect(audio.destination); o.start(t); o.stop(t + 1.4);
      }
    } catch (e) { /* no audio: the colour and words still change */ }
  }
  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-bell-toggle]");
    if (b) {
      var next = bellOn() ? "0" : "1";
      try { localStorage.setItem(bellKey(b), next); } catch (err) { /* ignore */ }
      if (next === "1") { audio = audio || new (window.AudioContext || window.webkitAudioContext)(); if (audio.resume) audio.resume(); }
      syncBellButtons();
      return;
    }
    if (e.target.closest("[data-print]")) window.print();
  });

  // ---------- phases ----------
  var lastPhase = {};
  function phaseFor(state, rem, warn) {
    if (state === "idle") return "idle";
    if (rem <= 0) return "over";
    if (warn > 0 && rem <= warn) return "warn";
    return "go";
  }
  function show(el, rem, phase, key, quiet) {
    var out = $(".timer-value", el) || el;
    out.textContent = clock(rem);
    var stage = el.closest(".run-stage");
    if (stage) stage.setAttribute("data-phase", phase);
    var txt = stage && $(".run-phase-text", stage);
    if (txt) txt.textContent = (el.getAttribute("data-text-" + phase) || "") + (el.getAttribute("data-state") === "paused" ? " (paused)" : "");
    var prev = lastPhase[key];
    if (!quiet && prev !== undefined && prev !== phase) {
      if (phase === "warn") { ring(1); say(el.getAttribute("data-text-warn") || "Warning bell"); }
      else if (phase === "over" && prev !== "idle") { ring(2); say(el.getAttribute("data-text-over") || "Time"); }
    }
    lastPhase[key] = phase;
  }

  // Server-held timers: the teacher's page and the projector.
  function initRunTimers() {
    document.querySelectorAll(".run-timer[data-remaining]").forEach(function (el) {
      if (el._init) return;
      el._init = true;
      el._base = parseFloat(el.getAttribute("data-remaining"));
      el._at = Date.now() / 1000;
    });
  }
  setInterval(function () {
    initRunTimers();
    document.querySelectorAll(".run-timer[data-remaining]").forEach(function (el) {
      var state = el.getAttribute("data-state");
      var rem = state === "running" ? el._base - (Date.now() / 1000 - el._at) : el._base;
      show(el, rem, phaseFor(state, rem, parseFloat(el.getAttribute("data-warn") || "0")), el.getAttribute("data-step"));
    });
  }, 200);

  // ---------- teacher controls: buttons and keys ----------
  function control() { return $("[data-run-control]"); }
  function send(form) {
    var region = control();
    var body = new URLSearchParams(new FormData(form));
    // getAttribute: the form's own input named "action" shadows the form.action property.
    return fetch(form.getAttribute("action"), { method: "POST", body: body, credentials: "same-origin",
                                headers: { "X-CSRF-Token": csrf(), "X-Run-Control": "1" } })
      .then(function (r) {
        if (!r.ok) { say("That didn't work. Reload the page."); return; }
        if (region && window.htmx) htmx.trigger(region, "live-update");
      });
  }
  function act(action) {
    var region = control();
    if (!region) return;
    var f = region.querySelector('form[data-run-act] input[name="action"][value="' + action + '"]');
    if (f) { send(f.form); return; }
    // The pause/start button shows one at a time; "toggle" works from either.
    var any = region.querySelector("form[data-run-act]");
    if (!any) return;
    var tmp = any.cloneNode(true);
    tmp.querySelector('input[name="action"]').value = action;
    var arg = tmp.querySelector('input[name="arg"]'); if (arg) arg.remove();
    send(tmp);
  }
  document.addEventListener("submit", function (e) {
    var form = e.target;
    if (!form.matches || !form.matches("form[data-run-act]")) return;
    e.preventDefault();
    e.stopPropagation();
    if (audio === null && bellOn()) { try { audio = new (window.AudioContext || window.webkitAudioContext)(); } catch (err) { /* ignore */ } }
    send(form);
  }, true);
  document.addEventListener("keydown", function (e) {
    if (!control() || e.altKey || e.ctrlKey || e.metaKey) return;
    var t = e.target;
    if (t && t.closest && t.closest("input, textarea, select, button, a, summary, [contenteditable]")) return;
    var map = { " ": "toggle", "ArrowRight": "next", "PageDown": "next", "ArrowLeft": "prev", "PageUp": "prev" };
    var action = map[e.key];
    if (!action) return;
    e.preventDefault();
    act(action);
  });

  // ---------- setup form: show only the speaker places in use; fill from the class list ----------
  function shuffle(a) { for (var i = a.length - 1; i > 0; i--) { var j = Math.floor(Math.random() * (i + 1)); var x = a[i]; a[i] = a[j]; a[j] = x; } return a; }
  function roster() { var r = $("#roster-names"); try { return r ? JSON.parse(r.textContent) : []; } catch (e) { return []; } }
  function syncSlots() {
    var sel = $('[data-run-setup] select[name="speakers_per_side"]');
    if (!sel) return;
    var n = parseInt(sel.value, 10);
    document.querySelectorAll("[data-run-setup] [data-slot]").forEach(function (f) {
      f.hidden = parseInt(f.getAttribute("data-slot"), 10) > n;
    });
  }
  document.addEventListener("change", function (e) { if (e.target.matches('select[name="speakers_per_side"]')) syncSlots(); });
  document.addEventListener("click", function (e) {
    if (e.target.closest("[data-fill-teams]")) {
      var used = {}, inputs = [];
      document.querySelectorAll("[data-run-setup] [data-slot]:not([hidden]) input").forEach(function (i) { if (i.value.trim()) used[i.value.trim()] = 1; else inputs.push(i); });
      var pool = shuffle(roster().filter(function (n) { return !used[n]; }));
      inputs.forEach(function (i) { if (pool.length) i.value = pool.shift(); });
      say("Filled " + inputs.length + " places at random.");
    }
    if (e.target.closest("[data-fill-round]")) {
      var ta = $("#names");
      if (ta) { ta.value = shuffle(roster().slice()).join("\n"); say("The whole class, in random order."); }
    }
  });

  // ---------- students' practice timer (client-only: nothing is sent until they save) ----------
  // A practice runs: draw a topic -> think (counts down) -> speak (counts down into overtime) -> review.
  var P = null;
  function practiceRoot() { return $("[data-practice]"); }
  function pSet(stage) {
    var root = practiceRoot(); if (!root) return;
    root.setAttribute("data-stage", stage);
    root.querySelectorAll("[data-show-in]").forEach(function (el) {
      el.hidden = el.getAttribute("data-show-in").split(" ").indexOf(stage) < 0;
    });
  }
  function pTick() {
    if (!P) return;
    var el = $("[data-practice] .run-timer");
    if (!el) return;
    var now = Date.now() / 1000;
    var spent = P.elapsed + (P.running ? now - P.started : 0);
    var rem = P.seconds - spent;
    el.setAttribute("data-state", P.running ? "running" : (spent > 0 ? "paused" : "idle"));
    if (P.phase === "think" && rem <= 0 && P.running) { ring(1); startSpeech(); return; }
    show(el, rem, P.phase === "think" ? (rem <= 10 ? "warn" : "go") : phaseFor(P.running || spent > 0 ? "running" : "idle", rem, P.warn),
         "practice-" + P.phase, P.phase === "think");
    var out = $("[data-practice] [name=actual_seconds]");
    if (out && P.phase === "speak") out.value = Math.round(spent);
  }
  setInterval(pTick, 200);
  function setTimer(seconds, warn, phase, labels) {
    var el = $("[data-practice] .run-timer");
    P = { seconds: seconds, warn: warn, phase: phase, elapsed: 0, started: 0, running: false };
    if (el) for (var k in labels) el.setAttribute("data-text-" + k, labels[k]);
    var lbl = $("[data-practice] [data-phase-label]"); if (lbl) lbl.textContent = phase === "think" ? "Thinking time" : "Your speech";
    delete lastPhase["practice-" + phase];
  }
  function startThink() {
    var root = practiceRoot();
    var think = parseInt(($("[name=think_seconds]", root) || {}).value || "0", 10);
    if (!think) { startSpeech(); return; }
    setTimer(think, 10, "think", { idle: "Ready", go: "Plan: use the structure card", warn: "Nearly time to speak", over: "Speak now" });
    pSet("think"); P.running = true; P.started = Date.now() / 1000;
    var b = $("[data-practice-skip]"); if (b) b.focus();
  }
  function startSpeech() {
    var root = practiceRoot();
    var secs = parseInt(($("[name=target_seconds]", root) || {}).value || "120", 10);
    var warn = secs >= 120 ? 30 : 15;
    setTimer(secs, warn, "speak", { idle: "Ready", go: "Speaking", warn: "Warning bell: start wrapping up", over: "Time: finish now" });
    pSet("speak"); P.running = true; P.started = Date.now() / 1000;
    var b = $("[data-practice-stop]"); if (b) b.focus();
    say("Start speaking.");
  }
  function stopSpeech() {
    if (P && P.running) { P.elapsed += Date.now() / 1000 - P.started; P.running = false; }
    var spoken = $("[data-practice] [data-spoken]"); if (spoken && P) spoken.textContent = clock(P.elapsed);
    pTick();
    pSet("review");
    var h = $("[data-practice] #h-review"); if (h) { h.setAttribute("tabindex", "-1"); h.focus(); }
  }
  function showTopic(text, context) {
    var root = practiceRoot(); if (!root) return;
    root.querySelectorAll("[data-topic-shown]").forEach(function (el) { el.textContent = text; });
    var ctx = $("[data-topic-context]", root); if (ctx && context !== undefined) ctx.textContent = context;
  }
  function drawTopic() {
    var root = practiceRoot();
    var src = $("#practice-topics"); if (!src) return;
    var all; try { all = JSON.parse(src.textContent); } catch (e) { return; }
    var mode = (root.querySelector("[name=mode]:checked") || root.querySelector("[name=mode]") || {}).value || "impromptu";
    if (mode === "prepared") return;
    var level = ($("[name=level]", root) || {}).value || "any";
    var pool = (all[mode] || []).filter(function (t) { return mode !== "impromptu" || level === "any" || t.level === level || t.level === "any"; });
    if (!pool.length) return;
    var t = pool[Math.floor(Math.random() * pool.length)];
    var topic = $("[name=topic]", root);
    if (topic) topic.value = t.text;
    showTopic(t.text, t.context || "");
    say("Your topic: " + t.text);
  }
  document.addEventListener("click", function (e) {
    if (!practiceRoot()) return;
    if (e.target.closest("[data-practice-draw]")) { drawTopic(); }
    else if (e.target.closest("[data-practice-go]")) { var topic = $("[data-practice] [name=topic]"); if (topic && !topic.value.trim()) drawTopic(); audio = audio || (practiceBell() ? new (window.AudioContext || window.webkitAudioContext)() : null); startThink(); }
    else if (e.target.closest("[data-practice-skip]")) { startSpeech(); }
    else if (e.target.closest("[data-practice-stop]")) { stopSpeech(); }
    else if (e.target.closest("[data-practice-pause]")) {
      if (!P) return;
      if (P.running) { P.elapsed += Date.now() / 1000 - P.started; P.running = false; } else { P.started = Date.now() / 1000; P.running = true; }
      e.target.closest("[data-practice-pause]").textContent = P.running ? "Pause" : "Resume";
    }
    else if (e.target.closest("[data-practice-again]")) { P = null; pSet("setup"); }
  });
  function initPractice() {
    var root = practiceRoot();
    if (!root || root._init) return;
    root._init = true;
    pSet("setup");
    var topic = $("[name=topic]", root);
    if (topic && !topic.value) drawTopic(); else if (topic) showTopic(topic.value);
    syncStructure();
  }
  function syncStructure() {
    var sel = $("[data-structure-select]"); if (!sel) return;
    document.querySelectorAll("[data-structure]").forEach(function (c) { c.hidden = c.getAttribute("data-structure") !== sel.value; });
  }
  document.addEventListener("change", function (e) {
    if (e.target.matches("[data-structure-select]")) syncStructure();
    if (e.target.matches("[data-prepared-select]")) {
      var o = e.target.selectedOptions[0], root = practiceRoot();
      if (o && o.value) {
        var topic = $("[name=topic]", root); if (topic) topic.value = o.getAttribute("data-title");
        var tgt = $("[name=target_seconds]", root), secs = o.getAttribute("data-seconds");
        if (tgt && tgt.querySelector('option[value="' + secs + '"]')) tgt.value = secs;
        showTopic(o.getAttribute("data-title"));
      }
    }
  });
  document.addEventListener("input", function (e) { if (e.target.matches("[data-practice] [name=topic]")) showTopic(e.target.value); });
  document.addEventListener("keydown", function (e) {
    // Enter in the topic box would save an untimed practice; on the setup step it starts nothing instead.
    if (e.key === "Enter" && e.target.matches("[data-practice][data-stage=setup] input")) e.preventDefault();
  });

  // ---------- speech writer: live word count and speaking time ----------
  var WPM = 130;
  function countWords(s) { var m = (s || "").trim().match(/\S+/g); return m ? m.length : 0; }
  function syncWriter() {
    var root = $("[data-speech-writer]"); if (!root) return;
    var total = 0;
    root.querySelectorAll("textarea[data-section]").forEach(function (t) {
      var n = countWords(t.value); total += n;
      var out = root.querySelector('[data-count-for="' + t.id + '"]');
      if (out) out.textContent = n + " word" + (n === 1 ? "" : "s");
    });
    var secs = Math.round(total / WPM * 60);
    var target = parseInt((root.querySelector("[name=target_seconds]") || {}).value || "0", 10);
    var sum = root.querySelector("[data-speech-total]");
    if (sum) sum.textContent = total + " words · about " + clock(secs) + " at " + WPM + " words a minute" +
      (target ? (secs > target + 15 ? " · longer than your target of " + clock(target) : (secs < target * 0.75 ? " · shorter than your target of " + clock(target) : " · on target")) : "");
  }
  document.addEventListener("input", function (e) { if (e.target.closest("[data-speech-writer]")) syncWriter(); });
  document.addEventListener("change", function (e) { if (e.target.closest("[data-speech-writer]")) syncWriter(); });

  // ---------- rehearsal: one section at a time against the target time ----------
  function rehearse(dir) {
    var root = $("[data-rehearse]"); if (!root) return;
    var cards = root.querySelectorAll("[data-card]");
    var i = parseInt(root.getAttribute("data-at") || "0", 10) + dir;
    i = Math.max(0, Math.min(cards.length - 1, i));
    root.setAttribute("data-at", String(i));
    cards.forEach(function (c, k) { c.hidden = k !== i; });
    var pos = root.querySelector("[data-card-pos]"); if (pos) pos.textContent = "Card " + (i + 1) + " of " + cards.length;
  }
  document.addEventListener("click", function (e) {
    if (e.target.closest("[data-card-next]")) rehearse(1);
    if (e.target.closest("[data-card-prev]")) rehearse(-1);
  });
  document.addEventListener("keydown", function (e) {
    var root = $("[data-rehearse]"); if (!root || e.altKey || e.ctrlKey || e.metaKey) return;
    var t = e.target; if (t && t.closest && t.closest("input, textarea, select")) return;
    if (e.key === "ArrowRight" || e.key === "PageDown") { e.preventDefault(); rehearse(1); }
    if (e.key === "ArrowLeft" || e.key === "PageUp") { e.preventDefault(); rehearse(-1); }
  });

  function init() { syncBellButtons(); syncSlots(); initPractice(); syncWriter(); rehearse(0); }
  document.addEventListener("DOMContentLoaded", init);
  document.addEventListener("htmx:afterSettle", init);
  if (document.readyState !== "loading") init();
})();
