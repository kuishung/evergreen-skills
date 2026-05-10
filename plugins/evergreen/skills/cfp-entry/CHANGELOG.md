# cfp-entry — Changelog

All notable changes to this skill are recorded here. The skill follows
[Semantic Versioning](https://semver.org/): MAJOR.MINOR.PATCH.

When you make a change:
1. Bump the version in `SKILL.md` frontmatter (`version:`) and the
   "Last updated" line.
2. Add a new section at the top of this file with the date and a
   bullet list of what changed.
3. If consolidation rules, document type, or import-template
   structure changes, mark it as **BREAKING** and bump MAJOR.

---

## 0.6.6 — 2026-05-10
**FurtherDescription format: date-grouped voucher trail with per-voucher fuel + qty.**

KS request: format FurtherDescription as
```
YYYY-MM-DD:
Voucher 1 - Petrol (Liter)
Voucher 2 - Petrol (Liter)
...
```
plus a confirmation that v0.3.0 ("per customer per station per
product daily invoicing") remains the consolidation rule.

Multi-day source handling: a multi-day source produces multiple
single-day Sales Invoices via the v0.3.0 consolidator -- the
FurtherDescription on each invoice carries only that day's
vouchers. So under v0.3.0 every FurtherDescription has exactly one
`YYYY-MM-DD:` heading. The renderer is written defensively for
multi-date buckets (sections separated by a blank line) so a future
relaxation of the consolidation rule needs no format change.

Behaviour change:
- FurtherDescription is now produced by `_build_further_description()`
  with format:
    YYYY-MM-DD:
    <voucher> - <fuel> (<qty>)
  Vouchers within each date are sorted by redemption datetime;
  date sections separated by `\\n\\n`.
- Per-voucher `<qty>` is taken VERBATIM from the source -- never
  derived:
    BL (litre present): `25.19L`
    TK / BS (no litre column): `RM 100.00`
- Cap raised from 200 -> 500 chars (the new format is more verbose);
  truncation suffix unchanged ("...").

New helpers in compile_cfp.py:
- `_format_voucher_line(r)` -- single voucher's line text.
- `_build_further_description(cr, cap=500)` -- groups by date,
  sorts within each date, applies cap.

Files changed:
- `compile_cfp.py`:
  - Two new private helpers (above).
  - `build_detail_rows()` -- the inline `Vouchers: ...; ...` string
    construction is replaced by `_build_further_description(cr)`.
- `SKILL.md` -- 0.6.5 -> 0.6.6; new "FurtherDescription format
  (locked in v0.6.6)" subsection documents the format,
  multi-day handling, and the multi-date-defensive renderer;
  "Required AutoCount columns" FurtherDescription cell points
  to the new section.
- `VERSION` -- `0.6.5` -> `0.6.6`.

Non-breaking:
- Sales Invoice headers, DocNo numbering, totals, customer mapping,
  ItemCode / ProjectNo, Description, Subtotal, Qty, UnitPrice, UOM,
  Audit / Unmapped / Reconciliation sheets -- ALL unchanged.
- Only the FurtherDescription text format changes.

---

## 0.6.5 — 2026-05-10
**FurtherDescription column populated with voucher trail; header-matching bug fixed.**

KS observation: "in the [template] there is a Description and
FurtherDescription Column".

The AutoCount Detail template carries a separate `FurtherDescription`
field (longer than `Description`'s 80-char cap). v0.6.0 had to drop
the voucher list from the import because `Description` couldn't hold
it -- the trail then lived only in the side `Audit` sheet. With
`FurtherDescription` now wired up, the voucher trail rides into
AutoCount on import.

Behaviour changes:
- New `further_description` field on `DetailRow`. Populated by
  `build_detail_rows()` as `Vouchers: <v1>; <v2>; ...`, capped at
  200 chars (typical AutoCount FurtherDescription column width;
  truncated with `...` if a bucket is unusually voucher-heavy).
- `COLUMN_MAP_DETAIL` gains `further_description` with aliases
  `furtherdescription` / `furtherdesc` / `further description` /
  `further desc`. The Audit sheet still carries the full,
  untruncated voucher list.

Bug fix:
- `_find_headers()` did `any(a in h for a in aliases)` substring
  matching -- so the alias `description` matched a
  `FurtherDescription` header (because `"description"` is a
  substring of `"furtherdescription"`). With both columns in the
  template, the script would have written the voucher list into
  the wrong cell. The matcher now does two passes: exact match
  first (claiming the column), then substring fallback for any
  canonical that didn't find an exact hit. Columns claimed in
  Pass 1 are removed from the Pass 2 pool. Also adds
  space-stripped header normalisation so `Further Description`
  matches `furtherdescription` aliases too.

Files changed:
- `compile_cfp.py`:
  - `_find_headers()` -- two-pass matching with column claiming.
  - `COLUMN_MAP_DETAIL` -- new `further_description` entry.
  - `DetailRow` -- new `further_description` field.
  - `build_detail_rows()` -- builds the `Vouchers: ...` string,
    200-char cap, `...` truncation.
  - `write_import()` -- writes `further_description` into the
    matched column.
- `SKILL.md` -- 0.6.4 → 0.6.5; "Required AutoCount columns" table
  gains a `Detail | FurtherDescription` row; the stale
  `Description | <Gas>...| Vouchers: ...` cell is corrected
  (`Description` is short text, `FurtherDescription` carries
  vouchers).
- `VERSION` -- `0.6.4` → `0.6.5`.

Non-breaking for templates without a FurtherDescription column:
- If the column doesn't exist, `_set` is a no-op. Existing
  templates produce identical output to v0.6.4. The voucher
  trail still lives in the Audit sheet either way.

---

## 0.6.4 — 2026-05-10
**No weighted average. UnitPrice taken directly from a source row.**

KS instruction: "never use weighted-average because the CFP system
is automatically generated and it should match".

The v0.6.3 implementation computed bucket UnitPrice as
`round(Σamount / Σlitre, 2)` -- mathematically a weighted average,
even though it equals every per-row value when the bucket is uniform
(typical case). The v0.6.4 rule rejects the weighted-average
abstraction entirely: the CFP system is deterministic, so per-row
`amount / litre` within one (date, customer, station, fuel) bucket
is guaranteed uniform. If rows disagree, the source is corrupt, not
legitimately mixed.

Behaviour change:
- **Bucket UnitPrice** is now the FIRST source row's
  `round(amount/litre, 2)` (first = source-PDF iteration order,
  deterministic). No averaging of any kind.
- **Check C** unchanged in formula -- compares every per-row
  `round(amount/litre, 2)` to the bucket UnitPrice with RM 0.01
  tolerance -- but the rationale is sharper: a disagreement is now
  flagged as **corrupt source data**, not a "mid-day price change".
  The previous SKILL.md guidance to "split the source data" or
  "accept after review" is removed; the operator must investigate
  the source.

Impact on the v0.6.3 mixed-bucket smoke test:
- Old (v0.6.3, weighted): UnitPrice = 3.99; Check C flagged ALL 3
  rows because the weighted average matched none of them.
- New (v0.6.4, first-row): UnitPrice = 3.97 (first row's price);
  Check C flags only row z (4.05) -- the actual outlier.
  Cleaner diagnosis.

Files changed:
- `compile_cfp.py`:
  - `build_detail_rows()` -- main path now picks the first source
    row's `unit_price_per_row`; explicit comment forbidding
    weighted averages.
  - Reconciliation header comment updated to reflect the
    "no weighted average" rule and the "corrupt data, not price
    change" framing.
- `SKILL.md` -- 0.6.3 → 0.6.4; "Qty / UOM / UnitPrice rules"
  rewritten (UnitPrice rule); Verification table Check C row
  updated; Required AutoCount columns UnitPrice formula updated.
- `VERSION` -- `0.6.3` → `0.6.4`.

Non-breaking for clean data:
- Every well-formed bucket where per-row prices are uniform
  produces an IDENTICAL xlsx to v0.6.3. Only mixed buckets
  diverge -- and they're now correctly framed as corrupt-source
  errors, not legitimate variance.

---

## 0.6.3 — 2026-05-10
**UnitPrice rule changed: per-source-row `amount/litre`, rounded 2 dp.**

KS instruction: "for each individual row of data of the source, the
amount divide by litre will be the unit price and that is to be used
to be inserted unit_price" + "round it to 2 decimal point only".

Behaviour changes:
- **UnitPrice** is now `round(Σamount / Σlitre, 2)` using the
  **unrounded** bucket sums (was: `round(Subtotal / Qty, 4)` using
  the already-rounded values, which introduced sub-cent drift on
  buckets with non-trivial fractional litres). When all source rows
  in a bucket share a uniform pump price -- the typical case -- the
  result equals every per-row `round(amount/litre, 2)` exactly.
- **Qty** unchanged: `round(Σlitre, 2)` when source has litres,
  `round(Σamount / RefPrice, 2)` otherwise.
- **Subtotal** unchanged: `round(Σamount, 2)`, source truth.
- **RefPrice fallback** (TK / BS PDFs with no litre column):
  UnitPrice is now `round(RefPrice, 2)` directly (was: derived
  via Subtotal / Qty). Mathematically the same when uniform but
  free of compounding rounding.

Verification changes:
- **Check C replaced.** The old "Qty * UnitPrice ≈ Subtotal" check
  was meaningful at 4 dp UnitPrice; at 2 dp the rounding error
  scales with Qty and would routinely report ~0.40 RM drift on
  normal buckets. AutoCount uses the explicit Subtotal column on
  import, and Check B (pipeline conservation) already guarantees
  no money is lost in aggregate, so the row-level Qty*UnitPrice
  check no longer adds value.
- **New Check C:** per-row UnitPrice uniformity. For every
  source redemption with a litre value,
  `|round(amount/litre, 2) - bucket.UnitPrice| <= 0.01`. FAIL
  when a (date, customer, station, fuel) bucket contains rows with
  materially different per-row unit prices -- typically a mid-day
  pump-price change inside one bucket, which the operator must
  resolve (split source data, override, or accept after review).
  RefPrice-fallback buckets are exempt and reported in the OK note
  as "skipped".

Files changed:
- `compile_cfp.py`:
  - `Redemption` -- new `unit_price_per_row` property
    (`amount / litre`, 2 dp, None if no litre).
  - `ConsolidatedRow` -- new `source_redemptions` field tracking
    every source row that contributed to the bucket.
  - `consolidate()` -- appends to `source_redemptions`.
  - `build_detail_rows()` -- new UnitPrice formula on both the
    main path and the RefPrice fallback path.
  - `build_reconciliation()` -- old Check C removed; new
    per-row uniformity Check C added.
  - Header comment for the Reconciliation block updated to
    explain the C change and why the old check was retired.
- `SKILL.md` -- 0.6.2 → 0.6.3; "Qty / UOM / UnitPrice rules"
  section rewritten; Verification table Check C row updated;
  "Required AutoCount columns" UnitPrice formula updated;
  sample reconciliation console block updated.
- `VERSION` -- `0.6.2` → `0.6.3`.

Non-breaking for clean data:
- A typical day where every bucket has a uniform per-row unit
  price produces an xlsx with the SAME Subtotal, the SAME Qty,
  and a UnitPrice that is identical to the v0.6.2 value (rounded
  to 2 dp instead of 4 dp).

---

## 0.6.2 — 2026-05-10
**Total-row handling rule locked: source Total feeds Check A, output never carries Total.**

KS instruction: "the source will contain a total row at the last
which is generated from the system, in the output remove the total
because it will be imported into the autocount".

The current PDF parser already discards `Total:` footer lines and the
v0.6.1 reconciliation captures their value for Check A. The current
`write_import` already produces only header + transaction rows in
Master and Detail. This release **codifies** that behaviour as a
locked rule and adds a defensive assertion so a future template
change or new source format can't quietly violate it.

Changes:
- `compile_cfp.py` — `write_import` now calls
  `_assert_no_total_row()` against both Master and Detail after
  writing all rows. Any cell whose value is `Total` / `Grand Total` /
  `Subtotal` / `Sub Total` (case-insensitive, trailing colon
  tolerated) on rows >= 2 raises `RuntimeError` and aborts the save.
  Helper sheets (Audit / Unmapped / Reconciliation) are unaffected
  -- AutoCount reads only the first two sheets by position.
- `SKILL.md` -- 0.6.1 -> 0.6.2; new "Total-row handling" subsection
  spells out source-side capture (per format: PDF footer today, xlsx
  trailing row when that source format lands) and the locked
  output-side rule that the AutoCount import contains no Total row.
- `VERSION` -- `0.6.1` -> `0.6.2`.

Forward-looking:
- When the xlsx-source code path lands (likely v0.7.0), the xlsx
  parser will read the last data row, treat it as the Check A
  control total, and drop it before the row enters `List[Redemption]`.

Non-breaking:
- Existing PDF-source flow produces identical xlsx output.

---

## 0.6.1 — 2026-05-10
**Reconciliation harness added; corrects "bank deposit" misnomer.**

KS request: "i need you to relook into the method you use and put in
a verification in place in this skill".

Re-walked the full PDF→xlsx pipeline and identified four leak points:
parser drop, date-filter drop, customer-match drop (intentional but
must be visible), and Qty×UnitPrice rounding drift. Three checks
cover all four:

- **Check A — per-PDF parse integrity.** The parser now captures each
  PDF's `Total:` / `Grand Total:` footer instead of just filtering it
  out. `parse_pdf` returns a `PDFParseResult(path, redemptions,
  source_total, parsed_total)`. Reconciliation flags any PDF where
  `|parsed_total − source_total| ≥ 0.01`. SKIP when the PDF carries
  no Total line.
- **Check B — pipeline conservation.**
  `Σ filtered = Σ consolidated + Σ unmapped`. Catches anything
  silently lost between filter and bucketed output.
- **Check C — AutoCount math.** For every detail row that will be
  written, `|Qty × UnitPrice − Subtotal| < 0.01`. Catches rounding
  drift in Qty / UnitPrice derivation that would otherwise make
  AutoCount disagree with our Subtotal.

The reconciliation report is printed to console, written to a new
`Reconciliation` sheet in the output xlsx, and any FAIL drives a
**non-zero exit (code 2)** so an automated caller can't silently
import a broken file.

Behaviour changes:
- Detail-row math (Qty / UnitPrice / Subtotal / Description) is now
  computed by `build_detail_rows()` and reused by both `write_import`
  and `build_reconciliation`. Decoupling guarantees the
  reconciliation reads exactly what was written.
- `parse_pdf` signature changed: `List[Redemption]` →
  `PDFParseResult`. Callers within this script are updated;
  external callers (none known) would need to read `.redemptions`.
- `write_import` signature changed: now takes `detail_rows` and
  optional `reconciliation`; deprecated `reference_prices` and
  `doc_no_prefix` parameters since the math now happens upstream.

Files changed:
- `compile_cfp.py` — adds `TOTAL_LINE_RX`, `_extract_total`,
  `PDFParseResult`, `DetailRow`, `build_detail_rows`, `ReconCheck`,
  `RECON_TOLERANCE`, `build_reconciliation`, `print_reconciliation`;
  refactors `parse_pdf` and `write_import`; `main()` now prints a
  per-PDF Total comparison and a full reconciliation block, exits
  with code 2 on any FAIL.
- `SKILL.md` — 0.6.0 → 0.6.1; new "Verification / Reconciliation"
  section; corrects the misleading "ties to the bank deposit"
  line (now: "ties back to the per-PDF `Total:` footer line");
  "How Claude should run it" updated with explicit FAIL-handling
  step and instruction to surface the recon block before declaring
  success.
- `VERSION` — `0.6.0` → `0.6.1`.

Non-breaking for the operator:
- A clean run still produces the same xlsx as v0.6.0 (just with an
  extra `Reconciliation` sheet).
- DocNo numbering, totals, customer mapping, item codes, project
  codes, reference prices unchanged.

---

## 0.6.0 — 2026-05-08
**Description trimmed to <=80 chars; UOM always LITER; Qty derived
from reference prices when source has no litres; CSV-only output.**

KS request: "the voucher number cannot put into Description because
maximum 80 char / UOM must be in LITER / Output CSV only".

Behaviour changes:
- Detail-row `Description` no longer carries the voucher list
  (AutoCount Description cap is 80 chars). Format is now
  `<Gas> @ <Station> (<n> vch[ est])` -- the `est` suffix marks
  rows where Qty was derived rather than read from source.
- `UOM` is hard-coded to `LITER` for every row.
- For TK and BS source PDFs (which don't carry a litre column),
  `Qty = round(Subtotal / RefPrice, 2)` using the new
  `reference_prices.csv`. UnitPrice is then `Subtotal / Qty`
  so `Qty * UnitPrice = Subtotal` exactly.
- Voucher trail is preserved -- it stays in the Audit sheet
  / consolidated.csv `Vouchers` column.

Files changed:
- `reference_prices.csv` -- NEW. Per (station, gas) RM/L:
  Petrol = 3.97, Diesel = 2.15 across all three stations,
  inferred and verified against the 2026-05-01 sample data.
- `SKILL.md` -- 0.5.1 -> 0.6.0; "Qty / UOM / UnitPrice rules"
  section added; description format updated; file-list updated.
- `VERSION` -- `0.5.1` -> `0.6.0`.
- `compile_cfp.py` -- adds `load_reference_prices()`; consolidator
  now derives litres from RefPrice when missing; UOM hard-set to
  `LITER`; description shortened; `--reference-prices` CLI flag.
- `output/SalesImport_2026-05-01_*.csv` -- regenerated. Litres now
  populated on all 16 rows (was 8 of 16 before).

Notes:
- Output is CSV-only in v0.6.0. xlsx generation still requires
  the Linux Python sandbox; the script can produce xlsx the
  moment it's runnable.
- Reference prices are based on observed 2026-05-01 data.
  When the actual fuel price changes (Malaysia adjusts pump
  prices weekly), update `reference_prices.csv` and bump to
  v0.6.x (PATCH).

---

## 0.5.1 — 2026-05-08
**Project codes filled in (PATCH, data-only).**

KS provided the project codes verbally:
- TK -> `TK-FUEL`
- BS -> `BS-FUEL`
- BL -> `BL-FUEL`

Files changed:
- `project_codes.csv` -- placeholder values replaced with real
  codes; `source` column notes "provided by KS 2026-05-08".
- `SKILL.md` -- "AutoCount project codes" section rewritten from
  "pending" to "locked"; TODO list updated.
- `VERSION` -- `0.5.0` -> `0.5.1`.
- `output/SalesImport_2026-05-01_*.csv` -- regenerated with the
  `ProjectNo` column populated (`TK-FUEL` / `BS-FUEL` / `BL-FUEL`
  per row).

No code or schema change. PATCH bump per the SemVer policy in this
skill (data-only updates).

---

## 0.5.0 — 2026-05-08
**DebtorName added to master output; all required import fields verified.**

KS request: "I need the following data to be imported also:
DebtorName, Qty, UOM, ItemCode, UnitPrice, ProjectNo".

Field-by-field status after v0.5.0:
- `DebtorName` -- NEW on master sheet, sourced from
  `customer_codes.csv.company_name`.
- `Qty` -- already on detail (litres when available, else 1).
- `UOM` -- already on detail (`Litre` or `Unit`).
- `ItemCode` -- already on detail (per-station fuel code from
  `stock_codes.csv`).
- `UnitPrice` -- already on detail (`Subtotal / Qty`).
- `ProjectNo` -- column is wired up; values still blank pending
  the actual codes from `Project Code.docx` (not yet readable).

Files changed:
- `SKILL.md` -- 0.4.0 -> 0.5.0; new "Required AutoCount columns"
  table makes the schema explicit.
- `VERSION` -- `0.4.0` -> `0.5.0`.
- `compile_cfp.py` -- `COLUMN_MAP_MASTER` gains `debtor_name`;
  master writer fills it from the customer master.
- `output/SalesImport_2026-05-01_master.csv` -- new `DebtorName`
  column.

Non-breaking:
- Detail sheet is unchanged. Total amounts, DocNo numbering,
  consolidation rule are all the same as v0.4.0.

---

## 0.4.0 — 2026-05-08
**Voucher list appended to AutoCount Detail Description for audit trail.**

KS request: "in the description i need the voucher detail to be
appended for import to autocount".

Behaviour:
- Detail-row `Description` column now ends with
  `| Vouchers: <code1>; <code2>; ...` so the audit trail lives
  inside AutoCount on import (not just in the side Audit sheet).
- Format: `<Gas> @ <Station> (<n> vch) | Vouchers: <v1>; <v2>; ...`
- The `Audit` sheet still includes the voucher list in its own
  column for redundant traceability.

Files changed:
- `SKILL.md` -- 0.3.0 -> 0.4.0; description format documented.
- `VERSION` -- `0.3.0` -> `0.4.0`.
- `compile_cfp.py` -- detail `description` field now appended with
  the voucher list pulled from `cr.voucher_list`.
- `output/SalesImport_2026-05-01_*.csv` -- regenerated with the
  new description format.

Non-breaking:
- DocNo numbering, totals, customer mapping unchanged.

---

## 0.3.0 — 2026-05-08
**Invoicing granularity changed: one Sales Invoice per (date, customer, station, product).**

KS request: "i need to amend per customer per station per product
for daily invoicing".

Behaviour:
- Header DocNo and detail line are now 1-to-1.
- A customer that redeems Petrol at TK and BL on the same day now
  produces **two** Sales Invoices (one per station-fuel combo)
  rather than one invoice with two lines.
- Sequence numbering still `CFP-YYYYMMDD-NNNN`, ordered by
  `(date, debtor, station, fuel)`.

Files changed:
- `SKILL.md` — version 0.2.0 -> 0.3.0; consolidation rule rewritten;
  example table updated.
- `VERSION` — `0.2.0` -> `0.3.0`.
- `compile_cfp.py` — `write_import` no longer dedupes the master
  header by `(date, acc_code)`; every consolidated detail row gets
  its own DocNo and its own master header row. Master row now
  carries the station + product in the description for visibility.
- `output/SalesImport_2026-05-01_*.csv` — regenerated to match the
  new rule. Total rows go from 16 to 16 detail rows under 16
  invoice headers (previously 16 detail rows under 13 headers).

BREAKING for downstream:
- The 2026-05-01 sample now has **16 invoices instead of 13**.
- A customer with Petrol + Diesel at the same station on the same
  day now produces 2 invoices instead of 1.

---

## 0.2.0 — 2026-05-08
**Per-station item codes locked; project-code scaffold added; consolidation rule refined.**

Inputs received from KS:
- `Item Listing.pdf` (08/05/2026 09:42:37) — FUEL group has 6 items:
  `PETROL - TK`, `DIESEL -TK`, `PETROL -BS`, `DIESEL- BS`,
  `PETROL - BL`, `DIESEL- BL`. Spacing is preserved verbatim from
  the AutoCount Item Listing.
- `Project Code.docx` — file present in
  `D:/CLAUDE/Skill/CFP Entry/Autocount Import Template/` but NOT
  yet read; .docx parsing requires the Linux sandbox which was
  unavailable this session. Placeholder `project_codes.csv`
  created with TK / BS / BL rows and blank values; user to
  fill in v0.3.0.

Files changed:
- `SKILL.md` — version 0.1.0 -> 0.2.0; consolidation rule rewritten
  (group key now includes station); item-code table embedded;
  CLI flags updated.
- `VERSION` — `0.1.0` -> `0.2.0`.
- `compile_cfp.py` — adds `STATION_FUEL_TO_ITEM_CODE` derived from
  `stock_codes.csv`, `--stock-codes` and `--project-codes` flags;
  group key now `(date, acc_code, station, gas_type)`; ItemCode
  and ProjectNo (when present) written into detail rows;
  deprecated `--petrol-code` / `--diesel-code` flags emit a
  warning and are ignored.
- `stock_codes.csv` — NEW. Maps `(station, gas_type)` -> AutoCount
  item code.
- `project_codes.csv` — NEW. Maps station -> AutoCount project
  code; values blank pending Project Code.docx contents.

BREAKING for downstream consumers of v0.1 output:
- A customer that redeems at multiple stations on the same day now
  produces multiple detail lines (one per station+fuel) instead of
  one merged line. The Sales Invoice header still consolidates them
  under one DocNo per (date, debtor).

---

## 0.1.0 — 2026-05-08
**Initial release.**

Decisions locked in this version (from KS):
- AutoCount document type: **Sales Invoice**.
- Output scope: **one combined xlsx per day**, all stations merged.
- Grouping granularity: **1 line per customer per fuel type per day**
  (Petrol and Diesel are separate detail rows under the same
  invoice header).
- Stock codes: **deferred** — user will supply Petrol / Diesel codes
  later. CLI flags `--petrol-code` / `--diesel-code` accept them, and
  blank cells will be left for manual fill in AutoCount.

Files added:
- `SKILL.md` — skill description, run instructions, versioning policy.
- `compile_cfp.py` — PDF parser, customer matcher, consolidator,
  AutoCount xlsx writer.
- `customer_codes.csv` — snapshot of AutoCount Debtor Listing
  (Active filter) as of **2026-05-07**, 144 debtors:
  acc_code, company_name, voucher_code, station.
- `CHANGELOG.md` — this file.

Known issues / follow-ups:
- `SINKHONG TRANSPORT` appears in 2026-05-01 TK report but is not in
  the master list — to be added when a 300-XXXX code is created.
- AutoCount tax code per line is not yet specified.
- DocNo convention defaults to `CFP-YYYYMMDD-NNNN`; confirm with
  finance.

---

## How to log future changes (template)

```
## 0.2.0 — YYYY-MM-DD
- Added 5 new debtors to customer_codes.csv: 300-XXXX, ...
- Petrol stock code locked in as `PETROL-RON95` (per finance email
  YYYY-MM-DD).

## 0.1.1 — YYYY-MM-DD
- Fixed BL-layout PDF parser: litre column was being misread when
  the value crossed 1,000 (comma split). Now strips thousand separators
  before float conversion.

## 1.0.0 — YYYY-MM-DD  *(BREAKING)*
- Switched from Sales Invoice to Debtor Knock-Off as confirmed with
  auditor on YYYY-MM-DD. Existing Sales Invoice mode is dropped.
```
