/* The speech coach (D-100): counts and marks a student's own writing, in the browser, as they type.
   Nothing leaves the laptop. The panel is _coach.html; its data (techniques, fillers, phrases) is app/web/coach.py.
   Marks are drawn on a copy of the text behind the (transparent) text box, so the writing itself is never changed. */
(function () {
  "use strict";
  var SPRITE = "/static/icons/sprite.svg";
  var store = {
    get: function (k) { try { return window.localStorage.getItem(k); } catch (e) { return null; } },
    set: function (k, v) { try { window.localStorage.setItem(k, v); } catch (e) { /* private window: forget it */ } }
  };
  function clock(s) { s = Math.max(0, Math.round(s)); var m = Math.floor(s / 60), r = s % 60; return m + ":" + (r < 10 ? "0" : "") + r; }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function reEsc(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }
  function ico(name) { return '<svg class="icon" aria-hidden="true" focusable="false"><use href="' + SPRITE + "#i-" + name + '"></use></svg>'; }
  function plural(n, one, many) { return n + " " + (n === 1 ? one : (many || one + "s")); }
  var reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ---------- reading the text ----------
  var WORD = /[A-Za-z0-9À-ɏ][A-Za-z0-9À-ɏ'’-]*/g;
  function words(text) { var m = (text || "").trim().match(/\S+/g); return m ? m.length : 0; }
  function tokens(text) { var out = [], m; WORD.lastIndex = 0; while ((m = WORD.exec(text))) out.push({ w: m[0], s: m.index, e: m.index + m[0].length }); return out; }
  function sentences(text) {
    var out = [], re = /[^.!?\n]*[^.!?\n\s][^.!?\n]*[.!?]*/g, m;
    while ((m = re.exec(text))) {
      var t = tokens(m[0]); if (!t.length) continue;
      var lead = m[0].length - m[0].replace(/^\s+/, "").length;
      out.push({ s: m.index + lead, e: m.index + m[0].length, n: t.length,
                 first: t[0].w.toLowerCase(), two: t.slice(0, 2).map(function (x) { return x.w.toLowerCase(); }).join(" ") });
    }
    return out;
  }
  function syllables(w) {
    w = w.toLowerCase().replace(/[^a-z]/g, ""); if (!w) return 0; if (w.length <= 3) return 1;
    w = w.replace(/(?:[^laeiouy]es|ed|[^laeiouy]e)$/, "").replace(/^y/, "");
    var g = w.match(/[aeiouy]{1,2}/g); return g ? g.length : 1;
  }
  function findAll(re, text, cls, key) {
    var out = [], m; re.lastIndex = 0;
    while ((m = re.exec(text))) { if (!m[0].length) { re.lastIndex++; continue; } out.push({ s: m.index, e: m.index + m[0].length, cls: cls, key: key }); }
    return out;
  }

  // ---------- one coach: a scope holding text boxes (or read-only text) and the panel ----------
  function Coach(scope) {
    var panel = scope.querySelector("[data-coach]");
    var cfg = JSON.parse(panel.querySelector("[data-coach-config]").textContent);
    var self = this;
    this.scope = scope; this.panel = panel; this.cfg = cfg;
    this.key = "soc-coach-aim:" + location.pathname + ":" + Array.prototype.indexOf.call(document.querySelectorAll("[data-coach-scope]"), scope);
    this.pace = parseInt(store.get("soc-coach-pace") || "130", 10) || 130;
    this.marks = (store.get("soc-coach-marks") || "").split(",").filter(Boolean);
    this.spot = null; this.last = null; this.techSeen = {};
    this.techs = cfg.techniques.map(function (t) { return { code: t.code, name: t.name, re: t.pattern ? new RegExp(t.pattern, "gi") : null }; });
    this.filler = new RegExp("\\b(?:" + cfg.fillers.map(reEsc).map(function (f) { return f.replace(/ /g, "\\s+"); }).join("|") + ")\\b", "gi");
    this.stop = {}; cfg.stop.forEach(function (w) { self.stop[w] = 1; });
    if (cfg.team_line) {
      var tl = tokens(cfg.team_line).map(function (t) { return reEsc(t.w); }).slice(0, 8);
      this.teamRe = tl.length >= 2 ? new RegExp(tl.join("[^A-Za-z0-9]+"), "gi") : null;
    }
    this.sources = Array.prototype.map.call(scope.querySelectorAll("[data-coach-text]"), function (el, i) {
      var lab = el.getAttribute("data-coach-label");
      if (!lab && el.id) { var l = scope.querySelector('label[for="' + el.id + '"]'); if (l) lab = (l.childNodes[0] && l.childNodes[0].textContent || l.textContent).trim(); }
      return { el: el, edit: el.tagName === "TEXTAREA", label: lab || "Part " + (i + 1), text: el.tagName === "TEXTAREA" ? el.value : el.textContent, ranges: [] };
    });
    this.target = scope.querySelector("[name=target_seconds]");
    var aimSel = panel.querySelector("[data-c-aim]");
    if (aimSel) { var saved = store.get(this.key); if (saved && aimSel.querySelector('option[value="' + saved + '"]')) aimSel.value = saved; }
    this.aimSel = aimSel;
    this.open = store.get("soc-coach-open") !== "0";
    this.bind(); this.setOpen(this.open, true); this.syncChips(); this.analyse(); this.voices();
  }

  Coach.prototype.aim = function () {
    var v = this.target ? this.target.value : (this.aimSel ? this.aimSel.value : this.cfg.aim);
    return parseInt(v, 10) || this.cfg.aim;
  };

  Coach.prototype.bind = function () {
    var self = this, p = this.panel;
    this.sources.forEach(function (src) {
      if (!src.edit) return;
      src.el.addEventListener("input", function () { src.text = src.el.value; self.later(); });
      src.el.addEventListener("focus", function () { self.last = src; });
      src.el.addEventListener("scroll", function () { if (src.back) src.back.scrollTop = src.el.scrollTop; });
      if (window.ResizeObserver) new ResizeObserver(function () { self.fit(src); }).observe(src.el);
    });
    if (this.target) this.target.addEventListener("change", function () { self.analyse(); });
    if (this.aimSel) this.aimSel.addEventListener("change", function () { store.set(self.key, self.aimSel.value); self.analyse(); });
    p.addEventListener("click", function (e) {
      var b = e.target.closest("button"); if (!b || !p.contains(b)) return;
      if (b.hasAttribute("data-coach-toggle")) return self.setOpen(!self.open);
      if (b.hasAttribute("data-coach-listen")) return self.listen();
      if (b.hasAttribute("data-c-pace")) { self.pace = parseInt(b.getAttribute("data-c-pace"), 10); store.set("soc-coach-pace", String(self.pace)); self.syncChips(); return self.analyse(); }
      if (b.hasAttribute("data-c-mark")) {
        var m = b.getAttribute("data-c-mark"), i = self.marks.indexOf(m);
        if (i >= 0) self.marks.splice(i, 1); else self.marks.push(m);
        store.set("soc-coach-marks", self.marks.join(",")); self.spot = null; self.syncChips(); return self.paint();
      }
      if (b.hasAttribute("data-c-tab")) return self.tab(b.getAttribute("data-c-tab"));
      if (b.hasAttribute("data-c-spot")) { var k = b.getAttribute("data-c-spot"); self.spot = self.spot === k ? null : k; self.syncChips(); self.paint(); if (self.spot) self.reveal(); return; }
      if (b.hasAttribute("data-c-insert")) return self.insert(b.getAttribute("data-c-insert"));
    });
    p.addEventListener("keydown", function (e) {
      var t = e.target.closest("[role=tab]"); if (!t) return;
      var tabs = Array.prototype.slice.call(p.querySelectorAll("[role=tab]")), i = tabs.indexOf(t);
      if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
        e.preventDefault(); var n = tabs[(i + (e.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length];
        self.tab(n.getAttribute("data-c-tab")); n.focus();
      }
    });
  };

  Coach.prototype.later = function () {
    var self = this; clearTimeout(this.t); this.t = setTimeout(function () { self.analyse(); }, 120);
  };

  Coach.prototype.setOpen = function (open, first) {
    this.open = open; if (!first) store.set("soc-coach-open", open ? "1" : "0");
    this.scope.classList.toggle("coach-closed", !open);
    var tg = this.panel.querySelector("[data-coach-toggle]");
    tg.setAttribute("aria-expanded", open ? "true" : "false");
    this.panel.querySelector("[data-c-toggle-label]").textContent = open ? "Hide" : "Show";
    this.panel.querySelector("[data-coach-body]").hidden = !open;
    var self = this;
    this.sources.forEach(function (src) { if (open) self.attach(src); else self.detach(src); });
    if (!open) this.stopListening();
    this.paint();
  };

  Coach.prototype.tab = function (name) {
    this.panel.querySelectorAll("[data-c-tab]").forEach(function (t) {
      var on = t.getAttribute("data-c-tab") === name; t.setAttribute("aria-selected", on ? "true" : "false"); t.tabIndex = on ? 0 : -1;
    });
    this.panel.querySelectorAll("[data-c-panel]").forEach(function (x) { x.hidden = x.getAttribute("data-c-panel") !== name; });
  };

  Coach.prototype.syncChips = function () {
    var self = this;
    this.panel.querySelectorAll("[data-c-pace]").forEach(function (b) { b.setAttribute("aria-pressed", parseInt(b.getAttribute("data-c-pace"), 10) === self.pace ? "true" : "false"); });
    this.panel.querySelectorAll("[data-c-mark]").forEach(function (b) { b.setAttribute("aria-pressed", self.marks.indexOf(b.getAttribute("data-c-mark")) >= 0 ? "true" : "false"); });
    this.panel.querySelectorAll("[data-c-spot]").forEach(function (b) { b.setAttribute("aria-pressed", b.getAttribute("data-c-spot") === self.spot ? "true" : "false"); });
  };

  // ---------- the copy behind each text box ----------
  Coach.prototype.attach = function (src) {
    if (!src.edit || src.back) return;
    var host = src.el.parentNode; host.classList.add("coach-host");
    var bd = document.createElement("div"); bd.className = "coach-back"; bd.setAttribute("aria-hidden", "true");
    host.insertBefore(bd, src.el); src.back = bd; src.el.classList.add("coach-ta"); this.fit(src);
  };
  Coach.prototype.detach = function (src) {
    if (src.back) { src.back.remove(); src.back = null; src.el.classList.remove("coach-ta"); }
    if (!src.edit) src.el.textContent = src.text;
  };
  Coach.prototype.fit = function (src) {
    var ta = src.el, bd = src.back; if (!bd) return;
    var cs = getComputedStyle(ta);
    ["boxSizing", "fontFamily", "fontSize", "fontWeight", "lineHeight", "letterSpacing", "wordSpacing", "textIndent", "tabSize",
     "paddingTop", "paddingBottom", "paddingLeft", "borderTopWidth", "borderBottomWidth", "borderLeftWidth", "borderRightWidth"].forEach(function (k) { bd.style[k] = cs[k]; });
    var bars = ta.offsetWidth - ta.clientWidth - parseFloat(cs.borderLeftWidth) - parseFloat(cs.borderRightWidth);
    bd.style.paddingRight = (parseFloat(cs.paddingRight) + Math.max(0, bars)) + "px";
    bd.style.width = ta.offsetWidth + "px"; bd.style.height = ta.offsetHeight + "px";
    bd.style.top = ta.offsetTop + "px"; bd.style.left = ta.offsetLeft + "px";
    bd.scrollTop = ta.scrollTop;
  };

  // ---------- counting ----------
  Coach.prototype.analyse = function () {
    var fillSaid = {}, self = this, cfg = this.cfg, total = 0, sents = 0, syl = 0, toks = 0, counts = {}, fill = {}, longs = [], opens = {}, firstP = 0;
    var tech = {}; this.techs.forEach(function (t) { tech[t.code] = 0; });
    var cum = 0, minutes = [], per = this.pace;
    this.sources.forEach(function (src, si) {
      var text = src.text, r = [];
      var tk = tokens(text), ss = sentences(text);
      src.words = words(text); total += src.words; sents += ss.length; toks += tk.length;
      tk.forEach(function (t, i) {
        syl += syllables(t.w);
        var lw = t.w.toLowerCase().replace(/[’']s$/, "").replace(/[’']/g, "'");
        if (lw.length >= 4 && !self.stop[lw] && /[a-z]/.test(lw)) { (counts[lw] = counts[lw] || []).push([si, t.s, t.e]); }
        if ((cum + i) > 0 && (cum + i) % per === 0) minutes.push([si, t.s, clock((cum + i) / per * 60)]);
      });
      cum += tk.length;
      findAll(self.filler, text, "filler", null).forEach(function (m) {
        var said = text.slice(m.s, m.e).replace(/\s+/g, " "), k = said.toLowerCase();
        m.key = "filler:" + k; fill[k] = (fill[k] || 0) + 1; if (!fillSaid[k] || /^I\b/.test(said)) fillSaid[k] = said; r.push(m);
      });
      ss.forEach(function (s, i) {
        if (s.n > cfg.long) { longs.push({ si: si, n: s.n, i: longs.length }); r.push({ s: s.s, e: s.e, cls: "long", key: "long:" + (longs.length - 1) }); }
        (opens[s.first] = opens[s.first] || []).push([si, s.s, s.s + s.first.length]);
        if (i > 0 && s.two.indexOf(" ") > 0 && s.two === ss[i - 1].two) { tech.anaphora = (tech.anaphora || 0) + 1; r.push({ s: s.s, e: s.s + s.two.length, cls: "tech", key: "tech:anaphora" }); }
      });
      self.techs.forEach(function (t) {
        var re = t.code === "teamline" ? self.teamRe : t.re; if (!re) return;
        findAll(re, text, "tech", "tech:" + t.code).forEach(function (m) { tech[t.code]++; r.push(m); });
      });
      if (cfg.first_person) findAll(/\b(?:I|me|my|myself)\b/g, text, "filler", "first").forEach(function (m) { firstP++; r.push(m); });
      src.ranges = r;
    });
    var repeats = Object.keys(counts).filter(function (w) { return counts[w].length >= cfg.repeat; })
      .sort(function (a, b) { return counts[b].length - counts[a].length || (a < b ? -1 : 1); }).slice(0, 8);
    repeats.forEach(function (w) { counts[w].forEach(function (x) { self.sources[x[0]].ranges.push({ s: x[1], e: x[2], cls: "repeat", key: "word:" + w }); }); });
    var openers = sents >= 4 ? Object.keys(opens).filter(function (w) { return opens[w].length >= 3 && opens[w].length / sents >= 0.3; }) : [];
    openers.forEach(function (w) { opens[w].forEach(function (x) { self.sources[x[0]].ranges.push({ s: x[1], e: x[2], cls: "repeat", key: "open:" + w }); }); });
    this.minutes = minutes;
    this.result = { fillSaid: fillSaid, total: total, sents: sents, syl: syl, toks: toks, repeats: repeats, counts: counts, fill: fill, longs: longs,
                    openers: openers, opens: opens, firstP: firstP, tech: tech };
    this.render(); this.paint();
  };

  // ---------- the panel ----------
  Coach.prototype.render = function () {
    var R = this.result, p = this.panel, aim = this.aim(), secs = R.total / this.pace * 60, cfg = this.cfg, self = this;
    p.querySelector("[data-c-time]").textContent = clock(secs);
    p.querySelector("[data-c-aim-text]").textContent = clock(aim);
    var frac = aim ? secs / aim : 0, state = !R.total ? "none" : (secs > aim + 15 ? "over" : (frac >= 0.75 ? "on" : "under"));
    var verdict = { none: "Start writing", under: "About " + clock(Math.max(0, aim - secs)) + " to go", on: "On time", over: "Over by " + clock(secs - aim) }[state];
    var v = p.querySelector("[data-c-verdict]"); v.textContent = verdict; v.setAttribute("data-state", state);
    p.querySelector(".coach-dial").setAttribute("data-state", state);
    p.querySelector("[data-c-dial]").setAttribute("stroke-dasharray", (Math.min(frac, 1) * 100).toFixed(1) + " 100");
    p.querySelector("[data-c-over]").setAttribute("stroke-dasharray", (Math.max(0, Math.min(frac - 1, 1)) * 100).toFixed(1) + " 100");
    var avg = R.sents ? Math.round(R.toks / R.sents) : 0;
    this.stat("words", R.total); this.stat("sentences", R.sents); this.stat("avg", R.sents ? avg : "–");
    var level = "–";
    if (R.toks >= 30 && R.sents) {
      var g = 0.39 * (R.toks / R.sents) + 11.8 * (R.syl / R.toks) - 15.59;
      level = g > 12.5 ? "University" : "Year " + Math.max(3, Math.min(12, Math.round(g)));
    }
    this.stat("level", level);
    p.querySelector('[data-c-stat="level"]').title = "An estimate from sentence and word length (Flesch–Kincaid). Shorter sentences are easier to follow out loud.";
    // Time in each part (only when the speech has parts)
    var bal = p.querySelector("[data-c-balance]");
    if (this.sources.length > 1) {
      bal.hidden = !R.total;
      var tones = ["t1", "t2", "t3", "t4", "t5", "t6"];
      p.querySelector("[data-c-bar]").innerHTML = this.sources.map(function (s, i) {
        return s.words ? '<span class="seg ' + tones[i % 6] + '" style="flex-grow:' + s.words + '" title="' + esc(s.label) + '"></span>' : "";
      }).join("");
      p.querySelector("[data-c-key]").innerHTML = this.sources.map(function (s, i) {
        return '<li><span class="sw ' + tones[i % 6] + '"></span>' + esc(s.label) + ' <span class="muted">' + clock(s.words / self.pace * 60) + "</span></li>";
      }).join("");
    }
    // Check
    var html = [], issues = 0;
    function group(title, hint, chips) { html.push('<div class="check-group"><h3>' + title + '</h3><div class="chip-row">' + chips.join("") + "</div>" + (hint ? '<p class="check-hint">' + hint + "</p>" : "") + "</div>"); }
    function chip(key, label, cls) { return '<button type="button" class="word-chip ' + cls + '" data-c-spot="' + esc(key) + '" aria-pressed="' + (self.spot === key) + '">' + label + "</button>"; }
    if (R.repeats.length) { issues += R.repeats.length; group("Repeated words", "Swap a few for another word, or cut them. Repeating on purpose? That's a technique: see Techniques.",
      R.repeats.map(function (w) { return chip("word:" + w, esc(w) + " <b>×" + R.counts[w].length + "</b>", "mk-repeat"); })); }
    var fk = Object.keys(R.fill).sort(function (a, b) { return R.fill[b] - R.fill[a]; });
    if (fk.length) { issues += fk.length; group("Fillers", "Words like these soften what you say. Cut most of them and your point sounds surer.",
      fk.map(function (w) { return chip("filler:" + w, "“" + esc(R.fillSaid[w] || w) + "” <b>×" + R.fill[w] + "</b>", "mk-filler"); })); }
    if (R.longs.length) { issues += R.longs.length; group("Long sentences", "Too long to say in one breath. Try splitting at “and”, “but” or “because”.",
      R.longs.map(function (l) { return chip("long:" + l.i, "Sentence of <b>" + l.n + "</b> words", "mk-long"); })); }
    if (R.openers.length) { issues += R.openers.length; group("Sentence starts", "Many sentences start the same way. Vary a few, unless the repetition is for effect.",
      R.openers.map(function (w) { return chip("open:" + w, plural(R.opens[w].length, "sentence") + " start “" + esc(w) + "”", "mk-repeat"); })); }
    if (R.firstP) { issues += 1; group("Speaking for your country", "In committee you speak for your country, not yourself: try “The delegation of …” or the country's name instead of I, me or my.",
      [chip("first", "I / me / my <b>×" + R.firstP + "</b>", "mk-filler")]); }
    var box = p.querySelector("[data-c-check]");
    if (!R.total) box.innerHTML = '<p class="small muted">Write a few sentences and the coach will look for repeated words, fillers and sentences too long to say in one breath.</p>';
    else if (!issues) box.innerHTML = '<p class="check-clear">' + ico("ok") + " No repeats, fillers or long sentences. Read it aloud to check the flow.</p>";
    else box.innerHTML = html.join("");
    p.querySelector('[data-c-n="check"]').textContent = issues ? String(issues) : "";
    // Techniques
    var shown = 0, used = 0;
    p.querySelectorAll("[data-c-tech]").forEach(function (li) {
      if (li.hidden) return; shown++;
      var code = li.getAttribute("data-c-tech"), n = R.tech[code] || 0, c = li.querySelector("[data-c-count]");
      if (n) used++;
      c.textContent = n ? "Used ×" + n : "Not yet";
      li.classList.toggle("used", !!n);
      if (n && !self.techSeen[code] && self.ready && !reduced) { li.classList.remove("pop"); void li.offsetWidth; li.classList.add("pop"); }
      self.techSeen[code] = !!n;
    });
    p.querySelector('[data-c-n="tech"]').textContent = used + "/" + shown;
    this.ready = true;
    // One quiet summary for screen readers, after the typing stops
    var say = plural(R.total, "word") + ", about " + clock(secs) + ". " + verdict + ".";
    clearTimeout(this.sayT); this.sayT = setTimeout(function () { var s = p.querySelector("[data-c-say]"); if (s.textContent !== say) s.textContent = say; }, 1500);
  };
  Coach.prototype.stat = function (k, v) { var d = this.panel.querySelector('[data-c-stat="' + k + '"]'); if (d && d.textContent !== String(v)) { d.textContent = v; } };

  // ---------- marks in the writing ----------
  Coach.prototype.paint = function () {
    var self = this, spot = this.spot, on = {};
    this.marks.forEach(function (m) { on[m] = 1; });
    this.sources.forEach(function (src, si) {
      var target = src.edit ? src.back : src.el; if (!target) return;
      if (!self.open && !src.edit) { src.el.textContent = src.text; return; }
      var text = src.text, rs = (src.ranges || []).filter(function (r) { return spot ? r.key === spot : on[r.cls]; });
      if (self.now && self.now.si === si) rs = rs.concat([{ s: self.now.s, e: self.now.e, cls: "now" }]);
      var pts = {}, mins = {};
      rs.forEach(function (r) { pts[r.s] = 1; pts[r.e] = 1; });
      if (!spot && on.minute) (self.minutes || []).forEach(function (m) { if (m[0] === si) { mins[m[1]] = m[2]; pts[m[1]] = 1; } });
      var cuts = Object.keys(pts).map(Number).concat([0, text.length]).filter(function (x) { return x >= 0 && x <= text.length; })
        .sort(function (a, b) { return a - b; }).filter(function (x, i, a) { return i === 0 || x !== a[i - 1]; });
      var out = [];
      for (var i = 0; i < cuts.length - 1; i++) {
        var a = cuts[i], b = cuts[i + 1], piece = esc(text.slice(a, b));
        if (mins[a]) out.push('<span class="cm-min" data-t="' + mins[a] + '"></span>');
        var cls = {}; rs.forEach(function (r) { if (r.s <= a && r.e >= b) cls["cm-" + r.cls] = 1; });
        var c = Object.keys(cls);
        out.push(c.length ? '<mark class="' + c.join(" ") + (spot ? " cm-spot" : "") + '">' + piece + "</mark>" : piece);
      }
      target.innerHTML = out.join("") + (src.edit ? " " : "");
      if (src.edit) target.scrollTop = src.el.scrollTop;
    });
  };
  Coach.prototype.reveal = function () {
    var self = this;
    for (var i = 0; i < this.sources.length; i++) {
      var src = this.sources[i], host = src.edit ? src.back : src.el; if (!host) continue;
      var m = host.querySelector("mark"); if (!m) continue;
      if (src.edit) { src.el.scrollTop = Math.max(0, m.offsetTop - src.el.clientHeight / 3); src.back.scrollTop = src.el.scrollTop; }
      var r = (src.edit ? src.el : m).getBoundingClientRect();
      if (r.top < 0 || r.bottom > window.innerHeight) (src.edit ? src.el : m).scrollIntoView({ block: "center", behavior: reduced ? "auto" : "smooth" });
      return;
    }
    void self;
  };

  // ---------- phrases ----------
  Coach.prototype.insert = function (text) {
    var original = text;
    var src = this.last || this.sources.filter(function (s) { return s.edit; })[0]; if (!src) return;
    var ta = src.el, s = ta.selectionStart, e = ta.selectionEnd, before = ta.value.slice(0, s);
    var pre = before && !/\s$/.test(before) ? " " : "";
    // After a comma, carry on the sentence: "…delegates, the delegation of …" (country names keep their capital)
    if (/,\s*$/.test(before) && /^(?:The|We|Our|This|For|While|With|As|Today|Even|So|But)\b/.test(text)) text = text.charAt(0).toLowerCase() + text.slice(1);
    var add = pre + text + (/[,:]$/.test(text) ? " " : "");
    if (ta.maxLength > 0 && ta.value.length - (e - s) + add.length > ta.maxLength) { this.say("There's no room left in this box."); return; }
    ta.focus(); ta.setRangeText(add, s, e, "end");
    var dot = add.indexOf("…");
    if (dot >= 0) ta.setSelectionRange(s + dot, s + dot + 1);
    ta.dispatchEvent(new Event("input", { bubbles: true }));
    var btn = this.panel.querySelector('[data-c-insert="' + CSS.escape(original) + '"]');
    if (btn && !reduced) { btn.classList.remove("added"); void btn.offsetWidth; btn.classList.add("added"); }
  };
  Coach.prototype.say = function (t) { var s = this.panel.querySelector("[data-c-say]"); s.textContent = t; };

  // ---------- listen: the laptop's own voices only, so the writing never leaves the machine ----------
  function localVoices() {
    if (!("speechSynthesis" in window)) return [];
    return window.speechSynthesis.getVoices().filter(function (v) { return v.localService && /^en/i.test(v.lang); });
  }
  Coach.prototype.voices = function () {
    var self = this, b = this.panel.querySelector("[data-coach-listen]");
    function check() { b.hidden = !localVoices().length; }
    check();
    if ("speechSynthesis" in window) window.speechSynthesis.addEventListener("voiceschanged", check);
  };
  Coach.prototype.listen = function () {
    var self = this, synth = window.speechSynthesis, b = this.panel.querySelector("[data-coach-listen]");
    if (this.speaking) return this.stopListening();
    var vs = localVoices(); if (!vs.length) return;
    var voice = vs.filter(function (v) { return /en-AU/i.test(v.lang); })[0] || vs.filter(function (v) { return /en-GB/i.test(v.lang); })[0] || vs[0];
    var queue = this.sources.map(function (s, i) { return [i, s]; }).filter(function (x) { return x[1].text.trim(); });
    if (!queue.length) return;
    this.speaking = true; b.setAttribute("aria-pressed", "true"); b.querySelector("[data-c-listen-label]").textContent = "Stop";
    synth.cancel();
    queue.forEach(function (x, k) {
      var u = new SpeechSynthesisUtterance(x[1].text); u.voice = voice; u.lang = voice.lang; u.rate = Math.max(0.6, Math.min(1.2, self.pace / 150));
      u.onboundary = function (ev) {
        if (ev.name && ev.name !== "word") return;
        var t = x[1].text, s = ev.charIndex, m = /^[^\s]+/.exec(t.slice(s));
        self.now = { si: x[0], s: s, e: s + (ev.charLength || (m ? m[0].length : 1)) }; self.paint();
      };
      if (k === queue.length - 1) u.onend = u.onerror = function () { self.stopListening(); };
      synth.speak(u);
    });
  };
  Coach.prototype.stopListening = function () {
    if (!this.speaking) return;
    this.speaking = false; this.now = null;
    try { window.speechSynthesis.cancel(); } catch (e) { /* nothing to stop */ }
    var b = this.panel.querySelector("[data-coach-listen]");
    b.setAttribute("aria-pressed", "false"); b.querySelector("[data-c-listen-label]").textContent = "Listen";
    this.paint();
  };

  function init() {
    document.querySelectorAll("[data-coach-scope]:not([data-coach-ready])").forEach(function (scope) {
      scope.setAttribute("data-coach-ready", "");
      try { scope._coach = new Coach(scope); } catch (e) { if (window.console) console.error("speech coach", e); }
    });
  }
  window.addEventListener("resize", function () {
    document.querySelectorAll("[data-coach-scope]").forEach(function (s) { if (s._coach) s._coach.sources.forEach(function (src) { s._coach.fit(src); }); });
  });
  window.addEventListener("pagehide", function () { try { window.speechSynthesis.cancel(); } catch (e) { /* none */ } });
  document.addEventListener("DOMContentLoaded", init);
  document.addEventListener("htmx:afterSettle", init);
  if (document.readyState !== "loading") init();
})();
