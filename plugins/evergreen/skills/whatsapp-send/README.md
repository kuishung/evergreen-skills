# whatsapp-send — setup checklist

End-to-end checklist of everything that must be configured **once** before the daily sale-audit can WhatsApp findings to your team. Work top-to-bottom; each section depends on the ones above it.

`SKILL.md` is the runtime contract. This file is the operational setup guide.

> **What changed in v0.2:** Recipients moved from a per-machine markdown memory to a single JSON file kept on Google Drive. Edit on any machine, Drive auto-syncs to others within seconds — no `git pull`, no manual copy. Twilio credentials remain per-machine and local-only.

---

## 1. Twilio account (console.twilio.com)

| # | Step | Where | Notes |
|---|------|-------|-------|
| 1.1 | Create a Twilio account | console.twilio.com | Free trial gives ~USD 15 credit, enough for hundreds of messages. |
| 1.2 | Activate the **WhatsApp Sandbox** | Console → Messaging → Try it out → Send a WhatsApp message | The sandbox is enough for testing. Going to production needs a Meta-approved Business sender; allow days–weeks. |
| 1.3 | Note the sandbox **From-number** | Same screen | Format: `whatsapp:+14155238886` (this exact number is shared by all Twilio sandbox accounts). |
| 1.4 | Note the sandbox **join keyword** | Same screen | Looks like `join two-words`. **Every recipient must send this keyword** from their own phone to the sandbox number once before they can receive any WhatsApp messages from your account. |
| 1.5 | Copy your **Account SID** | Console → Account → API keys & tokens | Starts with `AC…`. Public-ish; goes into the credentials file. |
| 1.6 | Copy your **Auth Token** | Same screen | Treat as a password. Never commit, never paste in chat. Goes into the credentials file. |

> ⚠ **Sandbox-mode caveat.** Without step 1.4, sends will fail silently or return Twilio Error 63007. The join keyword is the recipient's opt-in. Production WhatsApp Business uses approved templates instead — that opt-in model is different.

## 2. Credentials file (local-only, **per sending machine**)

This file stays per-machine — auth tokens should not roam through cloud storage that may be cached on other devices. Each machine that sends notifications needs its own copy.

Create this **outside** the git-tracked repo. Default location:

```
%USERPROFILE%\.evergreen\twilio\credentials.json
```

Copy [`credentials.example.json`](credentials.example.json) into that path and fill in the three values from §1:

```json
{
  "account_sid":  "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "auth_token":   "your_auth_token_here",
  "from_number":  "whatsapp:+14155238886"
}
```

**Verify the path is not inside the repo** — `git check-ignore <path>` should return non-zero (file is genuinely outside the worktree, not just gitignored). If you put the file inside the repo and commit it, **rotate the auth token in Twilio console immediately**.

If your `TwilioCredsPath` in [`run-sale-audit.ps1`](../../../../tools/win11-scheduled-audit/run-sale-audit.ps1) points elsewhere, use that path instead. Leave `TwilioCredsPath = ''` to disable WhatsApp for the scheduled run while keeping the audit running.

## 3. Recipients JSON (Drive-synced, **single source of truth**)

Unlike credentials, the recipients list is **shared across machines**. Save it on Google Drive and Drive for Desktop syncs it to every machine you use. Edit anywhere, the change is live everywhere within seconds.

### 3.1 Pick a Drive location

Any path inside `My Drive` works. Recommended: `<drive-root>\EVGData\config\recipients.json`. Different machines may mount Drive at different drive letters (e.g., `G:\My Drive\…` on Win 11, `H:\My Drive\…` on dev) — that's fine, the **content** is identical, only the local OS path differs.

```powershell
# Example on Win 11:
New-Item -ItemType Directory -Force -Path "G:\My Drive\EVGData\config" | Out-Null
```

### 3.2 Create the file

Copy [`recipients.example.json`](recipients.example.json) to your chosen Drive path, then edit. Real example:

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
      "notes": "Owner — all audits, both languages"
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

Field rules:

| Field | Type | Format / values |
|---|---|---|
| `name` | string | Free text. Logs only, never in the message body. |
| `whatsapp` | string | `+<countrycode><number>`, no spaces, no dashes. |
| `stations` | array | `["TK"]`, `["TK","BS"]`, or `["*"]`. |
| `languages` | array | `["EN"]`, `["EN","CH"]`, or `["*"]`. |
| `reports` | array | `["sale-audit"]` or `["*"]`. |
| `active` | boolean | `true` (default if omitted) or `false` to mute. |
| `notes` | string | Optional, ignored by the skill. |

A row matches when **every** filter dimension admits the call (stations, languages, reports) and `active != false`. The CLI deduplicates by phone — duplicate phone-number rows send only once.

### 3.3 Save the path on each machine

The skill needs to know where the JSON file lives on this machine. Save the absolute local path as a `reference` memory:

In a Claude Code chat:
```
Save 'WhatsApp recipients path' as a reference memory with value: G:\My Drive\EVGData\config\recipients.json
```

(Adjust the path to whatever Drive letter/path your machine uses. Each machine has its own copy of this memory; the **JSON content** is shared.)

You'll also paste the same path into [`run-sale-audit.ps1`](../../../../tools/win11-scheduled-audit/run-sale-audit.ps1)'s `$Config.RecipientsPath` (see §5).

### 3.4 Each new phone must opt in to the sandbox

For **every number** in `recipients.json`, the holder of that phone has to:

1. Open WhatsApp on their phone.
2. Send the `join <two-words>` keyword (from §1.4) to **+1 415 523 8886**.
3. Wait for "✅ You are all set!" reply.

Send this instruction to each recipient via your existing WhatsApp group. Without this step, they won't receive anything — Twilio drops the message with Error 63007.

> Note: sandbox opt-in expires after 72 hours of inactivity. If a recipient stops getting messages, they may need to re-send the join keyword. Once you migrate to a production WhatsApp Business sender (after Meta approval), this constraint goes away.

## 4. Drive folder share URL (optional but recommended)

Today the WhatsApp message is text-only. To make it actionable for recipients, point them at the audit-output folder in Google Drive:

1. In Google Drive, locate the **audit-output-root** folder (or whichever subfolder you want recipients to see).
2. Right-click → **Share** → set the right access: either "Anyone with the link → Viewer" (broadest) or share to specific Google accounts (tighter; recommended for staff).
3. Copy the share URL.
4. Paste it into [`run-sale-audit.ps1`](../../../../tools/win11-scheduled-audit/run-sale-audit.ps1)'s `$Config.AuditDriveFolderUrl`, **or** save a `reference` memory titled `Audit Drive folder URL` with the URL as content.

If you skip this step the WhatsApp message includes only the local filesystem path; recipients must already have Drive for Desktop syncing the same folder, or they need to ask you for the file.

## 5. Test the sender — single-send dry-run

From the worktree root, with credentials in place:

```powershell
# Validates creds + phone format. Does NOT call Twilio.
python plugins\evergreen\skills\whatsapp-send\send.py `
    --credentials "$env:USERPROFILE\.evergreen\twilio\credentials.json" `
    --to "+60123456789" `
    --body "test" `
    --dry-run
```

Expected: one JSON line with `"dry_run": true` and exit 0.

## 6. Test the sender — bulk dry-run with the real recipients file

```powershell
python plugins\evergreen\skills\whatsapp-send\send.py `
    --credentials "$env:USERPROFILE\.evergreen\twilio\credentials.json" `
    --recipients "G:\My Drive\EVGData\config\recipients.json" `
    --station TK `
    --language "EN,CH" `
    --report sale-audit `
    --body "TK audit smoke test" `
    --dry-run
```

Expected: one JSON line per matched recipient (with `"name"` field), exit 0. If you see `WARN: no active recipients matched` — your filters don't intersect the JSON; check the file.

## 7. Real send — opt yourself in first

**First, opt your phone in to the sandbox** (one-time, do this once per phone that should receive messages):

1. On your phone, open WhatsApp and message **+1 415 523 8886** with the `join <two-words>` keyword from §1.4.
2. WhatsApp replies "Twilio Sandbox: ✅ You are all set!".

Then run a real send (drop `--dry-run`):

```powershell
python plugins\evergreen\skills\whatsapp-send\send.py `
    --credentials "$env:USERPROFILE\.evergreen\twilio\credentials.json" `
    --recipients "G:\My Drive\EVGData\config\recipients.json" `
    --station TK `
    --language "EN,CH" `
    --report sale-audit `
    --body "Smoke test from whatsapp-send"
```

Within 1–2 seconds the message arrives in WhatsApp on every recipient that matched the filter. Cost: ~USD 0.005 per recipient.

If a single send fails (e.g., a recipient hasn't joined the sandbox), the script continues with the others and prints the failure to stderr. Exit code is `3` if at least one failed, `0` if all succeeded.

## 8. Test the chained flow (one full audit)

1. From the Win 11 server, run [`run-sale-audit.ps1`](../../../../tools/win11-scheduled-audit/run-sale-audit.ps1) manually:
   ```powershell
   powershell -File tools\win11-scheduled-audit\run-sale-audit.ps1
   ```
2. Wait for the audit to complete. Both PDFs should land under `<audit-output-root>/<YYYY>/<YYYY-MM>/<YYYY-MM-DD>/`.
3. The chat output (and the log file under `<audit-output-root>/_logs/`) should end with a line like `WhatsApp: TK 2/2 delivered, BS 1/1, BL 2/2`.
4. The recipients matched by each station's filter should each receive one WhatsApp.

If WhatsApp fails but PDFs are written — that's by design. The audit is still considered successful; investigate the WhatsApp issue separately.

## 9. Production readiness checklist

Tick all before relying on this in production:

- [ ] §1 — Twilio account active, sandbox enabled, recipients have joined the sandbox.
- [ ] §2 — Credentials file at the configured path on each sending machine; `git check-ignore` confirms each is outside the repo.
- [ ] §3 — Recipients JSON on Drive; every machine has the path saved as memory + in `run-sale-audit.ps1`; example rows replaced with real data.
- [ ] §4 — Drive folder URL set, recipients confirmed they can open it.
- [ ] §5–§7 — Dry runs and one live send succeed from the same machine that the schedule runs on.
- [ ] §8 — One full audit run delivers WhatsApp end-to-end.
- [ ] Plan to migrate from sandbox to a production WhatsApp Business sender before scaling beyond a few internal staff.

## 10. Where to look when something breaks

| Symptom | First place to look |
|---|---|
| Audit ran, no WhatsApp | `<audit-output-root>/_logs/audit-YYYYMMDD_HHMMSS.log` — search for `WhatsApp` and `whatsapp-send`. |
| `Twilio credentials file not found` | The path in `TwilioCredsPath` (or memory) doesn't resolve on this machine. |
| `recipients file not found` | The path in `RecipientsPath` (or memory) doesn't resolve. Drive may not be mounted, or the Drive letter differs from what's saved. |
| `Twilio HTTP 401` | Auth token wrong or rotated. Re-copy from console. |
| `WARN: no active recipients matched` | The filter (station/language/report) doesn't intersect any JSON row. Check the JSON's stations/languages/reports values. |
| `63007 — not joined` | Recipient must re-send the sandbox `join …` keyword. Sandbox opt-in expires after 72h inactivity. |
| Some recipients got it, others didn't | Their row's `stations`/`languages`/`reports` filter excluded them, or they haven't joined the sandbox, or `active: false`. |
| Wrong language sent | Sale-audit always sends one WhatsApp per station; the message points at the folder containing both PDFs. The `languages` array only filters whether a recipient gets a message at all. |
| Edits to `recipients.json` not picked up | Drive for Desktop may be paused, or the file is open in another editor with an exclusive lock. Check Drive's status icon in the system tray; close all editors. |

For deeper Twilio debugging, the **Console → Monitor → Logs → Messaging** view shows every send attempt with full request/response detail.
