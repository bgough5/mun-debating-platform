"""Phase 6 item 4: first-run wizard, join cards with a local QR code, in-app help."""
import segno

from app.modules.people.routes import _qr_svg
from app.web.markdown import render_markdown
from tests.conftest import db_one, db_rows, login_coordinator, make_settings, new_client


def _real_app(tmp_path):
    from app.main import create_app
    return create_app(make_settings(tmp_path, dataset="real"))


def test_wizard_real_dataset(tmp_path):
    app = _real_app(tmp_path)
    with new_client(app) as c:
        login_coordinator(c)
        r = c.get("/")
        assert "Getting started" in r.text
        r = c.get("/welcome")
        assert r.status_code == 200 and "1. Create a class" in r.text and "2. Add the students" not in r.text
        r = c.post("/welcome/class", {"name": "Fake 10M", "year": "2026"})
        assert "Its class code is" in r.text and "2. Add the students" in r.text
        cid = db_one(app, "SELECT id FROM class WHERE name = 'Fake 10M'")["id"]
        # A roster CSV with extra columns: only first name and initial are kept; surname and email are never stored.
        csv = "first_name,last_initial,surname,email\r\nTesta,Q,Testerson,testa@example.invalid\r\nTestb,,Other,x@example.invalid\r\n"
        r = c.post("/welcome/roster", {"class_id": cid}, files={"file": ("roster.csv", csv.encode(), "text/csv")})
        assert "Added 2 student(s)" in r.text
        st = db_rows(app, "SELECT first_name, last_initial FROM student WHERE class_id = ? ORDER BY first_name", (cid,))
        assert st == [{"first_name": "Testa", "last_initial": "Q"}, {"first_name": "Testb", "last_initial": ""}]
        assert not db_rows(app, "SELECT seq FROM event_log WHERE after_json LIKE '%Testerson%' OR after_json LIKE '%example.invalid%'")
        r = c.post("/welcome/roster", {"class_id": cid, "action": "fake"})
        assert r.status_code == 400 and "demo dataset" in r.text          # no fake students in real data
        r = c.post("/welcome/roster", {"class_id": cid}, files={"file": ("r.csv", b"surname\r\nX\r\n", "text/csv")})
        assert r.status_code == 400 and "first_name column" in r.text
        ct = db_one(app, "SELECT id FROM committee_type ORDER BY id LIMIT 1")["id"]
        r = c.post("/welcome/committee", {"class_id": cid, "conference": "Fake practice", "committee": "General Assembly",
                                          "committee_type_id": ct, "delegations": "AUS FJI KEN"})
        assert r.status_code == 200 and "4. Print join cards" in r.text
        com = db_one(app, "SELECT * FROM committee WHERE class_id = ?", (cid,))
        assert len(db_rows(app, "SELECT id FROM delegation WHERE committee_id = ?", (com["id"],))) == 3


def test_wizard_fake_roster_in_demo(app, coord):
    r = coord.post("/welcome/class", {"name": "Demo extra"})
    cid = db_one(app, "SELECT id FROM class WHERE name = 'Demo extra'")["id"]
    r = coord.post("/welcome/roster", {"class_id": cid, "action": "fake", "count": "7"})
    assert "Added 7 student(s)" in r.text


def test_join_cards_qr_points_at_lan_address(app, coord):
    c = db_one(app, "SELECT * FROM class WHERE code = 'DEMO9M'")
    r = coord.get(f"/people/classes/{c['id']}/join-cards")
    assert r.status_code == 200 and c["code"] in r.text and "testserver" not in r.text
    from app.web.net import local_ip
    url = f"http://{local_ip()}/join?code={c['code']}"
    assert _qr_svg(url) in r.text                         # the QR encodes the LAN address with the class code
    assert segno.make(url, error="m").designator.startswith(("1", "2", "3", "4", "5"))
    app.state.settings.values["join_base_url"] = "http://10.1.2.3:8080/"
    r = coord.get(f"/people/classes/{c['id']}/poster")
    assert "http://10.1.2.3:8080/join" in r.text and _qr_svg(f"http://10.1.2.3:8080/join?code={c['code']}", scale=10) in r.text
    app.state.settings.values.pop("join_base_url")


def test_join_prefills_code(client):
    r = client.get("/join?code=ab-c1<script>")
    assert 'value="ABC1SCRIPT"' in r.text and "filled in from the QR code" in r.text


def test_help_pages_and_context(client, coord):
    assert client.get("/help/glossary").status_code == 200
    assert "Whip count" in client.get("/help/glossary").text
    assert "Tap <strong>your own</strong> first name" in client.get("/help/students").text
    assert client.get("/help/staff", follow_redirects=False).status_code == 303      # staff only
    r = coord.get("/help/staff")
    assert r.status_code == 200 and "<h2" in r.text and "Before class" in r.text
    assert "Help: Model UN" in coord.get("/mun").text
    assert "Help: Debating" in coord.get("/debating").text
    assert "Help: Admin" in coord.get("/admin").text


def test_markdown_subset_is_escaped():
    html = str(render_markdown("## Title & more\n\nSome **bold** and `code` <script>x</script>.\n\n- one\n- two [link](/help)\n\n1. first\n2. [bad](javascript:alert(1))"))
    assert '<h2 id="title-more">Title &amp; more</h2>' in html
    assert "<strong>bold</strong>" in html and "<code>code</code>" in html and "&lt;script&gt;" in html
    assert "<ul>\n<li>one</li>\n<li>two <a href=\"/help\">link</a></li>\n</ul>" in html
    assert "<ol>" in html and "javascript:" not in html
