/* The Session: "How it works" (Ben, 11 Nov 2026). A brief tour of every mechanic, one card each, shown once before a
   player's first game (on the new-session page) and any time from "How it works" on the title menu. Skippable at every
   step; arrows or Space move on, Escape skips. Remembered in this browser only (localStorage), and a browser that
   blocks storage simply sees it each time. */
(function () {
  "use strict";
  var KEY = "soc-session-primer-seen";
  var CARDS = [
    ["Your mission", "You are your country's ambassador, with secret instructions: get your main aim into the resolution, then your second, and keep your red line out."],
    ["Stages and turns", "The session runs through stages (working group, blocs, sponsors), then the Summit. Each turn gives you a few actions; meet a stage's breakthrough to move on early."],
    ["Talking", "Go over to a delegation: they tell you what's on their mind. Answer with an argument or a tone. Every tone has a price, and those who don't trust you hold things back."],
    ["Visitors", "Delegates, the press and your capital come to you. Every answer has a consequence, and a broken promise or a lie that comes out brings them back to call you to account."],
    ["The draft", "Propose clauses, amend and strike them. Win sponsors and signatures to table your text."],
    ["Deals and promises", "Trade funding, trade terms or your support for a delegation's vote. Promises bind: keep them, because betrayal costs Standing and trust."],
    ["Groups and rivals", "Regional groups meet and can endorse your draft. Rival delegations have secret aims of their own and play to win; sometimes a compromise beats a fight."],
    ["Your staff", "Advisers study a delegation each and report every turn. Post them where it matters; they learn and are promoted. Every move costs something."],
    ["The whip sheet", "Predict how each delegation will vote. It locks when the Summit opens, and every call is checked against the real vote."],
    ["Influence and Standing", "Influence is your currency. Standing is how the room and your capital see you: it adds actions, and if it reaches zero you're recalled."],
    ["The Summit", "Statements, the draft read in full, a caucus, then amendments one at a time, each debated and voted, and a final vote on the whole text."],
    ["Medals", "Every game is graded on five paths at once; your best path is your result. Gold is a perfect score, and gold opens the next scenario."]
  ];
  var el = null, at = 0, back = null;

  function store(v) { try { if (v === undefined) return window.localStorage.getItem(KEY); window.localStorage.setItem(KEY, v); } catch (e) { return null; } return null; }
  function h(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text) e.textContent = text; return e; }

  function build() {
    el = h("div", "s-overlay s-primer"); el.id = "s-primer"; el.hidden = true;
    el.setAttribute("role", "dialog"); el.setAttribute("aria-modal", "true"); el.setAttribute("aria-labelledby", "s-primer-h");
    var doc = h("div", "s-doc s-primer-doc");
    doc.appendChild(h("p", "s-eyebrow", "How it works"));
    var hh = h("h2", "", ""); hh.id = "s-primer-h"; doc.appendChild(hh);
    var p = h("p", "s-primer-p", ""); p.id = "s-primer-p"; doc.appendChild(p);
    var dots = h("ol", "s-primer-dots"); dots.setAttribute("aria-hidden", "true");
    CARDS.forEach(function () { dots.appendChild(h("li")); }); doc.appendChild(dots);
    var row = h("div", "s-row s-primer-row");
    var n = h("span", "s-small", ""); n.id = "s-primer-n"; row.appendChild(n);
    var prev = h("button", "s-btn ghost small", "Back"); prev.type = "button"; prev.id = "s-primer-back";
    var next = h("button", "s-btn", "Next"); next.type = "button"; next.id = "s-primer-next";
    var skip = h("button", "s-btn ghost small", "Skip"); skip.type = "button"; skip.id = "s-primer-skip";
    prev.addEventListener("click", function () { go(at - 1); });
    next.addEventListener("click", function () { if (at >= CARDS.length - 1) close(); else go(at + 1); });
    skip.addEventListener("click", close);
    row.appendChild(prev); row.appendChild(next); row.appendChild(skip); doc.appendChild(row);
    el.appendChild(doc);
    el.addEventListener("keydown", function (e) {
      if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); close(); }
      else if (e.key === "ArrowRight" || (e.key === " " && document.activeElement && document.activeElement.tagName !== "BUTTON")) { e.preventDefault(); next.click(); }
      else if (e.key === "ArrowLeft") { e.preventDefault(); go(at - 1); }
    });
    (document.getElementById("b-stage") || document.body).appendChild(el);
  }
  function go(i) {
    at = Math.max(0, Math.min(CARDS.length - 1, i));
    document.getElementById("s-primer-h").textContent = CARDS[at][0];
    document.getElementById("s-primer-p").textContent = CARDS[at][1];
    document.getElementById("s-primer-n").textContent = (at + 1) + " of " + CARDS.length;
    document.getElementById("s-primer-back").disabled = at === 0;
    document.getElementById("s-primer-next").textContent = at === CARDS.length - 1 ? "Let's begin" : "Next";
    document.getElementById("s-primer-skip").hidden = at === CARDS.length - 1;
    el.querySelectorAll(".s-primer-dots li").forEach(function (d, k) { d.className = k === at ? "on" : k < at ? "done" : ""; });
    var doc = el.querySelector(".s-primer-doc"); doc.classList.remove("s-reel-in"); void doc.offsetWidth; doc.classList.add("s-reel-in");
  }
  function open() {
    if (!el) build();
    back = document.activeElement;
    el.hidden = false; go(0);
    document.getElementById("s-primer-next").focus();
  }
  function close() {
    if (!el) return;
    el.hidden = true; store("1");
    if (back && back.focus) back.focus();
  }

  window.socSession = window.socSession || {};
  window.socSession.primer = { open: open, close: close, cards: CARDS.length };
  document.addEventListener("click", function (e) { if (e.target.closest("[data-primer]")) { e.preventDefault(); open(); } });
  var page = document.body && document.body.getAttribute("data-page");
  if (page === "new" && !store() && !navigator.webdriver) setTimeout(open, 300);   // before a player's first game, once (not in test browsers)
})();
