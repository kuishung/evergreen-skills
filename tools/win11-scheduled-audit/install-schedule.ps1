#requires -Version 5.1
<#
  Evergreen Sale Audit - one-shot installer for Windows 11.

  Run once, end to end:
    iwr https://raw.githubusercontent.com/kuishung/evergreen-skills/main/tools/win11-scheduled-audit/install-schedule.ps1 -UseBasicParsing | iex

  What it does (in order):
    1. Verifies `claude` is on PATH (otherwise tells you to install it).
    2. Prompts for the five config values (folders, Web App URL, token).
    3. Writes the wrapper script + a runtime config to
       %ProgramData%\Evergreen\sale-audit\.
    4. Registers a daily Task Scheduler entry at 06:30 via schtasks.exe
       (no XML editing, no GUI).
    5. Offers to run a test invocation immediately.

  Re-running is safe - it overwrites the wrapper / config / task.
#>

$ErrorActionPreference = 'Stop'

# ───────────────────────── 1. Pre-flight checks ──────────────────────
Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  Evergreen Sale Audit - daily 06:30 schedule installer"     -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""

if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: 'claude' is not on PATH for this Windows account." -ForegroundColor Red
    Write-Host "Install Claude Code first, then re-run this installer:" -ForegroundColor Yellow
    Write-Host "  npm install -g @anthropic-ai/claude-code" -ForegroundColor Yellow
    Write-Host "  ...or download the installer at https://code.claude.com" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "After installing, run 'claude' once in PowerShell to authenticate," -ForegroundColor Yellow
    Write-Host "then run /plugin marketplace add kuishung/evergreen-skills and" -ForegroundColor Yellow
    Write-Host "/plugin install evergreen@evergreen inside that session." -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

Write-Host "[OK] Claude Code found: $((Get-Command claude).Source)" -ForegroundColor DarkGray

# ───────────────────────── 2. Prompt for config ──────────────────────
function Read-WithDefault($label, $default) {
    if ($default) {
        $v = Read-Host "$label [$default]"
        if ([string]::IsNullOrWhiteSpace($v)) { return $default } else { return $v }
    }
    do {
        $v = Read-Host $label
    } while ([string]::IsNullOrWhiteSpace($v))
    return $v
}

Write-Host ""
Write-Host "Tell me where things live on this machine. Press Enter to accept" -ForegroundColor Cyan
Write-Host "the default if it's already correct." -ForegroundColor Cyan
Write-Host ""

$DailyReportRoot = Read-WithDefault 'Daily-report root path' 'C:\Users\KS\DATA\Evergreen\DailyReports'
$AuditOutputRoot = Read-WithDefault 'Audit-output root path' 'C:\Users\KS\DATA\Evergreen\AuditOutput'
$LocalCsvPath    = Read-WithDefault 'Bank-ledger local CSV path (for fallback; can be empty)' ''
$WebAppUrl       = Read-WithDefault 'Bank-ledger Web App URL'   ''
$WebAppToken     = Read-WithDefault 'Bank-ledger Web App token' ''
$RunTime         = Read-WithDefault 'Daily run time (HH:mm 24h)' '06:30'

# Sanity-check the run time
if ($RunTime -notmatch '^\d{2}:\d{2}$') {
    Write-Host "ERROR: time must look like HH:mm (e.g., 06:30)." -ForegroundColor Red
    exit 2
}

# Sanity-check folders exist (or offer to create)
foreach ($pair in @(
    @{ Label = 'DailyReportRoot'; Path = $DailyReportRoot },
    @{ Label = 'AuditOutputRoot'; Path = $AuditOutputRoot }
)) {
    if (-not (Test-Path $pair.Path)) {
        $resp = Read-Host "Path doesn't exist: $($pair.Path) - create it now? [Y/n]"
        if ($resp -eq '' -or $resp -match '^[Yy]') {
            New-Item -ItemType Directory -Path $pair.Path -Force | Out-Null
            Write-Host "  Created $($pair.Path)" -ForegroundColor DarkGray
        } else {
            Write-Host "ERROR: $($pair.Label) must exist before scheduling." -ForegroundColor Red
            exit 3
        }
    }
}

# ───────────────────────── 3. Write the wrapper ──────────────────────
$installRoot = Join-Path $env:ProgramData 'Evergreen\sale-audit'
if (-not (Test-Path $installRoot)) {
    New-Item -ItemType Directory -Path $installRoot -Force | Out-Null
}

$wrapperPath = Join-Path $installRoot 'run-sale-audit.ps1'
$configPath  = Join-Path $installRoot 'config.json'

# Persist the config as JSON so the wrapper reads it at run time -
# means re-running this installer with new values is the only place
# that ever changes them.
@{
    DailyReportRoot = $DailyReportRoot
    AuditOutputRoot = $AuditOutputRoot
    LocalCsvPath    = $LocalCsvPath
    WebAppUrl       = $WebAppUrl
    WebAppToken     = $WebAppToken
    AuditOffsetDays = -1
    Stations        = @('TK', 'BS', 'BL')
} | ConvertTo-Json | Set-Content -Path $configPath -Encoding UTF8

Write-Host "[OK] Config written: $configPath" -ForegroundColor DarkGray

# The wrapper itself - small, reads config, builds prompt, calls claude
$wrapperContent = @'
$ErrorActionPreference = 'Stop'
$cfgPath = Join-Path $PSScriptRoot 'config.json'
if (-not (Test-Path $cfgPath)) { throw "Config not found: $cfgPath" }
$Cfg = Get-Content $cfgPath -Raw | ConvertFrom-Json

$auditDate = (Get-Date).AddDays($Cfg.AuditOffsetDays).ToString('yyyy-MM-dd')

$logDir = Join-Path $Cfg.AuditOutputRoot '_logs'
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
$logFile = Join-Path $logDir ("audit-{0}.log" -f (Get-Date -Format 'yyyyMMdd_HHmmss'))

if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
    "FATAL: 'claude' not on PATH" | Tee-Object -FilePath $logFile -Append | Write-Error
    exit 2
}

# Anchor the working directory to a folder we control, otherwise
# Task Scheduler launches us from C:\WINDOWS\system32 and Claude
# locks its permission scope there.
Set-Location -Path $Cfg.AuditOutputRoot

# Force Claude Code to refresh the evergreen plugin from GitHub on
# every launch. Without this the scheduled run uses whatever version
# was last pulled into ~\.claude\plugins\cache\, even after the
# maintainer pushes new commits. Setting FORCE_AUTOUPDATE_PLUGINS=1
# makes every 06:30 trigger pull-latest before invoking the skill,
# so the server never falls behind GitHub without explicit upkeep.
$env:FORCE_AUTOUPDATE_PLUGINS = '1'

$stationsCsv = $Cfg.Stations -join ', '
# IMPORTANT prompt ordering: action first, context second. claude in
# -p mode is single-turn, and if the first paragraph reads like a
# task ("Reference setup -- save each as a memory..."), claude
# treats it as THE task, finishes it, and exits without doing the
# actual audit. Leading with "Run the daily sale audit..." anchors
# the work; the reference values follow as supporting context.
$prompt = @"
TASK: Run the daily sale audit for business date $auditDate across stations $stationsCsv. Render the EN and CH PDFs per station via the deterministic renderer in the sale-audit skill's templates/ folder, and save them under <audit-output-root>/<YYYY>/<YYYY-MM>/<YYYY-MM-DD>/. The audit must produce 6 PDFs total (3 stations x 2 languages).

USE THESE REFERENCE VALUES for this run (override anything in older memory):
- Daily-report root: $($Cfg.DailyReportRoot)
- Audit-output root: $($Cfg.AuditOutputRoot)
- Bank-ledger Web App URL: $($Cfg.WebAppUrl)
- Bank-ledger Web App token: $($Cfg.WebAppToken)
- Bank-ledger local CSV path: $($Cfg.LocalCsvPath)

CLEARANCE: Per `§6` rule 11, try the Bank-ledger Web App first. If the Web App fails (network unreachable, token mismatch, 403, etc.), fall back to reading the local CSV at the path above. Only defer `§6.11` if neither source is available.

EXECUTION: Do not stop to ask questions. If any check fails, log the reason and continue to the next check / next station so the run still produces what it can. Exit non-zero only if no PDFs at all could be rendered.
"@

$banner = "=== Evergreen Sale Audit === $((Get-Date).ToString('yyyy-MM-dd HH:mm:ss')) === audit date $auditDate === stations $stationsCsv ==="
Add-Content -Path $logFile -Value $banner
Write-Host $banner

# --dangerously-skip-permissions is the documented opt-in for
# unattended runs: there's no human at 06:30 to answer prompts, and
# the wrapper is the only thing that ever calls claude in this
# context, so the trust boundary is the wrapper itself. The flag
# also makes --add-dir redundant -- with permissions skipped,
# claude can already read/write any path the prompt mentions.
#
# Invoke via the .cmd shim explicitly. The .ps1 shim that npm also
# generates joins args incorrectly when invoked through Tee-Object,
# turning the array into a single space-joined string that claude
# then sees as one unknown option. The .cmd shim uses %* which
# preserves arg boundaries reliably.
$claudeShim = Join-Path $env:APPDATA 'npm\claude.cmd'
if (-not (Test-Path $claudeShim)) {
    # Fall back to whatever resolves on PATH
    $resolved = Get-Command claude.cmd -ErrorAction SilentlyContinue
    if ($resolved) { $claudeShim = $resolved.Source } else { $claudeShim = 'claude' }
}

try {
    # Pipe the prompt via stdin instead of passing it as -p <prompt>:
    # cmd.exe's arg parser truncates multi-line strings at the first
    # newline, so the previous test only sent the first line of the
    # reference-setup block to claude. claude -p with no inline value
    # reads the prompt from stdin, where line breaks pass through
    # cleanly.
    $prompt | & $claudeShim --dangerously-skip-permissions -p 2>&1 |
        Tee-Object -FilePath $logFile -Append
    $exitCode = $LASTEXITCODE
} catch {
    $exitCode = 99
    "FATAL while invoking claude: $($_.Exception.Message)" |
        Tee-Object -FilePath $logFile -Append | Write-Error
}
"Finished $((Get-Date).ToString('yyyy-MM-dd HH:mm:ss')) (exit $exitCode)" | Tee-Object -FilePath $logFile -Append
exit $exitCode
'@

Set-Content -Path $wrapperPath -Value $wrapperContent -Encoding UTF8
Write-Host "[OK] Wrapper written: $wrapperPath" -ForegroundColor DarkGray

# ───────────────────────── 4. Register the scheduled task ────────────
$taskName = 'Evergreen Sale Audit Daily'

# Remove any prior version so the installer is idempotent. schtasks
# writes to stderr and returns non-zero when the task doesn't exist,
# which $ErrorActionPreference='Stop' would otherwise treat as fatal.
$taskExists = $false
try {
    $null = & schtasks /Query /TN $taskName 2>&1
    if ($LASTEXITCODE -eq 0) { $taskExists = $true }
} catch {
    # No prior task; that's fine.
}
if ($taskExists) {
    & schtasks /Delete /TN $taskName /F 2>&1 | Out-Null
    Write-Host "[OK] Removed previous schedule." -ForegroundColor DarkGray
}

$action = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$wrapperPath`""
schtasks /Create `
    /SC DAILY `
    /ST $RunTime `
    /TN $taskName `
    /TR $action `
    /RL LIMITED `
    /F | Out-Null

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: failed to register Task Scheduler entry." -ForegroundColor Red
    exit 4
}

Write-Host "[OK] Scheduled task '$taskName' registered for daily $RunTime." -ForegroundColor DarkGray

# ───────────────────────── 5. Offer a manual test ────────────────────
Write-Host ""
$test = Read-Host 'Run a test invocation now? (recommended) [Y/n]'
if ($test -eq '' -or $test -match '^[Yy]') {
    Write-Host ""
    Write-Host "--- TEST RUN ---" -ForegroundColor Yellow
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $wrapperPath
    $rc = $LASTEXITCODE
    Write-Host ""
    if ($rc -eq 0) {
        Write-Host "[OK] Test run completed (exit 0)." -ForegroundColor Green
        Write-Host "  Check $($AuditOutputRoot) for the rendered PDFs and" -ForegroundColor DarkGray
        Write-Host "  $($AuditOutputRoot)\_logs\ for the run log." -ForegroundColor DarkGray
    } else {
        Write-Host "[!!] Test run exited with code $rc - see $($AuditOutputRoot)\_logs\ for details." -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  Setup complete."                                            -ForegroundColor Green
Write-Host "  Daily run:    $RunTime"                                     -ForegroundColor Green
Write-Host "  Wrapper:      $wrapperPath"                                 -ForegroundColor Green
Write-Host "  Config:       $configPath"                                  -ForegroundColor Green
Write-Host "  Logs:         $AuditOutputRoot\_logs\"                      -ForegroundColor Green
Write-Host "  Task name:    $taskName"                                    -ForegroundColor Green
Write-Host ""
Write-Host "  To re-run on demand:    schtasks /Run /TN `"$taskName`""    -ForegroundColor DarkGray
Write-Host "  To change config:       re-run this installer."             -ForegroundColor DarkGray
Write-Host "  To remove the schedule: schtasks /Delete /TN `"$taskName`" /F" -ForegroundColor DarkGray
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
