"""D-089: the live room. Gavel, stage and vote markers for the projector's sounds and title cards, the vote reveal,
raised placards, breaking news (scripted for the fictional Veloria crisis, or the chair's own), the whip-count
tile map, and the Sound and motion setting."""
import re

from app.db import SYSTEM
from app.fakedata import DEMO_STAFF_PASSPHRASE
from app.modules.chair import service as C
from app.modules.mun import worldmap as WMAP
from app.modules.mun.tilemap import LATLON
from app.modules.sim import service as SIM
from tests.api.helpers import join_as
from tests.conftest import Client, db_one, db_rows, login_staff


def evatt(app, coord, n=6):
    ids = [r["id"] for r in db_rows(app, "SELECT id FROM student WHERE active = 1 ORDER BY id LIMIT ?", (n,))]
    r = coord.post("/start", {"op": "start", "kind": "evatt", "student_id": [str(i) for i in ids]}, follow_redirects=False)
    sid = int(r.headers["location"].rsplit("/", 1)[1])
    tok = db_one(app, "SELECT projector_token FROM live_session WHERE id = ?", (sid,))["projector_token"]
    return sid, ids, tok


def marker(html, name):
    m = re.search(rf'data-fx-{name}="([^"]*)"', html)
    return m.group(1) if m else None


def test_every_page_carries_the_sound_and_motion_setting_and_the_effects_script(app, coord):
    page = coord.get("/").text
    assert 'data-fx-sound="projector"' in page and 'data-fx-motion="on"' in page and "/static/js/effects.js" in page
    r = coord.post("/admin/effects", {"fx_sound": "chair"}, follow_redirects=False)
    assert r.status_code == 303
    page = coord.get("/").text
    assert 'data-fx-sound="chair"' in page and 'data-fx-motion="off"' in page
    assert coord.post("/admin/effects", {"fx_sound": "loud"}).status_code == 400
    assert "Try the gavel" in coord.get("/admin").text


def test_only_the_coordinator_changes_sound_settings(app):
    staff_id = db_one(app, "SELECT id FROM staff WHERE name = 'Demo Chair'")["id"]
    t = login_staff(Client(app, base_url="http://testserver").__enter__(), staff_id, DEMO_STAFF_PASSPHRASE)
    assert t.post("/admin/effects", {"fx_sound": "everywhere"}).status_code == 403


def test_projector_marks_the_room_and_the_gavel_changes_its_marker(app, coord):
    sid, _, tok = evatt(app, coord)
    proj = coord.get(f"/projector/{tok}/plain").text
    assert 'data-fx-room="projector"' in proj and "Turn on sound" in proj
    before = marker(proj, "gavel")
    coord.post(f"/chair/{sid}/gavel", {"knocks": "2"})
    after = marker(coord.get(f"/projector/{tok}/f").text, "gavel")
    assert after != before and int(after) > int(before)
    assert 'data-fx-room="chair"' in coord.get(f"/chair/{sid}").text
    st = join_as(app, db_one(app, "SELECT student_id FROM delegation_member dm JOIN delegation d ON d.id = dm.delegation_id "
                                  "JOIN live_session s ON s.committee_id = d.committee_id WHERE s.id = ? LIMIT 1", (sid,))["student_id"])
    assert st.post(f"/chair/{sid}/gavel", {"knocks": "2"}, follow_redirects=False).status_code in (303, 401, 403)


def test_stage_and_division_markers_follow_the_session(app, coord):
    sid, _, tok = evatt(app, coord)
    with app.state.db.write(SYSTEM) as w:
        SIM.set_stage(w, sid, "voting_procedure")
        did = C.open_division(w, sid, "Procedural test", "motion", None, procedural=True)
    f = coord.get(f"/projector/{tok}/f").text
    assert marker(f, "stage") == "voting_procedure" and marker(f, "division") == str(did)


def test_the_closed_vote_is_ready_for_the_reveal(app, coord):
    sid, ids, tok = evatt(app, coord)
    with app.state.db.write(SYSTEM) as w:
        did = C.open_division(w, sid, "Procedural test", "custom", None, procedural=True)
    for st in ids[:3]:
        join_as(app, st).post(f"/live/{sid}/vote", {"vote": "yes"})
    with app.state.db.write(SYSTEM) as w:
        C.close_division(w, did)
    f = coord.get(f"/projector/{tok}/f").text
    assert marker(f, "result") == str(did)
    assert '<template id="fx-reveal"' in f
    n = len(re.findall(r"data-fx-vote=", f))
    assert n == db_one(app, "SELECT COUNT(*) AS n FROM division_vote WHERE division_id = ?", (did,))["n"] and n > 0


def test_placards_go_up_the_chair_recognises_them_and_lowers_them(app, coord):
    sid, ids, tok = evatt(app, coord)
    with app.state.db.write(SYSTEM) as w:                                    # placards are for the floor (D-092)
        SIM.set_stage(w, sid, "floor")
    a, b = join_as(app, ids[0]), join_as(app, ids[1])
    a.post(f"/live/{sid}/placard", {"action": "raise"})
    b.post(f"/live/{sid}/placard", {"action": "raise"})
    a.post(f"/live/{sid}/placard", {"action": "raise"})                       # twice is still one placard
    assert db_one(app, "SELECT COUNT(*) AS n FROM placard WHERE session_id = ? AND lowered_at IS NULL", (sid,))["n"] == 2
    page = a.get(f"/live/{sid}").text
    assert "Lower my placard" in page and 'class="deed"' in page
    console = coord.get(f"/chair/{sid}").text
    assert "Placards up (2)" in console
    assert marker(coord.get(f"/projector/{tok}/f").text, "placards") == "2"
    pa = db_one(app, "SELECT id FROM placard WHERE session_id = ? AND student_id = ? AND lowered_at IS NULL", (sid, ids[0]))["id"]
    coord.post(f"/chair/{sid}/placards", {"action": "recognise", "placard_id": str(pa)})
    assert db_one(app, "SELECT COUNT(*) AS n FROM speakers_list_entry WHERE session_id = ? AND student_id = ? AND status = 'waiting'",
                  (sid, ids[0]))["n"] == 1
    assert "Raise my placard" in a.get(f"/live/{sid}").text
    coord.post(f"/chair/{sid}/placards", {"action": "lower_all"})
    assert db_one(app, "SELECT COUNT(*) AS n FROM placard WHERE session_id = ? AND lowered_at IS NULL", (sid,))["n"] == 0
    b.post(f"/live/{sid}/placard", {"action": "raise"})
    b.post(f"/live/{sid}/placard", {"action": "lower"})
    assert db_one(app, "SELECT COUNT(*) AS n FROM placard WHERE session_id = ? AND lowered_at IS NULL", (sid,))["n"] == 0


def test_scripted_breaking_news_reaches_every_screen_labelled_fictional(app, coord):
    sid, ids, tok = evatt(app, coord)
    console = coord.get(f"/chair/{sid}").text
    assert "Next scripted update" in console and "6 left" in console
    first = db_one(app, "SELECT * FROM crisis_script WHERE topic_code = 'SC_VELORIA' ORDER BY position LIMIT 1")
    coord.post(f"/chair/{sid}/news", {"script_id": str(first["id"])})
    student = join_as(app, ids[0]).get(f"/live/{sid}").text
    assert first["headline"] in student and "Fictional scenario update" in student
    proj = coord.get(f"/projector/{tok}/f").text
    assert first["headline"] in proj and marker(proj, "news") not in (None, "none")
    assert "5 left" in coord.get(f"/chair/{sid}").text
    coord.post(f"/chair/{sid}/news", {"headline": "Lunch is extended by ten minutes", "body": ""})
    assert "From the chair." in join_as(app, ids[1]).get(f"/live/{sid}").text
    assert coord.post(f"/chair/{sid}/news", {"headline": "x"}).status_code == 400


def test_a_general_assembly_has_no_script_but_takes_the_chairs_own_news(app, coord):
    ids = [r["id"] for r in db_rows(app, "SELECT id FROM student WHERE active = 1 ORDER BY id LIMIT 3")]
    r = coord.post("/start", {"op": "start", "kind": "unaa", "student_id": [str(i) for i in ids]}, follow_redirects=False)
    sid = int(r.headers["location"].rsplit("/", 1)[1])
    page = coord.get(f"/chair/{sid}").text
    assert "Next scripted update" not in page and "Write your own update" in page
    script = db_one(app, "SELECT id FROM crisis_script LIMIT 1")["id"]
    assert coord.post(f"/chair/{sid}/news", {"script_id": str(script)}).status_code == 404


def test_world_map_has_every_country_and_tokens_never_overlap():
    seeded = [r for r in open("app/db/seed/countries.csv", encoding="utf-8").read().splitlines()[1:] if r.strip()]
    codes = [line.split(",")[0].strip('"') for line in seeded]
    shapes = WMAP.data()["countries"]
    assert all(c in shapes or c in LATLON for c in codes)                  # drawn, or a dot at its real position
    assert len([c for c in codes if c in shapes]) >= 175
    w, h = WMAP.data()["width"], WMAP.data()["height"]
    for chosen in (codes[:31], ["FRA", "DEU", "BEL", "NLD", "LUX", "CHE", "AUT", "ITA", "GBR", "IRL", "DNK", "POL", "CZE"]):
        t = WMAP.place_tokens(chosen, w, h)
        pts = list(t.values())
        for i, a in enumerate(pts):
            for b in pts[i + 1:]:
                assert abs(a["x"] - b["x"]) >= WMAP.TOKEN_W - 1 or abs(a["y"] - b["y"]) >= WMAP.TOKEN_H - 1
    usa, chn, aus = WMAP.anchor("USA"), WMAP.anchor("CHN"), WMAP.anchor("AUS")
    assert usa[0] < chn[0] and aus[1] > chn[1]


def test_alliances_light_up_without_touching_the_prediction_model(app, coord):
    com = db_one(app, "SELECT id FROM committee ORDER BY id LIMIT 1")["id"]
    nato = coord.get(f"/mun/committees/{com}/map?view=NATO").text
    assert "<title>World map:" in nato and "NATO" in nato and "wm-member" in nato and "not yet checked" in nato
    assert "African Group" in coord.get(f"/mun/committees/{com}/map").text
    assert not db_rows(app, "SELECT id FROM bloc WHERE code IN ('NATO', 'AU', 'ASEAN', 'G20', 'BRICS')")   # map-only, never in the model
    assert db_one(app, "SELECT COUNT(*) AS n FROM alignment_member am JOIN alignment a ON a.id = am.alignment_id WHERE a.code = 'NATO'")["n"] == 32


def test_students_see_their_countrys_groupings_and_who_else_is_in_them(app):
    m = db_one(app, "SELECT dm.student_id, d.committee_id, d.iso3 FROM delegation_member dm JOIN delegation d ON d.id = dm.delegation_id "
                    "WHERE d.iso3 = 'FRA' AND dm.deleted_at IS NULL LIMIT 1")
    page = join_as(app, m["student_id"]).get(f"/mun/committees/{m['committee_id']}/map").text
    assert "Your country's groupings" in page and "NATO" in page and "Also in the room" in page
    other = db_one(app, "SELECT id FROM committee WHERE id != ? LIMIT 1", (m["committee_id"],))
    outsider = db_one(app, "SELECT st.id FROM student st WHERE st.id NOT IN (SELECT student_id FROM delegation_member dm JOIN delegation d "
                           "ON d.id = dm.delegation_id WHERE d.committee_id = ?) AND st.class_id != (SELECT class_id FROM committee WHERE id = ?) "
                           "LIMIT 1", (m["committee_id"], m["committee_id"]))
    if outsider:
        assert join_as(app, outsider["id"]).get(f"/mun/committees/{m['committee_id']}/map").status_code == 403


def test_whip_map_hides_the_direction_until_voting_then_reveals(app, coord):
    sid, ids, tok = evatt(app, coord)
    with app.state.db.write(SYSTEM) as w:
        SIM.set_stage(w, sid, "voting_procedure")
        s = C.get_session(w.conn, sid)
        res = db_one(app, "SELECT id FROM resolution WHERE committee_id = ? LIMIT 1", (s["committee_id"],))
        rid = SIM.start_whip(w, s, "resolution", res["id"], "Whole resolution", per_student=2)
    for st in ids:
        for p in db_rows(app, "SELECT delegation_id FROM whip_prediction WHERE round_id = ? AND student_id = ?", (rid, st)):
            join_as(app, st).post(f"/live/{sid}/whip/{rid}", {"delegation_id": str(p["delegation_id"]), "vote": "yes"})
    f = coord.get(f"/projector/{tok}/f").text
    assert 'data-fx-map="%d:open"' % rid in f and " call" in f and "wm-yes" not in f and "wm-no " not in f
    with app.state.db.write(SYSTEM) as w:
        did = C.open_division(w, sid, "Whole resolution", "resolution", res["id"])
        SIM.lock_round(w, rid, did)
    f = coord.get(f"/projector/{tok}/f").text
    assert 'data-fx-map="%d:locked"' % rid in f and "wm-yes" in f
    with app.state.db.write(SYSTEM) as w:
        C.close_division(w, did)
    page = coord.get(f"/chair/{sid}/whip-map").text
    assert 'data-fx-map="%d:revealed"' % rid in page and "read" in page and "correctly" in page
    assert "<title>Whip map:" in page


def test_now_speaking_and_amendment_adopted_markers(app, coord):
    """D-091: the projector knows who was just called (for the "Now speaking" card) and the latest adopted
    amendment, with the clause before and after (for the "Amendment adopted" moment)."""
    sid, ids, tok = evatt(app, coord)
    st = join_as(app, ids[0])
    st.post(f"/live/{sid}/speak", {})
    with app.state.db.write(SYSTEM) as w:
        C.next_speaker(w, sid)
    f = coord.get(f"/projector/{tok}/f").text
    assert marker(f, "speaker") not in (None, "none") and ", " in marker(f, "speaker-name")
    assert marker(f, "adopted") == "none"
    com = db_one(app, "SELECT committee_id FROM live_session WHERE id = ?", (sid,))["committee_id"]
    para = db_one(app, "SELECT p.id, v.text FROM paragraph p JOIN resolution r ON r.id = p.resolution_id JOIN paragraph_version v "
                       "ON v.id = p.current_version_id WHERE r.committee_id = ? AND p.kind = 'operative' ORDER BY p.position LIMIT 1", (com,))
    st.post(f"/mun/committees/{com}/amendments", {"paragraph_id": str(para["id"]), "kind": "replace",
                                                 "proposed_text": "Demands an immediate ceasefire monitored by the region;", "rationale": ""})
    aid = db_one(app, "SELECT id FROM amendment ORDER BY id DESC LIMIT 1")["id"]
    st.post(f"/mun/amendments/{aid}/act", {"action": "submit"})
    from app.modules.floor import service as F
    with app.state.db.write(SYSTEM) as w:
        F.accept_friendly(w, sid, aid)
    f = coord.get(f"/projector/{tok}/f").text
    assert marker(f, "adopted") not in (None, "none")
    assert '<template id="fx-adopt"' in f and "Demands an immediate ceasefire monitored by the region" in f
    assert para["text"][:40].replace("'", "&#39;") in f or para["text"][:40] in f
