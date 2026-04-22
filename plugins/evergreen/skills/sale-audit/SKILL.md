---
name: sale-audit
description: Use this skill whenever the user (Evergreen back-office / management) wants to audit, verify, or check the daily sale submission of a petrol station — TK (Tg. Kapor), BS (Berkat Setia), or BL (Bubul Lama). Triggers include phrases like "audit TK", "audit sale", "check BS sale", "verify fund report", "run daily audit", "daily sale audit for <date>", or any request to reconcile a station's Fund Report against its supporting documents and produce an audit PDF.
---

# Sale Audit — Evergreen Petrol Stations

Reconcile a station's daily Fund Report against the actual proof-of-fund documents, POS printouts, CFP report, and fuel records. The Fund Report is manually prepared and is **never conclusive** — always audit from the primary evidence, then flag every discrepancy in a landscape PDF.

---

## 1. Stations and business segments

| Code | Station      | Segments                                   |
|------|--------------|--------------------------------------------|
| TK   | Tg. Kapor    | Fuel, Buraqmart, Rental, iBing             |
| BS   | Berkat Setia | Fuel, Buraqmart, Rental                    |
| BL   | Bubul Lama   | Fuel, Buraqmart, Rental                    |

## 2. Bank accounts (all deposits must land here)

- **Maybank**: 510161015366, 560166149415, 560166149422
- **AmBank**: 8881058618135, 8881058618146, 8881058618157

Any deposit/transfer to an account outside this list is an automatic finding.

## 3. Network file server & output location

On first run, ask the user for **three** paths and save each to memory as a `reference` memory so they are never asked again:

1. **Daily-report root path** — per-station, per-date folders containing the files in §4.
2. **Bank-statement folder path** — kept separately from daily reports.
3. **Audit-output folder path** — where the final PDF reports are saved. Suggested convention: `<output-root>/<station>/<YYYY-MM-DD>-sale-audit.pdf`.

Before reusing any remembered path, verify it still resolves; if not, ask once and update the memory. If the user has not answered for a given path yet, ask for it at the start of the first audit that needs it — do not proceed without it.

Expected daily layout: `<daily-report-root>/<station>/<YYYY-MM-DD>/…`

## 4. Required daily files (per station, per date)

1. GreenPOS till report
2. Fund Report
3. Corporate Fuel Portal (CFP) report
4. Merchant settlement report
5. Proof-of-fund receipts — transfer slips, e-wallet screenshots, cash deposit slips, cheque images
6. Buraqmart Autocount POS report
7. Fuel delivery order *(only if delivery occurred)*
8. Opening GreenPOS fuel count
9. Closing GreenPOS fuel count
10. iBing sale report *(TK only, if applicable)*
11. Rental records
12. Fuel quantity records

**First audit step:** enumerate present vs. missing files. Every missing file is a finding.

## 5. Revenue channels

| Channel   | How it is proven                                                                 |
|-----------|----------------------------------------------------------------------------------|
| Cash      | Cash deposit machine receipt                                                     |
| Merchant  | Debit/credit card terminal settlement report                                     |
| CFP       | Voucher used = revenue. CFP top-ups are **deposits, not revenue**.               |
| BUDI95    | Customer pays part; balance claimed from gov't via principal supplier IPTB.      |

## 6. Audit rules — strict, non-negotiable

Run every check. Flag every failure.

1. **Independent reconciliation.** Summarise revenue **solely from the actual proof-of-fund files**, not from the Fund Report. The Fund Report is a starting point, never evidence.
2. **Cash receipts.** Only a cash deposit machine receipt counts as proof of cash deposited.
3. **Cash balance.** Compute opening cash + today's cash collected − today's deposits = expected closing cash. Compare against Fund Report's closing cash and flag any variance.
4. **Date match.** Every proof-of-fund document must bear the same date as the Fund Report. Reject any older slip used to pad today's revenue.
5. **Distinct documents.** No two proof-of-fund documents may be identical or duplicated (same slip reused).
6. **Correct account.** Deposits must land in one of the six bank accounts in §2.
7. **POS tally.** GreenPOS, Autocount POS, and iBing FeedMePOS totals (system-generated → source of truth) must match the Fund Report totals.
8. **Channel tally.** Per-channel revenue in proof-of-fund must match the per-channel split in the POS systems.
9. **CFP vs. GreenPOS voucher.** Total CFP report must tally with the GreenPOS voucher line.
10. **Fuel quantity.** Opening fuel + deliveries − sales = closing fuel. Reconcile against the fuel quantity records and delivery orders, per product.
11. **Funds cleared.** Cross-check the bank-statement folder to confirm the day's deposits/transfers actually cleared into the listed accounts.

## 7. Output — landscape PDF

Use `anthropic-skills:pdf` to generate the report. **Landscape** orientation, graphical where it helps, short-form text in tables, and headers with strong contrast (dark-on-light or light-on-dark — never low-contrast pastels).

**Section 1 — Revenue breakdown**
- Total revenue for the date.
- Revenue by business segment (bar or stacked bar).
- Revenue by channel (cash / merchant / CFP / BUDI95) as a **pie chart**.

**Section 2 — Proof-of-fund audit table**
One row per document. Use short-form column headers:

| Doc | Type | Amt (RM) | Date✓ | Uniq✓ | Acct✓ | POS✓ | Cleared✓ | Notes |

Tick / cross per criterion; one-line note on failures.

**Section 3 — Cash highlight**
Opening cash, closing cash (Fund Report vs. calculated), variance. Highlight any mismatch in red.

**Section 4 — Fuel quantity audit**
Per product: opening qty, delivery qty, sales qty, calculated closing, reported closing, variance. Highlight variances.

**Section 5 — Findings & recommendations**
Bulleted list of every flag, ordered by materiality (financial impact first, control weakness second). End with concrete management actions.

## 8. Workflow

1. Confirm **station(s)** and **date** (default to yesterday if not given).
2. Recall or ask for the three paths in §3 (daily-report root, bank-statement folder, audit-output folder). Save any missing ones to memory on first run.
3. List files present vs. missing for that station+date.
4. Run all §6 checks, preserving every intermediate calculation.
5. Render the landscape PDF per §7 and **save it to the audit-output folder** as `<station>/<YYYY-MM-DD>-sale-audit.pdf`.
6. Reply in chat with the 3–5 most material findings and the absolute path to the saved PDF.
