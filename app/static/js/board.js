/* The board (D-092): the war-room table on the projector. It reads the session as JSON whenever anything changes
   (the same live channel as every other screen), compares it with what it last drew, and plays the difference:
   the stage coin flies down from the banner and a scroll unrolls (or, for voting, the chamber doors close); the
   tokens are dealt onto the map at roll call and light up as countries answer, ticked off in the ledger; the camera
   glides to the country speaking, the room darkens around them and the brass clock runs; votes drop as chips and
   sweep across the map, vetoes are stamped, and the wax seal lands and settles in the corner.
   All text from the session goes in with textContent, never as HTML. Opening or reloading the board plays nothing:
   it shows the room as it is. Sounds come from effects.js (captioned; where they play is set in Admin). */
(function () {
  "use strict";
  var body = document.body, stage = document.getElementById("b-stage");
  var token = body.getAttribute("data-token"), sid = body.getAttribute("data-sid");
  var map = document.getElementById("b-map"), rail = document.getElementById("b-rail"), overlay = document.getElementById("b-overlay");
  var boardEl = document.getElementById("b-board"), spotEl = document.getElementById("b-spot"), compass = boardEl.querySelector(".b-compass");
  var keyEl = document.getElementById("b-key");
  var S = null, fetchedAt = 0, scale = 1;
  var tokens = {}, lands = {}, home = {};
  var tokGroup = document.getElementById("b-tokens");
  var TW = +tokGroup.getAttribute("data-w") || 52, TH = +tokGroup.getAttribute("data-h") || 36, LINE_MAX = 28;
  map.querySelectorAll(".b-token").forEach(function (g) {
    var iso = g.getAttribute("data-iso");
    tokens[iso] = g; home[iso] = [+g.getAttribute("data-x"), +g.getAttribute("data-y")];
  });
  map.querySelectorAll(".b-land").forEach(function (p) { (lands[p.getAttribute("data-iso")] = lands[p.getAttribute("data-iso")] || []).push(p); });
  var WORLD = map.getAttribute("viewBox").split(" ").map(Number);
  var view = WORLD.slice();
  var VOTE_WORD = { yes: "Yes", no: "No", abstain: "Abstain", absent: "Absent" };

  function motion() {
    if (body.getAttribute("data-fx-motion") === "off") return false;
    return !(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  }
  function play(name, arg) { if (window.socFx) window.socFx.play(name, arg); }
  function say(text) { var el = document.getElementById("b-say"); if (el) el.textContent = text; }
  function h(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined && text !== null) e.textContent = text;
    return e;
  }
  function add(parent) { for (var i = 1; i < arguments.length; i++) if (arguments[i]) parent.appendChild(arguments[i]); return parent; }
  function later(fn, ms) { return setTimeout(fn, motion() ? ms : 0); }
  function restart(el, cls) { el.classList.remove(cls); void el.getBoundingClientRect(); el.classList.add(cls); }
  function talking() { return S && ["opening_speeches", "floor"].indexOf(S.stage.code) >= 0; }
  function andList(xs) { return xs.length > 1 ? xs.slice(0, -1).join(", ") + " and " + xs[xs.length - 1] : (xs[0] || ""); }

  // ---------- the stage fills any screen, 16:9 ----------
  function fit() {
    scale = Math.min(window.innerWidth / 1920, window.innerHeight / 1080);
    stage.style.transform = "translate(" + ((window.innerWidth - 1920 * scale) / 2) + "px," + ((window.innerHeight - 1080 * scale) / 2) + "px) scale(" + scale + ")";
    spot();
  }
  window.addEventListener("resize", fit);
  // A point on screen, in the stage's own 1920x1080 coordinates.
  function local(r) { var s = stage.getBoundingClientRect(); return { x: (r.left + r.width / 2 - s.left) / scale, y: (r.top + r.height / 2 - s.top) / scale }; }

  // ---------- the camera: glide the map's viewBox; tokens keep their size on screen ----------
  var camAnim = null, lastK = 0;
  function placeTokens() {
    // Zoomed in, a token grows with the map only up to 1.5 times its normal size, so it never crowds the view.
    var k = Math.min(1, 1.5 * view[2] / WORLD[2]);
    if (Math.abs(k - lastK) < .002) return;
    lastK = k;
    Object.keys(tokens).forEach(function (iso) {
      tokens[iso].setAttribute("transform", "translate(" + home[iso][0] + " " + home[iso][1] + ") scale(" + k.toFixed(3) + ") translate(" + (-TW / 2) + " " + (-TH / 2) + ")");
    });
  }
  // The key steps aside if a token in this room would sit underneath it (a committee with countries in the far south-west).
  function keyCovers() {
    var k = keyEl.getBoundingClientRect();
    return Object.keys(tokens).some(function (iso) {
      var r = tokens[iso].querySelector(".b-face").getBoundingClientRect();     // the deed itself, not its glow
      return r.right > k.left && r.left < k.right && r.bottom > k.top && r.top < k.bottom;
    });
  }
  function setView(v) {
    view = v;
    map.setAttribute("viewBox", v.map(function (n) { return n.toFixed(1); }).join(" "));
    placeTokens(); spot();
    compass.classList.toggle("away", v[2] < WORLD[2] * .9);
    if (keyEl) keyEl.classList.toggle("away", v[2] < WORLD[2] * .9 || keyCovers());
  }
  function glide(to, ms) {
    if (camAnim) cancelAnimationFrame(camAnim);
    if (!motion() || !ms) { setView(to); return; }
    var from = view.slice(), t0 = performance.now();
    function step(t) {
      var k = Math.min(1, (t - t0) / ms), e = k < .5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2;
      setView(from.map(function (f, i) { return f + (to[i] - f) * e; }));
      if (k < 1) camAnim = requestAnimationFrame(step);
    }
    camAnim = requestAnimationFrame(step);
  }
  function focusOn(iso) {
    var g = tokens[iso];
    if (!g) return glide(WORLD, 1400);
    var b = g.getAttribute("data-box").split(" ").map(Number);
    var tx = home[iso][0], ty = home[iso][1];
    var x0 = Math.min(b[0], tx - 30), y0 = Math.min(b[1], ty - 22), x1 = Math.max(b[2], tx + 30), y1 = Math.max(b[3], ty + 22);
    var rect = map.getBoundingClientRect(), aspect = rect.width / Math.max(1, rect.height);
    var w = Math.max(x1 - x0, 230) * 1.7, hgt = Math.max(y1 - y0, 130) * 1.7;
    if (w / hgt > aspect) hgt = w / aspect; else w = hgt * aspect;
    w = Math.min(w, WORLD[2]); hgt = Math.min(hgt, WORLD[3]);
    var cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
    var vx = Math.max(WORLD[0] - 40, Math.min(cx - w / 2, WORLD[2] - w + 40)), vy = Math.max(WORLD[1] - 30, Math.min(cy - hgt / 2, WORLD[3] - hgt + 30));
    // Never cut a token in half at the top or bottom edge: move the view to take it in whole (or leave it out).
    var k = Math.min(1, 1.5 * w / WORLD[2]), half = TH / 2 * k, pad = 8 * k;
    Object.keys(home).forEach(function (c) {
      var top = home[c][1] - half, bottom = home[c][1] + half;
      if (top < vy && bottom > vy && vy - top < 70 * k) vy = top - pad;
      else if (top < vy + hgt && bottom > vy + hgt && bottom - (vy + hgt) < 70 * k && top - pad > vy) vy = bottom + pad - hgt;
    });
    glide([vx, vy, w, hgt], 1600);
  }
  // The room darkens around whoever has the floor.
  function spot() {
    if (!spotEl) return;
    var g = S && talking() && S.current ? tokens[S.current.iso3] : null;
    spotEl.classList.toggle("on", !!g);
    if (!g) return;
    var br = boardEl.getBoundingClientRect(), r = g.getBoundingClientRect();
    spotEl.style.setProperty("--sx", ((r.left + r.width / 2 - br.left) / scale).toFixed(0) + "px");
    spotEl.style.setProperty("--sy", ((r.top + r.height / 2 - br.top) / scale).toFixed(0) + "px");
    spotEl.style.setProperty("--sr", (Math.max(r.width, r.height) / scale * .8 + 50).toFixed(0) + "px");
  }

  // ---------- full-screen moments, one at a time ----------
  var queue = [], busy = false;
  function moment(build, ms, opts) { queue.push({ build: build, ms: ms, opts: opts || {} }); if (!busy) nextMoment(); }
  function nextMoment() {
    var m = queue.shift();
    if (!m) { busy = false; return; }
    busy = true;
    var layer = h("div", "b-moment" + (m.opts.cls ? " " + m.opts.cls : ""));
    overlay.appendChild(layer);
    m.build(layer);
    setTimeout(function () {
      layer.classList.add("out");
      setTimeout(function () { layer.remove(); if (m.opts.after) m.opts.after(); nextMoment(); }, motion() ? (m.opts.outMs || 500) : 0);
    }, motion() ? m.ms : Math.min(m.ms, 2500));
  }
  function scroll(eyebrow, title, lines, extra) {
    var wrap = h("div", "b-scroll"), sc = h("div", "b-scroll-body");
    add(sc, eyebrow ? h("p", "b-eyebrow", eyebrow) : null, h("h2", null, title), h("div", "b-rule"));
    (lines || []).forEach(function (l) { if (l) sc.appendChild(h("p", null, l)); });
    if (extra) extra(sc);
    var bottom = h("div", "b-roller bottom");
    add(wrap, h("div", "b-roller top"), sc, bottom);
    // The bottom roller starts at the top and rolls down as the parchment opens.
    wrap.ready = function () { bottom.style.setProperty("--h", (-sc.offsetHeight) + "px"); };
    return wrap;
  }
  function show(layer, sc) { layer.appendChild(sc); if (sc.ready) sc.ready(); return sc; }
  var SEAL_PATH = "M0-60C14-58 20-66 32-56S50-44 56-30 66-12 60 2 66 22 56 34 48 52 34 58 18 66 2 62-14 66-30 58-48 52-56 38-64 20-60 4-66-12-56-28-48-50-34-56-16-62 0-60Z";
  function sealSvg(size) {
    var d = h("div");
    d.innerHTML = '<svg viewBox="-70 -70 140 140" width="' + size + '" height="' + size + '" aria-hidden="true"><g class="b-seal"><path class="b-seal-wax" d="' + SEAL_PATH +
      '"/><circle class="b-seal-ring" r="44"/><text class="b-seal-text" text-anchor="middle" y="7" font-size="18"></text></g></svg>';
    return d.firstChild;
  }

  // ---------- the map's standing state, from the session ----------
  function country(iso) { return (S.countries || []).filter(function (x) { return x.iso3 === iso; })[0]; }
  function nameOf(iso) { var c = country(iso); return c ? c.name : iso; }
  function clearClasses(el, prefixList) {
    Array.prototype.slice.call(el.classList).forEach(function (c) { if (prefixList.some(function (p) { return c.indexOf(p) === 0; })) el.classList.remove(c); });
  }
  function shownVote() {
    // The vote the map shows: the open division, or the last result while voting, or the resolution at the debrief.
    var st = S.stage.code;
    if (S.division) return { votes: S.division.votes, veto: S.division.veto || [] };
    var src = st === "debrief" ? S.debrief : (st === "voting_procedure" ? S.result : null);
    if (!src) return null;
    var votes = {}; Object.keys(src.votes).forEach(function (k) { votes[k] = src.votes[k].vote; });
    return { votes: votes, veto: src.veto || [] };
  }
  function paint() {
    var st = S.stage.code, div = S.division, whip = S.whip, sv = shownVote();
    var votes = sv ? sv.votes : null, veto = {}, predicted = null, ring = null;
    if (sv) sv.veto.forEach(function (iso) { veto[iso] = 1; });
    if (!div && whip && st === "voting_procedure" && whip.phase === "locked") predicted = whip.predicted;
    if (whip && whip.phase === "revealed" && (st === "voting_procedure" || st === "debrief")) ring = whip.correct;
    var placards = {}; if (talking() || st === "agenda") (S.placards || []).forEach(function (p) { placards[p.iso3] = 1; });
    var speaker = talking() && S.current ? S.current.iso3 : null;
    (S.countries || []).forEach(function (c) {
      var iso = c.iso3, g = tokens[iso], ls = lands[iso] || [];
      ls.forEach(function (p) {
        clearClasses(p, ["v-", "p-"]); p.classList.remove("lit", "spot");
        if (st === "roll_call" && c.roll && c.roll !== "absent") p.classList.add("lit");
        if (votes && votes[iso]) p.classList.add("v-" + votes[iso]);
        else if (predicted && predicted[iso]) p.classList.add("p-" + predicted[iso]);
        if (speaker === iso) p.classList.add("spot");
      });
      if (!g) return;
      clearClasses(g, ["v-"]);
      g.classList.toggle("lit", st === "roll_call" && !!c.roll && c.roll !== "absent");
      g.classList.toggle("speaking", speaker === iso);
      g.classList.toggle("placard", !!placards[iso]);
      g.classList.toggle("cast", !!(votes && votes[iso]));
      g.classList.toggle("veto", !!veto[iso]);
      if (votes && votes[iso]) g.classList.add("v-" + votes[iso]);
      g.classList.toggle("right", !!(ring && ring[iso] === true));
      g.classList.toggle("wrong", !!(ring && ring[iso] === false));
      var txt;
      if (st === "roll_call") txt = c.roll === "present_and_voting" ? "P & V" : (c.roll === "present" ? "Present" : (c.roll === "absent" ? "Absent" : c.short));
      else if (votes && votes[iso]) txt = VOTE_WORD[votes[iso]];
      else if (whip && whip.phase === "open" && st === "voting_procedure") txt = (whip.calls[iso] || 0) + " call" + (whip.calls[iso] === 1 ? "" : "s");
      else if (predicted && predicted[iso]) txt = "call: " + predicted[iso];
      else txt = c.students.length ? c.students[0] + (c.students.length > 1 ? " +" + (c.students.length - 1) : "") : c.short;
      setLine(g, txt);
    });
    cornerSeal(false);
  }

  // A token's second line, squeezed to fit beside the flag when it is long (a long short name, a long first name).
  function setLine(g, txt) {
    var t = g.querySelector(".b-line");
    if (t.textContent !== txt) { t.textContent = txt; t.removeAttribute("textLength"); t.removeAttribute("lengthAdjust"); }
    try { if (t.getComputedTextLength() > LINE_MAX) { t.setAttribute("textLength", LINE_MAX); t.setAttribute("lengthAdjust", "spacingAndGlyphs"); } } catch (e) { /* not drawn yet */ }
  }

  // The seal of the last result rests in the corner of the board while it is the news of the room.
  var sealing = false;       // while a result is being revealed, its seal is still on its way
  function cornerSeal(arrive) {
    var el = document.getElementById("b-cornerseal"), st = S.stage.code;
    var src = sealing ? null : (st === "debrief" ? S.debrief : (st === "voting_procedure" && !S.division ? S.result : null));
    el.hidden = !src;
    if (!src) { el.innerHTML = ""; el.removeAttribute("data-id"); return; }
    if (el.getAttribute("data-id") !== String(src.id)) {
      el.innerHTML = ""; var svg = sealSvg(150); el.appendChild(svg);
      svg.querySelector(".b-seal").classList.add(src.passed ? "passed" : "failed");
      svg.querySelector(".b-seal-text").textContent = src.passed ? "PASSED" : "FAILED";
      el.setAttribute("data-id", String(src.id));
    }
    if (arrive && motion()) restart(el, "arrive");
  }

  // ---------- the rail: documents and brass plates for the stage ----------
  var seenKeys = {}, seenBig = {}, nextBig = {}, inked = {};
  function card(key, title, cls) { var c = h("section", "b-card" + (cls ? " " + cls : "")); c.setAttribute("data-key", key); c.appendChild(h("h2", null, title)); return c; }
  function big(key, text, cls) {
    var p = h("p", "b-big" + (cls ? " " + cls : ""), text);
    if (seenBig[key] !== undefined && seenBig[key] !== text && motion()) p.classList.add("roll");
    nextBig[key] = text;
    return p;
  }
  var ICONS = {
    gavel: '<svg class="b-plate-icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="2" y="19" width="12" height="3"/><path d="M12.6 1.8l5.6 5.6-2.4 2.4-5.6-5.6zM8.4 6l5.6 5.6-2.4 2.4L6 8.4zM12.2 9.6l9 9-2 2-9-9z"/></svg>',
    bell: '<svg class="b-plate-icon" viewBox="0 0 24 24" aria-hidden="true"><g class="b-bell"><path d="M12 1.5a1.6 1.6 0 0 1 1.6 1.6v.8A6.2 6.2 0 0 1 18.2 10v5l2.3 2.3V18.5H3.5v-1.2L5.8 15v-5a6.2 6.2 0 0 1 4.6-6.1v-.8A1.6 1.6 0 0 1 12 1.5z"/><rect x="10" y="19.6" width="4" height="2.6"/></g></svg>',
    seal: '<svg class="b-plate-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2l2.6 2 3.2-.4.9 3.1 2.8 1.6-1 3.1 1 3.1-2.8 1.6-.9 3.1-3.2-.4L12 22l-2.6-2-3.2.4-.9-3.1-2.8-1.6 1-3.1-1-3.1 2.8-1.6.9-3.1 3.2.4z"/></svg>'
  };
  function plate(key, icon, title, sub, cls) {
    var p = h("div", "b-plate" + (cls ? " " + cls : "")); p.setAttribute("data-key", key);
    p.innerHTML = ICONS[icon] || "";
    add(p, h("strong", null, title), sub ? h("span", null, sub) : null);
    return p;
  }
  function bars(counts, total) {
    var b = h("div", "b-bars");
    [["yes", "Yes"], ["no", "No"], ["abstain", "Abstain"]].forEach(function (k) {
      var row = h("div", "b-bar " + k[0]), tube = h("span", "b-tube"), i = h("i");
      tube.appendChild(i); add(row, h("span", null, k[1]), tube, h("span", null, String(counts[k[0]] || 0)));
      i.style.setProperty("--w", (100 * (counts[k[0]] || 0) / Math.max(1, total)) + "%");
      b.appendChild(row);
    });
    return b;
  }
  function lesson(src) {
    if (src.veto && src.veto.length) return (src.yes != null ? src.yes : countOf(src, "yes")) + " in favour, but vetoed by " + andList(src.veto.map(nameOf)) + ".";
    return src.summary || "";
  }
  function countOf(src, v) { return Object.keys(src.votes).filter(function (k) { return src.votes[k].vote === v; }).length; }
  function resultCard(key, heading, src) {
    var c = card(key, heading);
    add(c, big(key + ":word", src.passed ? "Passed" : "Failed", src.passed ? "passed" : "failed"), h("p", null, src.title),
        bars({ yes: countOf(src, "yes"), no: countOf(src, "no"), abstain: countOf(src, "abstain") }, Object.keys(src.votes).length));
    var l = lesson(src); if (l) c.appendChild(h("p", "b-lesson", l));
    return c;
  }
  function speakersCard() {
    var c = card("speakers", S.session.mode === "moderated" ? "Moderated caucus list" : "Speakers list");
    if (!S.queue.length) { c.appendChild(h("p", "b-sub", "No one waiting. Raise your placard to be added.")); return c; }
    var ul = h("ol", "b-list");
    S.queue.slice(0, 6).forEach(function (q, i) {
      var li = h("li", i === 0 ? "next" : ""); li.appendChild(h("b", null, q.iso3)); li.appendChild(h("span", null, q.by + (q.side ? " · " + q.side : "")));
      ul.appendChild(li);
    });
    c.appendChild(ul);
    if (S.queue.length > 6) c.appendChild(h("p", "b-sub", "and " + (S.queue.length - 6) + " more"));
    return c;
  }
  function rollCards() {
    var out = [], c = card("roll", "Roll call", "b-tally");
    add(c, big("roll", S.roll.present + " / " + S.roll.total), h("p", null, "delegations present"));
    out.push(c);
    var led = card("ledger", "The roll"), ul = h("ul", "b-ledger"), now = {};
    S.countries.forEach(function (x) {
      var li = h("li", x.roll ? "" : "waiting"), box = h("span", "b-box");
      if (x.roll && x.roll !== "absent") {
        box.innerHTML = '<svg class="b-tick" viewBox="0 0 20 20" aria-hidden="true"><path d="M3 10.5l4.5 4.5L17 4"/></svg>';
        now[x.iso3] = 1;
        if (S._prevInked && !S._prevInked[x.iso3]) li.classList.add("inked");
      }
      add(li, box, h("span", null, x.short), x.roll === "present_and_voting" ? h("em", null, "P & V") : (x.roll === "absent" ? h("em", null, "absent") : null));
      ul.appendChild(li);
    });
    led.appendChild(ul);
    if (S.countries.some(function (x) { return x.roll === "present_and_voting"; })) led.appendChild(h("p", "b-legend", "P & V: present and voting. They can't abstain on the resolution."));
    inked = now;
    out.push(led);
    return out;
  }
  function buildRail() {
    var st = S.stage.code, out = [];
    if (S.session.state !== "open") out.push(plate("state:" + S.session.state, "gavel", "Session " + S.session.state, S.session.state === "suspended" ? "Delegates, please wait." : "Thank you, delegates.", "alarm"));
    if (st === "roll_call") return out.concat(rollCards());
    if (st === "agenda") {
      var a = card("agenda", "The agenda");
      a.appendChild(h("p", null, S.session.agenda || "The committee is choosing its agenda."));
      out.push(a);
      if (S.session.draft) { var d = card("draft", "Draft resolution"); d.appendChild(h("p", null, S.session.draft)); out.push(d); }
      return out;
    }
    if (st === "opening_speeches" || st === "floor") {
      if (st === "floor") {
        var names = { formal: "Formal debate", moderated: "Moderated caucus", unmoderated: "Unmoderated caucus", voting: "Voting procedure" };
        out.push(plate("mode:" + S.session.mode + ":" + S.session.mode_topic, "gavel", names[S.session.mode] || "The floor", S.session.mode_topic));
      }
      out.push(speakersCard());
      if (st === "floor" && S.motions.length) {
        var m = card("motions", "Motions on the floor");
        S.motions.slice(0, 3).forEach(function (x) {
          var box = h("div", "b-motion"); add(box, h("strong", null, x.name + (x.minutes ? " · " + x.minutes + " min" : "")),
            h("p", "b-sub", (x.topic ? x.topic + " · " : "") + "proposed by " + x.by + (x.needs_second ? " · needs a second" : (x.seconded ? " · seconded by " + x.seconded : ""))));
          m.appendChild(box);
        });
        out.push(m);
      }
      if (S.amendment) {
        var am = card("amend:" + S.amendment.id, "On the floor: amendment", "b-amend");
        add(am, h("p", "b-sub", S.amendment.label + (S.amendment.by ? " · " + S.amendment.by : "")));
        if (S.amendment.before) am.appendChild(h("p", "b-old", S.amendment.before));
        if (S.amendment.after) am.appendChild(h("p", "b-new", S.amendment.after));
        out.push(am);
      }
      if (S.placards.length) {
        var pc = card("placards", "Placards up");
        pc.appendChild(h("p", null, S.placards.map(function (p) { return p.by; }).join(" · ")));
        out.push(pc);
      }
      return out;
    }
    if (st === "voting_procedure") {
      if (S.division) out.push(plate("bell:" + S.division.id, "bell", "Voting is open", S.division.title, "alarm"));
      if (S.whip) {
        var w = card("whip:" + S.whip.id, "Whip count: " + S.whip.title);
        if (S.whip.phase === "open") {
          var called = Object.keys(S.whip.calls).filter(function (k) { return S.whip.calls[k]; }).length;
          add(w, big("whip", called + " / " + S.countries.length), h("p", null, "countries called. Which way stays hidden until the vote."));
        } else if (S.whip.phase === "locked") w.appendChild(h("p", null, S.division ? "The class's calls are locked in. Now the room votes." : "The class's calls are on the map. The vote decides."));
        else add(w, big("whip", S.whip.right + " / " + S.whip.judged), h("p", null, "called correctly by the class."));
        out.push(w);
      }
      if (S.division) {
        var dv = card("div:" + S.division.id, "Division: " + S.division.title);
        add(dv, big("cast", S.division.cast + " / " + S.division.total), h("p", null, "votes cast"), bars(S.division.counts, S.division.total));
        if (S.division.veto_by.length) dv.appendChild(h("p", "b-lesson", "Veto: " + andList(S.division.veto_by) + " voted no."));
        out.push(dv);
      } else if (S.result) out.push(resultCard("result:" + S.result.id, "The vote", S.result));
      return out;
    }
    if (st === "debrief") {
      if (S.debrief) out.push(resultCard("debrief:" + S.debrief.id, "How the room voted", S.debrief));
      else { var e = card("debrief:none", "How the room voted"); e.appendChild(h("p", null, "No resolution vote yet.")); out.push(e); }
      if (S.debrief) out[out.length - 1].appendChild(h("p", "b-sub", "Each country on the map is coloured by its vote."));
      if (S.whip && S.whip.phase === "revealed") {
        var wc = card("reading", "Reading the room");
        add(wc, big("reading", S.whip.right + " / " + S.whip.judged), h("p", null, "countries the class called correctly"),
          h("p", "b-sub", "Green border: called it. Red border: missed. Your own score is on your laptop."));
        out.push(wc);
      }
    }
    return out;
  }
  function renderRail() {
    nextBig = {};
    var items = buildRail(), keys = {}, n = 0;
    rail.innerHTML = "";
    items.forEach(function (el) {
      var k = el.getAttribute("data-key"); keys[k] = 1;
      if (!seenKeys[k] && motion() && !busy) { el.classList.add("dealt"); el.style.animationDelay = (n++ * 140) + "ms"; if (el.classList.contains("alarm")) el.classList.add("ringing"); }
      rail.appendChild(el);
    });
    seenKeys = keys; seenBig = nextBig;
  }
  // After a full-screen moment the rail is dealt again, so the room sees the new stage's cards arrive.
  function redeal() {
    if (!motion()) return;
    Array.prototype.forEach.call(rail.children, function (el, i) {
      el.style.animationDelay = (i * 160) + "ms"; restart(el, "dealt");
      if (el.classList.contains("alarm")) restart(el, "ringing");
    });
  }

  // ---------- the banner, the speaker and the ticker ----------
  function renderBanner() {
    var rib = document.getElementById("b-ribbon"), ag = document.getElementById("b-agenda");
    ag.textContent = S.session.agenda ? "Agenda: " + S.session.agenda : "";
    rib.hidden = !S.session.agenda;
    var tk = document.getElementById("b-ticker");
    tk.hidden = !S.news || S.stage.code === "debrief";
    if (S.news) document.getElementById("b-ticker-text").textContent = S.news.headline + (S.news.label ? "  ·  " + S.news.label : "");
    stage.setAttribute("data-stage", S.stage.code);
  }
  function speakerTimer() {
    var t = (S.timers || []).filter(function (x) { return x.kind === "speaker"; })[0] || (S.timers || []).filter(function (x) { return x.state === "running"; })[0];
    return t || null;
  }
  function renderSpeaker() {
    var box = document.getElementById("b-speaker"), t = speakerTimer();
    var show = talking() && (!!S.current || !!(t && t.kind !== "speaker"));     // no speaker plate over a vote or the debrief
    box.hidden = !show;
    if (!show) return;
    document.getElementById("b-speaker-name").textContent = S.current ? S.current.by : t.label;
    document.getElementById("b-speaker-side").textContent = S.current && S.current.side ? "Speaking " + S.current.side + " the amendment" : "";
    box.querySelector(".b-speaker-tag").textContent = S.current ? "Now speaking" : "Timer";
  }
  function tick() {
    if (!S) return;
    var t = speakerTimer(), el = document.getElementById("b-time"), arc = document.getElementById("b-dial-arc"), hand = document.getElementById("b-dial-hand");
    if (!t) { el.textContent = ""; return; }
    var rem = t.remaining - (t.state === "running" ? (Date.now() - fetchedAt) / 1000 : 0);
    var a = Math.abs(rem), mm = Math.floor(a / 60), ss = Math.floor(a % 60);
    el.textContent = (rem < 0 ? "+" : "") + mm + ":" + (ss < 10 ? "0" : "") + ss;
    el.classList.toggle("over", rem < 0);
    var frac = Math.max(0, Math.min(1, rem / Math.max(1, t.total)));
    arc.style.strokeDashoffset = String(100 - frac * 100);
    arc.classList.toggle("warn", rem >= 0 && rem <= Math.min(30, t.total * .25));
    arc.classList.toggle("over", rem < 0);
    // The clock hand ticks once a second round the dial as the time is used.
    var used = Math.max(0, Math.min(t.total, t.total - Math.ceil(rem)));
    hand.style.transform = "rotate(" + (360 * used / Math.max(1, t.total)).toFixed(1) + "deg)";
  }
  setInterval(tick, 200);

  function trackLi(i) { return document.querySelectorAll("#b-track li")[i]; }
  function renderTrack() {
    document.querySelectorAll("#b-track li").forEach(function (li, i) {
      li.classList.toggle("done", i < S.stage.index);
      li.classList.toggle("now", i === S.stage.index);
    });
  }

  // ---------- moments: what changed since the last look ----------
  function sweep() {
    if (!motion()) return;
    var s = h("div", "b-sweep"); boardEl.appendChild(s); setTimeout(function () { s.remove(); }, 1800);
  }
  function dealTokens() {
    if (!motion()) return;
    Object.keys(tokens).sort(function (a, b) { return home[a][0] - home[b][0]; }).forEach(function (iso, i) {
      setTimeout(function () { restart(tokens[iso], "dealt"); if (i % 3 === 0) play("flip"); }, i * 70);
    });
  }
  function afterStage(N) {
    var li = trackLi(N.stage.index); if (li && motion()) restart(li, "b-landed");
    sweep(); redeal();
    if (N.stage.code === "roll_call") dealTokens();
    if (talking() && S.current) focusOn(S.current.iso3);          // back to whoever still has the floor
  }
  // The stage coin leaves the banner, spins to the middle above an unrolling scroll, then flies home.
  function stageScroll(N) {
    var n = N.stage.index + 1;
    moment(function (layer) {
      var sc = scroll("Stage " + n + " of " + N.stage.all.length, N.stage.name, [N.stage.prompt]);
      show(layer, sc);
      var wax = sealSvg(110); wax.setAttribute("class", "b-waxnum"); wax.querySelector(".b-seal-text").textContent = String(n);
      wax.querySelector(".b-seal-text").setAttribute("font-size", "40"); wax.querySelector(".b-seal-text").setAttribute("y", "14");
      sc.appendChild(wax);                                   // outside the parchment's clip, over the roller
      var li = trackLi(N.stage.index), coinEl = li && li.querySelector(".b-coin");
      if (!coinEl || !motion() || !layer.animate) return;
      var from = local(coinEl.getBoundingClientRect()), top = local(sc.getBoundingClientRect());
      var to = { x: 960, y: Math.max(90, top.y - sc.offsetHeight / 2 - 10) };
      var rays = h("div", "b-rays"); rays.style.left = to.x + "px"; rays.style.top = to.y + "px"; layer.appendChild(rays); rays.classList.add("on");
      var coin = h("div", "b-flycoin", String(n)); layer.appendChild(coin);
      coin.animate([{ left: from.x + "px", top: from.y + "px", transform: "scale(1) rotateY(0deg)" },
                    { left: to.x + "px", top: to.y + "px", transform: "scale(2.4) rotateY(1080deg)" }],
                   { duration: 1000, easing: "cubic-bezier(.3, 1.05, .4, 1)", fill: "forwards" });
      setTimeout(function () {
        coin.animate([{ left: to.x + "px", top: to.y + "px", transform: "scale(2.4)" }, { left: from.x + "px", top: from.y + "px", transform: "scale(1.24)" }],
                     { duration: 650, easing: "cubic-bezier(.5, 0, .7, 1)", fill: "forwards" });
      }, 4200);
    }, 4700, { after: function () { afterStage(N); } });
  }
  // Voting procedure: the doors of the chamber close; no one enters or leaves until the vote is done.
  function doorsMoment(N) {
    moment(function (layer) {
      var doors = h("div", "b-doors"); add(doors, h("div", "b-door l"), h("div", "b-door r")); layer.appendChild(doors);
      var pl = h("div", "b-door-plate");
      add(pl, h("p", null, "Stage " + (N.stage.index + 1) + " of " + N.stage.all.length), h("h2", null, N.stage.name),
          h("p", "b-door-sub", "The doors are closed. " + (N.stage.prompt || "")));
      layer.appendChild(pl);
      later(function () { play("gavel", 1); stage.classList.add("shake"); setTimeout(function () { stage.classList.remove("shake"); }, 400); }, 950);
    }, 4600, { cls: "doors", outMs: 950, after: function () { afterStage(N); } });
  }
  function sealOnBoard(passed, label) {
    var box = h("div", "b-sealbox"), svg = sealSvg(300);
    svg.querySelector(".b-seal").classList.add(passed ? "passed" : "failed");
    svg.querySelector(".b-seal-text").textContent = label;
    box.appendChild(svg); boardEl.appendChild(box);
    play("stamp"); setTimeout(function () { play("gavel", 1); stage.classList.add("shake"); setTimeout(function () { stage.classList.remove("shake"); }, 400); }, 260);
    // It lifts off the middle and settles in the corner, where it stays while this result is the news.
    later(function () { box.classList.add("gone"); sealing = false; cornerSeal(true); setTimeout(function () { box.remove(); }, 700); }, 2600);
  }
  function revealVote(result, after) {
    glide(WORLD, 900);
    sealing = true; document.getElementById("b-cornerseal").hidden = true;
    var order = Object.keys(result.votes).sort(function (a, b) { return nameOf(a).localeCompare(nameOf(b)); });
    var step = motion() ? Math.max(70, Math.min(240, 3600 / Math.max(1, order.length))) : 0;
    // Clear the colours, then sweep them back on in roll-call order.
    order.forEach(function (iso) {
      (lands[iso] || []).forEach(function (p) { clearClasses(p, ["v-", "p-"]); });
      if (tokens[iso]) { clearClasses(tokens[iso], ["v-"]); tokens[iso].classList.remove("cast", "veto"); }
    });
    order.forEach(function (iso, i) {
      setTimeout(function () {
        var v = result.votes[iso].vote;
        (lands[iso] || []).forEach(function (p) { p.classList.add("v-" + v); });
        var g = tokens[iso];
        if (g) { g.classList.add("v-" + v, "cast"); restart(g, "pop"); setLine(g, VOTE_WORD[v]); }
        if (i % 2 === 0) play("flip");
      }, 700 + i * step);
    });
    setTimeout(function () {
      (result.veto || []).forEach(function (iso, i) { setTimeout(function () { if (tokens[iso]) { tokens[iso].classList.add("veto"); play("stamp"); } }, i * 350); });
      setTimeout(function () {
        sealOnBoard(result.passed, result.passed ? "PASSED" : "FAILED");
        say(result.title + ": " + (result.passed ? "passed" : "failed") + ". " + lesson(result));
        if (after) after();
      }, (result.veto || []).length * 350 + 200);
    }, 900 + order.length * step);
  }
  function adoptedMoment(a) {
    var typeMs = motion() ? Math.min(2600, Math.max(600, (a.after || "").length * 22)) : 0;
    moment(function (layer) {
      var sc = scroll(a.friendly ? "Friendly amendment" : "Amendment adopted", a.label, []), bodyEl = sc.querySelector(".b-scroll-body");
      var old = a.before ? h("p", "b-old", a.before) : null, neu = a.after ? h("p", "b-new", "") : null;
      add(bodyEl, old, neu);
      var stamp = h("div", "b-stamp", "Adopted"); bodyEl.appendChild(stamp);
      show(layer, sc);
      if (old) setTimeout(function () { old.classList.add("struck"); }, 900);
      var start = a.before ? 1700 : 900;
      if (neu) {
        if (typeMs) { var i = 0, n = a.after.length; setTimeout(function t() { i = Math.min(n, i + Math.max(1, Math.round(n / (typeMs / 16)))); neu.textContent = a.after.slice(0, i); if (i < n) setTimeout(t, 16); }, start); }
        else neu.textContent = a.after;
      }
      later(function () { stamp.classList.add("landed"); play("stamp"); setTimeout(function () { play("gavel", 1); }, 240); }, start + typeMs + 300);
    }, 1700 + typeMs + 3600);
  }

  function changes(P, N) {
    var st = N.stage.code;
    if (P.stage.code !== N.stage.code) {
      play("chime");
      say("Stage " + (N.stage.index + 1) + ": " + N.stage.name);
      glide(WORLD, 1400);
      if (st === "voting_procedure") doorsMoment(N); else stageScroll(N);
    }
    if (N.session.agenda && N.session.agenda !== P.session.agenda) {
      var rib = document.getElementById("b-ribbon"); if (motion()) setTimeout(function () { restart(rib, "unfurl"); }, 300);
      moment(function (layer) { show(layer, scroll("The agenda", N.session.agenda, ["The committee will debate this topic."])); }, 4200);
    }
    // Roll call: each country that answers pops and lights; the ledger ticks it off.
    var before = {}; P.countries.forEach(function (c) { before[c.iso3] = c.roll; });
    N.countries.forEach(function (c) {
      if (c.roll && c.roll !== before[c.iso3] && tokens[c.iso3]) { restart(tokens[c.iso3], "pop"); play("flip"); }
    });
    // A new speaker: the camera glides to them and the lights come down around them.
    var pc = P.current ? P.current.id : null, nc = N.current && ["opening_speeches", "floor"].indexOf(st) >= 0 ? N.current.id : null;
    if (nc && nc !== pc) { focusOn(N.current.iso3); play("flip"); say("Now speaking: " + N.current.by); }
    if (!nc && pc && P.stage.code === N.stage.code) glide(WORLD, 1400);
    // A division opens: the bell, and the scroll.
    if (N.division && (!P.division || P.division.id !== N.division.id)) {
      play("division"); glide(WORLD, 900);
      moment(function (layer) { show(layer, scroll("Division", "Voting is open", [N.division.title, "Heads of delegation: vote on your laptop."])); }, 3800);
    }
    // Votes coming in: each chip drops onto its country.
    if (N.division && P.division && P.division.id === N.division.id) {
      Object.keys(N.division.votes).forEach(function (iso) { if (!P.division.votes[iso]) play("flip"); });
    }
    // A vote's result: the sweep, the vetoes, then the seal.
    if (N.result && (!P.result || P.result.id !== N.result.id)) revealVote(N.result, paint);
    if (N.news && (!P.news || P.news.id !== N.news.id)) {
      play("news");
      moment(function (layer) {
        show(layer, scroll("", N.news.headline, [N.news.body], function (sc) {
          sc.insertBefore(h("p", "b-band-news", "Breaking news"), sc.firstChild); if (N.news.label) sc.appendChild(h("p", "b-label", N.news.label));
        }));
      }, 7500);
    }
    if (N.adopted && (!P.adopted || P.adopted.seq !== N.adopted.seq)) adoptedMoment(N.adopted);
    if (N.gavel.seq && N.gavel.seq !== P.gavel.seq) {
      play("gavel", N.gavel.knocks); stage.classList.add("shake"); setTimeout(function () { stage.classList.remove("shake"); }, 400);
    }
    if (N.placards.length > P.placards.length) play("placard");
    if (N.session.state === "closed" && P.session.state !== "closed") {
      play("gavel", 3);
      moment(function (layer) { show(layer, scroll("The session is closed", N.session.committee, ["Thank you, delegates."])); }, 6000);
    }
  }

  function fitTitle() {
    var el = document.getElementById("b-committee"), size = 44;
    el.style.fontSize = size + "px";
    while (el.scrollWidth > el.clientWidth && size > 28) { size -= 2; el.style.fontSize = size + "px"; }
  }

  function apply(N, first) {
    var P = S; S = N; fetchedAt = Date.now();
    S._prevInked = first ? null : inked;
    if (!first && P) changes(P, N);
    renderTrack(); renderBanner(); renderRail(); renderSpeaker(); tick(); if (first) fitTitle();
    var sweeping = !first && P && N.result && (!P.result || P.result.id !== N.result.id);
    if (!sweeping) paint();
    if (first) { if (N.current && talking()) focusOn(N.current.iso3); else setView(WORLD); }
    spot();
  }

  // ---------- live: the session's channel, then the state ----------
  var timer = null, inflight = false, again = false;
  function refresh() {
    if (inflight) { again = true; return; }
    inflight = true;
    fetch("/projector/" + encodeURIComponent(token) + "/state.json", { cache: "no-store" })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (st) { if (!S || st.seq !== S.seq) apply(st, false); })
      .catch(function () { /* the next change or the safety poll will try again */ })
      .then(function () { inflight = false; if (again) { again = false; refresh(); } });
  }
  function soon() { clearTimeout(timer); timer = setTimeout(refresh, 120); }
  var backoff = 1000;
  function connect() {
    var ws = new WebSocket((location.protocol === "https:" ? "wss:" : "ws:") + "//" + location.host + "/ws?projector=" + encodeURIComponent(token));
    var live = document.getElementById("b-live");
    ws.onopen = function () { backoff = 1000; ws.send(JSON.stringify({ subscribe: ["session:" + sid], since: 0 })); live.textContent = ""; soon(); };
    ws.onmessage = function (ev) { var m = JSON.parse(ev.data); if (m.channels || m.resync) soon(); };
    ws.onclose = function () { live.textContent = "Reconnecting…"; setTimeout(connect, backoff); backoff = Math.min(backoff * 2, 10000); };
  }
  setInterval(refresh, 20000);                              // a safety net if a message is ever missed

  fit();
  apply(JSON.parse(document.getElementById("b-initial").textContent), true);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(fitTitle);       // Cinzel is wider than the fallback
  window.addEventListener("resize", fitTitle);
  connect();
  window.socBoard = { state: function () { return S; }, refresh: refresh };
})();
