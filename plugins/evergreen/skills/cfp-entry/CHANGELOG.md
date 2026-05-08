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
