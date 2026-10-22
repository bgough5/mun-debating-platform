"""Backups (spec C-9, Phase 5): download, restore, refusals, and sign-out after restore."""
import io
import zipfile

from tests.api.helpers import join_as
from tests.conftest import db_one


def _download(coord) -> bytes:
    r = coord.get("/admin/data/download")
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    z = zipfile.ZipFile(io.BytesIO(r.content))
    assert set(z.namelist()) == {"dataset.db", "manifest.json"}
    return r.content


def test_restore_round_trip_and_sign_out(coord, app):
    stu = db_one(app, "SELECT st.id FROM student st JOIN class c ON c.id = st.class_id WHERE c.code = 'DEMO9M' LIMIT 1")["id"]
    pupil = join_as(app, stu)
    assert pupil.get("/me").status_code == 200
    backup = _download(coord)
    coord.post("/people/classes", {"name": "Made after the backup", "year": "2026"})
    assert db_one(app, "SELECT id FROM class WHERE name = 'Made after the backup'")
    r = coord.post("/admin/data/restore", {}, files={"file": ("b.zip", backup, "application/zip")})
    assert "Tick the confirmation box" in r.text
    r = coord.post("/admin/data/restore", {"confirm": "yes"}, files={"file": ("b.zip", backup, "application/zip")})
    assert r.status_code == 200 and "Restored the backup" in r.text
    assert db_one(app, "SELECT id FROM class WHERE name = 'Made after the backup'") is None
    # The coordinator who restored stays signed in; the student signed in at backup time must sign in again.
    assert coord.get("/admin/data").status_code == 200
    r = pupil.get("/me", follow_redirects=False)
    assert r.status_code == 303 and "/join" in r.headers["location"]
    pupil.__exit__(None, None, None)
    # The data before the restore was kept as a file.
    assert any("before-restore" in p.name for p in app.state.settings.backup_dir.glob("*.db"))


def test_restore_refuses_bad_files(coord, app):
    for name, data in (("x.zip", b"not a zip"), ("x.zip", _zip({"hello.txt": b"hi"})),
                       ("x.zip", _zip({"dataset.db": b"x", "manifest.json": b'{"app": "other"}'})),
                       ("x.zip", _zip({"dataset.db": b"not sqlite", "manifest.json": b'{"app": "soc-platform"}'}))):
        r = coord.post("/admin/data/restore", {"confirm": "yes"}, files={"file": (name, data, "application/zip")})
        assert r.status_code in (400, 422) or "isn't" in r.text or "damaged" in r.text or "wasn't" in r.text, r.text[:300]
        assert "Restored the backup" not in r.text
    assert db_one(app, "SELECT COUNT(*) AS n FROM student")["n"] > 0


def _zip(files: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for k, v in files.items():
            z.writestr(k, v)
    return buf.getvalue()
