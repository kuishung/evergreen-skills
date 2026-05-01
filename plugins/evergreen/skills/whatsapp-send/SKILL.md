---
name: whatsapp-send
description: Use this skill whenever the user (Evergreen back-office) wants to send a WhatsApp message via Twilio — typically a daily-audit notification chained from `sale-audit` after PDFs are produced, but also any ad-hoc "WhatsApp X to Y", "ping the team about ...", "notify management of ..." request. The skill reads recipient routing rules from a `reference` memory and Twilio credentials from a local-only file (never committed). Today the channel is **WhatsApp text only** (Twilio Programmable Messaging) — see §6 for why PDF attachment is deferred.
version: 0.1.0
updated: 2026-05-01 18:00
---

# WhatsApp Send — Evergreen Notifications

Send a WhatsApp message via the Twilio API. Recipient routing lives in user memory (editable). Twilio credentials live on disk outside the repo. The skill is invoked **chained** from `sale-audit` at the end of a successful audit run, and can also be called interactively for ad-hoc messages.

---

## 1. Why this skill exists

`sale-audit` runs unattended on a schedule (Win 11 Task Scheduler) and produces audit PDFs that the back-office needs to act on **the same morning**. Email is too slow / ignored; WhatsApp is what the team actually reads. This skill closes that loop without requiring anyone to manually forward files.

It is intentionally **text-only** today. PDF attachments via Twilio require a publicly fetchable HTTPS URL (Twilio's servers download the file from the URL — there is no upload endpoint), which would expose audit data to the public internet for the duration of the fetch. The user accepted this tradeoff and chose the simpler design: send a text summary that points at the file's location (and optionally at a pre-shared Google Drive folder URL the recipients already have access to). See §6 for the upgrade path if attachments become non-negotiable.

## 2. Configuration — three reference values

On first run, ensure all three are present. Save each as a `reference` memory the first time it is supplied. Verify on every reuse and ask once if anything fails.

### 2.1 Twilio credentials path (local-only file)

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

If the file is missing, raise a finding: `Twilio credentials file not found at <path>. Create it per whatsapp-send/SKILL.md §2.1.` and abort the send (do **not** abort the parent audit — see §5).

### 2.2 Recipient routing — `reference` memory

Saved memory: `WhatsApp recipients` (file: `reference_whatsapp_recipients.md` in the user's auto-memory dir). The file is a markdown table the user edits directly. The skill reads it at runtime.

Schema:

| Column | Required | Format | Example |
|---|---|---|---|
| Name | yes | free text | `Owner Tan` |
| WhatsApp | yes | full international format with `+`, no spaces | `+60123456789` |
| Stations | yes | comma-separated `TK`/`BS`/`BL`, or `*` for all | `TK,BS` |
| Languages | yes | comma-separated `EN`/`CH`, or `*` for all | `EN` |
| Reports | yes | comma-separated report types, or `*` for all | `sale-audit` |
| Notes | no | free text | `WhatsApp via personal phone` |

A row matches a send when **all four filter columns** (Stations, Languages, Reports, plus an implicit "the row is not commented out") admit the current call. `*` matches anything in that dimension. A recipient appears in **at most one** outbound message per call (dedupe by phone number).

To temporarily mute a recipient, prefix the row with `<!--` and suffix with `-->`, or move them to a "Disabled" subsection below the active table — the skill ignores anything outside the active table.

### 2.3 Audit folder share URL — `reference` memory (optional)

Saved memory: `Audit Drive folder URL` — a Google Drive share link to the **audit-output-root** folder (or whichever subfolder recipients should land in). When set, the WhatsApp message includes this URL so recipients can click through to the PDFs. When unset, the message gives only the local filesystem path and recipients are expected to know where to find the file (e.g., they have Drive for Desktop on the same shared folder).

The user shares the Drive folder once (with the right access level — "anyone with link can view", or specific accounts) and pastes the URL into memory. The skill never edits Drive sharing.

## 3. CLI — `send.py`

The skill bundles a small Python script (`send.py`) that wraps Twilio's REST API using the Python standard library only — **no `pip install` needed**, so it runs in any sandbox including Cowork's scheduled-task runner.

```
python <skill_dir>/send.py \
    --credentials <path-to-credentials.json> \
    --to "+60123456789" \
    --body "Audit ready: TK 2026-05-01 — see Drive folder."
```

Flags:

| Flag | Required | Meaning |
|---|---|---|
| `--credentials` | yes | Path to the credentials JSON (§2.1). |
| `--to` | yes | Recipient phone in international format (`+60…`). The script prepends `whatsapp:` automatically. |
| `--body` | yes | Message text (UTF-8, supports CJK). Twilio enforces a 1600-char limit; the script truncates with an ellipsis if exceeded. |
| `--dry-run` | no | Print the request that would be sent and exit `0` without calling Twilio. |
| `--from` | no | Override the `from_number` from credentials (rarely needed). |

Exit codes:
- `0` — message accepted by Twilio (`sid` returned).
- `1` — credentials file missing / malformed.
- `2` — required argument missing or malformed.
- `3` — Twilio API error (network, auth, recipient blocked, etc.). The HTTP body is logged.

The script writes a structured JSON line to stdout per send: `{"to":"+60…","sid":"SM…","status":"queued"}`. It writes nothing else to stdout (errors to stderr).

## 4. Workflow — interactive

When the user asks "WhatsApp the morning audit to the team" or similar:

1. Resolve credentials path (§2.1). If missing or unreadable, stop with a clear error.
2. Read the recipients memory (§2.2). Filter rows where `Stations`, `Languages`, and `Reports` admit the call. Dedupe by phone.
3. Build the message body:
   - Line 1: `🌅 Daily audit — <station code> <YYYY-MM-DD>` (or whatever report type).
   - Lines 2–6: top-level summary (e.g., 2–3 most material findings, 1 line each — the caller passes this in, since the audit-data already has it).
   - Last line: `📂 <Drive folder URL>` if set; otherwise `📂 <local path>`.
4. For each recipient, invoke `send.py` once. Stream the JSON results. If `--dry-run` was requested, print the resolved message + recipient list and stop.
5. Reply in chat: `WhatsApp sent to N recipients (M succeeded, K failed). Failures: …`. Do **not** echo phone numbers in full — last-4 digits only (`…6789`) for privacy.

## 5. Workflow — chained from `sale-audit`

This is the production path. After `sale-audit` writes both language PDFs for a station, it invokes this skill **once per station** (not once per language — one WhatsApp per station with both PDFs referenced). The chained invocation passes:

- Station code (`TK` / `BS` / `BL`).
- Business date (`YYYY-MM-DD`).
- Absolute paths of the two PDFs (`_EN`, `_CH`).
- A short findings summary (3–5 bullets, taken from §6 of the audit data — same content as the chat reply).

Filter recipients by `Stations` ∋ station, `Languages` admitting any of the rendered languages, `Reports` ∋ `sale-audit`. Build a body like:

```
🌅 Daily Audit — BL 2026-05-01

Findings (top 3):
• MBB clearance deferred — bank-ledger v0.3 (MBB ingestion not yet)
• 1 cash slip dated T-1 (RM 1,200) — staff using older slip
• Closing cash variance RM 35 vs FR

📂 https://drive.google.com/drive/folders/…
```

If a recipient row's `Languages` is `EN` only, still link to the same folder — the user opens whichever PDF they want from there.

**Failure isolation.** If the WhatsApp send fails (creds missing, Twilio down, network error), the `sale-audit` run is **still considered successful** — the PDFs are on disk. Log the failure to the audit log file but do not raise it as an audit finding (it's an operational issue, not an audit finding). The chat reply (or scheduled-task log) should mention "WhatsApp send failed: <reason>" so the user knows to investigate.

## 6. PDF attachment — why deferred and how to add later

WhatsApp via Twilio supports media attachment via the `MediaUrl` parameter — a publicly accessible HTTPS URL Twilio fetches. There is no file-upload endpoint. To attach the PDF natively (so it appears in the WhatsApp chat with a preview) we would need:

- **Option A (clean)**: deploy a Google Apps Script Web App alongside the existing `bank-ledger` script that exposes a `?op=get_pdf&path=<…>&token=<…>` endpoint, returning the PDF bytes. The script sets a Drive ACL on the file just before serving and revokes it after the next call. The `MediaUrl` we pass to Twilio is `<webapp-url>?op=get_pdf&path=<encoded>&token=<token>`. Token-protected, time-bounded.
- **Option B (deferred — current design)**: send the WhatsApp message text-only with a Drive folder link. Recipients open the link with their existing Drive access. No public PDF URL ever exists.

The user chose B for v0.1. If A becomes needed, extend `bank-ledger`'s Apps Script (don't add a second script) and add a `--media-url` flag to `send.py` that becomes a Twilio `MediaUrl` form field.

## 7. Twilio account checklist (one-time)

Before this skill works, the user needs to have done the following on the Twilio side. If a send fails with `Error 21408` or `Error 63007`, point at this list.

1. Twilio account created at console.twilio.com.
2. WhatsApp Sender enabled — for testing, use the **Twilio Sandbox for WhatsApp** (Console → Messaging → Try it out → Send a WhatsApp message). Each recipient must opt in to the sandbox once by sending the join code from their phone (`join <two-words>` to the sandbox number). For production, apply for a WhatsApp Business sender (takes Meta review days/weeks).
3. From-number copied into `credentials.json` as `whatsapp:+14155238886` (sandbox) or your approved business sender.
4. Recipient numbers added to `reference_whatsapp_recipients.md` in international format (`+60…`).
5. **Sandbox-mode caveat**: every recipient must have sent the `join …` keyword to the sandbox number from their phone before they can receive messages. Not the back-office's job; share the keyword with each recipient at onboarding. Once on production WhatsApp Business, opt-in is template-based instead.

## 8. Skill folder layout

```
plugins/evergreen/skills/whatsapp-send/
├── SKILL.md           — this file
├── send.py            — stdlib-only Twilio client (§3)
└── credentials.example.json   — template for §2.1 (the real file lives outside the repo)
```

Nothing in this folder is sensitive — it's safe to publish on GitHub. Real credentials live at the path saved in memory (§2.1), which is per-user and never committed.
