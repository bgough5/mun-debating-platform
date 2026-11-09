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

# Procedure moments: the right answer earns Expertise and Standing; a wrong one costs a little Standing and explains why.
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
    "back_channel": {"branch": "Diplomacy", "name": "Back channel", "needs": None,
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
# Since 8 Nov 2026 skills come with your advisers' promotions, not from a tree: (adviser kind, stars) -> skills.
STAFF_SKILLS = {"analyst": {2: ["read_room"], 3: ["rival_intel"]},
                "regional": {2: ["back_channel"], 3: ["friendly"]},
                "legal": {2: ["point_of_order"], 3: ["division", "merge"]}}

# Your approach (8 Nov 2026): chosen before each game. Each is a trade-off, never simply better, and medals unlock them.
APPROACHES = {
    "diplomat": {"name": "Career diplomat", "what": "No strengths and no weaknesses: the classic ambassador.", "unlock": None,
                 "needs": None},
    "linguist": {"name": "The Linguist", "what": "Talks cost 1 Influence less. Opening a deal costs 1 Influence more.",
                 "unlock": "silver", "needs": "Silver or better on Standard or Hard"},
    "veteran": {"name": "The Veteran", "what": "You start with a senior adviser. One action fewer in each of your first three turns.",
                "unlock": "gold", "needs": "Gold on Standard or Hard"},
    "envoy": {"name": "The Envoy", "what": "Up to three visitors a turn and more offers at your door. Rivals gain 1 Influence more each turn.",
              "unlock": "three_golds", "needs": "Gold in three scenarios on Standard or Hard"},
}

# Insignia (8 Nov 2026): earned in finished games, shown on your ambassador and in your record. Cosmetic only.
INSIGNIA = {
    "first_pass": {"name": "First resolution", "what": "A resolution of yours adopted."},
    "gold_std": {"name": "Gold standard", "what": "Gold on Standard or Hard."},
    "hard_won": {"name": "Hard-won", "what": "Gold on Hard."},
    "council": {"name": "The Council", "what": "A resolution adopted in a Security Council scenario."},
    "honour": {"name": "Word of honour", "what": "Kept at least two promises and broke none, in one session."},
    "half_loaf": {"name": "Half a loaf", "what": "Backed a text that wasn't everything you wanted, and it carried your main aim."},
    "all_paths": {"name": "Every path", "what": "Gold on every path (in any sessions)."},
    "globetrotter": {"name": "Globetrotter", "what": "Finished sessions as five different countries."},
}

PATHS = {
    "mandate": {"name": "Mandate", "for": "The hardliner",
                "what": "Your secret instructions are in the final text, and it passes.",
                "gold": "a perfect score: it passes with your main and second aims in, your red line out, and every delegation voting yes."},
    "consensus": {"name": "Consensus", "for": "The broker",
                  "what": "It passes with the widest support, across regional groups.",
                  "gold": "a perfect score: it passes unanimously, three regional groups endorse you, and your main aim is in."},
    "architect": {"name": "Architect", "for": "The drafter",
                  "what": "The resolution bears your mark: your clauses and your amendments.",
                  "gold": "a perfect score: it passes, the whole text is yours or amended by you, every one of your clauses carries the room, and three of them are wholly your own."},
    "kingmaker": {"name": "Kingmaker", "for": "The analyst",
                  "what": "You read the room accurately, keep every promise and end with high Standing.",
                  "gold": "a perfect score: your whip sheet is entirely right, you break no promise, and your Standing ends at the top."},
    "ambassador": {"name": "Ambassador", "for": "The envoy",
                   "what": "You did the job you're paid for: you used your time and talked to the whole room.",
                   "gold": "a perfect score: it passes, you used every action you had, you engaged the whole room, and everyone you engaged votes yes."},
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


# Chapter crises (phase 7): one opens each chapter and changes the rules for that chapter, like an era event.
CRISES = [
    {"id": "new_government", "title": "A new government in {country}",
     "body": "An election in {country} brings in a new government. Its delegation has new instructions on any clause that {tag}.",
     "teaches": "Delegations speak for their governments: when a government changes, its positions can change overnight."},
    {"id": "press", "title": "The press turns on part of the draft",
     "body": "Newspapers in many capitals attack any clause that {tag}. Delegations become warier of it.",
     "teaches": "Public opinion at home limits what delegates can agree to abroad."},
    {"id": "deadline", "title": "The deadline is brought forward",
     "body": "The President of the committee announces that this stage's deadline comes a turn early. Work fast.",
     "teaches": "Negotiations run to the clock: deadlines force compromises, or leave texts unfinished."},
    {"id": "partner", "title": "{rival} gains a partner",
     "body": "A like-minded delegation joins {rival} and lends it staff for this stage. It can do more each turn.",
     "teaches": "Delegations pool their staff and their votes: small countries gain weight by working together."},
    {"id": "donor", "title": "A donor conference",
     "body": "Several capitals pledge money for the issue. Every delegation, rivals included, has more to work with this stage.",
     "teaches": "Funding pledges change what a resolution can promise, and who can afford to lobby for it."},
    {"id": "regional_summit", "title": "The {region} holds a summit",
     "body": "Leaders of the {region} meet in the middle of the session. The group is ready to back a draft more readily this stage.",
     "teaches": "Regional groups and organisations shape positions before they reach the UN."},
]

# Rival personalities (phase 7): how each rival plays, which a player can learn and plan for.
RIVAL_STYLES = {
    "hawk": {"name": "The Hawk", "what": "Blocks first: amends and strikes anything that crosses its instructions."},
    "broker": {"name": "The Broker", "what": "Buys allies: courts whole regional groups and builds a bloc against you."},
    "spoiler": {"name": "The Spoiler", "what": "Goes after your text: targets the clauses you wrote, and saves a floor amendment for the summit."},
}


# Your staff (phase 8). Advisers study one delegation each and report at the start of every turn. Junior advisers can
# be wrong, and say how sure they are; every report that proves right counts towards a promotion.
STAFF_KINDS = {
    "analyst": {"name": "Analyst", "icon": "analyst", "what": "Studies rivals: their next move, and what they're after."},
    "regional": {"name": "Regional expert", "icon": "regional", "what": "Knows the delegations of your own regional group best."},
    "legal": {"name": "Legal adviser", "icon": "legal", "what": "Reads the rules: at the summit, says whether a floor amendment would pass."},
}
STAFF_NAMES = ["Reyes", "Lindqvist", "Tanaka", "Asante", "Okafor", "Haddad", "Novak", "Moreau", "Kaur", "Silva", "Petrov",
               "Nguyen", "Mensah", "Costa", "Ibrahim", "Larsen"]
STAFF_RANKS = {1: "Junior adviser", 2: "Senior adviser", 3: "Principal adviser"}
SURE = {1: "a hunch", 2: "fairly sure", 3: "certain"}


# The deal table (phase 9): what you can offer a delegation, and what you can ask of it.
DEAL_GIVE = {
    "funding": {"name": "A funding pledge", "what": "Your government funds a programme they care about: 2 Influence and one pledge from your budget."},
    "trade": {"name": "Trade terms", "what": "Easier access to your market for their exports. Your capital minds unless trade matters to your own economy."},
    "candidacy": {"name": "Backing for their candidacy", "what": "Your vote for their candidate at the next UN election (two a session at most)."},
    "clause": {"name": "Backing for their clause", "what": "A promise to vote yes on the clause they like best."},
    "influence": {"name": "Influence", "what": "You put 3 Influence behind their priorities."},
    "standing": {"name": "Your public support", "what": "You speak up for their position in the room: it costs you 1 Standing."},
}
DEAL_GET = {
    "yes": {"name": "Their yes", "what": "A yes vote on the whole resolution, unless it crosses their own red line."},
    "abstain": {"name": "An abstention", "what": "They abstain rather than vote against (for a permanent member: no veto)."},
    "sponsor": {"name": "Sponsorship", "what": "They sponsor your draft."},
    "influence": {"name": "Influence", "what": "They put 3 Influence behind your work."},
    "intel": {"name": "Intelligence", "what": "What they know about a rival's next move."},
    "favour": {"name": "A vote owed", "what": "They owe you a favour: call it in at the summit before a vote."},
    "commit": {"name": "A signed commitment", "what": "They sign a commitment to your draft: rivals find them twice as hard to move."},
    "standing": {"name": "Their public praise", "what": "They praise your work in the room: +1 Standing."},
}


# Stages (phase 11): each ends at a breakthrough (move on now, or keep working) or at its deadline.
STAGES = {
    1: {"name": "Working group", "breakthrough": "zero draft agreed",
        "goal": "Agree a zero draft: five clauses or more, two of them yours, your main aim in the text, and a text that would pass.",
        "unlocks": "Bloc meetings open: the regional groups meet, one each turn.",
        "look": "The drafting table is open: build the text."},
    2: {"name": "Bloc meetings", "breakthrough": "a regional group endorses your draft",
        "goal": "Win a new regional group's endorsement for your draft (from the stage's second turn).",
        "unlocks": "Sponsors: the sign-up sheet opens, and the race to table first begins.",
        "look": "The map shows the regional groups. One group meets each turn: attend, and work its members."},
    3: {"name": "Sponsors", "breakthrough": "your draft is tabled as L.1",
        "goal": "Table your draft as L.1: three sponsors and enough signatories, before a rival tables theirs.",
        "unlocks": "The Summit: the draft goes to the vote.",
        "look": "The sign-up sheets are out: yours and each rival's fill with flags as you race."},
}
STAGES_QUICK = {1: {"name": "Working session", "breakthrough": "your draft is ready and tabled",
                    "goal": "In one session: agree a zero draft, win a regional group and table your draft.",
                    "unlocks": "The Summit: the draft goes to the vote.",
                    "look": "Everything at once: draft, meet the regional groups, and gather sponsors."}}


# Compromise with a rival (phase 12): what you can concede for peace.
TRUCE_GIVE = {
    "drop": {"name": "Drop the commitment it can't accept", "what": "Take its red line out of the draft, wherever it is."},
    "include": {"name": "Let its wish into the text", "what": "Add a clause with what it came for."},
}
