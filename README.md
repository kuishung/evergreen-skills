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
```

## Maintainer workflow (Kui Shung)

1. Edit `SKILL.md` or add files under `plugins/<plugin-name>/`.
2. Bump `version` in **both** `plugins/<plugin-name>/.claude-plugin/plugin.json`
   **and** the matching entry in `.claude-plugin/marketplace.json`.
3. `git commit -am "..." && git push`.
4. Staff pick it up on next `/plugin marketplace update evergreen` (or auto-update).
