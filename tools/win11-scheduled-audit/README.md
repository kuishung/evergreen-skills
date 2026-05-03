# Win 11 scheduled sale audit

Schedule the daily sale audit on a Windows 11 server. **One-command install:** copy-paste the line below into PowerShell, answer the prompts, done.

## Quick install (recommended)

Open PowerShell on the server (the regular one — admin not required) and paste:

```powershell
iwr https://raw.githubusercontent.com/kuishung/evergreen-skills/main/tools/win11-scheduled-audit/install-schedule.ps1 -UseBasicParsing | iex
```

The installer asks for up to **7 things** (3 required: daily-report root, audit-output root, run time; 4 optional for the WhatsApp + Drive-mirror flow: Twilio creds path, recipients path, Drive-mirror root, Drive folder URL — leave any blank to disable). It writes a wrapper script + config to `%ProgramData%\Evergreen\sale-audit\`, and registers a Task Scheduler entry. Total time ~1–2 minutes.

It also offers to run a test immediately so you can confirm the audit works end-to-end before tomorrow morning's run fires for real.

> **Bank-clearance verification has moved to a separate skill** as of `sale-audit` v0.18.0. The installer no longer asks for the bank-ledger Web App URL / token / local CSV path, the wrapper no longer waits for the AmBank statement to be ingested before running, and the audit no longer reports per-slip clearance — see SKILL.md §6 rule 11. The 06:30 default is now arbitrary; pick whatever time makes sense for your morning routine.

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
   Verify with `/plugin` — should show `evergreen` at `0.23.0` or higher.
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

## What this gives you

- Runs every morning at the configured time (06:30 default) under your Windows account, auditing yesterday's business date.
- Can `pip install` whatever the renderer wants — no sandbox limits.
- Logs each run to `<AuditOutputRoot>\_logs\audit-<timestamp>.log` so failures are debuggable.

(Versions of this README before sale-audit v0.18.0 documented a "wait for the bank-ledger before auditing" polling loop. That logic is gone — bank-clearance verification has moved to a separate skill, so the wrapper just fires once at the configured time and runs immediately.)

## Cowork still has a role

Use Cowork in chat for **interactive** ad-hoc work. The Win 11 schedule is for the unattended nightly production run.
