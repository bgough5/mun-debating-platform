"""Design system (D-058): brand in the header, letterhead in print and Word exports, projector theme."""
import io
import zipfile

from app.exports import table_docx, text_docx


def test_header_brand_and_print_letterhead(coord):
    html = coord.get("/").text
    assert 'class="brand"' in html and "South Oakleigh College" in html and "/static/soc_logo.png" in html
    assert 'class="letterhead"' in html and "Printed " in html
    assert 'id="toasts"' in html and 'aria-live="polite"' in html


def test_word_exports_carry_letterhead():
    for data in (text_docx("Run sheet", "ROUND 1\n- Welcome"), table_docx("Ladder", ["Team"], [["A"]])):
        z = zipfile.ZipFile(io.BytesIO(data))
        header = z.read("word/header1.xml").decode()
        assert "South Oakleigh College" in header
        assert any(n.startswith("word/media/") for n in z.namelist())


def test_projector_theme(app, coord):
    from tests.conftest import db_one
    com = db_one(app, "SELECT id FROM committee LIMIT 1")["id"]
    r = coord.post(f"/chair/committee/{com}/open", follow_redirects=False)
    sid = int(r.headers["location"].rstrip("/").rsplit("/", 1)[1])
    tok = db_one(app, "SELECT projector_token FROM live_session WHERE id = ?", (sid,))["projector_token"]
    html = coord.get(f"/projector/{tok}").text
    assert 'class="projector"' in html and "proj-brand" in html
