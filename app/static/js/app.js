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
