/* The Session (D-102): the Summit as the UN runs it. Position statements -> the draft read in full -> a caucus ->
   amendments, one at a time, each debated and then voted -> the final draft read with its changes -> the final vote.
   The game page passes in what this needs (`c`); the engine is campaign/summit.py. */
(function () {
  "use strict";
  window.socSession = window.socSession || {};
  window.socSession.mods = window.socSession.mods || {};
  window.socSession.mods.summit = function (c) {
    var $ = c.$, h = c.h, A = c.A, btn = c.btn;
    var STEP_NAMES = { statements: "Statements", reading: "The draft", caucus: "Caucus", amendments: "Amendments", final_reading: "Final text", final: "The vote" };
    var STANCE = { firm: ["Firm", "Rally the delegations who already share your aims."],
                   open: ["Open", "Listen first and acknowledge the other side. The room respects it: +1 Standing."],
                   bridge: ["Bridge", "Speak to the undecided, with something for each of them."] };
    var KIND = { strike: "Strike", remove: "Strike part", add: "Add", soften: "Soften", strengthen: "Strengthen" };
    var timer = null, shown = null, seq = null, G = c.G;
    function stop() { if (timer) { clearTimeout(timer); timer = null; } }
    function on() { return A.motionOn ? A.motionOn() : true; }

    // ---------- pacing (Ben, 10 Nov): the Summit breathes like a chamber ----------
    // A step is a list of beats: each reveals something, then waits. `show(next, s)` reveals it and calls `next` when
    // its pause is over; `all()` reveals it at once (skip, or a re-render of the same step). Nothing starts until the
    // panel is on screen. Skip (a button, or Space through session-keys.js) shows everything left. Motion off: the
    // same beats in order, with shorter pauses and no typing.
    function cancelSeq() { if (seq) { seq.dead = true; if (seq.tm) clearTimeout(seq.tm); if (seq.spk) seq.spk.finish(); seq = null; } }
    function ready() { var card = $("s-chapter-card"); return document.body.classList.contains("s-panel-open") && (!card || card.hidden); }
    function run(box, beats, fin, fresh) {
      if (!fresh || !beats.length) { beats.forEach(function (b) { b.all(); }); fin(); return; }
      var skip = btn("Skip", "s-btn ghost small s-skip", function () { finish(); });
      skip.setAttribute("aria-label", "Skip the pause (Space)");
      box.insertBefore(skip, box.firstChild);
      var s = seq = { dead: false, tm: null, spk: null, i: 0 };
      s.later = function (fn, ms) { s.tm = setTimeout(fn, ms); };
      function over() { s.dead = true; if (s.tm) clearTimeout(s.tm); if (skip.parentNode) skip.parentNode.removeChild(skip); if (seq === s) seq = null; }
      function finish() { if (s.dead) return; if (s.spk) s.spk.finish(); over(); beats.forEach(function (b) { b.all(); }); box.classList.add("s-skipped"); fin(); }
      function step() {
        if (s.dead) return;
        if (s.i >= beats.length) { over(); fin(); return; }
        beats[s.i++].show(step, s);
      }
      function begin() { if (s.dead) return; if (!ready()) { s.tm = setTimeout(begin, 150); return; } step(); }
      begin();
    }
    function wait(el, ms, sound) {                                // reveal an element, then pause
      el.hidden = true;
      return { all: function () { el.hidden = false; },
               show: function (next, s) { el.hidden = false; if (sound) A.play(sound); s.later(next, on() ? ms : Math.round(ms * 0.35)); } };
    }
    function pres(box, text, pause) {                              // the President speaks a line
      var d = h("div", "s-chief-says s-chief-note s-pres-line"), f = h("div", "s-chief-face"), p = h("p"), svg = null;
      if (G) { svg = G.portrait("eyebrow", "president"); f.appendChild(svg); }
      d.appendChild(f); d.appendChild(p); d.hidden = true; box.appendChild(d);
      return { all: function () { d.hidden = false; if (!p.textContent) p.textContent = text; },
               show: function (next, s) {
                 d.hidden = false;
                 var ms = on() ? pause : Math.round(pause * 0.4);
                 if (G && G.speak) s.spk = G.speak(svg, p, text, function () { if (!s.dead) s.later(next, ms); }, { pitch: G.voiceOf("president") });
                 else { p.textContent = text; s.later(next, ms); }
               } };
    }
    function announce(box, out, beats) {                           // the result of the vote that was just taken
      if (!out || !out.votes || !out.amendment || !Object.keys(out.votes).length) return;
      var n = { yes: 0, no: 0, abstain: 0 };
      Object.keys(out.votes).forEach(function (k) { n[out.votes[k]] = (n[out.votes[k]] || 0) + 1; });
      beats.push(pres(box, "The amendment is " + (out.passed ? "adopted" : "rejected") + ": " + n.yes + " in favour, " + n.no + " against" +
        (n.abstain ? ", " + n.abstain + " abstaining" : "") + ".", 900));
    }

    function strip(S, box) {                                    // where we are in the procedure
      var ol = h("ol", "s-proc-strip"); ol.setAttribute("aria-label", "The Summit's order of business");
      var at = S.steps.indexOf(S.step === "statement" ? "final" : S.step);
      S.steps.forEach(function (k, i) { var li = h("li", i < at ? "done" : i === at ? "now" : "", STEP_NAMES[k]); if (i === at) li.setAttribute("aria-current", "step"); ol.appendChild(li); });
      box.appendChild(ol);
    }
    function clauseLi(cl, opts) {
      var li = h("li", "s-sclause" + (cl.mine ? " mine" : ""));
      li.appendChild(h("b", "s-sn", String(cl.n)));
      var body = h("div");
      body.appendChild(h("p", "s-stext", cl.text));
      body.appendChild(h("p", "s-small", cl.sponsor + " · commits countries to: " + cl.labels.join("; ").toLowerCase()));
      if (opts && opts.chance && cl.chance !== null && cl.chance !== undefined) body.appendChild(h("p", "s-small", "As things stand: about " + Math.round(cl.chance * 100) + "% likely to carry"));
      (cl.changes || []).forEach(function (ch) { body.appendChild(h("p", "s-tracked", (ch.how === "friendly" ? "Accepted as friendly: " : "Amended: ") + ch.text + " (" + ch.by + ")")); });
      if (cl.promised_to && cl.promised_to.length) body.appendChild(h("p", "s-small s-warnline", "You promised " + cl.promised_to.join(", ") + " to back this clause."));
      li.appendChild(body); return li;
    }
    function draftList(S, chance) {
      var ol = h("ol", "s-sdraft");
      (S.draft || []).forEach(function (cl) { ol.appendChild(clauseLi(cl, { chance: chance })); });
      (S.struck || []).forEach(function (x) { var li = h("li", "s-sclause struck"); li.appendChild(h("p", "s-stext", x.text + " (" + x.by + ")")); ol.appendChild(li); });
      return ol;
    }

    // ink on parchment: as the President reads, each clause is written on; struck text is crossed out in red ink and
    // the changes appear as notes in the margin
    function ink(box, step) {
      var FX = window.socSession.fx; if (!FX) return 0;
      if (step === "reading" || step === "final_reading") {
        var t = 0.15;
        box.querySelectorAll(".s-sdraft > li").forEach(function (li) {
          var p = li.querySelector(".s-stext"); if (p) { FX.ink(p, t); t += 0.32; }
          li.querySelectorAll(".s-tracked").forEach(function (n) { FX.ink(n, t); t += 0.22; });
          if (li.classList.contains("struck") && FX.on()) { li.style.setProperty("--fx-strike", t + "s"); li.classList.add("fx-strike"); t += 0.3; }
        });
        return t;
      }
      return 0;
    }
    function readBeats(box, list, step) {                         // the clauses are written on, then the President moves on
      if (!on()) {                                                // plain text, clause by clause
        return Array.prototype.map.call(list.children, function (li) { return wait(li, 520, "paper"); });
      }
      list.hidden = true;
      return [{ all: function () { list.hidden = false; },
               show: function (next, s) { list.hidden = false; var t = ink(box, step); s.later(next, Math.round(t * 1000) + 900); } }];
    }
    function render(v, out) {
      var S = v.summit; if (!S) return;
      var box = $("c-summit"); box.textContent = "";
      var key = S.step + ":" + (S.cur ? S.cur.id + ":" + S.cur.stage : "");
      var fresh = key !== shown, beats = [], fin = function () {};
      cancelSeq();
      box.classList.remove("s-skipped");
      if (fresh) {
        stop();
        var panes = document.querySelector("#s-rail .s-panes");            // each step of the procedure opens at its top
        if (panes && shown !== null) panes.scrollTop = 0;
      }
      if (v.phase === "done") {
        box.appendChild(h("h2", "", "The session is over"));
        var fin = S.statement && S.statement.adopted ? "The resolution failed, but a Presidential Statement was agreed." :
          S.final && S.final.passed ? "The resolution was adopted. " + S.final.summary : "The resolution failed. " + (S.final ? S.final.summary : "");
        box.appendChild(h("p", "", fin));
        box.appendChild(btn("See your results", "s-btn", function () { c.result(v); }));
        shown = key; return;
      }
      strip(S, box);
      if (S.step === "statements") {
        box.appendChild(h("h2", "", "Position statements"));
        box.appendChild(h("p", "", "The President opens the Summit. Delegations state their positions on the draft."));
        var ul = h("ul", "s-statements");
        S.statements.forEach(function (st) {
          var li = h("li", st.view > 0 ? "for" : st.view < 0 ? "against" : "");
          li.appendChild(h("b", "", st.name)); li.appendChild(h("span", "", "“" + st.text + "”")); ul.appendChild(li);
          beats.push(wait(li, 1100, "paper"));
        });
        box.appendChild(ul);
        var turn = h("p", "s-small", "Your turn. How will " + v.you.name + " speak?"); box.appendChild(turn);
        var ta = h("textarea"); ta.className = "s-speech"; ta.setAttribute("aria-label", "Your statement, if you want to write it (not saved or marked)");
        ta.placeholder = "Your words, if you want to write them. For your own practice: not saved, not marked."; box.appendChild(ta);
        var stc = h("div", "s-stances");
        Object.keys(STANCE).forEach(function (k) {
          var b = h("button", "s-stance"); b.type = "button";
          b.appendChild(h("b", "", STANCE[k][0])); b.appendChild(h("span", "", STANCE[k][1]));
          b.addEventListener("click", function () { c.move({ do: "speech", stance: k }); });
          stc.appendChild(b);
        });
        box.appendChild(stc);
        var rest = [turn, ta, stc]; rest.forEach(function (e) { e.hidden = true; });
        fin = function () { rest.forEach(function (e) { e.hidden = false; }); };
      } else if (S.step === "reading") {
        box.appendChild(h("h2", "", "The draft, read in full"));
        box.appendChild(h("p", "", "The President reads the draft resolution, clause by clause, with its sponsors."));
        var rl0 = draftList(S, true); box.appendChild(rl0);
        var go0 = btn("The President moves to the caucus", "s-btn", function () { c.move({ do: "proceed" }); A.play("gavel"); });
        box.appendChild(go0); go0.hidden = true;
        beats = readBeats(box, rl0, "reading");
        fin = function () { go0.hidden = false; };
      } else if (S.step === "caucus") {
        box.appendChild(h("h2", "", "Caucus"));
        box.appendChild(h("p", "", "Before the amendments, move for a caucus. Rivals will use it too."));
        var mod = h("div", "s-caucus-opt"); mod.appendChild(h("h3", "", "Moderated caucus"));
        mod.appendChild(h("p", "s-small", "Choose the topic, and speak in the speakers' list: delegations who share your view on it move your way."));
        var sel = h("select", "wide"); sel.setAttribute("aria-label", "Topic for the moderated caucus");
        S.topics.forEach(function (t) { var o = h("option", "", t.label + (t.mine > 0 ? " (your aim)" : t.mine < 0 ? " (your red line)" : "")); o.value = t.code; sel.appendChild(o); });
        mod.appendChild(sel);
        mod.appendChild(btn("Move for a moderated caucus", "s-btn small", function () { c.move({ do: "caucus", kind: "moderated", tag: sel.value }); }));
        box.appendChild(mod);
        var un = h("div", "s-caucus-opt"); un.appendChild(h("h3", "", "Unmoderated caucus"));
        un.appendChild(h("p", "s-small", "Leave your seat: a quiet word with up to two delegations on the floor."));
        var pick = h("div", "s-floor"), chosen = [];
        S.floor.forEach(function (f) {
          var b = h("button", "s-chip", f.name + (f.lean ? " · " + (f.word ? f.word.toLowerCase() : f.lean === "yes" ? "for" : f.lean === "no" ? "against" : "undecided") : "")); b.type = "button";
          b.setAttribute("aria-pressed", "false");
          b.addEventListener("click", function () {
            var i = chosen.indexOf(f.iso3);
            if (i >= 0) chosen.splice(i, 1); else { chosen.push(f.iso3); if (chosen.length > 2) chosen.shift(); }
            pick.querySelectorAll(".s-chip").forEach(function (x, k) { x.setAttribute("aria-pressed", String(chosen.indexOf(S.floor[k].iso3) >= 0)); });
            A.play("tick");
          });
          pick.appendChild(b);
        });
        un.appendChild(pick);
        un.appendChild(btn("Move for an unmoderated caucus", "s-btn small", function () {
          if (!chosen.length) { c.say("Choose one or two delegations first."); return; }
          c.move({ do: "caucus", kind: "unmoderated", iso3: chosen.slice() });
        }));
        box.appendChild(un);
      } else if (S.step === "amendments") {
        if (S.caucus && out && out.caucus) {
          var cu = h("div", "s-caucus-result"); cu.appendChild(h("b", "", S.caucus.kind === "moderated" ? "The speakers' list" : "On the floor"));
          S.caucus.speakers.forEach(function (sp) { var cp = h("p", "s-small", (sp.name === v.you.name ? "" : sp.name + " ") + sp.text); cu.appendChild(cp); beats.push(wait(cp, 1400, "paper")); });
          box.appendChild(cu);
        }
        announce(box, out, beats);
        var cur = S.cur, gated = [];
        if (cur && cur.stage === "debate") {
          beats.push(pres(box, (cur.by_you ? "Ambassador, you have moved an amendment to clause " : "The delegation of " + cur.by + " moves an amendment to clause ") + cur.clause.n + ".", 700));
        }
        if (cur) {
          var hd = h("h2", "", "Amendment"); hd.appendChild(h("span", "s-count", (S.done.length + 1) + " of " + (S.done.length + 1 + S.queue.length))); box.appendChild(hd);
          var card = h("div", "s-amend-card" + (cur.threat ? " threat" : ""));
          card.appendChild(h("p", "s-eyebrow", (cur.by_you ? "Your amendment" : "Moved by " + cur.by) + " · " + KIND[cur.kind] + (cur.threat ? " · the ultimatum you refused" : "")));
          card.appendChild(h("p", "s-amend-text", cur.text));
          var ol = h("ol", "s-sdraft one"); ol.appendChild(clauseLi(cur.clause)); card.appendChild(ol);
          if (!cur.by_you) card.appendChild(h("p", "s-small", cur.side > 0 ? "It would help your instructions." : cur.side < 0 ? "It would cut against your instructions." : "Your instructions don't turn on it."));
          box.appendChild(card);
          if (cur.stage === "debate") {
            card.hidden = true;
            beats.push({ all: function () { card.hidden = false; },
                         show: function (next, s) { card.hidden = false; A.play("paper"); var FX = window.socSession.fx; if (FX) FX.ink(card.querySelector(".s-amend-text"), 0.1); s.later(next, on() ? 1200 : 600); } });
            var dq = h("p", "s-small", "The debate: " + cur.by + " speaks for it. What will you do?"); box.appendChild(dq);
            var dec = h("div", "s-decide");
            function opt(k, label, ok) { dec.appendChild(btn(label, "s-chip", function () { c.move({ do: "debate", choice: k }); A.play("paper"); }, !ok)); }
            opt("for", "Speak for it", true);
            opt("against", "Speak against it", true);
            if (!cur.by_you) opt("point_of_order", "Point of order", S.po);
            if (cur.your_clause && !cur.by_you) opt("reply", "Right of reply", S.can_reply);
            if (cur.your_clause && !cur.by_you && cur.side >= 0) opt("accept", "Accept it as friendly", true);
            opt("silent", "Stay silent", true);
            box.appendChild(dec);
            gated = [dq, dec]; gated.forEach(function (e) { e.hidden = true; });
            fin = function () { gated.forEach(function (e) { e.hidden = false; }); };
          } else {
            var deb = S.debate || { speeches: [] }, sp = h("ul", "s-speakers");
            deb.speeches.forEach(function (x) {
              var li = h("li", "s-" + x.side, x.name + (x.side === "reply" ? " exercised a right of reply" : " spoke " + x.side + " it"));
              sp.appendChild(li); beats.push(wait(li, 1200, "paper"));
            });
            box.appendChild(sp);
            if (!deb.speeches.length) beats.push(pres(box, "No delegation asks for the floor.", 800));
            if (cur.advice) { var lg = h("p", "s-legal", "Your legal adviser (" + cur.advice.sure + "): it would " + (cur.advice.passes ? "pass." : "fail.")); box.appendChild(lg); beats.push(wait(lg, 900)); }
            beats.push(pres(box, "The debate is closed. The amendment is put to the vote.", 500));
            var vq = h("p", "s-small", "The vote on the amendment. Cast " + v.you.name + "'s vote."); box.appendChild(vq); gated.push(vq);
            var extra = null, ex = h("div", "s-decide");
            function exOpt(k, label, ok) {
              var b = btn(label, "s-chip", function () { extra = extra === k ? null : k; ex.querySelectorAll(".s-chip").forEach(function (x) { x.setAttribute("aria-pressed", String(x === b && extra === k)); }); A.play("tick"); }, !ok);
              b.setAttribute("aria-pressed", "false"); ex.appendChild(b);
            }
            exOpt("offer", "With a last offer (" + S.offer_cost + " Influence)", S.influence >= S.offer_cost);
            exOpt("favour", "Call in a favour (" + S.favours.length + ")", S.favours.length > 0);
            box.appendChild(ex); gated.push(ex);
            var vt = h("div", "s-votes");
            [["yes", "Yes"], ["abstain", "Abstain"], ["no", "No"]].forEach(function (x) {
              vt.appendChild(btn(x[1], "s-btn v-" + x[0], function () { stop(); c.move({ do: "amend_vote", vote: x[0], extra: extra }); }));
            });
            box.appendChild(vt); gated.push(vt);
            gated.forEach(function (e) { e.hidden = true; });
            fin = function () {                                  // the decision, and only now its 20 seconds
              gated.forEach(function (e) { e.hidden = false; });
              if (A.settings().timer && fresh) {
                var bar = h("div", "s-timer"); bar.appendChild(h("i")); bar.style.setProperty("--secs", "20s"); box.appendChild(bar);
                requestAnimationFrame(function () { bar.classList.add("run"); });
                timer = setTimeout(function () { c.move({ do: "amend_vote", vote: cur.side > 0 ? "yes" : cur.side < 0 ? "no" : "abstain" }); }, 20000);
              }
            };
          }
        }
        if (S.options && S.options.length) {
          var my = h("details", "s-myamend"); my.appendChild(h("summary", "", "Table an amendment of your own (" + S.mine_left + " left)"));
          S.options.forEach(function (o) {
            my.appendChild(btn(KIND[o.kind] + ": " + o.text, "s-btn ghost small", function () { c.move({ do: "table", kind: o.kind, clause: o.clause, tag: o.tag }); }));
          });
          box.appendChild(my);
        }
        if (S.queue && S.queue.length) {
          var q = h("details", "s-queue"); q.appendChild(h("summary", "", S.queue.length + " more amendment" + (S.queue.length === 1 ? "" : "s") + " to come"));
          S.queue.forEach(function (x) { q.appendChild(h("p", "s-small", x.by + ": " + x.text)); });
          box.appendChild(q);
        }
      } else if (S.step === "final_reading") {
        box.appendChild(h("h2", "", "The final text"));
        box.appendChild(h("p", "", "The President reads the resolution as amended. Every change is marked."));
        announce(box, out, beats);
        var rl1 = draftList(S, false); box.appendChild(rl1);
        var go1 = btn("The President calls the final vote", "s-btn", function () { c.move({ do: "proceed" }); A.play("gavel"); });
        box.appendChild(go1); go1.hidden = true;
        beats = beats.concat(readBeats(box, rl1, "final_reading"));
        fin = function () { go1.hidden = false; };
      } else if (S.step === "final") {
        box.appendChild(h("h2", "", "The final vote"));
        box.appendChild(h("p", "", S.kept.length ? "The resolution, as amended, commits countries to: " + S.kept.join("; ").toLowerCase() + "." :
                                                     "No clause is left, so there is nothing to vote on."));
        box.appendChild(h("p", "s-small", "A recorded vote, by roll call. Cast " + v.you.name + "'s vote on the resolution as a whole."));
        if (S.golden === "aims_in") box.appendChild(c.chiefNote("eyebrow", "Remember the first rule of the UN, Ambassador: don't vote down progress because it isn't everything you wanted. This text carries your capital's main aim."));
        else if (S.golden === "red_in") box.appendChild(c.chiefNote("concerned", "This text crosses your red line. Voting against it is within your instructions; abstaining lets progress through without endorsing it."));
        var fv = h("div", "s-votes");
        [["yes", "Yes"], ["abstain", "Abstain"], ["no", "No"]].forEach(function (x) { fv.appendChild(btn(x[1], "s-btn v-" + x[0], function () { c.move({ do: "final", vote: x[0] }); })); });
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
          if (!tags.length) { c.say("Tick at least one commitment for the statement, or let it go."); return; }
          c.move({ do: "statement", tags: tags });
        }));
        row.appendChild(btn("No statement", "s-btn ghost", function () { c.move({ do: "statement", skip: true }); }));
        box.appendChild(row);
      }
      shown = key;
      run(box, beats, fin, fresh);
      var rl = $("c-result-list"); rl.textContent = "";                 // the amendments so far
      $("c-results").hidden = !(S.done && S.done.length);
      (S.done || []).forEach(function (d) {
        var li = h("li", d.result === "adopted" || d.result === "accepted as friendly" ? "passed" : "failed");
        li.appendChild(h("b", "", d.result.charAt(0).toUpperCase() + d.result.slice(1)));
        li.appendChild(h("span", "", d.by + ": " + d.text)); rl.appendChild(li);
      });
    }
    return { render: render, stop: stop };
  };
})();
