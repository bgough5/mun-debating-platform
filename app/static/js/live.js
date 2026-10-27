// Live updates. The server sends "channel X changed"; this script asks htmx to
// re-fetch the server-rendered fragments that show channel X. All rendering and
// access checks stay on the server. Without JavaScript, pages still work; they
// just need a reload to show other people's changes.
(function () {
  "use strict";
  var ws = null, channels = [], lastSeq = 0, backoff = 1000, pingTimer = null, wanted = "";
  var pending = new Set(), debounce = {};
  var announceQueue = null, lastAnnounce = 0;

  function projectorToken() { return document.body.getAttribute("data-projector-token") || ""; }

  function scan() {
    var set = {};
    document.querySelectorAll("[data-live-channel]").forEach(function (el) {
      el.getAttribute("data-live-channel").split(" ").forEach(function (c) { if (c) set[c] = 1; });
    });
    return Object.keys(set).sort();
  }

  function status(text, ok) {
    var el = document.getElementById("live-status");
    if (el) { el.textContent = text; el.className = "small " + (ok ? "muted" : "lockline"); }
  }

  function connect() {
    channels = scan();
    wanted = channels.join(" ");
    if (!channels.length) return;
    var proto = location.protocol === "https:" ? "wss:" : "ws:";
    var tok = projectorToken();
    ws = new WebSocket(proto + "//" + location.host + "/ws" + (tok ? "?projector=" + encodeURIComponent(tok) : ""));
    ws.onopen = function () {
      backoff = 1000;
      ws.send(JSON.stringify({ subscribe: channels, since: lastSeq }));
      clearInterval(pingTimer);
      pingTimer = setInterval(function () {
        if (ws && ws.readyState === 1) ws.send(JSON.stringify({ ping: Date.now() / 1000 }));
      }, 20000);
      status("Live", true);
    };
    ws.onmessage = function (ev) {
      var msg = JSON.parse(ev.data);
      if (msg.denied && msg.denied.length) {
        var d = msg.denied[0];
        status("Not live: " + (d.reason || "no access"), false);
      }
      if (msg.subscribed && typeof msg.seq === "number" && !lastSeq) { lastSeq = msg.seq; refreshStale(); }
      if (msg.resync) { refreshAll(); return; }
      if (msg.channels) {
        if (msg.seq > lastSeq) lastSeq = msg.seq;
        msg.channels.forEach(refreshChannel);
      }
    };
    ws.onclose = function () {
      clearInterval(pingTimer);
      status("Reconnecting…", false);
      setTimeout(connect, backoff);
      backoff = Math.min(backoff * 2, 10000);
    };
  }

  // A live region is not refreshed while it holds a form with unsaved typing, or an
  // open paragraph editor, so nobody loses what they are writing.
  function editing(el) {
    return !!el.querySelector("form[data-dirty], details[open] form[data-lock-paragraph]");
  }
  document.addEventListener("input", function (e) {
    var f = e.target && e.target.form;
    if (f && /^(TEXTAREA|INPUT)$/.test(e.target.tagName) && e.target.type !== "hidden") f.setAttribute("data-dirty", "1");
  });
  document.addEventListener("submit", function (e) { if (e.target.removeAttribute) e.target.removeAttribute("data-dirty"); }, true);

  function refreshChannel(c) {
    document.querySelectorAll("[data-live-channel]").forEach(function (el) {
      if (el.getAttribute("data-live-channel").split(" ").indexOf(c) < 0) return;
      refreshEl(el);
    });
  }

  function refreshEl(el) {
    if (editing(el)) {
      pending.add(el);
      status("Other changes will appear when you finish editing", true);
      return;
    }
    // Throttle: refresh at once, then at most every 250 ms while changes keep coming
    // (a burst of 25 votes becomes a few refreshes, and the last one is never skipped).
    var key = el.id || el.getAttribute("hx-get");
    var st = debounce[key] || (debounce[key] = { last: 0, timer: null });
    var wait = 250 - (Date.now() - st.last);
    if (st.timer) return;
    st.timer = setTimeout(function () {
      st.timer = null; st.last = Date.now();
      // The region may have been replaced while we waited (a boosted page swap): refresh the one on the page now,
      // or the update lands in a detached copy and the page stays stale.
      var target = (el.id && document.getElementById(el.id)) || el;
      if (window.htmx && document.body.contains(target)) htmx.trigger(target, "live-update");
    }, Math.max(0, wait));
  }

  // Keep disclosure panels the person opened (“Jump to a stage”, “Propose another motion”) open across a refresh.
  document.addEventListener("htmx:beforeSwap", function (e) {
    var t = e.detail && e.detail.target;
    if (!t || !t.hasAttribute || !t.hasAttribute("data-live-channel")) return;
    t._openPanels = Array.prototype.map.call(t.querySelectorAll("details[open] > summary"), function (s) { return s.textContent.trim(); });
    // Choices made in a drop-down but not yet sent (pick a stage, then Go) survive the refresh too.
    t._choices = {};
    t.querySelectorAll("select[id]").forEach(function (sel) {
      var dflt = Array.prototype.find.call(sel.options, function (o) { return o.defaultSelected; });
      if (sel.value !== (dflt ? dflt.value : sel.options.length ? sel.options[0].value : "")) t._choices[sel.id] = sel.value;
    });
  });
  document.addEventListener("htmx:afterSwap", function (e) {
    var t = e.detail && e.detail.target;
    if (t && t._choices) {
      Object.keys(t._choices).forEach(function (id) {
        var sel = t.querySelector("select#" + CSS.escape(id));
        if (sel && Array.prototype.some.call(sel.options, function (o) { return o.value === t._choices[id]; })) sel.value = t._choices[id];
      });
      t._choices = null;
    }
    if (!t || !t._openPanels || !t._openPanels.length) return;
    t.querySelectorAll("details > summary").forEach(function (s) {
      if (t._openPanels.indexOf(s.textContent.trim()) >= 0) s.parentNode.open = true;
    });
    t._openPanels = null;
  });

  function refreshAll() { document.querySelectorAll("[data-live-channel]").forEach(refreshEl); }

  // A page or fragment rendered before a change we have already been told about is stale: this happens when a
  // live message arrives while a full-page request (a boosted form or link) is in flight. Refresh it once more.
  function refreshStale(root) {
    document.querySelectorAll("[data-live-channel]").forEach(function (el) {
      var mark = el.querySelector("[data-view-seq]");
      if (mark && lastSeq && parseInt(mark.getAttribute("data-view-seq"), 10) < lastSeq) refreshEl(el);
    });
  }

  function flushPending() {
    pending.forEach(function (el) {
      if (!document.body.contains(el)) { pending.delete(el); return; }
      if (!editing(el)) { pending.delete(el); refreshEl(el); }
    });
    if (!pending.size && ws && ws.readyState === 1) status("Live", true);
  }
  setInterval(flushPending, 1000);

  // ---------- polite announcements for screen readers (rate-limited) ----------
  function announce(text) {
    var region = document.getElementById("live-announcer");
    if (!region || !text) return;
    var now = Date.now();
    var wait = Math.max(0, 3000 - (now - lastAnnounce));
    clearTimeout(announceQueue);
    announceQueue = setTimeout(function () { region.textContent = text; lastAnnounce = Date.now(); }, wait);
  }

  var lastAnnounced = {};
  function checkAnnouncements(root) {
    (root || document).querySelectorAll("[data-announce]").forEach(function (el) {
      var key = el.getAttribute("data-announce-key") || "default";
      var text = el.getAttribute("data-announce");
      if (lastAnnounced[key] !== undefined && lastAnnounced[key] !== text) announce(text);
      lastAnnounced[key] = text;
    });
  }

  // ---------- timers ----------
  function fmt(s) {
    var neg = s < 0; s = Math.abs(Math.round(s));
    return (neg ? "−" : "") + Math.floor(s / 60) + ":" + ("0" + (s % 60)).slice(-2);
  }
  function initTimers(root) {
    (root || document).querySelectorAll(".timer[data-remaining]").forEach(function (el) {
      el._base = parseFloat(el.getAttribute("data-remaining"));
      el._at = Date.now() / 1000;
      el._running = el.getAttribute("data-state") === "running";
      el._spoken = {};
    });
  }
  setInterval(function () {
    document.querySelectorAll(".timer[data-remaining]").forEach(function (el) {
      if (el._base === undefined) return;
      var rem = el._running ? el._base - (Date.now() / 1000 - el._at) : el._base;
      var out = el.querySelector(".timer-value") || el;
      out.textContent = fmt(rem);
      el.classList.toggle("low", rem <= 10);
      if (el._running) {
        [60, 30, 10, 0].forEach(function (mark) {
          if (rem <= mark && rem > mark - 1.5 && !el._spoken[mark]) {
            el._spoken[mark] = true;
            var label = el.getAttribute("data-label") || "Timer";
            announce(mark === 0 ? label + ": time is up" : label + ": " + mark + " seconds left");
          }
        });
      }
    });
  }, 250);

  // ---------- paragraph locks (one editor per paragraph) ----------
  function csrf() { var m = document.querySelector('meta[name="csrf-token"]'); return m ? m.content : ""; }
  var heartbeats = {};
  function lockCall(id, action) {
    return fetch("/mun/paragraphs/" + id + "/" + action, { method: "POST", headers: { "X-CSRF-Token": csrf() }, credentials: "same-origin" })
      .then(function (r) { return r.json().then(function (j) { return { status: r.status, body: j }; }); });
  }
  document.addEventListener("toggle", function (e) {
    var det = e.target;
    if (!det || det.tagName !== "DETAILS") return;
    var form = det.querySelector(":scope > form[data-lock-paragraph]");
    if (!form) return;
    var id = form.getAttribute("data-lock-paragraph");
    var msg = form.querySelector(".lock-msg");
    if (!msg) { msg = document.createElement("p"); msg.className = "lock-msg lockline"; msg.setAttribute("role", "status"); form.prepend(msg); }
    if (det.open) {
      lockCall(id, "lock").then(function (r) {
        if (r.status === 409) {
          msg.textContent = r.body.message;
          form.querySelectorAll("textarea, button[type=submit]").forEach(function (x) { x.disabled = true; });
        } else {
          msg.textContent = "You are editing this paragraph. Others see that it is reserved.";
          heartbeats[id] = setInterval(function () { lockCall(id, "lock"); }, 20000);
        }
      });
    } else {
      clearInterval(heartbeats[id]);
      delete heartbeats[id];
      lockCall(id, "unlock");
    }
  }, true);
  window.addEventListener("pagehide", function () {
    Object.keys(heartbeats).forEach(function (id) {
      navigator.sendBeacon && fetch("/mun/paragraphs/" + id + "/unlock", { method: "POST", keepalive: true, headers: { "X-CSRF-Token": csrf() } });
    });
  });

  // ---------- wiring ----------
  function start() {
    initTimers();
    checkAnnouncements();
    if (scan().join(" ") !== wanted) {
      if (ws) { ws.onclose = null; ws.close(); }
      connect();
    }
  }
  document.addEventListener("DOMContentLoaded", start);
  document.addEventListener("htmx:afterSettle", function (e) {
    initTimers(e.target);
    checkAnnouncements(e.target);
    if (scan().join(" ") !== wanted) start();
    refreshStale();
  });
})();
