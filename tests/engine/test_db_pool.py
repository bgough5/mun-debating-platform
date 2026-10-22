"""Phase 7 item 1: read connections of finished threads are closed, not kept for the life of the server (D-064)."""
import sqlite3
import threading

from app.db import Database


def test_finished_threads_do_not_keep_connections(tmp_path):
    path = tmp_path / "t.db"
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE x (a)")
    c.commit()
    c.close()
    db = Database(path)

    def work():
        with db.read() as conn:
            conn.execute("SELECT COUNT(*) FROM x").fetchone()

    for _ in range(200):                     # the server's worker threads come and go like this
        t = threading.Thread(target=work)
        t.start()
        t.join()
    assert db.pooled_count() <= 1            # before Phase 7: 200 open connections
    db.dispose()
    assert db.pooled_count() == 0
