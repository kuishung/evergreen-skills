---
name: ap-invoice
description: Use this skill whenever the user (Evergreen back-office) wants to turn uploaded vendor invoices into an Autocount AP Invoice import file. Triggers include "run AP invoice", "AP invoice skill", "process AP", "import vendor invoices", "AP entry", "generate AP import for Autocount", or any request to scan the AP invoice folder, dedupe, rename, and produce the Autocount import `.xls`.
version: 0.2.0
updated: 2026-04-23 21:38
---

# AP Invoice — Autocount Import Builder

Scan the AP invoice folder, extract each vendor invoice, dedupe by content, assign the correct Autocount project code, rename the file, and emit a delta `.xls` import file that staff imports into Autocount. Runs incrementally: on each invocation only new invoices are processed.

---

## 1. Stations and project codes (`ProjNo`)

The `ProjNo` column in Autocount must be one of:

| Station | Segments (→ ProjNo) |
|---------|---------------------|
| TK (Tg. Kapor)    | `TK-Fuel`, `TK-Mart`, `TK-iBing` |
| BS (Berkat Setia) | `BS-Fuel`, `BS-Mart`, `BS-Rental` |
| BL (Bubul Lama)   | `BL-Fuel`, `BL-Mart`, `BL-Rental` |

Each `ProjNo` is ≤ 10 characters (Autocount limit).

## 2. Paths — ask once, save to memory

On first run, ask and save three `reference` memories:

1. **AP-input root** — where site staff drops scanned invoices. Flat folder (no per-station subfolders required). Sub-folders `processed/` and `unresolved/` are created by the skill.
2. **AP-output root** — where the monthly `.xls` import files and the `ap-state.json` manifest live.
3. **AP-static folder** — where the vendor master and other reference files live (see §3).

Before reusing any remembered path, verify it resolves; if not, ask once and update the memory.

## 3. Static folder — required reference files

The AP-static folder must contain **both** reference files below before the skill can run. On start-up, confirm both files exist and are readable; if either is missing, stop and tell the user exactly which file is missing. **Do not guess creditor codes, GL accounts, or whether an invoice belongs to the company.**

### 3.1 `vendor-master.xlsx` (or `.xls`)

One row per vendor. Columns:

| Column          | Purpose                                                                    |
|-----------------|----------------------------------------------------------------------------|
| `VendorName`    | Canonical vendor name (case-insensitive match on invoice header).          |
| `Aliases`       | Semicolon-separated alternate spellings / trading names (optional).        |
| `CreditorCode`  | Autocount creditor code, e.g., `400-A001` (12 chars max).                  |
| `DefaultAccNo`  | Default Autocount GL account, e.g., `610-0000` (12 chars max).             |
| `DefaultTaxType`| Optional Autocount tax code (8 chars max). Blank = no tax line.            |
| `Notes`         | Freeform.                                                                  |

Matching an invoice to a vendor row: case-insensitive match on `VendorName` first, then against each entry in `Aliases`. No match → the invoice is **unresolved** (see §7) — never invent a creditor code.

### 3.2 `company-entities.txt`

Plain text. Two kinds of line, each with a prefix:

- **`ENTITY:`** — the **complete and correct** registered legal name that vendor invoices must bear on the bill-to / customer block. Partial names (e.g., "Evergreen", "Evergreen Insight") must **not** be listed here — only the full legal name counts as a valid Evergreen bill-to.
- **`STATION <CODE>:`** — a name or address fragment that identifies the delivery location as one specific station. `<CODE>` is one of `TK`, `BS`, `BL`. Multiple lines per station are allowed (aliases and spelling variants).

Blank lines and lines starting with `#` are comments.

Example:

```
# Registered entity — complete legal name required on every invoice bill-to
ENTITY: EVERGREEN INSIGHT SDN. BHD.

# Station delivery addresses — add variants as vendors use them
STATION TK: Tg. Kapor
STATION TK: Tanjung Kapor
STATION BS: Berkat Setia
STATION BL: Bubul Lama
```

**Matching semantics (both ENTITY and STATION):**

Normalize both the invoice text and the file entry by:
1. Upper-casing,
2. Stripping `.` and `,`,
3. Collapsing repeated whitespace to a single space,
4. Trimming leading/trailing whitespace.

Then check that the normalized file entry appears as a **contiguous substring** of the normalized invoice region. Example: `EVERGREEN INSIGHT SDN. BHD.` normalizes to `EVERGREEN INSIGHT SDN BHD`; an invoice bill-to reading `Evergreen Insight Sdn Bhd, 123 ABC Road` also normalizes to include `EVERGREEN INSIGHT SDN BHD` — match passes. An invoice reading just `Evergreen Sdn Bhd` or `Evergreen Insight` fails — missing token sequence.

**Never override the match.** If the user insists a particular invoice is legitimate but it does not bear the complete legal name, the correct fix is to send it back to the vendor for a reissue — not to add a shortened entity variant to this file.

## 4. Input — what staff upload

Accepted file types: PDF, JPG, JPEG, PNG. Anything else is moved to `unresolved/` with reason `unsupported file type`.

For each candidate file, extract (using vision/OCR as needed):

- Issuer / vendor name (free text on the invoice header)
- Invoice number (`SupplierInvoiceNo`)
- Invoice date
- Invoice total (amount)
- Line items (description, quantity, amount)
- Any tax line / SST amount
- **Bill-to / customer block** (company name + address on the "bill to" or "customer" portion)
- **Deliver-to / ship-to block** (separate delivery address block; sometimes identical to bill-to)

### 4.1 Validity and ownership checks — run before anything else

Apply these to every file **before** vendor lookup or project-code inference. Any failure routes the file to `unresolved/` (§7.3) with the stated reason. Matching uses the normalization rules in §3.2.

| # | Check | Reason if it fails |
|---|-------|--------------------|
| 1 | Looks like an invoice/receipt (has a vendor header, an invoice/receipt number *or* document date, and a monetary total) | `not an invoice` |
| 2 | **Bill-to / customer block** contains an `ENTITY:` entry from `company-entities.txt` as a complete substring | `missing complete legal name` |
| 3 | **Deliver-to / ship-to block** contains exactly one `STATION <CODE>:` entry from `company-entities.txt`; the matched `<CODE>` becomes the station | `delivery address does not identify TK/BS/BL` (or `delivery address identifies multiple stations — ambiguous`) |
| 4 | OCR / extraction produced a readable total amount | `total amount unreadable` |

Key strictness rules:

- Gate #2 matches **only on bill-to / customer**, never on the deliver-to block — otherwise a personal receipt happening to ship to a station would pass. Incomplete legal names (e.g., invoice bill-to reads just "Evergreen") fail this gate even if "Evergreen" appears inside a listed full name.
- Gate #3 matches **only on the deliver-to / ship-to block**. If the invoice has no deliver-to block, use the bill-to block as the fallback source for station identification — but gate #2 must still pass first.
- If a vendor can't or won't issue invoices with the complete legal name, the invoice should go back to the vendor, not through this skill.

Only files that pass 1–4 proceed to vendor matching and project-code inference (§6).

## 5. Output — Autocount AP Invoice `.xls`

Format: **legacy `.xls`** matching the Autocount template (`Import-AP-Invoice.xls`). Use Python `xlwt` (`pip install xlwt` if missing) or Excel COM automation on Windows. Never emit `.xlsx` for the import file — Autocount's template is `.xls` and the user has standardised on that.

Single sheet named `AP Invoice`. The first column is a label marker (leave blank on data rows). Data columns, in order:

**Master columns** (filled on the first detail row of each invoice; blank on subsequent detail rows):

| # | Field              | Default / Source                                         |
|---|--------------------|----------------------------------------------------------|
| 2 | `DocNo`            | `<<New>>`                                                |
| 3 | `DocDate`          | Invoice date, formatted `dd/MM/yyyy`                     |
| 4 | `CreditorCode`     | From vendor master                                       |
| 5 | `SupplierInvoiceNo`| Invoice number on the document                           |
| 6 | `JournalType`      | `PURCHASE`                                               |
| 7 | `DisplayTerm`      | `C.O.D.` unless vendor master says otherwise             |
| 8 | `PurchaseAgent`    | Blank                                                    |
| 9 | `Description`      | `PURCHASES`                                              |
|10 | `CurrencyRate`     | `1.0` (MYR)                                              |
|11 | `RefNo2`           | Blank                                                    |
|12 | `Note`             | Blank                                                    |
|13 | `InclusiveTax`     | `F`                                                      |

**Detail columns** (one row per line item, or one row per invoice if not split):

| #  | Field               | Source                                                          |
|----|---------------------|-----------------------------------------------------------------|
| 14 | `AccNo`             | Vendor's `DefaultAccNo` unless line item clearly maps elsewhere |
| 15 | `ToAccountRate`     | `1.0`                                                           |
| 16 | `DetailDescription` | Line item description (or invoice `Description` if single line) |
| 17 | `ProjNo`            | Inferred — see §6                                               |
| 18 | `DeptNo`            | Blank                                                           |
| 19 | `TaxType`           | Vendor's `DefaultTaxType` if set, else blank                    |
| 20 | `TaxableAmt`        | Taxable portion (blank if no tax)                               |
| 21 | `TaxAdjustment`     | Blank                                                           |
| 22 | `Amount`            | Line amount (inclusive of tax since `InclusiveTax=F` means lines are exclusive; use the invoice's own breakdown) |

### 5.1 Delta-run file naming

Each run produces a **new** `.xls` containing only invoices newly added this run (never previously exported). Filename:

```
<AP-output-root>/<YYYY>/<YYYY-MM>/AP-Import-<YYYY-MM>-Run_<YYYYMMDD>_<hh>_<mm>.xls
```

Past runs' `.xls` files are preserved for audit. If zero new invoices, **do not** create an empty file — report "nothing new" in chat and exit.

### 5.2 Version stamp inside the `.xls`

Add a second sheet named `About` with three rows:

```
skill        | ap-invoice
version      | <from this SKILL.md's frontmatter>
amended      | <from this SKILL.md's frontmatter>
generated    | <YYYY-MM-DD hh:mm at run time>
run_count    | <how many invoices in this file>
```

The staff then knows which skill revision produced the import.

## 6. Project code (`ProjNo`) — inference rules

Read the invoice end-to-end and assign `ProjNo` per line item where possible; otherwise one `ProjNo` per invoice.

**Station (TK/BS/BL)** — already determined by §4.1 gate #3 (deliver-to block match against `STATION <CODE>:` entries). Reuse that result here; do **not** re-infer. If the invoice reached §6 without a station, treat as a bug and fail the run.

**Segment (Fuel / Mart / iBing / Rental)** — determine from line-item nature:
- Fuel-related goods (RON95, RON97, diesel, fuel nozzles, pump maintenance, CFP-related) → `-Fuel`
- FMCG / groceries / convenience-store stock → `-Mart`
- iBing-branded equipment, content, or services (TK only) → `-iBing`
- Rent, lease, tenancy, utilities tied to the rental space (BS / BL only) → `-Rental`

If one invoice spans segments (e.g., a general supplier bill with both mart and fuel items), **split by line item** into multiple detail rows, each with its own `ProjNo` and `Amount`. Master row stays on the first detail row only.

If segment is unclear for a line and the invoice is otherwise valid, keep the invoice but flag the line in `unresolved/` (§7) for user review, and skip it from the `.xls` until resolved.

## 7. Dedup, unresolved, and manifest

### 7.1 `ap-state.json` — source of truth

Lives in the AP-output root. Tracks every processed invoice so incremental runs never double-count. Schema (JSON):

```jsonc
{
  "version": 1,
  "monthly_running_no": { "2026-04": 12, "2026-03": 48 },
  "invoices": [
    {
      "content_hash": "sha256:…",          // hash of the original file bytes
      "extracted": {                        // normalised extracted fields
        "issuer": "Shell Malaysia",
        "invoice_no": "INV12345",
        "invoice_date": "2026-04-22",
        "amount": 350.50
      },
      "running_no": 12,
      "renamed_path": ".../processed/[012_04] - [20260422] - [Shell Malaysia] - [INV12345] - [RM0350.50].pdf",
      "exported_in": "AP-Import-2026-04-Run_20260423_21_22.xls",
      "project_no": "TK-Fuel",
      "added_at": "2026-04-23T21:22"
    }
  ]
}
```

### 7.2 Dedup order (strict)

For every new file in the AP-input root:

1. **Exact match**: compare `content_hash` against manifest. Hit → skip, do not re-add.
2. **Content match**: if hash is new, extract fields, then normalise (trim, uppercase, strip punctuation from issuer and invoice_no) and compare against each manifest entry. Match on `(issuer, invoice_no)` → this is a re-upload of an existing invoice. Skip and log to chat summary as "duplicate of <existing>".
3. **Near-match warning**: same `(issuer, amount, invoice_date)` but different `invoice_no` → flag for user confirmation before including, don't auto-merge.

### 7.3 Unresolved folder

Create `<AP-input root>/unresolved/<YYYY-MM-DD>/` during the run. Move any file there when any of the following applies:

- Fails a validity / ownership check in §4.1 (`not an invoice`, `not addressed to an Evergreen entity`, `delivery address does not identify TK/BS/BL`, `total amount unreadable`).
- Unsupported file type (non-PDF/JPG/JPEG/PNG).
- Vendor not in `vendor-master.xlsx` (no `CreditorCode` available).
- Segment (Fuel / Mart / iBing / Rental) cannot be determined and the invoice is not line-splittable.
- Near-match flagged in §7.2 step 3.

**Every unresolved file is renamed** with a leading `UNRESOLVED` token so it is obvious at a glance:

```
UNRESOLVED - <original-filename-without-extension>.<ext>
```

If extraction produced enough structured fields to be worth capturing (date + issuer + invoice number + amount all present), instead use the richer form:

```
UNRESOLVED - [<YYYYMMDD>] - [<Issuer>] - [<InvoiceNo>] - [RM<AMOUNT>].<ext>
```

Never assign a monthly running number to an unresolved file — the number series is reserved for invoices that successfully export to Autocount.

Alongside each unresolved file, write a sibling `.txt` note (same base name + `.txt`) containing the **reason** and any partial fields that were extracted, so the user can triage without opening the invoice.

## 8. Rename rule (for successfully processed invoices only)

After an invoice is extracted, deduped, and exported, move the original file to `<AP-input root>/processed/` and rename to:

```
[<XXX>_<MM>] - [<YYYYMMDD>] - [<Issuer>] - [<InvoiceNo>] - [RM<AMOUNT>].<ext>
```

Where:

- `<XXX>` — monthly running number, zero-padded to 3 digits. Increments within the invoice's **invoice-date month**, read from `monthly_running_no` in the manifest. First invoice of the month = `001`.
- `<MM>` — two-digit month of the invoice date.
- `<YYYYMMDD>` — invoice date.
- `<Issuer>` — vendor name sanitised for filesystem: replace any of `<>:"/\|?*` with `-`, collapse repeated spaces, and trim to 40 chars. Trailing punctuation removed.
- `<InvoiceNo>` — invoice number, same sanitation as issuer, trimmed to 30 chars.
- `<AMOUNT>` — invoice total, formatted as `0000.00` (four integer digits, two decimals; pad with leading zeros). For invoices ≥ RM10,000 the integer portion widens naturally (e.g., `12345.67`) — do not truncate.
- `<ext>` — original file extension (`.pdf`, `.jpg`, etc.), lowercase.

Example: `[012_04] - [20260422] - [Shell Malaysia] - [INV12345] - [RM0350.50].pdf`

Note: the user's original spec used `/` between XXX and MM, but `/` is illegal in Windows filenames; `_` is used as the agreed substitute.

## 9. Workflow

1. Recall or ask for the three paths in §2. Verify **both** reference files exist in the AP-static folder (§3.1 `vendor-master.xlsx` and §3.2 `company-entities.txt`). If either is missing, stop and tell the user which one.
2. Load `ap-state.json` (or create an empty one).
3. Scan the AP-input root top level (ignore `processed/` and `unresolved/`). For each candidate file: run §4.1 validity + ownership checks first; if any fail, route to `unresolved/` with the reason. Then run the dedup order in §7.2 on the files that passed.
4. For each genuinely new file: extract fields, match vendor in master, infer station + segment per §6, assign running number per §8.
5. Build the delta `.xls` per §5 with only the new invoices. Include the `About` sheet per §5.2.
6. Save the `.xls` to the date-partitioned output path in §5.1.
7. Rename and move processed originals into `processed/` per §8. Rename unresolved originals with the `UNRESOLVED` prefix per §7.3 and move them into `unresolved/<YYYY-MM-DD>/` alongside their `.txt` reason notes.
8. Update `ap-state.json` with the new entries.
9. Reply in chat:
   - absolute path to the `.xls`,
   - count of new invoices exported,
   - count of duplicates skipped (with their filenames),
   - count and list of unresolved files with reasons,
   - any near-match warnings awaiting confirmation.

If nothing new was found: do not write an `.xls`, just report that in chat.

## 10. Non-negotiables

- Never invent a `CreditorCode`, `AccNo`, `ProjNo`, or station. If the mapping or inference is not confident, the invoice goes to `unresolved/`.
- Never modify or delete files in `processed/` or `unresolved/` from prior runs.
- Never regenerate an old run's `.xls`; each run's file is immutable for audit.
- Never overwrite `ap-state.json` without first loading the existing content and merging — append only.
