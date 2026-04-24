---
name: sale-audit
description: Use this skill whenever the user (Evergreen back-office / management) wants to audit, verify, or check the daily sale submission of a petrol station — TK (Tg. Kapor), BS (Berkat Setia), or BL (Bubul Lama). Triggers include phrases like "audit TK", "audit sale", "check BS sale", "verify fund report", "run daily audit", "daily sale audit for <date>", or any request to reconcile a station's Fund Report against its supporting documents and produce an audit PDF.
version: 0.6.0
updated: 2026-04-24 08:27
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
3. **Audit-output root** — a **single** folder shared by all stations. The skill creates the date tree inside it as `<audit-output-root>/<YYYY>/<YYYY-MM>/<YYYY-MM-DD>/` and writes every station's PDF into the same leaf folder, so the user never has to switch directories between stations. If an existing memory points to a per-station path, treat only its parent as the new root, confirm with the user once, and update the memory.

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

## 5. Inflow categories — Revenue vs. CFP Deposit

Not every amount received is revenue. Split the day's inflow into two disjoint groups and **never mix them**.

### 5.1 Revenue channels (recognised as revenue)

| Channel             | How it is proven                                                                                                                            |
|---------------------|---------------------------------------------------------------------------------------------------------------------------------------------|
| Cash                | Cash deposit machine receipt                                                                                                                |
| Merchant            | Debit/credit card terminal settlement report                                                                                                |
| CFP voucher used    | CFP report line showing redemption of a customer's pre-paid CFP balance against fuel sold (consumption of the balance — this is the sale). |
| BUDI95              | Subsidised RON95. Customer pays part at the pump; the balance is a **receivable claimed back from the government** via the principal supplier (IPTB). Count the full pump price in revenue; the claimable portion becomes a receivable, not a fund received today. Appears on GreenPOS as a BUDI95 tender. |

### 5.2 Non-revenue inflow

| Category     | How it is proven                                                                                                                              |
|--------------|-----------------------------------------------------------------------------------------------------------------------------------------------|
| CFP Deposit  | CFP top-up entries on the CFP report — the customer paid cash/card to **add balance to their CFP account** for future use. This is a customer-deposit liability on our books, **never revenue**. Must be reported separately in the PDF (see §7 Section 1). |

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
9. **CFP vs. GreenPOS voucher.** Sum of the CFP report's **voucher-usage lines only** (redemptions against pre-paid balance) must tally with the GreenPOS voucher line. CFP top-ups are deposits (§5.2) and are **excluded** from this tally — if a day's "CFP total" matches only when top-ups are included, someone has mis-classified a deposit as revenue.
10. **Fuel quantity.** Opening fuel + deliveries − sales = closing fuel. Reconcile against the fuel quantity records and delivery orders, per product.
11. **Funds cleared.** Cross-check the bank-statement folder to confirm the day's deposits/transfers actually cleared into the listed accounts.
12. **Fund Report aggregation integrity.** Staff sometimes sum several slips into a single Fund Report line (e.g., three cash-deposit slips reported as one "Cash deposits RMx" figure). For every Fund Report entry that aggregates more than one underlying slip, the sum of the underlying slips must equal the Fund Report line — flag any variance. Every individual slip must also appear somewhere in the Fund Report, either as its own line or as part of an aggregated line; any slip missing from the Fund Report entirely is an automatic finding (understatement). Audit always from the slips, never let the Fund Report's aggregated view suppress an individual row in the proof-of-fund table (see §7 Section 2).

## 7. Output — landscape PDF

Use `anthropic-skills:pdf` to generate the report. **Landscape** orientation, graphical where it helps, short-form text in tables, and headers with strong contrast (dark-on-light or light-on-dark — never low-contrast pastels).

**PDFs are the only artifacts.** Do not write CSV, XLSX, HTML, or intermediate files to the audit-output folder. If any scratch file is created during the run, delete it before finishing.

**Two language versions per run.** Every audit produces **two** PDFs — one English (`_EN`) and one Simplified Chinese (`_CH`). Same layout, same data, same charts, same footer stamp; only the language differs. Render both from the same computed figures so they cannot disagree. The PDF engine must use a font that covers CJK glyphs (e.g., Noto Sans CJK SC / Noto Serif CJK SC) — if the font is missing, fail loudly rather than silently output boxes.

**File path and name.** Save each station's audit as:

```
<audit-output-root>/<YYYY>/<YYYY-MM>/<YYYY-MM-DD>/<Station>-<YYYY_MM_DD>-Audit_<YYYYMMDD>_<hh>_<mm>_<Lang>.pdf
```

- `<Station>` — station code in caps (`TK`, `BS`, `BL`).
- `<YYYY_MM_DD>` — the **business date** being audited (underscores).
- `Audit_<YYYYMMDD>_<hh>_<mm>` — the moment the audit was generated, 24-hour local time.
- `<Lang>` — `EN` for English, `CH` for Simplified Chinese. Always produce both in the same run.
- Both date tree folders (`<YYYY>`, `<YYYY-MM>`, `<YYYY-MM-DD>`) refer to the business date, not the generation date.

Example, one run producing two files inside `.../2026/2026-04/2026-04-22/`:

- `TK-2026_04_22-Audit_20260423_14_30_EN.pdf`
- `TK-2026_04_22-Audit_20260423_14_30_CH.pdf`

Never overwrite or delete an older file in that folder. Re-running the audit for the same business date on the same day produces a **new** pair whose timestamp suffix differs, so the user can see every run side-by-side.

**Footer stamp (every page, bottom-right).** Print one of the following, depending on the PDF's language:

- English: `sale-audit v<version> · amended <updated> · generated <YYYY-MM-DD hh:mm>`
- Chinese: `sale-audit v<version> · 修订 <updated> · 生成 <YYYY-MM-DD hh:mm>`

Read `<version>` and `<updated>` from this file's own frontmatter (the `version` and `updated` fields at the top of `SKILL.md`). `<generated>` is the current timestamp at PDF-creation time. The stamp lets the user confirm the report came from the latest skill revision.

**Footer positioning — strict.** The stamp must appear on **every page** of **both** the English and Chinese PDFs, tucked into a thin bottom strip, clearly below every report element. Never let it overlap a table row, chart, page number, or any body line. The bottom reserve is deliberately small (~20 mm) so the report does not leave a large empty strip at the foot of each page.

- Vertical position: baseline **6 mm from the bottom edge** of the page. Measured to the text baseline, not the top of the line.
- Horizontal position: right-aligned to the content's right margin.
- Minimum clearance: at least **10 mm of empty space** between the last content line and the top of the stamp text.
- Size and weight: small (~7–8 pt), regular weight, muted colour (mid-grey, not black) so it does not compete with the report.
- Implementation: render the stamp as a true page-footer region (separate from the content flow), not as a trailing paragraph inside the report body — otherwise it drifts up into content on short pages. Applying the footer via the PDF engine's page-footer / running-footer API is preferred over manual positioning so the 6 mm anchor is consistent across pages.
- The content area must end at least ~20 mm from the bottom edge (6 mm for the footer baseline + stamp line height + 10 mm clearance). If a page lays out in a way that would push content into that zone, **reflow the content to a new page** rather than shrink the bottom margin. Content and stamp must never collide. Do not reserve more than ~20 mm at the bottom — a larger reserve leaves a big empty strip on every page.
- Both language PDFs use the same 6 mm anchor — positioning is identical; only the text content differs (English vs Chinese).

**Section 1 — Inflow breakdown**

Lead with the headline: **Total Inflow = Revenue + CFP Deposit**. Show the single headline number, then split into two clearly separated subsections. The word "Revenue" must never include CFP Deposit; if the Fund Report lumps them together, unpick them here.

**Revenue** (Cash + Merchant + CFP voucher used + BUDI95, per §5.1):
- Revenue total for the date.
- Revenue by business segment (bar or stacked bar).
- Revenue by channel, shown **two ways**:
  - A **pie chart** for proportions.
  - A **channel totals table** with the actual figures, computed from the proof-of-fund slips (not from the Fund Report). Columns: `Channel | Total (RM) | # of slips | % of revenue`. Add a `Total` row. All four channels (Cash, Merchant, CFP voucher used, BUDI95) must appear even if zero for the day. For BUDI95, note in the row what portion is the customer's cash/card payment vs. the receivable claimed from the government via IPTB.

**CFP Deposit** (non-revenue inflow, per §5.2):
- CFP deposit total for the day (sum of all CFP top-up entries on the CFP report).
- Count of top-up transactions.
- Render in a **visually distinct callout** (a different panel colour or a boxed frame, with the label "CFP Deposit — not revenue") so it is impossible to confuse with the Revenue block.

**Section 2 — Proof-of-fund audit table**

**One row per individual slip**, regardless of whether the Fund Report lists that slip individually or rolls several slips into a single aggregated line. Never collapse slips in this table even when the Fund Report collapsed them — this table exists to show the underlying evidence. Use short-form column headers:

| Doc | Type | Amt (RM) | Date✓ | Uniq✓ | Acct✓ | POS✓ | Cleared✓ | In FR | Notes |

`In FR` column values:
- `✓` — slip appears as its own line in the Fund Report.
- `∑` — slip is part of an aggregated Fund Report line (multiple slips summed into one entry). Note which FR line it rolls into.
- `✗` — slip is **not represented** in the Fund Report at all (understatement — automatic finding per §6 rule 12).

Tick / cross per other criterion; one-line note on failures. Immediately below the table, add a small "FR aggregation check" sub-table: for every Fund Report entry that aggregates multiple slips, show the FR line amount vs. the sum of the underlying slips and flag any variance.

**Section 3 — Cash highlight**
Opening cash, closing cash (Fund Report vs. calculated), variance. Highlight any mismatch in red.

**Section 4 — Fuel quantity audit**
Per product: opening qty, delivery qty, sales qty, calculated closing, reported closing, variance. Highlight variances.

**Section 5 — Findings & recommendations**
Bulleted list of every flag, ordered by materiality (financial impact first, control weakness second). End with concrete management actions.

## 8. Workflow

1. Confirm **station(s)** and **date** (default to yesterday if not given).
2. Recall or ask for the three paths in §3 (daily-report root, bank-statement folder, audit-output root). Save any missing ones to memory on first run.
3. List files present vs. missing for that station+date.
4. Run all §6 checks, preserving every intermediate calculation.
5. Render **two** landscape PDFs per §7 — English and Simplified Chinese — from the same computed figures. Create `<audit-output-root>/<YYYY>/<YYYY-MM>/<YYYY-MM-DD>/` if it does not exist (business-date tree, shared by all stations), then save both as `<Station>-<YYYY_MM_DD>-Audit_<YYYYMMDD>_<hh>_<mm>_EN.pdf` and `…_CH.pdf`. Produce no other files.
6. Reply in chat with the 3–5 most material findings and the absolute paths to both saved PDFs.
