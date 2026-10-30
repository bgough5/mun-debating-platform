/* The board (D-092): the war-room table on the projector. It reads the session as JSON whenever anything changes
   (the same live channel as every other screen), compares it with what it last drew, and plays the difference:
   the stage medallion advances and a scroll unrolls; countries light up as they answer the roll; the camera glides
   to the country speaking and the brass dial counts their time; votes sweep across the map and the wax seal lands.
   All text from the session goes in with textContent, never as HTML. Opening or reloading the board plays nothing:
   it shows the room as it is. Sounds come from effects.js (captioned; where they play is set in Admin). */
(function () {
  "use strict";
  var body = document.body, stage = document.getElementById("b-stage");
  var token = body.getAttribute("data-token"), sid = body.getAttribute("data-sid");
  var map = document.getElementById("b-map"), rail = document.getElementById("b-rail"), overlay = document.getElementById("b-overlay");
  var S = null, fetchedAt = 0;
  var tokens = {}, lands = {};
  map.querySelectorAll(".b-token").forEach(function (g) { tokens[g.getAttribute("data-iso")] = g; });
  map.querySelectorAll(".b-land").forEach(function (p) { (lands[p.getAttribute("data-iso")] = lands[p.getAttribute("data-iso")] || []).push(p); });
  var WORLD = map.getAttribute("viewBox").split(" ").map(Number);
  var view = WORLD.slice();

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

  // ---------- the stage fills any screen, 16:9 ----------
  function fit() {
    var s = Math.min(window.innerWidth / 1920, window.innerHeight / 1080);
    stage.style.transform = "translate(" + ((window.innerWidth - 1920 * s) / 2) + "px," + ((window.innerHeight - 1080 * s) / 2) + "px) scale(" + s + ")";
  }
  window.addEventListener("resize", fit);
  fit();

  // ---------- the camera: glide the map's viewBox ----------
  var camAnim = null;
  function setView(v) { view = v; map.setAttribute("viewBox", v.map(function (n) { return n.toFixed(1); }).join(" ")); }
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
    var tx = +g.getAttribute("data-x"), ty = +g.getAttribute("data-y");
    var x0 = Math.min(b[0], tx - 30), y0 = Math.min(b[1], ty - 20), x1 = Math.max(b[2], tx + 30), y1 = Math.max(b[3], ty + 20);
    var rect = map.getBoundingClientRect(), aspect = rect.width / Math.max(1, rect.height);
    var w = Math.max(x1 - x0, 230) * 1.7, hgt = Math.max(y1 - y0, 130) * 1.7;
    if (w / hgt > aspect) hgt = w / aspect; else w = hgt * aspect;
    w = Math.min(w, WORLD[2]); hgt = Math.min(hgt, WORLD[3]);
    var cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
    glide([Math.max(WORLD[0] - 40, Math.min(cx - w / 2, WORLD[2] - w + 40)), Math.max(WORLD[1] - 30, Math.min(cy - hgt / 2, WORLD[3] - hgt + 30)), w, hgt], 1600);
  }

  // ---------- full-screen moments, one at a time ----------
  var queue = [], busy = false;
  function moment(build, ms) { queue.push({ build: build, ms: ms }); if (!busy) nextMoment(); }
  function nextMoment() {
    var m = queue.shift();
    if (!m) { busy = false; return; }
    busy = true;
    var layer = h("div", "b-moment");
    m.build(layer);
    overlay.appendChild(layer);
    setTimeout(function () {
      layer.classList.add("out");
      setTimeout(function () { layer.remove(); nextMoment(); }, motion() ? 450 : 0);
    }, m.ms);
  }
  function scroll(eyebrow, title, lines, extra) {
    var sc = h("div", "b-scroll");
    add(sc, h("p", "b-eyebrow", eyebrow), h("h2", null, title), h("div", "b-rule"));
    (lines || []).forEach(function (l) { if (l) sc.appendChild(h("p", null, l)); });
    if (extra) extra(sc);
    return sc;
  }

  // ---------- the map's standing state, from the session ----------
  function nameOf(iso) { var c = (S.countries || []).filter(function (x) { return x.iso3 === iso; })[0]; return c ? c.name : iso; }
  function clearClasses(el, prefixList) {
    Array.prototype.slice.call(el.classList).forEach(function (c) { if (prefixList.some(function (p) { return c.indexOf(p) === 0; })) el.classList.remove(c); });
  }
  function paint() {
    var st = S.stage.code, div = S.division, whip = S.whip;
    var votes = null, predicted = null, ring = null;
    if (div) votes = div.votes;
    else if (S.debrief && st === "debrief") { votes = {}; Object.keys(S.debrief.votes).forEach(function (k) { votes[k] = S.debrief.votes[k].vote; }); }
    else if (S.result && st === "voting_procedure") { votes = {}; Object.keys(S.result.votes).forEach(function (k) { votes[k] = S.result.votes[k].vote; }); }
    if (!div && whip && st === "voting_procedure" && whip.phase === "locked") predicted = whip.predicted;
    if (whip && whip.phase === "revealed" && (st === "voting_procedure" || st === "debrief")) ring = whip.correct;
    var placards = {}; (S.placards || []).forEach(function (p) { placards[p.iso3] = 1; });
    (S.countries || []).forEach(function (c) {
      var iso = c.iso3, g = tokens[iso], ls = lands[iso] || [];
      ls.forEach(function (p) {
        clearClasses(p, ["v-", "p-"]); p.classList.remove("lit", "spot");
        if (st === "roll_call" && c.roll && c.roll !== "absent") p.classList.add("lit");
        if (votes && votes[iso]) p.classList.add("v-" + votes[iso]);
        else if (predicted && predicted[iso]) p.classList.add("p-" + predicted[iso]);
        if (S.current && S.current.iso3 === iso && !votes) p.classList.add("spot");
      });
      if (!g) return;
      clearClasses(g, ["v-"]);
      g.classList.toggle("lit", st === "roll_call" && !!c.roll && c.roll !== "absent");
      g.classList.toggle("speaking", !!(S.current && S.current.iso3 === iso));
      g.classList.toggle("placard", !!placards[iso]);
      g.classList.toggle("cast", !!(div && votes && votes[iso]));
      if (votes && votes[iso]) g.classList.add("v-" + votes[iso]);
      g.classList.toggle("right", !!(ring && ring[iso] === true));
      g.classList.toggle("wrong", !!(ring && ring[iso] === false));
      var line = g.querySelector(".b-line"), txt = "";
      if (st === "roll_call") txt = c.roll === "present_and_voting" ? "present & voting" : (c.roll === "present" ? "present" : (c.roll === "absent" ? "absent" : ""));
      else if (votes && votes[iso]) txt = { yes: "Yes", no: "No", abstain: "Abstain", absent: "Absent" }[votes[iso]];
      else if (whip && whip.phase === "open" && st === "voting_procedure") txt = (whip.calls[iso] || 0) + " call" + (whip.calls[iso] === 1 ? "" : "s");
      else if (predicted && predicted[iso]) txt = "call: " + predicted[iso];
      else txt = c.students.length ? c.students[0] + (c.students.length > 1 ? " +" + (c.students.length - 1) : "") : "computed";
      line.textContent = txt;
    });
  }

  // ---------- the rail: parchment cards for the stage ----------
  function card(title, cls) { var c = h("section", "b-card" + (cls ? " " + cls : "")); c.appendChild(h("h2", null, title)); return c; }
  function bars(counts, total) {
    var b = h("div", "b-bars");
    [["yes", "Yes"], ["no", "No"], ["abstain", "Abstain"]].forEach(function (k) {
      var row = h("div", "b-bar " + k[0]); row.appendChild(h("span", null, k[1])); var i = h("i"); row.appendChild(i);
      row.appendChild(h("span", null, String(counts[k[0]] || 0)));
      i.style.setProperty("--w", (100 * (counts[k[0]] || 0) / Math.max(1, total)) + "%");
      b.appendChild(row);
    });
    return b;
  }
  function speakersCard() {
    var c = card("Speakers list");
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
  function renderRail() {
    rail.innerHTML = "";
    var st = S.stage.code;
    if (st === "roll_call") {
      var c = card("Roll call");
      add(c, h("p", "b-big", S.roll.present + " / " + S.roll.total), h("p", null, "delegations present"));
      var pv = S.countries.filter(function (x) { return x.roll === "present_and_voting"; }).length;
      if (pv) c.appendChild(h("p", "b-sub", pv + " present and voting: they can't abstain on the resolution."));
      var waiting = S.countries.filter(function (x) { return !x.roll; }).map(function (x) { return x.iso3; });
      if (waiting.length) c.appendChild(h("p", "b-sub", "Still to answer: " + waiting.slice(0, 18).join(" · ") + (waiting.length > 18 ? " …" : "")));
      rail.appendChild(c);
    } else if (st === "agenda") {
      var a = card("The agenda");
      a.appendChild(h("p", null, S.session.agenda || "The committee is choosing its agenda."));
      rail.appendChild(a);
      if (S.session.draft) { var d = card("Draft resolution"); d.appendChild(h("p", null, S.session.draft)); rail.appendChild(d); }
    } else if (st === "opening_speeches" || st === "floor") {
      rail.appendChild(speakersCard());
      if (st === "floor" && S.motions.length) {
        var m = card("Motions on the floor");
        S.motions.slice(0, 3).forEach(function (x) {
          var box = h("div", "b-motion"); add(box, h("strong", null, x.name + (x.minutes ? " · " + x.minutes + " min" : "")),
            h("p", "b-sub", (x.topic ? x.topic + " · " : "") + "proposed by " + x.by + (x.needs_second ? " · needs a second" : (x.seconded ? " · seconded by " + x.seconded : ""))));
          m.appendChild(box);
        });
        rail.appendChild(m);
      }
      if (S.amendment) {
        var am = card("On the floor: amendment", "b-amend");
        add(am, h("p", "b-sub", S.amendment.label + (S.amendment.by ? " · " + S.amendment.by : "")));
        if (S.amendment.before) am.appendChild(h("p", "b-old", S.amendment.before));
        if (S.amendment.after) am.appendChild(h("p", "b-new", S.amendment.after));
        rail.appendChild(am);
      }
      if (S.placards.length) {
        var pc = card("Placards up");
        pc.appendChild(h("p", null, S.placards.map(function (p) { return p.by; }).join(" · ")));
        rail.appendChild(pc);
      }
    } else if (st === "voting_procedure") {
      if (S.whip) {
        var w = card("Whip count: " + S.whip.title);
        if (S.whip.phase === "open") {
          var called = Object.keys(S.whip.calls).filter(function (k) { return S.whip.calls[k]; }).length;
          add(w, h("p", "b-big", called + " / " + S.countries.length), h("p", null, "countries called. Which way stays hidden until the vote."));
        } else if (S.whip.phase === "locked") w.appendChild(h("p", null, "The class's calls are on the map. The vote decides."));
        else add(w, h("p", "b-big", S.whip.right + " / " + S.whip.judged), h("p", null, "called correctly by the class."));
        rail.appendChild(w);
      }
      if (S.division) {
        var dv = card("Division: " + S.division.title);
        add(dv, h("p", "b-big", S.division.cast + " / " + S.division.total), h("p", null, "votes cast"), bars(S.division.counts, S.division.total));
        if (S.division.veto_by.length) dv.appendChild(h("p", null, "Veto: " + S.division.veto_by.join(", ")));
        rail.appendChild(dv);
      } else if (S.result) {
        var r = card(S.result.passed ? "Passed" : "Failed");
        add(r, h("p", null, S.result.title), bars({ yes: S.result.yes, no: S.result.no, abstain: S.result.abstain }, S.result.yes + S.result.no + S.result.abstain),
          h("p", "b-sub", S.result.summary));
        rail.appendChild(r);
      }
    } else if (st === "debrief") {
      var db = S.debrief;
      var dc = card("How the room voted");
      if (db) {
        add(dc, h("p", "b-big", db.passed ? "Passed" : "Failed"), h("p", null, db.title));
        var counts = { yes: 0, no: 0, abstain: 0 };
        Object.keys(db.votes).forEach(function (k) { if (counts[db.votes[k].vote] !== undefined) counts[db.votes[k].vote]++; });
        dc.appendChild(bars(counts, Object.keys(db.votes).length));
        dc.appendChild(h("p", "b-sub", "Each country on the map is coloured by its vote."));
      } else dc.appendChild(h("p", null, "No resolution vote yet."));
      rail.appendChild(dc);
      if (S.whip && S.whip.phase === "revealed") {
        var wc = card("Reading the room");
        add(wc, h("p", "b-big", S.whip.right + " / " + S.whip.judged), h("p", null, "countries the class called correctly"),
          h("p", "b-sub", "Green ring: called it. Red ring: missed. Your own score is on your laptop."));
        rail.appendChild(wc);
      }
    }
  }

  // ---------- the mode banner, speaker and ticker ----------
  function renderBanner() {
    var m = document.getElementById("b-mode"); m.textContent = "";
    var st = S.stage.code;
    if (S.session.state !== "open") { m.textContent = "Session " + S.session.state; return; }
    if (st === "floor") {
      var names = { formal: "Formal debate", moderated: "Moderated caucus", unmoderated: "Unmoderated caucus", voting: "Voting procedure" };
      m.textContent = names[S.session.mode] || "";
      if (S.session.mode_topic) m.appendChild(h("small", null, S.session.mode_topic));
    } else if (st === "voting_procedure" && S.division) {
      m.textContent = "Division"; m.appendChild(h("small", null, S.division.title));
    }
    document.getElementById("b-agenda").textContent = S.session.agenda ? "Agenda: " + S.session.agenda : "";
    var tk = document.getElementById("b-ticker");
    tk.hidden = !S.news;
    if (S.news) document.getElementById("b-ticker-text").textContent = S.news.headline + (S.news.label ? "  ·  " + S.news.label : "");
  }
  function speakerTimer() {
    var t = (S.timers || []).filter(function (x) { return x.kind === "speaker"; })[0] || (S.timers || []).filter(function (x) { return x.state === "running"; })[0];
    return t || null;
  }
  function renderSpeaker() {
    var box = document.getElementById("b-speaker"), t = speakerTimer();
    var talking = ["opening_speeches", "floor"].indexOf(S.stage.code) >= 0;     // no speaker banner over a vote or the debrief
    var show = talking && (!!S.current || !!(t && t.kind !== "speaker"));
    box.hidden = !show;
    if (!show) return;
    document.getElementById("b-speaker-name").textContent = S.current ? S.current.by : t.label;
    document.getElementById("b-speaker-side").textContent = S.current && S.current.side ? "Speaking " + S.current.side + " the amendment" : "";
    box.querySelector(".b-speaker-tag").textContent = S.current ? "Now speaking" : "Timer";
  }
  function tick() {
    if (!S) return;
    var t = speakerTimer(), el = document.getElementById("b-time"), arc = document.getElementById("b-dial-arc");
    if (!t) { el.textContent = ""; return; }
    var rem = t.remaining - (t.state === "running" ? (Date.now() - fetchedAt) / 1000 : 0);
    var a = Math.abs(rem), mm = Math.floor(a / 60), ss = Math.floor(a % 60);
    el.textContent = (rem < 0 ? "+" : "") + mm + ":" + (ss < 10 ? "0" : "") + ss;
    el.classList.toggle("over", rem < 0);
    var frac = Math.max(0, Math.min(1, rem / Math.max(1, t.total)));
    arc.style.strokeDashoffset = String(100 - frac * 100);
    arc.classList.toggle("warn", rem >= 0 && rem <= Math.min(30, t.total * .25));
    arc.classList.toggle("over", rem < 0);
  }
  setInterval(tick, 200);

  function renderTrack() {
    document.querySelectorAll("#b-track li").forEach(function (li, i) {
      li.classList.toggle("done", i < S.stage.index);
      li.classList.toggle("now", i === S.stage.index);
    });
  }

  // ---------- moments: what changed since the last look ----------
  function sealOnBoard(passed, label) {
    var boardEl = document.getElementById("b-board");
    var box = h("div", "b-sealbox");
    box.innerHTML = '<svg viewBox="-70 -70 140 140" width="300" height="300" aria-hidden="true"><g class="b-seal"><path class="b-seal-wax" d="M0-60C14-58 20-66 32-56S50-44 56-30 66-12 60 2 66 22 56 34 48 52 34 58 18 66 2 62-14 66-30 58-48 52-56 38-64 20-60 4-66-12-56-28-48-50-34-56-16-62 0-60Z"/><circle class="b-seal-ring" r="44"/><text class="b-seal-text" text-anchor="middle" y="9" font-size="24"></text></g></svg>';
    box.querySelector(".b-seal").classList.add(passed ? "passed" : "failed");
    box.querySelector(".b-seal-text").textContent = label;
    boardEl.appendChild(box);
    play("stamp"); setTimeout(function () { play("gavel", 1); stage.classList.add("shake"); setTimeout(function () { stage.classList.remove("shake"); }, 400); }, 260);
    setTimeout(function () { box.classList.add("gone"); setTimeout(function () { box.remove(); }, 800); }, 6500);
  }
  function revealVote(result, after) {
    glide(WORLD, 900);
    var order = Object.keys(result.votes).sort(function (a, b) { return nameOf(a).localeCompare(nameOf(b)); });
    var step = motion() ? Math.max(70, Math.min(240, 3600 / Math.max(1, order.length))) : 0;
    // Clear the colours, then sweep them back on in roll-call order.
    order.forEach(function (iso) { (lands[iso] || []).forEach(function (p) { clearClasses(p, ["v-", "p-"]); }); if (tokens[iso]) clearClasses(tokens[iso], ["v-"]); });
    order.forEach(function (iso, i) {
      setTimeout(function () {
        var v = result.votes[iso].vote;
        (lands[iso] || []).forEach(function (p) { p.classList.add("v-" + v); });
        var g = tokens[iso];
        if (g) { g.classList.add("v-" + v); g.classList.remove("pop"); void g.getBBox(); g.classList.add("pop"); g.querySelector(".b-line").textContent = { yes: "Yes", no: "No", abstain: "Abstain", absent: "Absent" }[v]; }
        if (i % 2 === 0) play("flip");
      }, 700 + i * step);
    });
    setTimeout(function () {
      sealOnBoard(result.passed, result.passed ? "PASSED" : "FAILED");
      say(result.title + ": " + (result.passed ? "passed" : "failed") + ". " + result.summary);
      if (after) after();
    }, 900 + order.length * step);
  }
  function adoptedMoment(a) {
    var typeMs = motion() ? Math.min(2600, Math.max(600, (a.after || "").length * 22)) : 0;
    moment(function (layer) {
      var sc = scroll(a.friendly ? "Friendly amendment" : "Amendment adopted", a.label, []);
      var old = a.before ? h("p", "b-old", a.before) : null, neu = a.after ? h("p", "b-new", "") : null;
      add(sc, old, neu);
      var stamp = h("div", "b-stamp", "Adopted"); sc.appendChild(stamp);
      layer.appendChild(sc);
      if (old) setTimeout(function () { old.classList.add("struck"); }, 700);
      var start = a.before ? 1500 : 700;
      if (neu) {
        if (typeMs) { var i = 0, n = a.after.length; setTimeout(function t() { i = Math.min(n, i + Math.max(1, Math.round(n / (typeMs / 16)))); neu.textContent = a.after.slice(0, i); if (i < n) setTimeout(t, 16); }, start); }
        else neu.textContent = a.after;
      }
      setTimeout(function () { stamp.classList.add("landed"); play("stamp"); setTimeout(function () { play("gavel", 1); }, 240); }, start + typeMs + 300);
    }, 1500 + typeMs + 3600);
  }

  function changes(P, N) {
    var st = N.stage.code;
    if (P.stage.code !== N.stage.code) {
      play("chime");
      say("Stage " + (N.stage.index + 1) + ": " + N.stage.name);
      moment(function (layer) { layer.appendChild(scroll("Stage " + (N.stage.index + 1) + " of " + N.stage.all.length, N.stage.name, [N.stage.prompt])); }, 4200);
      if (st !== "opening_speeches" && st !== "floor") glide(WORLD, 1400);
    }
    if (N.session.agenda && N.session.agenda !== P.session.agenda) {
      moment(function (layer) { layer.appendChild(scroll("The agenda", N.session.agenda, ["The committee will debate this topic."])); }, 4200);
    }
    // Roll call: each country that answers pops and lights.
    var before = {}; P.countries.forEach(function (c) { before[c.iso3] = c.roll; });
    N.countries.forEach(function (c) {
      if (c.roll && c.roll !== before[c.iso3] && tokens[c.iso3]) {
        var g = tokens[c.iso3]; g.classList.remove("pop"); void g.getBBox(); g.classList.add("pop"); play("flip");
      }
    });
    // A new speaker: the camera glides to them.
    var pc = P.current ? P.current.id : null, nc = N.current ? N.current.id : null;
    if (nc && nc !== pc) { focusOn(N.current.iso3); play("flip"); say("Now speaking: " + N.current.by); }
    if (!nc && pc) glide(WORLD, 1400);
    // A division opens: the bell, and the scroll.
    if (N.division && (!P.division || P.division.id !== N.division.id)) {
      play("division"); glide(WORLD, 900);
      moment(function (layer) { layer.appendChild(scroll("Division", "Voting is open", [N.division.title, "Heads of delegation: vote on your laptop."])); }, 3800);
    }
    // A vote's result: the sweep, then the seal.
    if (N.result && (!P.result || P.result.id !== N.result.id)) revealVote(N.result, paint);
    if (N.news && (!P.news || P.news.id !== N.news.id)) {
      play("news");
      moment(function (layer) {
        layer.appendChild(scroll("", N.news.headline, [N.news.body], function (sc) {
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
      moment(function (layer) { layer.appendChild(scroll("The session is closed", N.session.committee, ["Thank you, delegates."])); }, 6000);
    }
  }

  function fitTitle() {
    var el = document.getElementById("b-committee"), size = 44;
    el.style.fontSize = size + "px";
    while (el.scrollWidth > el.clientWidth && size > 26) { size -= 2; el.style.fontSize = size + "px"; }
  }

  function apply(N, first) {
    var P = S; S = N; fetchedAt = Date.now();
    if (!first && P) changes(P, N);
    renderTrack(); renderBanner(); renderRail(); renderSpeaker(); tick(); if (first) fitTitle();
    var sweeping = !first && P && N.result && (!P.result || P.result.id !== N.result.id);
    if (!sweeping) paint();
    if (first) { if (N.current) focusOn(N.current.iso3); else setView(WORLD); }
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

  apply(JSON.parse(document.getElementById("b-initial").textContent), true);
  connect();
  window.socBoard = { state: function () { return S; }, refresh: refresh };
})();
