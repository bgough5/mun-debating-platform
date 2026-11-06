/* The Session (D-101, phase 13): delegates come to talk to you (one at a time, after the turn's reel and now and
   then after a move), the whip sheet (who you think is for or against each clause; free, scored at the summit) and
   the Powers panel (who is strong). The game page passes in what this needs (`c`). */
(function () {
  "use strict";
  window.socSession = window.socSession || {};
  window.socSession.mods = window.socSession.mods || {};
  window.socSession.mods.dialogue = function (c) {
    var $ = c.$, h = c.h, A = c.A, G = c.G;

    // ---------- conversations ----------
    var seen = {}, queue = [], showing = null, waiting = null;
    // a delegate's look, the same every game (the same sum as visits.likeness in Python): respectful variety only
    function likeness(iso) {
      var n = 0; for (var i = 0; i < iso.length; i++) n += (i + 7) * iso.charCodeAt(i);
      return ["k" + n % 5, "h" + Math.floor(n / 5) % 5, "w" + Math.floor(n / 25) % 3, Math.floor(n / 75) % 3 === 0 ? "gl" : "", "t" + Math.floor(n / 7) % 4]
        .filter(Boolean).join(" ");
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
      if (x.who === "press") return G.portrait(mood, "delegate k2 h2 w1 t1");
      return G.portrait(mood, "delegate " + x.face);
    }
    function offer(v) {
      if (A.settings().talk === false) return;                      // switched off in Settings
      (v.visits || []).forEach(function (x) { if (!seen[x.id]) { seen[x.id] = true; if (x.step > 1) queue.unshift(x.id); else queue.push(x.id); } });
      next();
    }
    var HEAD = { press: "A word in your ear", ally: "A friend at your shoulder", ask: "A quiet question", info: "Something to sell",
      caucus: "The caucus: your address", capital: "A call from your capital", media: "The press", collect: "A promise to keep", persuade: "Make the case" };
    var MOOD = { press: "eyebrow", ally: "delighted", ask: "thinking", info: "wry", caucus: "calm", capital: "eyebrow", media: "wry", collect: "calm", persuade: "thinking" };
    function next() {
      if (showing || waiting || !queue.length) return;
      if (document.querySelector(".s-overlay:not([hidden])") || !$("s-walk").hidden) { setTimeout(next, 700); return; }
      var v = c.view(), id = queue.shift(), x = (v.visits || []).filter(function (y) { return y.id === id; })[0];
      if (!x) { next(); return; }
      showing = x.id;
      var doc = document.querySelector("#s-visit .s-doc");
      doc.className = "s-doc s-reeldoc k-" + x.kind;
      var face = $("s-visit-face"); face.textContent = ""; face.classList.toggle("s-visit-pair", x.kind === "press");
      var mood = x.step > 1 ? (x.kind === "press" ? "concerned" : "thinking") : MOOD[x.kind];
      var them = portraitOf(x, mood); if (them) face.appendChild(them);
      if (x.kind === "press" && G && v.you) {                      // face to face, across the table
        face.appendChild(h("span", "s-vs", "and"));
        var me = G.portrait("calm", "delegate you " + likeness(v.you.iso3)); me.setAttribute("aria-label", "You"); face.appendChild(me);
      }
      if (x.feeling) face.appendChild(h("span", "s-feel f-" + x.feeling.toLowerCase(), x.feeling));
      var who = $("s-visit-who"); who.textContent = "";
      if (!x.who) who.appendChild(pin(x.iso3));
      who.appendChild(document.createTextNode(x.name + (x.kind === "press" ? " · a rival" : x.kind === "caucus" ? " · coordinator" : "")));
      $("s-visit-step").textContent = x.step > 1 ? "Reply " + (x.step - 1) : "";
      $("s-visit-h").textContent = x.step > 1 ? "They answer" : HEAD[x.kind];
      $("s-visit-p").textContent = x.text;
      var room = $("s-visit-room"); room.textContent = ""; room.hidden = !(x.room && x.room.length);
      (x.room || []).forEach(function (m) {
        var card = h("div", "s-member"); card.setAttribute("data-iso", m.iso3);
        if (G) card.appendChild(G.portrait("calm", "delegate " + m.face));
        var nm = h("b"); nm.appendChild(pin(m.iso3)); nm.appendChild(document.createTextNode(m.name)); card.appendChild(nm);
        card.appendChild(h("span", "s-feel f-" + m.feeling.toLowerCase(), m.feeling));
        room.appendChild(card);
      });
      var row = $("s-visit-opts"); row.textContent = "";
      x.options.forEach(function (o, i) {
        var b = h("button", "s-btn" + (i && x.kind !== "persuade" ? " ghost" : ""), o.label + (o.cost ? " (" + o.cost + " Influence)" : "")); b.type = "button";
        if (o.cost && v.influence < o.cost) b.disabled = true;
        b.addEventListener("click", function () { answer(x, o.code); });
        row.appendChild(b);
      });
      $("s-visit-n").textContent = queue.length ? queue.length + " more waiting to see you" : "";
      c.open("s-visit"); c.restart(doc, "s-reel-in"); A.play(x.kind === "capital" ? "tick" : "paper");
    }
    function answer(x, code) {
      c.close("s-visit"); showing = null; waiting = x.id;
      c.move({ do: "visit", id: x.id, choice: code });
      setTimeout(function () { if (waiting === x.id) { waiting = null; next(); } }, 4000);   // if the move failed
    }
    $("s-visit").addEventListener("keydown", function (e) {           // Escape ends it politely: the last answer
      if (e.key === "Escape") { e.stopPropagation(); var v = c.view(), x = (v.visits || []).filter(function (y) { return y.id === showing; })[0];
        if (x) answer(x, x.options[x.options.length - 1].code); else if (showing) leave(); }
    });
    function leave() { c.close("s-visit"); showing = null; setTimeout(next, 400); }
    // after you answer: the room's reactions (caucus), their reply, or straight on to whoever is next
    function after(v, out) {
      waiting = null;
      if (out && out.continues) { next(); return; }
      if (!out || !(out.reactions || out.reply)) { setTimeout(next, 500); return; }
      var room = $("s-visit-room"); room.textContent = ""; room.hidden = !out.reactions;
      Object.keys(out.reactions || {}).forEach(function (iso, i) {
        var r = out.reactions[iso], card = h("div", "s-member r-" + r.reaction); card.style.animationDelay = (i * 0.12) + "s";
        if (G) card.appendChild(G.portrait(r.reaction === "pleased" ? "delighted" : r.reaction === "annoyed" ? "concerned" : "calm", "delegate " + likeness(iso)));
        var nm = h("b"); nm.appendChild(pin(iso)); nm.appendChild(document.createTextNode(r.name)); card.appendChild(nm);
        card.appendChild(h("span", "s-feel f-" + r.feeling.toLowerCase(), r.reaction + " · " + r.feeling));
        room.appendChild(card);
      });
      var doc = document.querySelector("#s-visit .s-doc"); doc.className = "s-doc s-reeldoc" + (out.reactions ? " k-caucus" : "");
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
    return { offer: offer, sheet: sheet, powers: powers, after: after };
  };
})();
