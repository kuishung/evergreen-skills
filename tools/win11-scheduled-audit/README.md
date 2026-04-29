# Win 11 scheduled sale audit

Set up the daily 01:30 sale audit on a Windows 11 server. Replaces the Cowork-scheduled flow because Cowork's sandbox can't reach `script.google.com` and only mounts one user folder — both of those go away when we run on the actual Windows server.

## Files in this folder

| File | Purpose |
|---|---|
| `run-sale-audit.ps1` | PowerShell wrapper. Builds the prompt, invokes `claude -p`, captures output to a timestamped log under `<audit-output-root>/_logs/`. |
| `Evergreen-Sale-Audit-Daily.xml` | Task Scheduler import. Configures a daily 01:30 trigger that runs the wrapper. Edit the `<UserId>` and the `<Command>` path before importing. |

## One-time setup (~20 min)

### 1. Install Claude Code on the server

```powershell
npm install -g @anthropic-ai/claude-code
```

(Or use the desktop installer at <https://code.claude.com>; either way `claude` must resolve on PATH for whichever Windows account will run the scheduled task.)

### 2. Authenticate once interactively

Open PowerShell as the Windows account that will run the schedule:

```powershell
claude
```

Sign in. Credentials are saved under `%USERPROFILE%\.claude\` — every subsequent invocation (interactive or scheduled) reuses them.

### 3. Install the evergreen plugin

Inside the same `claude` session:

```
/plugin marketplace add kuishung/evergreen-skills
/plugin install evergreen@evergreen
```

Verify it picked the latest version (currently `0.16.0`):

```
/plugin
```

### 4. Drop the wrapper script onto disk

Pick a stable folder — recommend `C:\Tools\evergreen-sale-audit\`. Save these two files into it:

- `run-sale-audit.ps1`
- `Evergreen-Sale-Audit-Daily.xml`

### 5. Edit `run-sale-audit.ps1` CONFIG block

Open `run-sale-audit.ps1` in Notepad. Edit the values at the top:

| Setting | Example |
|---|---|
| `DailyReportRoot` | `C:\Users\KS\DATA\Evergreen\DailyReports` |
| `AuditOutputRoot` | `C:\Users\KS\DATA\Evergreen\AuditOutput` |
| `LocalCsvPath`    | `C:\Users\KS\My Drive\Evergreen\BankLedger\bank-ledger.csv` |
| `WebAppUrl`       | `https://script.google.com/macros/s/AKfycbz…/exec` |
| `WebAppToken`     | the long random string in `WEB_APP_TOKEN` Apps Script property |
| `Stations`        | leave as `@('TK', 'BS', 'BL')` unless rolling out only some |
| `AuditOffsetDays` | leave at `-1` so the 01:30 run audits *yesterday's* business date |

Save.

### 6. Test the wrapper manually

In a new PowerShell window:

```powershell
cd C:\Tools\evergreen-sale-audit
.\run-sale-audit.ps1
```

Watch the output. Expected behaviour:
- A banner with the audit date and station list.
- `claude` starts running, picks up the prompt, triggers `sale-audit`.
- It pings the Web App, reads the daily-report files, runs §6 checks, renders both PDFs (EN + CH) per station, lands them in `<AuditOutputRoot>\<YYYY>\<YYYY-MM>\<YYYY-MM-DD>\`.
- Final line: `Finished: <timestamp> (exit 0)`.
- A log file appears under `<AuditOutputRoot>\_logs\audit-<YYYYMMDD_HHMMSS>.log`.

If the manual run works, proceed. If it fails, check the log first.

### 7. Edit `Evergreen-Sale-Audit-Daily.xml` and import

Open the XML file in Notepad. Change two things:

1. `<UserId>EDIT-ME-WINDOWS-ACCOUNT-NAME</UserId>` → your actual Windows username (e.g., `KS` or `kswong`).
2. The `<Command>` argument path if you put the `.ps1` anywhere other than `C:\Tools\evergreen-sale-audit\run-sale-audit.ps1`.

Save.

Open Task Scheduler:

- **Win+R** → `taskschd.msc` → Enter
- Right-click **Task Scheduler Library** → **Import Task…**
- Browse to your edited XML → **OK**
- When prompted, enter the password for the Windows account so the task can run while logged out.

The task will fire at 01:30 nightly. To run it on demand: right-click the task → **Run**.

### 8. Verify the first scheduled run

Wait until the morning after the next 01:30 trigger. Open `<AuditOutputRoot>\<YYYY>\<YYYY-MM>\<yesterday>\` — six PDFs (3 stations × 2 languages) should be there. Check the audit log under `_logs/`.

If the run failed, the Task Scheduler **History** tab shows the exit code; the wrapper's log file shows what the skill actually did.

## What this gives you that Cowork didn't

| Capability | Cowork sandbox | Win 11 Task Scheduler |
|---|---|---|
| Reach `script.google.com` for §6.11 clearance | ❌ blocked | ✅ live verification every night |
| `pip install jinja2` (and `weasyprint` if you want native PDF) | ❌ blocked | ✅ unrestricted |
| See `My Drive/...` for the local-sync CSV (belt-and-braces) | ❌ not mounted | ✅ direct access |
| Persistent memory across runs | ❌ ephemeral | ✅ user-profile based |
| Run on a daily schedule | ✅ Cowork scheduler | ✅ Task Scheduler |

## Cowork still has a role

Use Cowork in chat for **interactive** work — ad-hoc audits, AP-invoice reviews, ledger queries. The Cowork sandbox already has access to your `DATA` folder for that, and §6.11 limitations don't bite when *you're at the keyboard* and can re-run from the Win 11 server / your laptop in a separate session.

The Win 11 schedule is for unattended production runs. Cowork is for interactive collaboration. Different jobs, different tools.
