"""The Session, phase 12 (D-101): how you talk to delegations.

- Pitches: lobbying is a choice of two arguments. Each delegation responds to some arguments more than others, read
  from its dossier and situation (rules of thumb for the game, not claims about any government). A well-matched pitch
  moves it far; a mismatched one barely at all. Country files and advisers tell you what will land.
- Haggling: the deal table runs in rounds. The delegation names a price; holding out brings it down towards its
  walk-away point, but each round risks it walking away, more so when a rival is courting it.
- Compromise with rivals: the same haggling with a rival. Drop the commitment it can't accept, or let its wish into
  the text, and it makes peace: it stops working against you, brings part of its support and co-sponsors.
- One commitments ledger: every promise, favour, pledge, deal vote, secured delegation and truce in one record.
- Unlocks by stage: systems open as the session goes on.

This module uses the engine's own primitives; the engine imports it at the end of its definitions."""
from __future__ import annotations

import random

from app.modules.sim.campaign import content as K
from app.modules.sim.campaign import econ as X
from app.modules.sim.campaign import engine as E

# ---------------------------------------------------------------- unlocks by stage

UNLOCK = {"post": 2, "hire": 2, "deal": 2, "compromise": 2, "attend": 2, "secure": 3, "reserve": 3, "sign": 3}


def locked(g: dict, do: str) -> str | None:
    """Why an action isn't open yet (None when it is). A Quick session has everything from the start."""
    need = UNLOCK.get(do)
    if not need or g.get("length") == "quick" or g.get("phase") != "chapter" or g["chapter"] >= need:
        return None
    return f"That opens in {K.STAGES[need]['name']}."


# ---------------------------------------------------------------- pitches

ARGS = {
    "interest": {"name": "Economic interest", "what": "What it means for their economy: jobs, trade, money."},
    "security": {"name": "Security and stability", "what": "What it means for their safety and for stability in their region."},
    "values": {"name": "Shared values", "what": "Rights, fairness and the kind of world you both want."},
    "precedent": {"name": "Law and precedent", "what": "Treaties, earlier resolutions and the rules everyone signed up to."},
    "region": {"name": "Regional solidarity", "what": "What their neighbours and their regional group are doing."},
}
STRONG, SOME, WEAK = 1.0, 0.5, 0.15


def receptive(scn, g: dict, iso: str) -> dict:
    """How much each argument moves a delegation: its two strongest land fully, the third half, the rest barely."""
    m, t = scn.member(iso), X.traits(iso)
    rng = random.Random(f"{g['seed']}:pitch:{iso}")
    region = m.region if m else ""
    raw = {
        "interest": 1.2 * (t["aid"] or t["low"]) + 0.8 * t["exporter"] + 0.3 * (t["size"] <= 2),
        "security": 1.2 * bool(m and m.p5) + 0.6 * (t["size"] >= 3) + 0.4 * (region == "EEG"),
        "values": 1.0 * t["rich"] + 0.5 * (region == "WEOG"),
        "precedent": 0.6 * t["rich"] + 0.4 * (t["size"] >= 2) + 0.4 * (not t["low"]),
        "region": 1.0 * (region in ("AFR", "GRULAC", "APG")) + 0.5 * (not t["rich"]),
    }
    order = sorted(raw, key=lambda k: -(raw[k] + rng.uniform(0, 0.7)))
    return {k: STRONG if i < 2 else SOME if i == 2 else WEAK for i, k in enumerate(order)}


def listens_to(scn, g: dict, iso: str) -> list[str]:
    r = receptive(scn, g, iso)
    return [ARGS[k]["name"] for k in sorted(r, key=lambda k: (-r[k], k)) if r[k] == STRONG]


def a_lobby(scn, g, a):
    """A pitch: two arguments. Without arguments (older saves, bots) it counts as an average pitch."""
    iso = a.get("iso3")
    E._country(scn, g, iso)
    args = [x for x in dict.fromkeys(a.get("args") or []) if x in ARGS]
    if a.get("args") is not None and len(args) != 2:
        raise E.GameError("Choose two arguments for your pitch.")
    cost = E.lobby_cost(scn, g, iso)
    E._spend(g, 1, cost)
    r = receptive(scn, g, iso)
    quality = sum(r[x] for x in args) / 2 if args else 0.5
    must = g["mandate"]["must"]
    mu = E.mu_of(scn, g, iso, [must])
    if mu <= E.R["redline"]:
        moved = E._sway(g, "you", iso, E.R["redline_step"])
        heard = "That is a red line for us. We won't move on it, though we respect your efforts."
    else:
        moved = E._sway(g, "you", iso, E.R["pitch_step"] * (0.3 + 0.7 * quality))
        heard = (("That argument resonates with us. " if quality >= 0.9 else "Some of that lands with us. " if quality >= 0.5 else
                  "With respect, that isn't what moves our capital. ") if args else "") + E.LINES[E.bucket(mu + g["sway"]["you"][iso])]
    g["region_last"][scn.member(iso).region] = "you"
    E._log(g, "you", f"You pitched to {scn.member(iso).name}" + (": " + " and ".join(ARGS[x]["name"].lower() for x in args) if args else "") + ".",
           "action", iso)
    out = {"heard": heard, "moved": round(moved, 2), "cost": cost, "red_line": mu <= E.R["redline"],
           "landed": {x: ("strong" if r[x] == STRONG else "some" if r[x] == SOME else "weak") for x in args}}
    if g["length"] != "quick" and g["chapter"] >= 2:
        out["leans"] = {scn.member(rv["iso3"]).name: round(E.lean(scn, g, rv["iso3"], iso), 2) for rv in g["rivals"]}
    if g["length"] != "quick" and g["chapter"] >= 3 and E.final_clause(g)["tags"]:
        out["would_vote"] = E.vote_of(scn, E.latent(scn, g, iso, E.final_clause(g), mood=False))
    return out


# ---------------------------------------------------------------- haggling (deals and compromises)

def _courted(scn, g, iso) -> str | None:
    """The rival courting this delegation harder than you are, if any."""
    best = max(g["rivals"], key=lambda r: g["sway"][r["iso3"]].get(iso, 0.0), default=None)
    if best and not best.get("truce") and g["sway"][best["iso3"]].get(iso, 0.0) > max(0.3, g["sway"]["you"].get(iso, 0.0)):
        return best["iso3"]
    return None


def _asks(give: dict, price: float, cap: dict) -> list[str]:
    """What they ask of you for a price: the fewest items that cover it, those your capital minds last."""
    items = sorted(give, key=lambda k: (cap.get(k, 0) < 0, -give[k], k))
    out, total = [], 0.0
    for k in items:
        if total >= price - 1e-9:
            break
        out.append(k)
        total += give[k]
    return out


def _seen_walk(scn, g, iso, walk) -> dict | None:
    """An adviser posted to the delegation reads its walk-away point: exactly at three stars, as a range at two."""
    adv = next((a for a in g.get("staff", []) if a.get("post") == iso), None)
    if not adv:
        return None
    s = E._eff_stars(scn, g, adv, iso)
    if s >= 3:
        return {"by": adv["name"], "exact": round(walk, 1)}
    if s == 2:
        return {"by": adv["name"], "low": round(walk - 0.6, 1), "high": round(walk + 0.6, 1)}
    return None


def _open(g, kind, iso, give_vals, cap, cost, bonus, greed, rival):
    price = round(cost - bonus + greed, 2)
    walk = round(cost - bonus + greed * 0.15, 2)
    talks = {"kind": kind, "iso3": iso, "price": max(0.5, price), "walk": max(0.3, walk), "round": 1,
             "patience": 2 + max(0, g["trust"].get(iso, 0)) if kind == "deal" else 3, "rival_bid": rival,
             "give_vals": give_vals, "cap": cap, "tick": g.get("tick")}
    talks["asks"] = _asks(give_vals, talks["price"], cap)
    g["talks"] = talks
    return talks


def a_deal(scn, g, a):
    """The deal table in rounds. stage "open" (2 actions): choose what you ask for; they name their price.
    stage "offer": offer what you give; they accept, counter or walk. stage "walk": leave the table.
    Without a stage (older callers): open and offer in one go."""
    stage = a.get("stage")
    if stage is None:
        a_deal(scn, g, {**a, "stage": "open"})
        return a_deal(scn, g, {**a, "stage": "offer"})
    if stage == "open":
        iso = a.get("iso3")
        E._country(scn, g, iso)
        name = scn.member(iso).name
        get = [i for i in dict.fromkeys(a.get("get") or []) if isinstance(i, str)]
        if not get:
            raise E.GameError("Choose what you're asking for.")
        if iso in g.setdefault("dealt", []):
            raise E.GameError(f"You've already made a deal with {name} this stage.")
        if g.get("deal_tick") == g.get("tick"):
            raise E.GameError("You've already sat at the deal table this turn.")
        t = E.deal_terms(scn, g, iso)
        if any(i not in t["get"] for i in get):
            raise E.GameError("Part of that isn't on the table any more.")
        if "yes" in get and "abstain" in get:
            get.remove("abstain")
        E._spend(g, E.R["deal_ap"], 0)
        g["deal_tick"] = g.get("tick")
        rival = _courted(scn, g, iso)
        greed = random.Random(f"{g['seed']}:greed:{iso}:{g['chapter']}").uniform(0.8, 1.8) + (0.6 if rival else 0.0)
        talks = _open(g, "deal", iso, t["give"], t["capital"], sum(t["get"][i] for i in get), t["bonus"], greed, rival)
        talks["get"] = get
        talks["clause"] = t["clause"]
        E._log(g, iso, f"{name} named its price" + (f"; {scn.member(rival).name} has been courting it too" if rival else "") + ".", "deal", iso)
        return {"talks": True}
    return _round(scn, g, a, stage)


def a_compromise(scn, g, a):
    """Compromise with a rival, haggled like a deal: you offer to drop the commitment it can't accept, or to let its
    wish into the text; it makes peace and co-sponsors."""
    stage = a.get("stage", "open")
    if stage != "open":
        return _round(scn, g, a, stage)
    iso = a.get("iso3")
    rv = next((r for r in g["rivals"] if r["iso3"] == iso), None)
    if not rv:
        raise E.GameError("Choose a rival delegation.")
    if rv.get("truce"):
        raise E.GameError("You've already made peace with that delegation.")
    if g.get("deal_tick") == g.get("tick"):
        raise E.GameError("You've already sat at the negotiating table this turn.")
    give = compromise_terms(scn, g, rv)
    if not give:
        raise E.GameError("There's nothing on the table to offer it: its red line isn't in the draft, and its wish is already in.")
    E._spend(g, E.R["deal_ap"], 0)
    g["deal_tick"] = g.get("tick")
    base = {"hawk": 2.8, "spoiler": 2.0, "broker": 1.6}.get(rv.get("style", "hawk"), 2.0)   # a hawk needs both concessions
    final = E.final_clause(g)
    losing = final["tags"] and E.projection(scn, g)["passed"] and E.stance(scn, g, iso, final) < 0
    greed = 0.4 + random.Random(f"{g['seed']}:truce:{iso}:{g['chapter']}").uniform(0.0, 0.4)
    talks = _open(g, "rival", iso, give, {k: _concession_cost(g, rv, k) for k in give}, base - (0.6 if losing else 0.0), 0.4, greed, None)
    E._log(g, iso, f"{scn.member(iso).name} agreed to talk, and named its price.", "deal", iso)
    return {"talks": True}


def compromise_terms(scn, g, rv) -> dict:
    tags = {t for c in g["draft"] for t in c["tags"]}
    out = {}
    if rv["block"] in tags:
        out["drop"] = 2.2
    if rv["want"] not in tags and len(g["draft"]) < E.R["draft_max"]:
        out["include"] = 1.6
    return out


def _concession_cost(g, rv, k) -> int:
    m = g["mandate"]
    if k == "drop":
        return -2 if rv["block"] == m["must"] else -1 if rv["block"] == m.get("also") else 0
    return -3 if rv["want"] == m["red"] else 0


def _round(scn, g, a, stage):
    talks = g.get("talks")
    if not talks or talks.get("tick") != g.get("tick"):
        raise E.GameError("There are no talks open. Open them at the table first.")
    iso, name = talks["iso3"], scn.member(talks["iso3"]).name
    if stage == "walk":
        g["talks"] = None
        if talks["kind"] == "deal":
            g.setdefault("dealt", []).append(iso)
        E._log(g, "you", f"You left the table with {name}.", "deal", iso)
        return {"walked": "you"}
    if stage != "offer":
        raise E.GameError("Make an offer, or leave the table.")
    give = [i for i in dict.fromkeys(a.get("give") or []) if i in talks["give_vals"]]
    if not give:
        raise E.GameError("Put something on your side of the table.")
    value = round(sum(talks["give_vals"][i] for i in give), 2)
    if value >= talks["price"] - 1e-9:
        g["talks"] = None
        return _close(scn, g, talks, give)
    rng = random.Random(f"{g['seed']}:round:{iso}:{g.get('tick')}:{talks['round']}")
    insult = value < talks["walk"]
    talks["patience"] -= 2 if insult else 1
    risk = 0.12 * talks["round"] + (0.2 if talks.get("rival_bid") else 0.0) - 0.05 * g["trust"].get(iso, 0)
    if talks["patience"] <= 0 or rng.random() < max(0.0, risk):
        g["talks"] = None
        if talks["kind"] == "deal":
            g.setdefault("dealt", []).append(iso)
        E._log(g, iso, f"{name} walked away from the table." + (f" {scn.member(talks['rival_bid']).name}'s offer looked better." if talks.get("rival_bid") else ""),
               "deal", iso)
        return {"walked": "them"}
    old = talks["price"]
    new = max(talks["walk"], min(old - 0.1, (old + value) / 2 + 0.1)) if not insult else old - 0.25 * (old - talks["walk"])
    talks["price"] = round(max(talks["walk"], min(old, new)), 2)              # holding out only ever brings it down
    if talks.get("rival_bid") and rng.random() < 0.3:
        talks["price"] = round(talks["price"] + 0.5, 2)
        E._log(g, talks["rival_bid"], f"{scn.member(talks['rival_bid']).name} sweetened its own offer to {name}.", "rival", iso)
    talks["round"] += 1
    talks["asks"] = _asks(talks["give_vals"], talks["price"], talks["cap"])
    E._log(g, iso, f"{name} came down: " + ("it took that as an insult, but it's still talking." if insult else "a counter-offer is on the table."), "deal", iso)
    return {"counter": talks["price"], "was": old, "insulted": insult}


def _close(scn, g, talks, give):
    iso, name = talks["iso3"], scn.member(talks["iso3"]).name
    saved = round(talks["give_vals"] and (sum(talks["give_vals"][i] for i in talks["asks"]) - sum(talks["give_vals"][i] for i in give)), 2)
    if talks["kind"] == "rival":
        return _make_peace(scn, g, talks, give)
    if "funding" in give:
        E._spend(g, 0, E.R["deal_funding"])
    g.setdefault("dealt", []).append(iso)
    for i in give:
        if i == "funding":
            g["pledged"] = g.get("pledged", 0) + 1
        elif i == "trade":
            g["trade_deals"] = g.get("trade_deals", 0) + 1
        elif i == "candidacy":
            g.setdefault("candidacies", []).append(iso)
        elif i == "clause" and talks.get("clause"):
            g["promises"].append({"iso3": iso, "clause": talks["clause"], "kept": None})
    for i in talks["get"]:
        if i in ("yes", "abstain"):
            g.setdefault("deal_votes", {})[iso] = i
        elif i == "sponsor":
            g["sponsors"].append(iso)
        elif i == "influence":
            g["influence"] += E.R["deal_influence"]
        elif i == "intel":
            hit = next(((k, v) for k, v in g.get("intent", {}).items() if v), None)
            if hit:
                E._log(g, iso, f"{name} tells you: {scn.member(hit[0]).name} will go after "
                               f"{E._target_name(scn, g, hit[1]['kind'], hit[1]['target'])} next.", "intel", hit[0])
    g["trust"][iso] = min(E.R["trust_max"], g["trust"][iso] + 1)
    E._sway(g, "you", iso, 0.2)
    g["deals"] = g.get("deals", 0) + 1
    g["table_deals"] = g.get("table_deals", 0) + 1
    g["held_out"] = g.get("held_out", 0) + (1 if talks["round"] > 1 else 0)
    E._log(g, "you", f"You made a deal with {name}" + (f" after {talks['round']} rounds" if talks["round"] > 1 else "") + ": "
           + ", ".join(K.DEAL_GIVE[i]["name"].lower() for i in give) + " for " + ", ".join(K.DEAL_GET[i]["name"].lower() for i in talks["get"]) + ".", "deal", iso)
    for i in give:
        if talks["cap"].get(i):
            E._capital(scn, g, talks["cap"][i], E.CAPITAL_WHY.get(i, "Your capital doesn't like that deal."))
    return {"deal": True, "rounds": talks["round"], "saved": saved}


def _make_peace(scn, g, talks, give):
    iso = talks["iso3"]
    rv = next(r for r in g["rivals"] if r["iso3"] == iso)
    name = scn.member(iso).name
    if "drop" in give:
        for c in list(g["draft"]):
            if rv["block"] in c["tags"]:
                new = [t for t in c["tags"] if t != rv["block"]]
                E._break_promises_if_changed(scn, g, c, new)
                if new:
                    c["tags"] = new
                    if "you" not in c["amended_by"]:
                        c["amended_by"].append("you")
                else:
                    g["draft"].remove(c)
                    g["struck"].append({**c, "by": "you"})
    if "include" in give:
        card = next((c for c in scn.cards if c["id"] in g["cards"] and rv["want"] in c["tags"]), None)
        text, tags = (card["text"], list(card["tags"])) if card else (scn.tags[rv["want"]] + ".", [rv["want"]])
        if card:
            g["cards"].remove(card["id"])
        g["draft"].append({"id": f"p{g['next_id']}", "text": text, "tags": tags, "author": iso, "amended_by": ["you"], "merged": True})
        g["next_id"] += 1
    rv["truce"] = True
    for i in list(g["sway"][iso]):
        moved = g["sway"][iso][i] * 0.5
        if moved > 0:
            E._sway(g, "you", i, moved)
        g["sway"][iso][i] = 0.0
    if iso not in g["sponsors"]:
        g["sponsors"].append(iso)
    g["truces"] = g.get("truces", 0) + 1
    E._log(g, "you", f"You made peace with {name}: a merged text, which it co-sponsors. Its supporters come part of the way with it.", "good", iso)
    for k in give:
        if talks["cap"].get(k):
            E._capital(scn, g, talks["cap"][k], "You gave a rival part of what your capital sent you to win." if k == "drop"
                       else "You let our red line into the text to buy a rival's support.")
    return {"peace": True, "rounds": talks["round"]}


def talks_view(scn, g) -> dict | None:
    t = g.get("talks")
    if not t or t.get("tick") != g.get("tick") or g["phase"] != "chapter":
        return None
    labels = K.DEAL_GIVE if t["kind"] == "deal" else K.TRUCE_GIVE
    return {"kind": t["kind"], "iso3": t["iso3"], "name": scn.member(t["iso3"]).name, "price": t["price"], "round": t["round"],
            "patience": max(0, t["patience"]), "asks": t["asks"], "get": t.get("get", []), "rival_bid": scn.member(t["rival_bid"]).name if t.get("rival_bid") else None,
            "give": {k: {"value": v, "capital": t["cap"].get(k, 0), **labels[k]} for k, v in t["give_vals"].items()},
            "walk_seen": _seen_walk(scn, g, t["iso3"], t["walk"])}


# ---------------------------------------------------------------- one commitments ledger

def ledger(scn, g, iso: str | None = None) -> list[dict]:
    """Every commitment between you and a delegation: what was agreed, and (after the vote) whether it held."""
    f = (g.get("summit") or {}).get("final") or {}
    votes = f.get("votes") or {}
    out = []

    def add(who, what, kind, kept=None):
        if iso is None or who == iso:
            out.append({"iso3": who, "name": scn.member(who).name, "what": what, "kind": kind, "kept": kept})
    for p in g["promises"]:
        add(p["iso3"], "you promised to back a clause", "promise", {True: True, False: False}.get(p["kept"]))
    for i in g.get("favours", []):
        add(i, "it owes you a favour", "favour")
    for i in g.get("pledges", []):
        add(i, "it pledged to abstain rather than veto", "pledge", None if not votes else votes.get(i) != "no")
    for i, v in (g.get("deal_votes") or {}).items():
        add(i, f"a deal: it votes {v} on the whole text", "deal", None if not votes else (votes.get(i) == v or (v == "abstain" and votes.get(i) != "no")))
    for i in g.get("secured", []):
        add(i, "it signed a commitment to your draft", "secured")
    for rv in g["rivals"]:
        if rv.get("truce"):
            add(rv["iso3"], "peace: a merged text it co-sponsors", "truce", None if not votes else votes.get(rv["iso3"]) != "no")
    return out


# ---------------------------------------------------------------- bots

def bot_args(scn, g, iso, rng, competent: bool) -> list[str]:
    if not competent:
        return rng.sample(sorted(ARGS), 2)
    if iso in g["read"] or any(a.get("post") == iso for a in g.get("staff", [])):
        r = receptive(scn, g, iso)
        return sorted(r, key=lambda k: (-r[k], k))[:2]
    t = X.traits(iso)
    return ["interest" if (t["aid"] or t["low"] or t["exporter"]) else "precedent", "region" if not t["rich"] else "values"]
