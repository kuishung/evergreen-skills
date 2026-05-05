# Autocount XLS templates

The nine Autocount-shipped XLS import templates the skill writes into. **Don't modify these files** — they're as-shipped. The skill copies a template to TXN-output, then appends data rows starting at the first empty data position.

| Filename | Autocount module | Sheet name | Cols | Header rows | Sample rows |
|---|---|---|---|---|---|
| `Import-AP-Invoice.xls`     | AP Invoice                     | `AP Invoice`     | 22 | 3 (group / type / names) | row 4–5 |
| `Import-AP-Credit-Note.xls` | AP Credit Note                 | `AR Payment`*¹   | 23 | 1 (names) | row 2+ has B/F transactions as live samples |
| `Import-AP-Debit-Note.xls`  | AP Debit Note                  | `AP DebitNote`   | 27 | 3 | row 4–5 |
| `Import-AP-Payment.xls`     | AP Payment                     | `AP Payment`     | 23 | 3 | row 4–5 |
| `Import-AR-Invoice.xls`     | AR Invoice                     | `AR Invoice`     | 22 | 3 | row 4–5 |
| `Import-AR-Credit-Note.xls` | AR Credit Note                 | `AR Payment`*¹   | 30 | 3 | row 4–5 |
| `Import-AR-Debit-Note.xls`  | AR Debit Note                  | `AR DebitNote`   | 22 | 3 | row 4–5 |
| `Import-AR-Payment.xls`     | AR Payment                     | `AR Payment`     | 23 | 3 | row 4–5 |
| `Import-Journal-Entry.xls`  | General Journal                | `Sheet1`*²       | 28 | 1 | row 2+ |

*¹ Both `Import-AP-Credit-Note.xls` and `Import-AR-Credit-Note.xls` ship with a sheet named `"AR Payment"` (Autocount packaging quirk). Autocount's importer recognises them by their column names regardless of sheet name. Don't rename the sheets.

*² `Import-Journal-Entry.xls` has three sheets — `Sheet1` is the canonical tabular format the skill writes into; `Sheet2` is a human-readable form Autocount also accepts but the skill ignores; `Sheet3` is empty.

## Header row convention

Most templates use a 3-row header:

| Row | Content |
|---|---|
| 1 | Section grouping: `Master Columns` / `Detail Columns` / `Payment Detail Column` / `Knock Off Detail` (only above the first column of each block) |
| 2 | Data-type spec: `(20 chars)`, `(Date: dd/MM/yyyy)`, `(Boolean: T or F)`, `(Number, use System Currency Decimal)` |
| 3 | **Actual column names**: `DocNo`, `DocDate`, `CreditorCode`, etc. — also includes the comment `Bold column are mandate fields.` in column A |

Two exceptions use 1-row headers (column names directly in row 1, sample data from row 2):
- `Import-AP-Credit-Note.xls`
- `Import-Journal-Entry.xls` (Sheet1)

The skill autodetects the convention by looking for `DocNo` in row 1 (1-row header) vs row 3 (3-row header). See SKILL.md §3 for the per-module column lists.

## Refreshing templates

If Autocount is upgraded and emits a new template version:

1. On the workstation with Autocount, go to `Tools → Import → <module>` → click **"Sample"** or **"Download Sample"**.
2. Save the resulting `.xls` over the existing file in this folder using the **same filename**.
3. Re-read the column structure (open it, confirm rows 1–3 still match the convention SKILL.md §3 describes).
4. If the column count or order changed, update SKILL.md §3 to match before bumping the skill version. The deterministic builder writes column-name-first, so a shuffled column order doesn't break it — but missing columns or new required columns will.
