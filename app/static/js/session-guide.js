/* The Chief of Protocol (D-101, phase 7): the guide who walks a player through The Session before it begins, and
   comments at the big moments. An original character drawn here in SVG, in the board's flat retro poster style,
   with changing expressions (calm, wry, eyebrow, concerned, delighted, thinking), blinking and breathing.

   window.socSession.guide: face(svgEl, expression), portrait(expression) -> SVG element, the expression names. */
(function () {
  "use strict";
  var NS = "http://www.w3.org/2000/svg";

  // Each expression sets the brows, the eyes and the mouth (paths in a 240 x 280 box).
  var FACES = {
    calm:      { browL: "M88 118 Q100 112 112 116", browR: "M128 116 Q140 112 152 118", eyes: "open",  mouth: "M106 168 Q120 174 134 168" },
    wry:       { browL: "M88 116 Q100 111 112 115", browR: "M128 113 Q140 107 152 112", eyes: "open",  mouth: "M106 168 Q122 172 136 162" },
    eyebrow:   { browL: "M88 119 Q100 115 112 118", browR: "M128 108 Q140 100 152 106", eyes: "open",  mouth: "M108 169 L132 169" },
    concerned: { browL: "M88 114 Q100 116 112 121", browR: "M128 121 Q140 116 152 114", eyes: "open",  mouth: "M106 172 Q120 164 134 172" },
    delighted: { browL: "M88 113 Q100 106 112 111", browR: "M128 111 Q140 106 152 113", eyes: "happy", mouth: "M102 164 Q120 182 138 164 Z" },
    thinking:  { browL: "M88 117 Q100 113 112 117", browR: "M128 114 Q140 110 152 116", eyes: "up",    mouth: "M110 170 Q118 168 126 171" }
  };
  var EXPRESSIONS = Object.keys(FACES);

  function el(tag, attrs, parent) {
    var e = document.createElementNS(NS, tag);
    Object.keys(attrs).forEach(function (k) { e.setAttribute(k, attrs[k]); });
    if (parent) parent.appendChild(e);
    return e;
  }

  function portrait(expression, variant) {
    var svg = el("svg", { viewBox: "0 0 240 280", class: "g-face" + (variant ? " " + variant : ""), role: "img",
                          "aria-label": variant === "minister" ? "Your Foreign Minister" : variant === "president" ? "The President of the committee" : "The Chief of Protocol" });
    var pres = variant === "president";
    var defs = el("defs", {}, svg);
    var clip = el("clipPath", { id: "g-oval-" + Math.random().toString(36).slice(2, 8) }, defs);
    el("ellipse", { cx: 120, cy: 140, rx: 108, ry: 128 }, clip);
    // the frame: a UN-blue backdrop with a laurel, inside a brass oval
    var inner = el("g", { "clip-path": "url(#" + clip.id + ")" }, svg);
    el("rect", { x: 0, y: 0, width: 240, height: 280, class: "g-backdrop" }, inner);
    for (var i = 0; i < 9; i++) {
      el("ellipse", { cx: 120, cy: 34, rx: 5, ry: 12, class: "g-laurel", transform: "rotate(" + (-120 + i * 30) + " 120 140)" }, inner);
    }
    var bust = el("g", { class: "g-bust" }, inner);
    // shoulders: a navy suit, white collar, maroon tie and the brass UN pin
    el("path", { d: "M18 290 Q22 222 84 206 L156 206 Q218 222 222 290 Z", class: "g-suit" }, bust);
    el("path", { d: "M98 206 L120 248 L142 206 Z", class: "g-shirt" }, bust);
    el("path", { d: "M114 214 L126 214 L130 262 L120 272 L110 262 Z", class: "g-tie" }, bust);
    el("path", { d: "M84 206 L120 252 L104 290 L70 290 Q66 240 84 206 Z", class: "g-lapel" }, bust);
    el("path", { d: "M156 206 L120 252 L136 290 L170 290 Q174 240 156 206 Z", class: "g-lapel" }, bust);
    el("circle", { cx: 150, cy: 236, r: 7, class: "g-pin" }, bust);
    el("path", { d: "M145 236 H155 M150 231 V241", class: "g-pin-line" }, bust);
    // the head
    el("rect", { x: 104, y: 178, width: 32, height: 34, rx: 10, class: "g-skin" }, bust);
    el("ellipse", { cx: 79, cy: 142, rx: 9, ry: 14, class: "g-skin" }, bust);
    el("ellipse", { cx: 161, cy: 142, rx: 9, ry: 14, class: "g-skin" }, bust);
    el("ellipse", { cx: 120, cy: 138, rx: 42, ry: 52, class: "g-skin" }, bust);
    // silver hair, swept back, with a touch of grey at the temples
    if (pres) {
      // the President: short dark hair swept up at the front, short at the sides
      el("path", { d: "M78 128 Q72 98 86 78 Q102 56 132 56 Q160 58 168 86 Q172 106 162 130 Q160 108 150 100 Q134 92 116 95 Q98 98 88 108 Q81 116 78 128 Z", class: "g-hair" }, bust);
      el("path", { d: "M94 74 Q116 56 146 64", class: "g-hair-line" }, bust);
      el("path", { d: "M90 86 Q112 70 140 76", class: "g-hair-line" }, bust);
      el("path", { d: "M150 68 Q162 78 164 96", class: "g-hair-line" }, bust);
    } else {
      el("path", { d: "M76 132 Q72 84 120 80 Q170 82 164 132 Q160 104 140 98 Q120 92 98 100 Q80 108 76 132 Z", class: "g-hair" }, bust);
      el("path", { d: "M78 128 Q78 116 84 108", class: "g-hair-line" }, bust);
      el("path", { d: "M162 128 Q162 116 156 108", class: "g-hair-line" }, bust);
      el("path", { d: "M92 96 Q112 88 136 92", class: "g-hair-line" }, bust);
    }
    // the face: brows, eyes, nose, mouth and the half-moon glasses
    var face = el("g", { class: "g-features" }, bust);
    el("path", { class: "g-brow", "data-part": "browL" }, face);
    el("path", { class: "g-brow", "data-part": "browR" }, face);
    var eyes = el("g", { class: "g-eyes" }, face);
    el("ellipse", { cx: 101, cy: 132, rx: 4.5, ry: 5.5, class: "g-eye", "data-part": "eyeL" }, eyes);
    el("ellipse", { cx: 139, cy: 132, rx: 4.5, ry: 5.5, class: "g-eye", "data-part": "eyeR" }, eyes);
    el("path", { d: "M95 132 Q101 125 107 132", class: "g-eye-happy", "data-part": "happyL" }, face);
    el("path", { d: "M133 132 Q139 125 145 132", class: "g-eye-happy", "data-part": "happyR" }, face);
    el("path", { d: "M120 136 Q114 152 118 156 Q122 158 126 155", class: "g-nose" }, face);
    el("path", { class: "g-mouth", "data-part": "mouth" }, face);
    if (pres) el("path", { d: "M106 159 Q113 152 120 156 Q127 152 134 159 Q127 162 120 159 Q113 162 106 159 Z", class: "g-moustache" }, face);
    el("path", { d: "M86 136 Q101 150 116 136", class: "g-glasses" }, face);
    el("path", { d: "M124 136 Q139 150 154 136", class: "g-glasses" }, face);
    el("path", { d: "M86 136 L116 136 M124 136 L154 136 M116 137 Q120 133 124 137 M86 136 L78 132 M154 136 L162 132", class: "g-glasses-rim" }, face);
    // the brass oval frame on top
    el("ellipse", { cx: 120, cy: 140, rx: 108, ry: 128, class: "g-frame" }, svg);
    el("ellipse", { cx: 120, cy: 140, rx: 100, ry: 120, class: "g-frame-inner" }, svg);
    face_(svg, expression || "calm");
    return svg;
  }

  function face_(svg, expression) {
    var f = FACES[expression] || FACES.calm;
    var q = function (p) { return svg.querySelector('[data-part="' + p + '"]'); };
    q("browL").setAttribute("d", f.browL);
    q("browR").setAttribute("d", f.browR);
    q("mouth").setAttribute("d", f.mouth);
    q("mouth").setAttribute("class", "g-mouth" + (f.mouth.slice(-1) === "Z" ? " open" : ""));
    var happy = f.eyes === "happy";
    ["eyeL", "eyeR"].forEach(function (p) {
      var e = q(p); e.style.display = happy ? "none" : "";
      e.setAttribute("cy", f.eyes === "up" ? 129 : 132);
      e.setAttribute("ry", f.eyes === "up" ? 4.5 : 5.5);
    });
    ["happyL", "happyR"].forEach(function (p) { q(p).style.display = happy ? "" : "none"; });
    svg.setAttribute("data-expression", expression);
  }

  window.socSession = window.socSession || {};
  window.socSession.guide = { portrait: portrait, face: face_, EXPRESSIONS: EXPRESSIONS };
})();
