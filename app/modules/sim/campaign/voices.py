"""The Session: every delegation has its own voice (Ben's playtest, 10 Nov 2026).

Each delegation speaks in one of six registers for the whole game. The register comes only from what the game already
knows about the delegation's place in the room: what it listens to (`talks.receptive`), the size of its economy,
whether it is a permanent member, whether it receives aid, whether it is a rival and how that rival plays, and a
seeded touch of the person in the seat. It never comes from a country's culture, and no line gives a delegation a
position the game hasn't given it: the lines change how a thing is said, never what is said.

- measured: careful and legalistic; talks about the text and the wording.
- warm:     friendly and collegial; talks about working together.
- blunt:    short and transactional; talks about what is in it for them.
- grave:    formal and weighty, as a great power speaks; "my government".
- urgent:   pressing and principled, as an exposed state speaks; "what is at stake for us".
- guarded:  gives little away; "I can't say more than that".

Everything here is a pure function of the game: lines are chosen with a seeded `random.Random`, never the engine's
own counter, so `engine.apply` stays pure, games replay identically and the numbers of a game are untouched."""
from __future__ import annotations

import random

from app.modules.sim.campaign import econ as X

REGISTERS = ("measured", "warm", "blunt", "grave", "urgent", "guarded")

# the one word shown on a delegation's file, and what it tells the player
MANNER = {
    "measured": ("Measured", "careful, and watches the wording"),
    "warm": ("Warm", "friendly, and likes to work together"),
    "blunt": ("Blunt", "short, and straight to the bargain"),
    "grave": ("Grave", "formal, and speaks for its government"),
    "urgent": ("Earnest", "pressing, and speaks from principle"),
    "guarded": ("Guarded", "gives little away"),
}

TEMPERAMENT = 0.9      # how much the person in the seat can outweigh the delegation's place in the room


def voice(scn, g: dict, iso: str) -> str:
    """The register a delegation speaks in: the same all game, read from its traits with a seeded temperament."""
    from app.modules.sim.campaign import talks as T          # talks loads after the engine; ask for it when needed
    m, t = scn.member(iso), X.traits(iso)
    r = T.receptive(scn, g, iso)
    hears = {k for k, x in r.items() if x == T.STRONG}
    rv = next((x for x in g.get("rivals", []) if x["iso3"] == iso), None)
    style = rv.get("style", "hawk") if rv else None
    p5 = bool(m and m.p5)
    exposed = t["known"] and t["size"] == 1 and (t["aid"] or t["low"])
    score = {
        "grave": 2.2 * p5 + 0.7 * (t["size"] == 4) + 0.3 * (t["size"] >= 3 and "security" in hears) + 0.8 * (style == "hawk"),
        "measured": 0.8 * ("precedent" in hears) + 0.3 * t["rich"] + 0.5 * (style == "spoiler"),
        "warm": 0.9 * ("region" in hears) + 0.5 * ("values" in hears) + 0.7 * (style == "broker"),
        "blunt": 0.7 * ("interest" in hears) + 0.4 * t["exporter"] + 0.3 * (style in ("hawk", "broker")),
        "urgent": 0.0 if p5 or t["size"] >= 3 else 1.0 * exposed + 0.4 * ("values" in hears) + 0.3 * (t["size"] == 1),
        "guarded": 0.7 + 0.3 * t["upper"] + 0.5 * (style == "spoiler"),
    }
    rng = random.Random(f"{g['seed']}:voice:{iso}")
    return max(REGISTERS, key=lambda k: score[k] + rng.uniform(0, TEMPERAMENT))


def manner(scn, g: dict, iso: str) -> dict:
    name, what = MANNER[voice(scn, g, iso)]
    return {"name": name, "what": what}


def _rng(g: dict, iso: str, slot: str) -> random.Random:
    return random.Random(f"{g['seed']}:voice:{g.get('tick', 0)}:{g.get('n', 0)}:{iso}:{slot}")


def pick(g: dict, key: str, options: list, rng: random.Random) -> str:
    """A line from `options` not yet heard in this game under `key`, while any remain (Ben, 11 Nov: talks repeated
    themselves). Every delegation that speaks in the same register shares the memory, so no two of them say the same
    line until the bank is used up. Seeded, so games replay identically."""
    used = g.setdefault("lines_used", {}).setdefault(key, [])
    free = [i for i in range(len(options)) if i not in used]
    if not free:
        used.clear()
        free = list(range(len(options)))
    i = rng.choice(free)
    used.append(i)
    return options[i]


def _say(scn, g, iso, bank, slot, rng=None) -> str:
    reg = voice(scn, g, iso)
    return pick(g, f"{slot}:{reg}", bank[reg], rng or _rng(g, iso, slot))


# ---------------------------------------------------------------- talking: first reactions, the verdict, the stance

def react(scn, g, iso, level: str, rng=None) -> str:
    """What they say when you open with an argument: level is "strong", "some" or "weak"."""
    reg = voice(scn, g, iso)
    return pick(g, f"react:{reg}:{level}", REACT[reg][level], rng or _rng(g, iso, "react"))


def stance(scn, g, iso, b: int, rng=None) -> str:
    """Where they stand on your position: the five buckets of `engine.bucket`, 2 (strongly for) to -2 (against)."""
    reg = voice(scn, g, iso)
    return pick(g, f"stance:{reg}:{b}", STANCE[reg][b], rng or _rng(g, iso, "stance"))


def answer(scn, g, iso, level: str | None, b: int) -> str:
    """Their answer at the end of a talk: how your case landed, then where they stand, as one thought. When the two
    pull apart (a good case but still against; not persuaded but for you anyway) a bridge says why, so nobody says
    "we're not persuaded, we strongly support you" (Ben's coherence rule)."""
    reg = voice(scn, g, iso)
    rng = _rng(g, iso, "answer")
    where = pick(g, f"stance:{reg}:{b}", STANCE[reg][b], rng)
    if level is None:
        return where
    parts = [pick(g, f"verdict:{reg}:{level}", VERDICT[reg][level], rng)]
    if level != "weak" and b < 0:
        parts.append(pick(g, f"but:{reg}", BUT[reg], rng))
    elif level == "weak" and b > 0:
        parts.append(pick(g, f"still:{reg}", STILL[reg], rng))
    return " ".join(parts + [where])


def red_line(scn, g, iso, when: str) -> str:
    """when: "open" (before you make your case) or "close" (after it)."""
    reg = voice(scn, g, iso)
    return pick(g, f"red:{reg}:{when}", RED[reg][when], _rng(g, iso, "red" + when))


# ---------------------------------------------------------------- visits

def greet(scn, g, iso, salt: str = "") -> str:
    reg = voice(scn, g, iso)
    return pick(g, f"greet:{reg}", GREET[reg], _rng(g, iso, "greet" + salt))


def visit(scn, g, iso, kind: str, **kw) -> str:
    """What a visiting delegate says, greeting first. kind: ask, ally, info, persuade, collect, olive, leak."""
    return greet(scn, g, iso, kind) + " " + VISIT[voice(scn, g, iso)][kind].format(**kw)


def reply(scn, g, iso, kind: str) -> str:
    """A short reply to your answer. kind: right, off, honest."""
    return REPLY[voice(scn, g, iso)][kind]


def caucus(scn, g, iso, speech: str, how: str, rng=None) -> str:
    """What a delegate says after your caucus speech (rally, reassure, demand): pleased, unmoved or annoyed."""
    bank = CAUCUS[voice(scn, g, iso)]
    return (rng or _rng(g, iso, "caucus")).choice(bank[speech][how] + [bank["any"][how]])


def caucus_lines(speech: str, how: str) -> set:
    """Every line any register may say for that speech and reaction (for tests)."""
    return {x for bank in CAUCUS.values() for x in bank[speech][how] + [bank["any"][how]]}


# ---------------------------------------------------------------- the Summit

def statement(scn, g, iso, kind: str, **kw) -> str:
    """A position statement: how they take the floor, then the statement. kind: for, toofar, against, wait, truce."""
    rng = random.Random(f"{g['seed']}:voice:statement:{iso}:{kind}")
    reg = voice(scn, g, iso)
    return rng.choice(FLOOR[reg]) + " " + rng.choice(STATEMENT[reg][kind]).format(**kw)


# ================================================================ the lines
# Rules for every line (the players are school students, and real countries are named): a professional diplomat,
# courteous even when hard; plain English and short, because the game types it out; nothing about a culture, a
# people or a real event; and it must suit any delegation that has the register.

REACT = {
    "measured": {
        "strong": ["That is a point of substance. Please continue.", "Yes. That goes to the heart of our instructions.",
                   "Noted, and noted with interest. Go on."],
        "some": ["There is some merit in that. It is not our main concern.", "A fair point, as far as it goes.",
                 "We take note. Other matters weigh more with us."],
        "weak": ["With respect, that is not the test we apply.", "I am not sure that argument applies to us.",
                 "We would not put it that way ourselves."]},
    "warm": {
        "strong": ["Now you're speaking our language. Go on.", "Yes! That is just what we hoped to hear.",
                   "My friend, that matters a great deal to us."],
        "some": ["I see what you mean. It's part of the picture for us.", "That's fair, though it isn't our first worry.",
                 "There's something in that. Tell me more."],
        "weak": ["I wish I could say that moves us. It doesn't, really.", "I hear you, but that isn't what our people ask about.",
                 "Kindly meant, I'm sure, but that's not our concern."]},
    "blunt": {
        "strong": ["Good. That's worth something to us. Go on.", "Now we're talking. Keep going.", "That's the part we care about."],
        "some": ["Maybe. It's not the main thing for us.", "Fine, as far as it goes. What else?", "That's worth a little. Not a lot."],
        "weak": ["That doesn't do anything for us.", "Wrong argument for us, Ambassador.", "No. That's not what we're here for."]},
    "grave": {
        "strong": ["That is a serious point. Continue.", "My government shares that concern. Go on.",
                   "You have chosen your ground well. Proceed."],
        "some": ["We recognise the point. It is not decisive for us.", "That has its place. Other matters weigh more heavily.",
                 "Perhaps. My government looks further than that."],
        "weak": ["That is not a consideration for my government.", "With respect, Ambassador, that does not weigh with us.",
                 "We do not see the matter in those terms."]},
    "urgent": {
        "strong": ["Yes. That is exactly why we came here. Go on.", "That is the heart of it for us. Please, go on.",
                   "At last, someone says it. Continue."],
        "some": ["That matters, but it isn't the urgent part for us.", "True enough. Our real worry is elsewhere.",
                 "We hear that. There are bigger things at stake for us."],
        "weak": ["With respect, that changes nothing for our people.", "That isn't what is at stake for us.",
                 "Forgive me, but that feels a long way from our problem."]},
    "guarded": {
        "strong": ["Hm. That is of interest to us. Go on.", "I can say that our capital watches that closely. Continue.",
                   "That is closer to our thinking than most. Go on."],
        "some": ["Possibly. I wouldn't put it higher than that.", "It's a point. I can't say it's the main one.",
                 "Perhaps. We'll see what else you have."],
        "weak": ["I don't think that is one for us.", "Hm. I can't see my capital warming to that.",
                 "That isn't where our interest lies, as far as I can say."]},
}

VERDICT = {
    "measured": {
        "strong": ["You have set out a careful case.", "That was well argued, and we have taken note.",
                   "Your reasoning is sound on the points that matter to us."],
        "some": ["Parts of that were persuasive.", "You have given us points to examine.", "Some of that will go in my report."],
        "weak": ["I do not think that case was made out.", "On balance, we are not persuaded.",
                 "Those were not the arguments that count with us."]},
    "warm": {
        "strong": ["Thank you. That was a case we can take home gladly.", "You've spoken to what matters to us.",
                   "That was good to hear, truly."],
        "some": ["Thank you for that. Some of it will help.", "You've given us things to talk over at home.",
                 "Part of that rang true for us."],
        "weak": ["I'm sorry, that didn't quite reach us.", "I'd like to say you convinced us. Not today.",
                 "Thank you for trying, but that wasn't our argument."]},
    "blunt": {
        "strong": ["That's a real case. We can use it.", "Good. You came with something solid.",
                   "You've made it worth our while to listen."],
        "some": ["Some of that was useful.", "Part of that works for us.", "You're half way there."],
        "weak": ["That didn't sell it.", "We're not buying that.", "You'll need a better case than that."]},
    "grave": {
        "strong": ["You have spoken to matters my government takes seriously.", "That was a weighty case, and it will be heard in my capital.",
                   "You argued with care. We respect that."],
        "some": ["My government will give that some weight.", "There was substance in parts of that.",
                 "We have heard you, and some of it will count."],
        "weak": ["My government is not moved by that case.", "That will carry little weight in my capital.",
                 "We have listened. We are not persuaded."]},
    "urgent": {
        "strong": ["You understand what is at stake for us. Thank you.", "That is the case we wanted someone to make.",
                   "You spoke about what matters. We won't forget it."],
        "some": ["Some of that speaks to our situation.", "You've seen part of what we face.", "There was something for us in that."],
        "weak": ["That didn't answer what we face.", "I'm afraid that missed what matters to us.",
                 "We needed a different argument from you."]},
    "guarded": {
        "strong": ["I'll admit that was a strong case.", "That will go into my report, and favourably.",
                   "You've given me more than I expected to take back."],
        "some": ["I'll pass some of that on.", "There may be something in that. I'll report it.",
                 "That was partly useful. I can say that much."],
        "weak": ["I doubt that will change minds at home.", "I can't promise that will get far with my capital.",
                 "I wouldn't expect much to come of that."]},
}

# a good case, but they are still against you
BUT = {
    "measured": ["It does not remove our difficulty with the text, however.", "Even so, the wording remains a problem for us.",
                 "That said, our position on the text has not changed."],
    "warm": ["I'm sorry to say it doesn't change our worries about the text.", "Even so, my friend, the text still troubles us.",
             "All the same, we can't pretend the draft sits well with us."],
    "blunt": ["It doesn't fix our problem with the text, though.", "But the text is still the problem.",
              "It doesn't change the facts: the draft costs us."],
    "grave": ["It does not, however, change our view of this text.", "Our difficulty with the text remains nonetheless.",
              "Even so, my government's concerns about the text stand."],
    "urgent": ["But the text still fails the test that matters to us.", "Even so, we cannot ignore what this draft would mean for us.",
               "It doesn't change what the text would do, though."],
    "guarded": ["I can't say it changes our difficulty with the text, though.", "Even so, the text remains a problem, as far as I can tell you.",
                "That doesn't alter where we are on the draft, I'm afraid."],
}

# not persuaded by your case, but they back you because the text serves their goals
STILL = {
    "measured": ["Even so, the text itself is in line with our goals.", "That said, the draft serves our interests as written.",
                 "Our view rests on the text, however, and the text suits our goals."],
    "warm": ["But don't worry: the draft itself serves our goals.", "All the same, your text does what we need it to do.",
             "Happily, the draft serves our goals anyway."],
    "blunt": ["But the text works for our goals anyway.", "It doesn't matter: the draft gets us what we need.",
              "Lucky for you, the draft suits us as it is."],
    "grave": ["Nonetheless, the text itself accords with our aims.", "The text, however, serves my government's purposes.",
              "Even so, the draft is in keeping with our goals."],
    "urgent": ["But the draft itself does what we need, and that matters more.", "Even so, the text serves the goals we came here with.",
               "Still, the draft answers our problem, and that decides it."],
    "guarded": ["As it happens, though, the draft suits our goals.", "Even so, I can tell you the text works for us as it stands.",
                "The draft serves our aims anyway, so that needn't worry you."],
}

STANCE = {
    "measured": {
        2: ["We support your position in full, and we will say so on the record.",
            "You may count on our vote and on our voice in the debate.",
            "We are firmly in favour, and we will speak for the text on the floor."],
        1: ["We can support you, subject to some changes in the wording.", "We lean in favour. A few amendments would make it easier.",
            "In principle, yes. We would like to see some drafting changes."],
        0: ["We have no instructions yet. An abstention is possible.", "Our capital is still studying the text. We may abstain.",
            "We reserve our position for now. We may well abstain."],
        -1: ["We have serious reservations about the direction of this text.", "As drafted, this gives us real difficulty.",
             "We are concerned by where this text is heading."],
        -2: ["We cannot accept this text. Our instructions leave no room.", "We must oppose it. Our instructions are explicit.",
             "This is not a text we can vote for as it stands."]},
    "warm": {
        2: ["We're with you all the way, and we'll say so on the floor.", "You have our full support. We'll speak up for you in the debate.",
            "Count on us. We'll stand up and say so."],
        1: ["We'd like to support you. A few changes would help us get there.", "We're on your side, though we'd welcome some changes.",
            "You can count on us, I think, if the text shifts a little."],
        0: ["We're still talking with our capital. We may have to abstain.", "I honestly can't say yet. We might abstain.",
            "We haven't made up our minds. An abstention is possible."],
        -1: ["I have to be honest: we're worried about where this text is going.", "We want to help, but this text gives us real concerns.",
             "It pains me to say it, but we have serious doubts about this draft."],
        -2: ["I'm sorry. We can't accept this text. Our instructions are clear.", "With real regret, we have to say no to this.",
             "We can't go along with this, my friend. Our capital has been firm."]},
    "blunt": {
        2: ["We're in. We'll say so on the floor.", "You have our vote, and we'll speak for it.",
            "Yes, all the way. We'll back you out loud."],
        1: ["We can back you. We'll want some changes.", "Probably yes. Fix a few things and it's certain.",
            "We're leaning your way. The text needs work."],
        0: ["No decision yet. We might abstain.", "Our capital hasn't told us. It could be an abstention.",
            "We're on the fence. Don't count us either way."],
        -1: ["We've got real problems with this text.", "We don't like where this is heading.", "As it stands, this is bad for us."],
        -2: ["No. We can't accept this. Our instructions are clear.", "We'll vote against this. Our capital was plain.",
             "This text is a no for us. Simple as that."]},
    "grave": {
        2: ["My government stands firmly behind your position, and will say so before the committee.",
            "You have our full support. We shall speak for this text on the floor.",
            "We are with you, and the committee will hear it from us."],
        1: ["My government is prepared to support you, with certain changes.",
            "We are inclined to support the text. Some changes would be expected.",
            "You may expect our support, provided the text is improved."],
        0: ["My government has not yet decided. An abstention remains possible.",
            "We are still in consultation with our capital. We may abstain.",
            "We keep our position open. We do not rule out an abstention."],
        -1: ["My government views the direction of this text with serious concern.",
             "We are gravely concerned by where this draft is heading.", "This text, as it stands, troubles my government deeply."],
        -2: ["My government cannot accept this text. Our instructions are clear.",
             "We shall oppose this text. My capital has left no doubt.", "This is not a text my government can accept."]},
    "urgent": {
        2: ["We stand with you fully, and we will say so on the floor.", "You have our vote and our voice. This text matters.",
            "We will back you openly. This is what we came for."],
        1: ["We want to support you. A few changes would make the text right.", "We can support this, though it needs some changes.",
            "We are with you, if the text is improved a little."],
        0: ["We are waiting on our capital. We may have to abstain.", "We cannot say yet, and time is short. We may abstain.",
            "We are torn. An abstention is possible."],
        -1: ["We are seriously worried about where this text is going.", "We have real concerns. This draft is heading the wrong way for us.",
             "We cannot stay silent: this text troubles us deeply."],
        -2: ["We cannot accept this. For us it is a matter of principle.", "No. Our instructions are clear, and so is our conscience.",
             "We must vote against. Too much is at stake for us."]},
    "guarded": {
        2: ["I can tell you this much: we support you, and we'll say so on the floor.",
            "For once I can be clear. We're with you, and we'll speak for the text.",
            "You have our support. We'll say it in the open, too."],
        1: ["We could support you, I think, if a few things change.", "We lean your way. I can't promise without some changes.",
            "Probably yes. Much depends on the final wording."],
        0: ["We're still consulting our capital. We may abstain.", "I can't tell you yet. An abstention is quite possible.",
            "We haven't decided. I wouldn't count on us either way."],
        -1: ["I should tell you we have serious concerns about this text.", "We're uneasy about where this is going. More than uneasy.",
             "I won't hide it: this draft worries my capital."],
        -2: ["We can't accept this. Our instructions are clear, and I can't go beyond them.",
             "The answer is no, I'm afraid. My capital has been definite.",
             "We'll have to vote against. There's no room in my instructions."]},
}

RED = {
    "measured": {"open": ["Before you continue: the clause you want crosses a red line for us. We will listen, but we cannot move far.",
                          "I should say at once that your clause is a red line for my delegation. We will hear you out, but we cannot move far."],
                 "close": ["We have gone as far as we can. That clause is a red line for us.",
                           "That clause remains a red line for us. We won't move on it, though I respect the effort you have made."]},
    "warm": {"open": ["Let me be honest before you start: your clause is a red line for us. We'll gladly listen, but we can't move far.",
                      "I must tell you kindly: that clause is a red line for us. Do go on, but we can't move far."],
             "close": ["We've said all we can, my friend. That clause is a red line for us.",
                       "I'm sorry. That clause stays a red line for us, though we value your efforts."]},
    "blunt": {"open": ["I'll save you time: that clause is a red line for us. Talk if you like, but we won't move far.",
                       "Straight up: your clause is a red line for us. We'll listen. We won't move far."],
              "close": ["That's all we've got. The clause is a red line for us.", "A fair effort. It's still a red line for us, and we won't move."]},
    "grave": {"open": ["I must stop you there. The clause you seek is a red line for my government. We will listen, but we will not move far.",
                       "Understand this first, Ambassador: that clause is a red line for my government. You may speak, but we will not move far."],
              "close": ["We have said what we can. That clause is a red line for my government.",
                        "That clause remains a red line for my government. We will not move on it, though we respect your efforts."]},
    "urgent": {"open": ["I have to stop you: that clause is a red line for us, on principle. We will listen, but we cannot move far.",
                        "Please understand first: your clause is a red line for us. We'll hear you, but it is not something we can trade."],
               "close": ["We have said what we can. That clause is a red line for us.",
                         "It is still a red line for us. Thank you for trying, all the same."]},
    "guarded": {"open": ["I should warn you: the clause you want is a red line for us. I'll listen, but I can't offer much.",
                         "Before you begin, that clause is a red line for us. I can hear you out, but we won't move far."],
                "close": ["I've said what I can. That clause is a red line for us.",
                          "It remains a red line for us. I can't tell you anything different."]},
}

GREET = {
    "measured": ["Ambassador, a moment, if I may.", "Ambassador, a point for your attention.", "Forgive the interruption, Ambassador."],
    "warm": ["Ambassador! I hoped to catch you.", "Good to see you, Ambassador. Have you a minute?", "Ah, Ambassador. Walk with me a moment."],
    "blunt": ["Ambassador. Got a minute?", "A quick word, Ambassador.", "Ambassador. Let's keep this short."],
    "grave": ["Ambassador. A word, if you please.", "Ambassador. My government has asked me to speak with you.",
              "A moment of your time, Ambassador."],
    "urgent": ["Ambassador, please, a moment. It matters.", "Ambassador, I'm glad I found you.", "Ambassador, this can't wait."],
    "guarded": ["Ambassador. A quiet word?", "Ambassador, do you have a moment? Somewhere quieter, perhaps.",
                "Ah, Ambassador. I was hoping for a word."],
}

VISIT = {
    "measured": {
        "ask": "Can you tell us where {about} stands on your draft? We prefer to know before the vote, not after.",
        "ally": "We support your draft. With something behind it, we could work the {region} for you. "
                "Or simply give us your word on the clause we care about.",
        "info": "We keep careful notes. For a little support, we can tell you what {rival} plans to do next.",
        "persuade": "We have not decided. Set out your case: why should my government support your draft?",
        "collect": "You gave us your word on clause {n}. We expect it to be kept at the vote.",
        "olive": "Our exchanges have been difficult. If you back clause {n}, we will abstain on your draft and not vote against it.",
        "leak": "This is not for the record. {rival} will go after {target} next."},
    "warm": {
        "ask": "Tell me, where does {about} stand on your draft? We'd hate to be the last to hear.",
        "ally": "We're with you. Put something behind it and we'll talk to the whole {region} for you. "
                "Or just promise to stand by the clause that matters to us.",
        "info": "People tell us things. For a little support, we'd happily share what {rival} is planning next.",
        "persuade": "We're truly undecided. Help me: why should my government back your draft?",
        "collect": "You promised to back clause {n}, remember? We're counting on you at the vote.",
        "olive": "We've been hard on each other, and I'm sorry for it. Back clause {n}, and we'll abstain on your draft, not vote against it.",
        "leak": "Between friends, and you didn't hear it from me: {rival} will go after {target} next."},
    "blunt": {
        "ask": "Where does {about} stand on your draft? We don't like surprises.",
        "ally": "We're with you. Put something behind it and we'll work the {region} for you. "
                "Or give us your word on our clause. Your choice.",
        "info": "We hear things. Give us a little support and we'll tell you what {rival} does next.",
        "persuade": "We could go either way. So convince me: why should we back your draft?",
        "collect": "You promised to back clause {n}. We expect you to deliver at the vote.",
        "olive": "We've gone at each other long enough. Back clause {n} and we abstain on your draft. No vote against.",
        "leak": "You didn't get this from me. {rival} goes after {target} next."},
    "grave": {
        "ask": "My government wishes to know where {about} stands on your draft. We do not care to learn such things late.",
        "ally": "My government supports you. Put something behind it and we will bring the {region} with us. "
                "Or give us your word on the clause that matters to us.",
        "info": "Little happens here that we do not hear of. For a measure of support, we will tell you what {rival} intends next.",
        "persuade": "My government has not made up its mind. Persuade me: why should we support your draft?",
        "collect": "You gave your word on clause {n}. My government expects it to be honoured at the vote.",
        "olive": "We have stood against each other long enough. Support clause {n}, and we will abstain on your draft and not oppose it.",
        "leak": "This did not come from my delegation. {rival} will go after {target} next."},
    "urgent": {
        "ask": "We need to know: where does {about} stand on your draft? We can't afford to be the last to find out.",
        "ally": "We believe in your draft. Put something behind it and we'll work the {region} for you. "
                "Or promise us you'll stand by the clause we care about.",
        "info": "We listen carefully in this building. For a little support, we'll tell you what {rival} is planning next.",
        "persuade": "We are on the fence, and the vote is coming. Convince me: why should my government back your draft?",
        "collect": "You promised to back clause {n}. It matters a great deal to us. We're counting on you at the vote.",
        "olive": "We've been hard on each other, and neither of us gains. Back clause {n}, and we'll abstain on your draft, not vote against it.",
        "leak": "You must not say this came from me. {rival} will go after {target} next."},
    "guarded": {
        "ask": "I wonder, where does {about} stand on your draft? We'd rather not be the last to know.",
        "ally": "We're with you, though I wouldn't say so loudly yet. Put something behind it and we'll work the {region} for you. "
                "Or tell us you'll stand by the clause we care about.",
        "info": "We hear things. For a little support, I could tell you what {rival} is planning next.",
        "persuade": "We're on the fence, and I'd like a reason to get off it. Why should my government back your draft?",
        "collect": "You did promise to back clause {n}. I trust that still holds at the vote.",
        "olive": "We've been hard on each other. Perhaps that can stop. Back clause {n}, and we'll abstain on your draft, not vote against it.",
        "leak": "You didn't hear this from me. {rival} will go after {target} next."},
}

REPLY = {
    "measured": {"right": "Thank you. We will see whether that holds.", "off": "That does not match our information.",
                 "honest": "A straight answer. We will remember it."},
    "warm": {"right": "Thank you, that's a help. We'll see if you're right.", "off": "Oh. That isn't what we've been hearing.",
             "honest": "Thank you for being honest. We'll remember that."},
    "blunt": {"right": "Thanks. We'll see if you're right.", "off": "That's not what we've heard.",
              "honest": "Honest. Good. We'll remember that."},
    "grave": {"right": "Thank you. We shall see whether you are right.", "off": "That is not what my government understands.",
              "honest": "An honest answer. It will be remembered."},
    "urgent": {"right": "Thank you. We hope you're right.", "off": "That isn't what we've heard, and it worries us.",
               "honest": "Thank you for the honest answer. We'll remember it."},
    "guarded": {"right": "Thank you. We'll see if you're right.", "off": "Hm. That isn't what we've heard.",
                "honest": "Honest of you. We'll remember that."},
}

CAUCUS = {
    "measured": {
        "rally": {"pleased": ["Well put. The principle is sound.", "We can stand behind a cause framed that way."],
                  "unmoved": ["Stirring. We will read the text all the same.", "A fine speech. Our instructions concern the wording."],
                  "annoyed": ["Principles are not paragraphs, Ambassador.", "We came for detail, not for a speech."]},
        "reassure": {"pleased": ["Clear and practical. That answers our questions.", "Thank you. That is the detail we needed."],
                     "unmoved": ["Reasonable. It does not settle our concerns.", "Noted. We will wait for the text."],
                     "annoyed": ["You assure us a great deal and specify very little.", "Assurances are not commitments, Ambassador."]},
        "demand": {"pleased": ["Plainly stated. We know where you stand.", "A firm position, clearly put. Good."],
                   "unmoved": ["We have heard your position. Ours is not yet fixed.", "A demand is not an argument. We will consider it."],
                   "annoyed": ["This group does not take instructions from one delegation.", "I would ask you to rephrase that, Ambassador."]},
        "any": {"pleased": "We take note, with approval.", "unmoved": "We take note.", "annoyed": "We take note, with regret."}},
    "warm": {
        "rally": {"pleased": ["Wonderful. That's the spirit we came here for.", "Well said! Our people would cheer that."],
                  "unmoved": ["Lovely words. We'd like to see the text, too.", "You speak well. Our instructions haven't changed, I'm afraid."],
                  "annoyed": ["Kind words, but our people need more than words.", "We've heard many fine speeches this week, my friend."]},
        "reassure": {"pleased": ["Thank you for listening to us. That helps.", "That puts our minds at rest. Thank you."],
                     "unmoved": ["That's kind of you. Our worries lie elsewhere.", "Sensible. We'll talk it over."],
                     "annoyed": ["You tell us not to worry. We still worry.", "I'd hoped for more than comfort, to be honest."]},
        "demand": {"pleased": ["Straight talk between friends. We respect that.", "Good. Friends should know where each other stands."],
                   "unmoved": ["We hear you. We haven't decided yet.", "Firm words. Let's keep talking."],
                   "annoyed": ["That's no way to speak among friends.", "We're partners here, Ambassador, not staff."]},
        "any": {"pleased": "Thank you. That was good to hear.", "unmoved": "Thank you, Ambassador. We'll think about it.",
                "annoyed": "I'm sorry, but that didn't sit well with us."}},
    "blunt": {
        "rally": {"pleased": ["Good speech. We can stand behind that.", "That's a cause worth our time."],
                  "unmoved": ["Nice speech. Show us the text.", "Speeches don't vote, Ambassador."],
                  "annoyed": ["Big words don't pay for anything.", "Less poetry, more detail, please."]},
        "reassure": {"pleased": ["Practical. We can work with that.", "Good. That's what our capital asked about."],
                     "unmoved": ["Fine. It isn't our main worry.", "Sensible enough. We'll see."],
                     "annoyed": ["A lot of comfort, not much substance.", "Don't tell us not to worry. Fix the text."]},
        "demand": {"pleased": ["Straight talk. We respect that.", "Good. Now we know where you stand."],
                   "unmoved": ["You'll need more than a demand.", "We heard you. No decision yet."],
                   "annoyed": ["We don't take orders in this room.", "Careful, Ambassador. We're not yours to command."]},
        "any": {"pleased": "Good. That works.", "unmoved": "Noted. We'll see.", "annoyed": "That didn't help your case."}},
    "grave": {
        "rally": {"pleased": ["Well spoken. That is a cause worthy of this room.", "My government can stand behind those words."],
                  "unmoved": ["Fine words. My government will judge the text.", "A stirring speech. It does not alter our instructions."],
                  "annoyed": ["This room has heard enough grand words.", "My government expects substance, not a performance."]},
        "reassure": {"pleased": ["Sensible and steady. My government welcomes that.", "That addresses what my capital asked. Thank you."],
                     "unmoved": ["Reasonable. Our concerns lie elsewhere.", "We have noted your assurances."],
                     "annoyed": ["My government does not need to be soothed.", "Many assurances, and little of substance."]},
        "demand": {"pleased": ["Firmly said. Serious delegations speak so.", "Good. We know where you stand."],
                   "unmoved": ["It will take more than a demand to move us.", "We have heard you. We are not yet decided."],
                   "annoyed": ["My government does not take instructions, Ambassador.",
                               "I would choose other words, Ambassador. We are not to be ordered."]},
        "any": {"pleased": "My government approves.", "unmoved": "We have heard you.", "annoyed": "That was ill-judged, Ambassador."}},
    "urgent": {
        "rally": {"pleased": ["That is the language we came here for.", "Yes. That is a cause worth standing behind."],
                  "unmoved": ["Fine words. We need to see them in the text.", "We've been inspired before. We'll wait for the text."],
                  "annoyed": ["Words won't fix what we face.", "We've no time for speeches, Ambassador."]},
        "reassure": {"pleased": ["Thank you for listening. Few do.", "That answers a fear we brought with us."],
                     "unmoved": ["Calm words. Our problem is still there.", "Sensible. It isn't what keeps us awake."],
                     "annoyed": ["You tell us not to worry. We have to worry.", "We needed action, and you gave us comfort."]},
        "demand": {"pleased": ["Firm and clear. This needs firmness.", "Good. Someone has to push this through."],
                   "unmoved": ["A demand won't settle it for us.", "We heard you. Our answer depends on the text."],
                   "annoyed": ["We may not be loud, but we won't be ordered.", "That is not how you win our support."]},
        "any": {"pleased": "Thank you. That gives us hope.", "unmoved": "We'll wait and see.",
                "annoyed": "That was a disappointment, Ambassador."}},
    "guarded": {
        "rally": {"pleased": ["I'll admit that was well said.", "That may be a cause we can stand behind."],
                  "unmoved": ["Fine words. We'll want to see the text.", "A good speech. I can't say it changes anything."],
                  "annoyed": ["We've heard a lot of big pictures this week.", "I'd have preferred fewer words, Ambassador."]},
        "reassure": {"pleased": ["That was useful. I can work with that.", "That answers a question my capital asked."],
                     "unmoved": ["Reasonable enough. We'll see.", "Noted. I can't say more than that."],
                     "annoyed": ["That was a lot of reassurance, and little I can report.", "Too careful to tell us anything, I'm afraid."]},
        "demand": {"pleased": ["Clear, at least. We know where you stand.", "Firm. I can respect that."],
                   "unmoved": ["We heard you. We haven't decided.", "Strong words. Let's see the votes."],
                   "annoyed": ["I don't think that tone will help you.", "My capital won't like being told, Ambassador."]},
        "any": {"pleased": "That may help. We'll see.", "unmoved": "We'll think about it.",
                "annoyed": "I'd rather not say what I thought of that."}},
}

# how they take the floor at the Summit
FLOOR = {
    "measured": ["Thank you, President. My delegation has read the draft closely.", "President, I will keep to the text before us.",
                 "Thank you, President. Let me state our position exactly."],
    "warm": ["Thank you, President, and greetings to all our colleagues.", "Thank you, President. It is good to see this room so full.",
             "President, colleagues, friends."],
    "blunt": ["Thank you, President. I'll be brief.", "President, I'll get straight to it.",
              "Thank you, President. Plain words from my delegation."],
    "grave": ["President, my delegation takes the floor with a sense of responsibility.",
              "Thank you, President. My government has weighed this draft with care.",
              "President, the committee is entitled to know where my government stands."],
    "urgent": ["Thank you, President. For my delegation, this debate is not a theory.",
               "President, my delegation cannot afford to be patient on this question.",
               "Thank you, President. I will speak plainly, because this matters."],
    "guarded": ["Thank you, President. My delegation will say only a little today.", "President, I will be careful in what I say.",
                "Thank you, President. Our position can be stated shortly."],
}

# the statement itself. {x} is a commitment as a verb phrase ("sets up a panel"): "a text that {x}", "whether it {x}"
STATEMENT = {
    "measured": {
        "for": ["This draft answers the problem before us. We ask every delegation to support it.",
                "The text is sound and it meets the need. We urge every delegation to support it."],
        "toofar": ["As drafted, this goes further than we can follow. We will study the amendments.",
                   "The text goes too far for us as it stands. We will listen to the amendments."],
        "against": ["We cannot accept a text that {x}. We will move to amend it.",
                    "A text that {x} would set a precedent we cannot accept. We will propose an amendment."],
        "wait": ["Our support depends on one question: whether this text {x}.",
                 "We will measure this draft by a single test: whether it {x}."],
        "truce": ["We have reached an understanding on this text, and we will support it."]},
    "warm": {
        "for": ["This draft answers the problem before us. We warmly ask every delegation to support it.",
                "This is a text we can all be proud of. Please, join us in supporting it."],
        "toofar": ["As it stands, this draft goes too far for us. We'll listen closely to the amendments.",
                   "We want to say yes, but the draft goes too far for us today. We look to the amendments."],
        "against": ["We say this with regret: we cannot accept a text that {x}. We will move to amend it.",
                    "Friends, we cannot support a text that {x}. We have an amendment ready."],
        "wait": ["We would like to support this text. It depends on whether it {x}.",
                 "Our friends know our test for this draft: whether it {x}."],
        "truce": ["We are glad to say we have reached an understanding on this text, and we will support it."]},
    "blunt": {
        "for": ["This draft does the job. We urge every delegation to support it.",
                "The text deals with the problem in front of us. We say: vote for it."],
        "toofar": ["As it stands, this goes too far for us. We'll listen to the amendments.",
                   "This draft asks too much of us as it stands. Let's hear the amendments."],
        "against": ["We won't accept a text that {x}. We'll move to amend it.",
                    "A text that {x} is a bad bargain. We have an amendment ready."],
        "wait": ["Our support comes down to one thing: whether this text {x}.", "One test for us: whether this text {x}."],
        "truce": ["We've come to an understanding on this text. We'll support it."]},
    "grave": {
        "for": ["This draft answers the problem before us. My government urges every delegation to support it.",
                "The text meets the gravity of the question. We call on all delegations to support it."],
        "toofar": ["As it stands, this draft goes further than my government can accept. We will hear the amendments.",
                   "The draft goes too far for us in its present form. We await the amendments."],
        "against": ["My government cannot accept a text that {x}. We shall move to amend it.",
                    "A resolution that {x} would set a dangerous precedent. We will seek to change it."],
        "wait": ["My government's support depends on whether this text {x}.", "We will judge this draft by one test: whether it {x}."],
        "truce": ["My government has reached an understanding on this text, and we will support it."]},
    "urgent": {
        "for": ["This draft answers the problem before us. We urge every delegation: support it.",
                "This text is what the moment asks of us. Please, vote for it."],
        "toofar": ["As it stands, this draft goes too far for us. We will listen to the amendments with hope.",
                   "We cannot follow the draft this far. We look to the amendments to put it right."],
        "against": ["We cannot accept a text that {x}. For us this is a matter of principle, and we will move to amend it.",
                    "My delegation will not support any text that {x}. We have an amendment ready."],
        "wait": ["Our support depends on one thing that matters deeply to us: whether this text {x}.",
                 "We ask one question of this draft: whether it {x}."],
        "truce": ["We have reached an understanding on this text. We will support it, and gladly."]},
    "guarded": {
        "for": ["This draft answers the problem before us. On this occasion we can say so plainly: support it.",
                "We have looked hard at this draft, and we find it sound. We ask others to support it."],
        "toofar": ["This draft goes too far for us as it stands. We will listen to the amendments.",
                   "We are not able to go as far as this draft does. We will wait for the amendments."],
        "against": ["We are not able to accept a text that {x}. We will move to amend it.",
                    "A text that {x} is more than my capital can accept. We have an amendment in mind."],
        "wait": ["Our support will depend on whether this text {x}. I can say no more yet.",
                 "We are watching one thing in this draft: whether it {x}."],
        "truce": ["We have reached an understanding on this text, and we will support it."]},
}


# ================================================================ more lines (12 Nov)
# The banks that talks draw on most, widened to six lines a slot so `pick` has room before anything repeats. They are
# added to the banks above (at the end, so the lines a saved game has already heard keep their numbers). Same rules.

_REACT = {
    "measured": {
        "strong": ["That is precisely the question my capital asks. Continue.", "You are on firm ground there. Please go on.",
                   "That argument bears directly on the text. I am listening."],
        "some": ["That is relevant, though it is not central for us.", "I can note that. It will not decide the matter.",
                 "There is a point there. I would not rest much on it."],
        "weak": ["That reasoning does not fit our instructions.", "I do not find that argument in my brief.",
                 "That is beside the point, as we read the text."]},
    "warm": {
        "strong": ["Oh, that's music to our ears. Do go on.", "You've put your finger on it, my friend.",
                   "That's close to our hearts. Tell me more."],
        "some": ["That's a kind thought, and partly right for us.", "We'd agree with some of that, certainly.",
                 "It helps a little. Go on."],
        "weak": ["Bless you for trying, but that isn't our worry.", "I can't honestly say that touches us.",
                 "That one doesn't speak to us, I'm sorry to say."]},
    "blunt": {
        "strong": ["Yes. That one matters to us. Go on.", "That's what I wanted to hear. More.", "Right. Now you have my attention."],
        "some": ["It's something. Not much.", "All right. That's a small plus.", "Could matter. Depends what comes with it."],
        "weak": ["Doesn't move us.", "Try a different one.", "That's nothing to us."]},
    "grave": {
        "strong": ["That speaks to my government's central concern. Go on.", "You touch on a matter of weight for us. Continue.",
                   "My capital will wish to hear more of that."],
        "some": ["It is a consideration. It is not the chief one.", "My government would grant you that much.",
                 "The point is taken. It settles little."],
        "weak": ["My government attaches no weight to that.", "That argument is of small interest to my capital.",
                 "You will not move my government on that ground."]},
    "urgent": {
        "strong": ["Yes, yes. That is what keeps us awake. Go on.", "You have named the very thing we fear. Continue.",
                   "That is our whole case, Ambassador. Please go on."],
        "some": ["It matters, yes. It is not what frightens us most.", "We care about that. We care about other things more.",
                 "That helps a little. Our need is greater."],
        "weak": ["That does nothing for the people we answer to.", "We cannot spend time on that, I'm afraid.",
                 "That is not the danger we came here about."]},
    "guarded": {
        "strong": ["That's one my capital asks about. Go on.", "Now that I can report with interest. Continue.",
                   "Hm. You're warmer than you know. Go on."],
        "some": ["It may count for something. I can't say how much.", "I'll note it. No more than that.",
                 "There's a little in that for us."],
        "weak": ["That won't mean much at home.", "I can't do anything with that.", "No. That isn't one of ours."]},
}

_VERDICT = {
    "measured": {
        "strong": ["Your argument was precise, and it met our instructions.", "I can report that case as it stands. It was sound.",
                   "The case was made with care, and it holds."],
        "some": ["There were points of merit in what you said.", "Your case was sound in places.",
                 "I have noted the stronger parts of that."],
        "weak": ["That reasoning does not meet our concerns.", "I cannot report that the case was persuasive.",
                 "The argument did not address our instructions."]},
    "warm": {
        "strong": ["Oh, well said. My capital will love that.", "You made that case beautifully, my friend.",
                   "I couldn't have put our own case better."],
        "some": ["There was a good deal in that for us.", "Some of that touched us, I'll admit.",
                 "You got part of the way to our hearts."],
        "weak": ["It was kindly put, but it missed us.", "I wanted to be convinced, and I wasn't.",
                 "That didn't speak to our worries, I'm afraid."]},
    "blunt": {
        "strong": ["Strong case. I can sell that at home.", "That was worth the time.", "Good pitch. It lands."],
        "some": ["Bits of that were worth hearing.", "Not bad. Not enough on its own.", "There's something there to work with."],
        "weak": ["That was the wrong pitch.", "Nothing in that for us.", "That one fell flat."]},
    "grave": {
        "strong": ["That was a serious case, seriously made.", "My government will find much to respect in that.",
                   "You have given my capital reason to listen."],
        "some": ["Parts of your case merit my government's attention.", "You made some points my capital will note.",
                 "It was not without weight."],
        "weak": ["That case does not meet my government's concerns.", "I cannot commend that argument to my capital.",
                 "You have not given my government a reason."]},
    "urgent": {
        "strong": ["Yes. That is what we needed to hear said.", "You made our case as if it were your own.",
                   "That gives us real hope, Ambassador."],
        "some": ["Part of that matters to us, truly.", "You came close to what we need.", "There is help for us in some of that."],
        "weak": ["That does not reach the heart of our trouble.", "We hoped for more than that.",
                 "That was not about the danger we face."]},
    "guarded": {
        "strong": ["That was better than I expected. I'll say so at home.", "A strong case. I don't say that often.",
                   "I can report that one well."],
        "some": ["Some of that may be useful to me.", "I'll note the better parts.", "There was a little there worth reporting."],
        "weak": ["That won't carry far at home.", "I've little to report from that.", "I don't think that moved anything."]},
}

_BUT = {
    "measured": ["Our objection to the wording stands, even so.", "The draft itself still presents a difficulty, however.",
                 "None of that cures the defect we see in the text."],
    "warm": ["Sadly, the draft still worries us.", "I wish that settled our trouble with the text. It doesn't.",
             "But the text is still hard for us, I'm afraid."],
    "blunt": ["The draft still hurts us, though.", "Doesn't change the text. That's the trouble.",
              "Still, the draft is the sticking point."],
    "grave": ["My government's objection to the text is unchanged, however.", "The draft remains unacceptable in parts, nonetheless.",
              "That does not lessen our concern at the text."],
    "urgent": ["But the draft would still harm us as it stands.", "Even so, the text leaves our fears unanswered.",
               "The danger in this draft is still there, though."],
    "guarded": ["The text is still a difficulty, though. I can say that.",
                "Even so, I can't report that the draft is any easier for us.",
                "It doesn't shift our trouble with the draft, I'm afraid."],
}

_STILL = {
    "measured": ["The draft, however, meets the aims in our instructions.", "Fortunately the text serves our interests on its own terms.",
                 "Our goals are met by the text itself, in any case."],
    "warm": ["Never mind: the draft gives us what we need.", "Luckily for us both, the text suits us nicely.",
             "But the draft works for us, so all is well."],
    "blunt": ["Doesn't matter. The draft meets our needs.", "Still, the text suits us fine.",
              "The draft serves our interests. That's enough."],
    "grave": ["The draft, nonetheless, serves my government's interests.", "The text meets our aims, however, and that is what counts.",
              "My government's purposes are served by the draft as it stands."],
    "urgent": ["But the text gives our people what they need.", "Still, this draft answers our problem, argument or no argument.",
               "Even so, the draft meets the need that brought us here."],
    "guarded": ["The draft suits us anyway. I can say that.", "As it happens, the text meets our needs.",
                "Still, the draft serves our interests, so I shan't complain."],
}

_STANCE = {
    "measured": {
        2: ["Our support is settled, and we shall state it in the debate.",
            "We are in favour without reservation, and will say so from our seat.",
            "My instructions are to support you, on the record and in full."],
        1: ["We are inclined to support you. The wording needs some attention.", "Our support is likely, given a few drafting changes.",
            "We lean towards yes. Certain phrases still need work."],
        0: ["My instructions are not final. An abstention cannot be excluded.", "We have not settled our position. We may abstain.",
            "Our vote is undecided. It could go either way, or to an abstention."],
        -1: ["The text as it is moving raises real concerns for us.", "We have reservations, and they are growing.",
             "Our difficulty with this draft is considerable."],
        -2: ["Our instructions are to vote against. They are not open to me.", "We oppose this text, and we will record that vote.",
             "My delegation cannot vote for the text. That is final."]},
    "warm": {
        2: ["You have all our support, and we'll say it loudly in the debate.",
            "We're with you, heart and soul. We'll speak up when the time comes.", "Our vote is yours, my friend, and our voice too."],
        1: ["We're leaning your way. A few small changes would settle it.", "I think we can support you. The text just needs a little work.",
            "We'd like to be on your side. Help us with a few changes."],
        0: ["We're truly undecided. It may come to an abstention.", "My capital can't make up its mind. We might well abstain.",
            "I wish I could tell you. It could go either way."],
        -1: ["I'm sorry, but this draft is troubling us more and more.",
             "We're uneasy, my friend. The text is going somewhere we can't follow.",
             "I won't hide it from you: we're worried about this draft."],
        -2: ["It's a no from us, I'm sorry to say. Our capital won't budge.", "We'll have to vote against, and it grieves me.",
             "My friend, we're against this text. I can't soften it."]},
    "blunt": {
        2: ["We're with you. Full stop. We'll say it out loud.", "Our vote's yours. We'll speak for the text too.",
            "Count on us. Vote and voice."],
        1: ["We lean yes. Tidy up the text and you have us.", "You'll likely get our support. The draft needs fixing first.",
            "We're on your side, more or less. Change a few things."],
        0: ["Undecided. Could be an abstention.", "No instructions yet. We may abstain.", "Could go either way. Ask me later."],
        -1: ["This draft is a problem for us.", "We've got serious doubts about this.",
             "The text is going the wrong way for us. That's a concern."],
        -2: ["We're against. That won't change.", "It's a no. Our capital said so in plain words.",
             "We can't vote for this. End of story."]},
    "grave": {
        2: ["My government supports you without reserve, and will declare it in the debate.",
            "Our vote and our voice are with you. The committee shall hear both.",
            "My government gives this text its full support, openly and on the floor."],
        1: ["My government leans towards support. It will expect changes.", "We are disposed to support you, if the text is amended.",
            "Support from my government is likely. The draft must first improve."],
        0: ["My capital has not instructed me. We may abstain.", "My government weighs the matter still. An abstention is possible.",
            "Our vote is not yet settled. It may go either way."],
        -1: ["My government has serious reservations about this draft.", "The course of this text gives my capital real concern.",
             "My government is troubled, Ambassador, and increasingly so."],
        -2: ["My government will vote against. That is settled.", "We oppose this text, and nothing said today alters that.",
             "My capital cannot accept the draft. I am instructed to say no."]},
    "urgent": {
        2: ["We are with you to the end, and we will say it in front of everyone.",
            "You have our full support. We will speak for this text with all we have.",
            "Our vote is yours, and we will not be quiet about it."],
        1: ["We lean towards you. Please, improve the text a little.", "We can support you, we think. A few changes would make us sure.",
            "We want to be on your side. The draft needs to come a little further."],
        0: ["We do not know yet. We may be forced to abstain.",
            "Our capital is still deciding, and we are running out of time. We may abstain.",
            "It could go either way for us. So much depends on the text."],
        -1: ["We are worried, Ambassador. This draft is moving away from us.", "This text is becoming a real problem for our people.",
             "Our concerns are serious, and they are growing."],
        -2: ["We must say no. We could not face our people otherwise.", "We will vote against. On this we cannot bend.",
             "This draft is against everything we came for. We cannot accept it."]},
    "guarded": {
        2: ["I'm able to say we support you. We'll say it in the room as well.", "We're with you. I don't often say that so plainly.",
            "You can have our vote, and a few words in the debate too."],
        1: ["We lean towards you. I can't make it firmer without changes.", "I'd expect us to support you, if the wording moves.",
            "We lean to yes more than no. It depends on the text."],
        0: ["No decision yet. An abstention wouldn't surprise me.", "I've no instructions to share. We may abstain.",
            "It could go either way. I really can't say more."],
        -1: ["There are concerns at home about this text. Serious ones.", "I can say we're troubled by the draft.",
             "We have doubts. I'd rather not list them."],
        -2: ["It's a no. I can't explain further.", "My instructions are to vote against. That's all I can tell you.",
             "We can't accept the draft. I've no room to say otherwise."]},
}

_RED = {
    "measured": {
        "open": ["Let me be precise at the outset: that clause is a red line for us. I will listen, but our room is very small.",
                 "For the record, the clause you seek is a red line in my instructions. Please continue, though we cannot go far.",
                 "I must note that your clause crosses a red line for my delegation. We can hear the argument. We cannot move much.",
                 "You should know before you begin that this clause is a red line for us. I will take notes, but expect little movement."],
        "close": ["I have heard the whole case. The clause is still a red line for us.",
                  "Your argument is recorded. It does not move a red line, and that clause is one.",
                  "We have reached the limit of my instructions. That clause is a red line.",
                  "Thank you for the care you took. A red line is a red line, and we cannot cross this one."]},
    "warm": {
        "open": ["Oh, my friend, I have to say it first: that clause is a red line for us. Tell me anyway, but we can't go far.",
                 "Before you go on, and I say it gently: your clause is a red line at home. I'll listen, of course.",
                 "You know I like to help, but that clause is a red line for us. Speak, and I'll hear you. We can't move much.",
                 "I'd rather be honest now than later: that clause is a red line for us. We'll listen, though we can't move far."],
        "close": ["I'm so sorry. I listened with an open heart, and it's still a red line for us.",
                  "You argued it well, my friend. It is a red line all the same.",
                  "I wish I had better news. That clause stays a red line for us.",
                  "Thank you for understanding. A red line is a red line, even between friends."]},
    "blunt": {
        "open": ["Before you start: that clause is a red line for us. Say your piece. We won't move far.",
                 "Fair warning: your clause is a red line. I'll hear you. Don't expect much.",
                 "That clause? A red line for us. Go ahead, but we're not moving far.",
                 "Know this first: your clause is a red line for us. Talk, if you want. It won't shift us far."],
        "close": ["Heard you. Still a red line.", "Nothing you said moves a red line. That clause is one.",
                  "No. The clause is a red line for us, and that's that.", "Good try. A red line doesn't move."]},
    "grave": {
        "open": ["Let there be no misunderstanding: that clause is a red line for my government. Speak, but do not expect us to move far.",
                 "Before you proceed, Ambassador, know that your clause is a red line for my capital. I will hear you. We will not move far.",
                 "My government regards the clause you want as a red line. I shall listen out of courtesy. We cannot move far.",
                 "I say this at once and plainly: your clause is a red line for my government. You may make your case. Little will change."],
        "close": ["I have listened. The clause remains a red line for my government.",
                  "My government does not move its red lines, Ambassador, and that clause is one.",
                  "You argued with skill. The clause is a red line for my government even so.",
                  "That is all I can say. The clause is a red line, and my capital will not cross it."]},
    "urgent": {
        "open": ["I must say this first: that clause is a red line for us. We will hear you, but we cannot give way.",
                 "Please know before you begin: your clause is a red line for our people. We will listen. We cannot move far.",
                 "Forgive me, but that clause is a red line for us, and it is not for sale. Speak, and we will listen.",
                 "You should hear it now: the clause you want is a red line for us. We have almost no room to move."],
        "close": ["We listened, truly. It is a red line for us, and it has to stay one.",
                  "I am sorry. That clause is a red line for us, because of what it would cost our people.",
                  "Nothing can change it, Ambassador. That clause is a red line for us.",
                  "You tried in good faith. A red line is a red line, and we cannot cross it."]},
    "guarded": {
        "open": ["I'd better say it now: that clause is a red line for us. I'll listen. I can't promise anything.",
                 "You should know your clause is a red line for my capital. Go on, but I've very little room.",
                 "That clause is a red line for us, I'm afraid. I'll hear what you have. I can't move far.",
                 "First, a caution: the clause you're after is a red line for us. Speak if you like. I can offer little."],
        "close": ["I listened. It's still a red line for us.", "That's all I'm able to say. The clause is a red line.",
                  "Nothing I heard changes a red line, and that clause is one.",
                  "It stays a red line for us. I can't go further than that."]},
}

_GREET = {
    "measured": ["Ambassador, may I raise a matter with you?", "A word on the text, Ambassador, if you have time.",
                 "Ambassador, I have a question for you."],
    "warm": ["There you are, Ambassador! Just the person I wanted.", "Ambassador, my friend, come and sit a moment.",
             "Ambassador! How good to find you free."],
    "blunt": ["Ambassador. One thing.", "Need a word, Ambassador.", "Ambassador. This won't take long."],
    "grave": ["Ambassador. I wish to speak with you.", "A matter of importance, Ambassador.",
              "Ambassador. My capital asks that we talk."],
    "urgent": ["Ambassador, thank goodness. I need a moment.", "Ambassador, please. There isn't much time.",
               "Ambassador, I must speak with you now."],
    "guarded": ["Ambassador. Have you a moment, in private?", "A word, Ambassador. Not here.",
                "Ambassador. I'd like to ask you something, quietly."],
}

for _reg in REGISTERS:
    for _level in ("strong", "some", "weak"):
        REACT[_reg][_level] += _REACT[_reg][_level]
        VERDICT[_reg][_level] += _VERDICT[_reg][_level]
    for _b in (2, 1, 0, -1, -2):
        STANCE[_reg][_b] += _STANCE[_reg][_b]
    for _when in ("open", "close"):
        RED[_reg][_when] += _RED[_reg][_when]
    BUT[_reg] += _BUT[_reg]
    STILL[_reg] += _STILL[_reg]
    GREET[_reg] += _GREET[_reg]
