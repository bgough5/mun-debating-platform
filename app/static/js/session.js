/* The Session (D-101): the title screen, the setup steps and the game page. The server works out every move; this
   draws what it says. A signed-in student's session is saved on the server; a guest's is kept in this browser
   (localStorage, up to three sessions), signed by the server so it can't be edited. Text from the server always goes
   in with textContent. */
(function () {
  "use strict";
  var page = document.body.getAttribute("data-page");
  var A = (window.socSession && window.socSession.audio) || { play: function () {}, settings: function () { return {}; }, set: function () {}, motionOn: function () { return false; } };
  var stage = document.getElementById("b-stage");
  var GUEST = "soc-session-guest", SLOTS = 3;

  function $(id) { return document.getElementById(id); }
  function h(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  // the bar at the bottom: a ticker of the latest news and moves; your last move's result; a failed move in red, with why
  var errUntil = 0;
  function say(t) {
    var m = $("p-msg") || $("s-msg"); var s = $("p-say"); if (s) s.textContent = t;
    if (!m || Date.now() < errUntil) return;
    m.className = "p-msg"; m.textContent = t;
  }
  function sayError(t) {
    var m = $("p-msg") || $("s-msg"); var s = $("p-say"); if (s) s.textContent = "That didn't work: " + t;
    if (!m) return;
    errUntil = Date.now() + 7000;
    m.className = "p-msg err"; m.textContent = "That didn't work: " + t;
    var al = $("s-alert");                                          // and in red, dropping from the banner (Ben, 8 Nov)
    if (al) { al.textContent = t; al.hidden = false; al.classList.remove("s-alert-in"); void al.offsetWidth; al.classList.add("s-alert-in");
      clearTimeout(sayError.t); sayError.t = setTimeout(function () { al.hidden = true; }, 5000); }
  }
  function ticker(log) {
    var m = $("p-msg"); if (!m || Date.now() < errUntil || !log || !log.length) return;
    var items = log.slice(-8).reverse().map(function (x) { return x.text; });
    m.className = "p-msg ticker"; m.textContent = "";
    var run = document.createElement("span"); run.className = "s-tick-run"; run.textContent = items.join("     ·     ");
    m.appendChild(run);
  }
  function restart(el, cls) { el.classList.remove(cls); void el.getBoundingClientRect(); el.classList.add(cls); }

  // ---------- the table at the screen's real size (phase 10): text never shrinks, and browser zoom works ----------
  function fitTitle() {
    var el = $("b-committee"); if (!el) return;
    var size = 30; el.style.fontSize = size + "px";
    while (el.scrollWidth > el.clientWidth && size > 20) { size -= 1; el.style.fontSize = size + "px"; }
  }
  window.addEventListener("resize", fitTitle);
  fitTitle();
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(fitTitle);

  // ---------- talking to the server ----------
  function csrf() { var m = document.cookie.match(/(?:^|;\s*)soc_csrf=([^;]+)/); return m ? decodeURIComponent(m[1]) : ""; }
  function api(body) {
    return fetch("/session/api", { method: "POST", headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf() }, body: JSON.stringify(body) })
      .then(function (r) { return r.json().then(function (j) { if (!r.ok) throw new Error(j.error || "That didn't work."); return j; }); });
  }

  // ---------- guest sessions, kept in this browser ----------
  function slots() { try { return JSON.parse(window.localStorage.getItem(GUEST) || "[]") || []; } catch (e) { return []; } }
  function keep(list) {
    try { window.localStorage.setItem(GUEST, JSON.stringify(list.slice(0, SLOTS))); return true; }
    catch (e) { say("This browser won't keep the session (private window or storage blocked): it will end when you close the tab."); return false; }
  }
  function where(v) { return v.phase === "done" ? "Finished" : v.phase === "summit" ? "The Summit" : (v.chapter_name || "Stage " + v.chapter) + ", turn " + v.turn; }

  // ---------- overlays: the chapter card, pause and settings ----------
  var lastFocus = null;
  function open(id) {
    var o = $(id); if (!o) return;
    lastFocus = document.activeElement; o.hidden = false;
    var f = o.querySelector("button, a"); if (f) f.focus();
    if (id === "s-settings") syncSettings();
  }
  function close(id) {
    var o = $(id); if (!o) return;
    o.hidden = true;
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }
  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-open]"); if (b) { open(b.getAttribute("data-open")); A.play("flip"); return; }
    b = e.target.closest("[data-close]"); if (b) { close(b.getAttribute("data-close")); return; }
    b = e.target.closest("[data-set]");
    if (b) {
      var raw = b.getAttribute("data-value"), v = raw === "true" ? true : raw === "false" ? false : raw;
      A.set(b.getAttribute("data-set"), v); syncSettings();
      if (b.getAttribute("data-set") === "sound" && v) A.play("chime");
    }
  });
  document.addEventListener("keydown", function (e) {
    if (e.key !== "Escape") return;
    var w = $("s-walk"); if (w && !w.hidden) { var sk = $("s-guide-skip"); if (sk) sk.click(); return; }
    var shown = Array.prototype.filter.call(document.querySelectorAll(".s-overlay"), function (o) { return !o.hidden; });
    if (shown.length) { close(shown[shown.length - 1].id); return; }
    if (window.socSessionPanel && window.socSessionPanel.close()) return;
    if (page === "game") open("s-pause");
  });
  function syncSettings() {
    var s = A.settings();
    document.querySelectorAll("[data-set]").forEach(function (b) {
      var raw = b.getAttribute("data-value"), v = raw === "true" ? true : raw === "false" ? false : raw;
      b.setAttribute("aria-pressed", String(s[b.getAttribute("data-set")] === v));
    });
  }

  // =====================================================================================================
  // The title screen: a guest's sessions on this laptop
  // =====================================================================================================
  function titlePage() {
    var ul = $("s-guest-saves"); if (!ul) return;
    var list = slots();
    $("s-guest-none").hidden = false;
    list.forEach(function (s, i) {
      var li = h("li"), b = h("button", "s-save");
      b.type = "button";
      b.appendChild(h("b", "", s.title));
      b.appendChild(h("span", "s-medal", s.medal || ""));
      b.appendChild(h("span", "", "as " + s.country + " · " + s.where));
      b.addEventListener("click", function () { window.location.href = "/session/guest/" + encodeURIComponent(s.pack) + "?slot=" + i; });
      li.appendChild(b); ul.appendChild(li);
    });
  }

  // =====================================================================================================
  // Setting up: six steps
  // =====================================================================================================
  function newPage() {
    var choice = { pack: null, iso3: null, length: "standard", difficulty: "standard", path: "mandate" };
    var labels = { length: "Standard", difficulty: "Standard", path: "Mandate" };
    var at = 1, loadedFor = null, moved = false;
    var RIB = { 1: "Choose a scenario", 2: "Choose your country", 3: "How long?", 4: "How strong are your rivals?", 5: "What will you aim for?", 6: "Your briefing" };
    function show(n) {
      at = n;
      document.querySelectorAll("[data-step]").forEach(function (s) {
        s.hidden = +s.getAttribute("data-step") !== n;
        if (!s.hidden && moved) restart(s, "s-anim");
      });
      moved = true;
      document.querySelectorAll("[data-step-dot]").forEach(function (d) {
        var k = +d.getAttribute("data-step-dot"); d.classList.toggle("now", k === n); d.classList.toggle("done", k < n);
      });
      $("s-ribbon").textContent = RIB[n];
      var cur = document.querySelector('[data-step="' + n + '"]'); if (cur) { var hd = cur.querySelector("h2"); if (hd) { hd.tabIndex = -1; hd.focus(); } }
      if (n === 2 && choice.pack !== loadedFor) loadSeats();
      if (n === 6) document.querySelectorAll("[data-show]").forEach(function (d) { d.textContent = labels[d.getAttribute("data-show")] || "–"; });
      sync();
    }
    function sync() {
      var need = { 1: "pack", 2: "iso3" }[at];
      var nx = document.querySelector('[data-step="' + at + '"] [data-next]');
      if (nx) nx.disabled = !!need && !choice[need];
    }
    function pick(btn) {
      var key = btn.getAttribute("data-pick"), val = btn.getAttribute("data-value");
      if (key === "pack" && choice.pack !== val) { choice.iso3 = null; labels.iso3 = null; }
      choice[key] = val; labels[key] = btn.getAttribute("data-label");
      document.querySelectorAll('[data-pick="' + key + '"]').forEach(function (b) { b.setAttribute("aria-pressed", String(b.getAttribute("data-value") === val)); });
      if (key === "iso3") {
        document.querySelectorAll("#s-seats-box .b-token").forEach(function (t) { t.classList.toggle("s-chosen", t.getAttribute("data-iso") === val); });
        say(labels.iso3 + " it is.");
      }
      A.play("flip"); sync();
    }
    document.addEventListener("click", function (e) {
      var b = e.target.closest("[data-pick]"); if (b) { pick(b); return; }
      if (e.target.closest("[data-next]")) { A.play("paper"); show(at + 1); return; }
      if (e.target.closest("[data-back]")) { show(at - 1); return; }
      var t = e.target.closest("#s-seats-box .b-token");
      if (t) { var seat = document.querySelector('.s-seat[data-value="' + t.getAttribute("data-iso") + '"]'); if (seat) { pick(seat); seat.scrollIntoView({ block: "nearest" }); } }
    });
    function loadSeats() {
      var box = $("s-seats-box"); box.textContent = "";
      box.appendChild(h("p", "s-note", "Loading the committee…"));
      fetch("/session/seats/" + encodeURIComponent(choice.pack)).then(function (r) { if (!r.ok) throw new Error(); return r.text(); }).then(function (html) {
        box.innerHTML = html;            // our own server-rendered fragment (escaped by the templates)
        loadedFor = choice.pack;
        box.querySelectorAll(".b-token").forEach(function (t) { t.setAttribute("tabindex", "-1"); });
      }).catch(function () { box.textContent = "The committee didn't load. Go back and try again."; });
    }
    var tipBox = $("s-tips-on");
    if (tipBox) { tipBox.checked = A.settings().tips !== false; tipBox.addEventListener("change", function () { A.set("tips", tipBox.checked); }); }
    $("s-begin").addEventListener("click", function () {
      var b = $("s-begin"); b.disabled = true; say("Taking your seat…");
      api({ do: "new", pack: choice.pack, iso3: choice.iso3, length: choice.length, difficulty: choice.difficulty, path: choice.path,
            approach: choice.approach || "diplomat" }).then(function (r) {
        A.play("gavel");
        if (r.state) {
          var list = slots();
          list.unshift({ pack: choice.pack, title: r.view.title, country: r.view.you.name, where: where(r.view), state: r.state, sig: r.sig, at: Date.now() });
          keep(list);
          window.location.href = r.url + "?slot=0";
        } else window.location.href = r.url;
      }).catch(function (e) { b.disabled = false; say(e.message); });
    });
    show(1);
  }

  // =====================================================================================================
  // The game: the table, the four tabs (Brief, Draft, Delegations, Record), and every move
  // =====================================================================================================
  function gamePage() {
    var mode = document.body.getAttribute("data-mode"), saveId = document.body.getAttribute("data-save-id");
    var slot = +(new URLSearchParams(window.location.search).get("slot") || 0);
    var guest = null, V = null, busy = false, seenLog = 0, picked = null, amending = null;
    var tokens = {}, lands = {};
    document.querySelectorAll("#b-map .b-token").forEach(function (g) { tokens[g.getAttribute("data-iso")] = g; });
    document.querySelectorAll("#b-map .b-land").forEach(function (l) { (lands[l.getAttribute("data-iso")] = lands[l.getAttribute("data-iso")] || []).push(l); });
    var SOUND = { lobby: "paper", read: "flip", propose: "stamp", amend: "paper", strike: "stamp", promise: "coin", side_event: "chime",
                  favour: "coin", whip: "tick", sign: "stamp", skill: "chime", divide: "paper", merge: "stamp", bloc_whip: "chime", abstain: "stamp",
                  hire: "coin", post: "flip", reserve: "tick", secure: "stamp", offer: "paper", deal: "stamp",
                  attend: "chime", overtime: "coin", stay: "flip" };
    var POS = { "2": ["p2", "Strongly for"], "1": ["p1", "For"], "0": ["p0", "Neutral"], "-1": ["n1", "Against"], "-2": ["n2", "Strongly against"] };

    function body(extra) {
      var b = { do: extra.do };
      if (extra.action) b.action = extra.action;
      if (mode === "saved") b.save_id = +saveId; else { b.state = guest.state; b.sig = guest.sig; }
      return b;
    }
    function call(extra) {
      if (busy) return Promise.reject(new Error("One moment…"));
      busy = true;
      document.body.classList.add("s-busy");
      return api(body(extra)).then(function (r) {
        busy = false; document.body.classList.remove("s-busy");
        if (r.state) {                                     // a guest: keep the new signed state on this laptop
          guest.state = r.state; guest.sig = r.sig; guest.where = where(r.view); guest.at = Date.now();
          if (r.view.result) guest.medal = ["No medal", "Bronze", "Silver", "Gold"][r.view.result.grade];
          var list = slots(); list[slot] = guest; keep(list);
        }
        return r;
      }, function (e) { busy = false; document.body.classList.remove("s-busy"); throw e; });
    }
    function btn(text, cls, onclick, disabled) {
      var b = h("button", cls || "s-btn small", text); b.type = "button";
      if (disabled) b.disabled = true;
      b.addEventListener("click", onclick);
      return b;
    }
    function opt(sel, value, text) { var o = h("option", "", text); o.value = value; sel.appendChild(o); return o; }

    // ---------- tabs ----------
    var TABS = ["brief", "draft", "dele", "coalition", "summit", "whip", "staff", "record"];
    var rail = $("s-rail");
    function panelOpen() { return rail.classList.contains("open"); }
    function setTab(name, focus, dock) {
      TABS.forEach(function (t) {
        var b = $("t-" + t), on = t === name;
        b.setAttribute("aria-selected", String(on)); b.tabIndex = on ? 0 : -1; $("p-" + t).hidden = !on;
      });
      var was = TABS.filter(function (t) { return $("t-" + t) && !$("p-" + t).hidden; })[0];
      rail.classList.add("open"); document.body.classList.add("s-panel-open");
      if (was !== name || !panelOpen()) { var pn = rail.querySelector(".s-panes"); if (pn) pn.scrollTop = 0; }   // each panel opens at its top
      rail.classList.add("center");
      if (focus) $("t-" + name).focus();
    }
    function closePanel() {
      if (!panelOpen()) return false;
      var inside = rail.querySelector(".s-panes").contains(document.activeElement);
      rail.classList.remove("open", "center", "dock-left"); document.body.classList.remove("s-panel-open");
      if (inside) { var cur = rail.querySelector('[role="tab"][aria-selected="true"]'); if (cur) cur.focus(); }   // focus back to its icon
      return true;
    }
    var keyBtn = $("s-key-btn");
    if (keyBtn) keyBtn.addEventListener("click", function () {
      var on = !stage.classList.contains("s-key-open");
      stage.classList.toggle("s-key-open", on); keyBtn.setAttribute("aria-expanded", String(on)); A.play("flip");
    });
    window.socSessionPanel = { close: function () { var w = $("s-walk"); return w && !w.hidden ? false : closePanel(); } };
    $("s-panel-close").addEventListener("click", function () { closePanel(); A.play("flip"); });
    document.querySelector(".s-tabs").addEventListener("click", function (e) {
      var b = e.target.closest("[data-tab]"); if (!b) return;
      if (panelOpen() && b.getAttribute("aria-selected") === "true") { closePanel(); A.play("flip"); return; }
      setTab(b.getAttribute("data-tab")); A.play("flip");
    });
    document.querySelector(".s-tabs").addEventListener("keydown", function (e) {
      var shown = TABS.filter(function (t) { return !$("t-" + t).hidden; });
      var i = shown.indexOf(document.activeElement.getAttribute("data-tab")); if (i < 0) return;
      if (e.key === "ArrowRight" || e.key === "ArrowLeft") { e.preventDefault(); setTab(shown[(i + (e.key === "ArrowRight" ? 1 : shown.length - 1)) % shown.length], true); }
    });

    // ---------- moves ----------
    function move(action) {
      if (V && V.phase === "done") return;
      call({ do: "move", action: action }).then(function (r) {
        var votes = r.out && (r.out.votes || (r.out.final && r.out.final.votes));
        if (votes && Object.keys(votes).length) {
          var passed = r.out.final ? r.out.final.passed : r.out.passed;
          draw(r.view, r.out, action);
          var wait = sweep(votes, passed);
          var sum = r.out.final ? r.out.final.summary : r.out.summary;
          say((r.out.amendment && action.do !== "amend_vote" ? "The floor amendment was " + r.out.amendment + ". " : "") +
              (r.out.final ? "The resolution: " : action.do === "amend_vote" ? "The amendment: " : "The clause: ") + (passed ? "adopted. " : "rejected. ") + (sum || ""));
          if (r.view.phase === "done") setTimeout(function () { result(r.view); }, wait);
          return;
        }
        draw(r.view, r.out, action);
        if (r.view.phase === "done") setTimeout(function () { result(r.view); }, action.do === "statement" ? 600 : 1800);
        if (action.do === "end_turn") A.play("gavel"); else if (SOUND[action.do]) A.play(SOUND[action.do]);
      }).catch(function (e) { sayError(e.message); A.play("tick"); });
    }

    function meter(id, value) {
      var li = $(id), b = li.querySelector("b"), old = b.textContent;
      b.textContent = value;
      if (old !== "–" && old !== String(value)) { restart(li, "bump"); if (id === "m-influence" && +value > +old) A.play("coin"); }
    }
    function chapterCard(v, prev) {
      if (v.phase === "done") return;                              // the results take over
      var summit = v.phase !== "chapter";
      var was = prev && prev.objectives && v.objectives[String(prev.chapter)];
      $("s-cc-eyebrow").textContent = summit ? "The final act" : (v.length === "quick" ? "One working session" : "Stage " + v.chapter + " of " + v.chapters);
      $("s-cc-h").textContent = summit ? "The Summit" : v.chapter_name;
      var pre = prev && prev.phase === "chapter" ? (prev.chapter_name + ": " + (was ? "breakthrough made. +3 Influence. " : "the deadline passed without a breakthrough. ")) : "";
      $("s-cc-goal").textContent = pre + (summit ? "The draft goes to the vote, clause by clause, then as a whole." :
        "Breakthrough: " + v.stage.goal + " Deadline: " + v.stage.deadline + " turns.");
      $("s-cc-look").textContent = summit ? "I'll preside. Every clause is voted on, then the whole text." : v.stage.look;
      var pf = $("s-cc-pres"); pf.textContent = ""; if (G) pf.appendChild(G.portrait(summit ? "eyebrow" : "delighted", "president"));
      stagePanel = summit ? null : (v.length === "quick" || v.chapter === 1 ? "draft" : "coalition");
      var cr = !summit && v.crisis && v.crisis.chapter === v.chapter ? v.crisis : null;
      $("s-cc-crisis").hidden = !cr;
      if (cr) { $("s-cc-crisis-h").textContent = cr.title; $("s-cc-crisis-p").textContent = cr.body; $("s-cc-crisis-t").textContent = cr.teaches; }
      open("s-chapter-card");
      restart(document.querySelector("#s-chapter-card .s-doc"), "shown");
      A.play(v.chapter === 1 && !summit && !prev ? "open" : "gavel");
    }
    var stagePanel = null, afterCard = null;
    // after a stage card: the Chief's intro to what's new (if the guide is on), then the turn's reel, then the stage's panel
    function afterStageCard() {
      var v = V; if (!v) return;
      var items = afterCard || []; afterCard = null;
      var p = stagePanel; stagePanel = null;
      var panel = function () { if (p && v.phase === "chapter" && !panelOpen() && $("s-walk").hidden) setTab(p, false, p === "draft" ? "center" : null); };
      var reel = function () { REEL.play(items, function () { panel(); DLG.offer(V); }); };
      var set = v.phase === "summit" ? "summit" : v.length !== "quick" && v.chapter > 1 ? "stage" + v.chapter : null;
      if (set && guideOn() && !seenIntro[set]) { seenIntro[set] = true; setTimeout(function () { WALK.start(V, reel, set); }, 300); }
      else setTimeout(reel, 250);
    }
    var seenIntro = {};

    // ---------- the Brief tab ----------
    function progress(v) {
      var ul = $("c-progress"); ul.textContent = "";
      if (v.stage) {
        v.stage.checklist.forEach(function (x) { ul.appendChild(h("li", x.done ? "done" : "", x.label + " (" + x.count + ")")); });
        var adv = $("c-advance"); adv.textContent = "";
        if (v.stage.made) adv.appendChild(btn("Move on now: +" + v.stage.momentum.respect + " Standing, +" + v.stage.momentum.influence + " Influence", "s-btn small", function () { move({ do: "advance" }); }));
        return;
      }
      var items = [], c1 = v.draft_ok.clauses >= 4, mine = v.draft_ok.mine >= 1;
      var endorsed = v.regions.some(function (r) { return r.owner === "you"; });
      var sp = v.sponsors >= v.costs.sponsors, sig = v.sponsors + v.signatories >= v.signers_needed;
      if (v.length === "quick" || v.chapter === 1) items.push([c1, "Four clauses in the draft (" + v.draft_ok.clauses + ")"], [mine, "At least one of them yours (" + v.draft_ok.mine + ")"]);
      if (v.length !== "quick" && v.chapter === 2) items.push([endorsed, "A regional group endorses your draft"]);
      if (v.length === "quick" || v.chapter === 3) items.push([sp, "Sponsors: " + v.sponsors + " of " + v.costs.sponsors], [sig, "Sponsors and signatories: " + (v.sponsors + v.signatories) + " of " + v.signers_needed]);
      items.forEach(function (x) { ul.appendChild(h("li", x[0] ? "done" : "", x[1])); });
    }
    function regions(v) {
      var ul = $("c-region-list"); ul.textContent = "";
      v.regions.forEach(function (r) {
        var li = h("li", r.owner === "you" ? "you" : r.owner ? "rival" : "");
        li.appendChild(h("b", "", r.name));
        li.appendChild(h("span", "s-small", r.owner ? (r.owner === "you" ? "Endorses you" : "Endorses " + r.owner_name) : "Undecided"));
        var bar = h("div", "s-bar-meter"), fill = h("i"); fill.style.width = (r.voters ? 100 * r.leaning / r.voters : 0) + "%";
        bar.appendChild(fill); bar.appendChild(h("em")); bar.setAttribute("aria-hidden", "true"); li.appendChild(bar);
        li.appendChild(h("span", "s-small", r.leaning + " of " + r.voters + " lean your way (more than half wins it)"));
        ul.appendChild(li);
      });
    }

    // ---------- the Draft tab ----------
    function draft(v, prev) {
      $("n-draft").textContent = v.draft.length;
      var known = prev ? prev.draft.map(function (c) { return c.id; }) : null;
      var ol = $("c-clauses"); ol.textContent = "";
      v.draft.forEach(function (c) {
        var li = h("li", (c.mine ? "mine" : c.stance < 0 ? "against" : "") + (known && known.indexOf(c.id) < 0 ? " s-new" : ""));
        if (c.chance !== null && c.chance !== undefined) {
          var dial = h("span", "s-dial"); dial.style.setProperty("--p", Math.round(c.chance * 100));
          dial.appendChild(h("span", "", Math.round(c.chance * 100) + "%")); dial.title = "Chance it would pass now";
          dial.setAttribute("aria-label", "About " + Math.round(c.chance * 100) + "% chance it would pass now");
          li.appendChild(dial);
        }
        var changed = known && prev && (prev.draft.filter(function (p) { return p.id === c.id; })[0] || {}).now !== c.now;
        if (changed) li.classList.add("s-changed");
        if (c.stale) {
          li.appendChild(h("p", "s-now", "Now commits countries to: " + c.now + "."));
          li.appendChild(h("p", "s-was", "Its wording before it was amended: " + c.text));
        } else li.appendChild(document.createTextNode(c.text));
        li.appendChild(h("span", "s-by", (c.mine ? "Yours" : c.author) + (c.amended_by.length ? " · amended by " + c.amended_by.join(", ") : "") +
                                          (c.stale ? "" : " · commits countries to: " + c.tags.map(function (t) { return t.label.toLowerCase(); }).join("; "))));
        if (c.history && c.history.length) {
          var hd = h("details", "s-hist"); hd.appendChild(h("summary", "", "History (" + c.history.length + ")" + (changed ? ": changed since your last look" : "")));
          var hl = h("ol"); c.history.forEach(function (x) { hl.appendChild(h("li", x.who === "you" ? "you" : x.who === "draft" ? "" : "them", x.when + ": " + x.name + " " + x.what)); });
          hd.appendChild(hl); li.appendChild(hd);
        }
        var acts = h("div", "s-acts");
        acts.appendChild(btn(amending === c.id ? "Cancel" : "Amend", "s-chip", function () { amending = amending === c.id ? null : c.id; draw(V); }, !v.ap));
        acts.appendChild(btn("Strike (" + v.costs.strike + " Influence)", "s-chip", function () {
          if (window.confirm("Ask the working group to strike this clause?")) move({ do: "strike", clause: c.id });
        }, !v.ap || v.draft.length <= 1));
        if (v.skills.indexOf("division") >= 0 && c.tags.length > 1) acts.appendChild(btn("Divide", "s-chip", function () { move({ do: "divide", clause: c.id }); }, !v.ap));
        if (v.skills.indexOf("merge") >= 0 && v.draft.length > 1) {
          var ms = h("select"); ms.setAttribute("aria-label", "Merge with");
          v.draft.forEach(function (o, k) { if (o.id !== c.id) opt(ms, o.id, "Merge with clause " + (k + 1)); });
          acts.appendChild(ms); acts.appendChild(btn("Merge", "s-chip", function () { move({ do: "merge", a: c.id, b: ms.value }); }, !v.ap));
        }
        li.appendChild(acts);
        if (amending === c.id) li.appendChild(amendBox(v, c));
        ol.appendChild(li);
      });
      var cards = $("c-cards"); cards.textContent = "";
      if (!v.cards.length) cards.appendChild(h("li", "", "No clause cards left on the table."));
      v.cards.filter(function (card) { return card.tags.some(function (t) { return (v.in_draft || []).indexOf(t) < 0; }); }).forEach(function (card) {
        var li = h("li");
        li.appendChild(h("span", "", card.text));
        li.appendChild(h("span", "s-tagline", "Commits countries to: " + card.tags.map(function (t) { return v.tags[t].toLowerCase(); }).join("; ")));
        var det = h("details"), sum = h("summary", "", "In your own words (optional)"), ta = h("textarea");
        ta.maxLength = 400; ta.setAttribute("aria-label", "Your wording of this clause");
        det.appendChild(sum); det.appendChild(ta); li.appendChild(det);
        li.appendChild(btn("Propose" + (v.costs.propose ? " (" + v.costs.propose + " Influence)" : ""), "s-btn small", function () {
          move({ do: "propose", card: card.id, text: ta.value.trim() });
        }, !v.ap || v.draft.length >= v.costs.draft_max));
        cards.appendChild(li);
      });
    }
    function amendBox(v, c) {
      var box = h("div", "s-amend"), have = c.tags.map(function (t) { return t.code; });
      box.appendChild(h("span", "s-small", "Tick what the clause should commit countries to (one to three). One addition and one removal per amendment."));
      Object.keys(v.tags).filter(function (code) { return have.indexOf(code) >= 0 || (v.in_draft || []).indexOf(code) < 0; }).forEach(function (code) {
        var lab = h("label"), cb = h("input"); cb.type = "checkbox"; cb.value = code; cb.checked = have.indexOf(code) >= 0;
        lab.appendChild(cb); lab.appendChild(document.createTextNode(v.tags[code])); box.appendChild(lab);
      });
      box.appendChild(btn("Propose the amendment" + (v.costs.amend ? " (" + v.costs.amend + " Influence)" : ""), "s-btn small", function () {
        var now = Array.prototype.filter.call(box.querySelectorAll("input:checked"), function () { return true; }).map(function (x) { return x.value; });
        var add = now.filter(function (t) { return have.indexOf(t) < 0; }), rem = have.filter(function (t) { return now.indexOf(t) < 0; });
        if (add.length > 1 || rem.length > 1) { say("One change at a time: add one commitment and remove one, at most."); return; }
        if (!add.length && !rem.length) { say("Tick or untick a commitment first."); return; }
        amending = null;
        move({ do: "amend", clause: c.id, add: add[0] || null, remove: rem[0] || null });
      }));
      return box;
    }

    // ---------- the Delegations tab ----------
    function countryPicker(v) {
      var sel = $("s-pick-country");
      if (!sel.options.length) {
        opt(sel, "", "Choose a delegation…");
        Object.keys(v.tokens).map(function (iso) { return [iso, v.tokens[iso].name]; }).filter(function (x) { return x[0] !== v.you.iso3; })
          .sort(function (a, b) { return a[1] < b[1] ? -1 : 1; }).forEach(function (x) { opt(sel, x[0], x[1]); });
        sel.addEventListener("change", function () { pick(sel.value || null); });
      }
      sel.value = picked || "";
    }
    var heardIso = null;
    function pick(iso) {
      picked = iso;
      if (heardIso !== iso) $("c-heard").hidden = true;             // their words belong to them, not the next delegation
      Object.keys(tokens).forEach(function (k) { tokens[k].classList.toggle("picked", k === iso); });
      if (V) country(V);
    }
    function country(v) {
      var box = $("c-country"); box.textContent = "";
      var d = picked && v.tokens[picked];
      if (!d) { box.appendChild(h("p", "s-small", "Click a country on the map, or choose one here.")); return; }
      var c = h("div", "s-country");
      c.appendChild(h("h3", "", d.name + (d.p5 ? " ★" : "")));
      var dl = h("dl", "s-facts");
      function fact(k, val) { dl.appendChild(h("dt", "", k)); var dd = h("dd"); if (typeof val === "string") dd.textContent = val; else dd.appendChild(val); dl.appendChild(dd); }
      fact("Group", d.region + (d.veto ? " · holds a veto" : ""));
      if (d.rival) {
        fact("Status", d.truce ? "At peace with you: it co-sponsors the merged text." : "Rival delegation: its instructions oppose yours. Pitches won't move it, but a compromise might.");
        c.appendChild(dl);
        if (!d.truce && v.phase === "chapter") {
          var lockedR = v.unlock.compromise;
          c.appendChild(btn(lockedR ? "Compromise: " + lockedR : "Negotiate a compromise (" + v.costs.deal_ap + " actions)", "s-btn small s-deal-btn",
                            function () { TALK.openTable(picked, "rival"); }, !!lockedR || !(d.peace_terms || []).length || !v.deal_ready || v.ap < v.costs.deal_ap));
          if (!(d.peace_terms || []).length) c.appendChild(h("p", "s-small", "Nothing to offer it yet: its red line isn't in the draft, and its wish is already in."));
        }
        box.appendChild(c); return;
      }
      fact("On the draft", d.est === "yes" ? "Likely for" : d.est === "no" ? "Likely against" : d.est ? "Unsure" : "No draft yet");
      fact("Relationship", relation(d.relation));
      if ((d.commitments || []).length) fact("Commitments", d.commitments.join("; "));
      if (d.deal && d.deal.asks) fact("Wants in a deal", d.deal.asks.map(function (k) { return ASK[k]; }).join(", "));
      if (d.studied_by) fact("Studied by", d.studied_by);
      var flags = [];
      if (d.signed) flags.push("signed as your " + d.signed);
      if (d.predicted) flags.push("you predicted: " + d.predicted);
      if (flags.length) fact("Also", flags.join("; "));
      c.appendChild(h("p", "s-status", (d.est === "yes" ? "Likely for" : d.est === "no" ? "Likely against" : d.est ? "Unsure" : "No draft yet") +
        " · " + relation(d.relation).toLowerCase() + ((d.commitments || []).length ? " · committed" : "")));
      var grid = h("div", "s-acts-grid"), noAp = !v.ap;
      grid.appendChild(TALK.pitchBox(v, d, picked));
      grid.appendChild(d.read ? btn("Open the file", "s-btn ghost small", function () { showFile(d.file); })
                              : btn("Read the file (1 action)", "s-btn ghost small", function () { move({ do: "read", iso3: picked }); }, noAp));
      if (d.promise_on && d.promise_on.length && !d.promised) {
        var ps = h("select", "wide"); ps.setAttribute("aria-label", "Promise to back which clause");
        v.draft.forEach(function (cl, k) { if (d.promise_on.indexOf(cl.id) >= 0) opt(ps, cl.id, "Promise to back clause " + (k + 1)); });
        var row = h("div", "s-row wide"); row.appendChild(ps);
        row.appendChild(btn("Promise", "s-btn small", function () { move({ do: "promise", iso3: picked, clause: ps.value }); }));
        grid.appendChild(row);
      }
      if (d.deal) grid.appendChild(btn(v.unlock.deal ? "Deal table: " + v.unlock.deal : "The deal table (" + v.costs.deal_ap + " actions)", "s-btn small s-deal-btn",
                                       function () { TALK.openTable(picked, "deal"); }, !!v.unlock.deal || d.deal.done || (!v.deal_ready && !(v.talks && v.talks.iso3 === picked)) || (v.ap < v.costs.deal_ap && !(v.talks && v.talks.iso3 === picked))));
      if (d.veto && v.veto.length) grid.appendChild(btn("Ask to abstain, not veto", "s-btn ghost small", function () { move({ do: "abstain", iso3: picked }); }, noAp || d.pledged || d.trust < 1));
      if (!v.unlock.sign && !d.signed && (v.last_chapter || v.length === "quick")) {
        grid.appendChild(btn("Ask to sponsor", "s-btn small", function () { move({ do: "sign", iso3: picked, role: "sponsor" }); }, noAp));
        grid.appendChild(btn("Ask to sign", "s-btn ghost small", function () { move({ do: "sign", iso3: picked, role: "signatory" }); }, noAp));
      }
      var pr = h("div", "s-predict wide"); pr.appendChild(h("span", "", "Your whip sheet, whole text (free):"));
      ["yes", "abstain", "no"].forEach(function (x) {
        var b = btn(x, "s-chip", function () { move({ do: "mark", iso3: picked, clause: "final", vote: d.predicted === x ? null : x }); });
        b.setAttribute("aria-pressed", String(d.predicted === x)); pr.appendChild(b);
      });
      grid.appendChild(pr);
      c.appendChild(grid);
      c.appendChild(dl);                                            // the details and the dossier below the actions
      if (d.dossier && d.dossier.known) c.appendChild(dossierBox(d.dossier, false));
      box.appendChild(c);
    }
    function showFile(f) {
      if (!f) return;
      $("s-file-h").textContent = f.name + (f.p5 ? " ★" : "");
      var b = $("s-file-body"); b.textContent = "";
      b.appendChild(h("p", "s-sub", f.region + (f.fictional ? " · a fictional scenario: every position is invented for practice." :
                                               " · positions are estimates from the sources below, not statements of fact.")));
      if (f.mood) b.appendChild(h("p", "", "Read the room: today they seem " + f.mood + "."));
      var t = h("table"), hr = h("tr"); hr.appendChild(h("th", "", "Commitment")); hr.appendChild(h("th", "", "Their position")); t.appendChild(hr);
      f.positions.forEach(function (p) {
        var tr = h("tr"), k = p.position === null || p.position === undefined ? null : String(p.position);
        tr.appendChild(h("td", "", p.label));
        var td = h("td"); td.appendChild(h("span", "s-pos " + (k ? POS[k][0] : "p0"), k ? POS[k][1] : "Not known")); tr.appendChild(td);
        t.appendChild(tr);
      });
      b.appendChild(t);
      if (f.shifts && f.shifts.length) b.appendChild(h("p", "s-shifted", "Since the session began: " + f.shifts.map(function (x) { return x.dir + " towards anything that " + lcf(x.label); }).join("; ") + "."));
      var dz = V && V.tokens[f.iso3] && V.tokens[f.iso3].dossier;
      if (dz && dz.known) b.appendChild(dossierBox(dz, true));
      if (f.listens_to && f.listens_to.length) b.appendChild(h("p", "s-listens", "Pitch it: it listens to " + f.listens_to.join(" and ").toLowerCase() + "."));
      if (f.red_lines.length) b.appendChild(h("p", "", "Red lines (they say they can never accept): " + f.red_lines.join("; ") + "."));
      if (f.sources.length) {
        var s = h("div", "s-sources"); s.appendChild(h("p", "s-sub", "Sources:"));
        var ul = h("ul");
        f.sources.forEach(function (u) { var li = h("li"), a = h("a", "", u); a.href = u; a.target = "_blank"; a.rel = "noopener"; li.appendChild(a); ul.appendChild(li); });
        s.appendChild(ul); b.appendChild(s);
      }
      open("s-file");
    }

    // ---------- skills ----------
    function skills(v) {                                             // skills come with your advisers' promotions (8 Nov)
      $("n-skills").textContent = "";
      var tree = $("s-tree"); tree.textContent = "";
      var by = {};
      v.skill_list.forEach(function (s) { (by[s.by] = by[s.by] || []).push(s); });
      Object.keys(by).forEach(function (who) {
        var col = h("div", "s-branch"); col.appendChild(h("h3", "", who));
        by[who].sort(function (a, b) { return a.stars - b.stars; }).forEach(function (s) {
          var d = h("div", "s-skill" + (s.have ? " have" : ""));
          d.appendChild(h("b", "", s.name)); d.appendChild(h("span", "", s.what));
          d.appendChild(h("span", "s-small", s.have ? "Yours" : "With a " + (s.stars === 2 ? "senior" : "principal") + " " + who.toLowerCase() + " (" + s.stars + "★)"));
          col.appendChild(d);
        });
        tree.appendChild(col);
      });
      $("s-skills-note").textContent = "Each skill comes with an adviser's promotion. Advisers are promoted when their reports prove right.";
    }

    // ---------- drawing everything ----------
    function draw(v, out, action) {
      var prev = V; V = v;
      ticker(v.log);
      var turnChanged = !!prev && v.phase === "chapter" && (prev.turn !== v.turn || prev.chapter !== v.chapter);
      $("s-where").textContent = v.phase === "done" ? "Finished" : v.phase === "summit" ? "The Summit" :
        v.chapter_name + " · turn " + v.turn + " of " + v.turns + (v.stage ? " · " + (v.stage.made ? "breakthrough made" : v.stage.turns_left + " left") : "");
      stageBar(v, prev);
      $("s-you").textContent = "You are " + v.you.name + " · aiming for " + v.path.name + (v.approach && v.approach.code !== "diplomat" ? " · " + v.approach.name : "") + (v.reputation ? " · known as " + v.reputation.replace(/^known to /, "someone known to ") : "");
      meter("m-influence", v.influence); meter("m-respect", v.respect);
      $("m-respect").classList.toggle("low", v.respect <= 2);
      var ap = $("s-ap"); ap.textContent = "";
      for (var i = 0; i < Math.max(v.ap, 0); i++) ap.appendChild(h("i", "on"));
      $("m-ap").setAttribute("aria-label", v.ap + " actions left this turn");
      $("c-chapter-h").textContent = v.phase === "summit" ? "The Summit" : (v.length === "quick" ? "Working session" : "Stage " + v.chapter + ": " + v.chapter_name);
      $("c-goal").textContent = v.phase === "chapter" ? v.goal : "The draft goes to the vote, clause by clause, then as a whole.";
      $("c-turn").textContent = v.phase === "chapter" ? "Turn " + v.turn + " of " + v.turns + ". " + (v.stage && v.stage.made ? "Breakthrough made: move on, or keep working until the deadline." :
        "The Chair moves on after turn " + v.turns + ", breakthrough or not.") : "";
      sources(v); rooms(v); sheets(v); stageLook(v); breakthroughCard(v, prev);
      if (v.phase === "chapter") progress(v); else $("c-progress").textContent = "";
      // news
      var ev = v.event, box = $("c-event-body"); box.textContent = "";
      $("c-event").hidden = !ev || v.phase !== "chapter";
      if (ev && v.phase === "chapter") {
        if (ev.hypothetical) box.appendChild(h("span", "s-hypo", "Hypothetical"));
        box.appendChild(h("p", "s-goal", ev.title));
        if (ev.body) box.appendChild(h("p", "", ev.body));
        if (ev.teaches && !v.question) box.appendChild(h("p", "s-small", ev.teaches));
        if (!prev || prev.turn !== v.turn || prev.chapter !== v.chapter) A.play("news");
      }
      var cr = v.phase === "chapter" && v.crisis && v.crisis.chapter === v.chapter ? v.crisis : null, cb = $("c-crisis-body");
      $("c-crisis").hidden = !cr; cb.textContent = "";
      if (cr) { cb.appendChild(h("p", "s-goal", cr.title)); cb.appendChild(h("p", "", cr.body)); cb.appendChild(h("p", "s-small", cr.teaches)); }
      var ol = $("c-agreement-list"); ol.textContent = "";                // one list of everything agreed (phase 14)
      $("c-agreements").hidden = !(v.agreements && v.agreements.length);
      (v.agreements || []).forEach(function (x) {
        var li = h("li", x.kept === true ? "kept" : x.kept === false ? "broken" : "");
        li.appendChild(h("b", "", x.name + ": ")); li.appendChild(document.createTextNode(x.what + (x.kept === true ? " (kept)" : x.kept === false ? " (broken)" : "")));
        ol.appendChild(li);
      });
      var il = $("c-instr-list"); il.textContent = "";
      [["in", "Get in: ", v.mandate.must.label], ["in", "Also get in: ", v.mandate.also.label], ["out", "Keep out: ", v.mandate.red.label]].forEach(function (x) {
        var li = h("li"); li.appendChild(h("span", x[0], x[1])); li.appendChild(document.createTextNode(x[2])); il.appendChild(li);
      });
      $("c-aim").textContent = "Your aim: " + v.path.name + ". " + v.path.what;
      regions(v);
      tug(v, prev);
      DLG.sheet(v); DLG.powers(v);
      if (prev && !turnChanged && !afterCard && $("s-chapter-card").hidden) DLG.offer(v);   // new visits mid-turn; at a turn change they follow the reel
      var nb = $("n-brief");                                          // what's waiting on the Brief: offers, a question
      if (nb) nb.textContent = v.phase === "chapter" && v.question ? "1" : "";
      staff(v);
      pins(v);
      var rs = $("s-reserve");
      rs.hidden = v.phase !== "chapter";
      rs.textContent = v.reserve ? "Reserve ready" : "Hold in reserve";
      rs.classList.toggle("ready", !!v.reserve);
      rs.disabled = !!v.reserve || !v.ap || !!v.unlock.reserve;
      rs.title = v.unlock.reserve || "Spend an action now to answer the first rival move against you before your next turn";
      rs.hidden = v.phase !== "chapter" || !!v.unlock.reserve;
      draft(v, prev);
      countryPicker(v); country(v); skills(v);
      // the delegate's reply, and anything else the move said
      if (out && out.heard) {
        heardIso = action.iso3 || out.talked;
        $("c-heard").hidden = false;
        var q = $("c-heard-text"); q.textContent = "";
        q.appendChild(document.createTextNode("“" + out.heard + "”"));
        q.appendChild(h("cite", "", "The delegate of " + (v.tokens[heardIso] || {}).name + (out.red_line ? " (a red line: they barely moved)" : "")));
        var landed = TALK.pitchAnswer(out); if (landed) q.appendChild(h("span", "s-intel", "Your pitch: " + landed));
        if (out.leans) q.appendChild(h("span", "s-intel", "Leaning towards each rival: " + Object.keys(out.leans).map(function (k) { return k + " " + (out.leans[k] > 0.3 ? "warm" : out.leans[k] < -0.3 ? "cold" : "neutral"); }).join(", ") + "."));
        if (out.would_vote) q.appendChild(h("span", "s-intel", "On the whole text as it stands, it would vote " + out.would_vote + "."));
        restart(q, "s-in");
      }
      if (out && out.file) showFile(out.file);
      if (action && action.do === "visit") DLG.after(v, out);
      if (action && action.do === "talk") DLG.talkStep(v, out, action);
      if (action && action.do === "answer") DLG.procAnswer(out);
      if (out && out.signed) signedCard(v, out.signed);
      if (action && (action.do === "deal" || action.do === "compromise")) TALK.answer(v, out || {}, action);
      else if (TALK.isOpen()) TALK.render();
      else if (out && action && action.do === "offer") say(out.refused_by_room ? "The working group wouldn't make the change, so the deal fell through." : out.accepted ? "Deal done." : "You turned the offer down.");
      else if (out && out.accepted === false) say(action.do === "strike" ? "The working group wants that clause, so it stays. Your Influence is returned." : "The working group didn't accept that amendment: it would lose support. Your Influence is returned.");
      else if (out && out.right !== undefined) say((out.right ? "Right. " : "Not quite. ") + out.why);
      else if (action && action.do === "end_turn") say(v.phase === "summit" ? "The summit opens." : "Rivals have moved: see the Record.");
      else if (action && action.do === "speech") say("You gave a " + action.stance + " opening speech. The first clause is before the committee.");
      // rivals and the record
      var rl = $("c-rival-list"); rl.textContent = "";
      v.rivals.forEach(function (r) {
        var li = h("li", "rival s-rival-" + r.style);
        li.appendChild(h("b", "", r.name)); li.appendChild(h("span", "s-style", r.style_name));
        li.appendChild(h("span", "s-small", r.style_what + " " + (r.want ? "Wants " + r.want.toLowerCase() + "; blocks " + r.block.toLowerCase() + "." : "Its instructions are unknown (Rival intelligence reveals them).")));
        rl.appendChild(li);
      });
      var lg = $("c-log"); lg.textContent = "";
      var fresh = v.log.length - Math.min(seenLog, v.log.length), news = seenLog ? v.log.slice(v.log.length - fresh) : [];
      v.log.slice().reverse().forEach(function (x, k) { lg.appendChild(h("li", x.kind + (k < fresh && seenLog ? " fresh" : ""), x.when + ": " + x.text)); });
      seenLog = v.log.length;
      // the map
      Object.keys(tokens).forEach(function (iso) {
        var t = tokens[iso], d = v.tokens[iso] || {};
        t.classList.toggle("you", !!d.you); t.classList.toggle("rival", !!d.rival); t.classList.toggle("signed", !!d.signed);
        t.classList.toggle("lean-for", !d.you && !d.rival && d.est === "yes"); t.classList.toggle("lean-against", !d.you && !d.rival && d.est === "no");
        t.classList.toggle("trust-pos", d.relation > 0); t.classList.toggle("trust-neg", d.relation < 0);
        t.classList.toggle("committed", !!(d.commitments || []).length); t.classList.toggle("truce", !!d.truce);
        t.classList.toggle("endorsed-you", v.regions.some(function (r) { return r.owner === "you" && r.members.indexOf(iso) >= 0; }));
        var line = t.querySelector(".b-line");
        if (line) line.textContent = d.you ? "You" : d.rival ? "Rival" : d.est === "yes" ? "For" : d.est === "no" ? "Against" : d.est ? "Unsure" : "";
      });
      // spheres of influence: like borders on a campaign map, the land of each delegation takes the colour of whoever it leans to
      Object.keys(lands).forEach(function (iso) {
        var d = v.tokens[iso] || {}, sph = d.you ? "you" : d.rival ? "rival" : d.est === "yes" ? "you" : (d.est === "no" && d.sphere === "rival") ? "rival" : null;
        lands[iso].forEach(function (l) { l.classList.toggle("terr-you", sph === "you"); l.classList.toggle("terr-rival", sph === "rival"); });
      });
      // envoys: each move this turn travels across the map, from whoever made it to the delegation it was about
      news.forEach(function (x, k) {
        if (!x.at || !tokens[x.at]) return;
        var from = x.who === "you" ? v.you.iso3 : x.who;
        setTimeout(function () { envoy(from, x.at, x.kind === "rival"); }, 380 * k);
      });
      if (news.some(function (x) { return x.kind === "rival"; })) setTimeout(function () { A.play("paper"); }, 300);
      if (prev) {
        var won = v.regions.some(function (r) { return r.owner === "you" && !prev.regions.some(function (p) { return p.code === r.code && p.owner === "you"; }); });
        var lost = prev.regions.some(function (p) { return p.owner === "you" && !v.regions.some(function (r) { return r.code === p.code && r.owner === "you"; }); });
        if (won) { A.play("fanfare"); say("A regional group now endorses your draft."); } else if (lost) { A.play("sting"); say("A regional group no longer endorses your draft."); }
        moments(v, prev, news, won, lost, turnChanged);
        if (turnChanged) {
          var reelItems = REEL.build(v, prev, news);
          if (prev.chapter !== v.chapter) afterCard = reelItems;            // after the stage card (and its intro)
          else setTimeout(function () { REEL.play(reelItems, function () { DLG.offer(V); }); }, 500);
        }
      }
      $("s-end-turn").hidden = v.phase !== "chapter";
      summitTabs(v);
      summitPane(v, out);
      if (!prev ? (v.turn === 1 && v.phase === "chapter" && seenLogAtStart(v)) : (prev.chapter !== v.chapter || prev.phase !== v.phase)) {
        if (!prev && guideOn() && v.chapter === 1) WALK.start(v, function () { chapterCard(v, prev); }, "intro");
        else chapterCard(v, prev);
      }
    }
    function seenLogAtStart(v) { return v.log.filter(function (x) { return x.kind === "action"; }).length === 0; }

    // ---------- the summit ----------
    var STANCE = {
      firm: ["Firm", "State your country's position plainly. Delegations that share your main aim warm to you; those against it cool a little."],
      open: ["Open", "Listen first and acknowledge the other side. The room respects it: +1 Standing."],
      bridge: ["Bridge", "Speak to the undecided. Delegations in the middle warm to you."]
    };
    var GRADE = ["No medal", "Bronze", "Silver", "Gold"];
    var choice = "stand", timer = null, shownStep = null;
    function stopTimer() { if (timer) { clearTimeout(timer); timer = null; } }
    function defaultVote(cur) { return cur.stance > 0 ? "yes" : cur.stance < 0 ? "no" : "abstain"; }

    function summitTabs(v) {
      var summit = v.phase !== "chapter";
      ["brief", "draft", "dele", "coalition"].forEach(function (t) { if (summit) $("t-" + t).hidden = true; });
      if (!summit) ["brief", "draft", "dele"].forEach(function (t) { $("t-" + t).hidden = false; });
      $("t-summit").hidden = !summit;
      if (summit && $("t-summit").getAttribute("aria-selected") !== "true" && $("t-record").getAttribute("aria-selected") !== "true") setTab("summit");
    }

    function summitPane(v, out) { SUMMIT.render(v, out); }       // the Summit's own module (D-102)

    function sweep(votes, passed) {
      Object.keys(tokens).forEach(function (iso) { tokens[iso].classList.remove("v-yes", "v-no", "v-abstain"); });
      var order = Object.keys(votes).sort(function (a, b) {
        var ta = tokens[a], tb = tokens[b];
        return (ta ? +ta.getAttribute("data-x") : 0) - (tb ? +tb.getAttribute("data-x") : 0);
      });
      var step = A.motionOn() ? 70 : 0;
      A.play("sweep");
      order.forEach(function (iso, k) {
        setTimeout(function () {
          var t = tokens[iso]; if (!t) return;
          t.classList.add("v-" + votes[iso]); if (step) restart(t, "v-cast"); if (k % 4 === 0) A.play("tick");
          var line = t.querySelector(".b-line"); if (line) line.textContent = { yes: "Yes", no: "No", abstain: "Abstain" }[votes[iso]] || "";
        }, k * step);
      });
      setTimeout(function () {
        var vd = $("s-verdict"); vd.className = "s-verdict " + (passed ? "yes" : "no");
        vd.querySelector("span").textContent = passed ? "Adopted" : "Rejected";
        restart(vd, "show"); A.play("stamp");
        setTimeout(function () { A.play(passed ? "fanfare" : "sting"); }, 300);
      }, order.length * step + 200);
      return order.length * step + 2900;
    }

    function result(v) {
      var r = v.result; if (!r) return;
      if (mode === "guest" && window.socSession.record) window.socSession.record(v, guest);   // a guest's record lives in this browser
      var d = v.debrief || {}, p = v.path, grade = r.grade;
      $("s-result-eyebrow").textContent = r.recalled ? "Your capital has lost confidence in you" : r.passed ? "The resolution was adopted" :
        r.statement ? "A Presidential Statement was agreed" : "The resolution failed";
      $("s-result-h").textContent = r.recalled ? "Recalled for consultations" : GRADE[grade] + " for " + p.name;
      var b = $("s-result-body"); b.textContent = "";
      // the rank plaque and the four medals
      if (d.rank) {
        var pl = h("div", "s-plaque");
        pl.appendChild(h("span", "s-plaque-k", "Your rank"));
        pl.appendChild(h("b", "", d.rank.name));
        pl.appendChild(h("span", "", d.points + " of 12 points" + (d.rank.next ? " · " + d.rank.to_next + " more to " + d.rank.next : " · the highest rank")));
        b.appendChild(pl);
      }
      var row = h("div", "s-medals");
      Object.keys(r.paths).forEach(function (k, i) {
        var g = r.paths[k], m = h("div", "s-medal" + (k === p.code ? " chosen" : ""));
        var coin = h("i", "g" + g, GRADE[g]); coin.style.animationDelay = (0.15 + i * 0.18) + "s";
        m.appendChild(coin); m.appendChild(h("b", "", k.charAt(0).toUpperCase() + k.slice(1)));
        m.appendChild(h("span", "", k === p.code ? "your aim" : ""));
        row.appendChild(m);
      });
      b.appendChild(row);
      b.appendChild(h("p", "s-sub s-center", "You aimed for " + p.name + ": " + p.what + "  Predictions right: " + r.whip_right + " of " + r.whip_judged +
                                             " · promises kept " + r.kept_promises + ", broken " + r.broken_promises + " · Standing " + r.respect + " · Expertise " + r.expertise + "."));
      if (d.history && d.history.length > 1) b.appendChild(chart(d.history));
      if (d.clauses && d.clauses.length) b.appendChild(deeds(d.clauses));
      if (d.moments && d.moments.length) {
        var mo = h("div", "s-debrief"); mo.appendChild(h("h3", "", "Turning points"));
        var ul = h("ol", "s-moments");
        d.moments.forEach(function (x) { var li = h("li", x.kind); li.appendChild(h("span", "s-when", x.when)); li.appendChild(document.createTextNode(x.text)); ul.appendChild(li); });
        mo.appendChild(ul); b.appendChild(mo);
      }
      var chief = h("div", "s-chief-says"), face = h("div", "s-chief-face");
      if (G) face.appendChild(G.portrait(grade >= 2 ? "delighted" : grade === 1 ? "wry" : "concerned"));
      chief.appendChild(face);
      chief.appendChild(h("p", "", grade === 3 ? "Superb work, Ambassador. They will be studying this session for years." :
        grade === 2 ? "Well done, Ambassador. A fine session, and there was more within reach: the dossier shows where." :
        grade === 1 ? "A respectable session. Read the turning points below: the next one will go further." :
        "A hard session, Ambassador. Every great delegate has one. The dossier below shows exactly what happened, and why."));
      b.insertBefore(chief, b.firstChild);
      if (v.debrief && v.debrief.capital) {
        var cp = h("div", "s-debrief"); cp.appendChild(h("h3", "", "Your standing"));
        cp.appendChild(h("p", "", "Standing at the end: " + v.debrief.capital.confidence + " of " + v.debrief.capital.of + ". " +
          v.debrief.capital.deals + " deal" + (v.debrief.capital.deals === 1 ? "" : "s") + " made." +
          (v.debrief.capital.recalled ? " You were recalled before the summit." : "")));
        b.appendChild(cp);
      }
      if (r.passed) {
        var ex = btn("Download the resolution (Word)", "s-btn", function () {
          var body = mode === "saved" ? { do: "export", save_id: +saveId } : { do: "export", state: guest.state, sig: guest.sig };
          api(body).then(function (j) {
            var bin = atob(j.docx), arr = new Uint8Array(bin.length); for (var i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
            var a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([arr], { type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" }));
            a.download = j.name; document.body.appendChild(a); a.click(); a.remove();
          }).catch(function (e) { sayError(e.message); });
        });
        var exw = h("div", "s-row s-export"); exw.appendChild(ex); exw.appendChild(h("span", "s-sub", "The adopted text, set out as a resolution."));
        b.appendChild(exw);
      }
      if (v.debrief && v.debrief.ledger && v.debrief.ledger.length) {
        var lg = h("div", "s-debrief"); lg.appendChild(h("h3", "", "Your commitments"));
        var lu = h("ul", "s-ledger");
        v.debrief.ledger.forEach(function (x) {
          var li = h("li", x.kept === true ? "kept" : x.kept === false ? "broken" : "");
          li.appendChild(h("b", "", x.name)); li.appendChild(document.createTextNode(": " + x.what + (x.kept === true ? ". Kept." : x.kept === false ? ". Broken." : ".")));
          lu.appendChild(li);
        });
        lg.appendChild(lu); b.appendChild(lg);
      }
      if (v.debrief && v.debrief.half_loaf) {
        var hl = h("div", "s-debrief s-loaf"); hl.appendChild(h("h3", "", "Half a loaf"));
        hl.appendChild(h("p", "", v.debrief.half_loaf.verdict));
        if (v.debrief.half_loaf.gained.length) hl.appendChild(h("p", "s-sub", "Your aims in the resolution: " + v.debrief.half_loaf.gained.join("; ") + "."));
        b.appendChild(hl);
      }
      if (v.debrief && v.debrief.rivals && v.debrief.rivals.length) {
        var rvb = h("div", "s-debrief"); rvb.appendChild(h("h3", "", "Your rivals"));
        var ul = h("ul", "s-rival-out");
        v.debrief.rivals.forEach(function (r) {
          var li = h("li", r.won ? "won" : ""); li.appendChild(h("b", "", r.name)); li.appendChild(h("span", "s-style", r.style));
          li.appendChild(h("span", "", " " + r.verdict + ". It wanted a clause that " + lcf(r.want) + ", and nothing that " + lcf(r.block) + "."));
          ul.appendChild(li);
        });
        rvb.appendChild(ul); b.appendChild(rvb);
      }
      if (v.debrief && v.debrief.staff && v.debrief.staff.length) {
        var sb = h("div", "s-debrief"); sb.appendChild(h("h3", "", "Your staff"));
        sb.appendChild(h("p", "s-sub", v.debrief.staff.map(function (a) { return a.name + " (" + a.kind + ", " + "★".repeat(a.stars) + ")"; }).join(" · ")));
        b.appendChild(sb);
      }
      debriefInto(b, v);
      hideAdvice();
      open("s-result");
      var doc = document.querySelector("#s-result .s-final"); doc.scrollTop = 0;
      var hd = $("s-result-h"); hd.tabIndex = -1; hd.focus();
      A.play("stamp");
      setTimeout(function () { A.play(grade >= 2 ? "fanfare" : grade === 1 ? "chime" : "sting"); }, 500);
    }

    // the session in numbers: your standing turn by turn, drawn like an old campaign ledger
    function chart(hist) {
      var box = h("div", "s-debrief"); box.appendChild(h("h3", "", "The session in numbers"));
      var W = 1040, H = 230, L = 46, T = 14, n = hist.length;
      var ns = "http://www.w3.org/2000/svg", svg = document.createElementNS(ns, "svg");
      svg.setAttribute("viewBox", "0 0 " + W + " " + (H + 46)); svg.setAttribute("class", "s-chart"); svg.setAttribute("role", "img");
      var last = hist[n - 1];
      svg.setAttribute("aria-label", "Your standing turn by turn. At the end: " + last.leaning + " of " + last.of + " delegations leaning your way, Influence " + last.influence + ", Standing " + last.respect + ".");
      function el(tag, attrs, text) { var e = document.createElementNS(ns, tag); Object.keys(attrs).forEach(function (k) { e.setAttribute(k, attrs[k]); }); if (text != null) e.textContent = text; svg.appendChild(e); return e; }
      for (var gy = 0; gy <= 4; gy++) el("line", { x1: L, x2: W - 10, y1: T + gy * H / 4, y2: T + gy * H / 4, class: "s-grid" });
      var maxI = 1.15 * Math.max.apply(null, hist.map(function (x) { return x.influence; }).concat([10]));
      var series = [
        ["Support", "s-l-support", function (x) { return x.of ? x.leaning / x.of : 0; }, function (x) { return x.leaning + " of " + x.of; }],
        ["Influence", "s-l-influence", function (x) { return x.influence / maxI; }, function (x) { return String(x.influence); }],
        ["Standing", "s-l-respect", function (x) { return x.respect / 10; }, function (x) { return String(x.respect); }]
      ];
      function X(i) { return L + (n === 1 ? 0 : i * (W - L - 190) / (n - 1)); }
      hist.forEach(function (x, i) {
        if (i === 0 || hist[i - 1].at.split(".")[0] !== x.at.split(".")[0]) el("text", { x: X(i), y: H + T + 22, class: "s-tick" }, x.at === "Summit" ? "Summit" : x.at.split(".")[0].replace("C", "Ch ").replace("W", "Work"));
      });
      var ends = [];
      series.forEach(function (sr, k) {
        var d = hist.map(function (x, i) { return (i ? "L" : "M") + X(i).toFixed(1) + " " + (T + H - Math.min(1, sr[2](x)) * H).toFixed(1); }).join(" ");
        var path = el("path", { d: d, class: "s-line " + sr[1] });
        path.style.animationDelay = (0.3 + k * 0.35) + "s";
        var y = T + H - Math.min(1, sr[2](last)) * H;
        el("circle", { cx: X(n - 1), cy: y, r: 6, class: "s-dot " + sr[1] });
        ends.push([y, sr]);
      });
      ends.sort(function (a, b) { return a[0] - b[0]; });
      var lastY = -99;
      ends.forEach(function (e) { var y = Math.max(e[0] + 5, lastY + 20); lastY = y; el("text", { x: X(n - 1) + 12, y: y, class: "s-end " + e[1][1] }, e[1][0] + " " + e[1][3](last)); });
      box.appendChild(svg);
      box.appendChild(h("p", "s-sub", "Support: delegations leaning your way. Influence and Standing at the end of each turn."));
      return box;
    }

    // every clause as a title deed: whose it was, and whether the committee granted it
    function deeds(clauses) {
      var box = h("div", "s-debrief"); box.appendChild(h("h3", "", "Title deeds: the resolution, clause by clause"));
      var grid = h("div", "s-deeds");
      clauses.forEach(function (c, i) {
        var card = h("div", "s-deed own-" + c.owner + (c.passed ? "" : " struck"));
        card.style.animationDelay = (0.2 + i * 0.12) + "s";
        var band = h("div", "s-deed-band"); band.appendChild(h("span", "", "Title deed")); band.appendChild(h("b", "", "Clause " + (i + 1)));
        card.appendChild(band);
        card.appendChild(h("p", "s-deed-what", c.labels.join("; ")));
        var dl = h("dl", "s-deed-rows");
        [["Held by", c.owner_name], ["Amended by", c.amended.length ? c.amended.join(", ") : "nobody"], ["Yes", c.yes], ["No", c.no], ["Abstain", c.abstain]].forEach(function (x) {
          dl.appendChild(h("dt", "", x[0])); dl.appendChild(h("dd", "", String(x[1])));
        });
        card.appendChild(dl);
        card.appendChild(h("span", "s-deed-stamp", c.passed ? "Adopted" : "Struck off"));
        grid.appendChild(card);
      });
      box.appendChild(grid);
      return box;
    }

    function envoy(fromIso, toIso, rival) {
      var a = tokens[fromIso], b = tokens[toIso];
      var land = function () { restart(b, rival ? "s-pulse-rival" : "s-pulse"); };
      if (!a || !b || a === b || !A.motionOn()) { if (b) land(); return; }
      var ns = "http://www.w3.org/2000/svg", x1 = +a.getAttribute("data-x"), y1 = +a.getAttribute("data-y");
      var c = document.createElementNS(ns, "circle");
      c.setAttribute("r", "7"); c.setAttribute("cx", x1); c.setAttribute("cy", y1); c.setAttribute("class", "s-envoy" + (rival ? " rival" : ""));
      $("b-tokens").appendChild(c);
      requestAnimationFrame(function () { requestAnimationFrame(function () {
        c.style.transform = "translate(" + (+b.getAttribute("data-x") - x1) + "px," + (+b.getAttribute("data-y") - y1) + "px)";
      }); });
      setTimeout(function () { c.remove(); land(); }, 1000);
    }

    // ---------- the Chief of Protocol: a walkthrough of the whole session before it begins, and advice at key moments ----------
    var G = window.socSession && window.socSession.guide;
    function guideOn() { return A.settings().tips !== false; }
    // advice: one short remark at a time, at the moments that matter, never over a card or the walkthrough
    var queue = [], adviceTimer = null, adviceFace = null, said = {};
    function advise(face, text, once, adv) {
      if (!guideOn() || !G) return;
      if (once) { if (said[once]) return; said[once] = true; }
      queue.push({ face: face, text: text, adv: adv || null });
      if (queue.length > 3) queue.shift();
      setTimeout(adviceNext, 900);
    }
    function hideAdvice() {
      var a = $("s-advice"); if (a) a.hidden = true;
      if (adviceTimer) { clearTimeout(adviceTimer); adviceTimer = null; }
    }
    function adviceNext() {
      var a = $("s-advice");
      if (!a || !queue.length || !a.hidden || !$("s-walk").hidden || document.querySelector(".s-overlay:not([hidden])")) return;
      if (V && V.phase === "done") { queue = []; return; }
      var x = queue.shift();
      var holder = $("s-advice-face");
      a.classList.toggle("s-telegram", !!x.tele);
      if (x.pres) {
        holder.textContent = ""; adviceFace = null;
        holder.appendChild(G.portrait(x.face, "president"));
        $("s-advice-h").textContent = "The President of the committee";
      } else if (x.tele) {
        holder.textContent = ""; adviceFace = null;
        holder.appendChild(G.portrait(x.face, "minister"));
        $("s-advice-h").textContent = "Telegram from your capital";
      } else if (x.adv) {
        holder.textContent = ""; adviceFace = null;
        holder.appendChild(staffIcon(x.adv.kind, x.adv.stars, 112));
        $("s-advice-h").textContent = x.adv.name + ", " + x.adv.kind_name;
      } else {
        if (!adviceFace) { holder.textContent = ""; adviceFace = G.portrait(x.face); holder.appendChild(adviceFace); }
        G.face(adviceFace, x.face);
        $("s-advice-h").textContent = "The Chief of Protocol";
      }
      $("s-advice-text").textContent = x.text;
      if (x.tele && A.motionOn()) typeOut($("s-advice-text"), x.text);
      a.hidden = false; restart(a, "s-advice-in"); if (adviceFace) restart(adviceFace, "g-react");
      A.play("flip");
      adviceTimer = setTimeout(function () { if (!a.matches(":hover") && !a.contains(document.activeElement)) { hideAdvice(); setTimeout(adviceNext, 400); } }, 9000);
    }
    $("s-advice-ok").addEventListener("click", function () { hideAdvice(); setTimeout(adviceNext, 300); });

    // what's worth a remark: new chapters and their crises, deals at the door, intelligence, lost clauses, groups won and lost
    function president(face, text, once) {
      if (!G || !guideOn()) return;
      if (once) { if (said[once]) return; said[once] = true; }
      queue.push({ pres: true, face: face, text: text }); if (queue.length > 3) queue.shift();
      setTimeout(adviceNext, 900);
    }
    function moments(v, prev, news, won, lost, turnChanged) {
      var aide = (v.staff || [])[0] || null;
      if (prev.phase === "chapter" && v.phase === "summit") advise("eyebrow", "The Summit is open. Choose how to open your speech: firm to rally your friends, open for Standing, bridge for the undecided.");
      if (won) advise("delighted", "A regional group now stands behind your draft. Rivals will try to win it back.", null, aide);
      if (lost) advise("concerned", "We've lost a regional group's endorsement. A side event or its meeting can win it back.", null, aide);
      if (!turnChanged) news.forEach(function (x) {                  // the turn's news is the reel's; these come mid-turn
        if (x.kind === "worry" || x.kind === "promote") advise(x.kind === "promote" ? "delighted" : "concerned", x.text, null, staffOf(v, x.text) || aide);
        if (x.kind === "counter") advise("delighted", x.text, null, aide);
        if (x.kind === "telegram") telegram(x.text, x.mood);
      });
      if (v.phase === "chapter" && prev.chapter !== v.chapter && prev.objectives) {
        var met = v.objectives[String(prev.chapter)];
        if (met !== undefined) advise(met ? "delighted" : "concerned", met ? "Breakthrough made. The committee has noticed." : "We missed that breakthrough. No matter: what counts is the final vote.");
      }
      if (v.phase === "chapter" && v.ap === 0) advise("calm", "Your actions are spent. End the turn when you're ready.", "ap0");
      if (v.phase === "chapter" && v.xp >= v.skill_cost) advise("wry", "Your staff have know-how enough for a new skill. Open Staff skills to choose one.", "skill");
    }

    // ---------- phase 8: the vote as it stands, your staff, and their pins on the map ----------
    function lcf(t) { t = String(t || "").replace(/\.$/, ""); return /^.[a-z]/.test(t) ? t.charAt(0).toLowerCase() + t.slice(1) : t; }
    function chiefNote(face, text) {
      var d = h("div", "s-chief-says s-chief-note"), f = h("div", "s-chief-face");
      if (G) f.appendChild(G.portrait(face));
      d.appendChild(f); d.appendChild(h("p", "", text));
      return d;
    }
    function staffOf(v, text) {
      var a = (v.staff || []).filter(function (x) { return text.indexOf(x.name) === 0; })[0];
      return a || null;
    }
    // each adviser's icon: a brass roundel with the tool of their trade (a magnifying glass, a globe, the scales)
    var GLYPH = {
      analyst: "M22 22 m-9 0 a9 9 0 1 0 18 0 a9 9 0 1 0 -18 0 M28.5 28.5 L37 37",
      regional: "M24 24 m-12 0 a12 12 0 1 0 24 0 a12 12 0 1 0 -24 0 M12 24 H36 M24 12 C17 18 17 30 24 36 M24 12 C31 18 31 30 24 36",
      legal: "M24 11 V36 M15 36 H33 M12 17 H36 M12 17 L8 27 H16 Z M36 17 L32 27 H40 Z"
    };
    function staffIcon(kind, stars, size) {
      var ns = "http://www.w3.org/2000/svg", svg = document.createElementNS(ns, "svg");
      svg.setAttribute("viewBox", "0 0 48 " + (stars ? 60 : 48)); svg.setAttribute("width", size); svg.setAttribute("height", stars ? size * 1.25 : size);
      svg.setAttribute("class", "s-ico s-ico-" + kind); svg.setAttribute("aria-hidden", "true");
      function el(tag, attrs) { var e = document.createElementNS(ns, tag); Object.keys(attrs).forEach(function (k) { e.setAttribute(k, attrs[k]); }); svg.appendChild(e); return e; }
      el("circle", { cx: 24, cy: 24, r: 22, class: "s-ico-disc" });
      el("circle", { cx: 24, cy: 24, r: 18.5, class: "s-ico-ring" });
      el("path", { d: GLYPH[kind] || GLYPH.analyst, class: "s-ico-glyph" });
      for (var i = 0; i < (stars || 0); i++) el("path", { d: "M" + (24 + (i - (stars - 1) / 2) * 12) + " 49 l2.4 4.9 5.4.8-3.9 3.8.9 5.4-4.8-2.5-4.8 2.5.9-5.4-3.9-3.8 5.4-.8z", class: "s-ico-star", transform: "scale(1 .9) translate(0 " + 5 + ")" });
      return svg;
    }
    function tug(v, prev) {
      var t = v.tug, box = $("s-tug"); if (!t) return;
      box.hidden = v.phase !== "chapter";            // at the summit the real votes take over
      var bar = box.querySelectorAll(".s-tug-bar i"), of = Math.max(1, t.of);
      bar[0].style.width = (100 * t.yes / of) + "%"; bar[1].style.width = (100 * t.abstain / of) + "%"; bar[2].style.width = (100 * t.no / of) + "%";
      var veto = /vetoed by ([^–—;.]+)/.exec(t.summary || "");
      $("s-tug-n").textContent = t.yes + " yes · " + t.abstain + " abstain · " + t.no + " no" + (veto ? " · vetoed by " + veto[1].trim() : "");
      var st = $("s-tug-stamp");
      st.textContent = t.passed ? "Would pass" : "Would fail"; st.className = "s-tug-stamp " + (t.passed ? "pass" : "fail");
      var ai = $("s-tug-aims"); if (ai) ai.textContent = t.aims !== undefined ? "Your instructions: " + t.aims + " of 3 in the text" : "";
      box.setAttribute("aria-label", "If the vote were now: " + t.summary);
      if (prev && prev.tug && (prev.tug.yes !== t.yes || prev.tug.no !== t.no)) restart(box, "s-tug-move");
      if (prev && prev.tug && prev.tug.passed !== t.passed && v.phase === "chapter") {
        A.play(t.passed ? "chime" : "sting");
        advise(t.passed ? "delighted" : "concerned", t.passed ? "As things stand, the draft would pass. Hold the room: rivals will try to turn it." :
                                                        "As things stand, the draft would fail. Find the delegations closest to tipping.", null, (v.staff || [])[0]);
      }
    }
    function staff(v) {
      var ul = $("c-staff-list"); ul.textContent = "";
      var others = Object.keys(v.tokens).filter(function (k) { return k !== v.you.iso3; })
        .sort(function (a, b) { return v.tokens[a].name < v.tokens[b].name ? -1 : 1; });
      (v.staff || []).forEach(function (a) {
        var li = h("li", "s-adviser");
        li.appendChild(staffIcon(a.kind, a.stars, 60));
        var body = h("div", "s-adviser-body");
        var top = h("p", "s-adviser-name"); top.appendChild(h("b", "", a.name)); top.appendChild(document.createTextNode(" · " + a.kind_name + ", " + a.rank));
        body.appendChild(top);
        if (a.next_star) {
          var xp = h("span", "s-xp"); xp.setAttribute("role", "img"); xp.setAttribute("aria-label", a.xp + " of " + a.next_star + " towards promotion");
          var fill = h("i"); fill.style.width = Math.min(100, 100 * a.xp / a.next_star) + "%"; xp.appendChild(fill); body.appendChild(xp);
        }
        var row = h("div", "s-row"), id = "s-post-" + a.id;
        var lab = h("label", "s-small", "Studies"); lab.setAttribute("for", id); row.appendChild(lab);
        var sel = h("select"); sel.id = id; opt(sel, "", "Nobody: back at the mission");
        others.forEach(function (iso) { opt(sel, iso, v.tokens[iso].name + (v.tokens[iso].rival ? " (rival)" : "")); });
        sel.value = a.post || "";
        sel.disabled = v.phase === "done" || !!v.unlock.post;
        if (v.unlock.post) sel.title = v.unlock.post;
        sel.addEventListener("change", function () { move({ do: "post", adviser: a.id, iso3: sel.value || null }); });
        row.appendChild(sel); body.appendChild(row);
        var rep = h("p", "s-report");
        if (a.report) { rep.appendChild(h("span", "s-sure s-sure-" + a.report.stars, a.report.sure)); rep.appendChild(document.createTextNode(" " + a.report.text)); }
        else rep.textContent = v.unlock.post ? "Blocked until Bloc meetings: advisers can be posted from the second stage." :
          a.post ? (a.starts ? "Starts reporting next turn." : "No report yet.") : a.what;
        body.appendChild(rep);
        li.appendChild(body); ul.appendChild(li);
      });
      var n = (v.staff || []).length, full = n >= v.costs.staff_max;
      $("c-hire-note").textContent = (v.unlock.post ? "Posting and hiring advisers " + v.unlock.post.toLowerCase().replace("that opens", "open") + " " : "") +
        n + " of " + v.costs.staff_max + " advisers. A new adviser starts as a junior and costs " + v.costs.hire + " Influence.";
      var hr = $("c-hire-row"); hr.textContent = "";
      (v.staff_kinds || []).forEach(function (k) {
        hr.appendChild(btn(k.name + " (" + v.costs.hire + " Influence)", "s-btn ghost small", function () { move({ do: "hire", kind: k.code }); },
                           full || v.influence < v.costs.hire || v.phase !== "chapter" || !!v.unlock.hire));
      });
    }
    function pins(v) {
      var layer = $("b-tokens"); if (!layer) return;
      layer.querySelectorAll(".s-pin").forEach(function (p) { p.remove(); });
      (v.staff || []).forEach(function (a) {
        var t = a.post && tokens[a.post]; if (!t) return;
        var ic = staffIcon(a.kind, 0, 26);
        ic.setAttribute("x", +t.getAttribute("data-x") + 14); ic.setAttribute("y", +t.getAttribute("data-y") - 34);
        ic.setAttribute("class", ic.getAttribute("class") + " s-pin");
        var tt = document.createElementNS("http://www.w3.org/2000/svg", "title"); tt.textContent = a.name + " studies " + a.post_name; ic.appendChild(tt);
        layer.appendChild(ic);
      });
      Object.keys(tokens).forEach(function (iso) { tokens[iso].classList.toggle("secured", !!(v.tokens[iso] || {}).secured); });
    }

    // ---------- phase 9: dossiers, the deal table and your capital ----------
    var ASK = { funding: "development money", trade: "access to markets", candidacy: "backing for a candidacy", clause: "its favourite clause" };
    function dossierBox(d, open) {
      var box = h("details", "s-dossier-box"); if (open) box.open = true;
      box.appendChild(h("summary", "", "Dossier: economy and trade"));
      var dl = h("dl", "s-facts s-dossier");
      d.rows.forEach(function (r) { dl.appendChild(h("dt", "", r.label)); dl.appendChild(h("dd", "", r.value + (r.year ? " (" + r.year + ")" : ""))); });
      box.appendChild(dl);
      var src = h("p", "s-small s-source"), a = h("a", "", d.source); a.href = d.url; a.target = "_blank"; a.rel = "noopener";
      src.appendChild(document.createTextNode("Source: ")); src.appendChild(a); src.appendChild(document.createTextNode(". Real figures, each with its year."));
      box.appendChild(src);
      return box;
    }
    function telegram(text, mood) {
      if (!G) return;
      queue.push({ tele: true, face: mood === "approve" ? "delighted" : mood === "furious" ? "concerned" : "eyebrow", text: text });
      if (queue.length > 3) queue.shift();
      A.play("paper");
      setTimeout(adviceNext, 900);
    }
    function typeOut(el, text) {
      el.textContent = ""; var i = 0;
      el.setAttribute("aria-label", text);
      (function step() { if (i > text.length || !el.isConnected) return; el.textContent = text.slice(0, i); i += 2; setTimeout(step, 22); })();
    }
    // ---------- phase 11: stages, breakthroughs, the President, a growing delegation, rooms and sheets ----------
    function stageBar(v) {
      var bar = $("s-stagebar"); if (!bar) return;
      bar.textContent = "";
      var stops = (v.stage_track || []).map(function (s) { return [s.n, s.name]; }).concat([["★", "Summit"]]);
      stops.forEach(function (x, i) {
        var n = x[0], done = v.phase !== "chapter" ? n !== "★" || v.phase === "done" : n !== "★" && n < v.chapter;
        var now = v.phase === "chapter" ? n === v.chapter : v.phase === "summit" && n === "★";
        var c = h("span", "s-sb" + (now ? " now" : done ? " done" : ""));
        c.appendChild(h("i", "", done && !now ? "✓" : String(n))); c.appendChild(h("b", "", x[1]));
        bar.appendChild(c);
      });
    }
    function sources(v) {
      var ul = $("c-ap-list"); if (!ul) return;
      ul.textContent = "";
      (v.ap_sources || []).forEach(function (x) {
        var li = h("li", x.n ? "on" : "off");
        var pips = h("span", "s-pips"); for (var i = 0; i < Math.max(x.n, x.next ? 1 : 0); i++) pips.appendChild(h("i", i < x.n ? "on" : "locked"));
        li.appendChild(pips); li.appendChild(h("b", "", x.name + (x.n ? " +" + x.n : "")));
        if (x.next) li.appendChild(h("span", "s-small", "Next: " + x.next + "."));
        ul.appendChild(li);
      });
    }
    var SIDE = { you: "leans your way", rival: "leans to a rival", undecided: "undecided", self: "you", "rival-self": "a rival" };
    function rooms(v) {
      var ul = $("c-rooms"); if (!ul) return;
      ul.textContent = "";
      var mb = $("c-meeting-body"); mb.textContent = "";
      if (v.meeting) {
        mb.appendChild(h("p", "s-goal", "This turn the " + v.meeting.name + " meets."));
        mb.appendChild(h("p", "s-small", "Attend (1 action, " + 1 + " Influence) to work every member at once. Advisers read its members one star better while it meets."));
        mb.appendChild(btn(v.meeting.attended ? "You attended this turn" : "Attend the meeting", "s-btn small", function () { move({ do: "attend" }); },
                           v.meeting.attended || !v.ap || v.influence < 1));
      } else mb.appendChild(h("p", "s-small", "No group meets this turn."));
      (v.rooms || []).forEach(function (r) {
        var li = h("li", "s-room" + (r.meeting ? " meeting" : "") + (r.owner_you ? " yours" : r.owner ? " theirs" : ""));
        var hd = h("p", "s-room-h"); hd.appendChild(h("b", "", r.name)); if (r.meeting) hd.appendChild(h("span", "s-style", "In session"));
        li.appendChild(hd);
        li.appendChild(h("p", "s-small", (r.owner ? "Endorses " + (r.owner_you ? "your draft" : r.owner + "'s") : "No endorsement yet") + " · " + r.yours + " of " + r.needed + " needed lean your way · coordinator: " + r.coordinator +
                         (r.courting.length ? " · courted by " + r.courting.join(", ") : "")));
        var chips = h("div", "s-chips");
        r.members.forEach(function (m) { var c = h("span", "s-chip-m " + m.side, m.name); c.title = m.name + ": " + (m.rival ? "leans to " + m.rival : SIDE[m.side]); chips.appendChild(c); });
        li.appendChild(chips); ul.appendChild(li);
      });
      var nb = $("n-coalition"); if (nb) nb.textContent = v.meeting && !v.meeting.attended ? "!" : "";
    }
    function sheets(v) {
      var ul = $("c-sheets"); if (!ul) return;
      ul.textContent = "";
      (v.race || []).forEach(function (r) {
        var li = h("li", "s-sheet" + (r.you ? " yours" : "") + (r.tabled ? " tabled" : ""));
        li.appendChild(h("b", "", r.you ? "Your draft" : r.who + "'s draft"));
        var bar = h("div", "s-sheet-bar"), f = h("i");
        f.style.width = Math.min(100, 100 * (r.sponsors.length + r.signatories.length) / Math.max(1, r.need_total)) + "%"; bar.appendChild(f); li.appendChild(bar);
        li.appendChild(h("p", "s-small", "Sponsors " + r.sponsors.length + " of " + r.need_sponsors + (r.sponsor_names.length ? " (" + r.sponsor_names.join(", ") + ")" : "") +
                         " · with signatories " + (r.sponsors.length + r.signatories.length) + " of " + r.need_total));
        if (r.tabled) li.appendChild(h("span", "s-sheet-stamp", "Tabled"));
        ul.appendChild(li);
      });
    }
    var landsTagged = false, lastLook = null;
    function stageLook(v) {
      var b = document.body;
      ["1", "2", "3", "summit"].forEach(function (k) { b.classList.remove("s-stage-" + k); });
      b.classList.add("s-stage-" + (v.phase === "chapter" ? (v.length === "quick" ? "1" : String(v.chapter)) : "summit"));
      var key = b.className.match(/s-stage-\w+/)[0];
      if (lastLook && lastLook !== key) { var fr = document.querySelector(".s-stage .b-frame"); if (fr) restart(fr, "s-stage-anim"); }
      lastLook = key;
      if (!landsTagged) {
        Object.keys(lands).forEach(function (iso) { var t = v.tokens[iso]; if (t && t.rcode) lands[iso].forEach(function (l) { l.classList.add("rg-" + t.rcode.toLowerCase()); }); });
        landsTagged = true;
      }
      if (v.phase === "chapter") {
        var hasRooms = !!(v.rooms || []).length, hasRace = !!(v.race || []).length;
        $("t-coalition").hidden = !(hasRooms || hasRace);
        $("c-signup").hidden = !hasRace; $("c-meeting").hidden = !hasRooms; $("c-roomcard").hidden = !hasRooms;
      }
      // a quieter first stage: Staff opens with Bloc meetings, and the walkthrough introduces it then
      $("t-staff").hidden = v.phase === "chapter" && v.length !== "quick" && v.chapter === 1;
    }
    function signedCard(v, s) {                                      // a delegation puts its name to your draft
      var row = $("s-signed-row"); row.textContent = "";
      var face = $("s-signed-face"); face.textContent = "";
      if (window.socSession.guide) face.appendChild(window.socSession.guide.portrait("delighted", "delegate " + DLG.likeness(s.iso3)));
      var who = $("s-signed-who"); who.textContent = ""; who.appendChild(DLG.pin(s.iso3)); who.appendChild(document.createTextNode(s.name));
      $("s-signed-h").textContent = s.role === "sponsor" ? "A new sponsor" : "A new signatory";
      $("s-signed-p").textContent = s.name + " puts its name to your draft as a " + s.role + ". Your sheet now has " +
        s.sponsors + " sponsor" + (s.sponsors === 1 ? "" : "s") + " and " + s.signatories + " signator" + (s.signatories === 1 ? "y" : "ies") + ".";
      row.appendChild(btn("Back to work", "s-btn", function () { close("s-signed"); }));
      open("s-signed"); restart(document.querySelector("#s-signed .s-doc"), "s-reel-in"); A.play("stamp");
    }
    var btShown = {};
    function breakthroughCard(v, prev) {
      if (!v.stage || !v.stage.made || v.stage.stayed || btShown[v.chapter]) return;
      btShown[v.chapter] = true;
      $("s-bt-h").textContent = "Breakthrough: " + v.stage.breakthrough;
      $("s-bt-p").textContent = "Well done, delegates. " + (v.stage.turns_left ? "You have " + v.stage.turns_left + " turn" + (v.stage.turns_left === 1 ? "" : "s") + " left in " + v.chapter_name +
        ". Move on now, and that time becomes momentum; or keep working to strengthen your hand." : "This is the stage's last turn.");
      $("s-bt-unlocks").textContent = v.stage.unlocks;
      $("s-bt-go").textContent = "Move on now: +" + v.stage.momentum.respect + " Standing, +" + v.stage.momentum.influence + " Influence";
      $("s-bt-stay").textContent = v.stage.turns_left ? "Keep working (" + v.stage.turns_left + " turn" + (v.stage.turns_left === 1 ? "" : "s") + " left)" : "Finish this turn";
      var pf = $("s-bt-pres"); pf.textContent = ""; if (G) pf.appendChild(G.portrait("delighted", "president"));
      setTimeout(function () {
        if (document.querySelector(".s-overlay:not([hidden])") || !$("s-walk").hidden) { btShown[v.chapter] = false; return; }
        open("s-breakthrough"); restart(document.querySelector("#s-breakthrough .s-doc"), "shown"); A.play("fanfare");
      }, 900);
    }

    // ---------- the debrief dossier ----------
    function debriefInto(b, v) {
      var d = v.debrief; if (!d) return;
      var box = h("div", "s-debrief");
      box.appendChild(h("h3", "", "What your diplomacy did"));
      var turned = d.turned.length ? "You turned " + d.turned.join(", ") + ": without your goodwill " + (d.turned.length === 1 ? "it" : "they") + " would have voted the other way." :
        "No delegation's vote on the final text changed because of your goodwill alone.";
      box.appendChild(h("p", "", turned + (d.lost.length ? " Your pull went the wrong way with " + d.lost.join(", ") + "." : "")));
      if (d.countries.length) {
        box.appendChild(h("h3", "", "Why each delegation voted as it did"));
        box.appendChild(h("p", "s-sub", "Every number is a push towards yes (positive) or no (negative) on the final text. A delegation votes yes above +0.4 in total, no below −0.4, and abstains in between. The mood is its hidden draw on the day: the vote's real uncertainty."));
        var t = h("table", "s-why"), hr = h("tr");
        ["Delegation", "Vote", "Your call", "Its stated position", "Model", "You", "Rivals", "Group", "Mood"].forEach(function (x) { hr.appendChild(h("th", "", x)); });
        t.appendChild(hr);
        function num(x) { return (x > 0 ? "+" : "") + x.toFixed(2); }
        d.countries.forEach(function (c) {
          var tr = h("tr", c.turned ? "turned" : ""), td = h("td");
          td.appendChild(document.createTextNode(c.name)); if (c.turned) { td.appendChild(document.createTextNode(" ")); td.appendChild(h("span", "s-badge", "you turned it")); }
          tr.appendChild(td);
          tr.appendChild(h("td", "v-" + c.vote, c.vote));
          tr.appendChild(h("td", "", c.predicted ? c.predicted + (c.right ? " ✓" : " ✗") : "–"));
          tr.appendChild(h("td", "", c.stated));
          [c.model, c.yours, c.rivals, c.group, c.mood].forEach(function (x) { tr.appendChild(h("td", "num", num(x))); });
          t.appendChild(tr);
        });
        box.appendChild(t);
      }
      box.appendChild(h("h3", "", "What to try next time"));
      var grid = h("div", "s-tips-list");
      d.tips.forEach(function (x) {
        var c = h("div"); c.appendChild(h("b", "", x.path.charAt(0).toUpperCase() + x.path.slice(1) + ": " + GRADE[x.grade]));
        var ul = h("ul"); x.next.forEach(function (n) { ul.appendChild(h("li", "", n.charAt(0).toUpperCase() + n.slice(1) + ".")); });
        c.appendChild(ul); grid.appendChild(c);
      });
      box.appendChild(grid);
      if (d.promises.length) box.appendChild(h("p", "s-sub", "Promises: " + d.promises.map(function (p) { return p.country + (p.kept === true ? " (kept)" : p.kept === false ? " (broken)" : " (the clause was struck)"); }).join("; ") + "."));
      b.appendChild(box);
    }

    // the map is the way in to a delegation
    $("b-map").addEventListener("click", function (e) {
      var t = e.target.closest(".b-token");
      if (!t) { if (V && V.phase === "chapter") closePanel(); return; }
      if (!V) return;
      var iso = t.getAttribute("data-iso"); if (iso === V.you.iso3) return;
      var mb = $("b-map").getBoundingClientRect(), tb = t.getBoundingClientRect();
      pick(iso); setTab("dele", false, tb.left + tb.width / 2 > mb.left + mb.width * 0.55 ? "left" : "right"); A.play("flip");
    });
    document.addEventListener("click", function (e) { if (e.target.closest("[data-close]")) setTimeout(adviceNext, 500); });
    $("s-replay-walk").addEventListener("click", function () { close("s-pause"); if (V) WALK.start(V, null, "intro"); });
    $("s-end-turn").addEventListener("click", function () { amending = null; move({ do: "end_turn" }); });
    $("s-reserve").addEventListener("click", function () { move({ do: "reserve" }); });
    $("s-bt-go").addEventListener("click", function () { close("s-breakthrough"); move({ do: "advance" }); });
    $("s-bt-stay").addEventListener("click", function () { close("s-breakthrough"); move({ do: "stay" }); });
    document.querySelector("#s-chapter-card [data-close]").addEventListener("click", afterStageCard);
    $("s-abandon").addEventListener("click", function () {
      if (!window.confirm("Abandon this session? It can't be brought back.")) return;
      if (mode === "saved") api({ do: "abandon", save_id: +saveId }).then(function () { window.location.href = "/session"; });
      else { var list = slots(); list.splice(slot, 1); keep(list); window.location.href = "/session"; }
    });

    function relation(n) { return ["Hostile", "Cool", "Neutral", "Warm", "Close"][(n || 0) + 2]; }
    var M = window.socSession.mods;
    var ctx = { $: $, h: h, A: A, G: G, btn: btn, opt: opt, move: move, say: say, open: open, close: close, restart: restart,
                setTab: setTab, closePanel: closePanel, pick: pick, envoy: envoy, stage: stage, TABS: TABS, ASK: ASK,
                hideAdvice: hideAdvice, syncSettings: syncSettings, staffIcon: staffIcon, staffOf: staffOf,
                view: function () { return V; }, redraw: function () { if (V) country(V); } };
    ctx.talk = function (iso) { DLG.talk(iso); };
    ctx.talks = function () { return TALK; };
    ctx.picked = function () { return picked; };
    ctx.chiefNote = chiefNote; ctx.result = function (v) { result(v); };
    var WALK = M.walk(ctx), TALK = M.talks(ctx), REEL = M.reel(ctx), DLG = M.dialogue(ctx);
    var SUMMIT = M.summit(ctx);
    if (M.keys) M.keys(ctx);
    if (mode === "guest") {
      guest = slots()[slot];
      if (!guest || guest.pack !== document.body.getAttribute("data-pack")) {
        say("This session isn't kept on this laptop. Start a new one from The Session.");
        $("s-end-turn").hidden = true;
        return;
      }
    }
    call({ do: "view" }).then(function (r) { draw(r.view); if (r.view.phase === "done") result(r.view); }).catch(function (e) { sayError(e.message); });
  }

  if (page === "title") titlePage();
  else if (page === "new") newPage();
  else if (page === "game") gamePage();
})();
