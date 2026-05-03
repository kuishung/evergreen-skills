---
name: sale-audit
description: Use this skill whenever the user (Evergreen back-office / management) wants to audit, verify, or check the daily sale submission of a petrol station — TK (Tg. Kapor), BS (Berkat Setia), or BL (Bubul Lama). Triggers include phrases like "audit TK", "audit sale", "check BS sale", "verify fund report", "run daily audit", "daily sale audit for <date>", or any request to reconcile a station's Fund Report against its supporting documents and produce an audit PDF.
version: 0.24.0
updated: 2026-05-04 00:45
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
2. **Audit-output root** — a **single** folder shared by all stations. The skill creates the date tree inside it as `<audit-output-root>/<YYYY>/<YYYY-MM>/<YYYY-MM-DD>/` and writes every station's PDF into the same leaf folder, so the user never has to switch directories between stations. If an existing memory points to a per-station path, treat only its parent as the new root, confirm with the user once, and update the memory.

Before reusing any remembered value, verify it still resolves on the filesystem. If anything fails, ask once and update the memory. If the user has not answered for a given input yet, ask for it at the start of the first audit that needs it — do not proceed without it.

Expected daily layout: `<daily-report-root>/<station>/<YYYY-MM-DD>/…`

> **Bank-clearance verification has moved to a separate skill** (per §9 redesign, v0.18.0). `sale-audit` no longer queries the bank-ledger Web App, the local CSV mirror, or any other clearance source — slip-level "Cleared✓" verification is out of scope. The previous reference-memory items for the Web App URL / token / CSV path can be left in place (the bank-clearance skill will reuse them when it ships) but `sale-audit` does not read them.

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
6b. **Slip type and channel — read from slip content, never from filename or FR.** A slip's type (CDM cash deposit, IFT merchant settlement, TT instant transfer, CFP voucher consumption, G4S Safeguards courier voucher, cheque) and its revenue channel (Cash / Merchant / CFP voucher / BUDI95 / TT-NonCFP / TT-CFP) are determined **only** from the slip image's printed content — bank logo and receipt header for CDM and IFT, app branding for e-wallet TT, voucher format for G4S, redemption line for CFP. Never classify a slip by its filename text (e.g. `SAFEGUARDS-...`, `TTCFP-...`), the FR section it appears under (e.g. "We Direct Bank-in"), or the document-number convention. The PDF's `Type` column must reflect what the slip itself prints; the §7 Section 2 bank-grouped channel mapping must follow from that printed type, not from the FR's classification. If the slip's content is unreadable, mark type as `?` and raise a finding requiring a clearer image.
7. **POS tally.** GreenPOS, Autocount POS, and iBing FeedMePOS totals (system-generated → source of truth) must match the Fund Report totals.
8. **Channel tally.** Per-channel revenue in proof-of-fund must match the per-channel split in the POS systems.
9. **CFP vs. GreenPOS voucher.** Sum of the CFP report's **voucher-usage lines only** (redemptions against pre-paid balance) must tally with the GreenPOS voucher line. CFP top-ups are deposits (§5.2) and are **excluded** from this tally — if a day's "CFP total" matches only when top-ups are included, someone has mis-classified a deposit as revenue.
10. **Fuel quantity.** Opening fuel + deliveries − sales = closing fuel. Reconcile against the fuel quantity records and delivery orders, per product.
11. **Funds cleared — OUT OF SCOPE.** As of v0.18.0, slip-level bank-clearance verification has moved to a **separate skill** (working name: `bank-clearance-audit`, not yet shipped). `sale-audit` no longer pings the bank-ledger Web App, no longer reads the local CSV mirror, and no longer paints a `Cleared✓` column in the proof-of-fund table. The PDF reports the slip's classification (Doc / Type / Amt / Date / Uniq / Acct / POS / In FR) and the §3 cash-flow / §3a FR-aggregation reconciliations only — actual bank-credit confirmation is verified out-of-band by the bank-clearance skill once it ships.
12. **Fund Report aggregation integrity.** Staff sometimes sum several slips into a single Fund Report line (e.g., three cash-deposit slips reported as one "Cash deposits RMx" figure). For every Fund Report entry that aggregates more than one underlying slip, the sum of the underlying slips must equal the Fund Report line — flag any variance. Every individual slip must also appear somewhere in the Fund Report, either as its own line or as part of an aggregated line; any slip missing from the Fund Report entirely is an automatic finding (understatement). Audit always from the slips, never let the Fund Report's aggregated view suppress an individual row in the proof-of-fund table (see §7 Section 2 / §3a).

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

- English: `sale-audit v<version> · generated <YYYY-MM-DD hh:mm>`
- Chinese: `sale-audit v<version> · 生成 <YYYY-MM-DD hh:mm>`

The renderer reads `version:` from this `SKILL.md`'s frontmatter for the sale-audit version and stamps `generated_at` from `datetime.now()` at run time. The bank-ledger version is **not** in the footer — bank-clearance verification has moved to a separate skill (per §9, v0.18.0), so a sale-audit PDF no longer references the bank-ledger pipeline. Footer baseline sits at 3 mm above the page edge; the bottom 17 mm of every page is reserved for it.

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
2. Recall or ask for the two reference values in §3 (daily-report root, audit-output root). Save any missing ones to memory on first run. The skill no longer pings the bank-ledger Web App — clearance verification is out of scope (see §6 rule 11).
3. List files present vs. missing for that station+date.
4. Run all §6 checks, preserving every intermediate calculation.
5. Build the audit-data JSON object per §7's data contract (`templates/audit-data.schema.md`). Every required field must be populated; partial data is a bug, not a degraded output. Write the JSON to a scratch path. **For each language (en, cn):** run `render-audit.py --data <json> --lang <lang> --out <scratch>_<LANG>.html` to produce deterministic Jinja2-substituted HTML, then invoke `anthropic-skills:pdf` on that HTML (A4 landscape) to write `<audit-output-root>/<YYYY>/<YYYY-MM>/<YYYY-MM-DD>/<Station>-<YYYY_MM_DD>-Audit_<YYYYMMDD>_<hh>_<mm>_<Lang>.pdf`. Create the date tree if missing. Delete the scratch JSON and the scratch HTML files when both PDFs are written. Produce no other files. **If `render-audit.py` errors at any point, fail the run** — never substitute an LLM-rendered or ReportLab-rendered PDF; the visual must be byte-stable across runs.
6. **Notify via WhatsApp (best-effort, non-blocking).** Once both PDFs are written for a station, invoke the `whatsapp-send` skill — **once per station**, not once per language. Skip this step entirely when either the `Twilio credentials path` or `WhatsApp recipients path` reference memory is missing or unset; those signal that WhatsApp notifications are intentionally disabled (e.g., on a dev machine). When both are present, build the message body in this exact shape (header line + one full path per language; no emoji, no findings list, no Drive URL):

    ```
    <STATION> Sale Audit for <YYYY-MM-DD> ready:
    EN: <full-path-to-EN-pdf>
    CH: <full-path-to-CH-pdf>
    ```

    Where each `<full-path-to-…-pdf>` is the **complete filesystem path including filename and `.pdf` extension** that this run just wrote — i.e., `<audit-output-root>/<YYYY>/<YYYY-MM>/<YYYY-MM-DD>/<Station>-<YYYY_MM_DD>-Audit_<YYYYMMDD>_<hh>_<mm>_<Lang>.pdf`. The path uses **local filesystem syntax** (e.g. `C:\Users\KS\DATA\…`), NOT a `https://drive.google.com/…` share URL. Recipients with Drive for Desktop see the same path automatically; those without Drive sync get told where each file lives so management can fetch it via RDP / NAS.

    Concrete example for TK on 2026-05-04 with audit generated at 06:30:

    ```
    TK Sale Audit for 2026-05-04 ready:
    EN: C:\Users\KS\DATA\EVG-AUDIT\2026\2026-05\2026-05-04\TK-2026_05_04-Audit_20260504_06_30_EN.pdf
    CH: C:\Users\KS\DATA\EVG-AUDIT\2026\2026-05\2026-05-04\TK-2026_05_04-Audit_20260504_06_30_CH.pdf
    ```

    The audit-running LLM **knows the exact filenames** because it just wrote them — substitute the real `<YYYYMMDD>_<hh>_<mm>` from the rendered file's actual name, not a placeholder. The body is composed at run time, fed to `--body` as a single multi-line string (newlines preserved by Twilio).

    Then invoke `whatsapp-send`'s bundled `send.py` in **bulk-mode** with one CLI call per station:

    ```
    python <whatsapp-send-skill-dir>/send.py \
        --credentials <Twilio credentials path> \
        --recipients <WhatsApp recipients path> \
        --station <STATION> --language "EN,CH" --report sale-audit \
        --body "<the body you built — header line + EN line + CH line>"
    ```

    The script reads the recipients JSON, filters by station/language/report/active, dedupes by phone, and sends one WhatsApp per match. Capture stdout (one JSON line per recipient) and stderr (per-recipient errors) into the audit log. **If the send fails for any reason** (creds missing, recipients file missing, Twilio error, network), log the failure and continue — the audit itself is **still successful** because the PDFs are on disk. Never raise a WhatsApp failure as a §6 audit finding (it's an operational issue, not an audit issue).

    **Why this format:** earlier versions composed a multi-line message with a top-3 findings list and a Drive folder URL. v0.23.0 collapsed it to a single-line "ready" with a folder path. v0.24.0 expanded the body again to include both **complete filenames** (EN + CH) so recipients can navigate straight to the file rather than landing in a folder and hunting. Recipients still open the actual PDF for detail; the message just signals readiness and the precise file location.
7. Reply in chat with the 3–5 most material findings, the absolute paths to both saved PDFs, and a one-line WhatsApp send result aggregating across all stations (e.g., `WhatsApp: TK 2/2, BS 2/2, BL 2/2` or `WhatsApp: send failed — see log`).

## 9. 2026-05-03 redesign — IMPLEMENTED in v0.17.0

The §7.2 PDF layout was reshaped during the 2026-05-03 review session and the renderer / template / schema / sample-data / labels were rewritten to match in `sale-audit` v0.17.0 (schema_version bumped from 1 to 2). This section preserves the spec text for context; the template files in `templates/` are now the source of truth for the implementation. **Audits emitted from v0.17.0 onward use the layout described below.**

### 9.1 Section 1 — Revenue table

Replace the current `revenue.segments` rows with this structure. Every figure currently sitting in explanatory paragraphs / footnotes around the table must be folded **into** the table itself — no out-of-band callouts:

- **Fuel — Petrol**: litres, then RM. The RM column splits into two sub-figures: **BUDI95** (the subsidised / IPTB-claimable portion) and **Collected** (what the customer actually paid at the pump).
- **Fuel — Diesel**: litres, then RM (no BUDI95 split — diesel isn't on the subsidy programme today).
- **Buraqmart**.
- **iBing** — TK only; do not emit a zero-amount row for BS or BL.
- **Lot Rental**.

### 9.2 Section 1 — Revenue Channel table (restructured)

Today's flat per-channel table becomes a **bank-grouped** table with explicit per-bank totals. Order:

1. **CFP Top-up** first (non-revenue) — render this block only when the day actually has CFP top-up inflow; suppress the entire CFP Top-up block if the day has none.
2. **Revenue** block, grouped **by bank account**. Each of the six approved Maybank/AmBank accounts (§2) that received money today gets its own sub-table; under each, list the channels that fed money into that account, with a per-bank subtotal at the foot.

**Channel taxonomy** (rows that may appear under each bank):

- We Direct Bank-in
- Instant Transfer (Non CFP)
- Instant Transfer (Lot Rental)
- Merchant Settlement
- Cheque
- BUDI95
- Safeguards — see classification rule below.

**Safeguards classification rule.** Read the Safeguards (G4S) receipt image before deciding the channel:

- If our company bank account number is **printed on the Safeguards receipt**, the cash credits straight to that account → reclassify the row as **We Direct Bank-in** under the matching bank.
- If our account number is **not** on the receipt, the cash goes through G4S central clearing first → keep the row as **Safeguards**.

Never classify a Safeguards slip from filename text or FR section — only from what's printed on the receipt itself.

**Per-row audit columns** (under each bank's channel list):

- `Doc` — document / receipt reference.
- `Type` — slip type (CDM, IFT, TT, Cheque, G4S voucher, …) read from the slip image per §6 rule 6b.
- `Amt` — amount in RM.
- `Date` — date-match tick (§6 rule 4).
- `Uniq` — uniqueness tick (§6 rule 5).
- `Acct` — destination account read off the slip (§6 rule 6).
- `POS` — POS tally tick (§6 rules 7–8).
- `In FR` — FR-aggregation tick (§6 rule 12).

**Drop the `Cleared✓` column entirely.** Bank-clearance verification (formerly §6 rule 11 — Web App ping, CSV fallback, per-slip clearance lookup) moves out of `sale-audit` into a **separate skill** (working name: bank-clearance-audit) and §6 rule 11 is recast as OUT OF SCOPE. Until that separate skill ships, the sale-audit PDF reports inflow categorisation only — clearance is verified out-of-band.

**Total-inflow reconciliation row.** At the foot of the Revenue Channel table, emit a single reconciliation line: `Total inflow (table) vs Sum of proof-of-fund slips uploaded` → pass / variance. Any variance is a §6 finding (the table missed a slip, or a slip is uploaded but not yet categorised into a channel).

### 9.3 Section 2 — FR aggregation: auto-generated direction-aware finding on variance

For every FR-aggregation row whose `variance != 0`, the audit must emit a §6 finding with the direction interpretation already done — the back-office reader should not have to reason about which direction means what:

- **Case A — `FR amount > Sum of slips`** (FR claims more than slips prove). Finding text template: *"FR `<line>` declared RM `<fr>` but only RM `<slips>` in proof-of-fund slips uploaded; RM `<|variance|>` unaccounted for — either (a) cash/value still held at site, or (b) deposit made but slip missing. Cross-check §3 closing cash: if §3 also overshoots by ~RM `<|variance|>`, value is still at site; otherwise request the missing slip."*
- **Case B — `FR amount < Sum of slips`** (slips prove more than FR claims). Finding text template: *"Proof-of-fund slips total RM `<slips>` but FR `<line>` only declared RM `<fr>`. Funds reached the bank; FR understated by RM `<|variance|>`. Action: amend the FR `<line>` row to match the slip total."*

Each variance row gets its own finding (so cross-references elsewhere can name a single Roman/Arabic number — see §9.4).

### 9.4 Section 6 — Findings numbering: switch from Roman to Arabic numerals

`FINDING I, II, III, …` → `FINDING 1, 2, 3, …`. Drop the `| roman` Jinja filter at template render time; keep `f.n` as the integer in JSON. Cross-references elsewhere in the report read `see FINDING 4` (no Roman). The renderer's `to_roman()` helper stays in `render-audit.py` as a no-op safety net but is no longer wired to the template.

### 9.5 Section 3 — Cash highlight: drop FR/Computed split, single arithmetic flow

The current 4-column layout (`Item` / `FR` / `Computed` / `Var`) is hard to read because every row carries two figures and a per-row variance, which obscures the actual cash flow. Replace it with a **single linear arithmetic flow** — one column of figures — followed by a single comparison line at the foot:

```
Opening cash                                            RM …
+ Cash collected from all segments today                RM …
− Cash already banked in (proven with deposit slips)    RM …
= Expected cash balance at site                         RM …

FR printed closing cash: RM …  ·  Variance vs expected: RM …  (Pass | Variance)
```

Rules:

- The four arithmetic lines are the only rows in the table. No FR column, no Computed column, no per-row variance.
- "Cash collected from all segments today" sums the cash-tender legs across every segment that handled cash (GreenPOS Cash, Buraqmart Autocount Cash, plus CFP cash-mode top-ups — the components currently rendered as separate rows 2–4 of the v0.15.x §3). Show those components either inline as a one-line breakdown (`= GreenPOS Cash 8,432.10 + Buraqmart 2,154.50 + CFP cash top-up 0.00`) or via a tooltip-style footnote — TBD at implementation time.
- "Cash already banked in" = sum of all Safeguards / CDM cash-deposit slip images dated for the audit day (today's row 5).
- "Expected cash balance at site" = Opening + collected − banked-in (today's row 6, but framed as expected on-hand, not as Closing).
- The single comparison line beneath the table is the FR closing-cash check. If `Variance vs expected != 0`, auto-emit a §6 finding using the same direction-aware Case A / Case B pattern as §9.3:
    - **Case A — FR > Expected** (FR claims more on-hand than the flow predicts): site may be holding cash from an un-uploaded inflow, or a deposit slip the audit missed exists. Cross-check the proof-of-fund slip set.
    - **Case B — FR < Expected** (FR claims less than expected): either an inflow went unrecorded today (e.g., a cash-mode CFP top-up missed), or staff has under-declared closing cash. Request reconciliation.

The "How each Computed value is derived" legend (`labels.section_3.computed_legend`) goes away — its content is folded into the four-line table itself, with any per-component breakdown handled via the inline / footnote treatment above.

### 9.6 Inline finding cross-reference on every red flag

Today the report colours problem rows red (§4b POS tally `passed: false`, §2 FR-aggregation variance, etc.) and lists explanatory findings separately in §6. The reader has to scan §6 to figure out which finding explains which red cell. Fix this by **stamping the finding number inline next to every red flag**, so the eye jumps straight from the red colour to the right §6 bullet.

Rule: wherever the report renders a cell or row in the variance / failed style (today's `.variance` / `passed:false` styling), it must also carry the matching finding number — typically appended to the existing result text (e.g., `✗ −17.40 — see FINDING 6`) or as a small in-row reference badge after the variance figure. The finding it references must exist in §6 with the same number.

Applies to every section that emits a §6 finding on variance:

- **§4b POS tally** — every `passed: false` row gains `see FINDING <n>` after the existing `✗ <variance>` result text. The audit author must therefore raise (and number) a finding for every red §4b row before rendering — there is no longer such thing as a red §4b row without a matching §6 entry.
- **§2 Revenue Channel table** — the foot reconciliation row (`Total inflow vs Sum of slips`, per §9.2) when in variance: append `see FINDING <n>` to the variance figure.
- **§2 FR aggregation table** — every variance row (per §9.3): append `see FINDING <n>` next to the variance figure / status badge.
- **§3 Cash highlight** — the foot comparison line (`FR printed closing cash vs Variance vs expected`, per §9.5) when in variance: append `see FINDING <n>` to the variance figure.

Implementation note: the JSON contract for these rows gains an optional `finding_n: <int>` field (matches `f.n` in `section_6_findings`). The template renders `see FINDING {{ row.finding_n }}` whenever the row is styled red **and** `finding_n` is set; if a row is red but `finding_n` is missing, the renderer treats it as a data error and emits a visible `[finding number missing]` placeholder so the gap is obvious during review (failing loud beats failing silent).

### 9.7 Out of scope for the implementation pass

- The bank-clearance skill itself — that's a separate skill folder, separate `SKILL.md`, separate version line. Spec it after this `sale-audit` amendment lands.
- Any changes to §4 (fuel quantity), §5 (§4 checklist) — those sections stay as v0.15.x.
