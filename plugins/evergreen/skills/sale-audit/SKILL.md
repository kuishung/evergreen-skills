---
name: sale-audit
description: Use this skill whenever the user (Evergreen back-office / management) wants to audit, verify, or check the daily sale submission of a petrol station — TK (Tg. Kapor), BS (Berkat Setia), or BL (Bubul Lama). Triggers include phrases like "audit TK", "audit sale", "check BS sale", "verify fund report", "run daily audit", "daily sale audit for <date>", or any request to reconcile a station's Fund Report against its supporting documents and produce an audit PDF.
version: 0.10.0
updated: 2026-04-26 21:01
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

On first run, ask the user for the inputs below and save each to memory as a `reference` memory so they are never asked again:

1. **Daily-report root path** — per-station, per-date folders containing the files in §4.
2. **Bank-ledger Web App URL** — the deployed `bank-ledger` Apps Script Web App. Format: `https://script.google.com/macros/s/AKfycb.../exec`. Set up via the `bank-ledger` skill's §7. Used by §6 rule 11 to verify clearance from any environment (your laptop, the Win 11 server, scheduled Cowork) without Google credentials. Replaces the old "bank-statement folder" path.
3. **Bank-ledger Web App token** — the shared-secret string stored as the Apps Script's `WEB_APP_TOKEN` script property. Required on every request to the Web App. Treat as a password.
4. **Audit-output root** — a **single** folder shared by all stations. The skill creates the date tree inside it as `<audit-output-root>/<YYYY>/<YYYY-MM>/<YYYY-MM-DD>/` and writes every station's PDF into the same leaf folder, so the user never has to switch directories between stations. If an existing memory points to a per-station path, treat only its parent as the new root, confirm with the user once, and update the memory.

Before reusing any remembered value, verify it still resolves: paths via filesystem check, Web App by issuing a token-only ping (`?token=<TOKEN>`) and confirming `{"ok":true,"ping":"bank-ledger",...}`. If anything fails, ask once and update the memory. If the user has not answered for a given input yet, ask for it at the start of the first audit that needs it — do not proceed without it.

Expected daily layout: `<daily-report-root>/<station>/<YYYY-MM-DD>/…`

> Migration note: the old `bank-statement folder path` memory is obsolete as of `sale-audit` v0.10.0. The `bank-ledger` Apps Script (now populating a Google Sheet from MBB / AmBank email alerts every 30 minutes) is the source of truth for clearance verification. If a stale folder-path memory exists, drop it and replace with items 2 and 3 above.

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
11. **Funds cleared.** Clearance is verified by querying the **bank-ledger Web App** (§3 items 2–3) which is fronted by the same Apps Script that ingests MBB / AmBank email alerts into the master Google Sheet every 30 minutes. The Web App returns structured JSON, so there is no OCR, no overlap, no folder coverage problem.

    1. **Connectivity ping.** Before any per-slip lookup, GET `<URL>?token=<TOKEN>` (no other params). Expected response: `{"ok":true,"ping":"bank-ledger","row_count":<int>}`. If the response is missing, non-200, or `ok: false`, the ledger is **unreachable** for this run — do not abort; instead leave every slip's `Cleared✓` blank and raise §6.11-status finding `clearance verification deferred — bank-ledger Web App unreachable: <reason>`. A ping failure must never block the rest of the audit (§6 rules 1–10 still run).
    2. **Per-slip query.** For every proof-of-fund slip, GET:
       ```
       <URL>?token=<TOKEN>&value_date=<YYYY-MM-DD>&account=<MBB-NNNN or AMB-NNNN>&amount=<RM>&direction=CR
       ```
       For cheque-funded slips, also pass `&tolerance_days=3` so the Web App searches T..T+3 instead of T only.
    3. **Match interpretation:**
       - `total_count == 1` → the slip cleared. Set `Cleared✓ = ✓`. Capture the matched `txn_id` and (if relevant) the `posting_date` in Notes (e.g., `cleared T+1 — txn 8a3f…`).
       - `total_count == 0` → no match. Set `Cleared✓ = ✗` with a short reason: `no matching credit on <date>` or `amount/account mismatch`. This is a finding.
       - `total_count > 1` → ambiguous. Set `Cleared✓ = ?` and list the candidate `txn_id`s in Notes; raise an aggregation-flag finding so the user reconciles manually. Multiple identical-amount credits to the same account on the same day usually mean two slips were grouped or one was re-issued.
    4. **Reverse check (unexplained credits).** After processing every slip, GET `<URL>?token=<TOKEN>&value_date=<audit date>&direction=CR` (no `account` or `amount` filter) to list **every** credit that landed on the audit date. Subtract the `txn_id`s you already consumed in step 3. Anything left over is an **unexplained credit** — raise as a finding with the txn details (potential undeclared revenue or misposted transfer).
    5. **Network failures during the slip loop.** If the Web App returns an error mid-loop, retry once with a 5-second backoff. If still failing, fall back to ping-failure behaviour for the remaining slips (set `Cleared✓` blank, finding noted), and continue the audit. Never let a single network blip kill an entire daily audit.
    6. **No file-folder logic.** The bank-statement folder is gone. Do not look for, accept paths to, or attempt to parse PDF / image bank statements. The Web App is the only clearance source.
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

**Footer positioning — strict.** The stamp must appear on **every page** of **both** the English and Chinese PDFs, tucked into a thin bottom strip, clearly below every report element. Never let it overlap a table row, chart, page number, or any body line. The bottom reserve is deliberately small (~15 mm) so the report does not leave a visible empty strip at the foot of each page.

- Vertical position: baseline **2 mm from the bottom edge** of the page. Measured to the text baseline, not the top of the line.
- Horizontal position: right-aligned to the content's right margin.
- Minimum clearance: at least **10 mm of empty space** between the last content line and the top of the stamp text.
- Size and weight: small (~7–8 pt), regular weight, muted colour (mid-grey, not black) so it does not compete with the report.
- Implementation: render the stamp as a true page-footer region (separate from the content flow), not as a trailing paragraph inside the report body — otherwise it drifts up into content on short pages. Applying the footer via the PDF engine's page-footer / running-footer API is preferred over manual positioning so the 2 mm anchor is consistent across pages.
- The content area must end at least ~15 mm from the bottom edge (2 mm for the footer baseline + stamp line height + 10 mm clearance). If a page lays out in a way that would push content into that zone, **reflow the content to a new page** rather than shrink the bottom margin. Content and stamp must never collide. Do not reserve more than ~15 mm at the bottom — a larger reserve leaves a visible empty strip on every page.
- Both language PDFs use the same 2 mm anchor — positioning is identical; only the text content differs (English vs Chinese).
- Note: 2 mm is tight against the page edge. PDFs are intended for digital review; if anyone physically prints them, most printers' unprintable bottom margin (~5 mm) may clip the stamp — that is acceptable since the stamp is for traceability of the digital file.

### 7.1 Visual template — match this design exactly

Every audit PDF must follow the same visual grammar so any Evergreen reviewer can read any audit at a glance. **Reference layout: the BL audit generated at `2026-04-24 23:59` (`BL-2026_04_23-Audit_20260424_23_59_EN.pdf`).** The user has confirmed that PDF as the canonical template. Match its structure — page anatomy, multi-column splits, palette, typography, and decoration — on every future run, EN and CH alike.

**Page setup**
- A4 landscape (297 × 210 mm).
- Margins: ~8 mm left, ~8 mm right, ~6 mm top, ~15 mm bottom reserve (footer stamp baseline at 2 mm + line height + 10 mm clearance, per the rules above).
- Background: very pale cream / warm off-white (`#F8F4E8` or near-equivalent).

**Color palette** — use these consistently:

| Use                                          | Hex (or near-equivalent) |
|----------------------------------------------|--------------------------|
| Primary brand band; dark accent panels       | `#0E5D3F` deep forest green |
| Section header band background               | `#BFDFC8` light pastel green |
| Warning / "not revenue" callout background   | `#FFF3CC` soft yellow |
| Warning / "not revenue" callout border       | `#E0A030` amber |
| Variance / negative figure                   | `#D72E2E` red |
| Footer stamp text                            | `#7A7A7A` mid-grey |
| Body text                                    | `#1A1A1A` near-black |
| Muted text / captions                        | `#5A5A5A` charcoal |
| Pie slice — Cash                             | `#D9A23B` mustard |
| Pie slice — Merchant                         | `#9CB6A6` sage |
| Pie slice — CFP voucher used                 | `#264E3F` deep teal-green |
| Pie slice — BUDI95                           | `#B65A28` burnt orange |

**Typography**
- Sans-serif throughout. EN: system Inter / Helvetica / Arial fallback. CH: Noto Sans CJK SC.
- Headline panel numbers: bold, ~24–28 pt.
- Section header band text: bold, ~11–12 pt; near-black on light green, **or** white on dark green.
- Table column headers: bold, ~10 pt, white on dark green (`#0E5D3F`).
- Body / table cells: regular, ~9–10 pt.
- Footer stamp: regular, ~7–8 pt, mid-grey (per the rules above).

**Element styles**
- **Section header bands** — full-width strip ~7–8 mm tall, light-green background, bold dark text aligned ~8 mm from the left edge. Every section starts with one.
- **Cards** — 1 px solid border in dark green, ~5–6 mm internal padding, white card background. Optional header row in dark green with white text (e.g., "Revenue — RM xx,xxx.xx").
- **Tables** — dark-green header row with white text; body rows alternating white / very-faint-green; bold "Total" row at the bottom; right-align all numeric columns; ~9–10 pt body.
- **Headline panel** — full-width dark-green band; three big white callout numbers separated by `=` and `+` glyphs, with small white captions above each amount.
- **Alert card** — amber border + soft-yellow fill + leading ⚠ icon. Used **only** for the CFP Deposit block and other "not revenue / pending" notices (e.g., the deferred-clearance strip in Section 2).
- **Pie chart** — flat 2D pie (not donut); legend on the right showing channel name + percent.
- **Inline share bars** — thin coloured bars rendered inside a table cell, width = share %; used in the segment table of Section 1.

**Multi-column layout map**

| Block                                                         | Width split |
|---------------------------------------------------------------|-------------|
| Top title band + meta strip                                   | Full width  |
| Section 1 headline panel                                      | Full width  |
| Section 1: Revenue card  /  CFP Deposit alert card            | ~65% / ~35% |
| Section 1: Channel-totals table  /  By-channel pie chart      | ~70% / ~30% |
| Section 2 (proof-of-fund table + FR aggregation sub-table)    | Full width  |
| Section 3 Cash highlight  /  Section 4 Fuel quantity          | ~50% / ~50% |
| Section 4b POS tally                                          | Right ~50%, beneath Section 4 |
| Section 5 §4 checklist                                        | Full width  |
| Section 6 Findings & recommendations                          | Full width  |

### 7.2 Top-of-page header

**Title band** — full width, dark-green (`#0E5D3F`) background, ~12–14 mm tall, white bold text. Format:

- English: `<STATION-NAME> (<CODE>) — DAILY SALE AUDIT · <YYYY-MM-DD>`
- Chinese: `<中文站名> (<CODE>) — 每日销售审计 · <YYYY-MM-DD>`

(For example: `BUBUL LAMA (BL) — DAILY SALE AUDIT · 2026-04-23`.)

**Meta strip** — immediately below the title band, light-grey background, ~7–8 mm tall, with bold labels and regular-weight values, separated by ample whitespace. Fields, in order:

| Order | Label (EN)     | Label (CH)  | Value                                                                                 |
|-------|----------------|-------------|---------------------------------------------------------------------------------------|
| 1     | Station        | 站           | Station code (`TK` / `BS` / `BL`)                                                     |
| 2     | Business date  | 业务日期     | Audited date, `YYYY-MM-DD`                                                            |
| 3     | Prepared by    | 制作人       | Person on shift / Fund Report submitter, if known; `—` if unknown                     |
| 4     | Bank ledger    | 银行账本     | Web App status: `connected (N rows)`, `unreachable: <reason>`, or `not configured`    |

**Section 1 — Inflow breakdown**

Layout:

1. **Headline panel** (full-width dark-green band, white text), three columns side-by-side:
   - "Total Inflow"  →  large bold figure (e.g., `RM 68,243.21`)
   - "= Revenue"     →  large bold figure
   - "+ CFP Deposit (non-revenue)"  →  large bold figure

   One small caption beneath the panel: `Total Inflow = Revenue + CFP Deposit (non-revenue)`.

2. **Revenue card** (left ~65 %), dark-green border, header row "Revenue — RM <total>". Inside:
   - Segment table — columns `Segment | RM | Share`. Rows: `Fuel`, `Buraqmart`, `Rental / iBing` (or station-equivalent), bold `Total` row at the bottom. The `Share` column renders an inline horizontal bar whose width equals the segment's share percentage, with the percentage label.
   - One italic footer line, ~9 pt, summarising fuel volume × price (e.g., `Petrol 9,840.43 L × RM 3.87; Diesel 2,946.30 L × RM 2.15.`) plus, on its own clause, the BUDI95 claimable amount (e.g., `BUDI95 claimable RM 11,552.40.`). If a fuel delivery occurred, append `Fuel delivery today.`

3. **CFP Deposit alert card** (right ~35 %), amber border + soft-yellow fill + ⚠ icon. Header `CFP Deposit — not revenue`. Inside:
   - Big bold amount (e.g., `RM 23,724.00`).
   - One-line caption (e.g., `All cash — zero bank transfer to PetrolFox today.`).
   - Sub-table — columns `Sub | Amt | #`. Rows: `Cash top-up`, `Bank transfer top-up`, bold `Total` row.

4. **Revenue — channel totals from slips** (left ~70 %, below the two cards). Table with columns `Channel | RM | # slips | % | Notes`. Rows: `Cash`, `Merchant`, `CFP voucher used`, `BUDI95 (full pump price)`, bold `Total` row. The four channels must always appear even if zero for the day. The Notes column carries one short clarification per channel — for BUDI95, split customer-paid portion vs. IPTB-claimable portion.

5. **By channel pie chart** (right ~30 %, beside the channel-totals table). Flat 2D pie, four slices in the palette colours above, legend on the right showing channel name + percent.

**Section 2 — Proof-of-fund**

Section header band: `Section 2 — Proof-of-fund (<N> slips · <aggregation note>)` — e.g., `(23 slips · all individual, no aggregation)`.

If clearance verification is deferred (e.g., bank-statement coverage missing per §6 rule 11), insert an amber/yellow alert strip immediately under the header summarising why the `Cleared✓` column is blank and citing `§6.11 deferred`.

Optional one-paragraph note then summarises recurring Fund-Report exceptions (e.g., persistent doc-number bugs) and confirms the §6.12 aggregation status.

Then the **proof-of-fund table**, full-width, **one row per individual slip**:

| Doc | Type | Amt (RM) | Date✓ | Uniq✓ | Acct✓ | POS✓ | Cleared✓ | In FR | Notes |

`In FR` values: `✓` individual · `∑` part of an aggregated FR line · `✗` missing. Tick / cross per criterion, one-line note on failures.

**Column key (legend)** — render this **inside the PDF**, immediately under the proof-of-fund table, as a small light-grey caption strip in ~8 pt regular text so any reviewer can read the columns without leaving the report. Match the language of the PDF.

English version:

> **Date✓** slip's printed date matches the audited business date (§6 r.4).
> **Uniq✓** slip is not a duplicate of any other proof-of-fund document (§6 r.5).
> **Acct✓** deposit landed in one of the six approved Maybank/AmBank accounts (§2, §6 r.6).
> **POS✓** slip's amount and channel reconcile to the POS system totals (§6 r.7–8).
> **Cleared✓** credit confirmed in the bank-ledger Google Sheet (queried via the Apps Script Web App) for the audited date — or T+1..T+3 for cheques (§6 r.11). Blank when the ledger is unreachable.
> **In FR** how the slip is represented in the Fund Report: `✓` individual line · `∑` part of an aggregated line · `✗` missing entirely (§6 r.12).

Simplified Chinese version:

> **日期✓** 收据日期与审核业务日期相符（§6 r.4）。
> **唯一✓** 此收据非他张证据的重复（§6 r.5）。
> **账户✓** 款项进入§2列出的六个核准 Maybank/AmBank 账户之一（§6 r.6）。
> **POS✓** 收据金额与渠道与 POS 系统总额相符（§6 r.7–8）。
> **已清算✓** 银行账本（Google 表格 / Apps Script Web App）已确认款项于审核日入账，支票允许 T+1 至 T+3（§6 r.11）。Web App 不可达时此栏留空。
> **在FR表** 此收据在资金报告中的呈现方式：`✓` 单独列出 · `∑` 属合并条目 · `✗` 完全缺漏（§6 r.12）。

Immediately below the legend, the **FR aggregation sub-table** (only rows that aggregate): `FR line | FR amount | Underlying slips | Sum of slips | Variance`. If no aggregated FR lines exist, omit the sub-table and the section header note already says "all individual, no aggregation".

**Section 3 — Cash highlight** (left ~50 %)

Table with columns `Item | FR | Computed | Var`. Rows in this order: `Opening cash`, `Cash revenue`, `CFP cash top-up`, `CDM deposited`, `Safeguards pick-up`, **bold** `Closing cash` (red if any variance, with the variance figure shown in the `Var` column; otherwise green tick or em-dash).

**Section 4 — Fuel quantity** (right ~50 %)

Table with columns `Product | Open | Deliv. | Sales (L) | Close | Var`. One row per fuel product (e.g., `Petrol`, `Diesel`). When a delivery occurred, the `Deliv.` cell shows `DELIV` (with the volume in the line below or in the body as appropriate). Highlight any non-zero `Var` in red.

**Section 4b — POS tally** (right ~50 %, beneath Section 4)

Table with columns `Check | POS | FR | Result`. Rows include at minimum:
- `GreenPOS fuel`
- `CFP vs PetrolFox`
- `Merchant fuel`
- `Autocount` (Buraqmart Autocount POS)
- additional system-reconciliation rows where available.

`Result` column shows `✓`, `✓ Verified`, or `✗ <variance description>`.

**Section 5 — §4 checklist**

Single-paragraph file-presence summary referencing §4 of this skill (Required daily files). Format:

`Present: <list>. Partial: <list>. Missing: <list>. N/A: <list>.`

**Section 6 — Findings & recommendations**

Bulleted list. One bullet per finding, ordered by materiality (financial impact first, control weakness second, presentation/data-quality issues last). Each bullet follows this exact form:

`FINDING <N> — <bold short title>.` Then a body sentence. End with `Action:` (also bold) followed by the concrete management action.

Always close with a finding for each of these statuses, even when clean (so the reader can confirm the check ran):
- `§6.11` — clearance verification status (verified / deferred + reason).
- `§6.12` — aggregation integrity status (clean / variances flagged).

## 8. Workflow

1. Confirm **station(s)** and **date** (default to yesterday if not given).
2. Recall or ask for the four reference values in §3 (daily-report root, bank-ledger Web App URL, bank-ledger Web App token, audit-output root). Save any missing ones to memory on first run. **Ping the Web App** (token-only GET, expect `ok:true`) to populate the meta strip's "Bank ledger" status before the run continues — record the result so §6 rule 11 can reuse it without re-pinging.
3. List files present vs. missing for that station+date.
4. Run all §6 checks, preserving every intermediate calculation.
5. Render **two** landscape PDFs per §7 — English and Simplified Chinese — from the same computed figures. Both PDFs must conform to the visual template in §7.1 (colours, typography, multi-column layout) and the section-by-section structure in §7.2 onwards (Sections 1, 2, 3, 4, 4b, 5, 6 in that order, with the title band + meta strip on top and the version-stamp footer on every page). Create `<audit-output-root>/<YYYY>/<YYYY-MM>/<YYYY-MM-DD>/` if it does not exist (business-date tree, shared by all stations), then save both as `<Station>-<YYYY_MM_DD>-Audit_<YYYYMMDD>_<hh>_<mm>_EN.pdf` and `…_CH.pdf`. Produce no other files.
6. Reply in chat with the 3–5 most material findings and the absolute paths to both saved PDFs.
