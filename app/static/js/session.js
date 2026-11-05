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
  function say(t) { var m = $("p-msg") || $("s-msg"); if (m) m.textContent = t; var s = $("p-say"); if (s) s.textContent = t; }
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
      api({ do: "new", pack: choice.pack, iso3: choice.iso3, length: choice.length, difficulty: choice.difficulty, path: choice.path }).then(function (r) {
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
    var TABS = ["brief", "draft", "dele", "blocs", "sponsors", "summit", "staff", "record"];
    var rail = $("s-rail");
    function panelOpen() { return rail.classList.contains("open"); }
    function setTab(name, focus, dock) {
      TABS.forEach(function (t) {
        var b = $("t-" + t), on = t === name;
        b.setAttribute("aria-selected", String(on)); b.tabIndex = on ? 0 : -1; $("p-" + t).hidden = !on;
      });
      rail.classList.add("open"); document.body.classList.add("s-panel-open");
      rail.classList.toggle("center", name === "summit" || dock === "center");
      rail.classList.toggle("dock-left", name === "dele" && dock === "left");
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
          say((r.out.amendment ? "The floor amendment was " + r.out.amendment + ". " : "") +
              (r.out.final ? "The resolution: " : "The clause: ") + (passed ? "adopted. " : "rejected. ") + (sum || ""));
          if (r.view.phase === "done") setTimeout(function () { result(r.view); }, wait);
          return;
        }
        draw(r.view, r.out, action);
        if (r.view.phase === "done") setTimeout(function () { result(r.view); }, action.do === "statement" ? 600 : 1800);
        if (action.do === "end_turn") A.play("gavel"); else if (SOUND[action.do]) A.play(SOUND[action.do]);
      }).catch(function (e) { say(e.message); A.play("tick"); });
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
      var pre = prev && prev.phase === "chapter" ? (prev.chapter_name + ": " + (was ? "breakthrough made. +3 Influence, +1 Respect. " : "the deadline passed without a breakthrough. −1 Respect. ")) : "";
      $("s-cc-goal").textContent = pre + (summit ? "The draft goes to the vote, clause by clause, then as a whole." :
        "Breakthrough: " + v.stage.goal + " Deadline: " + v.stage.deadline + " turns.");
      $("s-cc-look").textContent = summit ? "I'll preside. Every clause is voted on, then the whole text." : v.stage.look;
      var pf = $("s-cc-pres"); pf.textContent = ""; if (G) pf.appendChild(G.portrait(summit ? "eyebrow" : "delighted", "president"));
      stagePanel = summit ? null : (v.length === "quick" || v.chapter === 1 ? "draft" : v.chapter === 2 ? "blocs" : "sponsors");
      var cr = !summit && v.crisis && v.crisis.chapter === v.chapter ? v.crisis : null;
      $("s-cc-crisis").hidden = !cr;
      if (cr) { $("s-cc-crisis-h").textContent = cr.title; $("s-cc-crisis-p").textContent = cr.body; $("s-cc-crisis-t").textContent = cr.teaches; }
      open("s-chapter-card");
      restart(document.querySelector("#s-chapter-card .s-doc"), "shown");
      A.play(v.chapter === 1 && !summit && !prev ? "open" : "gavel");
    }
    var stagePanel = null;

    // ---------- the Brief tab ----------
    function progress(v) {
      var ul = $("c-progress"); ul.textContent = "";
      if (v.stage) {
        v.stage.checklist.forEach(function (x) { ul.appendChild(h("li", x.done ? "done" : "", x.label + " (" + x.count + ")")); });
        var adv = $("c-advance"); adv.textContent = "";
        if (v.stage.made) adv.appendChild(btn("Move on now: +" + v.stage.momentum.respect + " Respect, +" + v.stage.momentum.influence + " Influence", "s-btn small", function () { move({ do: "advance" }); }));
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
      var sel = $("s-region-pick"), keepVal = sel.value; sel.textContent = "";
      v.regions.forEach(function (r) {
        var li = h("li", r.owner === "you" ? "you" : r.owner ? "rival" : "");
        li.appendChild(h("b", "", r.name));
        li.appendChild(h("span", "s-small", r.owner ? (r.owner === "you" ? "Endorses you" : "Endorses " + r.owner_name) : "Undecided"));
        var bar = h("div", "s-bar-meter"), fill = h("i"); fill.style.width = (r.voters ? 100 * r.leaning / r.voters : 0) + "%";
        bar.appendChild(fill); bar.appendChild(h("em")); bar.setAttribute("aria-hidden", "true"); li.appendChild(bar);
        li.appendChild(h("span", "s-small", r.leaning + " of " + r.voters + " lean your way (more than half wins it)"));
        ul.appendChild(li);
        if (r.voters) opt(sel, r.code, r.name);
      });
      if (keepVal) sel.value = keepVal;
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
        li.appendChild(document.createTextNode(c.text));
        li.appendChild(h("span", "s-by", (c.mine ? "Yours" : c.author) + (c.amended_by.length ? " · amended by " + c.amended_by.join(", ") : "") +
                                          " · commits countries to: " + c.tags.map(function (t) { return t.label.toLowerCase(); }).join("; ")));
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
      v.cards.forEach(function (card) {
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
      Object.keys(v.tags).forEach(function (code) {
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
    function pick(iso) {
      picked = iso;
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
      if (d.rival) { fact("Status", "Rival delegation: its instructions oppose yours. It won't be moved."); c.appendChild(dl); box.appendChild(c); return; }
      fact("On the draft", d.est === "yes" ? "Likely for" : d.est === "no" ? "Likely against" : d.est ? "Unsure" : "No draft yet");
      var tr = h("span", "s-trust"); tr.setAttribute("aria-label", "Trust " + d.trust + " of 3");
      for (var i = 1; i <= 3; i++) tr.appendChild(h("span", d.trust >= i ? "on" : d.trust <= -i ? "neg" : "off", d.trust <= -i ? "✕" : d.trust >= i ? "●" : "○"));
      fact("Trust", tr);
      fact("Goodwill", d.sway > 0 ? "+" + d.sway.toFixed(2) + " towards you" : d.sway < 0 ? d.sway.toFixed(2) : "none yet");
      if (d.secured) fact("Secured", "signed a commitment: rivals find it twice as hard to move");
      if (d.deal_vote) fact("Your deal", d.deal_vote === "yes" ? "it will vote yes on the whole text, unless it crosses its red line" : "it will abstain rather than vote no");
      if (d.deal && d.deal.asks) fact("Wants in a deal", d.deal.asks.map(function (k) { return ASK[k]; }).join(", "));
      if (d.studied_by) fact("Studied by", d.studied_by);
      var flags = [];
      if (d.signed) flags.push("signed as your " + d.signed); if (d.pledged) flags.push("pledged to abstain");
      if (d.favour) flags.push("owes you a favour"); if (d.promised) flags.push("you've made it a promise");
      if (d.predicted) flags.push("you predicted: " + d.predicted);
      if (flags.length) fact("Also", flags.join("; "));
      c.appendChild(h("p", "s-status", (d.est === "yes" ? "Likely for" : d.est === "no" ? "Likely against" : d.est ? "Unsure" : "No draft yet") +
        " · trust " + d.trust + " of 3" + (d.deal_vote ? " · deal: " + d.deal_vote : "") + (d.secured ? " · secured" : "")));
      var grid = h("div", "s-acts-grid"), noAp = !v.ap;
      grid.appendChild(btn("Lobby (" + d.lobby_cost + " Influence)", "s-btn small", function () { move({ do: "lobby", iso3: picked }); }, noAp || v.influence < d.lobby_cost));
      grid.appendChild(d.read ? btn("Open the file", "s-btn ghost small", function () { showFile(d.file); })
                              : btn("Read the file (1 action)", "s-btn ghost small", function () { move({ do: "read", iso3: picked }); }, noAp));
      if (d.promise_on && d.promise_on.length && !d.promised) {
        var ps = h("select", "wide"); ps.setAttribute("aria-label", "Promise to back which clause");
        v.draft.forEach(function (cl, k) { if (d.promise_on.indexOf(cl.id) >= 0) opt(ps, cl.id, "Promise to back clause " + (k + 1)); });
        var row = h("div", "s-row wide"); row.appendChild(ps);
        row.appendChild(btn("Promise", "s-btn small", function () { move({ do: "promise", iso3: picked, clause: ps.value }); }));
        grid.appendChild(row);
      }
      grid.appendChild(btn("Call in a favour", "s-btn ghost small", function () { move({ do: "favour", iso3: picked }); }, noAp || d.trust < v.costs.favour_trust));
      if (d.deal) grid.appendChild(btn("The deal table (" + v.costs.deal_ap + " actions)", "s-btn small s-deal-btn", function () { dealTable(picked); },
                                       d.deal.done || !v.deal_ready || v.ap < v.costs.deal_ap));
      if (!d.secured) grid.appendChild(btn("Secure (" + v.costs.secure + " Influence)", "s-btn ghost small", function () { move({ do: "secure", iso3: picked }); },
                                          noAp || d.trust < 1 || d.est !== "yes" || v.secured >= v.costs.secure_max || v.influence < v.costs.secure));
      if (d.veto && v.veto.length) grid.appendChild(btn("Ask to abstain, not veto", "s-btn ghost small", function () { move({ do: "abstain", iso3: picked }); }, noAp || d.pledged || d.trust < 1));
      if (v.last_chapter && !d.signed) {
        grid.appendChild(btn("Ask to sponsor", "s-btn small", function () { move({ do: "sign", iso3: picked, role: "sponsor" }); }, noAp));
        grid.appendChild(btn("Ask to sign", "s-btn ghost small", function () { move({ do: "sign", iso3: picked, role: "signatory" }); }, noAp));
      }
      var pr = h("div", "s-predict wide"); pr.appendChild(h("span", "", "Predict their final vote (1 action):"));
      ["yes", "abstain", "no"].forEach(function (x) {
        var b = btn(x, "s-chip", function () { move({ do: "whip", iso3: picked, vote: x }); }, noAp);
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
      if (f.shifts && f.shifts.length) b.appendChild(h("p", "s-shifted", "Since the session began: " + f.shifts.map(function (x) { return x.dir + " towards anything that " + lc(x.label); }).join("; ") + "."));
      var dz = V && V.tokens[f.iso3] && V.tokens[f.iso3].dossier;
      if (dz && dz.known) b.appendChild(dossierBox(dz, true));
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
    function skills(v) {
      $("s-skills-btn").textContent = "Skills (" + v.xp + ")";
      var tree = $("s-tree"); tree.textContent = "";
      var by = {};
      v.skill_list.forEach(function (s) { (by[s.branch] = by[s.branch] || []).push(s); });
      Object.keys(by).forEach(function (br) {
        var col = h("div", "s-branch"); col.appendChild(h("h3", "", br));
        by[br].forEach(function (s) {
          var d = h("div", "s-skill" + (s.have ? " have" : ""));
          d.appendChild(h("b", "", s.name)); d.appendChild(h("span", "", s.what));
          if (s.have) d.appendChild(h("span", "", "Unlocked"));
          else d.appendChild(btn("Unlock (" + v.skill_cost + ")", "s-btn small", function () { move({ do: "skill", skill: s.code }); }, !s.can || v.phase !== "chapter"));
          col.appendChild(d);
        });
        tree.appendChild(col);
      });
      $("s-skills-note").textContent = "You have " + v.xp + " Expertise to spend. Earn more by reading country files and getting procedure right. Each skill costs " + v.skill_cost + ".";
      $("c-bloc").hidden = v.skills.indexOf("bloc_whip") < 0;
      var bs = $("s-bloc-pick"); if (!bs.options.length) v.blocs.forEach(function (b) { opt(bs, b, b + " bloc"); });
    }

    // ---------- drawing everything ----------
    function draw(v, out, action) {
      var prev = V; V = v;
      $("s-where").textContent = v.phase === "done" ? "Finished" : v.phase === "summit" ? "The Summit" :
        v.chapter_name + " · turn " + v.turn + " of " + v.turns + (v.stage ? " · " + (v.stage.made ? "breakthrough made" : v.stage.turns_left + " left") : "");
      stageBar(v, prev);
      $("s-you").textContent = "You are " + v.you.name + " · " + v.rule + " · aiming for " + v.path.name;
      meter("m-influence", v.influence); meter("m-respect", v.respect); meter("m-expertise", v.expertise);
      meter("m-capital", v.capital.value + "/" + v.capital.max);
      $("m-capital").classList.toggle("low", v.capital.value <= 2);
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
        if (v.question) {
          var row = h("div", "s-row");
          v.question.options.forEach(function (o, k) { row.appendChild(btn(o, "s-btn ghost small", function () { move({ do: "answer", option: k }); })); });
          box.appendChild(row);
        } else if (ev.teaches) box.appendChild(h("p", "s-small", ev.teaches));
        if (!prev || prev.turn !== v.turn || prev.chapter !== v.chapter) A.play("news");
      }
      var cr = v.phase === "chapter" && v.crisis && v.crisis.chapter === v.chapter ? v.crisis : null, cb = $("c-crisis-body");
      $("c-crisis").hidden = !cr; cb.textContent = "";
      if (cr) { cb.appendChild(h("p", "s-goal", cr.title)); cb.appendChild(h("p", "", cr.body)); cb.appendChild(h("p", "s-small", cr.teaches)); }
      var ol = $("c-offer-list"); ol.textContent = "";
      $("c-offers").hidden = !(v.offers && v.offers.length);
      (v.offers || []).forEach(function (o) {
        var li = h("li", "s-offer");
        li.appendChild(h("p", "s-offer-text", o.text)); li.appendChild(h("p", "s-small", o.terms));
        var row = h("div", "s-row");
        row.appendChild(btn("Accept", "s-btn small", function () { move({ do: "offer", id: o.id, answer: "accept" }); }));
        row.appendChild(btn("Turn it down", "s-btn ghost small", function () { move({ do: "offer", id: o.id, answer: "refuse" }); }));
        li.appendChild(row); ol.appendChild(li);
      });
      var il = $("c-instr-list"); il.textContent = "";
      [["in", "Get in: ", v.mandate.must.label], ["in", "Also get in: ", v.mandate.also.label], ["out", "Keep out: ", v.mandate.red.label]].forEach(function (x) {
        var li = h("li"); li.appendChild(h("span", x[0], x[1])); li.appendChild(document.createTextNode(x[2])); il.appendChild(li);
      });
      $("c-aim").textContent = "Your aim: " + v.path.name + ". " + v.path.what;
      regions(v);
      tug(v, prev);
      var nb = $("n-brief");                                          // what's waiting on the Brief: offers, a question
      if (nb) nb.textContent = v.phase === "chapter" ? ((v.offers || []).length + (v.question ? 1 : 0) || "") : "";
      staff(v);
      pins(v);
      var rs = $("s-reserve");
      rs.hidden = v.phase !== "chapter";
      rs.textContent = v.reserve ? "Reserve ready" : "Hold in reserve";
      rs.classList.toggle("ready", !!v.reserve);
      rs.disabled = !!v.reserve || !v.ap;
      draft(v, prev);
      countryPicker(v); country(v); skills(v);
      // the delegate's reply, and anything else the move said
      if (out && out.heard) {
        $("c-heard").hidden = false;
        var q = $("c-heard-text"); q.textContent = "";
        q.appendChild(document.createTextNode("“" + out.heard + "”"));
        q.appendChild(h("cite", "", "The delegate of " + (v.tokens[action.iso3] || {}).name + (out.red_line ? " (a red line: they barely moved)" : "")));
        if (out.leans) q.appendChild(h("span", "s-intel", "Leaning towards each rival: " + Object.keys(out.leans).map(function (k) { return k + " " + (out.leans[k] > 0.3 ? "warm" : out.leans[k] < -0.3 ? "cold" : "neutral"); }).join(", ") + "."));
        if (out.would_vote) q.appendChild(h("span", "s-intel", "On the whole text as it stands, it would vote " + out.would_vote + "."));
        restart(q, "s-in");
      }
      if (out && out.file) showFile(out.file);
      if (out && action && action.do === "deal") dealAnswer(v, out);
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
        t.classList.toggle("trust-pos", d.trust > 0); t.classList.toggle("trust-neg", d.trust < 0);
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
        moments(v, prev, news, won, lost);
      }
      $("s-end-turn").hidden = v.phase !== "chapter";
      summitTabs(v);
      summitPane(v, out);
      if (!prev ? (v.turn === 1 && v.phase === "chapter" && seenLogAtStart(v)) : (prev.chapter !== v.chapter || prev.phase !== v.phase)) {
        if (!prev && guideOn() && v.chapter === 1) walkStart(v, function () { chapterCard(v, prev); });
        else chapterCard(v, prev);
      }
    }
    function seenLogAtStart(v) { return v.log.filter(function (x) { return x.kind === "action"; }).length === 0; }

    // ---------- the summit ----------
    var STANCE = {
      firm: ["Firm", "State your country's position plainly. Delegations that share your main aim warm to you; those against it cool a little."],
      open: ["Open", "Listen first and acknowledge the other side. The room respects it: +1 Respect."],
      bridge: ["Bridge", "Speak to the undecided. Delegations in the middle warm to you."]
    };
    var GRADE = ["No medal", "Bronze", "Silver", "Gold"];
    var choice = "stand", timer = null, shownStep = null;
    function stopTimer() { if (timer) { clearTimeout(timer); timer = null; } }
    function defaultVote(cur) { return cur.stance > 0 ? "yes" : cur.stance < 0 ? "no" : "abstain"; }

    function summitTabs(v) {
      var summit = v.phase !== "chapter";
      ["brief", "draft", "dele", "blocs", "sponsors"].forEach(function (t) { if (summit) $("t-" + t).hidden = true; });
      if (!summit) ["brief", "draft", "dele"].forEach(function (t) { $("t-" + t).hidden = false; });
      $("t-summit").hidden = !summit;
      if (summit && $("t-summit").getAttribute("aria-selected") !== "true" && $("t-record").getAttribute("aria-selected") !== "true") setTab("summit");
    }

    function summitPane(v, out) {
      var S = v.summit; if (!S) return;
      var box = $("c-summit"); box.textContent = "";
      var key = S.step + ":" + (S.current ? S.current.id : "") + ":" + v.phase;
      if (key !== shownStep) { choice = "stand"; stopTimer(); }
      if (v.phase === "done") {
        box.appendChild(h("h2", "", "The session is over"));
        var fin = S.statement && S.statement.adopted ? "The resolution failed, but a Presidential Statement was agreed." :
          S.final && S.final.passed ? "The resolution was adopted. " + S.final.summary : "The resolution failed. " + (S.final ? S.final.summary : "");
        box.appendChild(h("p", "", fin));
        box.appendChild(btn("See your results", "s-btn", function () { result(v); }));
      } else if (S.step === "speech") {
        box.appendChild(h("h2", "", "Your opening speech"));
        box.appendChild(h("p", "", "The summit opens with each delegation's statement. How will " + v.you.name + " speak?"));
        var ta = h("textarea"); ta.setAttribute("aria-label", "Your speech, if you want to write it (not saved or marked)");
        ta.placeholder = "Your words, if you want to write them. For your own practice: not saved, not marked.";
        ta.className = "s-speech"; box.appendChild(ta);
        var st = h("div", "s-stances");
        Object.keys(STANCE).forEach(function (k) {
          var b = h("button", "s-stance"); b.type = "button";
          b.appendChild(h("b", "", STANCE[k][0])); b.appendChild(h("span", "", STANCE[k][1]));
          b.addEventListener("click", function () { move({ do: "speech", stance: k }); });
          st.appendChild(b);
        });
        box.appendChild(st);
      } else if (S.step === "clause" && S.current) {
        var cur = S.current;
        var hd = h("h2"); hd.appendChild(document.createTextNode("Clause " + cur.n)); hd.appendChild(h("span", "s-count", cur.n + " of " + cur.of)); box.appendChild(hd);
        var dial = h("span", "s-dial"); dial.style.setProperty("--p", Math.round(cur.chance.p_pass * 100));
        dial.appendChild(h("span", "", Math.round(cur.chance.p_pass * 100) + "%")); dial.setAttribute("aria-label", "About " + Math.round(cur.chance.p_pass * 100) + "% chance it passes");
        box.appendChild(dial);
        box.appendChild(h("p", "s-clause-big", cur.text));
        box.appendChild(h("p", "s-small", (cur.mine ? "Your clause" : cur.author) + " · commits countries to: " + cur.tags.join("; ").toLowerCase()));
        if (cur.expected) box.appendChild(h("p", "s-expect", "Expected, as things stand: " + cur.expected.yes + " yes · " + cur.expected.no + " no · " + cur.expected.abstain + " abstain"));
        if (cur.promised_to.length) box.appendChild(h("p", "s-small", "You promised " + cur.promised_to.join(", ") + " to back this clause: vote yes to keep your word."));
        if (S.pending) {
          var am = h("div", "s-amendment");
          am.appendChild(h("b", "", "Floor amendment from " + S.pending.by_name));
          am.appendChild(h("p", "", "They move to " + S.pending.change + ". Accept it as friendly, rule it out of order, or let it go to a vote first."));
          if (S.pending.advice) am.appendChild(h("p", "s-legal", "Your legal adviser (" + S.pending.advice.sure + "): put to a vote, it would " + (S.pending.advice.passes ? "pass." : "fail.")));
          box.appendChild(am);
        }
        if (S.attack) {
          var at = h("div", "s-amendment s-attack");
          at.appendChild(h("b", "", S.attack.by_name + " asks to speak against this clause"));
          at.appendChild(h("p", "", "Unanswered, the speech will cool the room towards it. A right of reply (Respect " + v.costs.reply_respect + " or more) answers it."));
          box.appendChild(at);
        }
        box.appendChild(h("p", "s-small", "First, what will you do? Then cast " + v.you.name + "'s vote."));
        var dec = h("div", "s-decide");
        function chip(k, label, enabled) {
          var b = btn(label, "s-chip", function () { choice = k; dec.querySelectorAll(".s-chip").forEach(function (x) { x.setAttribute("aria-pressed", String(x === b)); }); A.play("tick"); }, !enabled);
          b.setAttribute("aria-pressed", String(choice === k)); dec.appendChild(b);
        }
        chip("stand", S.pending ? "Let it go to a vote" : "Stand firm", true);
        chip("offer", "Last offer (" + S.offer_cost + " Influence)", S.influence >= S.offer_cost);
        chip("favour", "Call in a favour (" + S.favours.length + ")", S.favours.length > 0);
        if (S.pending) chip("accept", "Accept as friendly (+1 Respect)", true);
        if (S.pending) chip("point_of_order", "Point of order", S.po);
        if (S.attack) chip("reply", "Right of reply", S.can_reply);
        box.appendChild(dec);
        var vt = h("div", "s-votes");
        [["yes", "Yes"], ["abstain", "Abstain"], ["no", "No"]].forEach(function (x) {
          vt.appendChild(btn(x[1], "s-btn v-" + x[0], function () { stopTimer(); move({ do: "decide", choice: choice, vote: x[0] }); }));
        });
        box.appendChild(vt);
        if (A.settings().timer && key !== shownStep) {
          var bar = h("div", "s-timer"); bar.appendChild(h("i")); bar.style.setProperty("--secs", "20s"); box.appendChild(bar);
          box.appendChild(h("p", "s-timer-note", "The Chair calls the vote in twenty seconds. (Turn the timer off in Settings.)"));
          requestAnimationFrame(function () { bar.classList.add("run"); });
          timer = setTimeout(function () {
            say("Time: the Chair called the vote. " + v.you.name + " voted " + defaultVote(cur) + ".");
            move({ do: "decide", choice: choice, vote: defaultVote(cur) });
          }, 20000);
        }
      } else if (S.step === "final") {
        box.appendChild(h("h2", "", "The resolution as a whole"));
        box.appendChild(h("p", "", S.kept.length ? "What survived the division of the question commits countries to: " + S.kept.join("; ").toLowerCase() + "."
                                                 : "No clause was adopted, so there is nothing left to vote on."));
        box.appendChild(h("p", "s-small", "Cast " + v.you.name + "'s vote on the whole resolution."));
        if (S.golden === "aims_in") box.appendChild(chiefNote("eyebrow", "Remember the first rule of the UN, Ambassador: don't vote down progress because it isn't everything you wanted. This text carries your capital's main aim."));
        else if (S.golden === "red_in") box.appendChild(chiefNote("concerned", "This text crosses your red line. Voting against it is within your instructions; abstaining is a way to let progress through without endorsing it."));
        var fv = h("div", "s-votes");
        [["yes", "Yes"], ["abstain", "Abstain"], ["no", "No"]].forEach(function (x) { fv.appendChild(btn(x[1], "s-btn v-" + x[0], function () { move({ do: "final", vote: x[0] }); })); });
        box.appendChild(fv);
      } else if (S.step === "statement") {
        box.appendChild(h("h2", "", "A Presidential Statement"));
        box.appendChild(h("p", "", "The resolution has failed. The President of the Council proposes a statement instead: it isn't binding, and it is adopted only if no member objects."));
        var form = h("div", "s-statement");
        S.statement_options.forEach(function (o) {
          var lab = h("label"), cb = h("input"); cb.type = "checkbox"; cb.value = o.code;
          lab.appendChild(cb); lab.appendChild(document.createTextNode(o.label)); form.appendChild(lab);
        });
        box.appendChild(form);
        var row = h("div", "s-row");
        row.appendChild(btn("Propose the statement", "s-btn", function () {
          var tags = Array.prototype.map.call(form.querySelectorAll("input:checked"), function (x) { return x.value; });
          if (!tags.length) { say("Tick at least one commitment for the statement, or let it go."); return; }
          move({ do: "statement", tags: tags });
        }));
        row.appendChild(btn("No statement", "s-btn ghost", function () { move({ do: "statement", skip: true }); }));
        box.appendChild(row);
      }
      shownStep = key;
      // the votes so far
      var rl = $("c-result-list"); rl.textContent = "";
      $("c-results").hidden = !S.results.length;
      S.results.forEach(function (r, k) {
        var li = h("li", r.passed ? "passed" : "failed");
        li.appendChild(h("b", "", r.passed ? "Adopted" : "Rejected"));
        li.appendChild(h("span", "", "Clause " + (k + 1) + ": " + r.labels.join("; ").toLowerCase()));
        li.appendChild(h("span", "s-small", r.summary));
        rl.appendChild(li);
      });
    }

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
                                             " · promises kept " + r.kept_promises + ", broken " + r.broken_promises + " · Respect " + r.respect + " · Expertise " + r.expertise + "."));
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
        var cp = h("div", "s-debrief"); cp.appendChild(h("h3", "", "Your capital"));
        cp.appendChild(h("p", "", "Confidence at the end: " + v.debrief.capital.confidence + " of " + v.debrief.capital.of + ". " +
          v.debrief.capital.deals + " deal" + (v.debrief.capital.deals === 1 ? "" : "s") + " made." +
          (v.debrief.capital.recalled ? " You were recalled before the summit." : "")));
        b.appendChild(cp);
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
      svg.setAttribute("aria-label", "Your standing turn by turn. At the end: " + last.leaning + " of " + last.of + " delegations leaning your way, Influence " + last.influence + ", Respect " + last.respect + ".");
      function el(tag, attrs, text) { var e = document.createElementNS(ns, tag); Object.keys(attrs).forEach(function (k) { e.setAttribute(k, attrs[k]); }); if (text != null) e.textContent = text; svg.appendChild(e); return e; }
      for (var gy = 0; gy <= 4; gy++) el("line", { x1: L, x2: W - 10, y1: T + gy * H / 4, y2: T + gy * H / 4, class: "s-grid" });
      var maxI = 1.15 * Math.max.apply(null, hist.map(function (x) { return x.influence; }).concat([10]));
      var series = [
        ["Support", "s-l-support", function (x) { return x.of ? x.leaning / x.of : 0; }, function (x) { return x.leaning + " of " + x.of; }],
        ["Influence", "s-l-influence", function (x) { return x.influence / maxI; }, function (x) { return String(x.influence); }],
        ["Respect", "s-l-respect", function (x) { return x.respect / 10; }, function (x) { return String(x.respect); }]
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
      box.appendChild(h("p", "s-sub", "Support: delegations leaning your way. Influence and Respect at the end of each turn."));
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
    function stageBox(el) {
      var sr = stage.getBoundingClientRect(), sc = sr.width / stage.offsetWidth, r = el.getBoundingClientRect();
      return { x: (r.left - sr.left) / sc, y: (r.top - sr.top) / sc, w: r.width / sc, h: r.height / sc };
    }
    function visible(sel) { var e = sel && document.querySelector(sel); return e && e.getClientRects().length ? e : null; }
    function lc(t) { t = String(t || "").replace(/\.$/, ""); return /^.[a-z]/.test(t) ? t.charAt(0).toLowerCase() + t.slice(1) : t; }
    function list(items, cls) { var ul = h("ul", cls || "s-guide-list"); items.forEach(function (x) { var li = h("li"); if (x[0]) li.appendChild(h("b", "", x[0])); li.appendChild(document.createTextNode(x[1])); ul.appendChild(li); }); return ul; }

    // little pictures for the steps that look ahead: the shape of the hour, the paths, the summit, the debrief
    function artTimeline(v) {
      var row = h("ol", "s-g-time"), quick = v.length === "quick";
      var stops = quick ? [["Working session", "one stage"], ["The Summit", "the votes"], ["Debrief", "your medals"]] :
        [1, 2, 3].slice(0, v.chapters).map(function (n) { return ["Stage " + n, ["Working group", "Bloc meetings", "Sponsors"][n - 1]]; })
          .concat([["The Summit", "the votes"], ["Debrief", "your medals"]]);
      stops.forEach(function (x, i) {
        var li = h("li", i === 0 ? "now" : ""); li.style.animationDelay = (0.15 + i * 0.18) + "s";
        li.appendChild(h("b", "", x[0])); li.appendChild(h("span", "", x[1])); row.appendChild(li);
      });
      return row;
    }
    function artPresident() {
      var d = h("div", "s-g-pres"); if (G) d.appendChild(G.portrait("delighted", "president"));
      d.appendChild(h("span", "s-g-gavel", "The President of the committee")); return d;
    }
    function artRooms() {
      var t = h("div", "s-g-rooms");
      [["African Group", "you", 4], ["Asia-Pacific Group", "rival", 3], ["Western Europe and Others", "undecided", 5]].forEach(function (r, i) {
        var c = h("div", "s-g-room " + r[1]); c.style.animationDelay = (0.2 + i * 0.25) + "s";
        c.appendChild(h("b", "", r[0])); var dots = h("span", "");
        for (var k = 0; k < 6; k++) dots.appendChild(h("i", k < r[2] ? r[1] : ""));
        c.appendChild(dots); t.appendChild(c);
      });
      var sheet = h("div", "s-g-sheet"); sheet.appendChild(h("b", "", "L.1")); sheet.appendChild(h("span", "", "3 of 3 sponsors")); t.appendChild(sheet);
      return t;
    }
    function artPaths(v) {
      var g = h("div", "s-g-paths");
      [["mandate", "Mandate", "The hardliner"], ["consensus", "Consensus", "The broker"], ["architect", "Architect", "The drafter"], ["kingmaker", "Kingmaker", "The analyst"]].forEach(function (p, i) {
        var d = h("div", "s-g-path" + (v.path.code === p[0] ? " yours" : "")); d.style.animationDelay = (0.1 + i * 0.15) + "s";
        d.appendChild(h("i", "", "★")); d.appendChild(h("b", "", p[1])); d.appendChild(h("span", "", v.path.code === p[0] ? "Your aim" : p[2]));
        g.appendChild(d);
      });
      return g;
    }
    function artSummit() {
      var g = h("div", "s-g-summit");
      for (var i = 0; i < 10; i++) { var t = h("i", i < 6 ? "y" : i < 8 ? "a" : "n"); t.style.animationDelay = (0.3 + i * 0.12) + "s"; g.appendChild(t); }
      var st = h("span", "s-g-stamp", "Adopted"); g.appendChild(st);
      return g;
    }
    function artMedals() {
      var g = h("div", "s-g-medals");
      [["bronze", "Bronze"], ["silver", "Silver"], ["gold", "Gold"]].forEach(function (m, i) {
        var d = h("div", "s-g-medal " + m[0]); d.style.animationDelay = (0.2 + i * 0.25) + "s"; d.appendChild(h("span", "", m[1])); g.appendChild(d);
      });
      return g;
    }

    function walkSteps(v) {
      var sample = Object.keys(v.tokens).filter(function (k) { var t = v.tokens[k]; return !t.you && !t.rival; })[0];
      var sc = v.veto && v.veto.length, cr = v.crisis, quick = v.length === "quick";
      return [
        { face: "delighted", title: "Welcome, Ambassador",
          text: ["I am the Chief of Protocol. My job is to see that this committee keeps to its rules, and that you know them before the gavel falls.",
                 "In the next few minutes I'll show you exactly how this session will run: every stage, every choice open to you, and how it ends. Use Back to go over anything again, or Skip if you already know the way."] },
        { at: ".b-titles", face: "calm", title: "You are " + v.you.name,
          text: ["You represent " + v.you.name + " in " + v.title + ". The committee decides by its voting rule: " + v.rule + ".",
                 sc ? "Five permanent members hold a veto: one no from any of them sinks a resolution, however many others vote yes. An abstention is not a veto." :
                      "Every delegation has one vote. Abstentions don't count towards the majority, so turning a no into an abstention helps you."] },
        { face: "thinking", title: "How the hour will run", art: artTimeline,
          text: [(quick ? "This is a Quick session: one working session, then the Summit, then your debrief." :
                   "Three stages, each with its own look: the Working group drafts, Bloc meetings win regional groups, Sponsors table the draft. Then the Summit, then your debrief."),
                 "Each stage ends at a breakthrough (shown on its checklist) or at its deadline, whichever comes first. Make the breakthrough and choose: move on now, and every turn left becomes Respect and Influence (your rivals lose those turns too), or keep working to strengthen your hand. Miss it, and the Chair moves on without you: −1 Respect."] },
        { face: "delighted", title: "The President of the committee", art: artPresident,
          text: ["The President presides over the committee. He'll open each stage, announce your breakthroughs, and chair the Summit.",
                 "I'm here to guide you; he keeps the time. Watch the stage track at the top of the screen: it shows where you are, and how many turns are left."] },
        { at: "#c-instr", tab: "brief", face: "eyebrow", title: "Your secret instructions",
          text: [list([["Get in: ", "a clause that " + lc(v.mandate.must.label) + "."], ["Also get in: ", "a clause that " + lc(v.mandate.also.label) + "."],
                       ["Keep out: ", "anything that " + lc(v.mandate.red.label) + ". That is your red line."]]),
                 "Nobody else can see these orders. Your rivals have their own, roughly the opposite of yours."] },
        { face: "wry", title: "Four ways to win", art: artPaths,
          text: ["Every session is graded on all four paths, from no medal to gold. You're aiming for " + v.path.name + ": " + lc(v.path.what).replace(/\.$/, "") + ".",
                 "But a gold on any path is a gold. If the session turns against your plan, change it."] },
        { at: ".s-meters", face: "calm", title: "Your standing",
          text: [list([["Influence ₳ ", "is your currency: lobbying, side events and favours cost it. You earn " + E_INCOME + " a turn, more with a regional group behind you."],
                       ["Respect ✦ ", "is your standing in the room. At 5 and again at 8 it adds an action each turn; at 8 proposing clauses is free."],
                       ["Expertise ✎ ", "comes from reading country files and knowing procedure. Spend it on diplomatic skills."],
                       ["Actions ⚑ ", "are your moves this turn. Most things cost one."],
                       ["Capital ✉ ", "is your government's confidence in you."]])] },
        { at: "#c-ap", tab: "brief", face: "wry", title: "A delegation that grows",
          text: ["You start with about three actions a turn. More come from the stage you've reached, your staff (every four adviser stars), your experience (Expertise 5 and 10), Respect (5 and 8), and a coalition of two regional groups.",
                 "When you need one more, your staff can work late: overtime costs Influence, more each time in a turn. By the Sponsors stage you'll have five or six actions a turn, and less time to use them, as in a real negotiation."] },
        { at: ".s-tabs", face: "calm", title: "The command bar",
          text: ["Every panel opens from here, over the map: the Brief, the Draft, Delegates, your Staff and the Record. Blocs open in the Bloc meetings stage and Sponsors in the Sponsors stage.",
                 "Click a token on the map to open its card beside it. Click the sea, the ✕ or press Escape to close a panel."] },
        { face: "thinking", title: "Bloc meetings and the sign-up sheets", art: artRooms,
          text: ["In Bloc meetings the map shows the regional groups. One group meets each turn: attend its meeting (1 action) to work all its members at once. Each room shows who leans your way, who leans to a rival, and how many you need.",
                 "In Sponsors, the clerk's sign-up sheets race side by side: yours and each rival's. The first draft tabled, as L.1, is voted on first."] },
        { at: "#m-capital", face: "concerned", title: "Your capital",
          text: ["Your Foreign Minister is watching. This is their confidence in you, out of " + v.capital.max + ". It rises when you make a stage's breakthrough and get your aims into the text.",
                 "It falls when you miss a goal, let your red line into the draft, or make a deal that goes too far: trading away your instructions, or promising to back your red line. Telegrams tell you why. At zero you are recalled for consultations: " +
                 (v.difficulty === "hard" ? "on Hard, that ends your session." : "you lose a turn.")] },
        { at: "#b-board", face: "calm", title: "The room", demo: function () { if (sample) setTimeout(function () { envoy(v.you.iso3, sample, false); }, 500); },
          text: ["Every token is a delegation, banded in the colour of its regional group. Green leans towards your draft, red against.",
                 "As delegations lean your way, their land takes your colour; a rival's sphere shows too, like borders on a campaign map. Envoys cross the map whenever anyone makes a move. Click any token to work that delegation."] },
        { at: "#s-tug", face: "thinking", title: "The vote as it stands",
          text: ["This bar is the vote on the whole draft if it were held now: yes, abstain and no. Every move tugs it, yours and your rivals'.",
                 "It leaves out each delegation's mood on the day, so the real vote can still surprise you. Keep a margin."] },
        { at: "#c-country", tab: "dele", pick: sample, face: "thinking", title: "Working a delegation",
          text: [list([["Read the file ", "(1 action): its positions, red lines and sources. Lobbying works better once you've read it."],
                       ["Lobby ", "with Influence: the further they are from you, the more it costs."],
                       ["Promise ", "to back a clause they like: trust grows, but only if you keep your word at the summit."],
                       ["Call in a favour ", "when trust is high: they back you on the day."],
                       ["Ask them to sponsor or sign ", "so the draft can be tabled first."],
                       ["Predict their vote: ", "scored at the summit, and the Kingmaker's path." + (sc ? " Permanent members can be asked to abstain rather than veto." : "")],
                       ["Secure them ", "once they trust you and lean your way: a signed commitment makes them twice as hard for a rival to move."]])] },
        { face: "thinking", title: "Dossiers and the deal table", art: artDeal,
          text: ["Every delegation has a dossier: the size of its economy, its income group, what it exports and whether it receives development aid. These are real World Bank figures, each with its year.",
                 "What a delegation wants follows from them: development money, access to markets, backing for a candidacy, or its favourite clause. At the deal table you offer some of these for its yes, an abstention, sponsorship, Influence or intelligence. The meter shows whether it would accept, and your capital's reaction shows whether it would approve. A deal takes " + v.costs.deal_ap + " actions; one a turn, one per delegation a chapter, and your budget allows " + v.budget.total + " funding pledges in all."] },
        { at: "#c-regions", tab: "brief", face: "wry", title: "Regional groups",
          text: ["Win more than half of a regional group and it endorses your draft: extra Influence every turn, and its members lean your way at the vote.",
                 "A side event, on the Delegates tab, works on a whole group at once (2 actions). Rivals court groups too, so an endorsement can be lost."] },
        { at: "#c-clauses", tab: "draft", face: "thinking", title: "The draft",
          text: ["This is the resolution as it stands. The dial on each clause is its chance of passing now.",
                 "You can amend a clause one commitment at a time, or strike it; with skills, divide or merge clauses. The working group must agree to changes to anyone else's text: it won't make a clause less popular, or strike one it would pass."] },
        { at: "#c-cards", tab: "draft", face: "delighted", title: "The drafting table",
          text: ["Clause cards are yours to propose. Write them in your own words if you like: the committee judges a clause by what it commits countries to, not by its wording.",
                 "Your writing is for your own practice. It's never marked, and the Architect's path rewards a text that is mostly yours."] },
        { at: "#c-rivals", tab: "record", face: "concerned", title: "Your rivals",
          text: [list(v.rivals.map(function (r) { return [r.name + ", " + r.style_name + ": ", r.style_what]; })),
                 "They play to win: each turn they look for the move that serves their instructions best, and on Hard they go after the delegations you worked on last. Their plans are hidden. That's what your staff is for."] },
        { at: "#c-staff", tab: "staff", face: "wry", title: "Your staff",
          text: ["You have " + (v.staff || []).length + " advisers. " + (v.staff && v.staff.length > 2 ? "A big delegation brings more staff, but greener ones." : "A smaller delegation brings fewer staff, but seasoned ones."),
                 list([["Analysts ", "study rivals: where they're heading next, and what they're after."],
                       ["Regional experts ", "read the delegations of your own regional group best."],
                       ["Legal advisers ", "tell you at the summit whether a rival's floor amendment would pass."]]),
                 "Post each to a delegation; reports start the turn after. Juniors can be wrong and say how sure they are; reports that prove right earn promotions. You can take on more, up to " + v.costs.staff_max + ", for Influence."] },
        { at: "#s-reserve", face: "eyebrow", title: "Counter-moves",
          text: [list([["Hold in reserve: ", "spend an action now, and your team answers the first rival move against you before your next turn."],
                       ["Secure: ", "a delegation that trusts you signs a commitment, and rivals pay double to move it."],
                       ["Right of reply: ", "at the summit, answer a rival who speaks against your clause (Respect " + v.costs.reply_respect + " or more)."],
                       ["Point of order: ", "a skill: rule a rival's floor amendment out of order."]]),
                 "When an adviser warns you a rival is heading for a delegation, this is how you get there first."] },
        { at: cr ? "#c-crisis" : "#c-event", tab: "brief", face: "concerned", title: "Crises, news and offers",
          text: [list([["A crisis ", "opens every chapter and changes the rules for that chapter" + (cr ? ". This one: " + lc(cr.title) + "." : ".")],
                       ["News ", "arrives every turn. Procedure questions earn Expertise and Respect if you answer correctly."],
                       ["Offers ", "come to your door: deals from delegations. Answering costs no action, but read the terms before you accept."],
                       ["Positions shift. ", "Governments change their minds during the session, so a file you read early may be out of date later."]])] },
        { at: "#s-skills-btn", face: "wry", title: "Diplomatic skills",
          text: ["Spend Expertise on skills (" + v.skill_cost + " each) in four branches: Procedure, Diplomacy, Drafting and Analysis.",
                 "Each branch suits a different way of playing: points of order, bloc whips, friendly amendments, rival intelligence and more."] },
        { at: "#s-end-turn", face: "calm", title: "Ending a turn",
          text: ["When your actions are spent, end the turn. Offers lapse, Influence comes in, rivals move and the next turn opens. When a stage's deadline arrives, the President moves the committee on.",
                 "Menu, or Escape, pauses the game. Your session is kept after every move, so you can stop and come back."] },
        { face: "eyebrow", title: "The first rule of the UN",
          text: ["Don't say no to something just because it isn't exactly what you wanted. A resolution that carries some of your aims is better than no resolution at all: half a loaf is better than none.",
                 "Vote down a text that carries your capital's main aim and you lose Respect; back an imperfect one and the room respects you for it. Only your red line is a reason to say no. Your rivals keep this rule too: a rival that gets its wish will not sink the text."] },
        { face: "eyebrow", title: "Then, the Summit", art: artSummit,
          text: [list([["Your opening speech: ", "firm, open or bridge. Each moves a different part of the room."],
                       ["Clause by clause: ", "each is voted on separately. Before each vote, make a last offer, call in a favour or deal with a rival's floor amendment, then cast your own vote."],
                       ["The resolution as a whole ", "goes to the final vote." + (sc ? " If it fails in the Council, a Presidential Statement may still be agreed." : "")]]),
                 "With the summit timer on, you have twenty seconds for each decision. You can turn it off in Settings."] },
        { face: "delighted", title: "And the debrief", art: artMedals,
          text: ["When the gavel falls you'll see a medal on each path, your rank, the session in numbers, every clause as a title deed, the turning points, and why every delegation voted as it did, number by number.",
                 "Positions in real-issue scenarios are estimates from sources, never fact. Read them as a starting point."] },
        { face: "delighted", title: "The gavel is yours", last: true,
          text: ["That's the whole session, from the first turn to the debrief. I'll be close by, and I'll speak up at the big moments.",
                 "You can replay this walkthrough at any time from the Menu. Good luck, Ambassador."] }
      ];
    }
    var E_INCOME = 2;

    var W = { steps: null, i: 0, done: null, tab: null, face: null };
    function walkStart(v, done, replay) {
      if (!G) { if (done) done(); return; }
      hideAdvice();
      W.steps = walkSteps(v).filter(function (s) { return !s.at || !s.tab || !$("t-" + s.tab).hidden; });
      W.i = 0; W.done = done; W.tab = TABS.filter(function (t) { return $("t-" + t).getAttribute("aria-selected") === "true"; })[0] || "brief";
      var wrap = $("s-walk"), face = $("s-guide-face");
      if (!W.face) { face.textContent = ""; W.face = G.portrait("calm"); face.appendChild(W.face); }
      $("s-guide-off").checked = false;
      var dots = $("s-guide-dots"); dots.textContent = "";
      W.steps.forEach(function () { dots.appendChild(h("li")); });
      wrap.hidden = false;
      document.body.classList.add("s-walking");
      if (!replay) A.play("open");
      walkShow(0);
    }
    function walkShow(i) {
      var s = W.steps[i]; W.i = i;
      if (s.tab) setTab(s.tab);
      if (s.pick) pick(s.pick);
      var guide = $("s-guide"), talk = guide.querySelector(".s-guide-talk");
      restart(talk, "s-talk-in");
      G.face(W.face, s.face); restart(W.face, "g-react");
      $("s-guide-step").textContent = (i + 1) + " of " + W.steps.length;
      $("s-guide-h").textContent = s.title;
      var b = $("s-guide-body"); b.textContent = "";
      if (s.art) b.appendChild(s.art(V));
      s.text.forEach(function (t) { if (typeof t === "string") b.appendChild(h("p", "", t)); else b.appendChild(t); });
      $("s-guide-dots").querySelectorAll("li").forEach(function (d, k) { d.className = k < i ? "done" : k === i ? "on" : ""; });
      $("s-guide-back").disabled = i === 0;
      $("s-guide-next").textContent = s.last ? "Begin the session" : "Next";
      $("s-guide-skip").hidden = !!s.last;
      // the spotlight and the guide glide to the part of the table being explained
      var spot = $("s-spot"), target = visible(s.at);
      var panes = target && target.closest(".s-panes");
      if (panes) {
        var sc0 = stage.getBoundingClientRect().width / stage.offsetWidth, pr = panes.getBoundingClientRect(), tr = target.getBoundingClientRect();
        if (tr.top < pr.top || tr.bottom > pr.bottom) panes.scrollTop += (tr.top - pr.top) / sc0 - 12;
      }
      requestAnimationFrame(function () {
        var gw = guide.offsetWidth, gh = guide.offsetHeight, left, top, W0 = stage.clientWidth, H0 = stage.clientHeight;
        if (target) {
          var r = stageBox(target), pad = 10;
          spot.classList.remove("off");
          spot.style.left = (r.x - pad) + "px"; spot.style.top = (r.y - pad) + "px";
          var bottom = panes ? stageBox(panes).y + stageBox(panes).h : H0;
          spot.style.width = (r.w + 2 * pad) + "px"; spot.style.height = Math.max(40, Math.min(r.h + 2 * pad, bottom - r.y + pad)) + "px";
          // beside the target if there is room (left, right, below, above), so the guide never covers what it points at
          var cy = function (y) { return Math.min(Math.max(12, y), H0 - gh - 12); }, cx = function (x) { return Math.min(Math.max(12, x), W0 - gw - 12); };
          var tries = [[r.x - gw - 24, cy(r.y)], [r.x + r.w + 24, cy(r.y)], [cx(r.x + r.w / 2 - gw / 2), r.y + r.h + 20], [cx(r.x + r.w / 2 - gw / 2), r.y - gh - 20]];
          var fit = tries.filter(function (q) { return q[0] >= 12 && q[1] >= 12 && q[0] + gw <= W0 - 12 && q[1] + gh <= H0 - 12; })[0];
          if (fit) { left = fit[0]; top = fit[1]; }
          else if (r.w > W0 * 0.45) { left = W0 - gw - 40; top = H0 - gh - 80; }           // a target as big as the map
          else { left = r.x > W0 / 2 ? 12 : W0 - gw - 12; top = cy(r.y); }
        } else {
          spot.classList.add("off");
          spot.style.left = (W0 / 2) + "px"; spot.style.top = (H0 / 2) + "px"; spot.style.width = "0px"; spot.style.height = "0px";
          left = (W0 - gw) / 2; top = Math.max(20, (H0 - gh) / 2 - 20);
        }
        guide.style.left = Math.max(12, left) + "px"; guide.style.top = Math.max(12, Math.min(top, H0 - gh - 12)) + "px";
        var X = parseFloat(spot.style.left), Y = parseFloat(spot.style.top), SW = parseFloat(spot.style.width), SH = parseFloat(spot.style.height);
        var box = { t: [0, 0, W0, Y], b: [0, Y + SH, W0, H0 - Y - SH], l: [0, Y, X, SH], r: [X + SW, Y, W0 - X - SW, SH] };
        document.querySelectorAll("#s-walk .s-dim").forEach(function (d) {
          var q = box[d.getAttribute("data-dim")];
          d.style.left = q[0] + "px"; d.style.top = q[1] + "px"; d.style.width = Math.max(0, q[2]) + "px"; d.style.height = Math.max(0, q[3]) + "px";
        });
        if (s.demo) s.demo();
      });
      $("s-guide-next").focus();
      if (i > 0) A.play("flip");
    }
    function walkEnd() {
      var wrap = $("s-walk"); if (wrap.hidden) return;
      if ($("s-guide-off").checked) { A.set("tips", false); syncSettings(); }
      wrap.hidden = true;
      document.body.classList.remove("s-walking");
      setTab(W.tab);
      var pn = document.querySelector(".s-panes"); if (pn) pn.scrollTop = 0;
      if (V && V.phase === "chapter") closePanel();                 // back to the map: the panels open from the bar
      var done = W.done; W.done = null;
      if (done) done(); else A.play("chime");
    }
    $("s-guide-next").addEventListener("click", function () { if (W.i >= W.steps.length - 1) walkEnd(); else walkShow(W.i + 1); });
    $("s-guide-back").addEventListener("click", function () { if (W.i > 0) walkShow(W.i - 1); });
    $("s-guide-skip").addEventListener("click", walkEnd);
    $("s-walk").addEventListener("keydown", function (e) {
      if (e.key === "ArrowRight") { e.preventDefault(); $("s-guide-next").click(); }
      else if (e.key === "ArrowLeft") { e.preventDefault(); $("s-guide-back").click(); }
      else if (e.key === "Tab") {                                    // keep the keyboard inside the guide while it speaks
        var f = Array.prototype.filter.call($("s-guide").querySelectorAll("button, input"), function (x) { return !x.disabled && !x.hidden; });
        if (!f.length) return;
        if (e.shiftKey && document.activeElement === f[0]) { e.preventDefault(); f[f.length - 1].focus(); }
        else if (!e.shiftKey && document.activeElement === f[f.length - 1]) { e.preventDefault(); f[0].focus(); }
      }
    });

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
    function moments(v, prev, news, won, lost) {
      if (v.stage && !v.stage.made && v.stage.turns_left === 1 && prev && prev.turn !== v.turn)
        president("eyebrow", "Delegates, this is the last turn of " + v.chapter_name + ". After it, the committee moves on, breakthrough or not.");
      if (v.meeting && prev && prev.turn !== v.turn) president("calm", "The " + v.meeting.name + " meets this turn. Delegates are welcome to attend.", "meet" + v.chapter + "." + v.turn);
      if (v.phase === "chapter" && prev.chapter !== v.chapter && v.crisis && v.crisis.chapter === v.chapter)
        advise("concerned", "A crisis: " + v.crisis.title + ". " + v.crisis.teaches);
      if (prev.phase === "chapter" && v.phase === "summit") advise("eyebrow", "The Summit is open. Choose how to open your speech: firm to rally your friends, open for Respect, bridge for the undecided.");
      if (won) advise("delighted", "Splendid: a regional group stands behind your draft. Keep it there; rivals will try to win it back.");
      if (lost) advise("concerned", "We've lost a regional group's endorsement. A side event can win it back.");
      var fresh = (v.offers || []).filter(function (o) { return !(prev.offers || []).some(function (p) { return p.id === o.id; }); });
      if (fresh.length) advise("wry", fresh[0].name + " is at your door with an offer. It's on your Brief, and it lapses when the turn ends.");
      news.forEach(function (x) {
        if (x.kind === "rival" && /struck your clause/.test(x.text)) advise("concerned", x.text + " Clauses with wide support are safer: the working group won't strike a clause it would pass.");
        if (x.kind === "worry") advise("concerned", x.text, null, staffOf(v, x.text));
        if (x.kind === "promote") advise("delighted", x.text, null, staffOf(v, x.text));
        if (x.kind === "counter") advise("delighted", x.text + " Well judged, Ambassador.");
        if (x.kind === "telegram") telegram(x.text, x.mood);
      });
      if (v.phase === "chapter" && prev.chapter !== v.chapter && prev.objectives) {
        var met = v.objectives[String(prev.chapter)];
        if (met !== undefined) advise(met ? "delighted" : "concerned", met ? "Breakthrough made. The committee has noticed." : "We missed that breakthrough. No matter: what counts is the final vote.");
      }
      if (v.phase === "chapter" && v.ap === 0) advise("calm", "Your actions are spent. End the turn when you're ready.", "ap0");
      if (v.phase === "chapter" && v.xp >= v.skill_cost) advise("wry", "You have Expertise enough for a diplomatic skill. Open Skills to choose one.", "skill");
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
                                                        "As things stand, the draft would fail. Find the delegations closest to tipping.");
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
        sel.disabled = v.phase === "done";
        sel.addEventListener("change", function () { move({ do: "post", adviser: a.id, iso3: sel.value || null }); });
        row.appendChild(sel); body.appendChild(row);
        var rep = h("p", "s-report");
        if (a.report) { rep.appendChild(h("span", "s-sure s-sure-" + a.report.stars, a.report.sure)); rep.appendChild(document.createTextNode(" " + a.report.text)); }
        else rep.textContent = a.post ? (a.starts ? "Starts reporting next turn." : "No report yet.") : a.what;
        body.appendChild(rep);
        li.appendChild(body); ul.appendChild(li);
      });
      var n = (v.staff || []).length, full = n >= v.costs.staff_max;
      $("c-hire-note").textContent = n + " of " + v.costs.staff_max + " advisers. A new adviser starts as a junior and costs " + v.costs.hire + " Influence.";
      var hr = $("c-hire-row"); hr.textContent = "";
      (v.staff_kinds || []).forEach(function (k) {
        hr.appendChild(btn(k.name, "s-btn ghost small", function () { move({ do: "hire", kind: k.code }); },
                           full || v.influence < v.costs.hire || v.phase !== "chapter"));
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
    function artDeal() {
      var t = h("div", "s-g-deal");
      var l = h("div", "s-g-tray"); l.appendChild(h("b", "", "You offer"));
      ["A funding pledge", "Trade terms"].forEach(function (x, i) { var c = h("span", "", x); c.style.animationDelay = (0.2 + i * 0.25) + "s"; l.appendChild(c); });
      var m = h("div", "s-g-hand", "⇄");
      var r = h("div", "s-g-tray"); r.appendChild(h("b", "", "You ask for"));
      ["Their yes"].forEach(function (x, i) { var c = h("span", "", x); c.style.animationDelay = (0.7 + i * 0.25) + "s"; r.appendChild(c); });
      t.appendChild(l); t.appendChild(m); t.appendChild(r);
      return t;
    }
    var DEAL = { iso: null, give: {}, get: {}, note: "" };
    function dealTable(iso) {
      DEAL = { iso: iso, give: {}, get: {}, note: "" };
      renderDeal();
      open("s-deal");
      A.play("flip");
    }
    function renderDeal() {
      var v = V, d = v && v.tokens[DEAL.iso]; if (!d || !d.deal) return;
      var t = d.deal;
      $("s-deal-h").textContent = v.you.name + " and " + d.name;
      $("s-deal-sub").textContent = d.name + " wants " + t.asks.map(function (k) { return ASK[k]; }).join(", ") +
        ". Trust " + d.trust + (t.bonus ? " (worth +" + t.bonus + " on the table)" : "") + ". Your budget: " +
        (v.budget.total - v.budget.used) + " of " + v.budget.total + " funding pledges left.";
      function tray(id, items, side, labels) {
        var box = $(id); box.textContent = "";
        Object.keys(labels).forEach(function (k) {
          var on = !!DEAL[side][k], have = k in items;
          var b = h("button", "s-item" + (on ? " on" : "")); b.type = "button"; b.setAttribute("aria-pressed", String(on));
          b.appendChild(h("b", "", labels[k].name));
          b.appendChild(h("span", "", labels[k].what));
          if (have) {
            var val = items[k], tag = side === "give" ? "worth " + val.toFixed(1) + " to them" : "costs them " + val.toFixed(1);
            if (side === "give" && t.asks.indexOf(k) >= 0) tag += " · they want this";
            if (side === "give" && t.capital[k] < 0) tag += " · your capital objects";
            b.appendChild(h("em", "", tag));
          } else {
            b.disabled = true;
            b.appendChild(h("em", "", side === "get" && (k === "yes" || k === "abstain") && t.red_line ? "the draft crosses their red line" : "not on the table"));
          }
          b.addEventListener("click", function () {
            if (DEAL[side][k]) delete DEAL[side][k]; else DEAL[side][k] = true;
            if (side === "get" && k === "yes") delete DEAL.get.abstain;
            if (side === "get" && k === "abstain") delete DEAL.get.yes;
            DEAL.note = ""; A.play("tick"); renderDeal();
          });
          box.appendChild(b);
        });
      }
      tray("s-deal-give", t.give, "give", v.deal_items.give);
      tray("s-deal-get", t.get, "get", v.deal_items.get);
      var gk = Object.keys(DEAL.give), wk = Object.keys(DEAL.get);
      var score = gk.reduce(function (s, k) { return s + (t.give[k] || 0); }, 0) + t.bonus - wk.reduce(function (s, k) { return s + (t.get[k] || 0); }, 0);
      var verdict = !gk.length || !wk.length ? null : score >= 1.5 ? "delighted" : score >= 0 ? "accept" : score >= -1.5 ? "more" : "refuse";
      var words = { delighted: "They'd jump at it.", accept: "They'd accept.", more: "They'd want a little more.", refuse: "They'd refuse." };
      var dial = $("s-deal-dial");
      dial.className = "s-meter-dial" + (verdict ? " v-" + verdict : "");
      dial.querySelector("i").style.transform = "rotate(" + Math.max(-80, Math.min(80, score * 30)) + "deg)";
      $("s-deal-verdict").textContent = DEAL.note || (verdict ? words[verdict] : "Choose something for each side of the table.");
      var cap = gk.reduce(function (s, k) { return s + (t.capital[k] || 0); }, 0), cb = $("s-deal-capital"); cb.textContent = "";
      if (gk.length) {
        if (G) cb.appendChild(G.portrait(cap < -1 ? "concerned" : cap < 0 ? "eyebrow" : "calm", "minister"));
        cb.appendChild(h("p", "", cap < -1 ? "Your capital would be furious (" + cap + " confidence)." : cap < 0 ? "Your capital would grumble (" + cap + " confidence)." : "Your capital would approve."));
      }
      var cost = DEAL.give.funding ? v.costs.deal_funding : 0;
      $("s-deal-note").textContent = "A deal takes " + v.costs.deal_ap + " actions" + (cost ? " and " + cost + " Influence" : "") +
        ". A refusal still uses the actions. Promises made here are kept, or broken, at the summit.";
      $("s-deal-go").disabled = !gk.length || !wk.length || !v.deal_ready || v.ap < v.costs.deal_ap || v.influence < cost;
    }
    function dealAnswer(v, out) {
      if (out.deal) {
        close("s-deal");
        say("Deal done with " + (v.tokens[DEAL.iso] || {}).name + ".");
        restart(document.body, "s-dealt");
        return;
      }
      var labels = v.deal_items.give;
      DEAL.note = "They turned it down." + (out.counter ? " They'd take it with " + labels[out.counter].name.toLowerCase() + " added: try again next turn." : " Try a better offer next turn.");
      say(DEAL.note);
      if (!$("s-deal").hidden) renderDeal();
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
      var ot = $("c-overtime"); ot.textContent = "";
      if (v.overtime_next) ot.appendChild(btn("Overtime: +1 action for " + v.overtime_next + " Influence", "s-btn ghost small", function () { move({ do: "overtime" }); }, v.influence < v.overtime_next));
      else if (v.phase === "chapter") ot.appendChild(h("p", "s-small", "Your staff can't work any later this turn."));
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
      var nb = $("n-blocs"); if (nb) nb.textContent = v.meeting && !v.meeting.attended ? "!" : "";
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
    var landsTagged = false;
    function stageLook(v) {
      var b = document.body;
      ["1", "2", "3", "summit"].forEach(function (k) { b.classList.remove("s-stage-" + k); });
      b.classList.add("s-stage-" + (v.phase === "chapter" ? (v.length === "quick" ? "1" : String(v.chapter)) : "summit"));
      if (!landsTagged) {
        Object.keys(lands).forEach(function (iso) { var t = v.tokens[iso]; if (t && t.rcode) lands[iso].forEach(function (l) { l.classList.add("rg-" + t.rcode.toLowerCase()); }); });
        landsTagged = true;
      }
      if (v.phase === "chapter") { $("t-blocs").hidden = !(v.rooms || []).length; $("t-sponsors").hidden = !(v.race || []).length; }
    }
    var btShown = {};
    function breakthroughCard(v, prev) {
      if (!v.stage || !v.stage.made || v.stage.stayed || btShown[v.chapter]) return;
      btShown[v.chapter] = true;
      $("s-bt-h").textContent = "Breakthrough: " + v.stage.breakthrough;
      $("s-bt-p").textContent = "Well done, delegates. " + (v.stage.turns_left ? "You have " + v.stage.turns_left + " turn" + (v.stage.turns_left === 1 ? "" : "s") + " left in " + v.chapter_name +
        ". Move on now, and that time becomes momentum; or keep working to strengthen your hand." : "This is the stage's last turn.");
      $("s-bt-unlocks").textContent = v.stage.unlocks;
      $("s-bt-go").textContent = "Move on now: +" + v.stage.momentum.respect + " Respect, +" + v.stage.momentum.influence + " Influence";
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
    $("s-replay-walk").addEventListener("click", function () { close("s-pause"); if (V) walkStart(V, null, true); });
    $("s-side-event").addEventListener("click", function () { move({ do: "side_event", region: $("s-region-pick").value }); });
    $("s-bloc-whip").addEventListener("click", function () { move({ do: "bloc_whip", group: $("s-bloc-pick").value }); });
    $("s-end-turn").addEventListener("click", function () { amending = null; move({ do: "end_turn" }); });
    $("s-reserve").addEventListener("click", function () { move({ do: "reserve" }); });
    $("s-bt-go").addEventListener("click", function () { close("s-breakthrough"); move({ do: "advance" }); });
    $("s-bt-stay").addEventListener("click", function () { close("s-breakthrough"); move({ do: "stay" }); });
    document.querySelector("#s-chapter-card [data-close]").addEventListener("click", function () {
      if (stagePanel && V && V.phase === "chapter") {
        var p = stagePanel; stagePanel = null;
        setTimeout(function () { if (!panelOpen() && $("s-walk").hidden) setTab(p, false, p === "draft" ? "center" : null); }, 250);   // unless you've already opened one
      }
    });
    $("s-deal-go").addEventListener("click", function () {
      if (!DEAL.iso) return;
      move({ do: "deal", iso3: DEAL.iso, give: Object.keys(DEAL.give), get: Object.keys(DEAL.get) });
    });
    $("s-abandon").addEventListener("click", function () {
      if (!window.confirm("Abandon this session? It can't be brought back.")) return;
      if (mode === "saved") api({ do: "abandon", save_id: +saveId }).then(function () { window.location.href = "/session"; });
      else { var list = slots(); list.splice(slot, 1); keep(list); window.location.href = "/session"; }
    });

    if (mode === "guest") {
      guest = slots()[slot];
      if (!guest || guest.pack !== document.body.getAttribute("data-pack")) {
        say("This session isn't kept on this laptop. Start a new one from The Session.");
        $("s-end-turn").hidden = true;
        return;
      }
    }
    call({ do: "view" }).then(function (r) { draw(r.view); if (r.view.phase === "done") result(r.view); }).catch(function (e) { say(e.message); });
  }

  if (page === "title") titlePage();
  else if (page === "new") newPage();
  else if (page === "game") gamePage();
})();
