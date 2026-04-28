---
name: sale-audit
description: Use this skill whenever the user (Evergreen back-office / management) wants to audit, verify, or check the daily sale submission of a petrol station — TK (Tg. Kapor), BS (Berkat Setia), or BL (Bubul Lama). Triggers include phrases like "audit TK", "audit sale", "check BS sale", "verify fund report", "run daily audit", "daily sale audit for <date>", or any request to reconcile a station's Fund Report against its supporting documents and produce an audit PDF.
version: 0.11.0
updated: 2026-04-28 14:51
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
       <URL>?token=<TOKEN>&value_date=<YYYY-MM-DD>&account=<account>&amount=<RM>&direction=CR
       ```
       The `account` parameter accepts the full 13-digit AmBank number (`8881058618135`), the last-4 (`8135`), or the branded form (`AMB-8135`); the Web App normalises before matching. For Maybank slips today, ingestion is not implemented (`bank-ledger` v0.3.0) — the Web App will return `total_count: 0` for any MBB account, which sale-audit must surface as a finding (not a silent miss). For cheque-funded slips, also pass `&tolerance_days=3` so the Web App searches `TRAN DATE ∈ [value_date, value_date+3]` instead of value_date alone.
    3. **Match interpretation** — fields below come from the doGet response:
       - `total_count == 1` → the slip cleared. Set `Cleared✓ = ✓`. Capture the match's `tran_date` (and if it differs from the audit date, write `cleared T+n`), the `sender_receiver`, and the `payment_ref` in Notes — e.g., `cleared 2026-04-25 — MALINAH BINTI TUTUNG / Pindahan Dana`.
       - `total_count == 0` → no match. Set `Cleared✓ = ✗` with a short reason: `no matching credit on <date>` or `amount/account mismatch`. This is a finding. **For MBB-account slips today, always note `MBB ingestion not implemented in bank-ledger v0.3` so the user understands it's a coverage gap, not a real shortfall.**
       - `total_count > 1` → ambiguous. Set `Cleared✓ = ?` and list each candidate's `account_no`, `amount`, `sender_receiver`, and `tran_time` in Notes; raise an aggregation-flag finding so the user reconciles manually. Multiple identical-amount credits to the same account on the same day usually mean two slips were grouped or one was re-issued.
    4. **Reverse check (unexplained credits).** After processing every slip, GET `<URL>?token=<TOKEN>&value_date=<audit date>&direction=CR` (no `account` or `amount` filter) to list **every** credit that landed on the audit date. Subtract the rows you already consumed in step 3 (match by `account_no` + `amount` + `tran_time`). Anything left over is an **unexplained credit** — raise as a finding with the row's `account_no`, `amount`, `sender_receiver`, `payment_ref` (potential undeclared revenue or misposted transfer).
    5. **Network failures during the slip loop.** If the Web App returns an error mid-loop, retry once with a 5-second backoff. If still failing, fall back to ping-failure behaviour for the remaining slips (set `Cleared✓` blank, finding noted), and continue the audit. Never let a single network blip kill an entire daily audit.
    6. **No file-folder logic.** The bank-statement folder is gone. Do not look for, accept paths to, or attempt to parse PDF / image bank statements. The Web App is the only clearance source.
12. **Fund Report aggregation integrity.** Staff sometimes sum several slips into a single Fund Report line (e.g., three cash-deposit slips reported as one "Cash deposits RMx" figure). For every Fund Report entry that aggregates more than one underlying slip, the sum of the underlying slips must equal the Fund Report line — flag any variance. Every individual slip must also appear somewhere in the Fund Report, either as its own line or as part of an aggregated line; any slip missing from the Fund Report entirely is an automatic finding (understatement). Audit always from the slips, never let the Fund Report's aggregated view suppress an individual row in the proof-of-fund table (see §7 Section 2).

## 7. Output — landscape PDF

**The visual layout is frozen in code, not prose.** Every audit PDF is rendered by the bundled deterministic renderer at `render/render-audit.py` from a single audit-data JSON object plus the templates in `templates/`. Any two runs of the renderer over the same JSON produce byte-identical PDFs. The LLM never writes HTML or CSS — it only computes the audit data.

Files involved (all inside this skill folder):

| Path | Purpose |
|---|---|
| `templates/audit.html.j2`         | Jinja2 page template — the structural layout. |
| `templates/audit.css`             | Brand palette, typography, table styling, donut chart, footer position. |
| `templates/labels-en.json`        | All English visible strings. |
| `templates/labels-cn.json`        | All Simplified Chinese visible strings. |
| `templates/sample-data.json`      | Worked example of the data contract (BL audit 2026-04-25). |
| `templates/audit-data.schema.md`  | Documented JSON contract — the LLM's output target. |
| `render/render-audit.py`          | The renderer. Takes JSON + lang flag, produces HTML or PDF. |

**To change the look:** edit `audit.css` only. Every future audit picks up the change with no logic edits.
**To change a label:** edit `labels-en.json` / `labels-cn.json`.
**To change the structure (add a row, reorder a column):** edit `audit.html.j2`.
**To translate / extend a section:** add a new label key, then reference it in the template.

**PDFs are the only artifacts.** Do not write CSV, XLSX, intermediate HTML, or scratch files to the audit-output folder.

**Two language versions per run.** Every audit produces **two** PDFs — one English (`_EN`), one Simplified Chinese (`_CH`) — by invoking the renderer twice from the same JSON, once with `--lang en` and once with `--lang cn`. The PDF engine must use a font covering CJK glyphs (Noto Sans CJK SC or equivalent). If the font is missing, the renderer fails loudly rather than silently emitting boxes.

**File path and name.** Save each station's audit as:

```
<audit-output-root>/<YYYY>/<YYYY-MM>/<YYYY-MM-DD>/<Station>-<YYYY_MM_DD>-Audit_<YYYYMMDD>_<hh>_<mm>_<Lang>.pdf
```

- `<Station>` — station code in caps (`TK`, `BS`, `BL`).
- `<YYYY_MM_DD>` — the **business date** being audited (underscores).
- `Audit_<YYYYMMDD>_<hh>_<mm>` — the moment the audit was generated, 24-hour local time.
- `<Lang>` — `EN` for English, `CH` for Simplified Chinese. Always produce both in the same run.
- Both date tree folders refer to the **business date**, not the generation date.

Never overwrite or delete an older file in that folder. Re-running the audit on the same business date produces a **new** pair whose `Audit_…` timestamp differs, so every run is preserved side-by-side.

**Footer stamp** is rendered automatically by the template on every page, bottom-right:

- English: `sale-audit v<version> · amended <updated> · generated <YYYY-MM-DD hh:mm>`
- Chinese: `sale-audit v<version> · 修订 <updated> · 生成 <YYYY-MM-DD hh:mm>`

The renderer reads `version:` and `updated:` from this `SKILL.md`'s frontmatter and stamps `generated_at` from `datetime.now()` at run time, so all three fields are dynamic — every audit's footer reflects the actual skill release that produced it. Footer baseline sits at 3 mm above the page edge; the bottom 17 mm of every page is reserved for it.

### 7.1 Render workflow

1. Compute every figure required by the JSON contract in `templates/audit-data.schema.md` (sections 1, 2, 3, 4, 4b, 5, 6 plus meta strip and footer-stamp inputs).
2. Write the JSON to a scratch path (e.g., `/tmp/<station>-<date>-audit.json`). Validate that all required fields are present.
3. Render English:
   ```
   python <skill_dir>/render/render-audit.py --data <scratch>.json --lang en --out <out>_EN.pdf
   ```
4. Render Chinese:
   ```
   python <skill_dir>/render/render-audit.py --data <scratch>.json --lang cn --out <out>_CH.pdf
   ```
5. Delete the scratch JSON. The PDFs are the only retained outputs.

### 7.2 Section content — what data each section needs

The renderer fills the template; the LLM's job is to produce the data values. For every section, populate every field documented in `audit-data.schema.md`. Notes that are content-level (not structural):

- **Section 1 inflow breakdown.** Three headline figures — Total Inflow, Revenue, CFP Deposit — must always reconcile (Total = Revenue + CFP Deposit). The four revenue channels (Cash, Merchant, CFP voucher used, BUDI95) must always appear even if zero. For BUDI95 the `notes` field must split customer-paid portion vs. IPTB-claimable portion.
- **Section 1 fuel-delivery callout.** When a fuel delivery occurred, set `delivery.occurred = true` and put invoice / ticket / SN in `delivery.summary`. Otherwise omit the object or set `occurred = false`.
- **Section 2 proof-of-fund.** **One row per individual slip** — never collapse multiple slips into a single row even when the Fund Report aggregates them. `cleared.kind` is one of `verified` / `deferred` / `missing`. `in_fr` is `ok` / `agg` / `missing`. The column-key legend is rendered automatically by the template using strings from `labels-{en,cn}.json`. The FR-aggregation sub-table is omitted when `fr_aggregation` is empty.
- **Section 3 cash highlight.** Six rows in this order: Opening cash, Cash revenue (POS), CFP cash top-up, BuraqMart cash, Safeguards (CDM) pick-up, Closing cash. Set `is_total: true` on Closing cash; set `is_variance: true` on any row where `var != 0`. The optional `footer_note` is free text below the table for context (e.g., explaining a misposted FR cell).
- **Section 4 fuel quantity.** One row per fuel product. The L-fields are pre-formatted strings (`"17,176"`, `"DELIV 16,500"`) so qualifiers like `*` or `DELIV` come through verbatim.
- **Section 4b POS tally.** Each row sets `passed: true | false`; the renderer paints failed rows red and styles the result text accordingly. Include at minimum: GreenPOS fuel total, CFP voucher vs GreenPOS, Merchant fuel, Autocount Mart, BUDI95 sales (POS).
- **Section 5 §4 checklist.** Single HTML string (`<strong>` allowed for `Present:` / `Partial:` / `Missing:` / `N/A:` keywords) referencing the file list in §4.
- **Section 6 findings.** Ordered by materiality (financial impact first, control weakness second, presentation issues last). **Always include a closing finding for each of `§6.11` (clearance status) and `§6.12` (aggregation integrity)**, even when clean — so the reader can confirm those checks ran.

## 8. Workflow

1. Confirm **station(s)** and **date** (default to yesterday if not given).
2. Recall or ask for the four reference values in §3 (daily-report root, bank-ledger Web App URL, bank-ledger Web App token, audit-output root). Save any missing ones to memory on first run. **Ping the Web App** (token-only GET, expect `ok:true`) to populate the meta strip's "Bank ledger" status before the run continues — record the result so §6 rule 11 can reuse it without re-pinging.
3. List files present vs. missing for that station+date.
4. Run all §6 checks, preserving every intermediate calculation.
5. Build the audit-data JSON object per §7's data contract (`templates/audit-data.schema.md`). Every required field must be populated; partial data is a bug, not a degraded output. Write the JSON to a scratch path and run the renderer twice from the same JSON — once with `--lang en --out …_EN.pdf` and once with `--lang cn --out …_CH.pdf` — into `<audit-output-root>/<YYYY>/<YYYY-MM>/<YYYY-MM-DD>/<Station>-<YYYY_MM_DD>-Audit_<YYYYMMDD>_<hh>_<mm>_<Lang>.pdf`. Create the date tree if missing. Delete the scratch JSON when both PDFs are written. Produce no other files.
6. Reply in chat with the 3–5 most material findings and the absolute paths to both saved PDFs.
