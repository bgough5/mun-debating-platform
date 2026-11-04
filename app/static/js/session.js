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
  // The game
  // =====================================================================================================
  function gamePage() {
    var mode = document.body.getAttribute("data-mode"), saveId = document.body.getAttribute("data-save-id");
    var slot = +(new URLSearchParams(window.location.search).get("slot") || 0);
    var guest = null, V = null, busy = false, seenLog = 0;
    var tokens = {};
    document.querySelectorAll("#b-map .b-token").forEach(function (g) { tokens[g.getAttribute("data-iso")] = g; });

    function body(extra) {
      var b = { do: extra.do };
      if (extra.action) b.action = extra.action;
      if (mode === "saved") b.save_id = +saveId; else { b.state = guest.state; b.sig = guest.sig; }
      return b;
    }
    function call(extra) {
      if (busy) return Promise.reject(new Error("One moment…"));
      busy = true;
      return api(body(extra)).then(function (r) {
        busy = false;
        if (r.state) {                                     // a guest: keep the new signed state on this laptop
          guest.state = r.state; guest.sig = r.sig; guest.where = where(r.view); guest.at = Date.now();
          if (r.view.result) guest.medal = ["No medal", "Bronze", "Silver", "Gold"][r.view.result.grade];
          var list = slots(); list[slot] = guest; keep(list);
        }
        return r;
      }, function (e) { busy = false; throw e; });
    }

    function meter(id, value) {
      var li = $(id), b = li.querySelector("b"), old = b.textContent;
      b.textContent = value;
      if (old !== "–" && old !== String(value)) { restart(li, "bump"); if (id === "m-influence" && +value > +old) A.play("coin"); }
    }
    function chapterCard(v) {
      var summit = v.phase === "summit";
      $("s-cc-eyebrow").textContent = summit ? "The final act" : (v.length === "quick" ? "The working session" : "Chapter " + v.chapter + " of " + v.chapters);
      $("s-cc-h").textContent = summit ? "The Summit" : v.chapter_name;
      $("s-cc-goal").textContent = summit ? "The draft goes to the vote, clause by clause, then as a whole." : v.goal;
      open("s-chapter-card");
      restart(document.querySelector("#s-chapter-card .s-doc"), "shown");
      A.play(v.chapter === 1 && !summit ? "open" : "chime");
    }

    function draw(v, out) {
      var prev = V; V = v;
      $("s-where").textContent = v.phase === "done" ? "Finished" : v.phase === "summit" ? "The Summit" : (v.length === "quick" ? "Working session" : "Chapter " + v.chapter + " of " + v.chapters) + " · turn " + v.turn + " of " + v.turns;
      $("s-you").textContent = "You are " + v.you.name + " · " + v.rule + " · aiming for " + v.path.name;
      meter("m-influence", v.influence); meter("m-respect", v.respect); meter("m-expertise", v.expertise);
      var ap = $("s-ap"); ap.textContent = "";
      for (var i = 0; i < Math.max(v.ap, 0); i++) ap.appendChild(h("i", "on"));
      $("m-ap").setAttribute("aria-label", v.ap + " actions left this turn");
      // chapter
      $("c-chapter-h").textContent = v.phase === "summit" ? "The Summit" : (v.length === "quick" ? "Working session" : "Chapter " + v.chapter + ": " + v.chapter_name);
      $("c-goal").textContent = v.phase === "summit" ? "The summit screens arrive in the next update: for now, the session pauses here." : v.goal;
      $("c-turn").textContent = v.phase === "chapter" ? "Turn " + v.turn + " of " + v.turns + ". Sponsors " + v.sponsors + ", signatories " + v.signatories + " (" + v.signers_needed + " signers needed)." : "";
      // news
      var ev = v.event, box = $("c-event-body"); box.textContent = "";
      $("c-event").hidden = !ev || v.phase !== "chapter";
      if (ev && v.phase === "chapter") {
        if (ev.hypothetical) box.appendChild(h("span", "s-hypo", "Hypothetical"));
        box.appendChild(h("p", "s-goal", ev.title));
        if (ev.body) box.appendChild(h("p", "", ev.body));
        if (v.question) {
          var row = h("div", "s-row");
          v.question.options.forEach(function (opt, k) {
            var b = h("button", "s-btn ghost small", opt); b.type = "button";
            b.addEventListener("click", function () { move({ do: "answer", option: k }); });
            row.appendChild(b);
          });
          box.appendChild(row);
        } else if (ev.teaches) box.appendChild(h("p", "s-small", ev.teaches));
        if (!prev || !prev.event || prev.event.title !== ev.title || prev.turn !== v.turn) A.play("news");
      }
      // instructions
      var il = $("c-instr-list"); il.textContent = "";
      [["in", "Get in: ", v.mandate.must.label], ["in", "Also get in: ", v.mandate.also.label], ["out", "Keep out: ", v.mandate.red.label]].forEach(function (x) {
        var li = h("li"); li.appendChild(h("span", x[0], x[1])); li.appendChild(document.createTextNode(x[2])); il.appendChild(li);
      });
      $("c-aim").textContent = "Your aim: " + v.path.name + ". " + v.path.what;
      // the draft
      var ol = $("c-clauses"); ol.textContent = "";
      v.draft.forEach(function (c) {
        var li = h("li", c.mine ? "mine" : c.stance < 0 ? "against" : "");
        li.appendChild(document.createTextNode(c.text));
        li.appendChild(h("span", "s-by", (c.mine ? "Yours" : c.author) + (c.amended_by.length ? " · amended by " + c.amended_by.join(", ") : "") +
                                          " · " + c.tags.map(function (t) { return t.label; }).join("; ")));
        ol.appendChild(li);
      });
      // rivals
      var rl = $("c-rival-list"); rl.textContent = "";
      v.rivals.forEach(function (r) { rl.appendChild(h("li", "rival", r.name + (r.want ? ": wants " + r.want.toLowerCase() + "; blocks " + r.block.toLowerCase() : ": instructions unknown"))); });
      // the record (newest first; new lines slide in)
      var lg = $("c-log"); lg.textContent = "";
      var fresh = v.log.length - Math.min(seenLog, v.log.length);
      v.log.slice().reverse().forEach(function (x, k) { lg.appendChild(h("li", x.kind + (k < fresh && seenLog ? " fresh" : ""), x.when + ": " + x.text)); });
      if (seenLog && v.log.some(function (x, k) { return k >= v.log.length - fresh && x.kind === "rival"; })) A.play("paper");
      seenLog = v.log.length;
      // the map
      Object.keys(tokens).forEach(function (iso) {
        var t = tokens[iso], d = v.tokens[iso] || {};
        t.classList.toggle("you", !!d.you); t.classList.toggle("rival", !!d.rival); t.classList.toggle("signed", !!d.signed);
        t.classList.toggle("lean-for", !d.you && !d.rival && d.est === "yes"); t.classList.toggle("lean-against", !d.you && !d.rival && d.est === "no");
        var line = t.querySelector(".b-line");
        if (line) line.textContent = d.you ? "You" : d.rival ? "Rival" : d.est === "yes" ? "For" : d.est === "no" ? "Against" : d.est ? "Unsure" : "";
      });
      $("s-end-turn").hidden = v.phase !== "chapter";
      // a new chapter, or the summit, opens with its card
      if (!prev ? (v.turn === 1 && v.phase === "chapter" && seenLogAtStart(v)) : (prev.chapter !== v.chapter || prev.phase !== v.phase)) chapterCard(v);
      if (out && out.right !== undefined) say((out.right ? "Right. " : "Not quite. ") + out.why);
    }
    function seenLogAtStart(v) { return v.log.filter(function (x) { return x.kind === "action"; }).length === 0; }

    function move(action) {
      call({ do: "move", action: action }).then(function (r) { draw(r.view, r.out); if (action.do === "end_turn") A.play("gavel"); })
        .catch(function (e) { say(e.message); });
    }
    $("s-end-turn").addEventListener("click", function () { move({ do: "end_turn" }); });
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
