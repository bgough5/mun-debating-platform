"""Bots that play The Session, for measuring balance (tools/campaign_sim.py). Each plays one style well enough to
test whether that style can win its own victory path; `random` is the baseline. Bots see only what a player could:
countries' modelled positions and the game's visible effects, never a delegation's hidden mood (unless they've
unlocked Read the room and read its file, which shows the mood to a player too)."""
from __future__ import annotations

import random

from app.modules.mun.worldmap import REGIONS
from app.modules.sim.campaign import content as K
from app.modules.sim.campaign import engine as E
from app.modules.sim.campaign import talks as T
from app.modules.sim.campaign import visits as VI

STYLES = {"hardliner": "mandate", "broker": "consensus", "drafter": "architect", "analyst": "kingmaker", "random": None}
BRANCH = {"hardliner": ["point_of_order", "division", "bloc_whip"], "broker": ["bloc_whip", "back_channel", "friendly"],
          "drafter": ["friendly", "merge", "point_of_order"], "analyst": ["read_room", "rival_intel", "friendly"],
          "random": list(K.SKILLS)}


class Bot:
    def __init__(self, scn, style: str, seed: int, skill: float = 0.85):
        self.scn, self.style, self.rng, self.skill = scn, style, random.Random(f"bot:{style}:{seed}"), skill

    # ---------------- what a player can estimate
    def est(self, g, iso, clause, my=None) -> str:
        st = {a: E.stance(self.scn, g, a, clause) for a in ["you", *[r["iso3"] for r in g["rivals"]]]}
        if my is not None:
            st["you"] = my
        x = E.latent(self.scn, g, iso, clause, st, mood=False)
        if "read_room" in g["skills"] and iso in g["read"]:
            x += 0.5 * self.scn.dist(clause["tags"]).get(iso, (0, 1))[1] * g["moods"].get(iso, 0)
        return E.vote_of(self.scn, x)

    def est_yes(self, g, clause, my=1) -> int:
        return sum(1 for i in self.scn.isos if i not in E._others(g) and self.est(g, i, clause, my) == "yes")

    def final_clause(self, g) -> dict:
        return {"id": "final", "tags": list(dict.fromkeys(t for c in g["draft"] for t in c["tags"])), "author": "draft"}

    def free(self, g) -> list[str]:
        return [i for i in self.scn.isos if i not in E._others(g)]

    # ---------------- playing
    def play(self, g: dict) -> dict:
        guard = 0
        while g["phase"] != "done" and guard < 2000:
            guard += 1
            g = self.turn(g) if g["phase"] == "chapter" else self.summit(g)
        return g

    def likely_refused(self, g, action) -> bool:
        """Would the working group refuse this change, as far as a player can tell (moods unknown)?"""
        if action["do"] not in ("amend", "strike") or self.style == "random":
            return False
        c = next((c for c in g["draft"] if c["id"] == action.get("clause")), None)
        if not c or (action["do"] == "amend" and c["author"] == "you"):
            return False
        if action["do"] == "strike":
            yes = self.est_yes(g, c, E.stance(self.scn, g, "you", c))
            return yes * 2 > len(self.scn.members)
        tags = [t for t in c["tags"] if t != action.get("remove")] + ([action["add"]] if action.get("add") else [])
        return self.est_yes(g, {**c, "tags": tags}, E.stance(self.scn, g, "you", {**c, "tags": tags})) <             self.est_yes(g, c, E.stance(self.scn, g, "you", c))

    def act(self, g, action) -> tuple[dict, bool]:
        if action.get("do") == "lobby" and "args" not in action:      # a talk, as a player has it (8 Nov 2026)
            return self.talk(g, action["iso3"])
        if self.likely_refused(g, action):
            return g, False
        try:
            g2, _ = E.apply(self.scn, g, action)
            return g2, True
        except E.GameError:
            return g, False

    def talk(self, g, iso) -> tuple[dict, bool]:
        """Open with the argument most likely to land (one not used with them before, if there is a choice), then
        read their reaction as a player would: press a point that lands, or turn to the next best."""
        competent = self.style != "random"
        args = T.bot_args(self.scn, g, iso, self.rng, competent)
        if competent and T._used(g, iso, args[0]) > T._used(g, iso, args[1]):
            args = [args[1], args[0]]
        felt = T.receptive(self.scn, g, iso)[args[0]] * T.REPEAT ** T._used(g, iso, args[0])   # what the reply gives away
        try:
            g2, out = E.apply(self.scn, g, {"do": "talk", "step": "open", "iso3": iso, "arg": args[0]})
        except E.GameError:
            return g, False
        codes = [o["code"] for o in out["conv"]["options"]]
        if not competent:
            choice = self.rng.choice(codes)
        elif felt >= 0.9:
            choice = "press"
        elif "switch:" + args[1] in codes:
            choice = "switch:" + args[1]
        else:
            choice = "close"
        g3, _ = E.apply(self.scn, g2, {"do": "talk", "step": "follow", "choice": choice})
        return g3, True

    def turn(self, g: dict) -> dict:
        if g.get("question"):
            q = next(q for q in K.QUESTIONS if q["id"] == g["question"])
            right = self.rng.random() < (self.skill if self.style != "random" else 0.34)
            g, _ = self.act(g, {"do": "answer", "option": q["answer"] if right else (q["answer"] + 1) % len(q["options"])})
        for v in [v for v in g.get("visits", []) if v["kind"] == "offer"]:
            o = next((x for x in g.get("offers", []) if x["id"] == v["offer"]), None)
            if o:
                g, _ = self.act(g, {"do": "visit", "id": v["id"], "choice": "accept" if self.take(g, o) else "refuse"})
        if g["phase"] == "chapter" and g["ap"] >= 2:
            g = self.try_deal(g)
        if g["phase"] == "chapter" and g["ap"] >= 2:
            g = self.try_peace(g)
        if g["phase"] != "chapter":
            return g
        g = self.stage_choice(g)
        if g["phase"] != "chapter":
            return g
        m = g.get("meeting")
        if m and g["ap"] >= 2 and g["influence"] >= 2 and g["endorse"].get(m) != "you" and                 (self.style in ("broker", "analyst") or self.rng.random() < 0.5):
            g, _ = self.act(g, {"do": "attend"})
        tries = 0
        while g["ap"] > 0 and tries < 12:
            tries += 1
            done = False
            for action in self.options(g):
                g, ok = self.act(g, action)
                if ok:
                    done = True
                    break
            if not done:
                break
        g = self.stage_choice(g)
        if g["phase"] != "chapter":
            return g
        for act in list(VI.bot_answer(g, self.rng, self.style != "random")):
            g, _ = self.act(g, act)
        if g["ap"] > 0 and self.style != "random" and not g.get("reserve"):
            g, _ = self.act(g, {"do": "reserve"})          # keep the last action back to answer a rival
        g, _ = self.act(g, {"do": "end_turn"})
        return g

    def stage_choice(self, g):
        """At a breakthrough: move on now (momentum) or keep working. A competent bot moves on, except from the last
        stage while the vote is still close; the random bot tosses a coin."""
        ch = str(g["chapter"])
        if g["phase"] != "chapter" or ch not in g.get("breakthroughs", {}) or g.get("stayed", {}).get(ch):
            return g
        if self.style == "random":
            go = self.rng.random() < 0.5
        else:
            last = g["chapter"] == E.LENGTHS[g["length"]]["chapters"]
            p = E.projection(self.scn, g)
            go = not last or (p["passed"] and p["yes"] - p["no"] >= 2 and (self.style != "analyst" or len(g["whip"]) >= 8))
        g, _ = self.act(g, {"do": "advance" if go else "stay"})
        return g

    def try_deal(self, g):
        """Buy a wavering delegation's yes at the deal table with what costs the capital nothing. The random bot
        makes random deals, so the capital's anger is exercised too."""
        if self.style == "random":
            if self.rng.random() < 0.25:
                iso = self.rng.choice(self.free(g))
                t = E.deal_terms(self.scn, g, iso)
                if t["give"] and t["get"] and not t["done"]:
                    give = self.rng.sample(sorted(t["give"]), k=min(2, len(t["give"])))
                    get = [self.rng.choice(sorted(t["get"]))]
                    g, ok = self.act(g, {"do": "deal", "stage": "open", "iso3": iso, "get": get})
                    if ok:
                        g, _ = self.act(g, {"do": "deal", "stage": "offer", "give": give})
            return g
        proj = E.projection(self.scn, g)
        if proj["passed"] and proj["yes"] - proj["no"] > 2:
            return g                                          # no need to buy votes
        best = None
        veto = set(self.scn.rule.veto)
        for iso in self.free(g):
            t = E.deal_terms(self.scn, g, iso)
            ask = "abstain" if iso in veto and proj["votes"].get(iso) == "no" and "abstain" in t["get"] else "yes"
            cost = t["get"].get(ask)
            if t["done"] or not cost or cost <= 0.6 or cost > 3.5:
                continue
            gives, score = [], t["bonus"] - cost
            for item in sorted(t["give"], key=lambda i: (-t["give"][i], i)):
                if t["capital"].get(item, 0) < 0 or (item == "funding" and g["influence"] < 5):
                    continue
                gives.append(item)
                score += t["give"][item]
                if score >= 0.2:
                    break
            if score >= 0.2 and (best is None or len(gives) < len(best[1])):
                best = (iso, gives, ask)
        if best:
            g = self.haggle(g, {"do": "deal", "stage": "open", "iso3": best[0], "get": [best[2]]})
        return g

    def haggle(self, g, opening):
        """Open talks, then pay their price, or hold out once first (analysts and brokers), never with items the
        capital minds."""
        g, ok = self.act(g, opening)
        for rnd in range(3):
            t = g.get("talks")
            if not ok or not t:
                return g
            safe = [k for k in t["asks"] if t["cap"].get(k, 0) >= 0]
            if len(safe) < len(t["asks"]):
                g, _ = self.act(g, {"do": opening["do"], "stage": "walk"})
                return g
            if rnd == 0 and len(safe) > 1 and self.style in ("analyst", "broker"):
                safe = safe[:-1]                                  # hold out: offer a little less
            g, ok = self.act(g, {"do": opening["do"], "stage": "offer", "give": safe})
        return g

    def try_peace(self, g):
        """Brokers and analysts make peace with a rival when it costs the capital nothing."""
        if self.style not in ("broker", "analyst") or g["ap"] < 2 or g.get("length") != "quick" and g["chapter"] < 2:
            return g
        for rv in g["rivals"]:
            if rv.get("truce"):
                continue
            terms = T.compromise_terms(self.scn, g, rv)
            if any(T._concession_cost(g, rv, k) >= 0 for k in terms):
                return self.haggle(g, {"do": "compromise", "iso3": rv["iso3"]})
        return g

    def take(self, g, o) -> bool:
        """Whether to accept an offer at the door: never one that ties you to your red line."""
        if self.style == "random":
            return self.rng.random() < 0.5
        if o["kind"] == "trade":                                   # a trade: worth it for a vote, if the capital won't mind
            return o["get"][0] in ("yes", "abstain", "sponsor", "commit") and not o.get("cap") and \
                ("influence" not in o["give"] or g["influence"] >= 6) and ("standing" not in o["give"] or g["respect"] >= 5)
        if o["kind"] == "back":
            c = next((x for x in g["draft"] if x["id"] == o["clause"]), None)
            return bool(c) and g["mandate"]["red"] not in c["tags"]
        if o["kind"] == "drop":
            return o["tag"] not in (g["mandate"]["must"], g["mandate"].get("also"))
        return g["influence"] >= 4

    def options(self, g) -> list[dict]:
        return getattr(self, "opt_" + self.style)(g)

    # ---- shared building blocks
    def ensure_must(self, g) -> list[dict]:
        must, red = g["mandate"]["must"], g["mandate"]["red"]
        out = []
        if not any(must in c["tags"] for c in g["draft"]):
            card = next((c for c in self.scn.cards if c["id"] in g["cards"] and must in c["tags"] and red not in c["tags"]), None)
            if card:
                out.append({"do": "propose", "card": card["id"]})
            for c in sorted(g["draft"], key=lambda c: len(c["tags"])):
                if red not in c["tags"]:
                    out.append({"do": "amend", "clause": c["id"], "add": must})
        for c in g["draft"]:
            if red in c["tags"]:
                out.append({"do": "amend", "clause": c["id"], "remove": red} if len(c["tags"]) > 1 else {"do": "strike", "clause": c["id"]})
        also = g["mandate"].get("also")
        if also and not any(also in c["tags"] for c in g["draft"]):
            card = next((c for c in self.scn.cards if c["id"] in g["cards"] and also in c["tags"] and red not in c["tags"]), None)
            if card:
                out.append({"do": "propose", "card": card["id"]})
            for c in sorted(g["draft"], key=lambda c: len(c["tags"])):
                if red not in c["tags"] and len(c["tags"]) < 3:
                    out.append({"do": "amend", "clause": c["id"], "add": also})
        return out

    def veto_proof(self, g) -> list[dict]:
        """Where a permanent member would veto a clause, bundle in a commitment it wants (so it abstains instead)."""
        out = []
        if not self.scn.rule.veto:
            return out
        for c in g["draft"]:
            if E.stance(self.scn, g, "you", c) < 0:
                continue
            for p5 in sorted(self.scn.rule.veto):
                if p5 in E._others(g) or self.est(g, p5, c) != "no":
                    continue
                likes = sorted((t for t in self.scn.tags if t not in c["tags"] and t != g["mandate"]["red"]),
                               key=lambda t: -self.scn.dist([t]).get(p5, (0, 1))[0])
                if p5 not in g.get("pledges", []):
                    out.append({"do": "abstain", "iso3": p5})
                    liked = [x for x in g["draft"] if self.scn.dist(x["tags"]).get(p5, (0, 1))[0] >= 0.4
                             and E.stance(self.scn, g, "you", x) >= 0]
                    if liked and not any(pr["iso3"] == p5 and pr["kept"] is None for pr in g["promises"]):
                        out.append({"do": "promise", "iso3": p5, "clause": liked[0]["id"]})
                if likes and len(c["tags"]) < 3:
                    out.append({"do": "amend", "clause": c["id"], "add": likes[0]})
                out.append({"do": "lobby", "iso3": p5})
                break
        return out

    def sign_up(self, g) -> list[dict]:
        if g["chapter"] != E.LENGTHS[g["length"]]["chapters"]:
            return []
        need = E._signers_needed(self.scn)
        if len(g["sponsors"]) >= E.R["sponsors"] and len(g["sponsors"]) + len(g["signatories"]) >= need:
            return []
        pool = sorted((i for i in self.free(g) if i not in g["sponsors"] and i not in g["signatories"]),
                      key=lambda i: -E.lean(self.scn, g, "you", i))
        out = []
        for i in pool[:4]:
            role = "sponsor" if len(g["sponsors"]) < E.R["sponsors"] else "signatory"
            out.append({"do": "sign", "iso3": i, "role": role})
            if role == "sponsor":
                out.append({"do": "sign", "iso3": i, "role": "signatory"})
        return out

    def swing_targets(self, g, clause, my=1) -> list[str]:
        want = "yes" if my > 0 else "no"
        out = []
        for i in self.free(g):
            if self.est(g, i, clause, my) == want or g["sway"]["you"][i] >= E.R["sway_cap"]:
                continue
            st = {a: E.stance(self.scn, g, a, clause) for a in ["you", *[r["iso3"] for r in g["rivals"]]]}
            st["you"] = my
            gap = abs(E.latent(self.scn, g, i, clause, st, mood=False) - (self.scn.c_yes if my > 0 else self.scn.c_no))
            out.append((gap + 0.2 * E.lobby_cost(self.scn, g, i), i))
        return [i for _, i in sorted(out)]

    def lobby_list(self, g, clause, n=3) -> list[dict]:
        out = []
        for i in self.swing_targets(g, clause)[:n]:
            if i not in g["read"] and self.style in ("hardliner", "analyst") and len(g["read"]) < 6:
                out.append({"do": "read", "iso3": i})
            out.append({"do": "lobby", "iso3": i})
        return out

    def must_clause(self, g):
        must = g["mandate"]["must"]
        return next((c for c in g["draft"] if must in c["tags"]), None)

    def promises(self, g) -> list[dict]:
        out = []
        open_ = {p["iso3"] for p in g["promises"] if p["kept"] is None}
        for c in g["draft"]:
            if E.stance(self.scn, g, "you", c) < 0:
                continue
            for i in self.free(g):
                if i not in open_ and self.scn.dist(c["tags"]).get(i, (0, 1))[0] >= 0.4:
                    out.append({"do": "promise", "iso3": i, "clause": c["id"]})
        return out[:3]

    # ---- styles
    def opt_hardliner(self, g):
        out = self.ensure_must(g) + self.veto_proof(g) + self.sign_up(g)
        mc = self.must_clause(g)
        if mc:
            out += self.lobby_list(g, mc)
        out += self.promises(g)[:1]
        return out

    def popular_card(self, g):
        must, red = g["mandate"]["must"], g["mandate"]["red"]
        best = None
        for c in self.scn.cards:
            if c["id"] not in g["cards"] or red in c["tags"]:
                continue
            y = self.est_yes(g, {"id": "x", "tags": c["tags"], "author": "you"})
            key = (y + (2 if must in c["tags"] else 0), c["id"])
            if not best or key > best[0]:
                best = (key, c)
        return best[1] if best else None

    def divisive(self, g):
        worst = None
        for c in g["draft"]:
            if len(c["tags"]) < 2:
                continue
            for t in c["tags"]:
                if t == g["mandate"]["must"]:
                    continue
                trial = {**c, "tags": [x for x in c["tags"] if x != t]}
                gain = self.est_yes(g, trial) - self.est_yes(g, c)
                if gain > 0 and (not worst or gain > worst[0]):
                    worst = (gain, {"do": "amend", "clause": c["id"], "remove": t})
        return [worst[1]] if worst else []

    def opt_broker(self, g):
        out = []
        if not any(c["author"] == "you" for c in g["draft"]) or len(g["draft"]) < 4:
            card = self.popular_card(g)
            if card:
                out.append({"do": "propose", "card": card["id"]})
        out += [a for a in self.ensure_must(g) if a["do"] != "strike"][:1]
        out += self.veto_proof(g) + self.divisive(g) + self.sign_up(g)
        regions = []
        for reg in sorted({m.region for m in self.scn.members if m.region in REGIONS}):
            if E._region_members(self.scn, reg) and g["endorse"].get(reg) != "you":
                close = sum(1 for i in E._region_members(self.scn, reg) if i not in E._others(g) and 0 <= E.lean(self.scn, g, "you", i) <= E.R["lean_min"] + 0.1)
                regions.append((-close, reg))
        for _, reg in sorted(regions)[:1]:
            near = sorted((i for i in E._region_members(self.scn, reg) if i not in E._others(g)), key=lambda i: abs(E.lean(self.scn, g, "you", i) - E.R["lean_min"]))
            out += [{"do": "lobby", "iso3": i} for i in near[:2]]
        out += self.promises(g)
        fc = self.final_clause(g)
        out += self.lobby_list(g, fc)
        return out

    def opt_drafter(self, g):
        out = []
        own = sum(1 for c in g["draft"] if c["author"] == "you")
        if own * 2 <= len(g["draft"]) + 1:
            card = self.popular_card(g)
            if card:
                out.append({"do": "propose", "card": card["id"]})
        out += self.ensure_must(g)[:1] + self.veto_proof(g)
        if "merge" in g["skills"]:
            mine = [c for c in g["draft"] if c["author"] == "you"]
            others = [c for c in g["draft"] if c["author"] != "you"]
            for a in mine:
                for b in others:
                    if len(set(a["tags"]) | set(b["tags"])) <= 3:
                        out.append({"do": "merge", "a": a["id"], "b": b["id"]})
        for c in g["draft"]:
            if c["author"] != "you" and "you" not in c["amended_by"]:
                for t in self.scn.tags:
                    if t not in c["tags"] and t != g["mandate"]["red"] and len(c["tags"]) < 3:
                        trial = {**c, "tags": c["tags"] + [t]}
                        if self.est_yes(g, trial) >= self.est_yes(g, c):
                            out.append({"do": "amend", "clause": c["id"], "add": t})
                            break
        out += self.sign_up(g)
        for c in [c for c in g["draft"] if c["author"] == "you"][:2]:
            out += self.lobby_list(g, c, 2)
        return out

    def opt_analyst(self, g):
        out = self.sign_up(g)
        fc = self.final_clause(g)
        last = g["chapter"] == E.LENGTHS[g["length"]]["chapters"] and g["turn"] >= E.turns_now(g) - 1
        unread = [i for i in self.free(g) if i not in g["read"]]
        if unread and len(g["read"]) < 8:
            out.append({"do": "read", "iso3": unread[0]})
        if last or len(g["whip"]) < 4:
            for i in self.free(g):
                v = self.est(g, i, fc)
                if g["whip"].get(i) != v:
                    out.append({"do": "whip", "iso3": i, "vote": v})
        out += self.promises(g)
        out += self.ensure_must(g)[:1]
        if not any(c["author"] == "you" for c in g["draft"]):
            card = self.popular_card(g)
            if card:
                out.append({"do": "propose", "card": card["id"]})
        out += self.lobby_list(g, fc, 2)
        return out

    def opt_random(self, g):
        isos = self.free(g)
        draft = g["draft"]
        acts = [{"do": "lobby", "iso3": self.rng.choice(isos)}, {"do": "read", "iso3": self.rng.choice(isos)},
                {"do": "whip", "iso3": self.rng.choice(isos), "vote": self.rng.choice(E.VOTES)},
                {"do": "sign", "iso3": self.rng.choice(isos), "role": self.rng.choice(["sponsor", "signatory"])}]
        if g["cards"]:
            acts.append({"do": "propose", "card": self.rng.choice(g["cards"])})
        if draft:
            c = self.rng.choice(draft)
            acts += [{"do": "strike", "clause": c["id"]}, {"do": "amend", "clause": c["id"], "add": self.rng.choice(list(self.scn.tags))},
                     {"do": "promise", "iso3": self.rng.choice(isos), "clause": c["id"]}]
        self.rng.shuffle(acts)
        return acts

    # ---------------- the summit
    def summit(self, g: dict) -> dict:
        s = g["summit"]
        if s["step"] == "speech":
            stance = {"hardliner": "firm", "broker": "bridge", "drafter": "open", "analyst": "open"}.get(self.style) or self.rng.choice(E.STANCES)
            g, _ = self.act(g, {"do": "speech", "stance": stance})
            return g
        if s["step"] == "clause":
            c = E._clause(g, s["queue"][s["i"]])
            vote, choice = self.clause_vote(g, c), "stand"
            p = s["pending"]
            if self.style == "random":
                choice = self.rng.choice(["stand", "offer", "accept", "favour", "point_of_order"])
                vote = self.rng.choice(E.VOTES)
            elif p:
                hurts = (g["mandate"]["must"] == p.get("remove")) or (g["mandate"]["red"] == p.get("add")) or \
                        (c["author"] == "you" and self.style == "drafter")
                if hurts and "point_of_order" in g["skills"] and not s["po_used"]:
                    choice = "point_of_order"
                elif not hurts and self.style in ("broker", "analyst"):
                    choice = "accept"
            if choice == "stand" and self.style != "random" and s.get("attack") and vote == "yes"                     and g["respect"] >= E.R["reply_respect"]:
                choice = "reply"
            if choice == "stand" and self.style != "random":
                my = {"yes": 1, "no": -1, "abstain": 0}[vote]
                close = my and self.swing_targets(g, c, my)
                if g["favours"] and close and (g["mandate"]["must"] in c["tags"] or self.style != "hardliner"):
                    choice = "favour"
                elif close and g["influence"] >= E.R["offer_cost"]:
                    choice = "offer"
            g2, ok = self.act(g, {"do": "decide", "choice": choice, "vote": vote})
            if not ok:
                g2, _ = self.act(g, {"do": "decide", "choice": "stand", "vote": vote})
            return g2
        if s["step"] == "statement":
            if self.style == "random":
                tags = self.rng.sample(s["statement_options"], k=min(2, len(s["statement_options"])))
            else:
                red = g["mandate"]["red"]
                tags = [t for t in s["statement_options"] if t != red and all(
                    self.est(g, i, {"id": "st", "tags": [t], "author": "you"}) != "no" for i in self.scn.isos if i not in E._others(g))]
                tags = tags or [g["mandate"]["must"]]
            g, _ = self.act(g, {"do": "statement", "tags": tags})
            return g
        vote = "yes" if self.style != "random" else self.rng.choice(E.VOTES)
        if self.style == "hardliner":
            kept = {t for r in s["results"] if r["passed"] for t in r["tags"]}
            vote = "no" if g["mandate"]["red"] in kept else "yes"
        g, _ = self.act(g, {"do": "final", "vote": vote})
        return g

    def clause_vote(self, g, c) -> str:
        if any(p["clause"] == c["id"] and p["kept"] is None for p in g["promises"]):
            return "yes"
        st = E.stance(self.scn, g, "you", c)
        if self.style in ("broker", "drafter", "analyst") and st == 0:
            return "yes"
        return "yes" if st > 0 else "no" if st < 0 else "abstain"
