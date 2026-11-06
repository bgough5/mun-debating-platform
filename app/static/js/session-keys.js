/* The Session (D-101): hover cards on the map's tokens, and keyboard shortcuts (Ben's picks, 6 Nov 2026).
   Hover or focus a token for a small card: its name, how it leans, your relationship, and what it listens to if you
   know. Keys: E ends the turn, 1-8 open the visible panels in order, T talks to the delegation you have open.
   The game page passes in what this needs (`c`). */
(function () {
  "use strict";
  window.socSession = window.socSession || {};
  window.socSession.mods = window.socSession.mods || {};
  window.socSession.mods.keys = function (c) {
    var $ = c.$, h = c.h;
    var REL = ["Hostile", "Cool", "Neutral", "Warm", "Close"];

    // ---------- hover cards ----------
    var card = h("div", "s-hovercard"); card.setAttribute("role", "tooltip"); card.id = "s-hovercard"; card.hidden = true;
    var stageEl = $("b-stage"); stageEl.appendChild(card);
    var shownFor = null;
    function show(tok) {
      var v = c.view(); if (!v) return;
      var iso = tok.getAttribute("data-iso"), t = v.tokens[iso]; if (!t) return;
      if (shownFor === iso && !card.hidden) return;
      shownFor = iso; card.textContent = "";
      card.appendChild(h("b", "", t.name + (t.p5 ? " ★" : "")));
      var lines = [];
      if (t.you) lines.push("Your delegation");
      else if (t.rival) lines.push(t.truce ? "Rival, at peace with you" : "Rival delegation");
      else {
        lines.push(t.est === "yes" ? "Likely for your draft" : t.est === "no" ? "Likely against your draft" : t.est ? "Unsure about your draft" : "No draft yet");
        if (t.relation !== undefined) lines.push("Relationship: " + REL[t.relation + 2]);
        if (t.listens_to && t.listens_to.length) lines.push("Listens to " + t.listens_to.join(" and ").toLowerCase());
        if (t.talked && t.talked.length) lines.push("You've talked " + t.talked.map(function (k) { return (v.args[k] || {}).name; }).join(", ").toLowerCase());
      }
      lines.forEach(function (l) { card.appendChild(h("span", "", l)); });
      var sb = stageEl.getBoundingClientRect(), tb = tok.getBoundingClientRect();
      card.hidden = false;
      var w = card.offsetWidth, x = tb.left - sb.left + tb.width / 2 - w / 2, y = tb.top - sb.top - card.offsetHeight - 8;
      if (y < 8) y = tb.bottom - sb.top + 8;
      card.style.left = Math.max(8, Math.min(sb.width - w - 8, x)) + "px"; card.style.top = y + "px";
    }
    function hide() { card.hidden = true; shownFor = null; }
    var map = $("b-map");
    map.addEventListener("mouseover", function (e) { var t = e.target.closest(".b-token"); if (t) show(t); else hide(); });
    map.addEventListener("mouseleave", hide);
    map.addEventListener("focusin", function (e) { var t = e.target.closest(".b-token"); if (t) show(t); });
    map.addEventListener("focusout", hide);
    map.addEventListener("click", hide);

    // ---------- shortcuts ----------
    function typing(el) { return el && (el.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName)); }
    function busy() { return document.querySelector(".s-overlay:not([hidden])") || !$("s-walk").hidden; }
    document.addEventListener("keydown", function (e) {
      if (e.ctrlKey || e.metaKey || e.altKey || typing(document.activeElement) || busy()) return;
      var v = c.view(); if (!v || v.phase === "done") return;
      var k = e.key.toLowerCase();
      if (k === "e" && v.phase === "chapter") { var et = $("s-end-turn"); if (et && !et.hidden && !et.disabled) { e.preventDefault(); et.click(); } return; }
      if (/^[1-8]$/.test(k)) {
        var shown = c.TABS.filter(function (t) { var b = $("t-" + t); return b && !b.hidden; });
        var name = shown[+k - 1]; if (name) { e.preventDefault(); c.setTab(name, true); c.A.play("flip"); }
        return;
      }
      if (k === "t" && v.phase === "chapter") {
        var iso = c.picked(); var t = iso && v.tokens[iso];
        if (t && !t.rival && !t.you) { e.preventDefault(); c.talk(iso); }
      }
    });
    return { hide: hide };
  };
})();
