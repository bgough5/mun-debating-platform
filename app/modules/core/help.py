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
        "The guide at the top shows the stage, what to say and what happens next. Next moves on; Jump to a stage goes anywhere.",
        "Roll call: students answer on their devices; delegations with no student are answered by the engine and labelled computed.",
        "Before a vote, start a whip count so students predict how named delegations will vote; it locks when you open the vote.",
        "If your browser closes, open the chair console again: everything is as it was.",
    ]),
    ("/live", "Your live session", [
        "The stage tracker shows where the committee is; \"What you can do now\" says what you can do.",
        "Add yourself to the speakers list, answer the roll, predict votes in a whip count, and vote for your delegation.",
        "Your screen updates by itself. If it says it's reconnecting, wait a moment.",
    ]),
    ("/me/sim", "Practice committee", [
        "You run one delegation; the others are computed, each with a hidden position.",
        "Talk to up to five delegations, record what you think each will do, amend the paragraph if it would win votes, then call the vote.",
        "The debrief shows how well you read the room. Nothing here changes your class's work.",
    ]),
    ("/me", "Your page", [
        "Your delegation, tasks, live sessions, debates, practice speeches and pathway milestones.",
        "Practise: timed speeches with rubric self-review. AI delegation: practise negotiating (offline unless your school has approved an AI service).",
    ]),
    ("/mun", "Model UN", [
        "Conference → committee → delegations and resolutions. Allocate students to countries on the committee page.",
        "Evidence: record what a country has said, with its source. Predictions use it; a country with no evidence is shown as unknown.",
        "Prediction: the chance a paragraph passes, the countries most likely to swing it, and lobbying tasks for students.",
        "Each country is marked Sourced, Estimate only or Unknown. \"Estimate only\" means the prediction rests on the model's archetype guess or an unsourced note: treat it as a starting point, not evidence. The prediction page shows how much of the outcome rests on such estimates.",
        "Workspace: one editor per paragraph; everyone else proposes amendments. History restores any version.",
    ]),
    ("/debating", "Debating", [
        "Event → setup (teams, rooms, adjudicators) → rounds. Round 1 is random; later rounds are power-paired.",
        "Adjudicators enter ballots; the ladder, speaker tab and house points update as they arrive.",
        "Practice: tick who is here and the platform fits the format to the group, from solo speeches to full rooms.",
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
    ("Abstain", "Vote neither for nor against. In most General Assembly rules, abstentions don't count toward the majority."),
    ("Adjudicator", "The judge of a debate. A panel decides by majority; the chair adjudicator breaks a 1–1 tie."),
    ("Agenda", "The topic the committee will debate, set at the start by a motion or by consent."),
    ("Amendment", "A proposed change to a paragraph of a draft resolution. Friendly: all sponsors agree, so it's added without a vote. Unfriendly: it's voted on before the resolution."),
    ("Ballot", "The adjudicator's score sheet for one debate: each speaker's marks and who won."),
    ("Bloc", "A group of countries that often vote together, such as a regional group or a negotiating bloc."),
    ("Bye", "A round in which a team has no opponent because there is an odd number of teams."),
    ("Caucus", "Moderated: a debate on a sub-topic with its own speakers list and short speeches. Unmoderated: free time to lobby and draft."),
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
    ("Pivotal vote", "A vote that, if changed, would have flipped the result."),
    ("Power pairing", "Matching teams on the same number of wins after the first round."),
    ("Present and voting", "A roll-call answer meaning the delegation will vote yes or no on substantive matters, not abstain."),
    ("Prediction", "The platform's estimate of how a vote will go, as probabilities with the evidence shown. An estimate, not a fact."),
    ("Roll call", "The chair calls each delegation at the start of a session to record who is present."),
    ("Speakers list", "The queue of delegations waiting to speak."),
    ("Sponsor", "A delegation that wrote or backs a draft resolution or amendment."),
    ("Swing country", "A country whose vote is uncertain and would change the result most if it moved: the best people to lobby."),
    ("Veto", "In the Security Council, a no vote from a permanent member (China, France, Russia, the UK, the US) blocks a substantive resolution. An abstention isn't a veto."),
    ("Whip count", "Predicting, before a vote, how each delegation will vote. In this platform students are scored against the votes actually cast."),
    ("Yield", "Giving the rest of your speaking time to the chair, to questions, or to another delegate."),
]


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
