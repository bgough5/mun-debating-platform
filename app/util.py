"""Small shared helpers: time, codes, hashing."""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import string
import time
from datetime import date, datetime, timezone

# Tests can freeze the clock by setting this to a callable returning epoch seconds.
_clock = time.time


def set_clock(fn) -> None:
    global _clock
    _clock = fn or time.time


def now() -> float:
    return _clock()


def process_rss_mb() -> float | None:
    """Resident memory of this process in MB, measured from inside it (Windows and Linux), else None.

    The server measures itself because on Windows a venv's python.exe is a launcher whose PID is
    not the server's, and there is no /proc to read from outside (D-081)."""
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class _Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]

        counters = _Counters()
        counters.cb = ctypes.sizeof(_Counters)
        kernel32, psapi = ctypes.WinDLL("kernel32"), ctypes.WinDLL("psapi")
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(_Counters), wintypes.DWORD]
        if psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
            return counters.WorkingSetSize / (1024 * 1024)
        return None
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1024
    except OSError:
        return None
    return None


def now_iso() -> str:
    return datetime.fromtimestamp(_clock(), timezone.utc).isoformat(timespec="seconds")


def today_iso() -> str:
    return datetime.fromtimestamp(_clock(), timezone.utc).date().isoformat()


def parse_iso(value: str) -> datetime | None:
    if not value:
        return None
    try:
        d = datetime.fromisoformat(value)
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def days_since(value: str) -> float | None:
    d = parse_iso(value)
    if d is None:
        try:
            d = datetime.combine(date.fromisoformat(value), datetime.min.time(), timezone.utc)
        except (ValueError, TypeError):
            return None
    return (_clock() - d.timestamp()) / 86400


# Ported from the v2 server (server/rooms.py): no 0/1/O/I to avoid misreading.
CODE_ALPHABET = "".join(c for c in string.ascii_uppercase + string.digits if c not in "01OI")


def new_code(length: int = 6) -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(length))


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# Passphrases: hashlib.scrypt (D-017). Format: scrypt$n$r$p$salt_hex$hash_hex
_N, _R, _P = 2 ** 14, 8, 1


def hash_passphrase(passphrase: str) -> str:
    salt = os.urandom(16)
    h = hashlib.scrypt(passphrase.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${_N}${_R}${_P}${salt.hex()}${h.hex()}"


def check_passphrase(passphrase: str, stored: str) -> bool:
    try:
        _, n, r, p, salt_hex, hash_hex = stored.split("$")
        h = hashlib.scrypt(passphrase.encode("utf-8"), salt=bytes.fromhex(salt_hex),
                           n=int(n), r=int(r), p=int(p), dklen=32)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(h.hex(), hash_hex)


def display_name(first_name: str, last_initial: str = "") -> str:
    return f"{first_name} {last_initial}." if last_initial else first_name
