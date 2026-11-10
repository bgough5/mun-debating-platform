/* The Session (D-101): hover cards on the map's tokens, and keyboard shortcuts (Ben's picks, 6 Nov 2026).
   Hover or focus a token for a small card: its name, how it leans, your relationship, and what it listens to if you
   know. Keys (listed in the game on ? and in the pause menu): F full screen, E ends the turn, 1-8 open the visible
   panels in order (or, with a card or conversation open, choose its answers), T talks to the delegation you have
   open, M the map key, and at the Summit Y/A/N vote and Space lets the President move on. Full screen starts on the
   first click or key press (setting `fullscreen`). The game page passes in what this needs (`c`). */
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

    // ---------- full screen, like a game (Ben, 10 Nov) ----------
    // Browsers allow full screen only from a click or key press on this page, so the first one goes full screen.
    // Chrome and Edge then let the game keep Escape (hold it to leave full screen); leaving by choice stops the
    // automatic return until the game is next opened. Automated test browsers are left alone.
    var root = document.documentElement, leftByChoice = false;
    function isFull() { return !!document.fullscreenElement; }
    function enterFull() {
      if (isFull() || !root.requestFullscreen) return;
      root.requestFullscreen({ navigationUI: "hide" }).then(function () {
        if (navigator.keyboard && navigator.keyboard.lock) navigator.keyboard.lock(["Escape"]).catch(function () {});
      }).catch(function () {});
    }
    function toggleFull() { if (isFull()) { leftByChoice = true; document.exitFullscreen().catch(function () {}); } else { leftByChoice = false; enterFull(); } }
    function autoFull(e) {
      if (navigator.webdriver || leftByChoice || isFull() || c.A.settings().fullscreen === false) return;
      if (e.type === "keydown" && (e.key === "Escape" || e.key.toLowerCase() === "f")) return;
      enterFull();
    }
    document.addEventListener("pointerdown", autoFull, true);
    document.addEventListener("keydown", autoFull, true);
    document.addEventListener("fullscreenchange", function () {
      if (!isFull()) { leftByChoice = true; if (navigator.keyboard && navigator.keyboard.unlock) navigator.keyboard.unlock(); }
    });

    // ---------- shortcuts ----------
    function typing(el) { return el && (el.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName)); }
    function topOverlay() {
      var shown = Array.prototype.filter.call(document.querySelectorAll(".s-overlay"), function (o) { return !o.hidden; });
      return shown[shown.length - 1] || null;
    }
    function usable(b) { return b && !b.disabled && !b.hidden && b.offsetParent !== null; }
    // in a conversation, a question or a card: 1-9 choose its answers in order
    function pickInOverlay(o, n) {
      var row = o.querySelector("#s-visit-opts, #s-proc-opts, .s-row, .s-visit-opts");
      var bs = Array.prototype.filter.call((row || o).querySelectorAll("button"), usable);
      var b = bs[n - 1]; if (b) { b.click(); return true; }
      return false;
    }
    var spaceSkipped = false;                                        // a Space that finished a line: its key-up is swallowed too
    document.addEventListener("keyup", function (e) { if (e.key === " " && spaceSkipped) { spaceSkipped = false; e.preventDefault(); } }, true);
    document.addEventListener("keydown", function (e) {
      if (e.ctrlKey || e.metaKey || e.altKey || typing(document.activeElement)) return;
      var k = e.key.toLowerCase(), G = window.socSession.guide;
      if (k === " " && G && G.typing && G.typing()) { e.preventDefault(); spaceSkipped = true; G.skip(); return; }   // Space finishes a line being spoken, wherever focus is
      if (k === "f") { e.preventDefault(); toggleFull(); return; }
      if (k === "?" || (k === "/" && e.shiftKey)) { e.preventDefault(); c.open("s-keys"); return; }
      if (!$("s-walk").hidden) return;
      var o = topOverlay();
      if (o) {
        if (/^[1-9]$/.test(k) && o.id !== "s-settings" && o.id !== "s-keys" && pickInOverlay(o, +k)) e.preventDefault();
        return;
      }
      var v = c.view(); if (!v || v.phase === "done") return;
      if (v.phase !== "chapter" && /^[yan]$/.test(k)) {             // the Summit: vote Yes, Abstain or No
        var vb = document.querySelector("#c-summit .s-votes .v-" + { y: "yes", a: "abstain", n: "no" }[k]);
        if (usable(vb)) { e.preventDefault(); vb.click(); }
        return;
      }
      if (k === " " && document.activeElement && document.activeElement.tagName === "BUTTON") return;   // Space presses that button
      if (k === " " && v.phase !== "chapter") {                       // the Summit: the President moves on
        var go = Array.prototype.filter.call(document.querySelectorAll("#c-summit > .s-btn"), usable)[0];
        if (go) { e.preventDefault(); go.click(); }
        return;
      }
      if (k === "m") { var mk = $("s-key-btn"); if (usable(mk)) { e.preventDefault(); mk.click(); } return; }
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
