from __future__ import annotations

import os
import socket
import sys
import time


def _wait_for(host: str, port: int, timeout_seconds: float) -> None:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        sock = socket.socket()
        sock.settimeout(3)
        try:
            sock.connect((host, port))
            return
        except Exception as exc:  # pragma: no cover - startup probe only
            last_error = exc
            time.sleep(2)
        finally:
            sock.close()
    raise RuntimeError(f"dependency {host}:{port} unavailable: {last_error}")


def main() -> int:
    timeout_seconds = float(os.environ.get("APP_DEPENDENCY_WAIT_SECONDS", "180") or 180)
    checks = (
        ("mysql", int(os.environ.get("MYSQL_PORT", "3306") or 3306)),
        ("redis", int(os.environ.get("REDIS_PORT", "6379") or 6379)),
    )
    for host, port in checks:
        _wait_for(host, port, timeout_seconds)
    print("dependencies_ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
