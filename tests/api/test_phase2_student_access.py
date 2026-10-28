"""Students act only in their own role (spec §8.3): own delegation's paragraphs, amendments and tasks; no staff pages."""
from tests.api.helpers import ga, join_as, member_of
from tests.conftest import db_one, db_rows


def test_student_permissions(app, coord):
    com = ga(app)
    mem = member_of(app, com["id"])
    me, other = mem[0], mem[1]
    res = db_one(app, "SELECT id FROM resolution WHERE committee_id = ?", (com["id"],))["id"]
    p_mine = db_one(app, "SELECT id, current_version_id FROM paragraph WHERE resolution_id = ? AND kind='operative' AND position=1", (res,))
    p_other = db_one(app, "SELECT id, current_version_id FROM paragraph WHERE resolution_id = ? AND kind='operative' AND position=2", (res,))
    coord.post(f"/mun/paragraphs/{p_mine['id']}", {"text": "Owned text.", "tags": ["binding"], "version_id": p_mine["current_version_id"],
                                                   "owner_delegation_id": me["delegation_id"]})
    p_mine = db_one(app, "SELECT id, current_version_id FROM paragraph WHERE id = ?", (p_mine["id"],))
    c = join_as(app, me["student_id"])
    # edit own delegation's paragraph: allowed
    assert c.post(f"/mun/paragraphs/{p_mine['id']}", {"text": "Our better text.", "tags": ["binding"], "version_id": p_mine["current_version_id"]}).status_code == 200
    # edit someone else's: refused, must amend
    r = c.post(f"/mun/paragraphs/{p_other['id']}", {"text": "Hijack", "tags": [], "version_id": p_other["current_version_id"]})
    assert r.status_code == 403 and "table an amendment" in r.text
    # table an amendment: sponsor is forced to own delegation even if another is posted
    c.post(f"/mun/paragraphs/{p_other['id']}/amendments", {"kind": "replace", "proposed_text": "Our wording", "tags": ["binding"],
                                                            "sponsor_delegation_id": other["delegation_id"]})
    a = db_one(app, "SELECT * FROM amendment ORDER BY id DESC LIMIT 1")
    assert a["sponsor_delegation_id"] == me["delegation_id"]
    # students can't pass amendments, only withdraw their own
    assert c.post(f"/mun/amendments/{a['id']}/status", {"status": "passed"}).status_code == 403
    assert c.post(f"/mun/amendments/{a['id']}/status", {"status": "withdrawn"}).status_code == 200
    # evidence: only student intel, and needs a source
    r = c.post(f"/mun/committees/{com['id']}/evidence", {"subject_kind": "country", "iso3": "FJI", "target_kind": "paragraph",
                                                         "target_id_paragraph": p_other["id"], "position": "1", "source_type": "official_statement",
                                                         "source": "x"})
    assert r.status_code == 403
    r = c.post(f"/mun/committees/{com['id']}/evidence", {"subject_kind": "country", "iso3": "FJI", "target_kind": "paragraph",
                                                         "target_id_paragraph": p_other["id"], "position": "1", "source_type": "student_intel"})
    assert r.status_code == 400 and "needs a source" in r.text
    # staff-only pages
    for url in ("/admin", "/people", "/mun", "/chair", f"/mun/votes/paragraph/{p_other['id']}", "/mun/calibration"):
        assert c.get(url, follow_redirects=False).status_code in (403, 303), url


def test_students_see_only_own_tasks_and_class(app, coord):
    com = ga(app)
    mem = member_of(app, com["id"])
    me, other = mem[0], mem[1]
    para = db_one(app, "SELECT p.id FROM paragraph p JOIN resolution r ON r.id = p.resolution_id WHERE r.committee_id = ? AND p.kind='operative' LIMIT 1", (com["id"],))["id"]
    coord.post(f"/mun/predict/paragraph/{para}/tasks", {"delegation_id": other["delegation_id"], "top_n": 2})
    other_task = db_one(app, "SELECT id FROM task WHERE delegation_id = ?", (other["delegation_id"],))["id"]
    c = join_as(app, me["student_id"])
    assert "Lobby" not in c.get(f"/mun/committees/{com['id']}").text.split("Lobbying tasks")[1].split("Delegations")[0]
    assert c.post(f"/mun/tasks/{other_task}", {"status": "done"}).status_code == 403
    sc_com = db_one(app, "SELECT id FROM committee WHERE name = 'Security Council'")["id"]
    assert c.get(f"/mun/committees/{sc_com}").status_code == 403
