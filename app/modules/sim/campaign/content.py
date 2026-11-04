"""Cards for the campaign: events, procedure moments and the diplomatic skills.

Every card here teaches something true about committee work. Events from a real-issue scenario are always shown
as "Hypothetical" (the engine adds the label); procedure answers follow the platform's own rules of procedure.
"""
from __future__ import annotations

# Events: one is drawn at the start of each chapter turn. `effect` is applied for that turn only unless it says
# otherwise. Kinds: ap (action points), lobby_cost, influence, region_mood (a regional group warms to whoever
# lobbied it last), respect, question (a procedure moment).
EVENTS = [
    {"id": "speakers_closed", "title": "The speakers list closes early", "body": "The Chair closes the speakers list to save time. Fewer chances to be heard this session.",
     "effect": {"ap": -1}, "teaches": "A motion to close the speakers list ends debate once the remaining speakers have spoken."},
    {"id": "extended_caucus", "title": "Unmoderated caucus extended", "body": "The committee votes for five more minutes of unmoderated caucus. Delegates are on their feet.",
     "effect": {"ap": 1}, "teaches": "Committees extend caucuses by motion when negotiations are close."},
    {"id": "press_leak", "title": "A draft is leaked to the press", "body": "Capitals are watching closely. Delegations are cautious about being seen to move.",
     "effect": {"lobby_cost": 1}, "teaches": "Delegates answer to their capitals; public pressure makes them less flexible."},
    {"id": "coffee", "title": "Coffee in the delegates' lounge", "body": "Informal talks go well over coffee. Conversations are easier today.",
     "effect": {"lobby_cost": -1}, "teaches": "Much real negotiation happens informally, outside the chamber."},
    {"id": "instructions", "title": "New instructions from capital", "body": "Your foreign ministry sends funding for side events.",
     "effect": {"influence": 2}, "teaches": "Delegations act on instructions from their governments."},
    {"id": "regional_meeting", "title": "A regional group meets", "body": "One regional group holds its own meeting. Whoever has worked hardest with it gains ground.",
     "effect": {"region_mood": 0.15}, "teaches": "The five UN regional groups coordinate positions and nominate candidates."},
    {"id": "procedure_1", "title": "Procedure moment", "body": "", "effect": {"question": True}, "teaches": ""},
    {"id": "procedure_2", "title": "Procedure moment", "body": "", "effect": {"question": True}, "teaches": ""},
    {"id": "procedure_3", "title": "Procedure moment", "body": "", "effect": {"question": True}, "teaches": ""},
    {"id": "quiet", "title": "A quiet morning", "body": "Nothing unexpected. The committee gets on with its work.", "effect": {}, "teaches": ""},
]

# Procedure moments: the right answer earns Expertise and Respect; a wrong one costs a little Respect and explains why.
QUESTIONS = [
    {"id": "q_poi", "ask": "Another delegate wants to ask the speaker a question about their speech. What do they raise?",
     "options": ["A point of information", "A point of order", "A point of personal privilege"], "answer": 0,
     "why": "A point of information is a question to the speaker, if they agree to take it."},
    {"id": "q_order", "ask": "The Chair has called a vote while a motion with higher precedence was still on the floor. What do you raise?",
     "options": ["A point of personal privilege", "A point of order", "A right of reply"], "answer": 1,
     "why": "A point of order says the rules of procedure have not been followed."},
    {"id": "q_privilege", "ask": "You can't hear the speaker because of noise in the room. What do you raise?",
     "options": ["A point of order", "A point of information", "A point of personal privilege"], "answer": 2,
     "why": "A point of personal privilege is about your own comfort or ability to take part."},
    {"id": "q_mod", "ask": "You want a focused debate on one clause, with short speeches. Which motion?",
     "options": ["An unmoderated caucus", "A moderated caucus", "To close debate"], "answer": 1,
     "why": "A moderated caucus has a topic, a total time and a speaking time; the Chair calls on speakers."},
    {"id": "q_unmod", "ask": "Delegates need to write an amendment together. Which motion helps most?",
     "options": ["An unmoderated caucus", "A moderated caucus", "A point of information"], "answer": 0,
     "why": "In an unmoderated caucus delegates leave their seats to negotiate and draft."},
    {"id": "q_friendly", "ask": "Every sponsor of a clause agrees with your change to it. What kind of amendment is it?",
     "options": ["Unfriendly", "Friendly", "Out of order"], "answer": 1,
     "why": "A friendly amendment has the sponsors' agreement and is adopted without a vote."},
    {"id": "q_unfriendly", "ask": "The sponsors don't agree with your amendment. What happens to it?",
     "options": ["It is adopted anyway", "It is ruled out of order", "The committee votes on it"], "answer": 2,
     "why": "An unfriendly amendment is debated and voted on before the clause itself."},
    {"id": "q_division", "ask": "You support most of the resolution but not one clause. Which motion lets the committee vote on clauses separately?",
     "options": ["Division of the question", "A roll-call vote", "To table the resolution"], "answer": 0,
     "why": "Division of the question splits a resolution so clauses are voted on one by one."},
    {"id": "q_signatory", "ask": "You want the draft debated but don't fully support it. Can you still help it reach the floor?",
     "options": ["No: only sponsors count", "Yes, as a signatory", "Only with the Chair's permission"], "answer": 1,
     "why": "Signatories want a draft debated; they don't have to support it. Sponsors wrote it and back it."},
    {"id": "q_preamble", "ask": "Which part of a resolution says what the committee will actually do?",
     "options": ["Preambular clauses", "Operative clauses", "The title"], "answer": 1,
     "why": "Operative clauses act; preambular clauses set out the background and are not usually voted on separately."},
    {"id": "q_abstain", "ask": "Under a simple majority of those present and voting, how is an abstention counted?",
     "options": ["As a vote against", "It isn't counted towards the majority", "As half a vote"], "answer": 1,
     "why": "Abstaining delegations are present but not voting, so they don't count towards the majority."},
    {"id": "q_veto", "ask": "In the Security Council, what happens if a permanent member votes no on a substantive resolution?",
     "options": ["It fails, whatever the other votes", "It still passes with nine yes votes", "The vote is taken again"], "answer": 0,
     "why": "A no vote from any of the five permanent members is a veto. Abstaining is not a veto."},
    {"id": "q_reply", "ask": "Another delegate has insulted your country's integrity in a speech. What can you ask for?",
     "options": ["A point of information", "A right of reply", "A moderated caucus"], "answer": 1,
     "why": "A right of reply answers a personal or national insult; the Chair decides whether to grant it."},
]

# Diplomatic skills, unlocked with Expertise (section 7 of the rules). Each costs SKILL_COST; the second in a
# branch needs the first.
SKILLS = {
    "point_of_order": {"branch": "Procedure", "name": "Point of order", "needs": None,
                       "what": "Once in the summit, rule a rival's floor amendment out of order."},
    "division": {"branch": "Procedure", "name": "Division of the question", "needs": "point_of_order",
                 "what": "Split a clause with two commitments into two clauses (1 action point)."},
    "bloc_whip": {"branch": "Diplomacy", "name": "Bloc whip", "needs": None,
                  "what": "Lobby every member of one bloc at once (2 action points)."},
    "back_channel": {"branch": "Diplomacy", "name": "Back channel", "needs": "bloc_whip",
                     "what": "Promises win twice the goodwill."},
    "friendly": {"branch": "Drafting", "name": "Friendly amendment", "needs": None,
                 "what": "Amending costs no Influence and no Trust."},
    "merge": {"branch": "Drafting", "name": "Merge", "needs": "friendly",
              "what": "Combine two clauses into one (1 action point)."},
    "read_room": {"branch": "Analysis", "name": "Read the room", "needs": None,
                  "what": "Country files show which way a delegation is leaning today, not just its position."},
    "rival_intel": {"branch": "Analysis", "name": "Rival intelligence", "needs": "read_room",
                    "what": "See what each rival will try next turn."},
}
SKILL_COST = 3

PATHS = {
    "mandate": {"name": "Mandate", "for": "The hardliner",
                "what": "Your secret instructions are in the final text, and it passes."},
    "consensus": {"name": "Consensus", "for": "The broker",
                  "what": "It passes with the widest support, across regional groups."},
    "architect": {"name": "Architect", "for": "The drafter",
                  "what": "Most of the final text is yours: your clauses and amendments."},
    "kingmaker": {"name": "Kingmaker", "for": "The analyst",
                  "what": "You read the room accurately, keep every promise and end with high Respect."},
}

CHAPTERS = {
    1: {"name": "Working group", "goal": "Build the draft: at least four clauses, one of them yours."},
    2: {"name": "Blocs", "goal": "Win the endorsement of at least one regional group."},
    3: {"name": "Sponsors", "goal": "Gather sponsors and signatories to table the draft first."},
}

# How hard each scenario is, from the balance harness (competent bots reaching silver on Standard: Beginner 85%+,
# Standard 50-85%, Expert below 50%). Rerun tools/campaign_sim.py when a scenario changes; a new pack without a
# label shows as Standard until it's measured.
SCENARIO_LEVEL = {
    "comet_halcyon": "beginner",
    "veloria": "standard", "ga_ai_governance": "standard", "ga_autonomous_weapons": "standard",
    "ga_migration": "standard", "ga_climate_transition": "standard",
    "sc_ai_cyber": "expert", "sc_climate_security": "expert",
}
LEVEL_NAMES = {"beginner": "Beginner", "standard": "Standard", "expert": "Expert"}
