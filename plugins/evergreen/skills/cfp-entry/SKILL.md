---
name: cfp-entry
description: Use this skill when the user (Evergreen petrol-station back-office) wants to convert daily Customer Fuel Pre-paid (CFP) voucher-redemption reports from any of the three Buraqoil stations — TK (Tg Kapor), BS (Berkat Setia), BL (Bubul Lama) — into an AutoCount Sales Invoice import xlsx ready for upload. Triggers include "compile CFP", "process voucher redemption", "make AutoCount import for today's vouchers", "CFP entry", "import CFP", or any task that takes one or more CFP / gvLedger PDFs and produces a sales-import file. The skill produces ONE Sales Invoice per unique (date, customer, station, product) and looks up the AutoCount 300-XXXX debtor code, the per-station fuel ItemCode, and the per-station ProjectNo from internal master files, then writes the result back into the user's own AutoCount Sales template column layout.
version: 0.6.0
updated: 2026-05-08
---

# CFP Entry Skill

**Version:** 0.6.0
**Last updated:** 2026-05-08
**Owner:** Evergreen back-office (KS)

## What this skill does

Given one or more daily voucher-redemption PDFs (TK CFP REPORT,
gvLedger BS, gvLedger BL), the skill:

1. Parses every redemption line (company, fuel type, amount, litre,
   vehicle, station, voucher code, redeem datetime, receipt no.)
2. Matches each company to its AutoCount debtor account code
   (`300-XXXX`) via the master list saved in `customer_codes.csv`.
3. **Consolidates** all redemptions for the same customer on the same
   day so AutoCount receives **one Sales Invoice header per customer per
   day**, with **one detail line per fuel type** (Petrol, Diesel) --
   never one line per voucher.
4. Writes a new xlsx that re-uses the column layout of
   `Default Sales.xlsx` (the user's own AutoCount template) and adds two
   helper sheets: `Audit` (every consolidated row with voucher trail)
   and `Unmapped` (any company name from the daily report that the
   master list doesn't recognise -- so you can fix and re-run).

## Files in this skill

```
cfp-entry/
  SKILL.md               <- you are here
  CHANGELOG.md           <- version history
  VERSION                <- single-line current version
  customer_codes.csv     <- AutoCount debtor master (300-XXXX code, name, voucher tag)
  stock_codes.csv        <- per-station fuel ItemCode (FUEL group, 6 codes)
  project_codes.csv      <- per-station ProjectNo (TK-FUEL / BS-FUEL / BL-FUEL)
  reference_prices.csv   <- per-station per-fuel RM/L for Qty derivation when
                            source PDF has no litre column (TK/BS reports)
  compile_cfp.py         <- the parser/compiler script
```

## AutoCount item / stock codes (locked in v0.2.0)

Per the **Item Listing** dated 2026-05-08, the FUEL group has six items
-- one per station x fuel type. The skill picks the code based on which
station the redemption was at:

| Station | Petrol code  | Diesel code |
|---------|--------------|-------------|
| TK (Tg Kapor)   | `PETROL - TK` | `DIESEL -TK` |
| BS (Berkat Setia) | `PETROL -BS`  | `DIESEL- BS` |
| BL (Bubul Lama)   | `PETROL - BL` | `DIESEL- BL` |

These are stored in `stock_codes.csv` and embedded in
`compile_cfp.py` (`STATION_FUEL_TO_ITEM_CODE`). Note the irregular
spacing in the AutoCount master (e.g. `DIESEL- BL` vs `DIESEL -TK`)
-- the skill uses the strings **verbatim** so AutoCount matches them.

## AutoCount project codes (locked in v0.5.1)

| Station | ProjectNo |
|---------|-----------|
| TK (Tg Kapor)     | `TK-FUEL` |
| BS (Berkat Setia) | `BS-FUEL` |
| BL (Bubul Lama)   | `BL-FUEL` |

Stored in `project_codes.csv`. The compiler writes the matching
project code into AutoCount's `ProjectNo` column on every detail
row based on the source station of the redemption.

## Consolidation rule (UPDATED in v0.3.0)

**Each unique `(doc_date, debtor_code, station, gas_type)` is its
own Sales Invoice.** Header and detail are 1-to-1.

So PULAU SIPADAN's seven 2026-05-01 vouchers (5 at TK Petrol + 2 at
BL Petrol) now produce **two separate invoices**:

| DocNo | DocDate | DebtorCode | ItemCode    | Qty (L) | Subtotal | ProjectNo |
|---|---|---|---|---|---|---|
| CFP-20260501-0009 | 2026-05-01 | 300-P011 | `PETROL - TK` |        | 5,637.40 | TK |
| CFP-20260501-0010 | 2026-05-01 | 300-P011 | `PETROL - BL` | 980.00 | 3,890.60 | BL |

HAZAFIRAH HASSNAR (BS Petrol + BS Diesel on the same day) likewise
gets two invoices -- one per product.

DocNo numbering is sequential by `(date, debtor, station, fuel)`,
same `CFP-YYYYMMDD-NNNN` pattern as before.

**Voucher trail:** every voucher code that rolls up into the line
is listed in the Audit sheet's `Vouchers` column for traceability.
The Description column does NOT include vouchers (AutoCount caps it
at 80 chars).

### Description format (v0.6.0)
```
<Gas> @ <Station> (<n> vch[ est])
```
Suffix `est` is added when Qty was derived from `reference_prices.csv`
(i.e. the source PDF didn't carry litres).
Examples:
```
Petrol @ Buraqoil Bubul Lama (2 vch)
Petrol @ Buraqoil Tg Kapor (5 vch est)
```
All under 80 chars.

### Qty / UOM / UnitPrice rules (v0.6.0)
- **UOM** -- always `LITER`.
- **Qty** -- if the source PDF has a litre column for the row
  (BL `gvLedger` does), sum those litres. If not (TK CFP REPORT,
  BS gvLedger), derive `Qty = round(Subtotal / refprice, 2)` using
  `reference_prices.csv[(station, gas)]`.
- **UnitPrice** -- `Subtotal / Qty`, rounded to 4 dp. If source
  litres were used and the price stays uniform across vouchers,
  this matches the reference price exactly.
- **Subtotal** -- always the source-truth amount (sum of source
  redemption amounts), so it ties to the bank deposit.

### History of the consolidation rule
- v0.1: 1 invoice per (date, debtor); all stations and fuels merged.
- v0.2: 1 invoice per (date, debtor); detail split per station + fuel.
- v0.3: 1 invoice per (date, debtor, station, fuel) --
  matches "per customer per station per product daily invoicing".
- v0.4: same grouping as v0.3 + voucher list appended to the
  import Description.
- v0.5: + `DebtorName` on master; all six required fields populated.
- v0.5.1: project codes locked (TK-FUEL / BS-FUEL / BL-FUEL).
- **v0.6 (current): voucher list removed from Description (80-char
  cap); UOM always `LITER`; Qty derived from `reference_prices.csv`
  when the source PDF carries no litre column. Output: CSV only
  (xlsx generation requires the Linux Python sandbox).**

### Required AutoCount columns (locked in v0.5.0)

| Sheet  | Column        | Source                                       |
|--------|---------------|----------------------------------------------|
| Master | DocNo         | `CFP-YYYYMMDD-NNNN`                          |
| Master | DocDate       | redemption date                              |
| Master | DebtorCode    | `customer_codes.csv` (300-XXXX)              |
| Master | **DebtorName**| `customer_codes.csv.company_name`            |
| Master | Description   | `CFP <Gas> @ <Station> <Date>`               |
| Master | CurrencyCode  | `RM`                                         |
| Master | ExchangeRate  | `1`                                          |
| Detail | DocNo         | links to master                              |
| Detail | **ItemCode**  | `stock_codes.csv[(station, gas)]`            |
| Detail | Description   | `<Gas> @ <Station> (<n> vch) | Vouchers: ...`|
| Detail | **UOM**       | `Litre` if litre data present, else `Unit`   |
| Detail | **Qty**       | sum of source litres, or `1` if no litre data|
| Detail | **UnitPrice** | `Subtotal / Qty`                             |
| Detail | Subtotal      | sum of source amounts (positive)             |
| Detail | **ProjectNo** | `project_codes.csv[station]` (blank for now) |

The script tolerates missing columns in the user's actual template
-- it only writes a value if a matching column header is found. So
if `Default Sales.xlsx` lacks `DebtorName`, the value is dropped
silently rather than breaking the import.

## How Claude should run it

When the user asks to "compile CFP", "process voucher redemption",
"make AutoCount import for [date]", or similar:

1. **Confirm scope** -- which date, which station(s), where the daily
   PDFs are. If multiple PDFs cover the same day, all three may be
   passed in together; the script merges them into one combined import
   file.
2. **Locate the AutoCount Sales template** -- by default
   `D:\CLAUDE\Skill\CFP Entry\Autocount Import Template\Default Sales.xlsx`.
3. **Stock codes are now locked** -- v0.2.0 picks per-station codes
   automatically from `stock_codes.csv`. CLI flags `--petrol-code` /
   `--diesel-code` are deprecated and ignored.
4. **Project codes** -- if `project_codes.csv` has values, the script
   fills the AutoCount `ProjectNo` column. Until v0.3.0 these are
   blank.
5. **Run the script:**
   ```
   python compile_cfp.py \
     --reports "<path-to-pdf-1>" "<path-to-pdf-2>" ... \
     --date YYYY-MM-DD \
     --template "D:/CLAUDE/Skill/CFP Entry/Autocount Import Template/Default Sales.xlsx" \
     --customers "D:/CLAUDE/Skill/CFP Entry/cfp-entry/customer_codes.csv" \
     --stock-codes "D:/CLAUDE/Skill/CFP Entry/cfp-entry/stock_codes.csv" \
     --project-codes "D:/CLAUDE/Skill/CFP Entry/cfp-entry/project_codes.csv" \
     --out "D:/CLAUDE/Skill/CFP Entry/output/SalesImport_YYYY-MM-DD.xlsx"
   ```
5. **Review console output** -- the script prints how many rows it
   parsed per PDF, how many consolidated rows it produced, and any
   unmapped companies. Surface unmapped companies to the user so they
   can decide whether to add to `customer_codes.csv` or treat as a
   one-off cash sale.
6. **Hand the file to the user** with a `computer://` link.

## Customer master (`customer_codes.csv`)

Snapshot of the AutoCount Debtor Listing as of **2026-05-07** (Active
filter). 144 debtors. Columns:

| acc_code | company_name | voucher_code | station |
|---|---|---|---|
| 300-P011 | PULAU SIPADAN RESORT & TOURS SDN BHD | TK-V23 | TK |
| 300-T005 | THE BUWAN RESORT SDN BHD | BL-V6 | BL |
| ... | ... | ... | ... |

When a customer is added or renamed in AutoCount, refresh this file:

> Hey Claude, refresh the cfp-entry customer master from this PDF
> [attach new Debtor Listing]

The skill should:
1. Re-extract the table from the PDF
2. Compare with current `customer_codes.csv` -- show the user what's
   added / removed / renamed
3. Bump the skill MINOR version (e.g. 0.1.0 -> 0.2.0) and record the
   change in `CHANGELOG.md`

## Fuzzy matching

CFP report names often differ slightly from AutoCount names:
- AutoCount: `KATATA CONSTRUCTION (SABAH) SDN BHD -(BS-V81)`
- CFP report: `KATATA CONSTRUCTION (SABAH) SDN BHD`

The matcher therefore:
- uppercases & collapses whitespace
- strips trailing voucher tags `(BS-Vxx)`, `- (TK)`
- exact match first, then RapidFuzz token-set ratio with threshold 0.78
- anything below threshold goes into the `Unmapped` sheet and is
  surfaced in the console

## Known unmapped companies seen in samples

From the 2026-05-01 sample PDFs:
- `SINKHONG TRANSPORT` (TK report) -- not in the AutoCount master.
  Either add to AutoCount + this CSV, or treat as a walk-in cash sale.

## Versioning policy

This skill is versioned with [SemVer](https://semver.org/):
- **MAJOR** -- breaking change (e.g. switch from Sales Invoice to Cash Sale,
  change consolidation rule).
- **MINOR** -- new behaviour or new master data (customer additions,
  new station, new fuel type).
- **PATCH** -- bug fixes, parser tweaks, doc edits.

Every change must:
1. Update the `version:` field in this SKILL.md frontmatter.
2. Update the "Last updated" line.
3. Add an entry to `CHANGELOG.md` with the date, version, summary,
   and (if relevant) before/after example.

When the user says "show me the cfp-entry skill version", reply with
the version line from this file plus the latest CHANGELOG entry.

## Open items / TODO

- ~~**Stock codes** for Petrol and Diesel~~ -- DONE in v0.2.0 (six
  per-station codes from FUEL group).
- ~~**Project codes** for TK / BS / BL~~ -- DONE in v0.5.1
  (`TK-FUEL`, `BS-FUEL`, `BL-FUEL`).
- **Tax code**: AutoCount usually wants a tax code per detail line.
  Add the standard code (e.g. `SR`/`ZRL`/empty) once confirmed.
- **DocNo prefix**: currently `CFP-YYYYMMDD-NNNN`. If the user has an
  in-house DocNo convention, change `--doc-prefix`.

## Sample run (v0.2.0 grouping)

```
$ python compile_cfp.py \
    --reports "D:/CLAUDE/Skill/CFP Entry/20260501-CFP REPORT-TK.pdf" \
              "D:/CLAUDE/Skill/CFP Entry/gvLedger - 2026-05-01T143652.120.pdf" \
              "D:/CLAUDE/Skill/CFP Entry/gvLedger - BL.pdf" \
    --date 2026-05-01 \
    --template "D:/CLAUDE/Skill/CFP Entry/Autocount Import Template/Default Sales.xlsx" \
    --customers "D:/CLAUDE/Skill/CFP Entry/cfp-entry/customer_codes.csv" \
    --stock-codes "D:/CLAUDE/Skill/CFP Entry/cfp-entry/stock_codes.csv" \
    --project-codes "D:/CLAUDE/Skill/CFP Entry/cfp-entry/project_codes.csv" \
    --out "D:/CLAUDE/Skill/CFP Entry/output/SalesImport_2026-05-01.xlsx"

  parsed   8 rows  <- 20260501-CFP REPORT-TK.pdf
  parsed   5 rows  <- gvLedger - 2026-05-01T143652.120.pdf
  parsed  14 rows  <- gvLedger - BL.pdf

Filtered to 2026-05-01: 27 rows

Consolidated 16 customer-station-fuel rows; 1 unmapped row.
Unmapped companies (add to customer_codes.csv):
   - SINKHONG TRANSPORT  (Diesel, 81.40)

Wrote import file: D:/CLAUDE/Skill/CFP Entry/output/SalesImport_2026-05-01.xlsx
```

Examples:
- PULAU SIPADAN -- one Sales Invoice header (`CFP-20260501-0009`),
  two detail lines: `PETROL - TK` (5 vouchers, 5,637.40) and
  `PETROL - BL` (2 vouchers, 980 L, 3,890.60).
- SHAZAM CONTRACTOR -- one header, two lines: `DIESEL -TK` (1 vch,
  322.50) + `DIESEL- BL` (1 vch, 150 L, 322.50).
- HAZAFIRAH HASSNAR -- one header, two lines:
  `PETROL -BS` (79.40) + `DIESEL- BS` (43.00).

## Installation

Skill is auto-loaded as part of the **evergreen** plugin
(`plugins/evergreen/skills/cfp-entry/`). Once the plugin marketplace
auto-update fires, Claude Code lists `cfp-entry` in available skills
on every machine that has the evergreen plugin enabled. No manual
folder-copying required.
