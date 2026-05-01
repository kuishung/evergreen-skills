# ───────────────────────────────────────────────────────────────────
#  Evergreen Sale Audit — Windows 11 scheduled-task runner.
#
#  Designed to be invoked by Task Scheduler at 06:30 daily.
#  Triggers Claude Code in -p (non-interactive) mode against the
#  evergreen marketplace plugin's `sale-audit` skill, with all four
#  reference paths pre-stated so the skill never has to ask.
#
#  One-time setup before the first scheduled run:
#    1. `npm install -g @anthropic-ai/claude-code` (or use the
#       desktop installer; either way, `claude` must resolve on PATH).
#    2. Log in interactively once: open PowerShell, run `claude`,
#       authenticate. Credentials are persisted under
#       %USERPROFILE%\.claude\ for every subsequent run.
#    3. Install the plugin: in the interactive `claude` session,
#       /plugin marketplace add kuishung/evergreen-skills
#       /plugin install evergreen@evergreen
#    4. Edit the CONFIG block below with your real paths + token.
#    5. Test manually: `powershell -File run-sale-audit.ps1`
#    6. Schedule it (see README.md alongside this file).
# ───────────────────────────────────────────────────────────────────

$ErrorActionPreference = 'Stop'

# ═══════════════════════════ CONFIG ════════════════════════════════
# Edit these once for the server. The script substitutes them into
# the prompt sent to Claude Code so memory is populated even on a
# fresh box, and they override any stale values still in memory.

$Config = @{
    DailyReportRoot   = 'C:\Users\KS\DATA\Evergreen\DailyReports'
    AuditOutputRoot   = 'C:\Users\KS\DATA\Evergreen\AuditOutput'
    LocalCsvPath      = 'C:\Users\KS\My Drive\Evergreen\BankLedger\bank-ledger.csv'
    WebAppUrl         = 'https://script.google.com/macros/s/PASTE-YOUR-WEB-APP-URL-HERE/exec'
    WebAppToken       = 'PASTE-YOUR-WEB-APP-TOKEN-HERE'

    # whatsapp-send credentials file (local-only, NOT in the repo). Leave empty
    # to disable WhatsApp notifications — the audit still runs and writes PDFs.
    TwilioCredsPath   = "$env:USERPROFILE\.evergreen\twilio\credentials.json"

    # Optional: Google Drive share URL for the audit-output folder. When set,
    # the WhatsApp message includes this so recipients click through. Leave
    # empty to fall back to the local path.
    AuditDriveFolderUrl = ''

    Stations          = @('TK', 'BS', 'BL')
    AuditOffsetDays   = -1   # -1 = audit yesterday; 0 = today; -2 = day-before-yesterday
}

# Optional: pin to a specific Claude model for byte-stable output
# across upgrades. Empty string = use whatever the CLI defaults to.
$Config.Model = ''

# ═══════════════════════════ END CONFIG ════════════════════════════

# Compute the audit date in local timezone
$auditDate = (Get-Date).AddDays($Config.AuditOffsetDays).ToString('yyyy-MM-dd')

# Ensure the log folder exists before we write anything to it
$logDir = Join-Path $Config.AuditOutputRoot '_logs'
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
$logFile = Join-Path $logDir ("audit-{0}.log" -f (Get-Date -Format 'yyyyMMdd_HHmmss'))

# Sanity-check: claude on PATH?
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
    $msg = "FATAL: 'claude' not found on PATH. Install Claude Code or add it to PATH for this user."
    Add-Content -Path $logFile -Value $msg
    Write-Error $msg
    exit 2
}

# Sanity-check: required paths exist
foreach ($key in 'DailyReportRoot', 'AuditOutputRoot') {
    $p = $Config[$key]
    if (-not (Test-Path $p)) {
        $msg = "FATAL: $key does not exist: $p"
        Add-Content -Path $logFile -Value $msg
        Write-Error $msg
        exit 3
    }
}

# Build the prompt. `-p` is Claude Code's non-interactive mode; the
# skill matches via its `description` field in SKILL.md.
$stationsCsv = $Config.Stations -join ', '
# whatsapp-send config block — only injected when TwilioCredsPath is non-empty.
# Empty path means WhatsApp notifications are disabled for this run.
$whatsappBlock = ''
if ($Config.TwilioCredsPath -and $Config.TwilioCredsPath.Trim().Length -gt 0) {
    $driveLine = if ($Config.AuditDriveFolderUrl -and $Config.AuditDriveFolderUrl.Trim().Length -gt 0) {
        "- Audit Drive folder URL: $($Config.AuditDriveFolderUrl)"
    } else {
        "- Audit Drive folder URL: (not set — WhatsApp message will use local path)"
    }
    $whatsappBlock = @"
- Twilio credentials path: $($Config.TwilioCredsPath)
$driveLine
"@
}

$prompt = @"
Reference setup — save each as a ``reference`` memory if not already saved, and use these values in this run regardless of any older memory:
- Daily-report root: $($Config.DailyReportRoot)
- Audit-output root: $($Config.AuditOutputRoot)
- Bank-ledger Web App URL: $($Config.WebAppUrl)
- Bank-ledger Web App token: $($Config.WebAppToken)
- Bank-ledger local CSV path: $($Config.LocalCsvPath)
$whatsappBlock
Run the sale-audit skill for business date $auditDate across stations $stationsCsv. Render two PDFs per station (EN and CH) via the deterministic renderer in the skill's templates/ folder. Save them under <audit-output-root>/<YYYY>/<YYYY-MM>/<YYYY-MM-DD>/. Per §6 rule 11, try the Web App first; on any failure fall back to the local CSV. After both PDFs are written for each station, invoke the whatsapp-send skill per §8 step 6 of sale-audit — best-effort, never blocks the audit. Do not stop to ask questions — fail the run and log the reason instead.
"@

# Optional model pin
$claudeArgs = @('-p', $prompt)
if ($Config.Model -and $Config.Model.Trim().Length -gt 0) {
    $claudeArgs += @('--model', $Config.Model)
}

# Header in log so we can correlate runs
$banner = @"
============================================================
Evergreen Sale Audit — scheduled run
Started:    $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
Audit date: $auditDate
Stations:   $stationsCsv
Log:        $logFile
============================================================
"@
Add-Content -Path $logFile -Value $banner
Write-Host $banner

try {
    & claude $claudeArgs 2>&1 | Tee-Object -FilePath $logFile -Append
    $exitCode = $LASTEXITCODE
} catch {
    $exitCode = 99
    $err = "FATAL while invoking claude: $($_.Exception.Message)"
    Add-Content -Path $logFile -Value $err
    Write-Error $err
}

$footer = "Finished:   $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') (exit $exitCode)"
Add-Content -Path $logFile -Value $footer
Write-Host $footer
exit $exitCode
