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

  // ---------- the 1920x1080 table, scaled to the screen ----------
  function fit() {
    var s = Math.min(window.innerWidth / 1920, window.innerHeight / 1080);
    stage.style.transform = "translate(" + ((window.innerWidth - 1920 * s) / 2) + "px," + ((window.innerHeight - 1080 * s) / 2) + "px) scale(" + s + ")";
  }
  window.addEventListener("resize", fit); fit();
  function fitTitle() {
    var el = $("b-committee"); if (!el) return;
    var size = 44; el.style.fontSize = size + "px";
    while (el.scrollWidth > el.clientWidth && size > 26) { size -= 2; el.style.fontSize = size + "px"; }
  }
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
  function where(v) { return v.phase === "done" ? "Finished" : v.phase === "summit" ? "The Summit" : "Chapter " + v.chapter + ", turn " + v.turn; }

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
    var shown = Array.prototype.filter.call(document.querySelectorAll(".s-overlay"), function (o) { return !o.hidden; });
    if (shown.length) { close(shown[shown.length - 1].id); return; }
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
    var tokens = {};
    document.querySelectorAll("#b-map .b-token").forEach(function (g) { tokens[g.getAttribute("data-iso")] = g; });
    var SOUND = { lobby: "paper", read: "flip", propose: "stamp", amend: "paper", strike: "stamp", promise: "coin", side_event: "chime",
                  favour: "coin", whip: "tick", sign: "stamp", skill: "chime", divide: "paper", merge: "stamp", bloc_whip: "chime", abstain: "stamp" };
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
    var TABS = ["brief", "draft", "dele", "record"];
    function setTab(name, focus) {
      TABS.forEach(function (t) {
        var b = $("t-" + t), on = t === name;
        b.setAttribute("aria-selected", String(on)); b.tabIndex = on ? 0 : -1; $("p-" + t).hidden = !on;
      });
      if (focus) $("t-" + name).focus();
    }
    document.querySelector(".s-tabs").addEventListener("click", function (e) { var b = e.target.closest("[data-tab]"); if (b) { setTab(b.getAttribute("data-tab")); A.play("flip"); } });
    document.querySelector(".s-tabs").addEventListener("keydown", function (e) {
      var i = TABS.indexOf(document.activeElement.getAttribute("data-tab")); if (i < 0) return;
      if (e.key === "ArrowRight" || e.key === "ArrowLeft") { e.preventDefault(); setTab(TABS[(i + (e.key === "ArrowRight" ? 1 : 3)) % 4], true); }
    });

    // ---------- moves ----------
    function move(action) {
      if (V && V.phase !== "chapter") return;
      call({ do: "move", action: action }).then(function (r) {
        draw(r.view, r.out, action);
        if (action.do === "end_turn") A.play("gavel"); else if (SOUND[action.do]) A.play(SOUND[action.do]);
      }).catch(function (e) { say(e.message); A.play("tick"); });
    }

    function meter(id, value) {
      var li = $(id), b = li.querySelector("b"), old = b.textContent;
      b.textContent = value;
      if (old !== "–" && old !== String(value)) { restart(li, "bump"); if (id === "m-influence" && +value > +old) A.play("coin"); }
    }
    function chapterCard(v, prev) {
      var summit = v.phase === "summit";
      var was = prev && prev.objectives && v.objectives[String(prev.chapter)];
      $("s-cc-eyebrow").textContent = summit ? "The final act" : (v.length === "quick" ? "The working session" : "Chapter " + v.chapter + " of " + v.chapters);
      $("s-cc-h").textContent = summit ? "The Summit" : v.chapter_name;
      var pre = prev && prev.phase === "chapter" ? ("Chapter " + prev.chapter + ": goal " + (was ? "met. +3 Influence, +1 Respect. " : "missed. ")) : "";
      $("s-cc-goal").textContent = pre + (summit ? "The draft goes to the vote, clause by clause, then as a whole." : v.goal);
      open("s-chapter-card");
      restart(document.querySelector("#s-chapter-card .s-doc"), "shown");
      A.play(v.chapter === 1 && !summit && !prev ? "open" : "chime");
    }

    // ---------- the Brief tab ----------
    function progress(v) {
      var ul = $("c-progress"); ul.textContent = "";
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
      var flags = [];
      if (d.signed) flags.push("signed as your " + d.signed); if (d.pledged) flags.push("pledged to abstain");
      if (d.favour) flags.push("owes you a favour"); if (d.promised) flags.push("you've made it a promise");
      if (d.predicted) flags.push("you predicted: " + d.predicted);
      if (flags.length) fact("Also", flags.join("; "));
      c.appendChild(dl);
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
      $("s-where").textContent = v.phase === "done" ? "Finished" : v.phase === "summit" ? "The Summit" : (v.length === "quick" ? "Working session" : "Chapter " + v.chapter + " of " + v.chapters) + " · turn " + v.turn + " of " + v.turns;
      $("s-you").textContent = "You are " + v.you.name + " · " + v.rule + " · aiming for " + v.path.name;
      meter("m-influence", v.influence); meter("m-respect", v.respect); meter("m-expertise", v.expertise);
      var ap = $("s-ap"); ap.textContent = "";
      for (var i = 0; i < Math.max(v.ap, 0); i++) ap.appendChild(h("i", "on"));
      $("m-ap").setAttribute("aria-label", v.ap + " actions left this turn");
      $("c-chapter-h").textContent = v.phase === "summit" ? "The Summit" : (v.length === "quick" ? "Working session" : "Chapter " + v.chapter + ": " + v.chapter_name);
      $("c-goal").textContent = v.phase === "summit" ? "The summit screens arrive in the next update: for now, the session pauses here." : v.goal;
      $("c-turn").textContent = v.phase === "chapter" ? "Turn " + v.turn + " of " + v.turns + "." : "";
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
      var il = $("c-instr-list"); il.textContent = "";
      [["in", "Get in: ", v.mandate.must.label], ["in", "Also get in: ", v.mandate.also.label], ["out", "Keep out: ", v.mandate.red.label]].forEach(function (x) {
        var li = h("li"); li.appendChild(h("span", x[0], x[1])); li.appendChild(document.createTextNode(x[2])); il.appendChild(li);
      });
      $("c-aim").textContent = "Your aim: " + v.path.name + ". " + v.path.what;
      regions(v);
      draft(v, prev);
      countryPicker(v); country(v); skills(v);
      // the delegate's reply, and anything else the move said
      if (out && out.heard) {
        $("c-heard").hidden = false;
        var q = $("c-heard-text"); q.textContent = "";
        q.appendChild(document.createTextNode("“" + out.heard + "”"));
        q.appendChild(h("cite", "", "The delegate of " + (v.tokens[action.iso3] || {}).name + (out.red_line ? " (a red line: they barely moved)" : "")));
        restart(q, "s-in");
      }
      if (out && out.file) showFile(out.file);
      if (out && out.accepted === false) say(action.do === "strike" ? "The working group wants that clause, so it stays. Your Influence is returned." : "The working group didn't accept that amendment: it would lose support. Your Influence is returned.");
      else if (out && out.right !== undefined) say((out.right ? "Right. " : "Not quite. ") + out.why);
      else if (action && action.do === "end_turn") say("Rivals have moved: see the Record.");
      // rivals and the record
      var rl = $("c-rival-list"); rl.textContent = "";
      v.rivals.forEach(function (r) { rl.appendChild(h("li", "rival", r.name + (r.want ? ": wants " + r.want.toLowerCase() + "; blocks " + r.block.toLowerCase() : ": instructions unknown (Rival intelligence reveals them)"))); });
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
      news.forEach(function (x, k) {
        if (x.at && tokens[x.at]) setTimeout(function () { restart(tokens[x.at], x.kind === "rival" ? "s-pulse-rival" : "s-pulse"); }, 250 * k);
      });
      if (news.some(function (x) { return x.kind === "rival"; })) setTimeout(function () { A.play("paper"); }, 300);
      if (prev) {
        var won = v.regions.some(function (r) { return r.owner === "you" && !prev.regions.some(function (p) { return p.code === r.code && p.owner === "you"; }); });
        var lost = prev.regions.some(function (p) { return p.owner === "you" && !v.regions.some(function (r) { return r.code === p.code && r.owner === "you"; }); });
        if (won) { A.play("fanfare"); say("A regional group now endorses your draft."); } else if (lost) { A.play("sting"); say("A regional group no longer endorses your draft."); }
      }
      $("s-end-turn").hidden = v.phase !== "chapter";
      if (!prev ? (v.turn === 1 && v.phase === "chapter" && seenLogAtStart(v)) : (prev.chapter !== v.chapter || prev.phase !== v.phase)) chapterCard(v, prev);
    }
    function seenLogAtStart(v) { return v.log.filter(function (x) { return x.kind === "action"; }).length === 0; }

    // the map is the way in to a delegation
    $("b-map").addEventListener("click", function (e) {
      var t = e.target.closest(".b-token"); if (!t || !V) return;
      var iso = t.getAttribute("data-iso"); if (iso === V.you.iso3) return;
      pick(iso); setTab("dele"); A.play("flip");
    });
    $("s-side-event").addEventListener("click", function () { move({ do: "side_event", region: $("s-region-pick").value }); });
    $("s-bloc-whip").addEventListener("click", function () { move({ do: "bloc_whip", group: $("s-bloc-pick").value }); });
    $("s-end-turn").addEventListener("click", function () { amending = null; move({ do: "end_turn" }); });
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
    call({ do: "view" }).then(function (r) { draw(r.view); }).catch(function (e) { say(e.message); });
  }

  if (page === "title") titlePage();
  else if (page === "new") newPage();
  else if (page === "game") gamePage();
})();
