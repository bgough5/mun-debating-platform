// Small progressive enhancements. Every page works without this file.
(function () {
  "use strict";

  // htmx: swap error pages too, so people see the plain-English message.
  document.addEventListener("DOMContentLoaded", function () {
    if (window.htmx) {
      htmx.config.responseHandling = [
        { code: "204", swap: false },
        { code: "[23]..", swap: true },
        { code: "[45]..", swap: true, error: false },
      ];
      htmx.config.scrollIntoViewOnBoost = false;
    }
    applyEasyRead();
  });

  // After a boosted page change, move focus to the main region and announce the new title.
  // Phone menu (Phase 7 item 5): the button is hidden in the markup so that without JavaScript the list shows.
  function initMenu() {
    document.querySelectorAll(".menu-toggle[hidden]").forEach(function (b) { b.hidden = false; });
  }
  document.addEventListener("DOMContentLoaded", initMenu);

  // Panels that remember whether they were left open, on this laptop (the student's "My country", D-095).
  function rememberPanels() {
    document.querySelectorAll("details[data-remember]").forEach(function (d) {
      if (d._remember) return;
      d._remember = true;
      var key = "open:" + d.getAttribute("data-remember");
      try { if (localStorage.getItem(key) === "1") d.open = true; } catch (err) { /* storage blocked */ }
      d.addEventListener("toggle", function () { try { localStorage.setItem(key, d.open ? "1" : "0"); } catch (err) { /* ignore */ } });
    });
  }
  document.addEventListener("DOMContentLoaded", rememberPanels);

  // A debate ballot shows each speaker's total, each team's total and the margin as the marks go in (D-096).
  // Display only: the server works the totals out again when the ballot is saved.
  function ballotTotals(form) {
    var speakers = {}, teams = {}, complete = true, names = {};
    form.querySelectorAll("input[data-speaker]").forEach(function (i) {
      var v = parseFloat(i.value), w = parseFloat(i.getAttribute("data-weight")) || 1, sp = i.getAttribute("data-speaker"), tm = i.getAttribute("data-team");
      speakers[sp] = speakers[sp] || 0; teams[tm] = teams[tm] || 0;
      if (isNaN(v)) { complete = false; return; }
      speakers[sp] += v * w; teams[tm] += v * w;
    });
    function fmt(n) { return Math.round(n * 10) / 10; }
    Object.keys(speakers).forEach(function (k) { var el = form.querySelector('[data-speaker-total="' + k + '"]'); if (el) el.textContent = fmt(speakers[k]); });
    Object.keys(teams).forEach(function (k) { var el = form.querySelector('[data-team-total="' + k + '"]'); if (el) { el.textContent = fmt(teams[k]); names[k] = el.parentNode.textContent.split(" total")[0]; } });
    var out = form.querySelector("[data-ballot-margin]"), ids = Object.keys(teams);
    if (!out || ids.length !== 2) return;
    if (!complete) { out.textContent = "Fill in every mark to see the margin."; return; }
    var a = teams[ids[0]], b = teams[ids[1]];
    out.textContent = a === b ? "The totals are level: choose the winner below." : (a > b ? names[ids[0]] : names[ids[1]]) + " ahead by " + fmt(Math.abs(a - b)) + ".";
  }
  function initBallots() {
    document.querySelectorAll("form[data-ballot]").forEach(function (f) {
      if (f._ballot) return;
      f._ballot = true;
      f.addEventListener("input", function () { ballotTotals(f); });
      ballotTotals(f);
    });
  }
  document.addEventListener("DOMContentLoaded", initBallots);

  // Start an activity (D-099): only the chosen activity's options show. Without JavaScript every option shows.
  function initStart() {
    document.querySelectorAll("form[data-start]").forEach(function (f) {
      if (f._start) return;
      f._start = true;
      function sync() {
        var k = f.querySelector('input[name="kind"]:checked');
        f.querySelectorAll("[data-for]").forEach(function (el) { el.hidden = !k || el.getAttribute("data-for") !== k.value; });
      }
      f.addEventListener("change", function (e) { if (e.target.name === "kind") sync(); });
      sync();
    });
  }
  document.addEventListener("DOMContentLoaded", initStart);
  document.addEventListener("htmx:load", initStart);
  document.addEventListener("htmx:load", initBallots);
  document.addEventListener("htmx:load", rememberPanels);
  document.addEventListener("htmx:afterSettle", initMenu);
  document.addEventListener("click", function (e) {
    var b = e.target.closest && e.target.closest(".menu-toggle");
    if (b) b.setAttribute("aria-expanded", b.getAttribute("aria-expanded") === "true" ? "false" : "true");
  });
  document.addEventListener("keydown", function (e) {
    if (e.key !== "Escape") return;
    var b = document.querySelector(".menu-toggle[aria-expanded='true']");
    if (b && b.parentNode.contains(document.activeElement)) { b.setAttribute("aria-expanded", "false"); b.focus(); }
  });
  // Tabs (D-068): each tab is a link that works without JavaScript; with it, switching is instant, arrow keys move
  // between tabs, the choice survives live refreshes, and the address keeps ?tab= so a reload returns to it.
  function currentTab(list) {
    var sel = list.querySelector('[role="tab"][aria-selected="true"]');
    return sel ? sel.getAttribute("data-tab") : null;
  }
  function selectTab(list, name, focus) {
    list.querySelectorAll('[role="tab"]').forEach(function (t) {
      var on = t.getAttribute("data-tab") === name;
      t.setAttribute("aria-selected", on ? "true" : "false");
      t.setAttribute("tabindex", on ? "0" : "-1");
      if (on && focus) t.focus();
    });
    applyPanels(name);
    document.querySelectorAll("[data-tab-aware]").forEach(function (el) {
      var u = el.getAttribute("hx-get");
      if (u) el.setAttribute("hx-get", u.replace(/([?&])tab=[^&]*/, "$1tab=" + name));
    });
    try {
      var url = new URL(location.href);
      url.searchParams.set("tab", name);
      history.replaceState(history.state, "", url.toString());
    } catch (err) { /* old browsers: the tab still works */ }
  }
  function applyPanels(name) {
    document.querySelectorAll("[data-panel]").forEach(function (p) { p.hidden = p.getAttribute("data-panel") !== name; });
  }
  document.addEventListener("click", function (e) {
    var t = e.target.closest && e.target.closest('[data-tabs] [role="tab"]');
    if (!t) return;
    e.preventDefault();
    selectTab(t.closest("[data-tabs]"), t.getAttribute("data-tab"), false);
  });
  document.addEventListener("keydown", function (e) {
    var t = e.target.closest && e.target.closest('[data-tabs] [role="tab"]');
    if (!t) return;
    var tabs = Array.prototype.slice.call(t.closest("[data-tabs]").querySelectorAll('[role="tab"]'));
    var i = tabs.indexOf(t), j = null;
    if (e.key === "ArrowRight") j = (i + 1) % tabs.length;
    else if (e.key === "ArrowLeft") j = (i - 1 + tabs.length) % tabs.length;
    else if (e.key === "Home") j = 0;
    else if (e.key === "End") j = tabs.length - 1;
    else if (e.key === " " || e.key === "Enter") { e.preventDefault(); selectTab(t.closest("[data-tabs]"), t.getAttribute("data-tab"), true); return; }
    if (j === null) return;
    e.preventDefault();
    selectTab(t.closest("[data-tabs]"), tabs[j].getAttribute("data-tab"), true);
  });
  document.addEventListener("htmx:afterSwap", function () {
    var list = document.querySelector("[data-tabs]");
    if (list && currentTab(list)) applyPanels(currentTab(list));
  });
  // Page changes (D-078): a new page starts at the top; saving a form that comes back to the same page keeps the
  // reader exactly where they were, and the confirmation appears as a toast instead of out of sight at the top.
  var boostFrom = null;
  document.addEventListener("htmx:beforeRequest", function (e) {
    if (e.detail && e.detail.boosted) boostFrom = { path: location.pathname, y: window.scrollY };
  });
  document.addEventListener("htmx:afterSettle", function (e) {
    if (e.detail && e.detail.boosted) {
      var main = document.getElementById("main");
      var same = boostFrom && boostFrom.path === location.pathname;
      if (main) main.focus({ preventScroll: true });
      if (same) {
        window.scrollTo(0, boostFrom.y);
        var flash = document.querySelector("#main > .flash");
        if (flash && window.socToast) window.socToast(flash.textContent.trim());
      } else if (location.hash && document.getElementById(location.hash.slice(1))) {
        document.getElementById(location.hash.slice(1)).scrollIntoView();
      } else {
        window.scrollTo(0, 0);
      }
      boostFrom = null;
    }
    applyEasyRead();
  });

  function applyEasyRead() {
    var on = false;
    try { on = localStorage.getItem("easyRead") === "1"; } catch (err) { /* storage blocked */ }
    document.body.classList.toggle("easy-read", on);
    var btn = document.getElementById("easy-read-toggle");
    if (btn) btn.setAttribute("aria-pressed", on ? "true" : "false");
  }

  // Toasts: short confirmations in a polite live region. They stay until dismissed or 8 s pass,
  // and never carry the only copy of something important (that goes in the page).
  window.socToast = function (message) {
    var box = document.getElementById("toasts");
    if (!box) return;
    var t = document.createElement("div");
    t.className = "toast";
    var text = document.createElement("span");
    text.textContent = message;
    var close = document.createElement("button");
    close.type = "button";
    close.textContent = "Dismiss";
    close.addEventListener("click", function () { t.remove(); });
    t.appendChild(text);
    t.appendChild(close);
    box.appendChild(t);
    setTimeout(function () { t.remove(); }, 8000);
  };
  document.body && document.body.addEventListener("htmx:afterRequest", function (e) {
    var msg = e.detail && e.detail.xhr && e.detail.xhr.getResponseHeader("X-Toast");
    if (msg) window.socToast(msg);
  });

  // Dialogs: native <dialog>. Escape closes; focus goes back to the button that opened it.
  var opener = null;
  document.addEventListener("click", function (e) {
    var open = e.target.closest && e.target.closest("[data-dialog-open]");
    if (open) {
      var dlg = document.getElementById(open.getAttribute("data-dialog-open"));
      if (dlg && dlg.showModal) {
        e.preventDefault();
        opener = open;
        dlg.showModal();
      }
    }
    var shut = e.target.closest && e.target.closest("[data-dialog-close]");
    if (shut) {
      var d = shut.closest("dialog");
      if (d) d.close();
    }
  });
  document.addEventListener("close", function (e) {
    if (e.target.tagName === "DIALOG" && opener) {
      opener.focus();
      opener = null;
    }
  }, true);

  function countTicked(form) {
    var out = form && form.querySelector("[data-tick-count]");
    if (out) out.textContent = form.querySelectorAll("input[name=student_id]:checked").length + " ticked";
  }
  document.addEventListener("change", function (e) {
    if (e.target && e.target.name === "student_id") countTicked(e.target.form);
    if (e.target && e.target.hasAttribute("data-find-year")) findStudents(e.target.closest("form"));
  });
  // Find a student by name, or show one year level. Only hides rows: anyone ticked stays ticked (D-084).
  function findStudents(form) {
    var box = form.querySelector("[data-find]");
    if (!box) return;
    var q = box.querySelector("[data-find-name]").value.trim().toLowerCase();
    var yr = box.querySelector("[data-find-year]").value;
    var shown = 0;
    form.querySelectorAll(".year-block").forEach(function (b) {
      var n = 0;
      var yearOk = !yr || b.getAttribute("data-year") === yr;
      b.querySelectorAll(".checks label").forEach(function (l) {
        var ok = yearOk && (!q || l.textContent.toLowerCase().indexOf(q) !== -1);
        l.hidden = !ok;
        if (ok) n++;
      });
      b.hidden = n === 0;
      shown += n;
    });
    box.querySelector("[data-find-none]").hidden = shown > 0;
  }
  document.addEventListener("input", function (e) {
    if (e.target && e.target.hasAttribute("data-find-name")) findStudents(e.target.closest("form"));
  });
  // Autosave (D-087): a form marked data-autosave saves itself every 30 s while it has unsaved changes, and when the
  // page is hidden or left, so a lunchtime's writing survives a closed lid. The server answers 204 to autosave=1.
  var AUTOSAVE_MS = 30000;
  function autosave(form, leaving) {
    if (!form.__dirty || form.__saving) return;
    var status = form.querySelector("[data-autosave-status]");
    var data = new FormData(form);
    data.append("autosave", "1");
    form.__saving = true;
    form.__dirty = false;
    fetch(form.getAttribute("action"), { method: "POST", body: data, credentials: "same-origin", keepalive: !!leaving })
      .then(function (r) {
        if (!r.ok) throw new Error(r.status);
        if (status) status.textContent = "Saved automatically at " + new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) + ".";
      })
      .catch(function () {
        form.__dirty = true;
        if (status) status.textContent = "Not saved yet: press Save.";
      })
      .then(function () { form.__saving = false; });
  }
  document.addEventListener("input", function (e) {
    var form = e.target && e.target.closest && e.target.closest("form[data-autosave]");
    if (form) form.__dirty = true;
  });
  document.addEventListener("submit", function (e) {
    if (e.target && e.target.matches && e.target.matches("form[data-autosave]")) e.target.__dirty = false;
  }, true);
  window.socAutosaveNow = function () {
    document.querySelectorAll("form[data-autosave]").forEach(function (f) { autosave(f, false); });
  };
  setInterval(window.socAutosaveNow, AUTOSAVE_MS);
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "hidden") document.querySelectorAll("form[data-autosave]").forEach(function (f) { autosave(f, true); });
  });
  window.addEventListener("pagehide", function () {
    document.querySelectorAll("form[data-autosave]").forEach(function (f) { autosave(f, true); });
  });
  document.addEventListener("htmx:beforeRequest", function (e) {
    // A boosted link swaps the page without a pagehide: save first (not when the form itself is being submitted).
    var src = e.detail && e.detail.elt;
    document.querySelectorAll("form[data-autosave]").forEach(function (f) { if (src !== f && !f.contains(src)) autosave(f, true); });
  });

  // The board (D-092) opens in its own window for the extended screen: drag it across and press F11.
  document.addEventListener("click", function (e) {
    var b = e.target.closest && e.target.closest("[data-board-open]");
    if (!b) return;
    e.preventDefault();
    var w = window.open(b.getAttribute("data-board-open"), "soc-board", "popup=yes,width=1280,height=720");
    if (w) w.focus(); else location.href = b.getAttribute("data-board-open");
  });

  function showFind() { document.querySelectorAll("[data-find]").forEach(function (b) { b.hidden = false; }); }
  showFind();
  document.addEventListener("htmx:load", showFind);         // boosted navigation swaps the page in
  document.addEventListener("keydown", function (e) {
    // Enter in the search box filters; it must not submit the form.
    if (e.key === "Enter" && e.target && e.target.hasAttribute && e.target.hasAttribute("data-find-name")) e.preventDefault();
  });

  document.addEventListener("click", function (e) {
    var t = e.target;
    if (t && t.id === "easy-read-toggle") {
      var on = !document.body.classList.contains("easy-read");
      try { localStorage.setItem("easyRead", on ? "1" : "0"); } catch (err) { /* ignore */ }
      applyEasyRead();
    }
    // Start an activity: tick or untick a whole year level, and keep the "N ticked" count current (D-084).
    var all = t && t.closest && t.closest("[data-tick-all], [data-tick-none]");
    if (all) {
      var on = all.hasAttribute("data-tick-all");
      all.closest(".year-block").querySelectorAll("input[type=checkbox]").forEach(function (b) { b.checked = on; });
      countTicked(all.closest("form"));
    }
    // Destructive actions confirm and name the item (spec R4).
    var confirmFor = t && t.closest && t.closest("[data-confirm]");
    if (confirmFor && !window.confirm(confirmFor.getAttribute("data-confirm"))) {
      e.preventDefault();
      e.stopPropagation();
    }
  }, true);
})();
