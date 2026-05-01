---
name: sale-audit
description: Use this skill whenever the user (Evergreen back-office / management) wants to audit, verify, or check the daily sale submission of a petrol station — TK (Tg. Kapor), BS (Berkat Setia), or BL (Bubul Lama). Triggers include phrases like "audit TK", "audit sale", "check BS sale", "verify fund report", "run daily audit", "daily sale audit for <date>", or any request to reconcile a station's Fund Report against its supporting documents and produce an audit PDF.
version: 0.16.0
updated: 2026-05-01 18:00
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
2. **Bank-ledger Web App URL** — the deployed `bank-ledger` Apps Script Web App. Format: `https://script.google.com/macros/s/AKfycb.../exec`. Set up via the `bank-ledger` skill's §7. Used by §6 rule 11 as the **primary** clearance path (interactive runs on machines with HTTPS access to `script.google.com`). Replaces the old "bank-statement folder" path.
3. **Bank-ledger Web App token** — the shared-secret string stored as the Apps Script's `WEB_APP_TOKEN` script property. Required on every request to the Web App. Treat as a password.
4. **Bank-ledger local CSV path** — absolute filesystem path to `bank-ledger.csv` (e.g., `C:\Users\<you>\My Drive\Evergreen\BankLedger\bank-ledger.csv`). Written by the bank-ledger Apps Script's `exportLedgerForLocalSync()` (see bank-ledger SKILL.md §6.1) and synced to the local disk by Google Drive for Desktop. **This is the §6 rule 11 fallback** — used whenever the Web App is unreachable (e.g., Cowork's scheduled-task sandbox blocks `script.google.com`). Required for unattended runs; optional for purely interactive use.
5. **Audit-output root** — a **single** folder shared by all stations. The skill creates the date tree inside it as `<audit-output-root>/<YYYY>/<YYYY-MM>/<YYYY-MM-DD>/` and writes every station's PDF into the same leaf folder, so the user never has to switch directories between stations. If an existing memory points to a per-station path, treat only its parent as the new root, confirm with the user once, and update the memory.

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
4. **Date match — read the date off the slip image.** Every proof-of-fund document must bear the same date as the Fund Report. The "date" is the **transaction date printed on the slip image itself** — Maybank/AmBank CDM receipt date, IFT settlement date, TT confirmation timestamp, G4S courier voucher date, cheque date. Never use the filename's date prefix or the FR row's date as a substitute. If the filename's date and the slip's printed date disagree, the printed date wins and raise a finding for the discrepancy. Reject any slip whose printed date is earlier than the audit business date — that is staff padding today's revenue with an older deposit.
5. **Distinct documents — compare slip image content, not filenames.** No two proof-of-fund documents may be identical or duplicated. Compare slips by the **printed transaction reference + amount + timestamp** read off the slip image — never by filename, document index in the folder, or FR row order. Two slips with different filenames that point to the same scanned receipt count as one slip plus a finding; a single filename containing two distinct slip pages counts as two slips. If the printed transaction reference is illegible, raise a finding requiring a clearer image — never assume uniqueness from filename divergence.
6. **Correct account — read it off the slip, never infer.** For every proof-of-fund slip, the destination account is determined **only** by reading the **account number printed on the slip image** and matching it to one of the six accounts in §2. Do **not** infer the bank from filename text, FR section label (e.g. "We Direct Bank-in"), station-banking conventions, prior memory, or shortcut assumptions — these are unreliable and have produced wrong classifications in the past. Render the actual account in the PDF's `Acct` column as bank + last-4 (e.g. `MBB 5366`, `AMB 8146`), not generic labels like `MBB (CDM)`. If the printed account number is illegible, mark `Acct = ?`, set `Cleared✓ = ✗`, and raise a §6 finding requiring a clearer slip image — never guess. A slip whose printed account is **outside** the six approved accounts in §2 is an automatic finding.
6b. **Slip type and channel — read from slip content, never from filename or FR.** A slip's type (CDM cash deposit, IFT merchant settlement, TT instant transfer, CFP voucher consumption, G4S Safeguards courier voucher, cheque) and its revenue channel (Cash / Merchant / CFP voucher / BUDI95 / TT-NonCFP / TT-CFP) are determined **only** from the slip image's printed content — bank logo and receipt header for CDM and IFT, app branding for e-wallet TT, voucher format for G4S, redemption line for CFP. Never classify a slip by its filename text (e.g. `SAFEGUARDS-...`, `TTCFP-...`), the FR section it appears under (e.g. "We Direct Bank-in"), or the document-number convention. The PDF's `Type` column must reflect what the slip itself prints; the §7 Section 1 channel mapping must follow from that printed type, not from the FR's classification. If the slip's content is unreadable, mark type as `?`, set `Cleared✓ = ✗`, and raise a finding requiring a clearer image.
7. **POS tally.** GreenPOS, Autocount POS, and iBing FeedMePOS totals (system-generated → source of truth) must match the Fund Report totals.
8. **Channel tally.** Per-channel revenue in proof-of-fund must match the per-channel split in the POS systems.
9. **CFP vs. GreenPOS voucher.** Sum of the CFP report's **voucher-usage lines only** (redemptions against pre-paid balance) must tally with the GreenPOS voucher line. CFP top-ups are deposits (§5.2) and are **excluded** from this tally — if a day's "CFP total" matches only when top-ups are included, someone has mis-classified a deposit as revenue.
10. **Fuel quantity.** Opening fuel + deliveries − sales = closing fuel. Reconcile against the fuel quantity records and delivery orders, per product.
11. **Funds cleared.** Clearance is verified by querying the **bank-ledger Web App** (§3 items 2–3) — fronted by the same Apps Script that ingests AmBank email-attached daily statement CSVs into the master Google Sheet. The Web App returns structured JSON, so there is no OCR, no overlap, no folder coverage problem. When the Web App is unreachable (e.g., a sandboxed scheduled-task environment that blocks `script.google.com`), the skill **falls back automatically** to a local CSV mirror of the same Sheet (§3 item 4), written by the bank-ledger Apps Script after every successful daily ingestion and synced to disk via Google Drive for Desktop. The fallback uses the same matching logic and produces the same `Cleared✓` results — only the data-fetch path differs.

    1. **Connectivity ping.** Before any per-slip lookup, GET `<URL>?token=<TOKEN>` (no other params). Expected response: `{"ok":true,"ping":"bank-ledger","row_count":<int>}`. If the response is missing, non-200, or `ok: false`, the Web App is **unreachable** for this run — proceed to the **CSV fallback** in step 1b, do **not** defer immediately and do **not** abort the audit (§6 rules 1–10 still run regardless).
    1b. **CSV fallback.** If the Web App ping fails, look for the local CSV at the path saved as §3 item 4. If the file exists and its modified time is within the last 36 hours (acceptable since the upstream Apps Script export runs once per daily ingestion at ~06:00):
       - Read the file with Python's stdlib `csv` module — no `pip install` required, works in any sandbox.
       - Filter rows where direction (parsed from the `\bCR\b` / `\bDR\b` token in `TRAN DESC`) is `CR` and `TRAN DATE` (DD/MM/YYYY) equals the audit date (or T+1..T+3 for cheques).
       - Apply the same per-slip matching as the Web App (account, amount ±0.01).
       - Set `Cleared✓` accordingly — verified results are **authoritative**, equal in standing to a Web App match. Add a §6.11 status finding noting the source: `clearance verified via local CSV (mtime: <YYYY-MM-DD HH:MM>); Web App unreachable from this environment`.
       - If the CSV is missing, older than 36 hours, or empty, defer §6.11 with a structured note: `clearance verification deferred — Web App unreachable AND local CSV <missing/stale at HH:MM>`.
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

**Footer stamp** is rendered automatically by the template on **every** page, bottom-right (single source of truth — declared once in the template as a `position: running(footer)` element, replayed by the CSS `@page @bottom-right` rule on every printed page):

- English: `sale-audit v<version> · bank-ledger v<bl-version> · generated <YYYY-MM-DD hh:mm>`
- Chinese: `sale-audit v<version> · bank-ledger v<bl-version> · 生成 <YYYY-MM-DD hh:mm>`

The renderer reads `version:` from this `SKILL.md`'s frontmatter for the sale-audit version, `version:` from the **sibling** `../bank-ledger/SKILL.md` frontmatter for the bank-ledger version (so the user can tell at a glance which clearance pipeline produced the day's `Cleared✓` results), and stamps `generated_at` from `datetime.now()` at run time. The amended date is **not** in the footer — the version number alone identifies the release. Footer baseline sits at 3 mm above the page edge; the bottom 17 mm of every page is reserved for it.

### 7.1 Render workflow — two steps, deterministic, environment-portable

PDF rendering is split in two so the pipeline runs in any environment that has Python + Jinja2, regardless of whether `weasyprint` is installed:

1. **JSON → HTML** via `render/render-audit.py` (Jinja2 only, zero PDF dependencies). The renderer reads `templates/audit.css` and **inlines it** into the HTML as a `<style>` block; the produced HTML is therefore fully self-contained and does not depend on any sibling file. **Do not** re-introduce a `<link rel="stylesheet" href="audit.css">` in the template — when the scratch HTML is handed to the PDF rasterizer, that relative href fails to resolve and the result is an unstyled "plain" PDF (this regression hit on 2026-05-01 between v0.14.0 and v0.15.0; the inlining fix is v0.15.1).
2. **HTML → PDF** via the `anthropic-skills:pdf` skill (already available in every Claude environment, including sandboxed Cowork sessions where `pip install weasyprint` is blocked by network policy).

Concrete sequence per audit:

1. Compute every figure required by the JSON contract in `templates/audit-data.schema.md`. Write the JSON to a scratch path (e.g., `/tmp/<station>-<date>-audit.json`). Validate every required field.
2. Render the English HTML:
   ```
   python <skill_dir>/render/render-audit.py --data <scratch>.json --lang en --out <scratch>_EN.html
   ```
3. Convert that HTML to PDF by invoking `anthropic-skills:pdf` with the HTML file as input, A4 landscape, into the final output path `<Station>-<YYYY_MM_DD>-Audit_<YYYYMMDD>_<hh>_<mm>_EN.pdf`.
4. Repeat steps 2–3 with `--lang cn` and `_CH.pdf`.
5. Delete the scratch JSON and scratch HTML files. Only the two PDFs are retained.

**Failure handling — strict.** If `render-audit.py` fails (Jinja2 missing, template missing, schema mismatch), the run **must** fail with a structured error. **Never** fall back to LLM-generated HTML, ReportLab, or any other ad-hoc rendering path — that ad-hoc path is exactly the drift the templates eliminate. The deterministic look only holds if the deterministic renderer is the only renderer.

> **Why this design?** `weasyprint` is the canonical Python HTML→PDF library, but its installation requires native libraries (cairo, pango, gdk-pixbuf) which aren't pre-installed in many sandboxed environments and can't be `pip install`-ed when outbound network is restricted (this is the case in Cowork's scheduled-task sandbox). Keeping the Jinja2 substitution as one step and the PDF rasterisation as another lets the same skill produce the same byte-stable output on a developer laptop, the Win 11 server, and a sandboxed scheduled run.

### 7.2 Section content — what data each section needs

The renderer fills the template; the LLM's job is to produce the data values. For every section, populate every field documented in `audit-data.schema.md`. Notes that are content-level (not structural):

- **Section 1 inflow breakdown.** Three headline figures — Total Inflow, Revenue, CFP Deposit — must always reconcile (Total = Revenue + CFP Deposit). The four revenue channels (Cash, Merchant, CFP voucher used, BUDI95) must always appear even if zero. For BUDI95 the `notes` field must split customer-paid portion vs. IPTB-claimable portion.
- **Section 1 revenue segments.** The segments table (`revenue.segments`) lists the per-business-line split — **Fuel**, **Buraqmart**, **Rental**, and (TK only) **iBing**. **iBing and Rental are always separate rows; never combine them into a single "iBing / Rental" row.** Per §1: TK has all four segments; BS and BL have Fuel + Buraqmart + Rental only (no iBing row at all — do not emit a zero-amount iBing row for BS or BL).
- **Section 1 fuel-delivery callout.** When a fuel delivery occurred, set `delivery.occurred = true` and put invoice / ticket / SN in `delivery.summary`. Otherwise omit the object or set `occurred = false`.
- **Section 2 proof-of-fund.** **One row per individual slip** — never collapse multiple slips into a single row even when the Fund Report aggregates them. `cleared.kind` is one of `verified` / `deferred` / `missing`. `in_fr` is `ok` / `agg` / `missing`. The column-key legend is rendered automatically by the template using strings from `labels-{en,cn}.json`. The FR-aggregation sub-table is omitted when `fr_aggregation` is empty; otherwise it must include `fr_aggregation_total` (the column sums) — the renderer paints it as a Total row at the foot of the table. The auto-rendered caption above the table defines `FR amount` (the figure printed on that line of the Fund Report — usually a single cell summing several slips) vs `Sum of slips` (the actual total of the proof-of-fund slips this audit attributes to that same line); the Total row should reconcile against the corresponding channel total in Section 1, and any discrepancy between the two columns on a row is staff arithmetic the back-office must reconcile.
- **Section 3 cash highlight.** Six rows in this order: Opening cash, Cash revenue (POS), CFP cash top-up, BuraqMart cash, Safeguards (CDM) pick-up, Closing cash. Set `is_total: true` on Closing cash; set `is_variance: true` on any row where `var != 0`. Each row's `Computed` value is derived from a fixed formula documented in the auto-rendered legend the template prints under the table (`labels.section_3.computed_legend`) — populate the row values to match those formulas exactly. **CFP cash top-up = sum of CFP-report top-up entries whose payment mode is `cash` only**; bank-transfer / e-wallet top-ups are excluded and a station with bank-transfer-only top-ups (typical for TK on most days) will correctly show `Computed = 0` here. The optional `footer_note` is free text below the legend for **station-specific context** when something on a Computed value needs explanation beyond the legend (e.g., "today's only CFP top-up was Touch'nGo bank transfer, so the cash-only line is 0", or "FR posted yesterday's pick-up under today's date — see FINDING III").
- **Section 4 fuel quantity.** One row per fuel product. The L-fields are pre-formatted strings (`"17,176"`, `"DELIV 16,500"`) so qualifiers like `*` or `DELIV` come through verbatim.
- **Section 4b POS tally.** Each row sets `passed: true | false`; the renderer paints failed rows red and styles the result text accordingly. Include at minimum: GreenPOS fuel total, CFP voucher vs GreenPOS, Merchant fuel, Autocount Mart, BUDI95 sales (POS).
- **Section 5 §4 checklist.** Single HTML string (`<strong>` allowed for `Present:` / `Partial:` / `Missing:` / `N/A:` keywords) referencing the file list in §4.
- **Section 6 findings.** Ordered by materiality (financial impact first, control weakness second, presentation issues last). The renderer numbers findings as upper-case Roman numerals (FINDING I, II, III, …) — `f.n` is still the integer 1, 2, 3 in the JSON; the template applies the `| roman` filter at render time. **Always include a closing finding for each of `§6.11` (clearance status) and `§6.12` (aggregation integrity)**, even when clean — so the reader can confirm those checks ran. **Cross-references are mandatory.** Whenever any other row in the report (a `notes` cell on a slip, a status note in §2/§3/§4b, etc.) refers the reader to a finding, it must name the finding by its Roman number — write `see FINDING IV` (or `cf. FINDING II, III`), never the bare phrase "see notes" or "see findings". The reader needs to be able to jump straight to the right bullet without hunting.

## 8. Workflow

1. Confirm **station(s)** and **date** (default to yesterday if not given).
2. Recall or ask for the four reference values in §3 (daily-report root, bank-ledger Web App URL, bank-ledger Web App token, audit-output root). Save any missing ones to memory on first run. **Ping the Web App** (token-only GET, expect `ok:true`) to populate the meta strip's "Bank ledger" status before the run continues — record the result so §6 rule 11 can reuse it without re-pinging.
3. List files present vs. missing for that station+date.
4. Run all §6 checks, preserving every intermediate calculation.
5. Build the audit-data JSON object per §7's data contract (`templates/audit-data.schema.md`). Every required field must be populated; partial data is a bug, not a degraded output. Write the JSON to a scratch path. **For each language (en, cn):** run `render-audit.py --data <json> --lang <lang> --out <scratch>_<LANG>.html` to produce deterministic Jinja2-substituted HTML, then invoke `anthropic-skills:pdf` on that HTML (A4 landscape) to write `<audit-output-root>/<YYYY>/<YYYY-MM>/<YYYY-MM-DD>/<Station>-<YYYY_MM_DD>-Audit_<YYYYMMDD>_<hh>_<mm>_<Lang>.pdf`. Create the date tree if missing. Delete the scratch JSON and the scratch HTML files when both PDFs are written. Produce no other files. **If `render-audit.py` errors at any point, fail the run** — never substitute an LLM-rendered or ReportLab-rendered PDF; the visual must be byte-stable across runs.
6. **Notify via WhatsApp (best-effort, non-blocking).** Once both PDFs are written for a station, invoke the `whatsapp-send` skill — once per station, not once per language — to push a short notification to the recipients listed in the `WhatsApp recipients` reference memory. Pass the station code, business date, list of PDF absolute paths, and a 3–5 bullet summary of the most material §6 findings (same content as step 7's chat reply). The skill filters recipients by `Stations` ∋ this station, `Reports` ∋ `sale-audit`, and any `Languages` setting; reads Twilio credentials from the local-only path saved in memory; and sends one WhatsApp text per recipient that points at the audit-output folder (Drive URL if memory has one, else local path). **If the send fails for any reason** (creds missing, Twilio error, network), log the failure and continue — the audit itself is **still successful** because the PDFs are on disk. Never raise a WhatsApp failure as a §6 audit finding (it's an operational issue, not an audit issue).
7. Reply in chat with the 3–5 most material findings, the absolute paths to both saved PDFs, and a one-line WhatsApp send result (e.g., `WhatsApp: 3/3 delivered` or `WhatsApp: send failed — see log`).
