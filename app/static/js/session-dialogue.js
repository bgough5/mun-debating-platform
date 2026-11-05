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
    var seen = {}, queue = [], showing = null;
    function offer(v) {
      if (A.settings().talk === false) return;                      // switched off in Settings
      (v.visits || []).forEach(function (x) { if (!seen[x.id]) { seen[x.id] = true; queue.push(x.id); } });
      next();
    }
    function next() {
      if (showing || !queue.length) return;
      if (document.querySelector(".s-overlay:not([hidden])") || !$("s-walk").hidden) { setTimeout(next, 700); return; }
      var v = c.view(), id = queue.shift(), x = (v.visits || []).filter(function (y) { return y.id === id; })[0];
      if (!x) { next(); return; }
      showing = x.id;
      var face = $("s-visit-face"); face.textContent = "";
      var mood = { press: "eyebrow", ally: "delighted", ask: "thinking", info: "wry", caucus: "calm", capital: "eyebrow", media: "wry", collect: "calm", persuade: "thinking" }[x.kind];
      if (G) face.appendChild(G.portrait(mood, x.who === "minister" ? "minister" : "delegate d" + x.face));
      if (x.feeling) face.appendChild(h("span", "s-feel f-" + x.feeling.toLowerCase(), x.feeling));
      $("s-visit-who").textContent = x.name + (x.kind === "press" ? " · a rival" : x.kind === "caucus" ? " · coordinator" : "");
      $("s-visit-h").textContent = { press: "A word in your ear", ally: "A friend at your shoulder", ask: "A quiet question", info: "Something to sell",
        caucus: "The caucus: your address", capital: "A call from your capital", media: "The press", collect: "A promise to keep", persuade: "Make the case" }[x.kind];
      $("s-visit-p").textContent = x.text;
      var room = $("s-visit-room"); room.textContent = ""; room.hidden = !(x.room && x.room.length);
      (x.room || []).forEach(function (m) {
        var card = h("div", "s-member"); card.setAttribute("data-iso", m.iso3);
        if (G) card.appendChild(G.portrait("calm", "delegate d" + m.face));
        card.appendChild(h("b", "", m.name)); card.appendChild(h("span", "s-feel f-" + m.feeling.toLowerCase(), m.feeling));
        room.appendChild(card);
      });
      var row = $("s-visit-opts"); row.textContent = "";
      x.options.forEach(function (o, i) {
        var b = h("button", "s-btn" + (i ? " ghost" : ""), o.label + (o.cost ? " (" + o.cost + " Influence)" : "")); b.type = "button";
        if (o.cost && v.influence < o.cost) b.disabled = true;
        b.addEventListener("click", function () { answer(x, o.code); });
        row.appendChild(b);
      });
      $("s-visit-n").textContent = queue.length ? queue.length + " more waiting to see you" : "";
      c.open("s-visit"); c.restart(document.querySelector("#s-visit .s-doc"), "s-reel-in"); A.play("paper");
    }
    function answer(x, code) {
      c.close("s-visit"); showing = null;
      c.move({ do: "visit", id: x.id, choice: code });
      if (x.kind !== "caucus") setTimeout(next, 900);
    }
    $("s-visit").addEventListener("keydown", function (e) {           // Escape: they'll come back if you walk away? No: it ends politely
      if (e.key === "Escape") { e.stopPropagation(); var v = c.view(), x = (v.visits || []).filter(function (y) { return y.id === showing; })[0];
        if (x) answer(x, x.options[x.options.length - 1].code); }
    });

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
    // after a caucus address: each member's reaction under their face, football-manager style
    function after(v, out) {
      if (!out || !out.reactions) return;
      var room = $("s-visit-room"); room.textContent = ""; room.hidden = false;
      Object.keys(out.reactions).forEach(function (iso, i) {
        var r = out.reactions[iso], card = h("div", "s-member r-" + r.reaction); card.style.animationDelay = (i * 0.12) + "s";
        if (G) card.appendChild(G.portrait(r.reaction === "pleased" ? "delighted" : r.reaction === "annoyed" ? "concerned" : "calm", "delegate d" + (iso.charCodeAt(0) + iso.charCodeAt(1) + iso.charCodeAt(2)) % 4));
        card.appendChild(h("b", "", r.name)); card.appendChild(h("span", "s-feel f-" + r.feeling.toLowerCase(), r.reaction + " · " + r.feeling));
        room.appendChild(card);
      });
      $("s-visit-h").textContent = "How the room took it"; $("s-visit-p").textContent = "";
      var row = $("s-visit-opts"); row.textContent = "";
      var ok = h("button", "s-btn", "Leave the caucus"); ok.type = "button";
      ok.addEventListener("click", function () { c.close("s-visit"); showing = null; setTimeout(next, 400); });
      row.appendChild(ok); showing = "reactions"; c.open("s-visit"); A.play("chime");
    }
    function answering() { return showing; }
    return { offer: offer, sheet: sheet, powers: powers, after: after };
  };
})();
