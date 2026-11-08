/* The Session (D-101): your record and the scenario ladder (Ben, 8 Nov 2026).
   A guest's finished games are kept in this browser ("soc-session-record"); a signed-in student's record comes from
   the server. The same rules as store.profile: the first scenario is open, and gold (on any path) opens the next. */
(function () {
  "use strict";
  window.socSession = window.socSession || {};
  var KEY = "soc-session-record", GRADES = ["No medal", "Bronze", "Silver", "Gold"];
  function load() { try { return JSON.parse(localStorage.getItem(KEY) || "[]"); } catch (e) { return []; } }
  function keep(list) { try { localStorage.setItem(KEY, JSON.stringify(list.slice(-200))); } catch (e) { /* private window */ } }
  function best(res) { var p = (res && res.paths) || {}; return Object.keys(p).reduce(function (m, k) { return Math.max(m, p[k]); }, 0); }

  // a guest's finished game, recorded once (keyed by the game's seed and scenario)
  window.socSession.record = function (v, guest) {
    var st = guest && guest.state; if (!st || !v.result) return;
    var id = st.pack + ":" + st.seed, list = load();
    if (list.some(function (x) { return x.id === id; })) return;
    list.push({ id: id, pack: st.pack, iso3: st.iso3, country: v.you ? v.you.name : st.iso3, path: st.path, difficulty: st.difficulty,
                result: { paths: v.result.paths, passed: !!v.result.passed } });
    keep(list);
  };

  function profile(cards, records, open) {
    var bp = {}, un = {}, bi = {}, bpa = {}, names = {}, medals = { Bronze: 0, Silver: 0, Gold: 0 }, finished = 0, passed = 0;
    records.forEach(function (r) {
      if (!r.result) return;
      finished++; if (r.result.passed) passed++;
      var b = best(r.result); if (b) medals[GRADES[b]]++;
      bp[r.pack] = Math.max(bp[r.pack] || 0, b);
      if (r.difficulty === "standard" || r.difficulty === "hard") un[r.pack] = Math.max(un[r.pack] || 0, b);   // only these unlock bi[r.iso3] = Math.max(bi[r.iso3] || 0, b); names[r.iso3] = r.country || r.iso3;
      Object.keys(r.result.paths || {}).forEach(function (k) { bpa[k] = Math.max(bpa[k] || 0, r.result.paths[k]); });
    });
    var nextOpen = true, ladder = cards.map(function (c, i) {
      var locked = !(open || nextOpen);
      var out = { code: c.code, title: c.title, level_name: c.level_name, best: bp[c.code] || 0, medal: GRADES[bp[c.code] || 0], locked: locked,
                  needs: locked && i ? cards[i - 1].title : null };
      nextOpen = (un[c.code] || 0) >= 3 && !locked;
      return out;
    });
    return { games: records.length, finished: finished, passed: passed, medals: medals, scenarios: ladder,
             countries: Object.keys(bi).map(function (k) { return { iso3: k, name: names[k], best: bi[k], medal: GRADES[bi[k]] }; })
               .sort(function (a, b) { return b.best - a.best || (a.name < b.name ? -1 : 1); }),
             paths: null };
  }
  window.socSession.guestProfile = function (cards) { return profile(cards, load(), document.body.getAttribute("data-staff") === "yes"); };

  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; }
  function medal(m) { return el("span", "s-medal m-" + m.toLowerCase().replace(" ", "-"), m); }

  document.addEventListener("DOMContentLoaded", function () {
    var page = document.body.getAttribute("data-page");
    // the setup screen: a guest's ladder locks scenarios in this browser (a signed-in student's are locked by the server)
    if (page === "new" && document.body.getAttribute("data-signed-in") !== "yes" && document.body.getAttribute("data-staff") !== "yes") {
      var cards = Array.prototype.map.call(document.querySelectorAll('[data-pick="pack"]'), function (b) { return { code: b.getAttribute("data-value"), title: b.getAttribute("data-label"), level_name: "" }; });
      var p = profile(cards, load(), false);
      p.scenarios.forEach(function (s) {
        if (!s.locked) return;
        var b = document.querySelector('[data-pick="pack"][data-value="' + s.code + '"]');
        b.disabled = true; b.classList.add("locked");
        b.querySelector("h3").insertAdjacentElement("afterend", el("span", "s-lock", "Locked: win gold on Standard or Hard in " + s.needs + " to open it"));
      });
    }
    if (page !== "profile") return;
    var data = JSON.parse(document.getElementById("p-data").textContent);
    var prof = data.profile || profile(data.cards, load(), document.body.getAttribute("data-staff") === "yes");
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
    var pathList = prof.paths || [];
    if (!prof.paths) {                                               // a guest: work out each path's best here
      var bpa = {};
      load().forEach(function (r) { Object.keys((r.result || {}).paths || {}).forEach(function (k) { bpa[k] = Math.max(bpa[k] || 0, r.result.paths[k]); }); });
      pathList = Object.keys(data.paths || {}).filter(function (k) { return k in bpa; }).map(function (k) { return { name: data.paths[k].name, medal: GRADES[bpa[k]] }; });
    }
    if (!pathList.length) paths.appendChild(el("li", "s-sub", "Finish a session to see your best on each path."));
    pathList.forEach(function (x) { var li = el("li"); li.appendChild(el("b", "", x.name)); li.appendChild(medal(x.medal)); paths.appendChild(li); });
    var cs = document.getElementById("p-countries");
    if (!prof.countries.length) cs.appendChild(el("li", "s-sub", "No countries yet."));
    prof.countries.forEach(function (x) { var li = el("li"); li.appendChild(el("b", "", x.name)); li.appendChild(medal(x.medal)); cs.appendChild(li); });
  });
})();
