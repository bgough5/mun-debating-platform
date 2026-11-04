"""Balance harness for The Session (D-101): bots play many games on every scenario and difficulty, and the report
says how often each style earns its own victory path, which actions win, and how long a game would take.

  python tools/campaign_sim.py                 # 20 games per scenario x difficulty x style
  python tools/campaign_sim.py --games 60 --packs comet_halcyon veloria

Writes test-results/campaign/summary.json and prints a table. Uses a throwaway database with the scenario packs
installed (fake data only), never the real one.

Targets (docs/design/solo-campaign.md section 14):
  - Standard: a competent bot reaches at least silver on its chosen path in 40-60% of games;
  - each style gets gold on its own path in 30-70% of its games;
  - no single action is more than 35% of a winning bot's moves;
  - every pack winnable on every difficulty; the hardest pack on Standard at least 25%.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Seconds a student would spend on each move: reading, thinking and the animation (a model, to be checked in a
# real play test).
SECONDS = {"hire": 20, "post": 15, "reserve": 10, "secure": 25, "offer": 30, "lobby": 45, "read": 60, "propose": 50, "amend": 40, "strike": 30, "promise": 30, "side_event": 30, "favour": 20,
           "whip": 25, "sign": 25, "answer": 30, "skill": 30, "divide": 30, "merge": 30, "bloc_whip": 30, "end_turn": 40,
           "speech": 90, "decide": 60, "final": 60}
FIXED = 6 * 60      # setup, the chapter cards and the debrief


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=20)
    ap.add_argument("--packs", nargs="*")
    ap.add_argument("--length", default="standard")
    ap.add_argument("--out", default=str(ROOT / "test-results" / "campaign"))
    args = ap.parse_args()

    from app.db import SYSTEM
    from app.main import create_app
    from app.modules.mun.packfile import available
    from app.modules.sim import play
    from app.modules.sim.campaign import bots as B
    from app.modules.sim.campaign import engine as E
    from app.modules.sim.campaign.scenario import load
    from tests.conftest import make_settings

    app = create_app(make_settings(Path(tempfile.mkdtemp())))
    codes = args.packs or [p["code"] for p in available()]
    results = []
    started = time.time()
    with app.state.db.read() as rconn:
        for code in codes:
            with app.state.db.write(SYSTEM) as w:
                cid = play.guest_committee(w, code)
            scn = load(rconn, cid, code)
            scn.warm(3)
            isos = scn.isos
            for diff in E.DIFFICULTIES:
                for style, path in B.STYLES.items():
                    for k in range(args.games):
                        seed = 1000 + k
                        iso = isos[(k * 7) % len(isos)]
                        g = E.new_game(scn, iso, args.length, diff, path or "mandate", seed)
                        g = B.Bot(scn, style, seed).play(g)
                        if g["phase"] != "done":
                            results.append({"pack": code, "difficulty": diff, "style": style, "stuck": True})
                            continue
                        secs = FIXED + sum(SECONDS.get(a, 30) * n for a, n in g["stats"].items())
                        fin = g["summit"]["final"]
                        rivals_won = sum(1 for rv in g["rivals"] if fin["passed"] and rv["want"] in fin["tags"] and rv["block"] not in fin["tags"])
                        results.append({"pack": code, "difficulty": diff, "style": style, "iso3": iso, "path": g["path"],
                                        "grade": g["result"]["grade"], "paths": g["result"]["paths"], "passed": g["result"]["passed"],
                                        "stats": g["stats"], "minutes": round(secs / 60, 1), "objectives": g["objectives"],
                                        "rivals": len(g["rivals"]), "rivals_won": rivals_won,
                                        "rival_moves": sum(1 for x in g["log"] if x["kind"] == "rival")})
            print(f"{code}: done ({time.time() - started:.0f}s)", flush=True)
    report = summarise(results)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    (out / "games.json").write_text(json.dumps(results), encoding="utf-8")
    print_report(report)


def rate(xs, test) -> float:
    xs = list(xs)
    return round(sum(1 for x in xs if test(x)) / len(xs), 3) if xs else 0.0


def summarise(results: list[dict]) -> dict:
    ok = [r for r in results if not r.get("stuck")]
    styles = sorted({r["style"] for r in ok})
    by = defaultdict(list)
    for r in ok:
        by[(r["difficulty"], r["style"])].append(r)
    table = {}
    for (d, s), rs in sorted(by.items()):
        table[f"{d}/{s}"] = {"games": len(rs), "silver_plus": rate(rs, lambda r: r["grade"] >= 2), "gold": rate(rs, lambda r: r["grade"] == 3),
                             "any_medal": rate(rs, lambda r: r["grade"] >= 1), "passed": rate(rs, lambda r: r["passed"]),
                             "minutes": round(statistics.mean(r["minutes"] for r in rs), 1)}
    packs = {}
    for code in sorted({r["pack"] for r in ok}):
        rs = [r for r in ok if r["pack"] == code and r["style"] != "random"]
        packs[code] = {d: rate([r for r in rs if r["difficulty"] == d], lambda r: r["grade"] >= 2) for d in ("easy", "standard", "hard")}
    winners = [r for r in ok if r["style"] != "random" and r["grade"] >= 2]
    acts = Counter()
    for r in winners:
        acts.update({k: v for k, v in r["stats"].items() if k not in ("end_turn", "answer", "skill")})
    total = sum(acts.values()) or 1
    std = [r for r in ok if r["difficulty"] == "standard" and r["style"] != "random"]
    targets = {
        "standard_silver_plus_40_60": rate(std, lambda r: r["grade"] >= 2),
        "gold_own_path_30_70": {s: rate([r for r in ok if r["style"] == s and r["difficulty"] == "standard"], lambda r: r["grade"] == 3)
                                for s in styles if s != "random"},
        "max_action_share_le_35": max(acts.values()) / total if acts else 0,
        "hardest_pack_standard_ge_25": min((p["standard"] for p in packs.values()), default=0),
        "stuck_games": sum(1 for r in results if r.get("stuck")),
        "random_silver_plus": rate([r for r in ok if r["style"] == "random"], lambda r: r["grade"] >= 2),
        "rivals_win_share": {d: round(sum(r["rivals_won"] for r in ok if r["difficulty"] == d)
                                      / max(1, sum(r["rivals"] for r in ok if r["difficulty"] == d)), 3) for d in ("easy", "standard", "hard")},
    }
    cross = {s: {p: round(statistics.mean(r["paths"][p] for r in ok if r["style"] == s), 2) for p in ("mandate", "consensus", "architect", "kingmaker")}
             for s in styles}
    return {"games": len(results), "targets": targets, "table": table, "packs": packs,
            "action_share_of_winners": {k: round(v / total, 3) for k, v in acts.most_common()}, "mean_grade_by_style_and_path": cross}


def print_report(rep: dict) -> None:
    print(f"\n{rep['games']} games")
    print("\nTargets")
    for k, v in rep["targets"].items():
        print(f"  {k}: {v}")
    print("\nDifficulty/style: silver+ | gold | passed | minutes")
    for k, v in rep["table"].items():
        print(f"  {k:22} {v['silver_plus']:.2f} | {v['gold']:.2f} | {v['passed']:.2f} | {v['minutes']}")
    print("\nPacks (silver+ by difficulty, competent bots)")
    for k, v in rep["packs"].items():
        print(f"  {k:24} " + "  ".join(f"{d} {x:.2f}" for d, x in v.items()))
    print("\nAction share among winning bots")
    print("  " + ", ".join(f"{k} {v:.2f}" for k, v in rep["action_share_of_winners"].items()))
    print("\nMean grade (0-3) by style on each path")
    for s, v in rep["mean_grade_by_style_and_path"].items():
        print(f"  {s:10} " + "  ".join(f"{p} {x}" for p, x in v.items()))


if __name__ == "__main__":
    main()
