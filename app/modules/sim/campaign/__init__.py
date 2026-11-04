"""The Session: a one-hour solo Model UN campaign (D-101; rules in docs/design/solo-campaign.md).

- `scenario`: a read-only snapshot of a scenario pack's committee, with each country's modelled position for any
  set of commitments, taken from the real vote engine (`build_inputs` and `distribution`) and cached.
- `content`: event cards, procedure questions and clause cards.
- `engine`: the rules, a pure function of (scenario, game, action). A game is a plain JSON-safe dict with a seeded
  random-number counter, so a saved game replays exactly.
- `bots`: players with different styles, used by `tools/campaign_sim.py` to measure balance before any interface
  is built.
"""
