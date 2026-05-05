---
name: autocount-txn
description: Use this skill whenever the user (Evergreen back-office) wants to turn a batch of transactions into an Autocount XLS import file — for any of the nine Autocount import modules: AP Invoice, AP Credit Note, AP Debit Note, AP Payment, AR Invoice, AR Credit Note, AR Debit Note, AR Payment, or General Journal Entry. The skill takes structured row data (CSV, XLSX, or pasted-in batch), looks up creditor / debtor / GL-account / project codes against static reference files, and populates the matching Autocount XLS template. Triggers include "build AP invoice import", "build AP credit note import", "import AR receipts into Autocount", "generate journal entry XLS", "populate Autocount template for <module>", or any explicit reference to one of the nine module names above.
version: 0.1.0
updated: 2026-05-04
---

# Autocount Transaction Import Builder — SCAFFOLD

> **Status: scaffold — partially specced.** The nine Autocount XLS templates are committed under `templates/` and the column layout for each is documented in §3 below. The deterministic builder script (`scripts/populate-import.py`) is still a stub. The operator answers the source-data shape questions in §6 and the static reference files in §5 before the skill runs end-to-end.

---

## 1. What this skill does (and what it doesn't)

**Does:** takes a structured source dataset of transactions, maps each row to the columns Autocount expects for the chosen module, populates the matching Autocount XLS import template (see `templates/`), and writes a single `.xls` ready to drop into Autocount's import dialog.

**Does NOT:** import into Autocount itself. Autocount's import is interactive (file picker → preview → confirm); this skill produces the file, the operator clicks Import. The skill never logs into Autocount, never writes to its database, and never bypasses the operator review step.

**Does NOT:** do OCR or invoice-content extraction from scanned PDFs / images. The skill assumes the source data already arrives as structured rows with named fields. If you're starting from PDFs, run them through OCR / hand-data-entry first, produce a CSV or XLSX, then feed that to this skill.

## 2. Stations and project codes (`ProjNo`)

The `ProjNo` column in Autocount must be one of:

| Station | Segments (→ ProjNo) |
|---------|---------------------|
| TK (Tg. Kapor)    | `TK-Fuel`, `TK-Mart`, `TK-iBing` |
| BS (Berkat Setia) | `BS-Fuel`, `BS-Mart`, `BS-Rental` |
| BL (Bubul Lama)   | `BL-Fuel`, `BL-Mart`, `BL-Rental` |

Each `ProjNo` is ≤ 10 characters (Autocount limit).

## 3. Supported modules and their column layouts

The skill supports **nine** Autocount import modules. Each ships its own XLS template under `templates/`. The operator points the skill at one template per run (via `--type`); rows are appended starting at the first empty data row.

> **Header-row convention.** Most templates use a 3-row header:
> - **Row 1**: section grouping (`Master Columns` / `Detail Columns` / `Payment Detail Column` / `Knock Off Detail`).
> - **Row 2**: data-type spec (e.g. `(20 chars)`, `(Date: dd/MM/yyyy)`, `(Boolean: T or F)`).
> - **Row 3**: **actual column names** (this is what the skill maps source fields to).
>
> Two exceptions use a 1-row header (column names directly in row 1, sample data from row 2):
> - `Import-AP-Credit-Note.xls`
> - `Import-Journal-Entry.xls` (Sheet1)
>
> The skill autodetects the convention by checking row 1 for known column names like `DocNo`. Don't rebuild the templates by hand — use the as-shipped Autocount files (already committed under `templates/`).

### 3.1 AP Invoice (`templates/Import-AP-Invoice.xls`)

22 columns. Master block (one row per invoice header) + Detail block (one row per invoice line).

| Section | Column | Type | Notes |
|---|---|---|---|
| Master | `DocNo` | 20 chars | `<<New>>` to auto-number, or our own DocNo. |
| Master | `DocDate` | dd/MM/yyyy | Invoice date. |
| Master | `CreditorCode` | 12 chars | Autocount creditor, e.g. `400-A001`. |
| Master | `SupplierInvoiceNo` | 20 chars | Vendor's own invoice number. |
| Master | `JournalType` | 10 chars | Usually `PURCHASE`. |
| Master | `DisplayTerm` | 30 chars | E.g. `C.O.D.`, `30 DAYS`. |
| Master | `PurchaseAgent` | 12 chars | Optional. |
| Master | `Description` | 80 chars | Invoice header description. |
| Master | `CurrencyRate` | number | E.g. `1.0` for MYR. |
| Master | `RefNo2` | 20 chars | Optional secondary ref. |
| Master | `Note` | rich text | Long-form notes. |
| Master | `InclusiveTax` | T/F boolean | Whether tax is included in line amounts. |
| Detail | `AccNo` | 12 chars | GL account, e.g. `610-0000`. |
| Detail | `ToAccountRate` | number | Currency rate for this line. |
| Detail | `DetailDescription` | 100 chars | Per-line description. |
| Detail | `ProjNo` | 10 chars | Per §2. |
| Detail | `DeptNo` | 10 chars | Optional. |
| Detail | `TaxType` | 8 chars | E.g. `SR`, `ZR`, blank. |
| Detail | `TaxableAmt` | number | Line tax-base amount. |
| Detail | `TaxAdjustment` | number | Optional. |
| Detail | `Amount` | number | Line amount. |

A multi-line invoice repeats the Master columns blank on lines 2..N (only Detail columns populated). The skill takes care of this when you pass multiple line rows tagged with the same `DocNo`.

### 3.2 AP Credit Note (`templates/Import-AP-Credit-Note.xls`)

23 columns. **Single-row header.** (Sheet name is "AR Payment" — that's an Autocount packaging quirk; Autocount recognises it by its column names regardless of sheet name.)

Columns (in order): `DocNo` · `DocDate` · `CreditorCode` · `SupplierCNNo` · `JournalType` · `CNType` · `CurrencyCode` · `CurrencyRate` · `Description` · `SupplierInvoiceNo` · `InclusiveTax` · *(blank)* · *(blank)* · `Note` · `AccNo` · `ToAccountRate` · `DetailDescription` · `Amount` · *(blank)* · *(blank)* · `KnockOffDocType` · `KnockOffDocNo` · `KnockOffAmt`.

The two trailing knock-off columns let a CN immediately settle against an existing PB (Invoice) or PD (Debit Note). `KnockOffDocType` is 2 chars: `PB` for Invoice, `PD` for Debit Note.

### 3.3 AP Debit Note (`templates/Import-AP-Debit-Note.xls`)

27 columns. 3-row header. Similar shape to AP Invoice (Master + Detail) but adds `Reason` and `TaxPermitNo` columns.

Master columns: `DocNo` · `DocDate` · `CreditorCode` · `SupplierDNNo` · `JournalType` · `DisplayTerm` · `PurchaseAgent` · `Description` · `CurrencyCode` · `CurrencyRate` · `SupplierInvoiceNo` · `RefNo2` · `Note` · `Reason` · `InclusiveTax`.

Detail columns: `AccNo` · `ToAccountRate` · `DetailDescription` · `ProjNo` · `DeptNo` · `TaxType` · `TaxPermitNo` · `TaxableAmt` · `Tax` · `TaxAdjustment` · `Amount`.

### 3.4 AP Payment (`templates/Import-AP-Payment.xls`)

23 columns. 3-row header. Three blocks: Master · Payment Detail · Knock Off Detail.

Master: `DocNo` · `DocDate` · `CreditorCode` · `Description` · `ProjNo` · `DeptNo` · `CurrencyCode` · `ToHomeRate` · `ToCreditorRate` · `Note`.
Payment Detail: `PaymentMethod` · `ChequeNo` · `PaymentAmt` · `BankCharge` · `ToBankRate` · `PaymentBy` · `FloatDay` · `IsRCHQ` (Returned Cheque T/F) · `RCHQDate`.
Knock Off Detail: `KnockOffDocType` (`PB`/`PD`) · `KnockOffDocNo` · `KnockOffAmt`.

`PaymentMethod` ∈ `BANK`, `CASH`, `CHEQUE`, etc. — match exactly what Autocount has configured.

### 3.5 AR Invoice (`templates/Import-AR-Invoice.xls`)

22 columns. 3-row header. Mirror of AP Invoice but on the receivable side: `DebtorCode` instead of `CreditorCode`, `SalesAgent` instead of `PurchaseAgent`, `JournalType` is usually `SALES`, default `AccNo` is in the 5xx-xxxx range (revenue).

### 3.6 AR Credit Note (`templates/Import-AR-Credit-Note.xls`)

30 columns. 3-row header. (Sheet name is "AR Payment" — same Autocount quirk as §3.2.)

Master: `DocNo` · `DocDate` · `DebtorCode` · `JournalType` · `CNType` · `CurrencyCode` · `Description` · `Ref` · `RefNo2` · `Note` · *(blanks)* · `Note` · `InclusiveTax` · `CurrencyRate`.
Detail: `AccNo` · `ToAccountRate` · `DetailDescription` · `ProjNo` · `DeptNo` · `TaxType` · `TaxableAmt` · `TaxAdjustment` · `Amount`.
Knock Off: `KnockOffDocType` (`RI` for AR Invoice, `RD` for AR Debit Note) · `KnockOffDocNo` · `KnockOffAmt`.

### 3.7 AR Debit Note (`templates/Import-AR-Debit-Note.xls`)

22 columns. 3-row header. Mirror of AP Debit Note on the receivable side.

### 3.8 AR Payment (`templates/Import-AR-Payment.xls`)

23 columns. 3-row header. Mirror of AP Payment on the receivable side. `KnockOffDocType` ∈ `RI` (Invoice) / `RD` (Debit Note). `IsRCHQ` is the returned-cheque flag.

### 3.9 General Journal Entry (`templates/Import-Journal-Entry.xls`)

28 columns, **single-row header** in Sheet1.

Columns: `DocNo` · `DocDate` · `JournalType` · `DocNo2` · `DocumentDescription` · `CurrencyCode` · `CurrencyRate` · `InclusiveTax` · `AccNo` · `ToAccountRate` · `TaxType` · `Description` · `FurtherDescription` · `RefNo2` · `SalesAgent` · `TaxBRNo` · `TaxBName` · `TaxRefNo` · `TaxPermitNo` · `TaxExportCountry` · `DR` · `CR` · `TaxableDR` · `TaxableCR` · `TaxAdjustment` · `TaxDR` · `TaxCR` · `SupplyPurchase`.

Multi-line journals: row 1 carries the master fields (`DocNo` = `<<New>>` or our own number, `DocDate`, `JournalType`, `DocumentDescription`, `CurrencyCode`, `CurrencyRate`, `InclusiveTax`); rows 2..N leave those blank and fill only the line columns (`AccNo`, `Description`, `DR`/`CR`, etc.). Sheet2 contains a human-readable journal-entry template that Autocount also accepts but the skill doesn't write — Sheet1's tabular format is the canonical machine target.

## 4. Paths — ask once, save to memory

On first run, ask and save three `reference` memories:

1. **TXN-input root** — where source data files (CSV / XLSX / pasted-in batch) get dropped by the operator. Flat folder; the skill creates `processed/` and `unresolved/` subfolders on first scan.
2. **TXN-output root** — where monthly `.xls` import files and the `txn-state.json` manifest live.
3. **TXN-static folder** — where the chart-of-accounts mapping, customer/creditor masters, and other reference files live (see §5).

Before reusing any remembered path, verify it resolves; if not, ask once and update the memory.

## 5. Static folder — required reference files — TODO (operator confirms)

The skill never invents creditor codes, debtor codes, GL accounts, project codes, or tax types. All must be looked up from authoritative reference files in TXN-static. **TODO — operator confirms which reference files belong here. Likely set:**

- `chart-of-accounts.xlsx` — Autocount GL account master (`AccNo`, `AccName`, optional `IsControl`). Source-of-truth for §3 `AccNo` cells.
- `creditor-master.xlsx` — vendors. One row per creditor with `CreditorCode`, `CreditorName`, `Aliases`, `DefaultAccNo`, `DefaultTaxType`. Used by AP modules (§3.1–3.4).
- `debtor-master.xlsx` — customers. Same shape as creditor-master, `DebtorCode` instead of `CreditorCode`. Used by AR modules (§3.5–3.8).
- `tax-type-map.txt` — Autocount tax codes valid in the operator's COA, e.g. `SR`, `ZR`, `OS`, `EP`, blank. The skill rejects any source row whose tax type is not in this list.
- `project-no-map.txt` — the nine `ProjNo` codes in §2, possibly with default GL accounts per project.

For each reference file, **document its columns / format here once the operator settles the design.**

## 6. Source data shape — TODO (per module)

The skill's job per run: read N source rows, output one Autocount XLS. **TODO — operator describes how transactions arrive for each module they actually use.** Likely scenarios:

- **AP Invoice / AP Credit Note / AP Debit Note** — usually a hand-prepared XLSX from accounts staff after they've manually transcribed the vendor bills, OR an OCR-extracted JSON from any external invoice-extraction tool. The skill itself doesn't OCR PDFs.
- **AR Invoice / AR Credit Note / AR Debit Note** — arrive as a hand-prepared XLSX, or generated from a sales-side pipeline (TBD).
- **AP Payment / AR Payment** — arrive from bank statements (the bank-clearance skill, when it ships) or hand-prepared after staff reconciles cheques + IFTs against open invoices.
- **General Journal** — arrive as a hand-prepared XLSX (typical for accruals, depreciation, year-end adjustments).

For each input shape the skill needs:
- A repeatable parser (column index → field).
- A dedupe key (so the same source row never produces two import lines on consecutive runs — rerunning the skill on a partially-processed input is safe).
- A clear "unresolved" path for rows that don't map cleanly (missing creditor code, ambiguous account, tax type unknown) — never silently drop or invent.

## 7. Workflow

(Will be filled in once §5 + §6 are answered. Likely shape:)

1. Confirm the three reference values in §4 (TXN-input root, TXN-output root, TXN-static folder) and the target Autocount module.
2. Verify the static files in §5 exist and parse cleanly.
3. Open the matching XLS template under `templates/` (read-only — the skill never modifies committed templates; it copies and writes to TXN-output).
4. Scan the TXN-input root for new source files since the last run (per `txn-state.json`).
5. For each source row:
   - Parse → dedupe (skip if seen) → look up CreditorCode/DebtorCode/AccNo/ProjNo/TaxType in the static refs → map to template columns → emit one row at the next empty position in the output XLS.
   - Rows that can't map cleanly land in `unresolved/` with a written reason.
6. Save the output XLS to TXN-output, e.g. `<TXN-output-root>/<YYYY-MM>/<module>-<YYYY-MM>.xls`.
7. Update `txn-state.json` with the just-processed source-row hashes.
8. Reply with: count of imported rows, count of unresolved rows, absolute path to the `.xls`, list of any creditor / debtor / account / tax lookups that failed.

## 8. Output — what staff sees

- One `.xls` per Autocount module per month (e.g., `2026-05-ap-invoice.xls`, `2026-05-journal.xls`). Staff opens Autocount → Tools → Import → picks the file → Autocount previews → staff confirms.
- One `txn-state.json` manifest tracking which source rows have already been imported.
- An `unresolved/` subfolder under TXN-input with a copy of any input row the skill couldn't map, plus a `WHY-UNRESOLVED.txt` line per row.

## 9. Open questions for the operator (resolve these before the skill goes operational)

- For each of the 9 modules in §3, confirm the upstream source (hand-keyed XLSX? upstream skill output? bank-statement parser?). The skill spec for §6 follows from that.
- Static reference files: confirm which ones are needed per module (§5).
- Source data shape per module (§6) — especially: do AP Payments / AR Payments come from bank-statement parsing, from hand-prepared XLSX, or from another upstream skill?
- Naming convention for output files inside TXN-output root — date-folder or flat? One file per module per month or one combined?
- Re-import idempotence: does Autocount's import detect duplicates on `DocNo` itself, or do we own all the dedup logic in `txn-state.json`?
