"""The address students type: the laptop's school-network IP, never "localhost"."""
from __future__ import annotations

import socket

LOCAL = {"localhost", "127.0.0.1", "::1", "testserver"}


def local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))     # no packet is sent; this just picks the outgoing interface
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


def student_base_url(request) -> str:
    """Base URL for join cards and QR codes. A coordinator can fix it in config.json ("join_base_url") if the
    laptop has several networks; otherwise the host the page was opened on, or this machine's IP when that is localhost."""
    fixed = (request.app.state.settings.get("join_base_url") or "").rstrip("/")
    if fixed:
        return fixed
    host = request.url.hostname or "localhost"
    port = request.url.port
    if host in LOCAL:
        host = local_ip()
    return f"{request.url.scheme}://{host}" + (f":{port}" if port and port not in (80, 443) else "")
