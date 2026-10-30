/* Live-room effects (D-089): a gavel, stage chimes, the division bell and breaking-news sting, title cards between
   stages, the vote reveal, raised placards and the news banner. A table-top game look, 1995 board-game style:
   felt, walnut and parchment, with smooth card flips and a stamp.

   Every sound is made here with the Web Audio API (no recordings, so nothing to licence) and has an on-screen
   caption, so no one misses what it says. Admin → Sound and motion decides where sound plays (the projector by
   default; or the projector and the chair's laptop; everywhere; or off, never 25 laptops at once by default) and whether things move; a computer set to reduce motion
   gets no animation regardless. Effects are triggered by watching [data-fx] markers in live regions: a change
   seen while the page is open plays once; the first look after loading only records the state. */
(function () {
  "use strict";
  var body = document.body;
  var ctx = null;

  function soundOn() {
    var mode = body.getAttribute("data-fx-sound") || "projector";
    if (mode === "off") return false;
    if (mode === "everywhere") return true;
    if (mode === "chair") return !!document.querySelector("[data-fx-room]");
    return !!document.querySelector('[data-fx-room="projector"]');
  }
  function motionOn() {
    if (body.getAttribute("data-fx-motion") === "off") return false;
    return !(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  }
  function audio(force) {
    if (!force && !soundOn()) return null;
    if (!ctx) {
      var AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) return null;
      try { ctx = new AC(); } catch (e) { return null; }
    }
    if (ctx.state === "suspended") ctx.resume();
    return ctx;
  }
  // Browsers only allow sound after someone clicks: any click on the page unlocks it.
  document.addEventListener("pointerdown", function () { if (soundOn()) audio(); syncUnlock(); }, true);
  function syncUnlock() {
    var b = document.querySelector("[data-fx-unlock]");
    if (b) b.hidden = !soundOn() || (ctx && ctx.state === "running");
  }

  // ---------- sounds ----------
  function noise(c, secs) {
    var buf = c.createBuffer(1, Math.max(1, Math.floor(c.sampleRate * secs)), c.sampleRate);
    var d = buf.getChannelData(0);
    for (var i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
    var src = c.createBufferSource();
    src.buffer = buf;
    return src;
  }
  function env(c, node, t, peak, decay) {
    var g = c.createGain();
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(peak, t + 0.004);
    g.gain.exponentialRampToValueAtTime(0.0001, t + decay);
    node.connect(g);
    g.connect(c.destination);
    return g;
  }
  function knock(c, t, strength) {
    // Hardwood on a sounding block: a short filtered crack over a falling low thump.
    var n = noise(c, 0.09), bp = c.createBiquadFilter();
    bp.type = "bandpass"; bp.frequency.value = 1150; bp.Q.value = 1.4;
    n.connect(bp); env(c, bp, t, 0.9 * strength, 0.085); n.start(t); n.stop(t + 0.1);
    var o = c.createOscillator();
    o.type = "sine"; o.frequency.setValueAtTime(190, t); o.frequency.exponentialRampToValueAtTime(70, t + 0.14);
    env(c, o, t, 0.85 * strength, 0.18); o.start(t); o.stop(t + 0.2);
  }
  function bell(c, t, freq, dur, peak) {
    [1, 2.0, 3.01, 4.2].forEach(function (m, i) {
      var o = c.createOscillator();
      o.type = "sine"; o.frequency.value = freq * m;
      env(c, o, t, peak / (i + 1.4), dur / (1 + i * 0.6)); o.start(t); o.stop(t + dur);
    });
  }
  var SOUNDS = {
    gavel: function (c, t, n) { for (var i = 0; i < (n || 2); i++) knock(c, t + i * 0.32, i === (n || 2) - 1 ? 1 : 0.8); return "Gavel"; },
    chime: function (c, t) { bell(c, t, 784, 1.6, 0.35); bell(c, t + 0.28, 1046.5, 2.2, 0.35); return "Chime: next stage"; },
    division: function (c, t) {
      // The division bell: an electric bell ringing twice.
      for (var r = 0; r < 2; r++) {
        var s = t + r * 1.0, o = c.createOscillator(), lfo = c.createOscillator(), lg = c.createGain(), bp = c.createBiquadFilter();
        o.type = "square"; o.frequency.value = 1650; lfo.frequency.value = 24; lg.gain.value = 0.5;
        lfo.connect(lg); bp.type = "bandpass"; bp.frequency.value = 1650; bp.Q.value = 3;
        var g = c.createGain(); g.gain.setValueAtTime(0.0001, s); g.gain.exponentialRampToValueAtTime(0.16, s + 0.02);
        g.gain.setValueAtTime(0.16, s + 0.7); g.gain.exponentialRampToValueAtTime(0.0001, s + 0.85);
        lg.connect(g.gain); o.connect(bp); bp.connect(g); g.connect(c.destination);
        o.start(s); lfo.start(s); o.stop(s + 0.9); lfo.stop(s + 0.9);
      }
      return "Division bell: voting is open";
    },
    news: function (c, t) {
      // A short broadcast sting: four rising notes, then a held chord.
      [523.25, 659.25, 783.99, 1046.5].forEach(function (f, i) {
        var o = c.createOscillator(); o.type = "triangle"; o.frequency.value = f;
        env(c, o, t + i * 0.12, 0.25, 0.25); o.start(t + i * 0.12); o.stop(t + i * 0.12 + 0.3);
      });
      [523.25, 659.25, 783.99].forEach(function (f) {
        var o = c.createOscillator(); o.type = "sawtooth"; o.frequency.value = f / 2;
        var lp = c.createBiquadFilter(); lp.type = "lowpass"; lp.frequency.value = 1400; o.connect(lp);
        env(c, lp, t + 0.5, 0.09, 1.4); o.start(t + 0.5); o.stop(t + 2);
      });
      return "Breaking news";
    },
    stamp: function (c, t) {
      var o = c.createOscillator(); o.type = "sine"; o.frequency.setValueAtTime(120, t); o.frequency.exponentialRampToValueAtTime(45, t + 0.2);
      env(c, o, t, 0.9, 0.25); o.start(t); o.stop(t + 0.3);
      var n = noise(c, 0.06), lp = c.createBiquadFilter(); lp.type = "lowpass"; lp.frequency.value = 700;
      n.connect(lp); env(c, lp, t, 0.6, 0.06); n.start(t); n.stop(t + 0.07);
      return "Stamp";
    },
    flip: function (c, t) {
      var n = noise(c, 0.03), hp = c.createBiquadFilter(); hp.type = "highpass"; hp.frequency.value = 2500;
      n.connect(hp); env(c, hp, t, 0.12, 0.03); n.start(t); n.stop(t + 0.04);
      return "";
    },
    placard: function (c, t) {
      var n = noise(c, 0.25), bp = c.createBiquadFilter(); bp.type = "bandpass"; bp.Q.value = 0.8;
      bp.frequency.setValueAtTime(400, t); bp.frequency.exponentialRampToValueAtTime(2200, t + 0.2);
      n.connect(bp); env(c, bp, t, 0.25, 0.22); n.start(t); n.stop(t + 0.26);
      return "Placard raised";
    }
  };
  function play(name, arg, force) {
    var label = "";
    var c = audio(force);
    if (c && SOUNDS[name]) label = SOUNDS[name](c, c.currentTime + 0.02, arg);
    else if (SOUNDS[name]) label = { gavel: "Gavel", chime: "Chime: next stage", division: "Division bell: voting is open",
                                      news: "Breaking news", stamp: "Stamp", placard: "Placard raised" }[name] || "";
    if (label && c) caption(label);
  }
  window.socFx = { play: play };

  // ---------- captions: every sound is also said on screen ----------
  function caption(text) {
    var box = document.getElementById("fx-caption");
    if (!box) {
      box = document.createElement("div");
      box.id = "fx-caption"; box.className = "fx-caption"; box.setAttribute("role", "status"); box.setAttribute("aria-live", "polite");
      body.appendChild(box);
    }
    box.textContent = "[" + text + "]";
    box.classList.add("show");
    clearTimeout(box._t);
    box._t = setTimeout(function () { box.classList.remove("show"); }, 3200);
  }

  // ---------- full-screen moments, one at a time ----------
  var queue = [], busy = false;
  function moment(build, ms) {
    queue.push({ build: build, ms: ms });
    if (!busy) next();
  }
  function next() {
    var item = queue.shift();
    if (!item) { busy = false; return; }
    busy = true;
    var layer = document.createElement("div");
    layer.className = "fx-layer" + (motionOn() ? " fx-moving" : "");
    layer.setAttribute("role", "dialog");
    layer.setAttribute("aria-live", "assertive");
    item.build(layer);
    var skip = document.createElement("button");
    skip.type = "button"; skip.className = "fx-skip"; skip.textContent = "Close";
    layer.appendChild(skip);
    body.appendChild(layer);
    var done = function () {
      if (!layer.parentNode) return;
      layer.classList.add("fx-out");
      setTimeout(function () { layer.remove(); next(); }, motionOn() ? 350 : 0);
    };
    skip.addEventListener("click", done);
    layer._timer = setTimeout(done, item.ms);
  }
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined && text !== null) e.textContent = text;
    return e;
  }

  // Title card between stages (projector): parchment on felt, crest, gold rule.
  function titleCard(eyebrow, title, line) {
    moment(function (layer) {
      var card = el("div", "fx-card fx-title");
      var crest = document.createElement("img"); crest.src = "/static/soc_crest.png"; crest.alt = ""; crest.className = "fx-crest";
      card.appendChild(crest);
      card.appendChild(el("p", "fx-eyebrow", eyebrow));
      card.appendChild(el("h2", "fx-big", title));
      card.appendChild(el("hr", "fx-rule"));
      if (line) card.appendChild(el("p", "fx-line", line));
      layer.appendChild(card);
    }, 3600);
  }

  // The vote reveal: placards flip in roll-call order, the tally fills, then the stamp lands with the gavel.
  function reveal(tpl) {
    var data = tpl.content ? tpl.content.cloneNode(true) : null;
    if (!data) return;
    var items = Array.prototype.slice.call(data.querySelectorAll("[data-fx-vote]"));
    var passed = tpl.getAttribute("data-passed") === "1";
    var step = motionOn() ? Math.max(70, Math.min(260, 4200 / Math.max(1, items.length))) : 0;
    moment(function (layer) {
      var board = el("div", "fx-card fx-reveal");
      board.appendChild(el("p", "fx-eyebrow", "The vote"));
      board.appendChild(el("h2", "fx-mid", tpl.getAttribute("data-title")));
      var grid = el("div", "fx-placards");
      items.forEach(function (it, i) {
        var p = el("div", "fx-placard v-" + it.getAttribute("data-fx-vote"));
        var inner = el("div", "fx-placard-inner");
        var front = el("div", "fx-face fx-front"); front.appendChild(el("span", "fx-iso", it.getAttribute("data-iso3")));
        var back = el("div", "fx-face fx-back");
        back.appendChild(el("span", "fx-country", it.getAttribute("data-name")));
        back.appendChild(el("span", "fx-vote", it.getAttribute("data-label")));
        inner.appendChild(front); inner.appendChild(back); p.appendChild(inner); grid.appendChild(p);
        setTimeout(function () { p.classList.add("flipped"); if (i % 2 === 0) play("flip"); }, 600 + i * step);
      });
      board.appendChild(grid);
      var tally = el("div", "fx-tally");
      ["yes", "no", "abstain"].forEach(function (k) {
        var n = +tpl.getAttribute("data-" + k), total = Math.max(1, items.length);
        var row = el("div", "fx-bar-row");
        row.appendChild(el("span", "fx-bar-label", { yes: "Yes", no: "No", abstain: "Abstain" }[k] + " " + n));
        var bar = el("span", "fx-bar fx-bar-" + k); bar.style.setProperty("--w", (100 * n / total) + "%");
        row.appendChild(bar); tally.appendChild(row);
      });
      board.appendChild(tally);
      var stamp = el("div", "fx-stamp " + (passed ? "fx-passed" : "fx-failed"), passed ? "Passed" : "Failed");
      board.appendChild(stamp);
      board.appendChild(el("p", "fx-line", tpl.getAttribute("data-summary")));
      layer.appendChild(board);
      var at = 900 + items.length * step;
      setTimeout(function () { tally.classList.add("filled"); }, at);
      setTimeout(function () { stamp.classList.add("landed"); play("stamp"); setTimeout(function () { play("gavel", 1); }, 250); }, at + 1100);
    }, 3200 + items.length * step + 2600);
  }

  // Breaking news (projector and every student screen): red band, ticker headline, the sting.
  function breaking(headline, bodyText, label) {
    play("news");
    moment(function (layer) {
      layer.classList.add("fx-news-layer");
      var card = el("div", "fx-card fx-news");
      card.appendChild(el("p", "fx-news-band", "Breaking news"));
      card.appendChild(el("h2", "fx-mid", headline));
      if (bodyText) card.appendChild(el("p", "fx-line", bodyText));
      if (label) card.appendChild(el("p", "fx-label", label));
      layer.appendChild(card);
    }, 7000);
  }

  // "Now speaking" (projector): a game card slides up along the bottom and away again. It never covers the timer.
  function nowSpeaking(name, line) {
    var old = document.querySelector(".fx-lower");
    if (old) old.remove();
    var card = el("div", "fx-lower" + (motionOn() ? " fx-moving" : ""));
    card.setAttribute("role", "status");
    card.appendChild(el("span", "fx-lower-tag", "Now speaking"));
    card.appendChild(el("span", "fx-lower-name", name));
    if (line) card.appendChild(el("span", "fx-lower-line", line));
    body.appendChild(card);
    play("flip");
    setTimeout(function () { card.classList.add("fx-out"); setTimeout(function () { card.remove(); }, 400); }, 4200);
  }

  // "Amendment adopted" (projector): the old words struck through, the new words typed in, then the stamp.
  function adopted(tpl) {
    var before = tpl.getAttribute("data-before") || "", after = tpl.getAttribute("data-after") || "";
    var friendly = tpl.getAttribute("data-friendly") === "1";
    var typeMs = motionOn() ? Math.min(2600, Math.max(600, after.length * 22)) : 0;
    moment(function (layer) {
      var card = el("div", "fx-card fx-adopt");
      card.appendChild(el("p", "fx-eyebrow", friendly ? "Friendly amendment" : "Amendment adopted"));
      card.appendChild(el("h2", "fx-mid", tpl.getAttribute("data-label")));
      if (before) { var del = el("p", "fx-old", before); card.appendChild(del); setTimeout(function () { del.classList.add("struck"); }, 500); }
      var ins = el("p", "fx-new", "");
      if (after) card.appendChild(ins);
      var stamp = el("div", "fx-stamp fx-passed", "Adopted");
      card.appendChild(stamp);
      layer.appendChild(card);
      var start = before ? 1300 : 500;
      if (after && typeMs) {
        var i = 0, step = typeMs / after.length;
        setTimeout(function tick() {
          i = Math.min(after.length, i + Math.max(1, Math.round(16 / step)));
          ins.textContent = after.slice(0, i);
          if (i < after.length) setTimeout(tick, 16);
        }, start);
      } else {
        ins.textContent = after;
      }
      setTimeout(function () { stamp.classList.add("landed"); play("stamp"); setTimeout(function () { play("gavel", 1); }, 250); }, start + typeMs + 300);
    }, 1300 + typeMs + 3200);
  }

  // ---------- watch the live markers ----------
  var seen = {};
  function store(k, v) { try { sessionStorage.setItem("fx:" + k, v); } catch (e) { /* ignore */ } }
  function stored(k) { try { return sessionStorage.getItem("fx:" + k); } catch (e) { return null; } }
  function changed(key, value) {
    if (value === null || value === undefined) return false;
    var before = key in seen ? seen[key] : stored(key);
    seen[key] = value;
    store(key, value);
    return before !== null && before !== undefined && before !== value;
  }
  function scan() {
    document.querySelectorAll("[data-fx]").forEach(function (m) {
      var k = m.getAttribute("data-fx");
      var room = !!document.querySelector('[data-fx-room="projector"]');      // big moments only on the projector
      if (changed(k + ":stage", m.getAttribute("data-fx-stage"))) {
        play("chime");
        if (room) titleCard(m.getAttribute("data-fx-committee") || "", m.getAttribute("data-fx-stage-name"), m.getAttribute("data-fx-stage-line"));
      }
      var div = m.getAttribute("data-fx-division");
      if (changed(k + ":division", div) && div && div !== "none") {
        play("division");
        if (room) titleCard("Division", "Voting is open", m.getAttribute("data-fx-division-title"));
      }
      if (changed(k + ":result", m.getAttribute("data-fx-result"))) {
        var tpl = document.getElementById("fx-reveal");
        if (room && tpl) reveal(tpl); else play("gavel", 1);
      }
      if (changed(k + ":gavel", m.getAttribute("data-fx-gavel"))) play("gavel", +(m.getAttribute("data-fx-gavel-n") || 2));
      var news = m.getAttribute("data-fx-news");
      if (changed(k + ":news", news) && news && news !== "none") {
        breaking(m.getAttribute("data-fx-news-headline"), m.getAttribute("data-fx-news-body"), m.getAttribute("data-fx-news-label"));
      }
      document.querySelectorAll("[data-fx-map]").forEach(function (map) {
        // The whip map flips its tiles once, when its phase changes (predictions in, voting, the reveal).
        if (changed(k + ":map", map.getAttribute("data-fx-map")) && motionOn()) {
          map.classList.add("animate");
          if (/:revealed$/.test(map.getAttribute("data-fx-map"))) play("flip");
        }
      });
      var spk = m.getAttribute("data-fx-speaker");
      if (changed(k + ":speaker", spk) && spk && spk !== "none" && room) {
        nowSpeaking(m.getAttribute("data-fx-speaker-name"), m.getAttribute("data-fx-speaker-line"));
      }
      var adopt = m.getAttribute("data-fx-adopted");
      if (changed(k + ":adopted", adopt) && adopt && adopt !== "none") {
        var at = document.getElementById("fx-adopt");
        if (room && at) adopted(at); else play("gavel", 1);
      }
      var pc = m.getAttribute("data-fx-placards");
      var before = seen[k + ":placards"];
      if (changed(k + ":placards", pc) && +pc > +(before || 0)) play("placard");
    });
    syncUnlock();
  }
  document.addEventListener("htmx:afterSwap", scan);
  document.addEventListener("htmx:load", scan);
  scan();

  document.addEventListener("click", function (e) {
    var b = e.target.closest && e.target.closest("[data-fx-unlock]");
    if (b) { audio(); play("gavel", 1); syncUnlock(); }
    var g = e.target.closest && e.target.closest("[data-fx-test]");
    if (g) play(g.getAttribute("data-fx-test"), null, true);           // "Try the gavel" in Admin plays anywhere
  });
})();
