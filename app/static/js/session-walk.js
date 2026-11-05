/* The Session (D-101, phase 12): the Chief of Protocol's walkthrough. A short tour before the first turn, then a
   few steps as each stage unlocks something new (deals, advisers and compromise in Bloc meetings; the sign-up race,
   securing and the reserve in Sponsors; the golden rule at the Summit). A spotlight and the guide glide to each part
   of the table. The game page passes in what the walkthrough needs (`c`); it gets back start(view, done, set). */
(function () {
  "use strict";
  window.socSession = window.socSession || {};
  window.socSession.mods = window.socSession.mods || {};
  window.socSession.mods.walk = function (c) {
    var $ = c.$, h = c.h, A = c.A, G = c.G;
    function stageBox(el) {
      var sr = c.stage.getBoundingClientRect(), sc = sr.width / c.stage.offsetWidth, r = el.getBoundingClientRect();
      return { x: (r.left - sr.left) / sc, y: (r.top - sr.top) / sc, w: r.width / sc, h: r.height / sc };
    }
    function visible(sel) { var e = sel && document.querySelector(sel); return e && e.getClientRects().length ? e : null; }
    function lc(t) { t = String(t || "").replace(/\.$/, ""); return /^.[a-z]/.test(t) ? t.charAt(0).toLowerCase() + t.slice(1) : t; }
    function list(items) { var ul = h("ul", "s-guide-list"); items.forEach(function (x) { var li = h("li"); if (x[0]) li.appendChild(h("b", "", x[0])); li.appendChild(document.createTextNode(x[1])); ul.appendChild(li); }); return ul; }

    // pictures for the steps that look ahead
    function artTimeline(v) {
      var row = h("ol", "s-g-time"), quick = v.length === "quick";
      var stops = quick ? [["Working session", "one stage"], ["The Summit", "the votes"], ["Debrief", "your medals"]] :
        [["Stage 1", "Working group"], ["Stage 2", "Bloc meetings"], ["Stage 3", "Sponsors"], ["The Summit", "the votes"], ["Debrief", "your medals"]];
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
    function artPaths(v) {
      var g = h("div", "s-g-paths");
      [["mandate", "Mandate", "The hardliner"], ["consensus", "Consensus", "The broker"], ["architect", "Architect", "The drafter"], ["kingmaker", "Kingmaker", "The analyst"]].forEach(function (p, i) {
        var d = h("div", "s-g-path" + (v.path.code === p[0] ? " yours" : "")); d.style.animationDelay = (0.1 + i * 0.15) + "s";
        d.appendChild(h("i", "", "★")); d.appendChild(h("b", "", p[1])); d.appendChild(h("span", "", v.path.code === p[0] ? "Your aim" : p[2]));
        g.appendChild(d);
      });
      return g;
    }
    function artPitch() {
      var g = h("div", "s-g-pitch");
      [["Economic interest", "strong"], ["Regional solidarity", "strong"], ["Shared values", "weak"]].forEach(function (x, i) {
        var d = h("span", "s-arg " + x[1], x[0]); d.style.animationDelay = (0.2 + i * 0.2) + "s"; g.appendChild(d);
      });
      return g;
    }
    function artHaggle() {
      var g = h("div", "s-g-haggle");
      [["Their price", "4.0"], ["You hold out", "3.2"], ["They come down", "3.4"], ["Deal", "✓"]].forEach(function (x, i) {
        var d = h("div", ""); d.style.animationDelay = (0.2 + i * 0.25) + "s"; d.appendChild(h("b", "", x[1])); d.appendChild(h("span", "", x[0])); g.appendChild(d);
      });
      return g;
    }
    function artRooms() {
      var t = h("div", "s-g-rooms");
      [["African Group", "you", 4], ["Asia-Pacific Group", "rival", 3], ["Western Europe and Others", "undecided", 5]].forEach(function (r, i) {
        var d = h("div", "s-g-room " + r[1]); d.style.animationDelay = (0.2 + i * 0.25) + "s";
        d.appendChild(h("b", "", r[0])); var dots = h("span", "");
        for (var k = 0; k < 6; k++) dots.appendChild(h("i", k < r[2] ? r[1] : ""));
        d.appendChild(dots); t.appendChild(d);
      });
      var sheet = h("div", "s-g-sheet"); sheet.appendChild(h("b", "", "L.1")); sheet.appendChild(h("span", "", "3 of 3 sponsors")); t.appendChild(sheet);
      return t;
    }
    function artSummit() {
      var g = h("div", "s-g-summit");
      for (var i = 0; i < 10; i++) { var t = h("i", i < 6 ? "y" : i < 8 ? "a" : "n"); t.style.animationDelay = (0.3 + i * 0.12) + "s"; g.appendChild(t); }
      g.appendChild(h("span", "s-g-stamp", "Adopted"));
      return g;
    }

    function steps(v, set) {
      var sample = Object.keys(v.tokens).filter(function (k) { var t = v.tokens[k]; return !t.you && !t.rival; })[0];
      var sc = v.veto && v.veto.length, quick = v.length === "quick";
      var S = {};
      S.intro = [
        { face: "delighted", title: "Welcome, Ambassador",
          text: ["I am the Chief of Protocol. My job is to teach you how this committee works. I'll show you what you need now, and more as each stage opens.",
                 "Use Back to go over anything again, or Skip if you know the way."] },
        { at: ".b-titles", face: "calm", title: "You are " + v.you.name,
          text: ["You represent " + v.you.name + " in " + v.title + ". The committee decides by its voting rule: " + v.rule + ".",
                 sc ? "Five permanent members hold a veto: one no from any of them sinks a resolution. An abstention is not a veto." :
                      "Every delegation has one vote. Abstentions don't count towards the majority, so turning a no into an abstention helps you."] },
        { face: "thinking", title: "How the hour will run", art: artTimeline,
          text: [quick ? "A Quick session is one working session, then the Summit, then your debrief." :
                   "Three stages: the Working group drafts, Bloc meetings win regional groups, Sponsors table the draft. Then the Summit, then your debrief.",
                 "Each stage ends at a breakthrough or at its deadline. Make the breakthrough and you choose: move on now, and every turn left becomes Respect and Influence, or keep working. Miss it, and the committee moves on without you."] },
        { face: "delighted", title: "The President of the committee", art: artPresident,
          text: ["The President keeps the time. He opens each stage, announces breakthroughs and the news, and chairs the Summit. Your Foreign Minister sends telegrams from your capital; your advisers bring you intelligence.",
                 "At the start of each turn they report to you one at a time, so nothing gets lost."] },
        { at: "#c-instr", tab: "brief", face: "eyebrow", title: "Your secret instructions",
          text: [list([["Get in: ", "a clause that " + lc(v.mandate.must.label) + "."], ["Also get in: ", "a clause that " + lc(v.mandate.also.label) + "."],
                       ["Keep out: ", "anything that " + lc(v.mandate.red.label) + ". That is your red line."]]),
                 "Nobody else can see these orders. Your rivals have their own, roughly the opposite of yours."] },
        { face: "wry", title: "Four ways to win", art: artPaths,
          text: ["Every session is graded on all four paths, from no medal to gold. You're aiming for " + v.path.name + ", but a gold on any path is a gold."] },
        { at: ".s-meters", face: "calm", title: "Your standing",
          text: [list([["Influence ₳ ", "is your currency: pitches, deals and side events cost it."],
                       ["Respect ✦ ", "is your standing in the room. It adds actions at 5 and 8."],
                       ["Capital ✉ ", "is your government's confidence in you. Lose it all and you're recalled."],
                       ["Actions ⚑ ", "are your moves this turn. Your delegation grows as the session goes on."]])] },
        { at: "#c-country", tab: "dele", pick: sample, face: "thinking", title: "Pitching a delegation", art: artPitch,
          demo: function () { if (sample) setTimeout(function () { c.envoy(v.you.iso3, sample, false); }, 500); },
          text: ["Click a token to open its card. To win it over, pitch it: choose two arguments. Each delegation listens to some arguments more than others, from what matters to its country: its economy, its security, its neighbours, its values.",
                 "A pitch that matches moves it far; one that doesn't barely moves it. Read its file, or post an adviser to it, to learn what will land."] },
        { at: "#c-clauses", tab: "draft", face: "thinking", title: "The draft",
          text: ["The resolution as it stands. The dial on each clause is its chance of passing now. Propose clauses from cards, amend one commitment at a time, or strike a clause. The working group must agree to changes to anyone else's text.",
                 "Everything else opens from the bar on the right. When your actions are spent, end the turn."] }
      ];
      S.stage2 = [
        { at: ".s-tabs", face: "delighted", title: "Bloc meetings: new tools", art: artRooms,
          text: ["The regional groups now meet, one each turn. Open Blocs to see every meeting room: who leans your way, who leans to a rival, and how many you need. Attend the meeting in session to work all its members at once."] },
        { at: "#c-staff", tab: "staff", face: "wry", title: "Your staff",
          text: ["Your advisers can now be posted. Each studies one delegation or rival and reports at the start of each turn. Juniors can be wrong and say how sure they are; reports that prove right earn promotions. Hire more for Influence, up to " + v.costs.staff_max + "."] },
        { face: "eyebrow", title: "The deal table: haggling", art: artHaggle,
          text: ["You can now trade: funding, trade terms, backing for a candidacy or a clause, for a delegation's vote, sponsorship, Influence or intelligence.",
                 "They name a price. Hold out and they come down towards their walk-away point, but every round tests their patience, and a rival courting them may outbid you. An adviser posted to them can tell you how low they'll go."] },
        { face: "thinking", title: "Compromise with a rival",
          text: ["Rivals can become partners. Open a rival's card and negotiate: drop the commitment it can't accept, or let its wish into the text. If it agrees, it stops working against you, brings part of its support and co-sponsors a merged text.",
                 "Giving something up to win the vote is how the UN works. Your capital will tell you if you give up too much."] }
      ];
      S.stage3 = [
        { at: ".s-tabs", face: "eyebrow", title: "Sponsors: the race to table", art: artRooms,
          text: ["The sign-up sheets are out: yours beside each rival's. Ask delegations to sponsor or sign your draft. The first draft tabled, as L.1, is voted on first."] },
        { at: "#s-reserve", face: "wry", title: "Hold the line",
          text: [list([["Secure: ", "a delegation that trusts you signs a commitment; rivals pay double to move it."],
                       ["Hold in reserve: ", "spend an action now, and your team answers the first rival move against you before your next turn."]])] }
      ];
      S.summit = [
        { face: "eyebrow", title: "The first rule of the UN", art: artSummit,
          text: ["Don't say no to something just because it isn't exactly what you wanted. A resolution that carries some of your aims is better than none: half a loaf is better than no bread.",
                 "Each clause is voted on separately, then the whole text. Before each vote you can make a last offer, call in a favour, answer a rival, or deal with a floor amendment. Only your red line is a reason to vote no.", ""], last: true }
      ];
      var out = set === "intro" ? (quick ? S.intro.concat(S.stage2, S.stage3) : S.intro) : (S[set] || []);
      out = out.map(function (s) { return { face: s.face, title: s.title, at: s.at, tab: s.tab, pick: s.pick, art: s.art, demo: s.demo,
                                          text: s.text.filter(function (t) { return t !== ""; }) }; });
      if (out.length) out[out.length - 1].last = true;
      return out;
    }

    var W = { steps: null, i: 0, done: null, tab: null, face: null, set: null };
    function start(v, done, set) {
      set = set || "intro";
      if (!G) { if (done) done(); return; }
      c.hideAdvice();
      W.steps = steps(v, set).filter(function (s) { return !s.at || !s.tab || !$("t-" + s.tab).hidden; });
      if (!W.steps.length) { if (done) done(); return; }
      W.i = 0; W.done = done; W.set = set;
      W.tab = c.TABS.filter(function (t) { return $("t-" + t).getAttribute("aria-selected") === "true"; })[0] || "brief";
      var face = $("s-guide-face");
      if (!W.face) { face.textContent = ""; W.face = G.portrait("calm"); face.appendChild(W.face); }
      $("s-guide-off").checked = false;
      var dots = $("s-guide-dots"); dots.textContent = "";
      W.steps.forEach(function () { dots.appendChild(h("li")); });
      $("s-walk").hidden = false;
      document.body.classList.add("s-walking");
      A.play(set === "intro" ? "open" : "chime");
      show(0);
    }
    function show(i) {
      var s = W.steps[i]; W.i = i;
      if (s.tab) c.setTab(s.tab);
      if (s.pick) c.pick(s.pick);
      var guide = $("s-guide"), talk = guide.querySelector(".s-guide-talk");
      c.restart(talk, "s-talk-in");
      G.face(W.face, s.face); c.restart(W.face, "g-react");
      $("s-guide-step").textContent = (i + 1) + " of " + W.steps.length;
      $("s-guide-h").textContent = s.title;
      var b = $("s-guide-body"); b.textContent = "";
      if (s.art) b.appendChild(s.art(c.view()));
      s.text.forEach(function (t) { if (typeof t === "string") b.appendChild(h("p", "", t)); else b.appendChild(t); });
      $("s-guide-dots").querySelectorAll("li").forEach(function (d, k) { d.className = k < i ? "done" : k === i ? "on" : ""; });
      $("s-guide-back").disabled = i === 0;
      $("s-guide-next").textContent = s.last ? (W.set === "intro" ? "Begin the session" : "Carry on") : "Next";
      $("s-guide-skip").hidden = !!s.last;
      var spot = $("s-spot"), target = visible(s.at);
      var panes = target && target.closest(".s-panes");
      if (panes) {
        var sc0 = c.stage.getBoundingClientRect().width / c.stage.offsetWidth, pr = panes.getBoundingClientRect(), tr = target.getBoundingClientRect();
        if (tr.top < pr.top || tr.bottom > pr.bottom) panes.scrollTop += (tr.top - pr.top) / sc0 - 12;
      }
      requestAnimationFrame(function () {
        var gw = guide.offsetWidth, gh = guide.offsetHeight, left, top, W0 = c.stage.clientWidth, H0 = c.stage.clientHeight;
        if (target) {
          var r = stageBox(target), pad = 10;
          spot.classList.remove("off");
          spot.style.left = (r.x - pad) + "px"; spot.style.top = (r.y - pad) + "px";
          var bottom = panes ? stageBox(panes).y + stageBox(panes).h : H0;
          spot.style.width = (r.w + 2 * pad) + "px"; spot.style.height = Math.max(40, Math.min(r.h + 2 * pad, bottom - r.y + pad)) + "px";
          var cy = function (y) { return Math.min(Math.max(12, y), H0 - gh - 12); }, cx = function (x) { return Math.min(Math.max(12, x), W0 - gw - 12); };
          var tries = [[r.x - gw - 24, cy(r.y)], [r.x + r.w + 24, cy(r.y)], [cx(r.x + r.w / 2 - gw / 2), r.y + r.h + 20], [cx(r.x + r.w / 2 - gw / 2), r.y - gh - 20]];
          var fit = tries.filter(function (q) { return q[0] >= 12 && q[1] >= 12 && q[0] + gw <= W0 - 12 && q[1] + gh <= H0 - 12; })[0];
          if (fit) { left = fit[0]; top = fit[1]; }
          else if (r.w > W0 * 0.45) { left = W0 - gw - 40; top = H0 - gh - 80; }
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
    function end() {
      var wrap = $("s-walk"); if (wrap.hidden) return;
      if ($("s-guide-off").checked) { A.set("tips", false); c.syncSettings(); }
      wrap.hidden = true;
      document.body.classList.remove("s-walking");
      c.setTab(W.tab);
      var pn = document.querySelector(".s-panes"); if (pn) pn.scrollTop = 0;
      var v = c.view(); if (v && v.phase === "chapter") c.closePanel();
      var done = W.done; W.done = null;
      if (done) done(); else A.play("chime");
    }
    $("s-guide-next").addEventListener("click", function () { if (W.i >= W.steps.length - 1) end(); else show(W.i + 1); });
    $("s-guide-back").addEventListener("click", function () { if (W.i > 0) show(W.i - 1); });
    $("s-guide-skip").addEventListener("click", end);
    $("s-walk").addEventListener("keydown", function (e) {
      if (e.key === "ArrowRight") { e.preventDefault(); $("s-guide-next").click(); }
      else if (e.key === "ArrowLeft") { e.preventDefault(); $("s-guide-back").click(); }
      else if (e.key === "Tab") {
        var f = Array.prototype.filter.call($("s-guide").querySelectorAll("button, input"), function (x) { return !x.disabled && !x.hidden; });
        if (!f.length) return;
        if (e.shiftKey && document.activeElement === f[0]) { e.preventDefault(); f[f.length - 1].focus(); }
        else if (!e.shiftKey && document.activeElement === f[f.length - 1]) { e.preventDefault(); f[0].focus(); }
      }
    });
    return { start: start };
  };
})();
