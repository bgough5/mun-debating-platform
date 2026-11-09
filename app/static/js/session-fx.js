/* The Session's motion (Ben, 9 Nov): six effects that make the room feel physical. Each one shows something that
   really happened in the game; none of them carries information of its own, and all of them are skipped when
   motion is off (Settings, or the system's "reduce motion"). The text a test or a screen reader reads is always
   the plain final value: the moving parts are copies marked aria-hidden.

   window.socSession.fx:
     roll(meterLi, old, now)  mechanical counter: the digits of a meter roll from the old value to the new one
     flip(token)              a map token turns over when a delegation's lean changes
     ink(el, delay)           text written on in ink (clauses read out, amendments moved)
     light(key)               the light of the hour: morning, afternoon, lamplight, the Summit's chandelier
     react(svg, how)          a face reacts: "nod", "shake", "brow", "smile"
     medals(row)              medals with weight: they drop one at a time, lowest first, gold last
     paper(doc, kind)         paper arrives: "telegram" (slid under the door) or "news" (a newspaper unfolds) */
(function () {
  "use strict";
  window.socSession = window.socSession || {};
  function A() { return window.socSession.audio; }
  function on() { var a = A(); return !!(a && a.motionOn && a.motionOn()); }
  function restart(el, cls) { if (!el) return; el.classList.remove(cls); void el.getBoundingClientRect(); el.classList.add(cls); }
  function after(el, ms, fn) { setTimeout(fn, ms); }

  // ---------- mechanical counters ----------
  function roll(li, old, now) {
    if (!li || !on()) return;
    var b = li.querySelector("b"); if (!b) return;
    var from = String(old), to = String(now);
    if (!/^-?\d+$/.test(from) || !/^-?\d+$/.test(to) || from === to) return;
    var prior = li.querySelector(".fx-odo"); if (prior) prior.remove();
    var up = +to > +from, width = Math.max(from.length, to.length);
    var pad = function (s) { while (s.length < width) s = " " + s; return s; };
    var a = pad(from), z = pad(to);
    var odo = document.createElement("span"); odo.className = "fx-odo" + (up ? " up" : " down"); odo.setAttribute("aria-hidden", "true");
    for (var i = 0; i < width; i++) {
      var col = document.createElement("span"), strip = document.createElement("span");
      col.className = "fx-col"; strip.className = "fx-strip";
      var x = a.charAt(i), y = z.charAt(i);
      // the strip runs from the old digit to the new one, the way the wheel turns (a blank wheel shows nothing)
      var seq = [x];
      if (x !== y) {
        var dx = /\d/.test(x) ? +x : (up ? 9 : 0), dy = /\d/.test(y) ? +y : (up ? 0 : 9), step = up ? 1 : -1, n = dx, guard = 0;
        if (!/\d/.test(x)) seq = [" "];
        while (n !== dy && guard++ < 10) { n = (n + step + 10) % 10; seq.push(n === dy ? y : String(n)); }
        if (seq[seq.length - 1] !== y) seq.push(y);
      }
      seq.forEach(function (ch) { var d = document.createElement("span"); d.textContent = ch === " " ? " " : ch; strip.appendChild(d); });
      strip.style.setProperty("--fx-n", String(seq.length - 1));
      strip.style.animationDelay = ((width - 1 - i) * 0.07) + "s";      // the units wheel turns first, like a meter
      col.appendChild(strip); odo.appendChild(col);
    }
    var cs = window.getComputedStyle(b);                                  // the wheels wear the number's own type
    odo.style.fontFamily = cs.fontFamily; odo.style.fontSize = cs.fontSize; odo.style.fontWeight = cs.fontWeight; odo.style.lineHeight = cs.lineHeight; odo.style.textShadow = cs.textShadow;
    odo.style.fontVariantNumeric = "tabular-nums";
    li.classList.add("fx-rolling");
    li.appendChild(odo);
    odo.style.left = b.offsetLeft + "px"; odo.style.top = b.offsetTop + "px";
    odo.style.width = b.offsetWidth + "px"; odo.style.height = b.offsetHeight + "px";
    after(odo, 900 + width * 70, function () { odo.remove(); if (!li.querySelector(".fx-odo")) li.classList.remove("fx-rolling"); });
  }

  // ---------- tokens that turn over ----------
  function flip(t) { if (t && on()) { restart(t, "fx-flip"); after(t, 700, function () { t.classList.remove("fx-flip"); }); } }

  // ---------- ink on parchment ----------
  function ink(el, delay) {
    if (!el || !on()) return;
    el.style.setProperty("--fx-ink", (delay || 0) + "s");
    restart(el, "fx-ink");
  }

  // ---------- the light of the hour ----------
  var LIGHT = { "1": "morning", "2": "afternoon", "3": "lamp", summit: "chandelier" };
  function light(key) {
    var board = document.querySelector(".s-stage .b-board"); if (!board) return;
    var l = document.getElementById("fx-light");
    if (!l) { l = document.createElement("div"); l.id = "fx-light"; l.className = "fx-light"; l.setAttribute("aria-hidden", "true"); board.appendChild(l); }
    var name = LIGHT[key] || "morning";
    if (l.getAttribute("data-light") !== name) l.setAttribute("data-light", name);
  }
  // now and then, light catches the brass
  function glint() {
    if (on() && !document.hidden) {
      var all = document.querySelectorAll(".s-stage .b-roundel, .s-stage .s-meter i, .s-stage .s-tabs button");
      if (all.length) { var e = all[Math.floor(Math.random() * all.length)]; restart(e, "fx-glint"); after(e, 1300, function () { e.classList.remove("fx-glint"); }); }
    }
    setTimeout(glint, 9000 + Math.random() * 9000);
  }
  if (document.body && document.body.getAttribute("data-page") === "game") setTimeout(glint, 6000);

  // ---------- faces that react ----------
  var HOW = { nod: "fx-nod", shake: "fx-shake", brow: "fx-brow", smile: "fx-smile" };
  function react(svg, how) {
    if (!svg || !HOW[how] || !on()) return;
    Object.keys(HOW).forEach(function (k) { svg.classList.remove(HOW[k]); });
    restart(svg, HOW[how]);
    after(svg, 1300, function () { svg.classList.remove(HOW[how]); });
  }

  // ---------- medals with weight ----------
  function medals(row) {
    if (!row) return;
    var coins = Array.prototype.slice.call(row.querySelectorAll(".s-medal i"));
    if (!on()) { coins.forEach(function (c) { c.style.animation = "none"; }); return; }
    // lowest first, gold last: the order the room would want to see them in
    var order = coins.map(function (c, i) { return { c: c, g: +((c.className.match(/g(\d)/) || [0, 0])[1]), i: i }; })
      .sort(function (p, q) { return p.g - q.g || p.i - q.i; });
    order.forEach(function (o, k) {
      var at = 0.35 + k * 0.42 + (o.g === 3 ? 0.35 : 0);
      o.c.style.animationDelay = at + "s";
      o.c.parentNode.style.setProperty("--fx-land", at + "s");
      o.c.parentNode.classList.add("fx-drop");
      setTimeout(function () { var a = A(); if (a) a.play(o.g === 3 ? "medal_gold" : o.g ? "medal" : "tick"); }, (at + 0.62) * 1000);
    });
  }

  // ---------- paper arrives ----------
  function paper(doc, kind) {
    if (!doc) return;
    doc.classList.remove("fx-telegram", "fx-news");
    if (!on() || !kind) return;
    restart(doc, kind === "news" ? "fx-news" : "fx-telegram");
  }

  window.socSession.fx = { on: on, roll: roll, flip: flip, ink: ink, light: light, react: react, medals: medals, paper: paper };
})();
