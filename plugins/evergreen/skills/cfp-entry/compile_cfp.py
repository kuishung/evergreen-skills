#!/usr/bin/env python3
"""
compile_cfp.py
==============

Skill: cfp-entry  (version 0.6.0)

CFP voucher-redemption -> AutoCount Sales Invoice import compiler.

What it does
------------
1. Reads one or more daily CFP / gvLedger PDFs (from any of the three
   stations: TK = Tg Kapor, BS = Berkat Setia, BL = Bubul Lama).
2. Parses every voucher-redemption line.
3. Looks up each company against customer_codes.csv (extracted from the
   AutoCount Debtor Listing) to attach the 300-XXXX account code.
4. Groups all redemptions by (account_code, gas_type) for the day so each
   customer appears in AutoCount as one Petrol line and/or one Diesel
   line per day -- never one line per voucher.
5. Opens the user's AutoCount "Default Sales.xlsx" template, copies its
   header layout, and writes the consolidated rows into a new xlsx
   ready for AutoCount's Sales Invoice import.

Usage
-----
    python compile_cfp.py \
        --reports "D:/CLAUDE/Skill/CFP Entry/20260501-CFP REPORT-TK.pdf" \
                  "D:/CLAUDE/Skill/CFP Entry/gvLedger - 2026-05-01T143652.120.pdf" \
                  "D:/CLAUDE/Skill/CFP Entry/gvLedger - BL.pdf" \
        --date 2026-05-01 \
        --template "D:/CLAUDE/Skill/CFP Entry/Autocount Import Template/Default Sales.xlsx" \
        --customers "D:/CLAUDE/Skill/CFP Entry/cfp-entry/customer_codes.csv" \
        --out "D:/CLAUDE/Skill/CFP Entry/output/SalesImport_2026-05-01.xlsx" \
        --petrol-code "" --diesel-code ""

If --date is omitted, the script infers it from the first redemption row.

Customer-name matching
----------------------
The CFP report and AutoCount sometimes spell names slightly differently
(extra spaces, "(SABAH)" added, trailing "- (BL-V14)" etc.). The
matcher therefore:
  * uppercases & collapses whitespace on both sides
  * strips trailing parenthetical "- (BL-V14)" / "(BS-V1)" markers
  * tries exact match first, then a fuzzy contains/Jaccard fallback
  * any unmatched company is written into a separate "Unmapped" sheet
    so you can fix the master list and re-run

Dependencies
------------
    pip install pdfplumber openpyxl rapidfuzz

(rapidfuzz is optional; if unavailable, a built-in fallback is used.)

Author : Evergreen back-office automation
Skill  : cfp-entry
See    : SKILL.md and CHANGELOG.md for version history.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

try:
    import pdfplumber
except ImportError:  # pragma: no cover
    print("ERROR: pdfplumber is required. Run: pip install pdfplumber", file=sys.stderr)
    raise

try:
    from openpyxl import load_workbook, Workbook
except ImportError:  # pragma: no cover
    print("ERROR: openpyxl is required. Run: pip install openpyxl", file=sys.stderr)
    raise

try:
    from rapidfuzz import fuzz as _rfz_fuzz
    def _ratio(a: str, b: str) -> float:
        return _rfz_fuzz.token_set_ratio(a, b) / 100.0
except ImportError:  # pragma: no cover
    def _ratio(a: str, b: str) -> float:
        # crude Jaccard on tokens as a fallback
        sa, sb = set(a.split()), set(b.split())
        if not sa or not sb:
            return 0.0
        return len(sa & sb) / len(sa | sb)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Redemption:
    company_raw: str
    gas_type: str          # "Petrol" / "Diesel"
    amount: float          # absolute, positive
    litre: Optional[float] # may be None for TK/BS reports that omit litres
    vehicle: str
    station: str           # "Buraqoil Tg Kapor" / "...Berkat Setia" / "...Bubul Lama"
    voucher: str
    redeem_dt: datetime
    receipt: str

    @property
    def date(self) -> str:
        return self.redeem_dt.strftime("%Y-%m-%d")


@dataclass
class CustomerRow:
    acc_code: str
    company_name: str
    voucher_code: str
    station: str


# ---------------------------------------------------------------------------
# Per-station fuel item codes  (from Item Listing.pdf, 2026-05-08)
# Spacing is verbatim from AutoCount -- DO NOT normalise.
# ---------------------------------------------------------------------------
STATION_FUEL_TO_ITEM_CODE: Dict[Tuple[str, str], str] = {
    ("TK", "Petrol"): "PETROL - TK",
    ("TK", "Diesel"): "DIESEL -TK",
    ("BS", "Petrol"): "PETROL -BS",
    ("BS", "Diesel"): "DIESEL- BS",
    ("BL", "Petrol"): "PETROL - BL",
    ("BL", "Diesel"): "DIESEL- BL",
}

STATION_NAME_TO_KEY: Dict[str, str] = {
    "Buraqoil Tg Kapor":     "TK",
    "Buraqoil Berkat Setia": "BS",
    "Buraqoil Bubul Lama":   "BL",
}


def load_stock_codes(path: Optional[Path]) -> Dict[Tuple[str, str], str]:
    """Override the built-in mapping with values from stock_codes.csv (if given)."""
    if path is None or not path.exists():
        return dict(STATION_FUEL_TO_ITEM_CODE)
    out: Dict[Tuple[str, str], str] = {}
    with path.open(newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            stn = (r.get("station") or "").strip().upper()
            gas = (r.get("gas_type") or "").strip().title()
            code = (r.get("item_code") or "").strip()
            if stn and gas and code:
                out[(stn, gas)] = code
    # Fill any gaps from the built-in map
    for k, v in STATION_FUEL_TO_ITEM_CODE.items():
        out.setdefault(k, v)
    return out


def load_project_codes(path: Optional[Path]) -> Dict[str, str]:
    """station -> ProjectNo. Empty values mean 'leave the column blank'."""
    out: Dict[str, str] = {"TK": "", "BS": "", "BL": ""}
    if path is None or not path.exists():
        return out
    with path.open(newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            stn = (r.get("station") or "").strip().upper()
            code = (r.get("project_code") or "").strip()
            if stn:
                out[stn] = code
    return out


# ---------------------------------------------------------------------------
# Reference prices (v0.6.0): used when the source PDF doesn't carry a litre
# column (TK CFP REPORT, BS gvLedger). Default values inferred from the
# 2026-05-01 BL data and verified to round-trip against the same-day TK/BS
# amounts.
# ---------------------------------------------------------------------------
DEFAULT_REFERENCE_PRICES: Dict[Tuple[str, str], float] = {
    ("TK", "Petrol"): 3.97,
    ("TK", "Diesel"): 2.15,
    ("BS", "Petrol"): 3.97,
    ("BS", "Diesel"): 2.15,
    ("BL", "Petrol"): 3.97,
    ("BL", "Diesel"): 2.15,
}


def load_reference_prices(path: Optional[Path]) -> Dict[Tuple[str, str], float]:
    if path is None or not path.exists():
        return dict(DEFAULT_REFERENCE_PRICES)
    out: Dict[Tuple[str, str], float] = {}
    with path.open(newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            stn = (r.get("station") or "").strip().upper()
            gas = (r.get("gas_type") or "").strip().title()
            try:
                price = float((r.get("price_per_litre") or "0").strip())
            except ValueError:
                price = 0.0
            if stn and gas and price > 0:
                out[(stn, gas)] = price
    for k, v in DEFAULT_REFERENCE_PRICES.items():
        out.setdefault(k, v)
    return out


# ---------------------------------------------------------------------------
# Customer master loader
# ---------------------------------------------------------------------------

def load_customers(path: Path) -> List[CustomerRow]:
    rows: List[CustomerRow] = []
    with path.open(newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rows.append(CustomerRow(
                acc_code=r["acc_code"].strip(),
                company_name=r["company_name"].strip(),
                voucher_code=(r.get("voucher_code") or "").strip(),
                station=(r.get("station") or "").strip(),
            ))
    return rows


def _norm(s: str) -> str:
    s = s.upper()
    # strip trailing "- (BS-V14)" / "(TK)" / "BS-V14"
    s = re.sub(r"[\(\-]\s*[A-Z]{2}\s*-?\s*V?\s*\d*\s*\)?\s*$", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = s.replace(".", "").replace(",", "")
    s = re.sub(r"\bSDN\.?\s*BHD\.?", "SDN BHD", s)
    s = re.sub(r"\bSDH\b", "SDN", s)  # typo seen in master list
    return s.strip()


class CustomerMatcher:
    def __init__(self, customers: List[CustomerRow]):
        self.customers = customers
        self._index: Dict[str, CustomerRow] = {}
        for c in customers:
            self._index[_norm(c.company_name)] = c

    def match(self, company_raw: str, threshold: float = 0.78) -> Tuple[Optional[CustomerRow], float]:
        key = _norm(company_raw)
        if key in self._index:
            return self._index[key], 1.0
        # fuzzy
        best, best_score = None, 0.0
        for c in self.customers:
            score = _ratio(key, _norm(c.company_name))
            if score > best_score:
                best, best_score = c, score
        if best_score >= threshold:
            return best, best_score
        return None, best_score


# ---------------------------------------------------------------------------
# PDF parsing
# ---------------------------------------------------------------------------

# The reports come in two layouts. We support both by extracting text and
# matching a flexible regex line-by-line.
#
# Layout A (TK / BS):
#   Company  Type  Gas  Amount  Vehicle  Station  Voucher  RedeemDate  Receipt
# Layout B (BL):
#   Company  Type  Amount  Gas  Litre  Vehicle  Station  Voucher  RedeemDate  Receipt
#
# We rely on:
#   - the amount being signed (always negative in source) and unique enough
#   - the redeem datetime in YYYY-MM-DD HH:MM:SS form
#   - the voucher matches \d{6}-\w+-\w+

VOUCHER_RX = re.compile(r"\d{6}-[A-Z0-9]+-[A-Z0-9]+")
DT_RX      = re.compile(r"20\d{2}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}")
AMOUNT_RX  = re.compile(r"-[\d,]+\.\d{2}")
GAS_RX     = re.compile(r"\b(Petrol|Diesel)\b", re.IGNORECASE)
STATION_RX = re.compile(r"Buraqoil\s+(Tg\s*Kapor|Berkat\s*Setia|Bubul\s*Lama)", re.IGNORECASE)


def parse_pdf(path: Path) -> List[Redemption]:
    out: List[Redemption] = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            # First try table extraction -- both layouts render as a
            # bordered table so this usually gets clean rows.
            tables = page.extract_tables() or []
            for table in tables:
                for row in table:
                    rec = _row_to_redemption(row)
                    if rec:
                        out.append(rec)
            # Fallback: regex on raw text (handles malformed extractions)
            if not out:
                text = page.extract_text() or ""
                for line in text.splitlines():
                    rec = _line_to_redemption(line)
                    if rec:
                        out.append(rec)
    return out


def _row_to_redemption(row: List[Optional[str]]) -> Optional[Redemption]:
    if not row:
        return None
    cells = [(c or "").strip() for c in row]
    joined = " | ".join(cells)
    if "Total:" in joined or "Company" in joined and "Voucher" in joined:
        return None
    m_dt   = DT_RX.search(joined)
    m_amt  = AMOUNT_RX.search(joined)
    m_vch  = VOUCHER_RX.search(joined)
    m_gas  = GAS_RX.search(joined)
    m_stn  = STATION_RX.search(joined)
    if not (m_dt and m_amt and m_vch and m_gas):
        return None
    company = cells[0]
    if not company or company.lower().startswith("company"):
        return None
    amount = float(m_amt.group().replace(",", "").replace("-", ""))
    # litre -- present in BL layout only; pick the first non-amount numeric
    litre = None
    for c in cells:
        if c and c != m_amt.group():
            mlit = re.fullmatch(r"-?\d{1,4}\.\d{2}", c)
            if mlit:
                v = float(c)
                if 0 < abs(v) < 5000:  # plausibly a litre count
                    litre = abs(v)
                    break
    vehicle = ""
    for c in cells:
        if re.match(r"^[A-Z]{1,3}\s*\d{1,5}\s*[A-Z/]*$", c) or re.match(r"^[A-Z]{2,3}\d{3,5}$", c):
            vehicle = c
            break
    station = "Buraqoil " + m_stn.group(1).title() if m_stn else ""
    return Redemption(
        company_raw=company,
        gas_type=m_gas.group(1).title(),
        amount=amount,
        litre=litre,
        vehicle=vehicle,
        station=station,
        voucher=m_vch.group(),
        redeem_dt=datetime.strptime(m_dt.group(), "%Y-%m-%d %H:%M:%S"),
        receipt=cells[-1],
    )


def _line_to_redemption(line: str) -> Optional[Redemption]:
    if "Total:" in line:
        return None
    m_dt   = DT_RX.search(line)
    m_amt  = AMOUNT_RX.search(line)
    m_vch  = VOUCHER_RX.search(line)
    m_gas  = GAS_RX.search(line)
    m_stn  = STATION_RX.search(line)
    if not (m_dt and m_amt and m_vch and m_gas):
        return None
    # Company is everything before the first "Refuel"
    head = re.split(r"\bRefuel\b", line, maxsplit=1)[0].strip()
    if not head:
        return None
    return Redemption(
        company_raw=head,
        gas_type=m_gas.group(1).title(),
        amount=float(m_amt.group().replace(",", "").replace("-", "")),
        litre=None,
        vehicle="",
        station="Buraqoil " + m_stn.group(1).title() if m_stn else "",
        voucher=m_vch.group(),
        redeem_dt=datetime.strptime(m_dt.group(), "%Y-%m-%d %H:%M:%S"),
        receipt="",
    )


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

@dataclass
class ConsolidatedRow:
    doc_date: str
    acc_code: str
    company_name: str
    station_key: str      # TK / BS / BL  (v0.2.0 -- now part of group key)
    gas_type: str         # Petrol / Diesel
    total_amount: float   # positive
    total_litre: float    # 0.0 if all source rows had no litre info
    voucher_count: int
    voucher_list: str     # ;-separated for audit trail
    station_full: str     # human-readable e.g. "Buraqoil Tg Kapor"
    notes: str = ""


def _station_key_from_full(s: str) -> str:
    return STATION_NAME_TO_KEY.get(s, "")


def consolidate(redemptions: Iterable[Redemption],
                matcher: CustomerMatcher) -> Tuple[List[ConsolidatedRow], List[Redemption]]:
    """v0.2.0: group key = (date, acc_code, station, gas_type)."""
    bucket: Dict[Tuple[str, str, str, str], ConsolidatedRow] = {}
    unmapped: List[Redemption] = []
    for r in redemptions:
        cust, score = matcher.match(r.company_raw)
        if cust is None:
            unmapped.append(r)
            continue
        stn_key = _station_key_from_full(r.station)
        key = (r.date, cust.acc_code, stn_key, r.gas_type)
        if key not in bucket:
            bucket[key] = ConsolidatedRow(
                doc_date=r.date,
                acc_code=cust.acc_code,
                company_name=cust.company_name,
                station_key=stn_key,
                gas_type=r.gas_type,
                total_amount=0.0,
                total_litre=0.0,
                voucher_count=0,
                voucher_list="",
                station_full=r.station,
                notes="" if score >= 0.99 else f"fuzzy match {score:.2f} from '{r.company_raw}'",
            )
        cr = bucket[key]
        cr.total_amount += r.amount
        cr.total_litre  += (r.litre or 0.0)
        cr.voucher_count += 1
        cr.voucher_list = f"{cr.voucher_list};{r.voucher}".strip(";")
    rows = sorted(bucket.values(),
                  key=lambda x: (x.doc_date, x.acc_code, x.station_key, x.gas_type))
    return rows, unmapped


# ---------------------------------------------------------------------------
# AutoCount xlsx writer
# ---------------------------------------------------------------------------

# AutoCount's "Default Sales.xlsx" template has Master and Detail sheets.
# Rather than hard-code them, we open the template, read row-1 headers
# verbatim, and only fill the columns that actually exist. Anything we
# don't have data for is left blank. The user can extend by editing the
# COLUMN_MAP below.

# Lower-cased canonical name -> list of header keywords any of which counts.
# Add aliases as your AutoCount build differs.
COLUMN_MAP_MASTER = {
    "doc_no":       ["docno", "doc no", "invoice no", "invoiceno"],
    "doc_date":     ["docdate", "doc date", "invoice date", "date"],
    "debtor_code":  ["debtorcode", "debtor code", "account no", "account code", "code"],
    "debtor_name":  ["debtorname", "debtor name", "customer name", "name"],
    "description":  ["description", "remark", "memo", "note"],
    "agent":        ["agent"],
    "currency":     ["currencycode", "currency"],
    "exchange":     ["exchangerate", "rate"],
}
COLUMN_MAP_DETAIL = {
    "doc_no":       ["docno", "doc no", "invoice no"],
    "item_code":    ["itemcode", "item code", "stock code", "stockcode"],
    "description":  ["description", "remark"],
    "uom":          ["uom"],
    "qty":          ["qty", "quantity", "numofunit"],
    "unit_price":   ["unitprice", "price"],
    "discount":     ["discount"],
    "subtotal":     ["subtotal", "amount", "total"],
    "tax_code":     ["taxcode", "taxtype"],
    "tax_amount":   ["taxamount", "tax amount"],
    "project_no":   ["projectno", "project no", "project"],
}


def _find_headers(ws, alias_map: Dict[str, List[str]]) -> Dict[str, int]:
    """Return canonical_name -> column_index (1-based) by scanning row 1."""
    found: Dict[str, int] = {}
    if ws.max_row < 1:
        return found
    headers = []
    for col in range(1, ws.max_column + 1):
        v = ws.cell(row=1, column=col).value
        headers.append((col, str(v).strip().lower() if v else ""))
    for canonical, aliases in alias_map.items():
        for col, h in headers:
            if not h:
                continue
            if any(a == h for a in aliases) or any(a in h for a in aliases):
                found[canonical] = col
                break
    return found


def write_import(template_path: Path,
                 out_path: Path,
                 rows: List[ConsolidatedRow],
                 unmapped: List[Redemption],
                 stock_codes: Dict[Tuple[str, str], str],
                 project_codes: Dict[str, str],
                 reference_prices: Dict[Tuple[str, str], float],
                 doc_no_prefix: str = "CFP") -> None:
    wb = load_workbook(str(template_path))
    sheet_names = wb.sheetnames

    # Locate master & detail sheets
    master_ws = wb[sheet_names[0]]
    detail_ws = wb[sheet_names[1]] if len(sheet_names) > 1 else None

    master_cols = _find_headers(master_ws, COLUMN_MAP_MASTER)
    detail_cols = _find_headers(detail_ws, COLUMN_MAP_DETAIL) if detail_ws else {}

    # Clear any existing sample data below row 1
    for ws in (master_ws, detail_ws):
        if ws is None:
            continue
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                cell.value = None

    # Write rows. One DocNo per (date, acc_code) header; one detail row per
    # (date, acc_code, gas_type).
    next_master_row = 2
    next_detail_row = 2
    seq = 1

    # v0.3.0: ONE Sales Invoice per (date, debtor, station, fuel).
    # Header and detail are 1-to-1.
    for cr in rows:
        doc_no = f"{doc_no_prefix}-{cr.doc_date.replace('-', '')}-{seq:04d}"
        seq += 1
        item_code = stock_codes.get((cr.station_key, cr.gas_type), "")
        project_no = project_codes.get(cr.station_key, "")

        # Master row -- one per detail row in v0.3.0
        mr = next_master_row
        next_master_row += 1
        master_desc = (f"CFP {cr.gas_type} @ {cr.station_full or cr.station_key} "
                       f"{cr.doc_date}")
        _set(master_ws, mr, master_cols.get("doc_no"),       doc_no)
        _set(master_ws, mr, master_cols.get("doc_date"),     cr.doc_date)
        _set(master_ws, mr, master_cols.get("debtor_code"),  cr.acc_code)
        _set(master_ws, mr, master_cols.get("debtor_name"),  cr.company_name)
        _set(master_ws, mr, master_cols.get("description"),  master_desc)
        _set(master_ws, mr, master_cols.get("currency"),     "RM")
        _set(master_ws, mr, master_cols.get("exchange"),     1)

        # Detail row
        if detail_ws is None:
            continue
        dr = next_detail_row
        next_detail_row += 1

        # v0.6.0: derive litres from reference price when source has none.
        if cr.total_litre and cr.total_litre > 0:
            qty = round(cr.total_litre, 2)
            est = False
        else:
            ref_price = reference_prices.get((cr.station_key, cr.gas_type), 0.0)
            qty = round(cr.total_amount / ref_price, 2) if ref_price > 0 else 0.0
            est = True
        unit_price = round(cr.total_amount / qty, 4) if qty > 0 else 0.0

        # v0.6.0: short description, no voucher list (80-char cap).
        desc = (f"{cr.gas_type} @ {cr.station_full or cr.station_key} "
                f"({cr.voucher_count} vch{' est' if est else ''})")

        _set(detail_ws, dr, detail_cols.get("doc_no"),      doc_no)
        _set(detail_ws, dr, detail_cols.get("item_code"),   item_code)
        _set(detail_ws, dr, detail_cols.get("description"), desc[:80])
        _set(detail_ws, dr, detail_cols.get("uom"),         "LITER")
        _set(detail_ws, dr, detail_cols.get("qty"),         qty)
        _set(detail_ws, dr, detail_cols.get("unit_price"),  unit_price)
        _set(detail_ws, dr, detail_cols.get("subtotal"),    round(cr.total_amount, 2))
        if project_no:
            _set(detail_ws, dr, detail_cols.get("project_no"), project_no)

    # Audit sheet (always)
    if "Audit" in wb.sheetnames:
        audit_ws = wb["Audit"]
        wb.remove(audit_ws)
    audit_ws = wb.create_sheet("Audit")
    audit_ws.append(["Date", "AccCode", "Customer", "Station", "Gas",
                     "ItemCode", "ProjectNo", "Amount", "Litre",
                     "VoucherCount", "Vouchers", "Notes"])
    for cr in rows:
        audit_ws.append([cr.doc_date, cr.acc_code, cr.company_name,
                         cr.station_full or cr.station_key, cr.gas_type,
                         stock_codes.get((cr.station_key, cr.gas_type), ""),
                         project_codes.get(cr.station_key, ""),
                         round(cr.total_amount, 2), round(cr.total_litre, 2),
                         cr.voucher_count, cr.voucher_list, cr.notes])

    # Unmapped sheet
    if "Unmapped" in wb.sheetnames:
        wb.remove(wb["Unmapped"])
    unmapped_ws = wb.create_sheet("Unmapped")
    unmapped_ws.append(["CompanyAsReported", "Gas", "Amount", "Voucher",
                        "Station", "RedeemDate", "Receipt"])
    for r in unmapped:
        unmapped_ws.append([r.company_raw, r.gas_type, r.amount, r.voucher,
                            r.station, r.redeem_dt.strftime("%Y-%m-%d %H:%M:%S"),
                            r.receipt])

    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(out_path))


def _set(ws, row: int, col: Optional[int], value):
    if col is None or row is None:
        return
    ws.cell(row=row, column=col, value=value)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Compile CFP voucher redemptions into an AutoCount sales import xlsx.")
    p.add_argument("--reports", nargs="+", required=True, help="One or more CFP/gvLedger PDFs")
    p.add_argument("--date", default=None, help="Document date YYYY-MM-DD (auto-detect if omitted)")
    p.add_argument("--template", required=True, help="Path to AutoCount Default Sales.xlsx")
    p.add_argument("--customers", required=True, help="customer_codes.csv")
    p.add_argument("--out", required=True, help="Output xlsx path")
    p.add_argument("--stock-codes", default=None,
                   help="Path to stock_codes.csv (overrides built-in mapping)")
    p.add_argument("--project-codes", default=None,
                   help="Path to project_codes.csv")
    p.add_argument("--reference-prices", default=None,
                   help="Path to reference_prices.csv (per-station-gas RM/L)")
    # deprecated -- silently accepted for backward compat
    p.add_argument("--petrol-code", default=None, help=argparse.SUPPRESS)
    p.add_argument("--diesel-code", default=None, help=argparse.SUPPRESS)
    p.add_argument("--doc-prefix", default="CFP", help="DocNo prefix (default: CFP)")
    args = p.parse_args(argv)

    if args.petrol_code or args.diesel_code:
        print("WARNING: --petrol-code / --diesel-code are deprecated since v0.2.0; "
              "the script picks per-station codes from stock_codes.csv.",
              file=sys.stderr)

    matcher = CustomerMatcher(load_customers(Path(args.customers)))
    stock_codes = load_stock_codes(Path(args.stock_codes) if args.stock_codes else None)
    project_codes = load_project_codes(Path(args.project_codes) if args.project_codes else None)
    reference_prices = load_reference_prices(
        Path(args.reference_prices) if args.reference_prices else None)

    all_red: List[Redemption] = []
    for rp in args.reports:
        path = Path(rp)
        if not path.exists():
            print(f"WARN: report not found: {rp}", file=sys.stderr)
            continue
        recs = parse_pdf(path)
        print(f"  parsed {len(recs):3d} rows  <- {path.name}")
        all_red.extend(recs)

    if args.date:
        all_red = [r for r in all_red if r.date == args.date]
        print(f"Filtered to {args.date}: {len(all_red)} rows")

    rows, unmapped = consolidate(all_red, matcher)
    print(f"\nConsolidated {len(rows)} customer-fuel rows; {len(unmapped)} unmapped rows.")
    if unmapped:
        print("Unmapped companies (add to customer_codes.csv):")
        for r in unmapped:
            print(f"   - {r.company_raw}  ({r.gas_type}, {r.amount:.2f})")

    write_import(
        template_path=Path(args.template),
        out_path=Path(args.out),
        rows=rows,
        unmapped=unmapped,
        stock_codes=stock_codes,
        project_codes=project_codes,
        reference_prices=reference_prices,
        doc_no_prefix=args.doc_prefix,
    )
    print(f"\nWrote import file: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
