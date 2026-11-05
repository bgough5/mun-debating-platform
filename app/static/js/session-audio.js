/* The Session's sound (D-101): effects, a quiet music bed and the murmur of the room, all made here with the Web
   Audio API (no recordings, nothing to licence). Everything is off until the player turns it on in Settings, and
   every sound effect is also said in a caption. Settings live in this browser only (localStorage), and a browser
   that blocks storage simply starts with everything off.

   window.socSession.audio: play(name), music(on), murmur(on), settings(), set(key, value), caption(text). */
(function () {
  "use strict";
  var KEY = "soc-session-settings";
  var DEFAULTS = { sound: false, music: false, murmur: false, motion: "auto", text: "normal", timer: true, tips: true, talk: true };
  var ctx = null, master = null, musicBus = null, musicTimer = null, murmurNode = null;

  function settings() {
    var s = {};
    try { s = JSON.parse(window.localStorage.getItem(KEY) || "{}") || {}; } catch (e) { s = {}; }
    var out = {};
    Object.keys(DEFAULTS).forEach(function (k) { out[k] = k in s ? s[k] : DEFAULTS[k]; });
    return out;
  }
  function set(k, v) {
    var s = settings(); s[k] = v;
    try { window.localStorage.setItem(KEY, JSON.stringify(s)); } catch (e) { /* storage blocked: it lasts this page only */ }
    apply(s);
    return s;
  }
  function motionOn(s) {
    s = s || settings();
    if (s.motion === "off") return false;
    if (s.motion === "on") return true;
    return !(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  }
  function apply(s) {
    document.body.classList.toggle("s-nomotion", !motionOn(s));
    document.body.classList.toggle("s-large", s.text === "large");
    music(!!s.music);
    murmur(!!s.murmur);
  }

  function audio() {
    if (!ctx) {
      var AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) return null;
      try { ctx = new AC(); } catch (e) { return null; }
      master = ctx.createGain(); master.gain.value = 0.9; master.connect(ctx.destination);
    }
    if (ctx.state === "suspended") ctx.resume();
    return ctx;
  }
  // Browsers allow sound only after a click: the first click on the page starts whatever is switched on.
  document.addEventListener("pointerdown", function () { var s = settings(); if (s.sound || s.music || s.murmur) { audio(); apply(s); } }, true);

  // ---------- building blocks ----------
  function noise(c, secs) {
    var buf = c.createBuffer(1, Math.max(1, Math.floor(c.sampleRate * secs)), c.sampleRate), d = buf.getChannelData(0);
    for (var i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
    var src = c.createBufferSource(); src.buffer = buf; return src;
  }
  function env(c, node, t, peak, decay, out) {
    var g = c.createGain();
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(peak, t + 0.005);
    g.gain.exponentialRampToValueAtTime(0.0001, t + decay);
    node.connect(g); g.connect(out || master);
    return g;
  }
  function tone(c, type, f, t, peak, decay, out) {
    var o = c.createOscillator(); o.type = type; o.frequency.setValueAtTime(f, t);
    env(c, o, t, peak, decay, out); o.start(t); o.stop(t + decay + 0.05); return o;
  }
  function knock(c, t, s) {
    var n = noise(c, 0.09), bp = c.createBiquadFilter(); bp.type = "bandpass"; bp.frequency.value = 1150; bp.Q.value = 1.4;
    n.connect(bp); env(c, bp, t, 0.9 * s, 0.085); n.start(t); n.stop(t + 0.1);
    var o = c.createOscillator(); o.type = "sine"; o.frequency.setValueAtTime(190, t); o.frequency.exponentialRampToValueAtTime(70, t + 0.14);
    env(c, o, t, 0.85 * s, 0.18); o.start(t); o.stop(t + 0.2);
  }
  function bell(c, t, f, dur, peak) {
    [1, 2.0, 3.01, 4.2].forEach(function (m, i) { tone(c, "sine", f * m, t, peak / (i + 1.4), dur / (1 + i * 0.6)); });
  }
  function brass(c, t, freqs, dur, peak) {
    freqs.forEach(function (f) {
      var o = c.createOscillator(); o.type = "sawtooth"; o.frequency.value = f;
      var lp = c.createBiquadFilter(); lp.type = "lowpass"; lp.frequency.setValueAtTime(600, t); lp.frequency.linearRampToValueAtTime(2400, t + 0.12);
      o.connect(lp);
      var g = c.createGain(); g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(peak, t + 0.06);
      g.gain.setValueAtTime(peak, t + dur * 0.7); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
      lp.connect(g); g.connect(master); o.start(t); o.stop(t + dur + 0.05);
    });
  }

  // ---------- effects ----------
  var SOUNDS = {
    gavel: function (c, t) { knock(c, t, 0.8); knock(c, t + 0.32, 1); return "Gavel"; },
    chime: function (c, t) { bell(c, t, 784, 1.6, 0.3); bell(c, t + 0.28, 1046.5, 2.2, 0.3); return "Chime"; },
    stamp: function (c, t) {
      var o = c.createOscillator(); o.type = "sine"; o.frequency.setValueAtTime(120, t); o.frequency.exponentialRampToValueAtTime(45, t + 0.2);
      env(c, o, t, 0.9, 0.25); o.start(t); o.stop(t + 0.3);
      var n = noise(c, 0.06), lp = c.createBiquadFilter(); lp.type = "lowpass"; lp.frequency.value = 700; n.connect(lp); env(c, lp, t, 0.6, 0.06); n.start(t); n.stop(t + 0.07);
      return "Stamp";
    },
    flip: function (c, t) {
      var n = noise(c, 0.05), hp = c.createBiquadFilter(); hp.type = "highpass"; hp.frequency.value = 2400; n.connect(hp); env(c, hp, t, 0.16, 0.05); n.start(t); n.stop(t + 0.06);
      return "Card turned";
    },
    paper: function (c, t) {
      var n = noise(c, 0.35), bp = c.createBiquadFilter(); bp.type = "bandpass"; bp.Q.value = 0.7;
      bp.frequency.setValueAtTime(900, t); bp.frequency.exponentialRampToValueAtTime(3200, t + 0.3); n.connect(bp); env(c, bp, t, 0.18, 0.32); n.start(t); n.stop(t + 0.36);
      return "Paper";
    },
    coin: function (c, t) { tone(c, "sine", 1318.5, t, 0.22, 0.25); tone(c, "sine", 1760, t + 0.07, 0.2, 0.5); return "Influence"; },
    tick: function (c, t) { tone(c, "square", 1800, t, 0.05, 0.03); return ""; },
    sweep: function (c, t) {
      var n = noise(c, 0.9), bp = c.createBiquadFilter(); bp.type = "bandpass"; bp.Q.value = 1.1;
      bp.frequency.setValueAtTime(300, t); bp.frequency.exponentialRampToValueAtTime(3500, t + 0.8); n.connect(bp); env(c, bp, t, 0.22, 0.85); n.start(t); n.stop(t + 0.9);
      return "The vote sweeps the map";
    },
    news: function (c, t) {
      [523.25, 659.25, 783.99, 1046.5].forEach(function (f, i) { tone(c, "triangle", f, t + i * 0.12, 0.22, 0.25); });
      return "Breaking news";
    },
    fanfare: function (c, t) { brass(c, t, [293.66, 369.99, 440], 0.35, 0.07); brass(c, t + 0.38, [293.66, 369.99, 440, 587.33], 1.4, 0.08); return "Fanfare"; },
    sting: function (c, t) { brass(c, t, [293.66, 349.23], 0.4, 0.07); brass(c, t + 0.42, [277.18, 329.63], 1.2, 0.07); return "The vote is lost"; },
    open: function (c, t) { brass(c, t, [146.83, 220, 293.66], 2.2, 0.06); bell(c, t + 0.4, 587.33, 2.4, 0.18); return "The session opens"; }
  };
  function play(name) {
    var s = settings();
    if (!s.sound || !SOUNDS[name]) return;
    var c = audio(); if (!c) return;
    var label = SOUNDS[name](c, c.currentTime + 0.02);
    if (label) caption(label);
  }

  // ---------- music: a slow war-room pad in D minor (i - VI - III - VII), with a soft drum every other bar ----------
  var CHORDS = [[146.83, 174.61, 220.0], [116.54, 146.83, 174.61], [174.61, 220.0, 261.63], [130.81, 164.81, 196.0]];
  function music(on) {
    if (!on) {
      if (musicTimer) { clearInterval(musicTimer); musicTimer = null; }
      if (musicBus) { var mb = musicBus; musicBus = null; try { mb.gain.setTargetAtTime(0.0001, ctx.currentTime, 0.8); setTimeout(function () { mb.disconnect(); }, 3000); } catch (e) { /* none */ } }
      return;
    }
    if (musicBus) return;
    var c = audio(); if (!c) return;
    musicBus = c.createGain(); musicBus.gain.value = 0.0001; musicBus.connect(master);
    musicBus.gain.setTargetAtTime(0.55, c.currentTime, 2.5);
    var lp = c.createBiquadFilter(); lp.type = "lowpass"; lp.frequency.value = 900; lp.connect(musicBus);
    var i = 0, BAR = 8;
    function bar() {
      if (!musicBus) return;
      var t = c.currentTime + 0.05, ch = CHORDS[i % CHORDS.length];
      ch.forEach(function (f, k) {
        [-4, 4].forEach(function (det) {
          var o = c.createOscillator(); o.type = k === 0 ? "triangle" : "sawtooth"; o.frequency.value = f; o.detune.value = det;
          var g = c.createGain(); g.gain.setValueAtTime(0.0001, t); g.gain.linearRampToValueAtTime(0.022, t + 2.6);
          g.gain.setValueAtTime(0.022, t + BAR - 2.2); g.gain.linearRampToValueAtTime(0.0001, t + BAR + 0.6);
          o.connect(g); g.connect(lp); o.start(t); o.stop(t + BAR + 0.8);
        });
      });
      var d = c.createOscillator(); d.type = "sine"; d.frequency.value = 73.42;            // the low D underneath everything
      var dg = c.createGain(); dg.gain.setValueAtTime(0.0001, t); dg.gain.linearRampToValueAtTime(0.05, t + 3); dg.gain.linearRampToValueAtTime(0.0001, t + BAR + 0.5);
      d.connect(dg); dg.connect(musicBus); d.start(t); d.stop(t + BAR + 0.6);
      if (i % 2 === 0) {                                                                 // a distant timpani
        var o2 = c.createOscillator(); o2.type = "sine"; o2.frequency.setValueAtTime(98, t + 4); o2.frequency.exponentialRampToValueAtTime(70, t + 5);
        env(c, o2, t + 4, 0.12, 1.4, musicBus); o2.start(t + 4); o2.stop(t + 5.6);
      }
      i++;
    }
    bar();
    musicTimer = setInterval(bar, BAR * 1000);
  }

  // ---------- the room: delegates murmuring, far off ----------
  function murmur(on) {
    if (!on) {
      if (murmurNode) { var m = murmurNode; murmurNode = null; try { m.g.gain.setTargetAtTime(0.0001, ctx.currentTime, 0.6); setTimeout(function () { m.src.stop(); }, 2500); } catch (e) { /* none */ } }
      return;
    }
    if (murmurNode) return;
    var c = audio(); if (!c) return;
    var src = noise(c, 4); src.loop = true;
    var bp = c.createBiquadFilter(); bp.type = "bandpass"; bp.frequency.value = 520; bp.Q.value = 0.9;
    var g = c.createGain(); g.gain.value = 0.0001; g.gain.setTargetAtTime(0.05, c.currentTime, 2);
    var lfo = c.createOscillator(), lg = c.createGain(); lfo.frequency.value = 0.17; lg.gain.value = 0.02; lfo.connect(lg); lg.connect(g.gain);
    src.connect(bp); bp.connect(g); g.connect(master); src.start(); lfo.start();
    murmurNode = { src: src, g: g };
  }

  // ---------- captions: every effect is also said on screen ----------
  function caption(text) {
    var box = document.getElementById("fx-caption");
    if (!box) {
      box = document.createElement("div"); box.id = "fx-caption"; box.className = "fx-caption";
      box.setAttribute("role", "status"); box.setAttribute("aria-live", "polite"); document.body.appendChild(box);
    }
    box.textContent = "♪ " + text;
    box.classList.add("show");
    clearTimeout(box._t);
    box._t = setTimeout(function () { box.classList.remove("show"); }, 2600);
  }

  window.socSession = window.socSession || {};
  window.socSession.audio = { play: play, music: music, murmur: murmur, settings: settings, set: set, caption: caption, motionOn: motionOn };
  document.addEventListener("DOMContentLoaded", function () { apply(settings()); });
})();
