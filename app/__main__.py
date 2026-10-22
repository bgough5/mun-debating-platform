"""Run the platform:  python -m app [--demo] [--port 8080] [--host 0.0.0.0]

Students on the school Wi-Fi open http://<this laptop's IP>:8080/join
"""
from __future__ import annotations

import argparse
import socket

import uvicorn

from app.config import Settings


def local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))     # no packet is sent; this just picks the outgoing interface
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


def main() -> None:
    ap = argparse.ArgumentParser(description="South Oakleigh Debating & MUN platform")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--demo", action="store_true", help="open the demo dataset (fake data only)")
    ap.add_argument("--data-dir", default=None, help="folder for databases, backups and local config")
    args = ap.parse_args()
    settings = Settings() if not args.data_dir else Settings(data_dir=__import__("pathlib").Path(args.data_dir))
    settings.load()
    if args.demo and settings.dataset != "demo":
        settings.set("dataset", "demo")
    from app.main import create_app
    app = create_app(settings)
    ip = local_ip()
    print(f"\n  South Oakleigh Debating & MUN platform ({settings.dataset} data)")
    print(f"  Staff, on this laptop:   http://localhost:{args.port}/")
    print(f"  Students, on school Wi-Fi: http://{ip}:{args.port}/join\n")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning", ws_ping_interval=20, ws_ping_timeout=20)


if __name__ == "__main__":
    main()
