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
  document.addEventListener("htmx:afterSettle", function (e) {
    if (e.detail && e.detail.boosted) {
      var main = document.getElementById("main");
      if (main) main.focus({ preventScroll: false });
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
