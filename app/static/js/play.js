/* Single player on the board (D-099). One game, two ways to keep it: a signed-in student's moves are saved as they go;
   a guest's game lives only in this tab and goes to the server with each move, which answers and forgets it.
   The steps: read the clause, lobby up to five delegations (click a country), record what you think they'll do,
   amend the clause if it would win votes, then call the vote and watch it sweep the map. All text from the server
   goes in with textContent. */
(function () {
  "use strict";
  var G = JSON.parse(document.getElementById("p-initial").textContent);
  var stage = document.getElementById("b-stage"), map = document.getElementById("b-map"), boardEl = document.getElementById("b-board");
  var tokens = {}, lands = {}, scale = 1, amending = false, draftTags = null, busy = false;
  map.querySelectorAll(".b-token").forEach(function (g) { tokens[g.getAttribute("data-iso")] = g; });
  map.querySelectorAll(".b-land").forEach(function (p) { (lands[p.getAttribute("data-iso")] = lands[p.getAttribute("data-iso")] || []).push(p); });
  var READS = [[-2, "Strongly against"], [-1, "Against"], [0, "Undecided"], [1, "For"], [2, "Strongly for"]];
  var WORD = { yes: "Yes", no: "No", abstain: "Abstain", absent: "Absent" };

  function $(id) { return document.getElementById(id); }
  function h(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function motion() { return document.body.getAttribute("data-fx-motion") !== "off" && !(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches); }
  function say(t) { $("p-say").textContent = t; $("p-msg").textContent = t; }
  function restart(el, cls) { el.classList.remove(cls); void el.getBoundingClientRect(); el.classList.add(cls); }

  function fit() {
    scale = Math.min(window.innerWidth / 1920, window.innerHeight / 1080);
    stage.style.transform = "translate(" + ((window.innerWidth - 1920 * scale) / 2) + "px," + ((window.innerHeight - 1080 * scale) / 2) + "px) scale(" + scale + ")";
  }
  window.addEventListener("resize", fit); fit();
  function fitTitle() {
    var el = $("b-committee"), size = 44;
    el.style.fontSize = size + "px";
    while (el.scrollWidth > el.clientWidth && size > 26) { size -= 2; el.style.fontSize = size + "px"; }
  }
  fitTitle();
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(fitTitle);

  function csrf() { var m = document.cookie.match(/(?:^|;\s*)soc_csrf=([^;]+)/); return m ? decodeURIComponent(m[1]) : ""; }
  function api(action, extra) {
    var body = { action: action, mode: G.mode };
    if (G.mode === "saved") body.pid = G.pid;
    else { body.code = G.code; body.iso3 = G.iso3; body.seed = G.seed; body.paragraph_id = G.paragraph_id; body.tags = G.tags; body.lobbies = G.lobbies; }
    Object.keys(extra || {}).forEach(function (k) { body[k] = extra[k]; });
    return fetch("/play/api", { method: "POST", headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf() }, body: JSON.stringify(body) })
      .then(function (r) { return r.json().then(function (j) { if (!r.ok) throw new Error(j.error || "That didn't work."); return j; }); });
  }
  function fail(e) { say(e.message || "That didn't work. Try again."); busy = false; }

  // ---------- the steps track ----------
  function step(n) {
    document.querySelectorAll("#p-track li").forEach(function (li, i) { li.classList.toggle("done", i < n); li.classList.toggle("now", i === n); });
  }

  // ---------- the clause and amending it ----------
  function renderTags() {
    var ul = $("p-tags"); ul.innerHTML = "";
    var labels = G.tag_labels, current = amending ? draftTags : G.tags;
    Object.keys(labels).forEach(function (code) {
      var on = current.indexOf(code) >= 0;
      if (!amending && !on) return;
      var li = h("li", on ? "on" : "");
      if (amending) {
        var lab = h("label"), box = document.createElement("input"); box.type = "checkbox"; box.checked = on;
        box.addEventListener("change", function () {
          draftTags = box.checked ? draftTags.concat([code]) : draftTags.filter(function (t) { return t !== code; });
          li.classList.toggle("on", box.checked);
        });
        lab.appendChild(box); lab.appendChild(document.createTextNode(labels[code])); li.appendChild(lab);
      } else li.textContent = labels[code];
      ul.appendChild(li);
    });
  }
  $("p-amend").addEventListener("click", function () {
    if (G.stage !== "lobbying") return;
    amending = !amending; draftTags = G.tags.slice();
    $("p-amend").textContent = amending ? "Cancel" : "Amend the clause";
    $("p-amend-save").hidden = !amending;
    renderTags();
    if (amending) say("Tick what the clause should commit countries to. Dropping what a country objects to can win its vote.");
  });
  $("p-amend-save").addEventListener("click", function () {
    if (!draftTags.length) { say("A clause needs at least one thing it commits countries to."); return; }
    var saved = G.tags; G.tags = draftTags.slice();
    api("amend", { tags: draftTags }).then(function (r) {
      G.tags = r.tags; amending = false; $("p-amend").textContent = "Amend the clause"; $("p-amend-save").hidden = true;
      renderTags(); step(2); say("Amended. Delegations you spoke to earlier may now see it differently."); chance();
    }).catch(function (e) { G.tags = saved; fail(e); });
  });

  // ---------- the whip count ----------
  function chance() {
    api("chance").then(function (r) {
      $("p-chance").textContent = Math.round(r.p_pass * 100) + "%";
      $("p-range").textContent = "chance it passes · about " + r.yes_mean + " yes votes expected (" + r.yes_lo + " to " + r.yes_hi + ")";
    }).catch(fail);
  }

  // ---------- lobbying ----------
  function renderLog(freshIso) {
    var ol = $("p-log"); ol.innerHTML = "";
    G.lobbies.slice().reverse().forEach(function (l, j) {
      var i = G.lobbies.length - 1 - j;
      var li = h("li", l.iso3 === freshIso && j === 0 ? "fresh" : "");
      li.appendChild(h("p", "who", G.names[l.iso3] || l.iso3));
      li.appendChild(h("p", "heard", "“" + l.heard + "”"));
      var row = h("div", "p-reads"); row.setAttribute("role", "group"); row.setAttribute("aria-label", "What do you think " + (G.names[l.iso3] || l.iso3) + " will do?");
      READS.forEach(function (r) {
        var b = h("button", null, r[1]); b.type = "button"; b.setAttribute("aria-pressed", String(l.position === r[0]));
        b.disabled = G.stage !== "lobbying";
        b.addEventListener("click", function () { record(i, r[0]); });
        row.appendChild(b);
      });
      li.appendChild(row); ol.appendChild(li);
    });
    var left = G.limit - G.lobbies.length;
    $("p-left").textContent = left > 0 ? left + " of " + G.limit + " conversations left." : "No conversations left: record what you think, then vote.";
    $("p-talk").disabled = left <= 0 || G.stage !== "lobbying";
    paintTokens();
  }
  function record(i, pos) {
    var l = G.lobbies[i]; l.position = pos; renderLog();
    var done = function () { chance(); say("Noted: " + (G.names[l.iso3] || l.iso3) + ", " + READS[pos + 2][1].toLowerCase() + "."); };
    if (G.mode === "saved") api("read", { id: l.id, position: pos }).then(done).catch(fail); else done();
  }
  $("p-talk").addEventListener("click", function () {
    if (busy || G.stage !== "lobbying") return;
    var iso = $("p-who").value; busy = true;
    api("lobby", { iso3_target: iso }).then(function (r) {
      G.lobbies.push({ id: r.id, iso3: iso, heard: r.heard, position: null, tags: r.tags });
      busy = false; step(1); renderLog(iso);
      if (tokens[iso]) restart(tokens[iso], "pop");
      say((G.names[iso] || iso) + " says: “" + r.heard + "” What do you think they'll do?");
    }).catch(fail);
  });
  Object.keys(tokens).forEach(function (iso) {
    tokens[iso].addEventListener("click", function () {
      if (iso === G.iso3) { say("That's you: " + G.country + "."); return; }
      var sel = $("p-who"); sel.value = iso;
      Object.keys(tokens).forEach(function (k) { tokens[k].classList.toggle("picked", k === iso); });
      say("Talk to " + (G.names[iso] || iso) + "? Press Talk.");
    });
  });

  function paintTokens() {
    var read = {};
    G.lobbies.forEach(function (l) { read[l.iso3] = l.position; });
    Object.keys(tokens).forEach(function (iso) {
      var g = tokens[iso], pos = read[iso];
      g.classList.toggle("you", iso === G.iso3);
      g.classList.toggle("talked", iso in read);
      ["read-yes", "read-no", "read-abstain"].forEach(function (c) { g.classList.remove(c); });
      if (pos != null && !G.result) g.classList.add(pos >= 1 ? "read-yes" : pos <= -1 ? "read-no" : "read-abstain");
      var line = g.querySelector(".b-line");
      if (line && !G.result) line.textContent = iso === G.iso3 ? "You" : (pos != null ? READS[pos + 2][1] : (iso in read ? "Talked" : ""));
    });
  }

  // ---------- the vote ----------
  var SEAL = "M0-60C14-58 20-66 32-56S50-44 56-30 66-12 60 2 66 22 56 34 48 52 34 58 18 66 2 62-14 66-30 58-48 52-56 38-64 20-60 4-66-12-56-28-48-50-34-56-16-62 0-60Z";
  function seal(passed) {
    var box = h("div", "b-sealbox");
    box.innerHTML = '<svg viewBox="-70 -70 140 140" width="300" height="300" aria-hidden="true"><g class="b-seal"><path class="b-seal-wax" d="' + SEAL +
      '"/><circle class="b-seal-ring" r="44"/><text class="b-seal-text" text-anchor="middle" y="7" font-size="18"></text></g></svg>';
    box.querySelector(".b-seal").classList.add(passed ? "passed" : "failed");
    box.querySelector(".b-seal-text").textContent = passed ? "PASSED" : "FAILED";
    boardEl.appendChild(box);
    // It lands, then lifts off so the map shows how every country voted.
    setTimeout(function () { box.classList.add("gone"); setTimeout(function () { box.remove(); }, 700); }, motion() ? 2800 : 0);
  }
  function showVotes(res, animate, done) {
    var order = Object.keys(res.votes).sort(function (a, b) { return (G.names[a] || a).localeCompare(G.names[b] || b); });
    var gap = animate && motion() ? Math.max(70, Math.min(220, 3200 / Math.max(1, order.length))) : 0;
    order.forEach(function (iso, i) {
      setTimeout(function () {
        var v = res.votes[iso];
        (lands[iso] || []).forEach(function (p) { p.classList.add("v-" + v); });
        var g = tokens[iso];
        if (g) {
          ["read-yes", "read-no", "read-abstain", "picked"].forEach(function (c) { g.classList.remove(c); });
          g.classList.add("v-" + v, "cast"); if (gap) restart(g, "pop");
          var line = g.querySelector(".b-line"); if (line) line.textContent = WORD[v] || v;
        }
      }, i * gap);
    });
    setTimeout(function () { seal(res.passed); done(); }, order.length * gap + (gap ? 300 : 0));
  }
  function renderResult(res) {
    var c = $("p-result"); c.hidden = false; c.innerHTML = "";
    c.appendChild(h("h2", null, "The result"));
    c.appendChild(h("p", "b-big " + (res.passed ? "passed" : "failed"), res.passed ? "Passed" : "Failed"));
    c.appendChild(h("p", null, res.summary));
    var right = res.readings.filter(function (r) { return r.correct === true; }).length, judged = res.readings.filter(function (r) { return r.correct !== null; }).length;
    if (judged) c.appendChild(h("p", null, "You read " + right + " of " + judged + " delegations correctly."));
    var ul = h("ul", "p-result-list");
    res.readings.forEach(function (r) {
      if (r.correct === null) return;
      ul.appendChild(h("li", null, r.country + ": you thought " + (WORD[r.read_vote] || "?").toLowerCase() + ", they voted " + (WORD[r.actual_vote] || "?").toLowerCase() +
        (r.correct ? " ✓" : "") + (r.moved_after ? " (your amendment moved them)" : "")));
    });
    if (ul.children.length) c.appendChild(ul);
    if (res.moved && res.moved.length) c.appendChild(h("p", "p-sub", "Your amendment changed the votes of " + res.moved.map(function (m) { return m.country; }).join(", ") + "."));
    if (res.vetoed_by && res.vetoed_by.length) c.appendChild(h("p", "b-lesson", "Vetoed by " + res.vetoed_by.join(", ") + "."));
    var again = h("p", "p-row"), a = h("a", "p-btn", "Play again"); a.href = "/play"; again.appendChild(a); c.appendChild(again);
    $("p-lobby-card").hidden = true; $("p-vote-card").hidden = true; $("p-amend").hidden = true; $("p-amend-save").hidden = true;
    c.scrollIntoView({ block: "nearest" });
  }
  $("p-call").addEventListener("click", function () {
    var mine = document.querySelector('input[name="p-my"]:checked');
    if (!mine) { say("First choose how " + G.country + " votes."); return; }
    if (busy) return; busy = true; $("p-call").disabled = true;
    say("The vote is open. Delegations are voting…");
    api("vote", { my_vote: mine.value }).then(function (res) {
      G.result = res; G.stage = "voted"; step(3);
      showVotes(res, true, function () { renderResult(res); say((res.passed ? "Passed. " : "Failed. ") + res.summary); busy = false; });
    }).catch(function (e) { $("p-call").disabled = false; fail(e); });
  });

  // ---------- start ----------
  renderTags(); renderLog(); paintTokens();
  if (G.result) { step(3); showVotes(G.result, false, function () { renderResult(G.result); }); }
  else { chance(); step(G.lobbies.length ? 1 : 0); say("Read the clause. Then click a country on the map and talk to it: you have " + G.limit + " conversations."); }
  if (G.my_vote) { var r = document.querySelector('input[name="p-my"][value="' + G.my_vote + '"]'); if (r) r.checked = true; }
})();
