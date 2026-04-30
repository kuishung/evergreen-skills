# Win 11 scheduled sale audit

Schedule the daily sale audit on a Windows 11 server. **One-command install:** copy-paste the line below into PowerShell, answer the prompts, done.

## Quick install (recommended)

Open PowerShell on the server (the regular one — admin not required) and paste:

```powershell
iwr https://raw.githubusercontent.com/kuishung/evergreen-skills/main/tools/win11-scheduled-audit/install-schedule.ps1 -UseBasicParsing | iex
```

The installer asks for **6 things** (folders, Web App URL + token, run time), writes a wrapper script + config to `%ProgramData%\Evergreen\sale-audit\`, and registers a Task Scheduler entry. Total time ~2 minutes.

It also offers to run a test immediately so you can confirm the audit works end-to-end before tomorrow morning's 06:30 fires for real.

The 06:30 default is deliberate: the bank-ledger Apps Script trigger fires at 06:00, ingests the overnight AmBank statement emails, and refreshes the local-sync CSV/XLSX exports. The 30-minute gap leaves Google Drive Desktop time to sync those files down before the audit reads them.

## Pre-flight (do these once before running the installer)

1. **Install Claude Code** if it isn't already on this server:
   ```powershell
   npm install -g @anthropic-ai/claude-code
   ```
   (Or get the desktop installer from <https://code.claude.com>.)
2. **Authenticate once interactively:**
   ```powershell
   claude
   ```
   Sign in. Credentials persist for every later run.
3. **Install the evergreen plugin** inside that interactive session:
   ```
   /plugin marketplace add kuishung/evergreen-skills
   /plugin install evergreen@evergreen
   ```
   Verify with `/plugin` — should show `evergreen` at `0.16.0` or higher.
4. Quit the interactive session (`Ctrl+C` or `/exit`).

Now run the **Quick install** line above.

## Re-running and changes

- **Change a path or token?** Re-run the installer. It overwrites the config and re-registers the task. Old values are gone.
- **Change the daily run time?** Re-run; new time is asked at the prompt.
- **Run on demand right now?**
  ```powershell
  schtasks /Run /TN "Evergreen Sale Audit Daily"
  ```
- **Remove the schedule entirely?**
  ```powershell
  schtasks /Delete /TN "Evergreen Sale Audit Daily" /F
  ```

## Files in this folder (for reference / power users)

| File | Purpose |
|---|---|
| **`install-schedule.ps1`** | One-shot installer (the recommended path). |
| `run-sale-audit.ps1` | Older standalone wrapper — kept for compatibility. The installer writes its own copy under `%ProgramData%\Evergreen\sale-audit\` from a config-driven template, so you don't normally use this one directly. |
| `Evergreen-Sale-Audit-Daily.xml` | Task Scheduler import for the manual / GUI path. The installer registers via `schtasks.exe` instead, which is faster and skips the XML editing. Keep around if you prefer Task Scheduler GUI. |

## Behaviour: "wait for the bank-ledger before auditing"

When 06:30 hits, the wrapper first **pings the bank-ledger Web App** to check whether yesterday's credits have been ingested. If yes — runs the audit immediately. If no — sleeps 30 min, retries up to 4 times, then gives up and runs the audit anyway (with `§6.11` deferred for that day).

This protects against the AmBank email arriving late. If the bank statement lands at, say, 07:15, the wrapper that fired at 06:30 catches it on its second retry at 07:00 and the audit runs cleanly.

Maximum delay from scheduled fire to audit start: `WaitMaxRetries × WaitMinutesBetweenRetries` = 4 × 30 min = 2 hours by default. Edit `%ProgramData%\Evergreen\sale-audit\config.json` to change those values, or set `WaitForBankLedger: false` to disable the wait entirely and run immediately every time.

## What this gives you

- Runs every morning at 06:30 (configurable) under your Windows account, auditing yesterday's business date.
- Reaches `script.google.com` directly — `§6.11` clearance verifies live every night, no deferred slips.
- Can `pip install` whatever the renderer wants — no sandbox limits.
- Reads `My Drive/...` for the bank-ledger CSV fallback if you've set that up.
- Logs each run to `<AuditOutputRoot>\_logs\audit-<timestamp>.log` so failures are debuggable.

## Cowork still has a role

Use Cowork in chat for **interactive** ad-hoc work. The Win 11 schedule is for the unattended nightly production run.
