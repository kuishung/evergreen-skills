---
name: cfp-entry
description: Use this skill when the user (Evergreen petrol-station back-office) wants to convert daily Customer Fuel Pre-paid (CFP) voucher-redemption reports from any of the three Buraqoil stations — TK (Tg Kapor), BS (Berkat Setia), BL (Bubul Lama) — into an AutoCount Sales Invoice import xlsx ready for upload. Triggers include "compile CFP", "process voucher redemption", "make AutoCount import for today's vouchers", "CFP entry", "import CFP", or any task that takes one or more CFP / gvLedger PDFs or the unified gvLedger.xlsx and produces a sales-import file. The skill produces ONE Sales Invoice per unique (date, customer, station, product) and looks up the AutoCount 300-XXXX debtor code, the per-station fuel ItemCode, and the per-station ProjectNo from internal master files, then writes the result back into the user's own AutoCount Sales template column layout.
version: 0.7.0
updated: 2026-05-11
---

# CFP Entry Skill

**Version:** 0.7.0
**Last updated:** 2026-05-11
**Owner:** Evergreen back-office (KS)

## What this skill does

Given one or more daily voucher-redemption source files — either the
legacy per-station PDFs (TK CFP REPORT, gvLedger BS, gvLedger BL) **or**
the unified `gvLedger.xlsx` (v0.7.0+), which covers all three stations
in a single sheet — the skill:

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
  requirements.txt       <- pip dependencies (v0.7.0+, for Cowork / fresh envs)
  customer_codes.csv     <- AutoCount debtor master (300-XXXX code, name, voucher tag)
  stock_codes.csv        <- per-station fuel ItemCode (FUEL group, 6 codes)
  project_codes.csv      <- per-station ProjectNo (TK-FUEL / BS-FUEL / BL-FUEL)
  reference_prices.csv   <- per-station per-fuel RM/L for Qty derivation
                            (used for any row whose source litre is missing
                            or zero — see "Source formats" below)
  compile_cfp.py         <- the parser/compiler script
```

## Source formats (v0.7.0)

The skill accepts two formats; the dispatcher picks one per file by
extension.

| Format | Coverage | Litre column | Total row | Typical usage |
|---|---|---|---|---|
| `.pdf` (TK CFP REPORT) | TK only | none | `Total:` footer | legacy per-station flow |
| `.pdf` (gvLedger BS) | BS only | none | `Total:` footer | legacy per-station flow |
| `.pdf` (gvLedger BL) | BL only | yes | `Total:` footer | legacy per-station flow |
| **`.xlsx` (gvLedger)** | **all three** | yes (some rows blank/zero) | last data row carries `Total: <amount>` in a single cell | **v0.7.0+ recommended** |

The xlsx is the unified gvLedger export — one file per day covering all
three stations. Columns: `Company | Type | Amount | Gas | Litre |
Vehicle | Station | Voucher | Redeem Date | Receipt`. Sign convention:
Amount always negative (debit from voucher balance); Litre may be
positive, negative, or zero — the parser `abs()`-es and treats zero as
"missing".

**Per-row Litre fallback (v0.7.0).** Any row whose source Litre is blank
or zero gets `litre = amount / RefPrice` filled in by
`derive_missing_litres()`, with `litre_estimated=True` on the row. The
Description column shows `(N vch, K est)` when 0 < K < N (mixed
bucket — xlsx-only case), `(N vch est)` when K == N (full fallback,
e.g. TK PDF), and just `(N vch)` when no estimation happened. The
FurtherDescription voucher line shows `RM <amount>` for estimated
rows (verbatim from source) and `<litre>L` only when the litre came
from the source. Reconciliation Check C exempts estimated rows
(`unit_price_per_row` returns None for them, so the comparison is
skipped naturally).

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

### Qty / UOM / UnitPrice rules (v0.7.0)
- **UOM** -- always `LITER`.
- **Qty** -- after `derive_missing_litres()` runs, every redemption has
  a numeric litre. The bucket's Qty is `round(sum(r.litre), 2)`.
  Source-truth litres come from the file's Litre column when present
  and non-zero (BL gvLedger PDF, xlsx rows with Litre>0); RefPrice-
  derived litres come from `reference_prices.csv[(station, gas)]` for
  rows where the source litre was missing or zero (TK / BS PDFs, xlsx
  blank-litre rows). For a TK PDF bucket the per-row math is
  numerically identical to the v0.6.6 bucket-level fallback.
- **UnitPrice** (v0.6.4 RULE) -- taken **directly** from a source
  row's `round(amount / litre, 2)`. **NEVER** a weighted average.
  The CFP system is automatically generated, so per-row
  `amount / litre` is deterministically uniform within one
  (date, customer, station, fuel) bucket -- if it isn't, the source
  data is corrupt, not legitimately mixed.
  Implementation: bucket UnitPrice = the **first** source row's
  `round(amount/litre, 2)` (first = source-PDF iteration order,
  deterministic). Reconciliation Check C then verifies every other
  source row in the bucket matches that value within RM 0.01.
  Any disagreement FAILs the run -- the operator must investigate the
  source data; a "mid-day price change" justification is NOT
  accepted because the system can't legitimately produce one within
  a single bucket.
  RefPrice-fallback path (no source litres, TK / BS PDFs):
  UnitPrice = the RefPrice rounded to 2 dp.
- **Subtotal** -- always the source-truth amount (sum of source
  redemption amounts), so it ties back to the per-PDF `Total:` footer
  line. Reconciliation Check A (see Verification section below)
  enforces this on every run. Note that with UnitPrice at 2 dp,
  `Qty * UnitPrice` will routinely differ from Subtotal by a fraction
  of a ringgit -- AutoCount uses the explicit Subtotal column on
  import, and pipeline conservation (Check B) is what guarantees
  no money is lost in aggregate.

## Verification / Reconciliation (locked in v0.6.1)

Every run produces a **Reconciliation report** -- printed to the console,
written to a `Reconciliation` sheet in the output xlsx, and used as the
script's exit code. Three checks run on every invocation, with a
RM 0.01 tolerance:

| # | Check | What it proves | Fails when |
|---|---|---|---|
| **A** | Per-PDF `Total:` line ↔ sum of parsed redemption rows from that PDF | The parser didn't silently drop a row | Source PDF Total line doesn't match the sum the parser saw. SKIP if the PDF has no Total: footer (the script prints the parser sum so the operator can sanity-check it manually). |
| **B** | Σ filtered redemptions ↔ Σ consolidated rows + Σ unmapped rows | The consolidator + customer matcher together didn't lose money | Anything was silently dropped between filtering and the output buckets. |
| **C** | Per source row with a litre value: \|round(amount/litre, 2) − bucket.UnitPrice\| ≤ 0.01 | The v0.6.4 UnitPrice rule actually held — every source row's per-row unit price matches the bucket's chosen UnitPrice (= first source row's value, never a weighted average) | Two source rows in the same (date, customer, station, fuel) bucket disagree on per-row unit price by more than 1 cent. Treat as **corrupt source data** — the CFP system is auto-generated and cannot legitimately produce mixed prices within one bucket. RefPrice-fallback buckets (TK / BS PDFs with no litres) are exempt and counted as "skipped" in the OK note. |

**Exit semantics:**
- All checks `OK` (or `OK` + `SKIP`) → exit code `0`. Safe to import.
- Any check `FAIL` → exit code `2`. The xlsx is still written (so you
  can inspect the `Reconciliation` sheet), but the script prints
  `DO NOT IMPORT` and a non-zero exit signals automated callers.

**Operator rule:** never import the xlsx into AutoCount until every
reconciliation check is `OK` or `SKIP`. Claude must surface the
reconciliation block to the user before saying the run succeeded.

### Total-row handling (locked in v0.6.2)

**Source side.** Every source carries a system-generated Total at the
end of the data. The skill captures it for Check A and excludes it
from the redemption list:

| Source format | Where Total lives | How it's captured |
|---|---|---|
| TK CFP REPORT (PDF) | `Total:` footer line | `TOTAL_LINE_RX` in the parser; last-seen value wins |
| BS / BL gvLedger (PDF) | `Total:` / `Grand Total:` footer | same as above |
| xlsx source (future) | last data row, marked with `Total` / `Grand Total` in the first non-empty cell | xlsx parser will read the value, then drop the row before it enters `List[Redemption]` |

The Total is **only** used as the control number for Check A. It
never becomes a transaction.

**Output side (locked rule, NON-NEGOTIABLE).** The xlsx that goes to
AutoCount must contain **only header (row 1) + transaction rows** in
both the Master and Detail sheets. **No Total row, anywhere.**
AutoCount computes its own totals on import — a Total row in the
import would be treated as an extra transaction and double the day's
revenue.

The script enforces this at write time via `_assert_no_total_row()`,
which scans both sheets and raises `RuntimeError` if any row's first
non-empty cell is `Total` / `Grand Total` / `Subtotal` (case-insensitive,
trailing colon tolerated). The Audit / Unmapped / Reconciliation helper
sheets are unaffected — AutoCount only reads Master + Detail by sheet
position, so totals or notes inside those helper sheets cannot leak
into the import.

### History of the consolidation rule
- v0.1: 1 invoice per (date, debtor); all stations and fuels merged.
- v0.2: 1 invoice per (date, debtor); detail split per station + fuel.
- v0.3: 1 invoice per (date, debtor, station, fuel) --
  matches "per customer per station per product daily invoicing".
- v0.4: same grouping as v0.3 + voucher list appended to the
  import Description.
- v0.5: + `DebtorName` on master; all six required fields populated.
- v0.5.1: project codes locked (TK-FUEL / BS-FUEL / BL-FUEL).
- v0.6: voucher list removed from Description (80-char cap); UOM always
  `LITER`; Qty derived from `reference_prices.csv` when the source PDF
  carries no litre column.
- **v0.7 (current): xlsx source format supported -- unified
  `gvLedger.xlsx` covering all three stations in one file. Per-row
  Litre fallback (mixed buckets handled). `requirements.txt` shipped.
  PDF support retained (lazy `pdfplumber` import).**

### FurtherDescription format (locked in v0.6.6)

The audit trail that previously lived only in the `Audit` helper sheet
now also rides into AutoCount via `FurtherDescription`, formatted as:

```
YYYY-MM-DD:
<voucher> - <fuel> (<qty>)
<voucher> - <fuel> (<qty>)
...
```

Per voucher line, `<qty>` is taken **verbatim** from the source -- no
derivation:

| Source format | Has litre column? | `<qty>` shown |
|---|---|---|
| BL gvLedger | yes | `25.19L` |
| TK CFP REPORT | no | `RM 100.00` |
| BS gvLedger | no | `RM 100.00` |

Vouchers within each date are sorted by redemption datetime so the
trail reads chronologically.

**Multi-day source files.** When the source spans multiple days
(e.g., Mon + Tue + Wed redemptions in one batch), the v0.3.0
consolidation rule produces **separate Sales Invoices for each day**,
not one mega-invoice spanning the days. A customer who fills Petrol at
BL on Mon AND Tue therefore gets two invoices: `CFP-YYYYMMDD-NNNN` for
Monday and `CFP-YYYYMMDD-NNNN` for Tuesday, each carrying its own
single-date FurtherDescription. So under v0.3.0 every
FurtherDescription has exactly one `YYYY-MM-DD:` heading.

The format renderer is written defensively to handle multi-date
buckets too (separating each date with a blank line), so if the
consolidation rule is ever relaxed -- e.g., to (customer, station)
or (customer, station, fuel) -- the FurtherDescription text will
adapt automatically without code changes.

Cap is 500 chars. If a bucket has so many vouchers that the
formatted text exceeds 500, the trailing portion is truncated with
`...`. The full untruncated trail still lives in the `Audit` helper
sheet for reference.

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
| Detail | Description   | `<Gas> @ <Station> (<n> vch[ est][ , <k> est])`, ≤ 80 chars — see v0.7.0 mixed-bucket form |
| Detail | **FurtherDescription** | Date-grouped voucher trail (v0.6.6 format) — see "FurtherDescription format" below; ≤ 500 chars (truncated with `...` if exceeded) |
| Detail | **UOM**       | always `LITER` (v0.6.0+)                     |
| Detail | **Qty**       | sum of source litres, or `1` if no litre data|
| Detail | **UnitPrice** | First source row's `round(amount/litre, 2)` — never a weighted average (v0.6.4 rule); RefPrice fallback rounded 2 dp |
| Detail | Subtotal      | sum of source amounts (positive)             |
| Detail | **ProjectNo** | `project_codes.csv[station]` (blank for now) |

The script tolerates missing columns in the user's actual template
-- it only writes a value if a matching column header is found. So
if `Default Sales.xlsx` lacks `DebtorName`, the value is dropped
silently rather than breaking the import.

## How Claude should run it

When the user asks to "compile CFP", "process voucher redemption",
"make AutoCount import for [date]", or similar:

1. **Confirm scope** -- which date, which source file(s). The v0.7.0+
   default is a single unified `gvLedger.xlsx` for the day. The
   legacy three-PDF flow still works; pass any mix of PDFs and / or
   xlsx files to `--reports`.
2. **Install dependencies** (Cowork / fresh env / first run on a box):
   ```
   pip install -r requirements.txt
   ```
   For an xlsx-only run, `pdfplumber` is not strictly needed (it's
   lazy-imported), so `pip install openpyxl rapidfuzz` is enough.
3. **Locate the AutoCount Sales template** -- by default
   `D:\CLAUDE\Skill\CFP Entry\Autocount Import Template\Default Sales.xlsx`.
4. **Stock + project codes are locked** (v0.2.0 / v0.5.1) -- the script
   picks per-station codes automatically from `stock_codes.csv` and
   `project_codes.csv`. Deprecated CLI flags `--petrol-code` /
   `--diesel-code` are silently ignored.
5. **Run the script:**
   ```
   python compile_cfp.py \
     --reports "<path-to-source>.xlsx" \
     --date YYYY-MM-DD \
     --template "D:/CLAUDE/Skill/CFP Entry/Autocount Import Template/Default Sales.xlsx" \
     --customers "<skill>/customer_codes.csv" \
     --stock-codes "<skill>/stock_codes.csv" \
     --project-codes "<skill>/project_codes.csv" \
     --reference-prices "<skill>/reference_prices.csv" \
     --out "<output>/SalesImport_YYYY-MM-DD.xlsx"
   ```
   For the legacy three-PDF flow, just pass all the PDFs to `--reports`
   instead of one xlsx.
6. **Review console output** -- the script prints, for each source file:
   rows parsed, parsed sum, source `Total:` value, and per-file `[OK]` /
   `[MISMATCH]` marker. v0.7.0 adds a line counting any rows whose
   Litre was derived via RefPrice. Then a `=== Reconciliation ===`
   block with the three checks (A / B / C) defined in the
   **Verification / Reconciliation** section above.
7. **Surface findings to the user**:
   - Any unmapped companies (decide: add to `customer_codes.csv`, or
     treat as one-off cash sale).
   - The reconciliation summary (`N FAIL, N OK, N SKIP`).
   - The estimated-litre count (v0.7.0) if non-zero -- so the operator
     knows how much of the day's Qty was derived rather than read.
8. **DO NOT proceed to import** if any reconciliation check is `FAIL`.
   The script's exit code is 2 in that case; investigate, fix, re-run.
9. **Hand the file to the user** with a `computer://` link only after
   reconciliation is clean.

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

  parsed   8 rows  parsed_total=    XXXX.XX  source_total=    XXXX.XX  delta=+0.00 [OK]   <- 20260501-CFP REPORT-TK.pdf
  parsed   5 rows  parsed_total=     XXX.XX  source_total=     XXX.XX  delta=+0.00 [OK]   <- gvLedger - 2026-05-01T143652.120.pdf
  parsed  14 rows  parsed_total=    XXXX.XX  source_total=    XXXX.XX  delta=+0.00 [OK]   <- gvLedger - BL.pdf

Filtered to 2026-05-01: 27 rows

Consolidated 16 customer-station-fuel rows; 1 unmapped row.
Unmapped companies (add to customer_codes.csv):
   - SINKHONG TRANSPORT  (Diesel, 81.40)

=== Reconciliation ============================================
  [OK  ] A. 20260501-CFP REPORT-TK.pdf: PDF Total vs parsed sum
  [OK  ] A. gvLedger - 2026-05-01T143652.120.pdf: PDF Total vs parsed sum
  [OK  ] A. gvLedger - BL.pdf: PDF Total vs parsed sum
  [OK  ] B. Conservation: filtered = consolidated + unmapped
  [OK  ] C. Per-row UnitPrice uniformity: amount/litre matches bucket UnitPrice

  0 FAIL, 5 OK, 0 SKIP
================================================================

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
