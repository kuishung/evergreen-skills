#!/usr/bin/env python3
"""
Twilio WhatsApp sender — stdlib only, no pip install required.

Two modes:
  • Single send (--to <phone>) — message one recipient, one call.
  • Bulk send  (--recipients <path> --station X --language EN[,CH] --report sale-audit)
    — read a recipients JSON file, filter by station/language/report/active,
    dedupe by phone, send to each match. Designed to be called once per
    audit-station by the whatsapp-send skill (chained from sale-audit).

In bulk mode, sends emit one JSON line per recipient on stdout. Per-recipient
errors go to stderr but do NOT abort the loop — the script continues so a
single bad number doesn't suppress the rest of the team. Exit code is 0
when every send succeeds, 3 when any send failed.

See SKILL.md §3 for full CLI surface.
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


# ─── credential / recipient loading ─────────────────────────────────────────


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


def load_recipients(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"recipients file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"recipients file is not valid JSON: {e}")
    if not isinstance(data, dict) or "recipients" not in data:
        raise ValueError(
            "recipients file must be a JSON object with a 'recipients' array; "
            "see recipients.example.json"
        )
    rows = data["recipients"]
    if not isinstance(rows, list):
        raise ValueError("'recipients' must be an array")
    return rows


# ─── filtering ──────────────────────────────────────────────────────────────


def _matches(field: list, requested: set[str]) -> bool:
    """A list field matches when it contains '*' or overlaps `requested`."""
    if not isinstance(field, list):
        return False
    if "*" in field:
        return True
    return bool(set(field) & requested)


def filter_recipients(
    rows: list[dict], stations: set[str], languages: set[str], report: str
) -> list[dict]:
    """Return active rows where stations, languages, and reports all admit.

    `stations` is a set so callers can pass either a single station
    ({"TK"}) or the union of all stations ({"TK","BS","BL"}) to send
    one message per audit run that covers all stations at once. A row's
    `stations` field matches when it contains "*" OR overlaps the
    requested set — same union semantics as `languages` and `reports`.
    """
    matched: list[dict] = []
    seen_phones: set[str] = set()
    for r in rows:
        if r.get("active") is False:
            continue
        if not _matches(r.get("stations", []), stations):
            continue
        if not _matches(r.get("languages", []), languages):
            continue
        if not _matches(r.get("reports", []), {report}):
            continue
        phone = (r.get("whatsapp") or "").strip()
        if not phone or phone in seen_phones:
            continue
        seen_phones.add(phone)
        matched.append(r)
    return matched


# ─── Twilio call ────────────────────────────────────────────────────────────


def normalize_to(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("whatsapp:"):
        return raw
    if not raw.startswith("+"):
        raise ValueError(f"phone must be E.164 starting with '+' (got {raw!r})")
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
        raise RuntimeError(f"Twilio HTTP {e.code}: {body_text}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Twilio network error: {e.reason}")

    return {
        "to": to_number,
        "sid": payload.get("sid"),
        "status": payload.get("status"),
    }


# ─── per-row send (used by both modes) ──────────────────────────────────────


def _send_one(
    creds: dict,
    raw_phone: str,
    body: str,
    from_override: str | None,
    name: str | None,
    dry_run: bool,
) -> tuple[bool, dict]:
    """Send one recipient. Returns (ok, json-record). Never raises."""
    try:
        to_number = normalize_to(raw_phone)
    except ValueError as e:
        return False, {"error": str(e), "to": raw_phone, "name": name}

    if dry_run:
        record = {
            "dry_run": True,
            "from": from_override or creds["from_number"],
            "to": to_number,
            "name": name,
            "body_chars": len(body),
            "body_preview": body[:200],
        }
        return True, record

    try:
        result = send(creds, to_number, body, from_override)
    except RuntimeError as e:
        return False, {"error": str(e), "to": to_number, "name": name}

    if name:
        result["name"] = name
    return True, result


# ─── CLI ────────────────────────────────────────────────────────────────────


def main() -> int:
    p = argparse.ArgumentParser(description="Send a WhatsApp message via Twilio.")
    p.add_argument("--credentials", required=True, type=Path)
    p.add_argument("--body", required=True)
    p.add_argument("--from", dest="from_override", default=None)
    p.add_argument("--dry-run", action="store_true")

    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--to", help="E.164 recipient, e.g. +60123456789 (single-send mode)")
    mode.add_argument(
        "--recipients",
        type=Path,
        help="Path to recipients JSON file (bulk-send / filter mode)",
    )

    p.add_argument(
        "--station",
        help="Station code(s), comma-separated for multi-station, e.g. 'TK' or 'TK,BS,BL' (required with --recipients)",
    )
    p.add_argument(
        "--language",
        help="Comma-separated language codes, e.g. EN,CH (required with --recipients)",
    )
    p.add_argument("--report", help="Report type, e.g. sale-audit (required with --recipients)")

    args = p.parse_args()

    try:
        creds = load_credentials(args.credentials)
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    body = truncate(args.body)

    # ─── Single-send mode ───
    if args.to:
        ok, record = _send_one(
            creds, args.to, body, args.from_override, name=None, dry_run=args.dry_run
        )
        if ok:
            print(json.dumps(record, ensure_ascii=False))
            return 0
        print(f"ERROR: {record.get('error')}", file=sys.stderr)
        return 3

    # ─── Bulk-send / filter mode ───
    missing = [
        flag
        for flag, val in (
            ("--station", args.station),
            ("--language", args.language),
            ("--report", args.report),
        )
        if not val
    ]
    if missing:
        print(
            f"ERROR: --recipients requires {', '.join(missing)}",
            file=sys.stderr,
        )
        return 2

    try:
        rows = load_recipients(args.recipients)
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    languages = {lang.strip() for lang in args.language.split(",") if lang.strip()}
    stations = {s.strip() for s in args.station.split(",") if s.strip()}
    matches = filter_recipients(rows, stations, languages, args.report)

    if not matches:
        # Not an error — just no one routed. Print a warning to stderr and exit 0.
        print(
            f"WARN: no active recipients matched stations={sorted(stations)!r} "
            f"language={sorted(languages)!r} report={args.report!r}",
            file=sys.stderr,
        )
        return 0

    failures = 0
    for r in matches:
        ok, record = _send_one(
            creds,
            r["whatsapp"],
            body,
            args.from_override,
            name=r.get("name"),
            dry_run=args.dry_run,
        )
        if ok:
            print(json.dumps(record, ensure_ascii=False))
        else:
            failures += 1
            print(json.dumps(record, ensure_ascii=False), file=sys.stderr)

    return 3 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
