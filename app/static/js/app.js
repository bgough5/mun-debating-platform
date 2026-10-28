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

  document.addEventListener("click", function (e) {
    var t = e.target;
    if (t && t.id === "easy-read-toggle") {
      var on = !document.body.classList.contains("easy-read");
      try { localStorage.setItem("easyRead", on ? "1" : "0"); } catch (err) { /* ignore */ }
      applyEasyRead();
    }
    // Destructive actions confirm and name the item (spec R4).
    var confirmFor = t && t.closest && t.closest("[data-confirm]");
    if (confirmFor && !window.confirm(confirmFor.getAttribute("data-confirm"))) {
      e.preventDefault();
      e.stopPropagation();
    }
  }, true);
})();
