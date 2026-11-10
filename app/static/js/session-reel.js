/* The Session (D-101, phase 12): the turn-start reel. Instead of many pop-ups at once, the start of each turn is one
   paced sequence, a card at a time, each from the character whose job it is: the President (the clock, the news,
   meetings), your Foreign Minister (telegrams from your capital) and your advisers (intelligence: rivals' moves,
   reports, who is at your door). Next, or skip the rest. */
(function () {
  "use strict";
  window.socSession = window.socSession || {};
  window.socSession.mods = window.socSession.mods || {};
  window.socSession.mods.reel = function (c) {
    var $ = c.$, h = c.h, A = c.A, G = c.G;
    var items = [], at = 0, done = null, line = null;

    function build(v, prev, news) {
      var out = [], staff = (v.staff || [])[0];
      var adv = function (who) { return who || staff; };
      if (v.stage && !v.stage.made && v.stage.turns_left === 0)
        out.push({ who: "president", face: "eyebrow", title: "The last turn of " + v.chapter_name, text: "Delegates, this is the last turn of " + v.chapter_name + ". After it, the committee moves on, breakthrough or not." });
      // a procedure question is asked in the President's own window straight after the reel, so the reel doesn't read
      // it out first as news (it did until 10 Nov: the player read every question twice)
      if (v.event && v.event.title && !(v.question && v.event.id === "procedure")) {
        var ev = { who: "president", news: true, face: "calm", title: v.event.title, text: v.event.body || "", hypo: v.event.hypothetical };
        out.push(ev);
      }
      var caucusComing = c.A.settings().talk !== false && (v.visits || []).some(function (x) { return x.kind === "caucus"; });
      if (v.meeting && !caucusComing) out.push({ who: "president", face: "calm", title: "The " + v.meeting.name + " meets", text: "Delegates are welcome to attend. Open Blocs to see the room and attend." });
      news.filter(function (x) { return x.kind === "telegram"; }).forEach(function (x) {
        out.push({ who: "minister", face: x.mood === "approve" ? "delighted" : x.mood === "furious" ? "concerned" : "eyebrow", title: "Telegram from your capital", text: x.text, tele: true });
      });
      var rivals = news.filter(function (x) { return x.kind === "rival"; });
      if (rivals.length) out.push({ who: "staff", adv: adv(), face: "concerned", title: "What the rivals did", text: rivals.length + " move" + (rivals.length === 1 ? "" : "s") + " since your last turn.",
                                   list: rivals.slice(-4).map(function (x) { return x.text; }) });
      var reports = news.filter(function (x) { return x.kind === "staff" || x.kind === "worry" || x.kind === "promote" || x.kind === "intel"; });
      if (reports.length) out.push({ who: "staff", adv: adv(c.staffOf(v, reports[0].text)), face: "thinking", title: "Your staff report", text: "", list: reports.map(function (x) { return x.text; }) });
      var shifts = news.filter(function (x) { return x.kind === "shift"; });
      if (shifts.length) out.push({ who: "staff", adv: adv(), face: "eyebrow", title: "Positions are shifting", text: "", list: shifts.map(function (x) { return x.text; }) });
      return out;
    }
    var lineSkip = $("s-reel-line-skip");                            // Skip ahead: finish the line being written (10 Nov)
    if (lineSkip) lineSkip.addEventListener("click", function () { if (line) line.finish(); });
    function play(list, then) {
      if (!list.length || !G) { if (then) then(); return; }
      // never over another card (a visit that slipped in first, a file): wait for it, as the visits do
      if (document.querySelector(".s-overlay:not([hidden])") || !$("s-walk").hidden) { setTimeout(function () { play(list, then); }, 600); return; }
      items = list; at = 0; done = then || null;
      c.open("s-reel"); show();
    }
    function show() {
      var x = items[at], face = $("s-reel-face"); face.textContent = "";
      if (x.who === "staff" && x.adv) face.appendChild(c.staffIcon(x.adv.kind, x.adv.stars, 120));
      else face.appendChild(G.portrait(x.face, x.who === "president" ? "president" : x.who === "minister" ? "minister" : null));
      $("s-reel-who").textContent = x.who === "president" ? "The President of the committee" : x.who === "minister" ? "Your Foreign Minister" :
        x.who === "staff" && x.adv ? x.adv.name + ", " + x.adv.kind_name : "The Chief of Protocol";
      $("s-reel-h").textContent = x.title;
      if (line) { line.finish(); line = null; }                      // a line still being written is completed first
      var p = $("s-reel-p"), sk = $("s-reel-line-skip"); p.textContent = ""; if (sk) sk.hidden = true;
      if (x.hypo) p.appendChild(h("span", "s-hypo", "Hypothetical"));
      if (x.text && G && G.speak) { if (sk) sk.hidden = false;
        var said = G.speak(face.querySelector("svg.g-face"), p, x.text, function () { if (sk) sk.hidden = true; }, { pitch: G.voiceOf(x.who) });
        line = said.done() ? null : said; }
      else if (x.text) p.appendChild(document.createTextNode(x.text));
      var ul = $("s-reel-list"); ul.textContent = "";
      (x.list || []).forEach(function (t) { ul.appendChild(h("li", "", t)); });
      ul.hidden = !(x.list || []).length;
      $("s-reel").classList.toggle("tele", !!x.tele);
      $("s-reel-n").textContent = (at + 1) + " of " + items.length;
      $("s-reel-next").textContent = at === items.length - 1 ? "To work" : "Next";
      $("s-reel-skip").hidden = at === items.length - 1;
      var doc = document.querySelector("#s-reel .s-doc"); c.restart(doc, "s-reel-in");
      if (window.socSession.fx) window.socSession.fx.paper(doc, x.tele ? "telegram" : x.news ? "news" : null);   // paper arrives
      A.play(x.tele ? "paper" : x.who === "president" ? "gavel" : "flip");
      $("s-reel-next").focus();
    }
    function finish() {
      c.close("s-reel");
      var then = done; done = null; items = [];
      if (then) then();
    }
    $("s-reel-next").addEventListener("click", function () { if (at >= items.length - 1) finish(); else { at += 1; show(); } });
    $("s-reel-skip").addEventListener("click", finish);
    $("s-reel").addEventListener("keydown", function (e) { if (e.key === "Escape") { e.stopPropagation(); finish(); } });
    return { build: build, play: play };
  };
})();
