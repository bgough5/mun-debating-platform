/* The Session (D-101, phase 13): delegates come to talk to you (one at a time, after the turn's reel and now and
   then after a move), the whip sheet (who you think is for or against each clause; free, scored at the summit) and
   the Powers panel (who is strong). The game page passes in what this needs (`c`). */
(function () {
  "use strict";
  window.socSession = window.socSession || {};
  window.socSession.mods = window.socSession.mods || {};
  window.socSession.mods.dialogue = function (c) {
    var $ = c.$, h = c.h, A = c.A, G = c.G;
    function FX() { return window.socSession.fx || { react: function () {} }; }
    // a face reacts to what was just said: its expression, then a nod, a shake or a raised brow
    function reactIn(holder, expr, how, wait) {
      var svg = holder && holder.querySelector("svg.g-face"); if (!svg) return;
      if (expr && G) G.face(svg, expr);
      setTimeout(function () { FX().react(svg, how); }, wait || 250);
    }

    // ---------- conversations ----------
    var seen = {}, queue = [], showing = null, waiting = null, line = null;
    // speaking (9 Nov): the line writes itself out; the answers appear when it's done, or at once with the skip button
    function say(face, el, text, row, key) {
      if (line) line.finish();
      el.textContent = "";
      var svg = face && face.querySelector("svg.g-face");
      row.hidden = true;
      var skip = $("s-visit-skip"); if (skip) skip.hidden = false;
      line = G && G.speak ? G.speak(svg, el, text, function () { row.hidden = false; if (skip) skip.hidden = true; line = null;
        var first = row.querySelector("button:not([disabled])"); if (first && !$("s-visit").hidden) first.focus(); }, { pitch: G.voiceOf(key) }) : null;
      if (!line) { el.textContent = text; row.hidden = false; if (skip) skip.hidden = true; }
    }
    function finishLine() { if (line) { line.finish(); return true; } return false; }
    // a talk's result ("Your arguments: … landed") belongs to that talk alone: clear it before any other card is drawn
    function clearIntel() { document.querySelectorAll("#s-visit .s-intel-box").forEach(function (x) { x.remove(); }); }
    // a delegate's look, the same every game (the same sum as visits.likeness in Python): respectful variety only
    function likeness(iso) {
      var n = 0; for (var i = 0; i < iso.length; i++) n += (i + 7) * iso.charCodeAt(i);
      var NATURAL = [0, 1, 3, 4, 5, 6, 2], look = Math.floor(n / 17) % 2 ? "dl-gf" : "dl-gm";   // the same as visits.likeness
      return ["dl-k" + n % 7, "dl-h" + Math.floor(n / 7) % 8, "dl-w" + NATURAL[Math.floor(n / 56) % NATURAL.length],
              Math.floor(n / 392) % 3 === 0 ? "dl-e1" : "", "dl-t" + Math.floor(n / 11) % 4, "dl-j" + Math.floor(n / 13) % 6, look,
              look === "dl-gm" ? "dl-f" + Math.floor(n / 19) % 4 : ""].filter(Boolean).join(" ");
    }
    // the country's flag, as a lapel pin, copied from its token on the map
    function pin(iso) {
      var src = document.querySelector('#b-map .b-token[data-iso="' + iso + '"] .b-flag g[transform^="scale"]');
      var box = h("span", "s-pin"); box.setAttribute("aria-hidden", "true");
      if (!src) return box;
      var svg = document.createElementNS("http://www.w3.org/2000/svg", "svg"); svg.setAttribute("viewBox", "0 0 24 18");
      svg.setAttribute("preserveAspectRatio", "none");
      Array.prototype.forEach.call(src.childNodes, function (n) { svg.appendChild(n.cloneNode(true)); });
      box.appendChild(svg); return box;
    }
    function portraitOf(x, mood) {
      if (!G) return null;
      if (x.who === "minister") return G.portrait(mood, "minister");
      if (x.who === "press") return G.portrait(mood, "delegate dl-k2 dl-h2 dl-w1 dl-t1");
      if (x.who === "staff") return null;                         // your adviser: their own icon is in the Staff panel
      return G.portrait(mood, "delegate " + x.face);
    }
    function offer(v) {
      if (v.question && v.phase === "chapter" && !seen["q:" + v.turn + ":" + v.chapter + ":" + v.question.id]) {   // the President's question first
        seen["q:" + v.turn + ":" + v.chapter + ":" + v.question.id] = true; queue.unshift("q:" + v.question.id);
      }
      if (A.settings().talk === false) { next(); return; }          // conversations switched off in Settings
      (v.visits || []).forEach(function (x) { if (!seen[x.id]) { seen[x.id] = true; if (x.step > 1) queue.unshift(x.id); else queue.push(x.id); } });
      next();
    }
    var HEAD = { press: "A word in your ear", ally: "A friend at your shoulder", ask: "A quiet question", info: "Something to sell",
      caucus: "The caucus: your address", capital: "A call from your capital", offer: "A deal at your door",
      ultimatum: "An ultimatum", bargain: "A bloc's bargain", mediate: "A dispute to settle", leak: "In confidence",
      old_sins: "The press remembers", confront: "Called to account", olive: "An olive branch", staff: "Your staff", media: "The press", collect: "A promise to keep", persuade: "Make the case" };
    var MOOD = { confront: "concerned", ultimatum: "concerned", bargain: "calm", mediate: "thinking", leak: "wry", old_sins: "eyebrow", olive: "calm", staff: "calm", offer: "wry", press: "eyebrow", ally: "delighted", ask: "thinking", info: "wry", caucus: "calm", capital: "eyebrow", media: "wry", collect: "calm", persuade: "thinking" };
    function next() {
      if (showing || waiting || !queue.length) return;
      if (document.querySelector(".s-overlay:not([hidden])") || !$("s-walk").hidden) { setTimeout(next, 700); return; }
      var v = c.view(), id = queue.shift();
      if (id.indexOf("q:") === 0) { if (v.question) procedure(v); else next(); return; }
      var x = (v.visits || []).filter(function (y) { return y.id === id; })[0];
      if (!x) { next(); return; }
      showing = x.id;
      clearIntel();
      var doc = document.querySelector("#s-visit .s-doc");
      doc.className = "s-doc s-reeldoc k-" + x.kind;
      var face = $("s-visit-face"); face.textContent = ""; face.classList.toggle("s-visit-pair", x.kind === "press");
      var mood = x.step > 1 ? (x.kind === "press" ? "concerned" : "thinking") : MOOD[x.kind];
      var them = portraitOf(x, mood); if (them) face.appendChild(them);
      if (x.who === "staff") { var adv = (v.staff || []).filter(function (s) { return s.id === x.adviser; })[0];   // your adviser's own icon (10 Nov)
        if (adv) face.appendChild(c.staffIcon(adv.kind, adv.stars, 120)); }
      if (x.kind === "press" && G && v.you) {                      // face to face, across the table
        face.appendChild(h("span", "s-vs", "and"));
        var mine = window.socSession.avatar && window.socSession.avatar();          // your own ambassador, if you built one
        var me = G.portrait("calm", "delegate you " + (mine || likeness(v.you.iso3))); me.setAttribute("aria-label", "You"); face.appendChild(me);
      }
      if (x.feeling) face.appendChild(h("span", "s-feel f-" + x.feeling.toLowerCase(), x.feeling));
      var who = $("s-visit-who"); who.textContent = "";
      if (!x.who) who.appendChild(pin(x.iso3));
      who.appendChild(document.createTextNode(x.name + (x.kind === "press" ? " · a rival" : x.kind === "caucus" ? " · coordinator" : "")));
      $("s-visit-step").textContent = x.step > 1 ? "Reply " + (x.step - 1) : "";
      $("s-visit-h").textContent = x.step > 1 ? "They answer" : HEAD[x.kind];
      var room = $("s-visit-room"); room.textContent = ""; room.hidden = !(x.room && x.room.length);
      (x.room || []).forEach(function (m) {
        var card = h("div", "s-member"); card.setAttribute("data-iso", m.iso3);
        if (G) card.appendChild(G.portrait("calm", "delegate " + m.face));
        var nm = h("b"); nm.appendChild(pin(m.iso3)); nm.appendChild(document.createTextNode(m.name)); card.appendChild(nm);
        card.appendChild(h("span", "s-feel f-" + m.feeling.toLowerCase(), m.feeling));
        room.appendChild(card);
      });
      var row = $("s-visit-opts"); row.textContent = ""; row.classList.remove("s-cards5");
      x.options.forEach(function (o, i) {
        var b = h("button", "s-btn ghost", o.label + (o.cost ? " (" + o.cost + " Influence)" : "")); b.type = "button";     // every answer alike (10 Nov)
        if ((o.cost && v.influence < o.cost) || (o.ap && v.ap < o.ap)) b.disabled = true;
        b.addEventListener("click", function () { answer(x, o.code); });
        row.appendChild(b);
      });
      $("s-visit-n").textContent = queue.length ? queue.length + " more waiting to see you" : "";
      c.open("s-visit"); c.restart(doc, "s-reel-in"); A.play(x.kind === "capital" ? "tick" : "paper");
      say(face, $("s-visit-p"), x.text, row, x.who || x.iso3);
    }
    function answer(x, code) {
      c.close("s-visit"); showing = null; waiting = x.id;
      c.move({ do: "visit", id: x.id, choice: code });
      setTimeout(function () { if (waiting === x.id) { waiting = null; next(); } }, 4000);   // if the move failed
    }
    var skipBtn = $("s-visit-skip");
    if (skipBtn) skipBtn.addEventListener("click", function () { finishLine(); });
    $("s-visit-p").addEventListener("click", function () { finishLine(); });
    $("s-visit").addEventListener("keydown", function (e) {
      if (e.key === "Enter" && line) { e.preventDefault(); finishLine(); }      // Space: session-keys.js
    });
    $("s-visit").addEventListener("keydown", function (e) {           // Escape ends it politely: the last answer
      if (e.key === "Escape") { e.stopPropagation(); var v = c.view(), x = (v.visits || []).filter(function (y) { return y.id === showing; })[0];
        if (x) answer(x, x.options[x.options.length - 1].code); else if (showing === "talk") leaveTalk(); else if (showing) leave(); }
    });
    function leave() { c.close("s-visit"); showing = null; setTimeout(next, 400); }
    // after you answer: the room's reactions (caucus), their reply, or straight on to whoever is next
    function after(v, out) {
      waiting = null;
      if (out && out.continues) { next(); return; }
      if (!out || !(out.reactions || out.reply)) { setTimeout(next, 500); return; }
      clearIntel();
      var room = $("s-visit-room"); room.textContent = ""; room.hidden = !out.reactions;
      Object.keys(out.reactions || {}).forEach(function (iso, i) {
        var r = out.reactions[iso], card = h("div", "s-member r-" + r.reaction); card.style.animationDelay = (i * 0.12) + "s";
        if (G) card.appendChild(G.portrait(r.reaction === "pleased" ? "delighted" : r.reaction === "annoyed" ? "concerned" : "calm", "delegate " + likeness(iso)));
        var nm = h("b"); nm.appendChild(pin(iso)); nm.appendChild(document.createTextNode(r.name)); card.appendChild(nm);
        card.appendChild(h("span", "s-feel f-" + r.feeling.toLowerCase(), r.reaction + " · " + r.feeling));
        if (r.said) card.appendChild(h("q", "s-member-said", r.said));
        room.appendChild(card);
        reactIn(card, null, r.reaction === "pleased" ? "nod" : r.reaction === "annoyed" ? "shake" : "brow", 500 + i * 160);
      });
      var doc =document.querySelector("#s-visit .s-doc"); doc.className = "s-doc s-reeldoc" + (out.reactions ? " k-caucus" : "");
      $("s-visit-face").textContent = "";
      $("s-visit-step").textContent = ""; $("s-visit-who").textContent = "";
      $("s-visit-h").textContent = out.reactions ? "How the room took it" : "Their reply";
      $("s-visit-p").textContent = out.reply || "";
      var row = $("s-visit-opts"); row.textContent = "";
      var ok = h("button", "s-btn", out.reactions ? "Leave the caucus" : "Carry on"); ok.type = "button";
      ok.addEventListener("click", leave);
      row.appendChild(ok); showing = "reply"; c.open("s-visit"); A.play("chime");
    }

    // ---------- the whip sheet ----------
    var CYCLE = { "": "yes", yes: "abstain", abstain: "no", no: "" }, SHORT = { yes: "Y", abstain: "A", no: "N", "": "·" };
    function sheet(v) {
      var box = $("c-sheet"); if (!box) return;
      box.textContent = "";
      var cols = v.draft.map(function (cl, i) { return [cl.id, "C" + (i + 1)]; }).concat([["final", "Whole"]]);
      var t = h("table", "s-sheet-t"), hr = h("tr");
      hr.appendChild(h("th", "", "Delegation"));
      cols.forEach(function (col) { var th = h("th", "", col[1]); th.title = col[0] === "final" ? "The whole resolution" : "Clause " + col[1].slice(1); hr.appendChild(th); });
      t.appendChild(hr);
      Object.keys(v.tokens).filter(function (k) { return !v.tokens[k].you; })
        .sort(function (a, b) { return v.tokens[a].name < v.tokens[b].name ? -1 : 1; }).forEach(function (iso) {
          var tr = h("tr", v.tokens[iso].rival ? "rival" : "");
          tr.appendChild(h("th", "", v.tokens[iso].name));
          cols.forEach(function (col) {
            var cur = ((v.sheet || {})[col[0]] || {})[iso] || "";
            var td = h("td"), b = h("button", "s-mark " + (cur || "none"), SHORT[cur]); b.type = "button";
            b.setAttribute("aria-label", v.tokens[iso].name + ", " + (col[0] === "final" ? "whole resolution" : "clause " + col[1].slice(1)) + ": " + (cur || "not marked"));
            b.addEventListener("click", function () { c.move({ do: "mark", iso3: iso, clause: col[0], vote: CYCLE[cur] || null }); A.play("tick"); });
            td.appendChild(b); tr.appendChild(td);
          });
          t.appendChild(tr);
        });
      box.appendChild(t);
    }

    // ---------- the Powers panel ----------
    function powers(v) {
      var ul = $("c-powers"); if (!ul) return;
      ul.textContent = "";
      var maxI = Math.max.apply(null, (v.powers || []).map(function (p) { return p.influence; }).concat([1]));
      (v.powers || []).forEach(function (p) {
        var li = h("li", "s-power" + (p.who === "you" ? " you" : "") + (p.truce ? " truce" : ""));
        var hd = h("p", "s-power-h"); hd.appendChild(h("b", "", p.name)); if (p.style) hd.appendChild(h("span", "s-style", p.truce ? "At peace" : p.style)); li.appendChild(hd);
        function bar(label, val, max, txt) {
          var r = h("div", "s-pbar"); r.appendChild(h("span", "", label));
          var tr = h("i"), f = h("b"); f.style.width = Math.min(100, 100 * val / Math.max(1, max)) + "%"; tr.appendChild(f); r.appendChild(tr);
          r.appendChild(h("em", "", txt)); return r;
        }
        li.appendChild(bar("Influence", p.influence, maxI, String(p.influence)));
        li.appendChild(bar("Share of the draft", p.share, 1, Math.round(p.share * 100) + "%"));
        li.appendChild(h("p", "s-small", p.endorsements + " regional group" + (p.endorsements === 1 ? "" : "s") + " · " + p.sponsors + " sponsor" + (p.sponsors === 1 ? "" : "s") +
                         (p.moves !== null ? " · " + p.moves + " move" + (p.moves === 1 ? "" : "s") + " last turn" : "")));
        ul.appendChild(li);
      });
    }
    // ---------- the President's procedure question (it has its own window since 8 Nov) ----------
    function procedure(v) {
      showing = "proc";
      var face = $("s-proc-face"); face.textContent = ""; if (G) face.appendChild(G.portrait("thinking", "president"));
      $("s-proc-h").textContent = "A point of procedure";
      var row = $("s-proc-opts"); row.textContent = "";
      v.question.options.forEach(function (o, k) {
        var b = h("button", "s-btn ghost", o); b.type = "button";
        b.addEventListener("click", function () { c.move({ do: "answer", option: k }); });
        row.appendChild(b);
      });
      c.open("s-proc"); c.restart(document.querySelector("#s-proc .s-doc"), "s-reel-in"); A.play("gavel");
      $("s-proc-p").textContent = "";
      var sk = $("s-proc-skip"); if (sk) sk.hidden = true;
      if (G && G.speak) { row.hidden = true; if (sk) sk.hidden = false;
        procLine = G.speak(face.querySelector("svg"), $("s-proc-p"), v.question.ask, function () { row.hidden = false; if (sk) sk.hidden = true; }, { pitch: G.voiceOf("president") }); }
      else $("s-proc-p").textContent = v.question.ask;
    }
    function procAnswer(out) {
      if (!out || out.right === undefined) return;
      var face = $("s-proc-face"); face.textContent = ""; if (G) face.appendChild(G.portrait(out.right ? "delighted" : "concerned", "president"));
      $("s-proc-h").textContent = out.right ? "Correct" : "Not quite";
      $("s-proc-p").textContent = (out.right ? "" : "The answer: " + out.answer + ". ") + out.why;
      var row = $("s-proc-opts"); row.textContent = "";
      var ok = h("button", "s-btn", "Thank you, Mr President"); ok.type = "button";
      ok.addEventListener("click", function () { c.close("s-proc"); showing = null; setTimeout(next, 400); });
      row.appendChild(ok); A.play(out.right ? "chime" : "tick");
      reactIn(face, null, out.right ? "nod" : "shake");
    }
    $("s-proc").addEventListener("keydown", function (e) { if (e.key === "Escape") e.stopPropagation(); });   // answer it, or it waits
    var procLine = null, procSkip = $("s-proc-skip");                 // Skip ahead on the President's question (10 Nov)
    if (procSkip) procSkip.addEventListener("click", function () { if (procLine) procLine.finish(); });

    // ---------- talking with a delegation (Ben, 6 Nov): open with an argument, they react, you take it on ----------
    var talking = null;
    function talkFrame(iso, h2, text) {
      var v = c.view(), t = v.tokens[iso];
      clearIntel();
      var doc = document.querySelector("#s-visit .s-doc"); doc.className = "s-doc s-reeldoc k-talk";
      var face = $("s-visit-face"); face.textContent = ""; face.classList.remove("s-visit-pair");
      if (G) face.appendChild(G.portrait(h2 === "Their answer" ? "calm" : "thinking", "delegate " + likeness(iso)));
      var rel = t && t.relation !== undefined ? ["Hostile", "Cool", "Neutral", "Warm", "Close"][t.relation + 2] : null;
      if (rel) face.appendChild(h("span", "s-feel f-" + rel.toLowerCase(), rel));
      var who = $("s-visit-who"); who.textContent = ""; who.appendChild(pin(iso)); who.appendChild(document.createTextNode(t ? t.name : iso));
      $("s-visit-step").textContent = ""; $("s-visit-h").textContent = h2; $("s-visit-p").textContent = text;
      var room = $("s-visit-room"); room.textContent = ""; room.hidden = true;
      $("s-visit-n").textContent = "";
      var row = $("s-visit-opts"); row.textContent = ""; row.classList.remove("s-cards5"); return row;
    }
    function talk(iso) {                                               // open (or return to) a conversation
      var v = c.view(); if (!v || showing) return;
      talking = iso; showing = "talk";
      if (v.conv && v.conv.iso3 === iso) { talkReply(v.conv); return; }
      var d = v.tokens[iso];
      var row = talkFrame(iso, "What will you open with?", (d.listens_to && d.listens_to.length ? "From its file, it listens to " + d.listens_to.join(" and ").toLowerCase() + ". " : "") +
        "Choose the argument you lead with. Watch how they take it: where you go next decides how far they move.");
      row.classList.add("s-cards5");
      Object.keys(v.args).forEach(function (k) {
        var known = d.listens_to && d.listens_to.indexOf(v.args[k].name) >= 0, used = (d.talked || []).indexOf(k) >= 0;
        var b = h("button", "s-btn ghost s-argcard" + (known ? " known" : "") + (used ? " used" : "")); b.type = "button";
        b.appendChild(h("b", "", v.args[k].name)); b.appendChild(h("span", "", v.args[k].what));
        if (used) b.appendChild(h("em", "", "You've used this with them"));
        b.addEventListener("click", function () { c.move({ do: "talk", step: "open", iso3: iso, arg: k }); A.play("paper"); });
        row.appendChild(b);
      });
      var back = h("button", "s-btn ghost small", "Not now"); back.type = "button";
      back.addEventListener("click", leaveTalk); row.appendChild(back);
      c.open("s-visit"); c.restart(document.querySelector("#s-visit .s-doc"), "s-reel-in"); A.play("paper");
    }
    function talkReply(cv) {
      var row = talkFrame(cv.iso3, "They react", "");
      cv.options.forEach(function (o, i) {
        var b = h("button", "s-btn ghost", o.label); b.type = "button";      // every answer alike (10 Nov)
        b.addEventListener("click", function () { c.move({ do: "talk", step: "follow", choice: o.code }); A.play("paper"); });
        row.appendChild(b);
      });
      if ($("s-visit").hidden) c.open("s-visit");
      say($("s-visit-face"), $("s-visit-p"), "You opened with " + cv.first_name.toLowerCase() + ". \u201c" + cv.reply + "\u201d", row, cv.iso3);
      var T = { strong: ["delighted", "nod"], some: ["thinking", "brow"], weak: ["concerned", "shake"], red: ["concerned", "shake"] }[cv.tone];
      if (T) reactIn($("s-visit-face"), T[0], T[1]);
    }
    function talkEnd(v, out) {
      var iso = out.talked, t = v.tokens[iso] || {};
      var row = talkFrame(iso, "Their answer", "");
      var p = $("s-visit-p");
      var ok = h("button", "s-btn", "Done"); ok.type = "button"; ok.addEventListener("click", leaveTalk); row.appendChild(ok);
      if ($("s-visit").hidden) c.open("s-visit");
      say($("s-visit-face"), p, "\u201c" + out.heard + "\u201d", row, iso);
      if (out.q !== undefined) reactIn($("s-visit-face"), out.q >= 0.9 ? "delighted" : out.q >= 0.5 ? "eyebrow" : "concerned",
                                       out.q >= 0.9 ? "smile" : out.q >= 0.5 ? "brow" : "shake");
      var intel = h("span", "s-intel-box");
      var landed = TALKS().pitchAnswer(out); if (landed) intel.appendChild(h("span", "s-intel", "Your arguments: " + landed));
      if (out.would_vote) intel.appendChild(h("span", "s-intel", "On the whole text as it stands: " + (out.would_says || out.would_vote) + "."));
      if (out.leans) intel.appendChild(h("span", "s-intel", "Towards each rival: " + Object.keys(out.leans).map(function (k) { return k + " " + (out.leans[k] > 0.3 ? "warm" : out.leans[k] < -0.3 ? "cold" : "neutral"); }).join(", ") + "."));
      row.parentNode.insertBefore(intel, row);
      A.play(out.moved > 0.2 ? "chime" : "tick");
    }
    function leaveTalk() { c.close("s-visit"); showing = null; talking = null; setTimeout(next, 400); }
    function TALKS() { return c.talks(); }
    // after a talk move: their reaction, or the end of the conversation
    function talkStep(v, out, action) {
      if (action.step === "open" && out && out.conv) { talkReply(out.conv); return; }
      if (out && out.talked) talkEnd(v, out);
    }
    return { offer: offer, procAnswer: procAnswer, sheet: sheet, powers: powers, after: after, talk: talk, talkStep: talkStep, likeness: likeness, pin: pin };
  };
})();
