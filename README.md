# Evergreen Claude Code Skills

Internal Claude Code plugin marketplace for Evergreen staff.

## Install (staff, one time per machine)

```bash
gh auth login                                       # authenticate with GitHub
claude                                              # start Claude Code
```

Inside Claude Code:

```
/plugin marketplace add kuishung/evergreen-skills
/plugin install hello-evergreen@evergreen
```

Restart Claude Code (or run `/reload-plugins`). Ask Claude *"hello evergreen"* to verify.

## Update (staff, when new skills ship)

```
/plugin marketplace update evergreen
/plugin update
```

Or enable auto-update in `/plugin` → **Marketplaces** tab.

## Layout

```
.claude-plugin/marketplace.json          catalog of plugins
plugins/<plugin-name>/
  .claude-plugin/plugin.json             plugin manifest (bump version here)
  skills/<skill-name>/SKILL.md           the actual skill
tools/                                   deployment helpers (not part of the plugin)
  win11-scheduled-audit/                 Task Scheduler runner for nightly sale-audit
```

## Scheduled runs (Windows 11 server)

For unattended daily audits at 06:30 (auditing yesterday's business date, after the 06:00 bank-ledger ingestion has finished), use the Task Scheduler runner under [`tools/win11-scheduled-audit/`](tools/win11-scheduled-audit/README.md). One PowerShell line installs everything: prompts you for the paths and Web App credentials, writes the wrapper, registers the daily task, optionally runs a test. Cowork's sandbox can't reach `script.google.com` for §6.11 clearance verification, so production schedules belong on the Windows server; Cowork is reserved for interactive ad-hoc work.

## Maintainer workflow (Kui Shung)

1. Edit `SKILL.md` or add files under `plugins/<plugin-name>/`.
2. Bump `version` in **both** `plugins/<plugin-name>/.claude-plugin/plugin.json`
   **and** the matching entry in `.claude-plugin/marketplace.json`.
3. `git commit -am "..." && git push`.
4. Staff pick it up on next `/plugin marketplace update evergreen` (or auto-update).
