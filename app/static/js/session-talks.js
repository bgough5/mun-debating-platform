/* The Session (D-101, phase 12): talking to delegations. Pitches (choose two arguments), the deal table in rounds
   (they name a price; holding out brings it down, but tests their patience), and compromise with a rival (the same
   haggling, for peace and a merged text). The game page passes in what this needs (`c`). */
(function () {
  "use strict";
  window.socSession = window.socSession || {};
  window.socSession.mods = window.socSession.mods || {};
  window.socSession.mods.talks = function (c) {
    var $ = c.$, h = c.h, A = c.A, G = c.G;

    // ---------- pitches ----------
    var chosen = {};
    function pitchBox(v, d, iso) {                                    // talking is a conversation now (dialogue module)
      var box = h("div", "s-pitch wide");
      var top = h("p", "s-pitch-h");
      top.appendChild(h("b", "", "Talk with " + d.name)); top.appendChild(document.createTextNode(" · " + d.lobby_cost + " Influence, 1 action"));
      box.appendChild(top);
      if (d.listens_to && d.listens_to.length) box.appendChild(h("p", "s-small", "From its file: it listens to " + d.listens_to.join(" and ").toLowerCase() + "."));
      var open = v.conv && v.conv.iso3 === iso;
      box.appendChild(c.btn(open ? "Continue the conversation" : "Talk to " + d.name, "s-btn small s-talk-btn", function () { c.talk(iso); },
                            !open && (!!v.conv || !v.ap || v.influence < d.lobby_cost)));
      if (v.conv && !open) box.appendChild(h("p", "s-small", "You're in a conversation with " + v.conv.name + ": finish it first."));
      return box;
    }
    function pitchAnswer(out) {
      if (!out || !out.landed) return null;
      var words = { strong: "landed", some: "partly landed", weak: "fell flat" }, v = c.view();
      return Object.keys(out.landed).map(function (k) { return v.args[k].name + " " + words[out.landed[k]]; }).join("; ") + ".";
    }

    // ---------- the table: deals and compromises ----------
    var T = { iso: null, kind: "deal", get: {}, give: {}, note: "" };
    function openTable(iso, kind) {
      T = { iso: iso, kind: kind || "deal", get: {}, give: {}, note: "" };
      var t = c.view().talks;
      if (t && t.iso3 === iso) t.asks.forEach(function (k) { T.give[k] = true; });
      render(); c.open("s-deal"); A.play("flip");
    }
    function render() {
      var v = c.view(), d = v && v.tokens[T.iso]; if (!d) return;
      var t = v.talks && v.talks.iso3 === T.iso ? v.talks : null, rival = T.kind === "rival";
      $("s-deal-h").textContent = v.you.name + " and " + d.name;
      var dl = d.deal || {};
      $("s-deal-sub").textContent = rival ? d.name + " is a rival. It will make peace for the right concession: it stops working against you, brings part of its support and co-sponsors a merged text." :
        d.name + " wants " + (dl.asks || []).map(function (k) { return c.ASK[k]; }).join(", ") + ". Your budget: " + (v.budget.total - v.budget.used) + " of " + v.budget.total + " funding pledges left.";
      var give = t ? t.give : rival ? peaceItems(v, d) : giveItems(v, d), getBox = $("s-deal-get"); getBox.textContent = "";
      // what you ask for: chosen before the talks open, fixed after
      if (rival) getBox.appendChild(item({ name: "Peace and co-sponsorship", what: "It stops working against you, and co-sponsors the merged text." }, true, true, "the point of the talks"));
      else Object.keys(v.deal_items.get).forEach(function (k) {
        var have = dl.get && k in dl.get, on = t ? t.get.indexOf(k) >= 0 : !!T.get[k];
        var b = item(v.deal_items.get[k], on, !have || !!t, have ? "costs them " + dl.get[k].toFixed(1) : "not on the table");
        if (have && !t) b.addEventListener("click", function () {
          if (T.get[k]) delete T.get[k]; else T.get[k] = true;
          if (k === "yes") delete T.get.abstain; if (k === "abstain") delete T.get.yes;
          A.play("tick"); render();
        });
        getBox.appendChild(b);
      });
      var giveBox = $("s-deal-give"); giveBox.textContent = "";
      Object.keys(give).forEach(function (k) {
        var it = give[k], on = !!T.give[k];
        var tag = "worth " + it.value.toFixed(1) + " to them" + (t && t.asks.indexOf(k) >= 0 ? " · they ask for this" : "") + (it.capital < 0 ? " · your capital objects (" + it.capital + ")" : "");
        var b = item(it, on, !t, tag);
        if (t) b.addEventListener("click", function () { if (T.give[k]) delete T.give[k]; else T.give[k] = true; A.play("tick"); render(); });
        giveBox.appendChild(b);
      });
      var mid = $("s-deal-verdict"), dial = $("s-deal-dial"), fuse = $("s-deal-fuse"), note = $("s-deal-note");
      fuse.textContent = "";
      if (!t) {
        dial.className = "s-meter-dial"; dial.querySelector("i").style.transform = "rotate(-80deg)";
        mid.textContent = T.note || (rival ? "Open talks to hear its price." : "Choose what you'll ask for, then open talks to hear their price.");
        note.textContent = "Opening talks takes " + v.costs.deal_ap + " actions; the rounds after cost nothing. One set of talks a turn.";
        setGo("Open talks (" + v.costs.deal_ap + " actions)", (!rival && !Object.keys(T.get).length) || !v.deal_ready || v.ap < v.costs.deal_ap, function () {
          c.move(rival ? { do: "compromise", stage: "open", iso3: T.iso } : { do: "deal", stage: "open", iso3: T.iso, get: Object.keys(T.get) });
        });
        $("s-deal-accept").hidden = true; $("s-deal-walk").hidden = true;
      } else {
        var offer = Object.keys(T.give).reduce(function (s, k) { return s + (give[k] ? give[k].value : 0); }, 0);
        var gap = offer - t.price;
        dial.className = "s-meter-dial " + (gap >= 0 ? "v-accept" : gap > -1.5 ? "v-more" : "v-refuse");
        dial.querySelector("i").style.transform = "rotate(" + Math.max(-80, Math.min(80, gap * 30)) + "deg)";
        mid.textContent = T.note || ("Their price: " + t.price.toFixed(1) + " · your offer: " + offer.toFixed(1));
        for (var i = 0; i < 5; i++) fuse.appendChild(h("i", i < t.patience ? "on" : ""));
        fuse.setAttribute("aria-label", "Their patience: " + t.patience);
        var bits = ["Round " + t.round + "."];
        if (t.rival_bid) bits.push(t.rival_bid + " is courting them too: they may walk sooner, or ask more.");
        if (t.walk_seen) bits.push(t.walk_seen.by + (t.walk_seen.exact !== undefined ? ": they'll go as low as " + t.walk_seen.exact.toFixed(1) + "." :
          ": they'll go as low as somewhere between " + t.walk_seen.low.toFixed(1) + " and " + t.walk_seen.high.toFixed(1) + "."));
        bits.push("Offer less than their price and they'll come down, but each round tests their patience.");
        note.textContent = bits.join(" ");
        setGo("Make this offer", !Object.keys(T.give).length, function () { c.move({ do: T.kind === "rival" ? "compromise" : "deal", stage: "offer", give: Object.keys(T.give) }); });
        var acc = $("s-deal-accept"); acc.hidden = false;
        acc.textContent = "Accept their terms (" + t.asks.map(function (k) { return give[k].name.toLowerCase(); }).join(", ") + ")";
        $("s-deal-walk").hidden = false;
      }
      var cap = Object.keys(T.give).reduce(function (s, k) { return s + ((give[k] || {}).capital || 0); }, 0), cb = $("s-deal-capital"); cb.textContent = "";
      if (Object.keys(T.give).length) {
        if (G) cb.appendChild(G.portrait(cap < -1 ? "concerned" : cap < 0 ? "eyebrow" : "calm", "minister"));
        cb.appendChild(h("p", "", cap < -1 ? "Your capital would be furious (" + cap + " Standing)." : cap < 0 ? "Your capital would grumble (" + cap + " Standing)." : "Your capital would approve."));
      }
    }
    function giveItems(v, d) {
      var out = {}, dl = d.deal || {};
      Object.keys(dl.give || {}).forEach(function (k) { out[k] = { name: v.deal_items.give[k].name, what: v.deal_items.give[k].what, value: dl.give[k], capital: (dl.capital || {})[k] || 0 }; });
      return out;
    }
    function peaceItems(v, d) {
      var out = {}, labels = { drop: ["Drop the commitment it can't accept", "Take its red line out of the draft, wherever it is.", 2.2],
                              include: ["Let its wish into the text", "Add a clause with what it came for.", 1.6] };
      (d.peace_terms || []).forEach(function (k) { out[k] = { name: labels[k][0], what: labels[k][1], value: labels[k][2], capital: 0 }; });
      return out;
    }
    function item(it, on, disabled, tag) {
      var b = h("button", "s-item" + (on ? " on" : "")); b.type = "button"; b.setAttribute("aria-pressed", String(on));
      if (disabled) b.disabled = true;
      b.appendChild(h("b", "", it.name)); b.appendChild(h("span", "", it.what)); if (tag) b.appendChild(h("em", "", tag));
      return b;
    }
    var goFn = null;
    function setGo(label, disabled, fn) { var g = $("s-deal-go"); g.textContent = label; g.disabled = disabled; goFn = fn; }
    $("s-deal-go").addEventListener("click", function () { if (goFn) goFn(); });
    $("s-deal-accept").addEventListener("click", function () {
      var t = c.view().talks; if (!t) return;
      T.give = {}; t.asks.forEach(function (k) { T.give[k] = true; });
      c.move({ do: T.kind === "rival" ? "compromise" : "deal", stage: "offer", give: t.asks.slice() });
    });
    $("s-deal-walk").addEventListener("click", function () { c.move({ do: T.kind === "rival" ? "compromise" : "deal", stage: "walk" }); });

    function answer(v, out, action) {
      if (action.stage === "open") {
        var t = v.talks; T.give = {}; if (t) t.asks.forEach(function (k) { T.give[k] = true; });
        T.note = t ? "They name their price: " + t.price.toFixed(1) + ". They ask for " + t.asks.map(function (k) { return t.give[k].name.toLowerCase(); }).join(", ") + "." : "";
        c.say(T.note); render(); A.play("paper"); return;
      }
      if (out.deal || out.peace) {
        c.close("s-deal"); A.play(out.peace ? "fanfare" : "stamp");
        c.say(out.peace ? "Peace made: a merged text, co-sponsored." : "Deal done" + (out.rounds > 1 ? " after " + out.rounds + " rounds" + (out.saved > 0 ? ": holding out saved you " + out.saved.toFixed(1) + "." : ".") : "."));
        return;
      }
      if (out.walked) {
        T.note = out.walked === "them" ? "They walked away from the table." : "You left the table.";
        c.say(T.note); A.play(out.walked === "them" ? "sting" : "flip");
        setTimeout(function () { c.close("s-deal"); }, out.walked === "them" ? 1600 : 200); return;
      }
      if (out.counter !== undefined) {
        T.note = (out.insulted ? "They took that as an insult, but they're still talking. " : "They came down: ") + out.was.toFixed(1) + " → " + out.counter.toFixed(1) + ".";
        T.give = {}; (v.talks ? v.talks.asks : []).forEach(function (k) { T.give[k] = true; });
        c.say(T.note); A.play("coin"); render();
      }
    }
    return { pitchBox: pitchBox, pitchAnswer: pitchAnswer, openTable: openTable, render: render, answer: answer, isOpen: function () { return !$("s-deal").hidden; } };
  };
})();
