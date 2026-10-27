"""In-app help (Phase 6 item 4): contextual help for each section, a glossary, a student quick-start and the staff guide.

Definitions are plain-English descriptions of how this platform and typical school conferences use a term; the
glossary says to check a conference's own handbook, because rules differ between competitions.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request

from app.web.auth import require_staff
from app.web.markdown import render_markdown
from app.web.templating import env, render

router = APIRouter(prefix="/help")
DOCS = Path(__file__).resolve().parents[3] / "docs"

# Contextual help: the first matching path prefix wins. (title, [points]) — short, task-focused.
CONTEXT = [
    ("/admin", "Admin", [
        "Every table here is editable: countries, blocs, voting rules, rules of procedure, procedure stages (the chair's script), rubrics, templates, debate formats and house points rules.",
        "Edits are versioned: open a row and use History to restore an earlier version. Deleted rows can be restored for 30 days.",
        "Data: switch between real and demo data, back up, download a backup or restore one.",
    ]),
    ("/chair", "Chairing a session", [
        "Six stages: roll call, agenda, opening statements, the floor, voting procedure, debrief. The guide shows what to say and what happens next.",
        "On the floor, ask for points or motions. Take motions most disruptive first: an unmoderated caucus is up to 10 minutes a time.",
        "Amendments reach the floor once they have their signatories (a fifth of the delegations with students, at least two). Take speakers for and against, then vote; an adopted amendment changes the text on every screen.",
        "Points raised from devices appear at the top of the floor panel. Delegate messages are under Tools; you can hide one.",
        "Close debate (two-thirds; nine in the Security Council) moves to voting procedure. If the resolution fails and another draft is ready, reopen the floor with it.",
        "If your browser closes, open the chair console again: everything is as it was.",
    ]),
    ("/live", "Your live session", [
        "Speak and negotiate out loud: the tabs help, they don't replace the room.",
        "Floor: the stage, who is speaking, the speakers list and votes. Motions and votes: propose a caucus (up to 10 minutes) and second motions. Points: log a point so the chair sees it.",
        "Messages: notes to other delegations. They aren't marked, but the chair can read them. My speech: your own drafts, only for you.",
        "Amendments: see every submitted amendment as tracked changes, sign them, suggest edits. Friends and foes: your reading of who supports each operative clause.",
        "Your screen updates by itself. If it says it's reconnecting, wait a moment.",
    ]),
    ("/me/prep", "Prep and practise", [
        "Debate case: pick a motion and a side, write a team line and your arguments in four parts (claim, reasoning, example, impact).",
        "Rebuttal: the other side's likely arguments are listed. Answer each in four steps: they say, but, because, so.",
        "Speeches: choose a structure, write each part in your own words, then rehearse with the timer or print cue cards.",
        "Your teacher can score your work and comment. The structure check only counts which parts you've written.",
    ]),
    ("/me/practice", "Practising a speech", [
        "Impromptu: draw a topic, think with a structure card, then speak. Prepared: rehearse one of your speeches. Rebuttal drill: answer an argument in a minute.",
        "One bell rings for the warning and two at time. The timer never stops you: it shows how far over you went.",
        "Score yourself honestly afterwards. Your teacher can comment on what you save.",
    ]),
    ("/me/sim", "Practice committee", [
        "You run one delegation; the others are computed, each with a hidden position.",
        "Talk to up to five delegations, record what you think each will do, amend the paragraph if it would win votes, then call the vote.",
        "The debrief shows how well you read the room. Nothing here changes your class's work.",
    ]),
    ("/me/committees", "Preparing for a committee", [
        "Read your country's brief and the proposed resolution, then write your opening statement in your own words.",
        "Friends and foes: for each operative clause, record who you think is with you. The engine's estimate is beside it, labelled as an estimate.",
    ]),
    ("/me", "Your page", [
        "Your delegation, tasks, live sessions, debates, practice speeches and pathway milestones.",
        "Practise: timed speeches with rubric self-review. Practice negotiation: practise negotiating with a rule-based partner, which is not AI (an AI service is used only if your school has approved one).",
    ]),
    ("/mun", "Model UN", [
        "Conference → committee → delegations and resolutions. Allocate students to countries on the committee page.",
        "Evidence: record what a country has said, with its source. Predictions use it; a country with no evidence is shown as unknown.",
        "Prediction: the chance a paragraph passes, the countries most likely to swing it, and lobbying tasks for students.",
        "Each country is marked Sourced, Estimate only or Unknown. \"Estimate only\" means the prediction rests on the model's archetype guess or an unsourced note: treat it as a starting point, not evidence. The prediction page shows how much of the outcome rests on such estimates.",
        "Workspace: one editor per paragraph; everyone else proposes amendments. History restores any version.",
    ]),
    ("/debating/runs", "Running a class debate or speaking round", [
        "Open the projector view on the screen the class sees; run it from your own page.",
        "Space starts or pauses the timer; the right arrow moves to the next speaker, the left arrow goes back. A presentation clicker works too.",
        "The timer shows the bells as colour and words: green while speaking, amber after the warning bell, red at time. It keeps counting past time so you can see by how much.",
        "Each speaker's time is recorded when you move on. Add scores, a result and comments under Scores and results; students whose names match the class list see their own.",
    ]),
    ("/debating/prep", "Student preparation", [
        "Each student's debate cases, rebuttals and speech drafts. Score each point on its rubric and leave a comment: the student sees both.",
        "The structure check counts which parts a student has written. It doesn't judge quality; your rubric score does.",
    ]),
    ("/debating", "Debating and public speaking", [
        "Class debate: type each team's speakers, set the times, and project the timer. Speaking round: a list of speakers, prepared or impromptu.",
        "Student preparation: open a class to see and score the cases, rebuttals and speeches students have written.",
        "Tournaments and carnivals: draws, ballots, ladders and house points, as before.",
    ]),
    ("/people", "People", [
        "Classes, their codes and rosters (first names only), staff, and each student's pathway.",
        "Print join cards with a QR code from the class page. Change the class code each term.",
        "If a student's name is taken on another device, approve or deny the request on the class page.",
    ]),
    ("/intel", "Intelligence", [
        "UN voting data can't be imported until its licence is confirmed here. Synthetic test data is for the demo only.",
        "AI features are offline unless the school's approval is recorded in AI settings.",
    ]),
    ("/", "This platform", [
        "Model UN: prediction, resolution workspace and live chair tools. Debating: draws, ballots, ladders and house points.",
        "Students join at /join with the class code and their first name.",
        "Every change is saved as it happens; Undo and History are available on most pages.",
    ]),
]

GLOSSARY = [
    ("Impromptu speech", "A speech on a topic you see only moments before speaking, with a short time to think. A structure such as point, reason, example, point helps."),
    ("Rebuttal", "Answering the other side's argument: say it fairly, show what's wrong with it, back that up, and say why it matters."),
    ("Team line", "A team's whole case in one sentence, repeated by every speaker so the adjudicator can follow it."),
    ("Warning bell", "A single bell before a speaker's time is up (often a minute before); a double bell means time. Speakers finish their sentence and sit down."),
    ("Reply speech", "A short closing speech by each team, usually given by the first or second speaker; the Negative replies first."),
    ("Friends and foes", "Your own record of which delegations support or oppose each operative clause. Only you see it; the engine's estimate beside it is labelled as an estimate."),
    ("Abstain", "Vote neither for nor against. In most General Assembly rules, abstentions don't count toward the majority."),
    ("Adjudicator", "The judge of a debate. A panel decides by majority; the chair adjudicator breaks a 1–1 tie."),
    ("Agenda", "The topic the committee will debate, set at the start by a motion or by consent."),
    ("Amendment", "A proposed change to a paragraph of a draft resolution. Friendly: all sponsors agree, so it's added without a vote. Unfriendly: it's voted on before the resolution."),
    ("Ballot", "The adjudicator's score sheet for one debate: each speaker's marks and who won."),
    ("Bloc", "A group of countries that often vote together, such as a regional group or a negotiating bloc."),
    ("Bye", "A round in which a team has no opponent because there is an odd number of teams."),
    ("Caucus", "Moderated: a debate on a sub-topic with its own speakers list and short speeches. Unmoderated: free time to lobby and draft, up to 10 minutes a motion here."),
    ("Computed delegation", "A country with no student in this platform, whose roll-call answer and vote come from the prediction engine. Always labelled."),
    ("Delegation", "The student or students representing one country in a committee."),
    ("Division", "A formal vote. The platform applies the committee's voting rule, including the Security Council veto."),
    ("Draft resolution", "The text the committee debates: preambular paragraphs (why) and operative paragraphs (what to do)."),
    ("Estimate only", "A country whose prediction rests only on estimates (the archetype model, an unsourced note, an invented demo position or an AI estimate), with no sourced evidence. Shown with its own label so a guess is never mistaken for evidence."),
    ("Evidence", "What a country has said or done on an issue, with a source. The prediction engine weights it by how reliable the source is."),
    ("House points", "Points for school houses from debates and carnivals. Every entry says who added it and why; mistakes are reversed, never deleted."),
    ("Ladder", "The ranking of teams: wins, then total points, then margin."),
    ("Mandate", "What your country would want, judged from the evidence. In the debrief your vote is compared with it, and your teacher can override that judgement."),
    ("Matter, manner, method", "The three parts of a speaker's score in schools debating: what you argue, how you deliver it, and how it is structured."),
    ("Motion (debating)", "The statement a debate is about, such as \"That schools should ban homework\"."),
    ("Motion (MUN)", "A procedural proposal, such as a moderated caucus or closing debate. Most need a seconder and a vote."),
    ("Operative paragraph", "A numbered paragraph of a resolution that says what will be done. These are what get amended and voted on."),
    ("Point of order", "Raised when the rules of procedure aren't being followed. The chair rules on it at once."),
    ("Point of personal privilege", "Raised when something stops you taking part, such as not being able to hear. The only point that may interrupt a speaker."),
    ("Point of parliamentary inquiry", "A question to the chair about the rules of procedure."),
    ("Pivotal vote", "A vote that, if changed, would have flipped the result."),
    ("Power pairing", "Matching teams on the same number of wins after the first round."),
    ("Present and voting", "A roll-call answer meaning the delegation will vote yes or no on substantive matters, not abstain."),
    ("Prediction", "The platform's estimate of how a vote will go, as probabilities with the evidence shown. An estimate, not a fact."),
    ("Right of reply", "A request to answer when a speech has insulted your country. The chair decides; if granted, you speak next."),
    ("Roll call", "The chair calls each delegation at the start of a session to record who is present."),
    ("Signatory", "A delegation that signs an amendment or draft so it can be debated. Signing doesn't commit your vote."),
    ("Speakers list", "The queue of delegations waiting to speak."),
    ("Sponsor", "A delegation that wrote or backs a draft resolution or amendment."),
    ("Swing country", "A country whose vote is uncertain and would change the result most if it moved: the best people to lobby."),
    ("Tracked changes", "How the platform shows an amendment: added words highlighted and underlined, removed words struck through, against today's text."),
    ("Veto", "In the Security Council, a no vote from a permanent member (China, France, Russia, the UK, the US) blocks a substantive resolution. An abstention isn't a veto."),
    ("Whip count", "Predicting, before a vote, how each delegation will vote. In this platform students are scored against the votes actually cast."),
    ("Yield", "Giving the rest of your speaking time to the chair, to questions, or to another delegate."),
]

GLOSSARY.sort(key=lambda t: t[0].lower())


def page_help(path: str) -> tuple[str, list[str]]:
    for prefix, title, points in CONTEXT:
        if path == prefix or path.startswith(prefix.rstrip("/") + "/") or prefix == "/":
            return title, points
    return CONTEXT[-1][1], CONTEXT[-1][2]


env.globals["page_help"] = page_help


@router.get("")
def help_home(request: Request):
    return render(request, "core/help_home.html", {"title": "Help", "topics": CONTEXT})


@router.get("/glossary")
def glossary(request: Request):
    return render(request, "core/glossary.html", {"title": "Glossary", "terms": GLOSSARY})


@router.get("/students")
def students_quickstart(request: Request):
    return render(request, "core/help_students.html", {"title": "Student quick-start"})


@router.get("/staff")
def staff_guide(request: Request, sess=Depends(require_staff)):
    path = DOCS / "staff-guide.md"
    text = path.read_text(encoding="utf-8") if path.exists() else "# Staff guide\n\nThe guide file is missing from this copy."
    body = text.split("\n", 1)[1] if text.startswith("# ") else text      # the page has its own h1
    return render(request, "core/help_staff.html", {"title": "Staff guide", "body": render_markdown(body)})
