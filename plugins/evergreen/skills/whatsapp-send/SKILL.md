---
name: whatsapp-send
description: Use this skill whenever the user (Evergreen back-office) wants to send a WhatsApp message via Twilio — typically a daily-audit notification chained from `sale-audit` after PDFs are produced, but also any ad-hoc "WhatsApp X to Y", "ping the team about ...", "notify management of ..." request. The skill reads the recipient list from a JSON file synced via Google Drive (single source of truth across machines) and Twilio credentials from a local-only file (never committed). Today the channel is **WhatsApp text only** (Twilio Programmable Messaging) — see §6 for why PDF attachment is deferred.
version: 0.3.0
updated: 2026-05-04 02:00
---

# WhatsApp Send — Evergreen Notifications

Send a WhatsApp message via the Twilio API. Recipient routing lives in a JSON file kept on Google Drive (one file shared across all machines via Drive for Desktop). Twilio credentials live on disk outside the repo, per-machine. The skill is invoked **chained** from `sale-audit` at the end of a successful audit run, and can also be called interactively for ad-hoc messages.

---

## 1. Why this skill exists

`sale-audit` runs unattended on a schedule (Win 11 Task Scheduler) and produces audit PDFs that the back-office needs to act on **the same morning**. Email is too slow / ignored; WhatsApp is what the team actually reads. This skill closes that loop without requiring anyone to manually forward files.

It is intentionally **text-only** today. PDF attachments via Twilio require a publicly fetchable HTTPS URL (Twilio's servers download the file from the URL — there is no upload endpoint), which would expose audit data to the public internet for the duration of the fetch. The user accepted this tradeoff and chose the simpler design: send a text summary that points at the file's location (and optionally at a pre-shared Google Drive folder URL the recipients already have access to). See §6 for the upgrade path if attachments become non-negotiable.

## 2. Configuration — three reference values

On first run, ensure all three are present. Save each as a `reference` memory the first time it is supplied. Verify on every reuse and ask once if anything fails.

### 2.1 Twilio credentials path (local-only, per-machine)

Saved memory: `Twilio credentials path` — absolute path to a JSON file on the local disk, **outside** any git-tracked folder. Default suggestion: `%USERPROFILE%\.evergreen\twilio\credentials.json`.

File contents (the user creates this manually after creating their Twilio account; the skill never writes it):

```json
{
  "account_sid": "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "auth_token": "your_auth_token_here",
  "from_number": "whatsapp:+14155238886"
}
```

- `account_sid` — Twilio Account SID from console.twilio.com.
- `auth_token` — Twilio Auth Token. **Treat as a password.** Never log, never echo to chat.
- `from_number` — the WhatsApp-enabled Twilio number, prefixed with `whatsapp:` and including `+countrycode`. For sandbox testing, this is the Twilio sandbox number; for production it is your approved WhatsApp Business sender.

This file is per-machine — each machine that sends notifications needs its own copy. It is **not** synced via Drive (auth tokens should not roam through cloud storage that may be cached on other devices).

If the file is missing, raise a finding: `Twilio credentials file not found at <path>. Create it per whatsapp-send/SKILL.md §2.1.` and abort the send (do **not** abort the parent audit — see §5).

### 2.2 Recipients JSON path — single source of truth via Drive

Saved memory: `WhatsApp recipients path` — absolute path to a `recipients.json` file kept on Google Drive (synced to all machines via Drive for Desktop). Each machine has the path saved locally; the **content** lives once on Drive and propagates within seconds whenever you save an edit.

Recommended location: `<drive-root>\EVGData\config\recipients.json` (e.g., `G:\My Drive\EVGData\config\recipients.json` on Win 11; the dev machine's Drive may mount at a different letter — that's fine, each machine's path memory points at its own mount).

Schema (see `recipients.example.json` for a fully-commented template):

```json
{
  "recipients": [
    {
      "name": "Owner KK",
      "whatsapp": "+60168881234",
      "stations": ["*"],
      "languages": ["*"],
      "reports": ["*"],
      "active": true,
      "notes": "Owner — all audits"
    },
    {
      "name": "TK Manager",
      "whatsapp": "+60198887654",
      "stations": ["TK"],
      "languages": ["EN"],
      "reports": ["sale-audit"],
      "active": true
    }
  ]
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | string | yes | Used in logs only, never in the message body. |
| `whatsapp` | string | yes | E.164 format with leading `+`, no spaces or dashes. Sandbox testing requires the recipient to have sent `join <two-words>` to the Twilio sandbox number first (see §7). |
| `stations` | array of strings | yes | `"TK"`, `"BS"`, `"BL"`, or `"*"` to match all. |
| `languages` | array of strings | yes | `"EN"`, `"CH"`, or `"*"`. The skill sends one WhatsApp per station regardless of language; this filters whether the recipient gets the message at all. A recipient with `languages: ["EN"]` matches when the requested languages overlap (i.e., when `"EN"` is among the audit's rendered languages). |
| `reports` | array of strings | yes | `"sale-audit"` today, or `"*"`. |
| `active` | boolean | no (default `true`) | Set `false` to mute without removing the row — useful for audit trail. |
| `notes` | string | no | Free text, ignored by the skill. |

A row matches a send when **every** filter dimension admits the call (and `active != false`). The CLI deduplicates by phone number — two rows with the same `whatsapp` send only once.

To edit, open the JSON in a text editor on any machine, save. Drive for Desktop syncs to other machines within seconds. No commit, no deploy.

### 2.3 Audit folder share URL — `reference` memory (optional)

Saved memory: `Audit Drive folder URL` — a Google Drive share link to the **audit-output-root** folder (or whichever subfolder recipients should land in). When set, the WhatsApp message includes this URL so recipients can click through to the PDFs. When unset, the message gives only the local filesystem path and recipients are expected to know where to find the file.

The user shares the Drive folder once (with the right access level — "anyone with link can view", or specific accounts) and pastes the URL into memory. The skill never edits Drive sharing.

## 3. CLI — `send.py`

The skill bundles a small Python script (`send.py`) that wraps Twilio's REST API using the Python standard library only — **no `pip install` needed**, so it runs in any sandbox including Cowork's scheduled-task runner.

The script has **two modes**.

### 3.1 Single-send mode — `--to`

For one-off sends; identical to v0.1.

```
python <skill_dir>/send.py \
    --credentials <path-to-credentials.json> \
    --to "+60123456789" \
    --body "Audit ready: TK 2026-05-01 — see Drive folder."
```

Outputs one JSON line: `{"to":"whatsapp:+60…","sid":"SM…","status":"queued"}`.

### 3.2 Bulk / filter mode — `--recipients`

For chained calls from `sale-audit`. The script reads the recipients JSON, filters by station/language/report/active, dedupes by phone, sends to each match. **One CLI invocation handles the whole team for one station.**

```
python <skill_dir>/send.py \
    --credentials <path-to-credentials.json> \
    --recipients <path-to-recipients.json> \
    --station TK \
    --language "EN,CH" \
    --report sale-audit \
    --body "🌅 Daily Audit — TK 2026-05-01\n\n..."
```

Per-recipient output (stdout, one JSON line each):
```
{"to":"whatsapp:+60168881234","sid":"SM…","status":"queued","name":"Owner KK"}
{"to":"whatsapp:+60198887654","sid":"SM…","status":"queued","name":"TK Manager"}
```

Per-recipient errors go to stderr and **do not abort the loop** — the script continues so a single bad number doesn't suppress the rest of the team.

### 3.3 Common flags

| Flag | Required | Meaning |
|---|---|---|
| `--credentials` | yes | Path to credentials JSON (§2.1). |
| `--body` | yes | Message text (UTF-8, supports CJK). 1600-char limit; truncated with ellipsis. |
| `--to` | one of | Single recipient (single-send mode). Mutually exclusive with `--recipients`. |
| `--recipients` | one of | Path to recipients JSON (bulk mode). Mutually exclusive with `--to`. |
| `--station` | yes (bulk) | Station code, e.g. `TK`. **Comma-separated list also accepted** for multi-station union filter, e.g. `TK,BS,BL`. A recipient row matches when its `stations` field contains `"*"` OR overlaps the requested set. (Added in v0.3.0 so sale-audit can send one combined message per audit run instead of one per station.) |
| `--language` | yes (bulk) | Comma-separated language codes, e.g. `"EN,CH"`. |
| `--report` | yes (bulk) | Report type, e.g. `sale-audit`. |
| `--dry-run` | no | Print the request(s) that would be sent and exit `0` without calling Twilio. |
| `--from` | no | Override the `from_number` from credentials. |

### 3.4 Exit codes

| Code | Meaning |
|---|---|
| `0` | Every send succeeded (or matched zero recipients — that's a `WARN`, not an error). |
| `1` | Credentials or recipients file missing / malformed. |
| `2` | Required argument missing or argparse mutex violated. |
| `3` | At least one send failed (Twilio API error, bad phone, network). Other sends in the same run still attempted. |

## 4. Workflow — interactive

When the user asks "WhatsApp the morning audit to the team" or similar:

1. Resolve credentials path (§2.1) and recipients path (§2.2) from memory. If either is missing or unreadable, stop with a clear error.
2. Compose the message body (e.g., 2–3 most material findings, the audit-output folder URL).
3. Invoke `send.py --recipients <path> --station <X> --language <EN,CH> --report sale-audit --body "..."`.
4. Stream the JSON results back to chat. If `--dry-run` was requested, run with `--dry-run` first and let the user confirm before re-running for real.
5. Reply in chat: `WhatsApp sent to N recipients (M succeeded, K failed). Failures: …`. Do **not** echo phone numbers in full — last-4 digits only (`…6789`) for privacy.

For ad-hoc sends to one specific number (not driven by the recipients list), use `--to` directly.

## 5. Workflow — chained from `sale-audit`

This is the production path. After `sale-audit` writes both language PDFs for a station, it invokes this skill **once per station** (not once per language — one WhatsApp per station with both PDFs referenced via the Drive folder URL). The chained invocation:

1. Builds a body like:
    ```
    🌅 Daily Audit — BL 2026-05-01

    Findings (top 3):
    • MBB clearance deferred — bank-ledger v0.3 (MBB ingestion not yet)
    • 1 cash slip dated T-1 (RM 1,200) — staff using older slip
    • Closing cash variance RM 35 vs FR

    📂 https://drive.google.com/drive/folders/…
    ```
2. Invokes:
    ```
    python <skill_dir>/send.py \
        --credentials <creds-path> \
        --recipients <recipients-path> \
        --station BL --language "EN,CH" --report sale-audit \
        --body "<body>"
    ```
3. Captures stdout + stderr to the audit log; does not parse the JSON in the chat reply (that's the script's job).

**Failure isolation.** If the WhatsApp send fails (creds missing, Twilio down, network error, exit code 1/2/3), the `sale-audit` run is **still considered successful** — the PDFs are on disk. Log the failure to the audit log file but do not raise it as an audit finding (it's an operational issue, not an audit finding). The chat reply (or scheduled-task log) should mention "WhatsApp send failed: <reason>" so the user knows to investigate.

## 6. PDF attachment — why deferred and how to add later

WhatsApp via Twilio supports media attachment via the `MediaUrl` parameter — a publicly accessible HTTPS URL Twilio fetches. There is no file-upload endpoint. To attach the PDF natively (so it appears in the WhatsApp chat with a preview) we would need:

- **Option A (clean)**: deploy a Google Apps Script Web App alongside the existing `bank-ledger` script that exposes a `?op=get_pdf&path=<…>&token=<…>` endpoint, returning the PDF bytes. The script sets a Drive ACL on the file just before serving and revokes it after the next call. The `MediaUrl` we pass to Twilio is `<webapp-url>?op=get_pdf&path=<encoded>&token=<token>`. Token-protected, time-bounded.
- **Option B (deferred — current design)**: send the WhatsApp message text-only with a Drive folder link. Recipients open the link with their existing Drive access. No public PDF URL ever exists.

The user chose B for v0.1+. If A becomes needed, extend `bank-ledger`'s Apps Script (don't add a second script) and add a `--media-url` flag to `send.py` that becomes a Twilio `MediaUrl` form field.

## 7. Twilio account checklist (one-time)

Before this skill works, the user needs to have done the following on the Twilio side. If a send fails with `Error 21408` or `Error 63007`, point at this list.

1. Twilio account created at console.twilio.com.
2. WhatsApp Sender enabled — for testing, use the **Twilio Sandbox for WhatsApp** (Console → Messaging → Try it out → Send a WhatsApp message). Each recipient must opt in to the sandbox once by sending the join code from their phone (`join <two-words>` to the sandbox number). For production, apply for a WhatsApp Business sender (takes Meta review days/weeks).
3. From-number copied into `credentials.json` as `whatsapp:+14155238886` (sandbox) or your approved business sender.
4. Recipients added to `recipients.json` on Drive in international format (`+60…`).
5. **Sandbox-mode caveat**: every recipient must have sent the `join …` keyword to the sandbox number from their phone before they can receive messages. Not the back-office's job; share the keyword with each recipient at onboarding. Once on production WhatsApp Business, opt-in is template-based instead.

## 8. Skill folder layout

```
plugins/evergreen/skills/whatsapp-send/
├── SKILL.md                    — this file
├── README.md                   — operational setup checklist
├── send.py                     — stdlib-only Twilio client (§3)
├── credentials.example.json    — template for §2.1 (real file lives outside the repo)
└── recipients.example.json     — template for §2.2 (real file lives on Drive)
```

Nothing in this folder is sensitive — it's safe to publish on GitHub. Real credentials live at the path saved as the `Twilio credentials path` memory (per-machine). Real recipients live at the path saved as the `WhatsApp recipients path` memory (Drive-synced, shared across machines).
