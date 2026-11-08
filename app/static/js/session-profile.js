/* The Session (D-101): your record, the scenario ladder, your ambassador, insignia and approaches (Ben, 8 Nov 2026).
   A guest's finished games are kept in this browser ("soc-session-record"); a signed-in student's record comes from
   the server. These rules match store.profile: the first scenario is open, and gold (on any path) on Standard or Hard
   opens the next. Your ambassador's look is kept in this browser ("soc-session-avatar") for everyone. */
(function () {
  "use strict";
  window.socSession = window.socSession || {};
  var KEY = "soc-session-record", AKEY = "soc-session-avatar", GRADES = ["No medal", "Bronze", "Silver", "Gold"];
  var STD = { standard: true, hard: true };
  function load() { try { return JSON.parse(localStorage.getItem(KEY) || "[]"); } catch (e) { return []; } }
  function keep(list) { try { localStorage.setItem(KEY, JSON.stringify(list.slice(-200))); } catch (e) { /* private window */ } }
  function best(res) { var p = (res && res.paths) || {}; return Object.keys(p).reduce(function (m, k) { return Math.max(m, p[k]); }, 0); }

  // ---------- your ambassador's look (the same respectful options as delegates; no costume) ----------
  var LOOK = { k: ["Skin tone", 5], h: ["Hair", 5], w: ["Hair colour", 3], gl: ["Glasses", 2], t: ["Neckwear", 4] };
  var LOOK_NAMES = { h: ["Short", "Long", "Cropped", "Curls", "Bun"], w: ["Black", "Brown", "Grey"], gl: ["None", "Glasses"],
                     t: ["Maroon tie", "Blue tie", "Green tie", "Scarf"] };
  function look() { try { return JSON.parse(localStorage.getItem(AKEY) || "null"); } catch (e) { return null; } }
  function classes(a) { return "dl-k" + a.k + " dl-h" + a.h + " dl-w" + a.w + (a.gl ? " dl-gl" : "") + " dl-t" + a.t; }
  window.socSession.avatar = function () { var a = look(); return a ? classes(a) : null; };

  // a guest's finished game, recorded once (keyed by the game's seed and scenario)
  window.socSession.record = function (v, guest) {
    var st = guest && guest.state; if (!st || !v.result) return;
    var id = st.pack + ":" + st.seed, list = load();
    if (list.some(function (x) { return x.id === id; })) return;
    var r = v.result;
    list.push({ id: id, pack: st.pack, iso3: st.iso3, country: v.you ? v.you.name : st.iso3, path: st.path, difficulty: st.difficulty,
                result: { paths: r.paths, passed: !!r.passed, kept_promises: r.kept_promises || 0, broken_promises: r.broken_promises || 0,
                          golden: r.golden || null } });
    keep(list);
  };

  function profile(cards, records, open) {
    var bp = {}, un = {}, bi = {}, bpa = {}, names = {}, medals = { Bronze: 0, Silver: 0, Gold: 0 }, finished = 0, passed = 0;
    var types = {}; cards.forEach(function (c) { types[c.code] = c.type || ""; });
    var fin = records.filter(function (r) { return r.result; });
    fin.forEach(function (r) {
      finished++; if (r.result.passed) passed++;
      var b = best(r.result); if (b) medals[GRADES[b]]++;
      bp[r.pack] = Math.max(bp[r.pack] || 0, b);
      if (STD[r.difficulty]) un[r.pack] = Math.max(un[r.pack] || 0, b);          // only Standard or Hard unlocks
      bi[r.iso3] = Math.max(bi[r.iso3] || 0, b); names[r.iso3] = r.country || r.iso3;
      Object.keys(r.result.paths || {}).forEach(function (k) { bpa[k] = Math.max(bpa[k] || 0, r.result.paths[k]); });
    });
    var nextOpen = true, ladder = cards.map(function (c, i) {
      var locked = !(open || nextOpen);
      var out = { code: c.code, title: c.title, best: bp[c.code] || 0, medal: GRADES[bp[c.code] || 0], locked: locked,
                  needs: locked && i ? cards[i - 1].title : null };
      nextOpen = (un[c.code] || 0) >= 3 && !locked;
      return out;
    });
    var golds = Object.keys(un).filter(function (k) { return un[k] >= 3; });
    var have = { silver: Object.keys(un).some(function (k) { return un[k] >= 2; }), gold: golds.length > 0, three_golds: golds.length >= 3 };
    return { games: records.length, finished: finished, passed: passed, medals: medals, scenarios: ladder, have: have, open: open,
             bestPath: bpa,
             earned: {
               first_pass: fin.some(function (r) { return r.result.passed; }),
               gold_std: golds.length > 0,
               hard_won: fin.some(function (r) { return r.difficulty === "hard" && best(r.result) >= 3; }),
               council: fin.some(function (r) { return r.result.passed && types[r.pack] === "Security Council"; }),
               honour: fin.some(function (r) { return (r.result.kept_promises || 0) >= 2 && !r.result.broken_promises; }),
               half_loaf: fin.some(function (r) { return r.result.golden === "kept"; }),
               all_paths: ["mandate", "consensus", "architect", "kingmaker", "ambassador"].every(function (k) { return (bpa[k] || 0) >= 3; }),
               globetrotter: Object.keys(bi).length >= 5 },
             countries: Object.keys(bi).map(function (k) { return { iso3: k, name: names[k], best: bi[k], medal: GRADES[bi[k]] }; })
               .sort(function (a, b) { return b.best - a.best || (a.name < b.name ? -1 : 1); }) };
  }

  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; }
  function medal(m) { return el("span", "s-medal m-" + m.toLowerCase().replace(" ", "-"), m); }
  function staff() { return document.body.getAttribute("data-staff") === "yes"; }

  document.addEventListener("DOMContentLoaded", function () {
    var page = document.body.getAttribute("data-page");
    // the setup screen: a guest's ladder and approaches lock in this browser (a signed-in student's are locked by the server)
    if (page === "new" && document.body.getAttribute("data-signed-in") !== "yes" && !staff()) {
      var cards = Array.prototype.map.call(document.querySelectorAll('[data-pick="pack"]'), function (b) { return { code: b.getAttribute("data-value"), title: b.getAttribute("data-label") }; });
      var p = profile(cards, load(), false);
      p.scenarios.forEach(function (s) {
        if (!s.locked) return;
        var b = document.querySelector('[data-pick="pack"][data-value="' + s.code + '"]');
        b.disabled = true; b.classList.add("locked");
        b.querySelector("h3").insertAdjacentElement("afterend", el("span", "s-lock", "Locked: win gold on Standard or Hard in " + s.needs + " to open it"));
      });
      var UNLOCK = { linguist: "silver", veteran: "gold", envoy: "three_golds" };
      document.querySelectorAll('[data-pick="approach"]').forEach(function (b) {
        var need = UNLOCK[b.getAttribute("data-value")]; if (!need || p.have[need]) return;
        b.disabled = true; b.classList.add("locked");
        b.querySelector("h3").insertAdjacentElement("afterend", el("span", "s-lock", "Locked: " + b.getAttribute("data-needs")));
      });
    }
    if (page !== "profile") return;
    var data = JSON.parse(document.getElementById("p-data").textContent);
    var server = data.profile, guest = profile(data.cards, load(), staff());
    var prof = server || guest;

    // your ambassador: the builder and the preview
    var G = window.socSession.guide, face = document.getElementById("p-face"), opts = document.getElementById("p-avatar-opts");
    var a = look() || { k: 1, h: 0, w: 1, gl: 0, t: 0 };
    function preview() { face.textContent = ""; if (G) face.appendChild(G.portrait("delighted", "delegate you " + classes(a))); }
    Object.keys(LOOK).forEach(function (key) {
      var row = el("div", "s-row"); row.appendChild(el("span", "", LOOK[key][0]));
      for (var i = 0; i < LOOK[key][1]; i++) (function (i) {
        var b = el("button", "", LOOK_NAMES[key] ? LOOK_NAMES[key][i] : String(i + 1)); b.type = "button";
        b.setAttribute("aria-label", LOOK[key][0] + " " + (LOOK_NAMES[key] ? LOOK_NAMES[key][i] : "option " + (i + 1)));
        b.setAttribute("aria-pressed", String(a[key] === i));
        b.addEventListener("click", function () {
          a[key] = i; try { localStorage.setItem(AKEY, JSON.stringify(a)); } catch (e) { /* private window */ }
          row.querySelectorAll("button").forEach(function (x, j) { x.setAttribute("aria-pressed", String(j === i)); }); preview();
        });
        row.appendChild(b);
      })(i);
      opts.appendChild(row);
    });
    preview();

    // insignia (from the server for a signed-in student; worked out here for a guest)
    var ins = document.getElementById("p-insignia");
    var earned = server ? {} : guest.earned;
    if (server) server.insignia.forEach(function (x) { earned[x.code] = x.earned; });
    Object.keys(data.insignia).forEach(function (code) {
      var x = data.insignia[code], li = el("li", earned[code] ? "earned" : "");
      li.appendChild(el("b", "", x.name)); li.appendChild(el("span", "", x.what)); li.appendChild(el("span", "s-small", earned[code] ? "Earned" : "Not yet"));
      ins.appendChild(li);
    });

    var stats = document.getElementById("p-stats");
    [["Sessions started", prof.games], ["Finished", prof.finished], ["Resolutions passed", prof.passed],
     ["Gold", prof.medals.Gold], ["Silver", prof.medals.Silver], ["Bronze", prof.medals.Bronze]].forEach(function (x) {
      stats.appendChild(el("dt", "", x[0])); stats.appendChild(el("dd", "", String(x[1])));
    });
    var lad = document.getElementById("p-ladder");
    prof.scenarios.forEach(function (s) {
      var li = el("li", s.locked ? "locked" : s.best >= 3 ? "gold" : "");
      li.appendChild(el("b", "", s.title));
      li.appendChild(s.locked ? el("span", "s-lock", "Locked: win gold on Standard or Hard in " + s.needs) : medal(s.medal));
      lad.appendChild(li);
    });
    var paths = document.getElementById("p-paths");
    var pathList = server ? server.paths : Object.keys(data.paths || {}).map(function (k) { return { name: data.paths[k].name, medal: GRADES[guest.bestPath[k] || 0] }; });
    pathList.forEach(function (x) { var li = el("li"); li.appendChild(el("b", "", x.name)); li.appendChild(medal(x.medal)); paths.appendChild(li); });
    var ap = document.getElementById("p-approaches");
    var apList = server ? server.approaches : Object.keys(data.approaches).map(function (code) {
      var x = data.approaches[code]; return { name: x.name, what: x.what, needs: x.needs, locked: !(guest.open || !x.unlock || guest.have[x.unlock]) };
    });
    apList.forEach(function (x) {
      var li = el("li", x.locked ? "locked" : ""); var t = el("div"); t.appendChild(el("b", "", x.name)); t.appendChild(el("span", "s-small", " " + x.what)); li.appendChild(t);
      li.appendChild(x.locked ? el("span", "s-lock", "Locked: " + x.needs) : el("span", "s-medal m-gold", "Open"));
      ap.appendChild(li);
    });
    var cs = document.getElementById("p-countries");
    if (!prof.countries.length) cs.appendChild(el("li", "s-sub", "No countries yet."));
    prof.countries.forEach(function (x) { var li = el("li"); li.appendChild(el("b", "", x.name)); li.appendChild(medal(x.medal)); cs.appendChild(li); });
  });
})();
