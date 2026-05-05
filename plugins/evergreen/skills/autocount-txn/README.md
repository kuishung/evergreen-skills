# autocount-txn — scaffold

Quick orientation. Authoritative spec is **`SKILL.md`**.

## What this skill is meant to do

Take a batch of transactions (bank receipts, GL journals, sales receipts — anything **except** AP invoices, which `ap-invoice` already handles) and produce an Autocount-compatible `.xls` import file the operator drops into Autocount's import dialog.

## What's in this folder

| Path | Purpose |
|---|---|
| `SKILL.md`                          | The spec. Has TODO markers — read those first. |
| `templates/`                        | Drop the Autocount-shipped XLS import templates here, one per scoped transaction type. See SKILL.md §6. |
| `scripts/populate-import.py`        | Stub for the deterministic builder. Real logic lands here once the operator answers SKILL.md §2 / §5 / §6 / §7. |
| `examples/`                         | Sample source data + expected output for whichever modules end up scoped. |

## Why this is a separate skill from `ap-invoice`

AP invoices have their own integrity rules: vendor master, project codes derived from the bill-to address, complete-legal-name enforcement on the company entity. Mixing those with general-ledger or bank-side transactions confuses both flows. Two skills, clean separation.

## How to take this from scaffold to operational

1. Open `SKILL.md` and answer the TODO markers — pick which transaction types this skill will scope (§2), describe the source data shape (§7), drop Autocount templates into `templates/` (§6), and decide what reference files live in the static folder (§5).
2. Fill in `scripts/populate-import.py` with the row-mapping logic.
3. Bump `version:` in `SKILL.md` frontmatter to 0.2.0 once the first transaction type is wired end-to-end.
4. Test against a known-good source batch. Verify the resulting `.xls` actually imports into Autocount's preview screen without column errors.
5. When the skill works, document the operational flow at the top of SKILL.md and remove the "SCAFFOLD" status banner.
