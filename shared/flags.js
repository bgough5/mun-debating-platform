// ============================================================
// WHIP COUNT — FLAGS
// Small inline SVG flags for the pack_climate2026 roster (31 countries).
// Inline, not emoji: a lot of Windows configurations still render
// Unicode flag emoji as two-letter codes rather than actual flags, which
// would be worse than no flag at all on school laptops. No CDN, no
// external files — everything here is self-contained markup.
//
// These are deliberately SIMPLIFIED, not vexillologically exact: correct
// base colours and layout, but complex coats of arms / calligraphy are
// reduced to simple shapes (a circle, a star, a mark) rather than
// reproduced in detail. That's the standard, honest trade-off for a small
// inline icon — getting the colours and stripes right is what makes a
// flag recognisable at 20px wide; a precisely-rendered coat of arms
// wouldn't even be legible at that size.
// ============================================================
const Flags = (function () {
  "use strict";

  const CODE_OF = {
    "Australia": "au", "Barbados": "bb", "Brazil": "br", "Canada": "ca",
    "Central African Republic": "cf", "Chile": "cl", "China": "cn", "Costa Rica": "cr",
    "Denmark": "dk", "Egypt": "eg", "Fiji": "fj", "France": "fr",
    "Gambia": "gm", "Germany": "de", "Greece": "gr", "India": "in",
    "Japan": "jp", "Kenya": "ke", "Madagascar": "mg", "Mexico": "mx",
    "Mongolia": "mn", "Morocco": "ma", "Philippines": "ph", "Saudi Arabia": "sa",
    "South Africa": "za", "Spain": "es", "Türkiye": "tr", "Tuvalu": "tv",
    "United Kingdom": "gb", "United States of America": "us", "Vanuatu": "vu",
  };

  // Reusable simplified Union Jack canton (10x7, positioned at 0,0) for the
  // three Pacific/Commonwealth flags that carry it (au, fj, tv).
  const MINI_UJ =
    '<rect width="10" height="7" fill="#00247D"/>' +
    '<path d="M0 0L10 7M10 0L0 7" stroke="#fff" stroke-width="1.2"/>' +
    '<path d="M0 0L10 7M10 0L0 7" stroke="#CF142B" stroke-width="0.5"/>' +
    '<rect x="4.1" y="0" width="1.8" height="7" fill="#fff"/>' +
    '<rect x="0" y="2.9" width="10" height="1.8" fill="#fff"/>' +
    '<rect x="4.5" y="0" width="1" height="7" fill="#CF142B"/>' +
    '<rect x="0" y="3.3" width="10" height="1" fill="#CF142B"/>';

  const BODY = {
    au: `<rect width="24" height="16" fill="#00247D"/>${MINI_UJ}
      <circle cx="18" cy="12" r="1.1" fill="#fff"/>
      <circle cx="21" cy="6.5" r="0.8" fill="#fff"/>
      <circle cx="15" cy="8.5" r="0.8" fill="#fff"/>
      <circle cx="19.5" cy="14.5" r="0.8" fill="#fff"/>
      <circle cx="22" cy="10.5" r="0.6" fill="#fff"/>`,
    bb: `<rect width="8" height="16" fill="#00267F"/><rect x="8" width="8" height="16" fill="#FFC726"/><rect x="16" width="8" height="16" fill="#00267F"/>
      <path d="M12 3v10M10.5 13h3M9.5 15h5" stroke="#000" stroke-width="1"/>`,
    br: `<rect width="24" height="16" fill="#009739"/>
      <path d="M12 2 L22 8 L12 14 L2 8 Z" fill="#FEDD00"/>
      <circle cx="12" cy="8" r="3.2" fill="#012169"/>
      <path d="M8.8 8a3.2 3.2 0 0 1 6.4 0" stroke="#fff" stroke-width="0.5" fill="none"/>`,
    ca: `<rect width="24" height="16" fill="#fff"/><rect width="6" height="16" fill="#D80621"/><rect x="18" width="6" height="16" fill="#D80621"/>
      <path d="M12 4l1 2.4 2.4-1-0.6 2.4 2.2 0.6-1.8 1.6 1 2.2-2.4-0.4 0.2 2.4-1.6-1.6-1.6 1.6 0.2-2.4-2.4 0.4 1-2.2-1.8-1.6 2.2-0.6-0.6-2.4 2.4 1z" fill="#D80621"/>`,
    cf: `<rect width="24" height="4" fill="#003082"/><rect y="4" width="24" height="4" fill="#fff"/><rect y="8" width="24" height="4" fill="#289728"/><rect y="12" width="24" height="4" fill="#FFCE00"/>
      <rect x="10.8" width="2.4" height="16" fill="#D21034"/>
      <path d="M3 1.2l0.5 1.4h1.5l-1.2 0.9 0.5 1.4-1.3-0.9-1.3 0.9 0.5-1.4-1.2-0.9h1.5z" fill="#FFCE00"/>`,
    cl: `<rect width="24" height="8" fill="#fff"/><rect y="8" width="24" height="8" fill="#D52B1E"/>
      <rect width="8" height="8" fill="#0039A6"/>
      <path d="M4 2.4l0.6 1.8h1.9l-1.5 1.1 0.6 1.8-1.6-1.1-1.6 1.1 0.6-1.8-1.5-1.1h1.9z" fill="#fff"/>`,
    cn: `<rect width="24" height="16" fill="#DE2910"/>
      <path d="M5 3l0.7 2.1h2.2l-1.8 1.3 0.7 2.1L5 7.2 3.2 8.5l0.7-2.1L2.1 5.1h2.2z" fill="#FFDE00"/>
      <circle cx="9.5" cy="2" r="0.6" fill="#FFDE00"/><circle cx="11" cy="4" r="0.6" fill="#FFDE00"/>
      <circle cx="11" cy="6.5" r="0.6" fill="#FFDE00"/><circle cx="9.5" cy="8.5" r="0.6" fill="#FFDE00"/>`,
    cr: `<rect width="24" height="16" fill="#002B7F"/><rect y="2.3" width="24" height="11.4" fill="#fff"/><rect y="4.6" width="24" height="6.8" fill="#CE1126"/>`,
    dk: `<rect width="24" height="16" fill="#C60C30"/><rect x="8" width="2.4" height="16" fill="#fff"/><rect y="7" width="24" height="2.4" fill="#fff"/>`,
    eg: `<rect width="24" height="5.33" fill="#CE1126"/><rect y="5.33" width="24" height="5.33" fill="#fff"/><rect y="10.66" width="24" height="5.34" fill="#000"/>
      <circle cx="12" cy="8" r="1.8" fill="#C09300"/>`,
    fj: `<rect width="24" height="16" fill="#68BFE5"/>${MINI_UJ}
      <path d="M17 8l3-2 3 2-1 3h-4z" fill="#fff" stroke="#002868" stroke-width="0.4"/>`,
    fr: `<rect width="8" height="16" fill="#0055A4"/><rect x="8" width="8" height="16" fill="#fff"/><rect x="16" width="8" height="16" fill="#EF4135"/>`,
    gm: `<rect width="24" height="16" fill="#CE1126"/><rect y="5.5" width="24" height="5" fill="#fff"/><rect y="6" width="24" height="4" fill="#0C1C8C"/><rect y="11" width="24" height="5" fill="#3A7728"/>`,
    de: `<rect width="24" height="5.33" fill="#000"/><rect y="5.33" width="24" height="5.33" fill="#DD0000"/><rect y="10.66" width="24" height="5.34" fill="#FFCE00"/>`,
    gr: `<rect width="24" height="16" fill="#0D5EAF"/>
      ${[0,1,2,3,4].map(i=>`<rect y="${1.6*(2*i+1)}" width="24" height="1.6" fill="#fff"/>`).join("")}
      <rect width="9" height="9" fill="#0D5EAF"/><rect x="3.5" width="2" height="9" fill="#fff"/><rect y="3.5" width="9" height="2" fill="#fff"/>`,
    in: `<rect width="24" height="5.33" fill="#FF9933"/><rect y="5.33" width="24" height="5.33" fill="#fff"/><rect y="10.66" width="24" height="5.34" fill="#138808"/>
      <circle cx="12" cy="8" r="2" fill="none" stroke="#000080" stroke-width="0.5"/><circle cx="12" cy="8" r="0.4" fill="#000080"/>`,
    jp: `<rect width="24" height="16" fill="#fff"/><circle cx="12" cy="8" r="4.6" fill="#BC002D"/>`,
    ke: `<rect width="24" height="4.5" fill="#000"/><rect y="4.5" width="24" height="1" fill="#fff"/><rect y="5.5" width="24" height="5" fill="#BB0000"/><rect y="10.5" width="24" height="1" fill="#fff"/><rect y="11.5" width="24" height="4.5" fill="#006600"/>
      <path d="M12 5.5l2.4 1.4v2.6l-2.4 1.4-2.4-1.4V6.9z" fill="#BB0000" stroke="#fff" stroke-width="0.3"/>`,
    mg: `<rect width="8" height="16" fill="#fff"/><rect x="8" width="16" height="8" fill="#FC3D32"/><rect x="8" y="8" width="16" height="8" fill="#007E3A"/>`,
    mx: `<rect width="8" height="16" fill="#006847"/><rect x="8" width="8" height="16" fill="#fff"/><rect x="16" width="8" height="16" fill="#CE1126"/>
      <circle cx="12" cy="8" r="1.6" fill="#8B5E3C"/>`,
    mn: `<rect width="6" height="16" fill="#C4272F"/><rect x="6" width="12" height="16" fill="#015197"/><rect x="18" width="6" height="16" fill="#C4272F"/>
      <path d="M3 3v10M2 4.5h2M2 11.5h2" stroke="#F9CF02" stroke-width="0.8" fill="none"/>`,
    ma: `<rect width="24" height="16" fill="#C1272D"/>
      <path d="M12 5l0.9 2.8h3l-2.4 1.8 0.9 2.8-2.4-1.8-2.4 1.8 0.9-2.8-2.4-1.8h3z" fill="none" stroke="#006233" stroke-width="0.7"/>`,
    ph: `<rect width="24" height="8" fill="#0038A8"/><rect y="8" width="24" height="8" fill="#CE1126"/>
      <path d="M0 0L9 8L0 16Z" fill="#fff"/>
      <circle cx="3" cy="8" r="1.5" fill="#FCD116"/>`,
    sa: `<rect width="24" height="16" fill="#006C35"/>
      <rect x="4" y="10.5" width="15" height="1" fill="#fff"/><path d="M4 10.5l-1.4 0.5 1.4 0.5z" fill="#fff"/>`,
    za: `<path d="M0 0H24V16H0Z" fill="#DE3831"/>
      <path d="M0 0H24V6.4H0Z" fill="#002395"/>
      <path d="M0 0L10 8L0 16Z" fill="#000" stroke="#FFB612" stroke-width="1.2"/>
      <path d="M0 3.2L7 8L0 12.8Z" fill="#fff"/>
      <path d="M0 4.8L5 8L0 11.2Z" fill="#007A4D"/>`,
    es: `<rect width="24" height="16" fill="#AA151B"/><rect y="4" width="24" height="8" fill="#F1BF00"/>`,
    tr: `<rect width="24" height="16" fill="#E30A17"/>
      <circle cx="10" cy="8" r="4" fill="#fff"/><circle cx="11.3" cy="8" r="3.3" fill="#E30A17"/>
      <path d="M15 8l0.7 2.1h2.2l-1.8 1.3 0.7 2.1-1.8-1.3-1.8 1.3 0.7-2.1-1.8-1.3h2.2z" fill="#fff"/>`,
    tv: `<rect width="24" height="16" fill="#38A1DB"/>${MINI_UJ}
      ${[[15,4],[18,3],[21,5],[16,8],[19,7],[22,9],[15,11],[18,12]].map(([x,y])=>`<circle cx="${x}" cy="${y}" r="0.6" fill="#FFCE00"/>`).join("")}`,
    gb: `<rect width="24" height="16" fill="#00247D"/>
      <path d="M0 0L24 16M24 0L0 16" stroke="#fff" stroke-width="2.2"/>
      <path d="M0 0L24 16M24 0L0 16" stroke="#CF142B" stroke-width="0.9"/>
      <rect x="9.6" width="4.8" height="16" fill="#fff"/><rect y="5.6" width="24" height="4.8" fill="#fff"/>
      <rect x="10.6" width="2.8" height="16" fill="#CF142B"/><rect y="6.6" width="24" height="2.8" fill="#CF142B"/>`,
    us: `<rect width="24" height="16" fill="#fff"/>
      ${[0,1,2,3,4,5,6].map(i=>`<rect y="${(16/13)*i}" width="24" height="${16/13}" fill="#B31942"/>`).join("")}
      <rect width="10" height="8.6" fill="#0A3161"/>
      ${[[1.5,1.2],[3.5,1.2],[5.5,1.2],[7.5,1.2],[2.5,2.6],[4.5,2.6],[6.5,2.6],[1.5,4],[3.5,4],[5.5,4],[7.5,4],[2.5,5.4],[4.5,5.4],[6.5,5.4],[1.5,6.8],[3.5,6.8],[5.5,6.8],[7.5,6.8]].map(([x,y])=>`<circle cx="${x}" cy="${y}" r="0.45" fill="#fff"/>`).join("")}`,
    vu: `<path d="M0 0H24V16H0Z" fill="#CE1126"/>
      <path d="M0 0H24V16H0Z" fill="#007A5E" clip-path="url(#vuclip)"/>
      <defs><clipPath id="vuclip"><path d="M0 16L14 8L0 0Z"/></clipPath></defs>
      <path d="M0 6.4L13 8L0 9.6Z" fill="#000" stroke="#FDCE12" stroke-width="0.8"/>
      <circle cx="3.2" cy="8" r="1.1" fill="#FDCE12"/>`,
  };

  function svgFor(countryName, width) {
    const code = CODE_OF[countryName];
    const body = code && BODY[code];
    if (!body) return "";
    width = width || 20;
    const height = Math.round(width * 16 / 24);
    return `<svg class="flag" width="${width}" height="${height}" viewBox="0 0 24 16" xmlns="http://www.w3.org/2000/svg">${body}</svg>`;
  }

  return { CODE_OF, svgFor };
})();
