"""The Session's player accounts (Ben, 9 Nov 2026; D-103): a username and a password, plus "remember me".

Security, in one place:
- Sign-up is on (Ben, 9 Nov: no school approval needed); the coordinator can switch it off at /session/accounts.
  Signing in to an existing account still works if sign-up is switched off.
- Passwords: scrypt (app.util.hash_passphrase), 10 to 128 characters, not containing the username, not a common
  password. The hash is set outside the change log, so it is never logged.
- Sign-in: one generic error ("Username or password is wrong."), a hash check even for an unknown username (so the
  timing doesn't tell), and throttling by username and by address.
- Sessions: a random token in an HttpOnly, SameSite=Lax cookie (Secure over HTTPS); only its SHA-256 is stored.
  Without "remember me" the cookie lasts the browser session and the server ends it after 12 hours; with it, 30 days.
  A remembered token is replaced at most daily as it is used; signing out ends it; changing the password or deleting
  the account ends every session.
- Separation: accounts have their own tables and saves (account_save); nothing here can read a student's data.
- Erasure: deleting an account deletes its saves and sessions, and the account row itself.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from app.db import one, rows
from app.errors import UserError
from app.util import check_passphrase, hash_passphrase, new_token, now_iso, token_hash
from app.web.auth import Throttle

COOKIE = "soc_player"
SESSION_HOURS = 12
REMEMBER_DAYS = 30
ROTATE_AFTER_HOURS = 24
USERNAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{2,19}$")
RESERVED = {"admin", "administrator", "coordinator", "staff", "teacher", "system", "root", "moderator", "support"}
COMMON = {"password", "password1", "password12", "password123", "1234567890", "12345678910", "qwertyuiop", "qwertyuiop1",
          "iloveyou12", "letmein123", "football12", "abcdefghij", "0123456789", "1111111111", "aaaaaaaaaa", "passw0rd12",
          "welcome123", "monkey1234", "dragon1234", "sunshine12", "princess12", "baseball12"}
DUMMY = hash_passphrase("not a real password, for timing")

signin_throttle = Throttle(limit=5, window_s=300, lockout_s=300)
signup_throttle = Throttle(limit=5, window_s=3600, lockout_s=3600)


def open_signup(settings) -> bool:
    """New accounts may be made unless the coordinator has switched sign-up off."""
    cfg = settings.get("session_accounts", {}) or {}
    return bool(cfg.get("open", True))


def _ts(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def check_new(username: str, password: str) -> str:
    """The rules for a new account; returns the lower-case key."""
    if not USERNAME.match(username or ""):
        raise UserError("Choose a username of 3 to 20 letters, numbers or underscores, starting with a letter.")
    key = username.lower()
    if key in RESERVED:
        raise UserError("That username isn't available. Choose another.")
    check_password(password, key)
    return key


def check_password(password: str, key: str) -> None:
    if not isinstance(password, str) or not 10 <= len(password) <= 128:
        raise UserError("Choose a password of at least 10 characters (a short phrase works well).")
    low = password.lower()
    if key and key in low:
        raise UserError("Your password mustn't contain your username.")
    if low in COMMON or len(set(low)) < 4:
        raise UserError("That password is too easy to guess. Try a short phrase only you would think of.")


def create(w, username: str, password: str) -> int:
    key = check_new(username, password)
    if one(w.conn, "SELECT 1 FROM player_account WHERE username_key = ?", (key,)):
        raise UserError("That username is taken. Choose another.")
    aid = w.insert("player_account", {"username": username, "username_key": key, "created_at": now_iso()})
    w.conn.execute("UPDATE player_account SET pass_hash = ? WHERE id = ?", (hash_passphrase(password), aid))   # never logged
    w.log("player_account", aid, "password set", None, {"note": "a password was set"})
    return aid


def authenticate(conn, username: str, password: str):
    """The account if the username and password match; None otherwise. Always does one hash check."""
    key = (username or "").strip().lower()
    row = one(conn, "SELECT * FROM player_account WHERE username_key = ? AND deleted_at IS NULL", (key,)) if key else None
    ok = check_passphrase(password or "", row["pass_hash"] if row and row["pass_hash"] else DUMMY)
    return row if (row and ok) else None


def authenticate_row(row, password: str) -> bool:
    return bool(row) and check_passphrase(password or "", row["pass_hash"] or DUMMY)


def start(conn, account_id: int, remember: bool) -> str:
    token = new_token()
    t = _now()
    exp = t + (timedelta(days=REMEMBER_DAYS) if remember else timedelta(hours=SESSION_HOURS))
    conn.execute("INSERT INTO player_session (token_hash, account_id, remember, created_at, expires_at) VALUES (?,?,?,?,?)",
                 (token_hash(token), account_id, 1 if remember else 0, _ts(t), _ts(exp)))
    conn.execute("UPDATE player_account SET last_login_at = ? WHERE id = ?", (_ts(t), account_id))
    return token


def load(conn, token: str | None):
    """The signed-in account for this browser, or None (expired, signed out, or deleted)."""
    if not token or len(token) > 200:
        return None
    s = one(conn, "SELECT ps.*, pa.username, pa.deleted_at AS gone FROM player_session ps JOIN player_account pa ON pa.id = ps.account_id "
                  "WHERE ps.token_hash = ? AND ps.revoked_at IS NULL", (token_hash(token),))
    if not s or s["gone"] or s["expires_at"] <= _ts(_now()):
        return None
    return s


def rotate(conn, sess) -> str | None:
    """A remembered sign-in is replaced at most once a day as it is used: a stolen old cookie stops working."""
    if not sess or not sess["remember"]:
        return None
    made = datetime.fromisoformat(sess["created_at"])
    if _now() - made < timedelta(hours=ROTATE_AFTER_HOURS):
        return None
    conn.execute("UPDATE player_session SET revoked_at = ? WHERE id = ?", (_ts(_now()), sess["id"]))
    token = new_token()
    conn.execute("INSERT INTO player_session (token_hash, account_id, remember, created_at, expires_at) VALUES (?,?,?,?,?)",
                 (token_hash(token), sess["account_id"], 1, _ts(_now()), sess["expires_at"]))
    return token


def end(conn, token: str | None) -> None:
    if token:
        conn.execute("UPDATE player_session SET revoked_at = ? WHERE token_hash = ? AND revoked_at IS NULL", (_ts(_now()), token_hash(token)))


def end_all(conn, account_id: int) -> None:
    conn.execute("UPDATE player_session SET revoked_at = ? WHERE account_id = ? AND revoked_at IS NULL", (_ts(_now()), account_id))


def change_password(w, account_id: int, new: str) -> None:
    row = one(w.conn, "SELECT username_key FROM player_account WHERE id = ?", (account_id,))
    check_password(new, row["username_key"] if row else "")
    w.conn.execute("UPDATE player_account SET pass_hash = ? WHERE id = ?", (hash_passphrase(new), account_id))
    w.log("player_account", account_id, "password changed", None, {"note": "the password was changed"})
    end_all(w.conn, account_id)


def delete(w, account_id: int) -> None:
    """Erase an account: its saves, its sessions and the account itself."""
    w.conn.execute("DELETE FROM account_save WHERE account_id = ?", (account_id,))
    w.conn.execute("DELETE FROM player_session WHERE account_id = ?", (account_id,))
    w.conn.execute("DELETE FROM player_account WHERE id = ?", (account_id,))
    w.log("player_account", account_id, "erased", None, {"note": "the account and its saves were erased"})


def listing(conn) -> list[dict]:
    """Every account, most recently used first: when it last signed in, whether it's signed in now, and its games."""
    now = _ts(_now())
    year = _ts(_now() - timedelta(days=365))
    out = rows(conn, "SELECT pa.id, pa.username, pa.created_at, pa.last_login_at, "
                     "(SELECT COUNT(*) FROM account_save s WHERE s.account_id = pa.id AND s.deleted_at IS NULL) AS saves, "
                     "(SELECT MAX(s.updated_at) FROM account_save s WHERE s.account_id = pa.id AND s.deleted_at IS NULL) AS last_played, "
                     "(SELECT COUNT(*) FROM player_session ps WHERE ps.account_id = pa.id AND ps.revoked_at IS NULL AND ps.expires_at > ?) AS live "
                     "FROM player_account pa WHERE pa.deleted_at IS NULL "
                     "ORDER BY COALESCE(pa.last_login_at, pa.created_at) DESC", (now,))
    for r in out:
        r["stale"] = (r["last_login_at"] or r["created_at"]) < year
    return out


def erase_stale(w, days: int = 365) -> int:
    """Erase every account that hasn't signed in for `days` days (a year by default)."""
    cut = _ts(_now() - timedelta(days=days))
    ids = [r["id"] for r in rows(w.conn, "SELECT id FROM player_account WHERE deleted_at IS NULL AND COALESCE(last_login_at, created_at) < ?", (cut,))]
    for aid in ids:
        delete(w, aid)
    return len(ids)


def cookie_kwargs(request, remember: bool) -> dict:
    kw = {"httponly": True, "samesite": "lax", "secure": request.url.scheme == "https", "path": "/"}
    if remember:
        kw["max_age"] = REMEMBER_DAYS * 24 * 3600
    return kw
