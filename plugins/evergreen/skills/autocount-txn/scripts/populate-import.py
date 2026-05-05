#!/usr/bin/env python3
"""
autocount-txn — populate an Autocount import .xls from a source batch.

SCAFFOLD STUB. Not yet operational. The 9 Autocount XLS templates are
already in templates/ (see SKILL.md §3 for column layouts), but the
row-mapping logic is the v0.2.0 milestone — operator answers SKILL.md
§5 (static reference files) and §6 (source-data shape per module) first.

Intended CLI (post-implementation):
    python populate-import.py \\
        --module ap-invoice \\
        --source <path-to-source-csv-or-xlsx> \\
        --static-dir <txn-static-folder> \\
        --out <path-to-output-import.xls> \\
        [--state <path-to-txn-state.json>] \\
        [--month YYYY-MM]

Expected behaviour:
  1. Resolve the matching XLS template under <skill-dir>/templates/
     based on --module (e.g. ap-invoice → Import-AP-Invoice.xls).
  2. Detect the template's header convention (1-row vs 3-row, see
     templates/README.md). Read the actual column-name row.
  3. Load the source data (CSV or XLSX).
  4. Load the static reference files (chart-of-accounts,
     creditor-master, debtor-master, tax-type-map, etc.).
  5. For each source row:
       - Skip if its content-hash is in --state (already imported).
       - Map source fields → template columns using the static refs.
       - Validate: every required column populated, every code
         (CreditorCode/DebtorCode/AccNo/ProjNo/TaxType) recognised.
       - Append the mapped row to the output .xls at the next empty
         data row, preserving the template's headers / sheet
         structure so Autocount's import picks it up cleanly.
       - On any unresolvable row, write a copy + reason to
         <static-dir>/../unresolved/ instead of the import file.
  6. Update --state with the hashes of every successfully-imported row.
  7. Print a JSON summary:
        { module: "ap-invoice", imported: N, unresolved: M,
          out_path: "...", lookup_failures: [...] }

Dependencies (target):
  - xlrd 2.0.x (read .xls templates — v2 dropped .xlsx, that's fine
    since the templates are .xls).
  - xlwt for .xls writing (legacy BIFF). Or xlutils.copy(template) +
    in-place edits if header preservation matters.
  - openpyxl optionally for .xlsx source data.
  - pandas optionally for CSV / XLSX source parsing convenience.

This file is a STUB until the operator answers SKILL.md §5 / §6.
Filling in the real implementation here is the v0.2.0 milestone.
"""

import argparse
import sys

# Module → template filename mapping. Matches the nine .xls files in
# templates/. Adding a new module means adding a row here AND a
# matching .xls under templates/.
MODULE_TEMPLATES = {
    "ap-invoice":     "Import-AP-Invoice.xls",
    "ap-credit-note": "Import-AP-Credit-Note.xls",
    "ap-debit-note":  "Import-AP-Debit-Note.xls",
    "ap-payment":     "Import-AP-Payment.xls",
    "ar-invoice":     "Import-AR-Invoice.xls",
    "ar-credit-note": "Import-AR-Credit-Note.xls",
    "ar-debit-note":  "Import-AR-Debit-Note.xls",
    "ar-payment":     "Import-AR-Payment.xls",
    "journal":        "Import-Journal-Entry.xls",
}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--module", required=True, choices=sorted(MODULE_TEMPLATES.keys()),
                   help="Autocount import module to target (see SKILL.md §3).")
    p.add_argument("--source", required=True,
                   help="Path to source CSV / XLSX with the rows to import.")
    p.add_argument("--static-dir", required=True,
                   help="Path to TXN-static folder (chart-of-accounts, "
                        "creditor-master, debtor-master, tax-type-map).")
    p.add_argument("--out", required=True,
                   help="Output .xls path.")
    p.add_argument("--state", default=None,
                   help="Optional path to txn-state.json for incremental runs.")
    p.add_argument("--month", default=None,
                   help="Filter source rows to this month, YYYY-MM. "
                        "Defaults to the source's own date range.")
    args = p.parse_args()

    # SCAFFOLD: no real logic yet.
    print(
        f"autocount-txn populate-import.py is a SCAFFOLD STUB. "
        f"module={args.module!r} → template={MODULE_TEMPLATES[args.module]!r} "
        f"(under <skill-dir>/templates/). Implement per SKILL.md §5 / §6 "
        f"before running for real.",
        file=sys.stderr,
    )
    print(
        f"Args received: module={args.module!r} source={args.source!r} "
        f"static_dir={args.static_dir!r} out={args.out!r}",
        file=sys.stderr,
    )
    return 2  # exit non-zero so callers don't mistake the stub for success


if __name__ == "__main__":
    sys.exit(main())
