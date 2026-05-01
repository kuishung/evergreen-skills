#!/usr/bin/env python3
"""
Twilio WhatsApp sender — stdlib only, no pip install required.

Reads credentials from a local JSON file (path passed via --credentials),
posts to the Twilio Messages API with HTTP Basic auth, and emits one JSON
line per send to stdout. Designed to be called once per recipient by the
whatsapp-send skill.

See SKILL.md §3 for usage.
"""

import argparse
import base64
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

TWILIO_API_BASE = "https://api.twilio.com/2010-04-01"
MAX_BODY_CHARS = 1600


def load_credentials(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"credentials file not found: {path}")
    try:
        creds = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"credentials file is not valid JSON: {e}")
    for key in ("account_sid", "auth_token", "from_number"):
        if not creds.get(key):
            raise ValueError(f"credentials file missing required key: {key}")
    if not creds["from_number"].startswith("whatsapp:"):
        raise ValueError(
            f"from_number must start with 'whatsapp:' (got {creds['from_number']!r})"
        )
    return creds


def normalize_to(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("whatsapp:"):
        return raw
    if not raw.startswith("+"):
        raise ValueError(f"--to must be E.164 format starting with '+' (got {raw!r})")
    return f"whatsapp:{raw}"


def truncate(body: str) -> str:
    if len(body) <= MAX_BODY_CHARS:
        return body
    return body[: MAX_BODY_CHARS - 1] + "…"


def send(creds: dict, to_number: str, body: str, from_override: str | None) -> dict:
    url = f"{TWILIO_API_BASE}/Accounts/{creds['account_sid']}/Messages.json"
    from_number = from_override or creds["from_number"]
    if from_override and not from_override.startswith("whatsapp:"):
        from_number = f"whatsapp:{from_override}"

    form = urllib.parse.urlencode(
        {"From": from_number, "To": to_number, "Body": body}
    ).encode("utf-8")

    auth = base64.b64encode(
        f"{creds['account_sid']}:{creds['auth_token']}".encode("utf-8")
    ).decode("ascii")

    req = urllib.request.Request(
        url,
        data=form,
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Twilio HTTP {e.code}: {body_text}"
        )
    except urllib.error.URLError as e:
        raise RuntimeError(f"Twilio network error: {e.reason}")

    return {
        "to": to_number,
        "sid": payload.get("sid"),
        "status": payload.get("status"),
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Send a WhatsApp message via Twilio.")
    p.add_argument("--credentials", required=True, type=Path)
    p.add_argument("--to", required=True, help="E.164 recipient, e.g. +60123456789")
    p.add_argument("--body", required=True)
    p.add_argument("--from", dest="from_override", default=None)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    try:
        creds = load_credentials(args.credentials)
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    try:
        to_number = normalize_to(args.to)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    body = truncate(args.body)

    if args.dry_run:
        preview = {
            "dry_run": True,
            "from": args.from_override or creds["from_number"],
            "to": to_number,
            "body_chars": len(body),
            "body_preview": body[:200],
        }
        print(json.dumps(preview, ensure_ascii=False))
        return 0

    try:
        result = send(creds, to_number, body, args.from_override)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 3

    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
