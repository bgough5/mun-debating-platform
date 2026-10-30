"""D-087: cue cards from any speech (dot points or full), saved speeches that autosave and carry on, debate teammates
reading each other's cases and speeches read-only, with an overlap check."""
import re

from app.db import SYSTEM
from app.modules.debating import cuecards as K
from app.modules.debating import team as T
from tests.api.helpers import join_as
from tests.conftest import db_one, db_rows

SPEECH = ("Honourable adjudicators, ladies and gentlemen. Firstly, I believe that school uniforms reduce bullying "
          "because nobody can be judged on the clothes their family can afford. In 2019 a survey of Victorian schools "
          "found fewer reports of teasing after uniforms were introduced.\n\n"
          "Secondly, uniforms save families money over a year. Finally, they build pride in the school community!")


def students(app, n):
    return [r["id"] for r in db_rows(app, "SELECT id FROM student WHERE active = 1 ORDER BY id LIMIT ?", (n,))]


def free_speech(c, text=SPEECH):
    r = c.post("/me/prep/speeches", {"template_code": "free", "title": "Uniforms"}, follow_redirects=False)
    sid = int(re.search(r"/me/prep/speeches/(\d+)", r.headers["location"]).group(1))
    c.post(f"/me/prep/speeches/{sid}", {"title": "Uniforms", "target_seconds": "120", "sec_speech": text})
    return sid


# ---------- the card maker ----------

def test_dot_points_shorten_the_students_own_words_and_add_none():
    cards = K.build([("", SPEECH)], "dots")
    dots = [d for c in cards for d in c["body"].split("\n")]
    assert dots[0] == "Honourable adjudicators, ladies and gentlemen"          # all greeting: kept as written
    assert dots[1].startswith("School uniforms reduce bullying")               # "Firstly, I believe that" dropped
    source_words = set(re.findall(r"[a-z0-9']+", SPEECH.lower()))
    for d in dots:
        assert len(d.replace(" …", "").split()) <= K.DOT_WORDS
        assert set(re.findall(r"[a-z0-9']+", d.lower())) <= source_words, d  # never a word the student didn't write
    assert all(len(c["body"].split("\n")) <= K.DOTS_PER_CARD for c in cards)


def test_full_cards_keep_whole_sentences_and_stay_short():
    long = " ".join(f"Sentence number {i} makes one small point about the motion." for i in range(30))
    cards = K.build([("Argument 1", long)], "full")
    assert len(cards) > 1 and cards[0]["heading"] == "Argument 1" and cards[1]["heading"] == "Argument 1 (continued)"
    for c in cards:
        assert len(c["body"].split()) <= K.FULL_WORDS
        assert c["body"].endswith(".")                                        # no sentence cut in half
    assert " ".join(c["body"] for c in cards) == long


# ---------- a student's cards ----------

def test_free_form_speech_to_cards_to_print(app):
    st = join_as(app, students(app, 1)[0])
    sid = free_speech(st)
    page = st.get(f"/me/cards/speech/{sid}?mode=dots").text
    assert "<title>Cue cards: Uniforms" in page and "School uniforms reduce bullying" in page
    pr = st.get(f"/me/cards/speech/{sid}/print?mode=full").text
    n = len(K.build([("", SPEECH)], "full"))
    assert f"1 / {n}" in pr and "pc-text" in pr
    assert "large" in st.get(f"/me/cards/speech/{sid}/print?mode=dots&size=large").text
    assert st.get(f"/me/prep/speeches/{sid}/cards", follow_redirects=False).headers["location"] == f"/me/cards/speech/{sid}"


def test_edited_cards_are_kept_marked_stale_when_the_speech_changes_and_can_be_rebuilt(app):
    st = join_as(app, students(app, 1)[0])
    sid = free_speech(st)
    st.post(f"/me/cards/speech/{sid}", {"op": "save", "mode": "dots", "h_0": "Open", "b_0": "Greet the adjudicators\nUniforms stop bullying",
                                        "h_1": "", "b_1": ""})
    pr = st.get(f"/me/cards/speech/{sid}/print?mode=dots").text
    assert "Greet the adjudicators" in pr and "1 / 1" in pr
    assert "Your edited cards." in st.get(f"/me/cards/speech/{sid}?mode=dots").text
    assert "I believe that school uniforms reduce bullying" in st.get(f"/me/cards/speech/{sid}?mode=full").text   # full cards untouched
    free_speech_text = SPEECH + "\n\nThank you."
    st.post(f"/me/prep/speeches/{sid}", {"title": "Uniforms", "target_seconds": "120", "sec_speech": free_speech_text})
    assert "Your speech has changed since you edited these cards" in st.get(f"/me/cards/speech/{sid}?mode=dots").text
    st.post(f"/me/cards/speech/{sid}", {"op": "rebuild", "mode": "dots"})
    assert "Greet the adjudicators" not in st.get(f"/me/cards/speech/{sid}/print?mode=dots").text


def test_only_the_writer_opens_their_cards(app, coord):
    a, b = students(app, 2)
    sa = join_as(app, a)
    sid = free_speech(sa)
    sb = join_as(app, b)
    assert sb.get(f"/me/cards/speech/{sid}").status_code in (403, 404)
    assert sb.post(f"/me/cards/speech/{sid}", {"op": "save", "mode": "dots", "b_0": "x"}).status_code in (403, 404)
    assert coord.get(f"/me/cards/speech/{sid}", follow_redirects=False).status_code in (303, 401, 403)
    assert sa.get("/me/cards/nothing/1").status_code == 404


def test_autosave_answers_204_and_saves(app):
    st = join_as(app, students(app, 1)[0])
    sid = free_speech(st, "First draft.")
    r = st.post(f"/me/prep/speeches/{sid}", {"title": "Uniforms", "target_seconds": "120", "sec_speech": "Saved by itself.", "autosave": "1"},
                follow_redirects=False)
    assert r.status_code == 204
    assert "Saved by itself." in db_one(app, "SELECT sections FROM prep_speech WHERE id = ?", (sid,))["sections"]
    assert 'data-autosave' in st.get(f"/me/prep/speeches/{sid}").text


def test_carry_on_where_you_left_off(app):
    st = join_as(app, students(app, 1)[0])
    sid = free_speech(st)
    page = st.get("/me/prep").text
    assert "Carry on where you left off" in page and f'href="/me/prep/speeches/{sid}"' in page


def test_mun_draft_cards_for_the_writer_only(app):
    from tests.api.helpers import ga, member_of
    com = ga(app)
    m1, m2 = member_of(app, com["id"])[:2]
    a = join_as(app, m1["student_id"])
    a.post(f"/me/committees/{com['id']}/speeches", {"kind": "opening", "title": "Opening statement",
                                                    "body": "Australia supports the resolution. We ask for finance for the Pacific.",
                                                    "next": f"/me/committees/{com['id']}/prepare"})
    d = db_one(app, "SELECT id FROM speech_draft WHERE student_id = ? ORDER BY id DESC LIMIT 1", (m1["student_id"],))
    assert "Australia supports the resolution" in a.get(f"/me/cards/mun/{d['id']}?mode=dots").text
    assert join_as(app, m2["student_id"]).get(f"/me/cards/mun/{d['id']}").status_code == 403


# ---------- debate teams ----------

def _debate(app, coord, n=4):
    ids = students(app, n)
    r = coord.post("/start", {"op": "start", "kind": "debate", "student_id": [str(i) for i in ids]}, follow_redirects=False)
    rid = int(r.headers["location"].rsplit("/", 1)[1])
    run = db_one(app, "SELECT * FROM class_run WHERE id = ?", (rid,))
    sides = {s["student_id"]: s["side"] for s in db_rows(app, "SELECT * FROM class_run_speaker WHERE run_id = ? AND deleted_at IS NULL", (rid,))}
    return run, sides


def _case(app, c, run, side, claim, speech=""):
    c.post("/me/prep/cases", {"motion": run["motion"], "side": side}, follow_redirects=False)
    cid = db_one(app, "SELECT id FROM prep_case ORDER BY id DESC LIMIT 1")["id"]
    c.post(f"/me/prep/cases/{cid}/points", {"kind": "argument", "part_claim": claim, "part_reason": "Because of how it works in schools."})
    if speech:
        c.post(f"/me/prep/cases/{cid}", {"speech_text": speech})
    return cid


def test_teammates_read_each_others_case_and_speech_but_not_the_other_side(app, coord):
    run, sides = _debate(app, coord)
    aff = [s for s, side in sides.items() if side == "aff"]
    neg = [s for s, side in sides.items() if side == "neg"]
    a1, a2, n1 = join_as(app, aff[0]), join_as(app, aff[1]), join_as(app, neg[0])
    c1 = _case(app, a1, run, "aff", "Uniforms cut the cost of school for families", "My whole speech about cost.")
    _case(app, a2, run, "aff", "Uniforms build a sense of belonging")
    _case(app, n1, run, "neg", "Uniforms stop students expressing who they are", "The negative speech.")
    page = a2.get(f"/me/team/{run['id']}").text
    assert "Uniforms cut the cost of school for families" in page and "My whole speech about cost." in page
    assert "Uniforms stop students expressing who they are" not in page and "The negative speech." not in page
    assert f'action="/me/prep/cases/{c1}"' not in page                     # nothing on the page edits a teammate's case
    assert a2.post(f"/me/prep/cases/{c1}", {"speech_text": "hijacked"}).status_code == 403
    assert db_one(app, "SELECT speech_text FROM prep_case WHERE id = ?", (c1,))["speech_text"] == "My whole speech about cost."
    assert "The negative speech." in n1.get(f"/me/team/{run['id']}").text and "My whole speech" not in n1.get(f"/me/team/{run['id']}").text
    other = db_one(app, "SELECT id FROM student WHERE id NOT IN ({}) AND active = 1 LIMIT 1".format(",".join(map(str, sides))))["id"]
    assert join_as(app, other).get(f"/me/team/{run['id']}").status_code == 403
    assert f"/me/team/{run['id']}" in a1.get("/me/prep").text and f"/me/team/{run['id']}" in a1.get(f"/me/prep/cases/{c1}").text


def test_team_overview_flags_arguments_that_look_alike(app, coord):
    run, sides = _debate(app, coord)
    aff = [s for s, side in sides.items() if side == "aff"]
    _case(app, join_as(app, aff[0]), run, "aff", "Uniforms reduce bullying about expensive clothing brands")
    _case(app, join_as(app, aff[1]), run, "aff", "Bullying about expensive brands of clothing goes down with uniforms")
    page = join_as(app, aff[0]).get(f"/me/team/{run['id']}").text
    assert "These might overlap" in page and "rough word match" in page
    assert T.similarity("Uniforms save families money", "School trips should be free") < T.OVERLAP


def test_case_cards_use_the_speech_or_else_the_arguments(app, coord):
    run, sides = _debate(app, coord, 2)
    me = next(iter(sides))
    c = join_as(app, me)
    cid = _case(app, c, run, sides[me], "Uniforms make mornings easier for families")
    assert "Uniforms make mornings easier for families" in c.get(f"/me/cards/case/{cid}?mode=full").text
    c.post(f"/me/prep/cases/{cid}", {"speech_text": "Good morning. Mornings are calmer with a uniform."})
    page = c.get(f"/me/cards/case/{cid}?mode=full").text
    assert "Mornings are calmer with a uniform." in page and "Argument 1" not in page
    r = c.post(f"/me/prep/cases/{cid}", {"speech_text": "Autosaved text.", "autosave": "1"}, follow_redirects=False)
    assert r.status_code == 204 and db_one(app, "SELECT speech_text FROM prep_case WHERE id = ?", (cid,))["speech_text"] == "Autosaved text."
    # Saving the speech leaves the team line and definition alone (each form sends only its own fields).
    c.post(f"/me/prep/cases/{cid}", {"team_line": "Uniforms help everyone", "definition": ""})
    c.post(f"/me/prep/cases/{cid}", {"speech_text": "Final."})
    assert db_one(app, "SELECT team_line FROM prep_case WHERE id = ?", (cid,))["team_line"] == "Uniforms help everyone"


def test_erasing_a_student_removes_their_cue_cards(app):
    sid_student = students(app, 1)[0]
    st = join_as(app, sid_student)
    sid = free_speech(st)
    st.post(f"/me/cards/speech/{sid}", {"op": "save", "mode": "dots", "b_0": "My point"})
    from app.retention import erase_student
    with app.state.db.write(SYSTEM) as w:
        erase_student(w, sid_student)
    assert not db_rows(app, "SELECT id FROM cue_card_set WHERE student_id = ?", (sid_student,))


def test_print_splits_cards_that_would_not_fit_on_paper():
    cards = [{"heading": "Open", "body": "\n".join(f"Point {i}" for i in range(1, 8))}]
    large = K.fit_for_print(cards, "dots", large=True)
    assert [len(c["body"].splitlines()) for c in large] == [3, 3, 1]
    assert [c["heading"] for c in large] == ["Open", "Open (continued)", "Open (continued)"]
    assert len(K.fit_for_print(cards, "dots", large=False)) == 2
    long = [{"heading": "", "body": " ".join(f"Sentence {i} is here." for i in range(40))}]
    assert all(len(c["body"].split()) <= K.PRINT_FIT[("full", True)] for c in K.fit_for_print(long, "full", large=True))
