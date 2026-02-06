"""
Minimal client simulator for the licensing server.

Why this exists:
- Quickly validate the server behavior without a real desktop client.
- Reproduce flows: validate -> heartbeat -> release.
- Useful for manual testing and future regression checks.

Uses only Python stdlib (no requests dependency).

Examples:
  python client_sim.py validate --license-id LIC-ACME-001 --org-id acme-corp --device-id dev-1
  python client_sim.py session --license-id LIC-ACME-001 --org-id acme-corp --device-id dev-1 --duration 30 --interval 5
  python client_sim.py release --license-id LIC-ACME-001 --org-id acme-corp --device-id dev-1
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass
class HttpResult:
    status: int
    body: dict | list | str | None
    raw: str | None


def _post_json(url: str, payload: dict, timeout_s: float = 10.0) -> HttpResult:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url=url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            # Set a UA so it's easy to spot in logs/audit.
            "User-Agent": "lic-server-client-sim/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                body = json.loads(raw) if raw else None
            except json.JSONDecodeError:
                body = raw
            return HttpResult(status=getattr(resp, "status", 200), body=body, raw=raw)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace") if e.fp else None
        try:
            body = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            body = raw
        return HttpResult(status=e.code, body=body, raw=raw)
    except urllib.error.URLError as e:
        return HttpResult(status=0, body={"error": str(e)}, raw=None)


def _print_result(label: str, r: HttpResult) -> None:
    print(f"\n== {label} ==")
    print(f"HTTP {r.status}")
    if isinstance(r.body, (dict, list)):
        print(json.dumps(r.body, indent=2))
    elif r.body is None:
        print("(no body)")
    else:
        print(r.body)


def _common_payload(args: argparse.Namespace) -> dict:
    # These match the server's expected request fields.
    return {
        "license_id": getattr(args, "license_id", None),
        "org_id": getattr(args, "org_id", None),
        "device_id": getattr(args, "device_id", None),
        "hostname": args.hostname,
        "os": args.os,
        "app_version": args.app_version,
    }


def cmd_validate(args: argparse.Namespace) -> int:
    url = args.base_url.rstrip("/") + "/license/validate"
    payload = _common_payload(args)
    r = _post_json(url, payload, timeout_s=args.timeout)
    _print_result("license/validate", r)
    return 0 if 200 <= r.status < 300 else 1


def cmd_heartbeat(args: argparse.Namespace) -> int:
    url = args.base_url.rstrip("/") + "/license/heartbeat"
    payload = _common_payload(args)
    r = _post_json(url, payload, timeout_s=args.timeout)
    _print_result("license/heartbeat", r)
    return 0 if 200 <= r.status < 300 else 1


def cmd_release(args: argparse.Namespace) -> int:
    url = args.base_url.rstrip("/") + "/license/release"
    payload = _common_payload(args)
    r = _post_json(url, payload, timeout_s=args.timeout)
    _print_result("license/release", r)
    return 0 if 200 <= r.status < 300 else 1


def cmd_trial(args: argparse.Namespace) -> int:
    url = args.base_url.rstrip("/") + "/trial/validate"
    payload = {
        "device_id": args.device_id,
        "org_id": args.org_id,
        "hostname": args.hostname,
        "os": args.os,
        "app_version": args.app_version,
    }
    r = _post_json(url, payload, timeout_s=args.timeout)
    _print_result("trial/validate", r)
    return 0 if 200 <= r.status < 300 else 1


def cmd_session(args: argparse.Namespace) -> int:
    # validate once
    if cmd_validate(args) != 0:
        return 1

    # heartbeat loop
    start = time.time()
    while True:
        elapsed = time.time() - start
        if elapsed >= args.duration:
            break
        time.sleep(args.interval)
        if cmd_heartbeat(args) != 0:
            return 1

    if args.release:
        return cmd_release(args)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Licensing server client simulator")
    p.add_argument("--base-url", default="http://127.0.0.1:3000", help="Server base URL")
    p.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout (seconds)")
    p.add_argument("--hostname", default=socket.gethostname(), help="Client hostname")
    p.add_argument("--os", default=sys.platform, help="Client OS string")
    p.add_argument("--app-version", default="dev", help="Client app version")

    sub = p.add_subparsers(dest="cmd", required=True)

    pv = sub.add_parser("validate", help="POST /license/validate")
    pv.add_argument("--license-id", required=True)
    pv.add_argument("--org-id", required=True)
    pv.add_argument("--device-id", required=True)
    pv.set_defaults(func=cmd_validate)

    ph = sub.add_parser("heartbeat", help="POST /license/heartbeat")
    ph.add_argument("--license-id", required=True)
    ph.add_argument("--org-id", required=True)
    ph.add_argument("--device-id", required=True)
    ph.set_defaults(func=cmd_heartbeat)

    pr = sub.add_parser("release", help="POST /license/release")
    pr.add_argument("--license-id", required=True)
    pr.add_argument("--org-id", required=True)
    pr.add_argument("--device-id", required=True)
    pr.set_defaults(func=cmd_release)

    pt = sub.add_parser("trial", help="POST /trial/validate")
    pt.add_argument("--device-id", required=True)
    pt.add_argument("--org-id")
    pt.set_defaults(func=cmd_trial)

    ps = sub.add_parser("session", help="validate then heartbeat loop (like a running app)")
    ps.add_argument("--license-id", required=True)
    ps.add_argument("--org-id", required=True)
    ps.add_argument("--device-id", required=True)
    ps.add_argument("--duration", type=float, default=30.0, help="Total session time (seconds)")
    ps.add_argument("--interval", type=float, default=5.0, help="Heartbeat interval (seconds)")
    ps.add_argument("--release", action="store_true", help="Call release at the end")
    ps.set_defaults(func=cmd_session)

    return p


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

