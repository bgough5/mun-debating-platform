"""The speech coach (D-100): what sits beside every speech box.

Everything here is data for `app/static/js/coach.js`, which counts and marks the student's own writing in the
browser. Nothing is sent anywhere and nothing is written for the student: the techniques are spotted by simple
patterns (and the page says so), and the phrase bank holds the set phrases of debating and Model UN procedure
that every speaker uses, with "…" where the student's own words go.

Patterns are written so that Python's `re` and JavaScript's `RegExp` read them the same way (tests check them in
Python against the examples; the browser uses them with the `gi` flags).
"""
from __future__ import annotations

KINDS = ("speech", "debate", "mun")
PACES = [(110, "Slow"), (130, "Steady"), (150, "Quick")]      # 130 matches the estimate on the server (prep.WPM)
AIMS = [30, 60, 90, 120, 180, 240, 300, 360, 480]
DEFAULT_AIM = {"speech": 180, "debate": 240, "mun": 90}

# (code, name, what it does, an example, pattern or None for a check the script does itself, kinds)
TECHNIQUES = [
    ("question", "Rhetorical question", "A question you don't expect answered. It makes the audience think along with you.",
     "If not us, then who?", r"[^.!?\n]*\?", KINDS),
    ("three", "Rule of three", "Three items in a row sound complete and stick in the memory.",
     "It is cheaper, fairer and faster.", r"\b[\w'-]+(?: [\w'-]+){0,3}, [\w'-]+(?: [\w'-]+){0,3},? (?:and|or) [\w'-]+", KINDS),
    ("inclusive", "Inclusive language", "\"We\" and \"our\" put you and the audience on the same side.",
     "This is our school and our choice.", r"\b(?:we|us|our|ours|ourselves|together)\b", ("speech", "debate")),
    ("direct", "Direct address", "Speaking to the audience as \"you\" pulls them in.",
     "You have felt this too.", r"\b(?:you|your|yours|yourself|yourselves)\b", ("speech",)),
    ("numbers", "Facts and figures", "A number makes a claim concrete and harder to dismiss.",
     "One in four students skips breakfast.",
     r"\b\d[\d,.]*(?: ?(?:%|per ?cent|million|billion|thousand))?|\b(?:half|a third|a quarter|one in \w+)\b", KINDS),
    ("source", "Expert or source", "Naming where a fact comes from makes it trustworthy.",
     "According to the Bureau of Meteorology, …",
     r"\b(?:according to|research(?:ers)?|stud(?:y|ies)|reports?|surveys?|experts?|scientists?|statistics|data shows?)\b", KINDS),
    ("emotive", "Emotive language", "Words with feeling in them make the audience care, not just agree.",
     "a devastating loss for families",
     r"\b(?:devastat\w*|tragic\w*|heartbreak\w*|suffer\w*|vulnerable|innocent|terrif\w*|fear\w*|hope\w*|dream\w*|"
     r"proud|pride|shame\w*|outrage\w*|unfair|injustice|justice|dangerous|danger|threat\w*|crisis|catastroph\w*|"
     r"desperate\w*|alarming|incredible|inspir\w*|brave\w*|cruel\w*|safe|safety|precious|betray\w*|abandon\w*)\b", KINDS),
    ("story", "Story or example", "A short story or a picture in the mind makes the point real.",
     "Imagine walking into class on day one …",
     r"\b(?:imagine|picture this|for example|for instance|take the case of|when I was|last (?:year|week|summer|month)|"
     r"I remember|consider)\b", ("speech", "debate")),
    ("anaphora", "Repetition for effect", "Starting sentences the same way on purpose builds rhythm (\"We will … We will …\").",
     "We will listen. We will act. We will lead.", None, KINDS),
    ("contrast", "Contrast", "Putting two ideas side by side makes yours look better.",
     "Not a cost, but an investment.",
     r"\bnot\b[^.!?\n]{1,60}\bbut\b|\b(?:instead of|rather than|whereas|on the other hand|however)\b", KINDS),
    ("action", "Call to action", "Tell the audience exactly what you want them to do.",
     "Today, I urge you to vote yes.",
     r"\b(?:we must|we need to|we should|I urge|we urge|I ask you|let us|let's|join (?:us|me)|"
     r"vote (?:for|against|yes|no|in favour)|calls? (?:on|upon)|it is time to)\b", KINDS),
    ("signpost", "Signposting", "Telling the audience where you are in the speech keeps them with you.",
     "My second argument is …",
     r"\b(?:firstly|secondly|thirdly|finally|first of all|to begin|to start|in conclusion|to conclude|in summary|"
     r"to sum up|moving on|turning to|my (?:first|second|third|next|final) (?:point|argument|reason))\b", KINDS),
    ("rebuttal", "Rebuttal", "Name what the other side said before you take it apart.",
     "Our opponents told you that … but …",
     r"\b(?:our opponents?|the (?:other|opposing) (?:side|team)|the (?:affirmative|negative|opposition|government)(?: team)?|"
     r"they (?:said|told you|claimed|argued|suggested)|their (?:first|second|third) (?:argument|speaker))\b", ("debate",)),
    ("teamline", "Team line", "Repeating your team line ties every speaker's speech to one case.",
     "", None, ("debate",)),
    ("diplomatic", "Diplomatic address", "Formal address shows respect for the Chair and the committee.",
     "Honourable Chair, distinguished delegates, …",
     r"\b(?:honou?rable|distinguished|esteemed|(?:madam|mister|mr|madame) chair|fellow delegates?|the delegations? of|"
     r"the delegates? (?:of|from))\b", ("mun",)),
    ("clauses", "The resolution", "Pointing to the clauses keeps the committee on the text it will vote on.",
     "Operative clause 3 must …",
     r"\b(?:operative (?:clause|paragraph)s?|preambular|clauses? \d+|the (?:draft )?resolution|amendments?|"
     r"this committee|member states)\b", ("mun",)),
]

FILLERS = ["very", "really", "just", "basically", "actually", "literally", "totally", "pretty much", "kind of",
           "sort of", "a lot", "lots of", "stuff", "things", "I think", "I feel", "I guess", "in my opinion", "maybe",
           "obviously", "honestly"]

# Common words that are never worth flagging as repeated.
STOP = sorted(set("""a about above after again against all also am an and any are as at be because been before being
below between both but by can could did do does doing down during each few for from further had has have having he her
here hers herself him himself his how i if in into is it its itself just me more most my myself no nor not now of off on
once only or other our ours ourselves out over own same she should so some such than that the their theirs them
themselves then there these they this those through to too under until up very was we were what when where which while
who whom why will with would you your yours yourself yourselves will shall may might must one two three also than
there's it's that's don't can't won't isn't aren't we're they're i'm you're let's""".split()))

LONG_SENTENCE = 30          # words: past this, a sentence is hard to say in one breath
REPEAT_MIN = 3              # a content word used this often (or more) is listed

# Click to add. "{country}" becomes the student's country; "…" is where their own words go (selected after adding).
PHRASES = {
    "mun": [
        ("Opening", ["Honourable Chair, distinguished delegates,",
                     "The delegation of {country} thanks the Chair for the opportunity to speak.",
                     "{country} is honoured to address this committee on …"]),
        ("Your position", ["{country} firmly believes that …",
                           "The delegation of {country} cannot support … because …",
                           "As a nation that …, {country} knows first-hand that …",
                           "{country} welcomes the spirit of this resolution, but …"]),
        ("Answering others", ["{country} thanks the honourable delegate of … for their remarks.",
                              "While {country} shares the concerns of the delegate of …, we believe …",
                              "With respect to the delegate of …, the facts suggest otherwise: …"]),
        ("Working together", ["{country} invites like-minded delegations to work with us on …",
                              "We are open to amendments that …",
                              "{country} will gladly co-sponsor a resolution that …"]),
        ("The resolution", ["Operative clause … should be strengthened to …",
                            "{country} proposes an amendment to operative clause … so that …",
                            "This committee must not leave the resolution without …"]),
        ("Closing", ["{country} urges this committee to …",
                     "For these reasons, {country} will vote … on this resolution.",
                     "{country} yields its remaining time to the Chair.",
                     "{country} yields the floor to points of information."]),
        ("From the floor", ["Motion to open a moderated caucus on …, for … minutes, with a speaking time of … seconds.",
                            "Motion to open an unmoderated caucus for … minutes.",
                            "Point of information: would the honourable delegate of … agree that …?",
                            "Point of order: …",
                            "Point of personal privilege: …"]),
    ],
    "debate": [
        ("Opening", ["Adjudicator, ladies and gentlemen,",
                     "Today our team will prove that …",
                     "We define the motion as …",
                     "Our team line is: …"]),
        ("Signposting", ["I will make … arguments. First, …",
                         "My first argument is …",
                         "Turning to my second argument, …",
                         "This matters because …"]),
        ("Rebuttal", ["Our opponents told you that … But …",
                      "Even if that were true, …",
                      "This argument fails for two reasons. First, …",
                      "The other side has not answered our point that …"]),
        ("Evidence", ["For example, …", "According to …, …", "Consider …"]),
        ("Closing", ["To summarise, our team has shown that …",
                     "For all of these reasons, we are proud to …",
                     "The question you need to ask is …"]),
    ],
    "speech": [
        ("A strong start", ["Imagine …", "What if …?", "Picture this: …", "Have you ever …?"]),
        ("Moving on", ["But that's not the whole story.", "Here's why that matters: …", "So what does this mean for us?",
                       "Think about it this way: …"]),
        ("Closing", ["So next time you …", "If you remember one thing today, remember this: …",
                     "The choice is ours.", "Thank you."]),
    ],
}


def techniques(kind: str) -> list[dict]:
    return [{"code": c, "name": n, "what": w, "example": e, "pattern": p}
            for c, n, w, e, p, kinds in TECHNIQUES if kind in kinds]


def coach_config(kind: str = "speech", country: str | None = None, team_line: str | None = None,
                 aim: int | None = None, readonly: bool = False) -> dict:
    """Everything the panel needs, as one JSON object (rendered into a <script type="application/json">)."""
    kind = kind if kind in KINDS else "speech"
    phrases = [] if readonly else [{"group": g, "lines": [p.replace("{country}", country or "our country") for p in ps]}
                                   for g, ps in PHRASES[kind]]
    return {
        "kind": kind, "readonly": readonly, "aim": aim or DEFAULT_AIM[kind], "aims": AIMS, "paces": PACES,
        "techniques": techniques(kind), "fillers": FILLERS, "stop": STOP, "long": LONG_SENTENCE,
        "repeat": REPEAT_MIN, "team_line": (team_line or "").strip(), "phrases": phrases,
        "first_person": kind == "mun",
    }
