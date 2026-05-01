# whatsapp-send — setup checklist

End-to-end checklist of everything that must be configured **once** before the daily sale-audit can WhatsApp findings to your team. Work top-to-bottom; each section depends on the ones above it.

`SKILL.md` is the runtime contract. This file is the operational setup guide.

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

## 2. Credentials file (local-only, per sending machine)

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

## 3. Recipient routing (in user memory)

Edit [`reference_whatsapp_recipients.md`](#) in your auto-memory directory:

```
%USERPROFILE%\.claude\projects\<project-name>\memory\reference_whatsapp_recipients.md
```

Replace the `_example_` row(s) with real recipients. Schema:

| Column | Required | Format | Example |
|---|---|---|---|
| Name | yes | free text | `Owner Tan` |
| WhatsApp | yes | E.164 with `+`, no spaces | `+60123456789` |
| Stations | yes | `TK`/`BS`/`BL` (comma-sep) or `*` | `TK,BS` |
| Languages | yes | `EN`/`CH` (comma-sep) or `*` | `EN` |
| Reports | yes | `sale-audit` (comma-sep) or `*` | `sale-audit` |
| Notes | no | free text | `Owner — all reports` |

Move a row out of the **Active recipients** table and into **Disabled recipients** to mute. The skill ignores everything outside the active table.

> Reminder for sandbox mode: every phone in this table must have completed step 1.4 from their own handset.

## 4. Drive folder share URL (optional but recommended)

Today the WhatsApp message is text-only. To make it actionable for recipients, point them at the audit-output folder in Google Drive:

1. In Google Drive, locate the **audit-output-root** folder (or whichever subfolder you want recipients to see).
2. Right-click → **Share** → set the right access: either "Anyone with the link → Viewer" (broadest) or share to specific Google accounts (tighter; recommended for staff).
3. Copy the share URL.
4. Paste it into [`run-sale-audit.ps1`](../../../../tools/win11-scheduled-audit/run-sale-audit.ps1)'s `$Config.AuditDriveFolderUrl`, **or** save a `reference` memory titled `Audit Drive folder URL` with the URL as content.

If you skip this step the WhatsApp message includes only the local filesystem path; recipients must already have Drive for Desktop syncing the same folder, or they need to ask you for the file.

## 5. Test the sender (no audit needed)

From the worktree root, with credentials in place:

```powershell
# Dry run — does NOT call Twilio. Validates creds shape + phone format.
python plugins\evergreen\skills\whatsapp-send\send.py `
    --credentials "$env:USERPROFILE\.evergreen\twilio\credentials.json" `
    --to "+60123456789" `
    --body "test" `
    --dry-run

# Real send — costs ~USD 0.005 and lands in WhatsApp.
python plugins\evergreen\skills\whatsapp-send\send.py `
    --credentials "$env:USERPROFILE\.evergreen\twilio\credentials.json" `
    --to "+60123456789" `
    --body "Smoke test from whatsapp-send"
```

Expected stdout for the real send: a single JSON line like
`{"to":"whatsapp:+60123456789","sid":"SMxxxxxxxx…","status":"queued"}`.

If you get `Twilio HTTP 401` → wrong Auth Token. `HTTP 21211` → bad recipient format. `63007` → recipient hasn't joined the sandbox. `21408` → from-number not WhatsApp-enabled.

## 6. Test the chained flow (one full audit)

1. From the Win 11 server, run [`run-sale-audit.ps1`](../../../../tools/win11-scheduled-audit/run-sale-audit.ps1) manually:
   ```powershell
   powershell -File tools\win11-scheduled-audit\run-sale-audit.ps1
   ```
2. Wait for the audit to complete. Both PDFs should land under `<audit-output-root>/<YYYY>/<YYYY-MM>/<YYYY-MM-DD>/`.
3. The chat output (and the log file under `<audit-output-root>/_logs/`) should end with a line like `WhatsApp: 3/3 delivered`.
4. The recipients in §3 should each receive one WhatsApp per station.

If WhatsApp fails but PDFs are written — that's by design. The audit is still considered successful; investigate the WhatsApp issue separately.

## 7. Production readiness checklist

Tick all before relying on this in production:

- [ ] §1 — Twilio account active, sandbox enabled, recipients have joined the sandbox.
- [ ] §2 — Credentials file at the configured path; `git check-ignore` confirms it's outside the repo.
- [ ] §3 — Recipients table edited; example rows removed; phone numbers verified by sending one real message to each.
- [ ] §4 — Drive folder URL set, recipients confirmed they can open it.
- [ ] §5 — Dry run + one live send both succeed from the same machine that the schedule runs on.
- [ ] §6 — One full audit run delivers WhatsApp end-to-end.
- [ ] Plan to migrate from sandbox to a production WhatsApp Business sender before scaling beyond a few internal staff.

## 8. Where to look when something breaks

| Symptom | First place to look |
|---|---|
| Audit ran, no WhatsApp | `<audit-output-root>/_logs/audit-YYYYMMDD_HHMMSS.log` — search for `WhatsApp` and `whatsapp-send`. |
| `Twilio credentials file not found` | The path in `TwilioCredsPath` (or memory) doesn't resolve. |
| `Twilio HTTP 401` | Auth token wrong or rotated. Re-copy from console. |
| `63007 — not joined` | Recipient must re-send the sandbox `join …` keyword. |
| Some recipients got it, others didn't | Their row's `Stations`/`Languages`/`Reports` filter excluded them, or they haven't joined the sandbox. |
| Wrong language sent | Sale-audit always sends one WhatsApp per station; the message points at the folder containing both PDFs. The `Languages` column only filters whether a recipient gets a message at all. |

For deeper Twilio debugging, the **Console → Monitor → Logs → Messaging** view shows every send attempt with full request/response detail.
