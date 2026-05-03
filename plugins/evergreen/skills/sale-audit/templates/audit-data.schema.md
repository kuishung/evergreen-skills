# Audit data — JSON contract (schema_version: 2)

The renderer (`../render/render-audit.py`) takes one JSON object and renders it via `audit.html.j2` using either `labels-en.json` or `labels-cn.json`. The LLM running `sale-audit` produces this JSON each run; the renderer is deterministic, so any two runs over the same JSON produce byte-identical PDFs.

`sample-data.json` in this folder is a complete worked example matching the BL audit dated 2026-04-25, restructured for schema_version 2 (the §9 redesign that landed in `sale-audit` 0.16.0).

## Top-level fields

| Field | Type | Notes |
|---|---|---|
| `schema_version` | int | Pin to `2`. Bumped from `1` when the §9 redesign landed. |
| `language` | `"en"` \| `"cn"` | Echoed into `<html lang="…">`; the `--lang` CLI flag overrides which label pack is loaded. |
| `skill_version` | string | Filled at render time from `SKILL.md` frontmatter `version:` if absent. Footer reads this. |
| `skill_updated` | string | Filled at render time from `SKILL.md` frontmatter `updated:` if absent. Reserved — not currently rendered. |
| `generated_at` | string `YYYY-MM-DD HH:MM` | Filled by `datetime.now()` if absent. Footer reads this. |
| `station` | object | `code` (`"TK"`/`"BS"`/`"BL"`), `name_long`, `name_long_cn`. |
| `business_date` | string `YYYY-MM-DD` | Date being audited. |
| `meta` | object | `prepared_by`, `fund_report_status`. (The `bank_stmts_status` field from schema v1 is gone — bank clearance moves to a separate skill.) |
| `delivery` | object \| null | `{occurred: bool, summary: string}`. Yellow callout above Section 1 when `occurred=true`. |
| `inflow` | object | `{total, revenue, cfp_deposit}`, all numeric (RM). |
| `revenue` | object | See **Revenue object** below. |
| `cfp_deposit` | object | See **CFP Deposit object** below. |
| `section_2` | object | Bank-grouped channel table (slip-by-slip evidence). See below. |
| `section_2b` | object | Inflow reconciliation summary — every component of `inflow.total` accounted for. Per-revenue-component view. See below. |
| `section_2c` | object | Per-account expected-bank-credits table — watch-list for tomorrow's bank statements. See below. |
| `section_3_cash` | object | Single arithmetic flow + FR comparison. See below. |
| `section_3_fr_aggregation` | object | FR-vs-slips reconciliation. See below. |
| `section_4_fuel` | object | One row per fuel product. See below. |
| `section_4b_pos_tally` | array | One row per POS-vs-FR check. See below. |
| `section_5_checklist` | string | HTML allowed (`<strong>`); rendered as a paragraph. |
| `section_6_findings` | array | One bullet per finding. Numbered Arabic 1, 2, 3, …. |

## Revenue object (§1)

Per §9.1 the segments table breaks Fuel into Petrol / Diesel and surfaces the BUDI95 vs Collected split for petrol. Every figure that used to live in explanatory paragraphs now sits in a cell.

```jsonc
{
  "total": 48687.10,                       // sum of segments
  "litres_total": "13,810.60",             // already-formatted string
  "budi95_total": 23130.10,                // RM, sum of all budi95_rm
  "collected_total": 25557.00,             // RM, sum of all collected_rm
  "segments": [
    // TK: Petrol, Diesel, Buraqmart, iBing, Lot Rental (five rows).
    // BS / BL: Petrol, Diesel, Buraqmart, Lot Rental (no iBing row).
    { "name": "Fuel — Petrol",
      "litres": "10,948.96",               // string; null for non-fuel segments
      "budi95_rm": 23130.10,               // RM; null if segment has no BUDI95 (Diesel, Buraqmart, ...)
      "collected_rm": 19259.77,            // RM; non-BUDI95 portion (cash + card + voucher at pump)
      "amount": 42389.87,                  // segment total (= budi95_rm + collected_rm where applicable)
      "share_pct": 87.1 },
    { "name": "Fuel — Diesel",
      "litres": "2,861.64", "budi95_rm": null, "collected_rm": 6152.53,
      "amount": 6152.53, "share_pct": 12.6 },
    { "name": "Buraqmart",
      "litres": null, "budi95_rm": null, "collected_rm": 144.70,
      "amount": 144.70, "share_pct": 0.3 },
    { "name": "Lot Rental",
      "litres": null, "budi95_rm": null, "collected_rm": 0.00,
      "amount": 0.00, "share_pct": 0.0 }
  ]
}
```

Where a segment has no value for a given column (Diesel has no BUDI95; Buraqmart has no litres), set the field to `null` — the template renders it as `—`.

## CFP Deposit object (§1)

Unchanged from schema v1.

```jsonc
{
  "total": 967.50,
  "subtitle": "All bank transfer; zero cash CFP top-up today.",
  "subchannels": [
    { "name": "Cash top-up",          "amount": 0.0,    "count": 0 },
    { "name": "Bank transfer top-up", "amount": 967.50, "count": 1 }
  ],
  "subchannels_total": { "amount": 967.50, "count": 1 }
}
```

## Section 2 — Revenue Channel table (§9.2)

Per §9.2, the flat per-channel table is replaced with a bank-grouped table. CFP Top-up first (only when present), then revenue grouped by destination bank account, with per-bank subtotals. Each slip row shows Doc / Type / Amt / Date / Uniq / Acct / POS / In FR / Notes — no Cleared column.

```jsonc
{
  "subtitle": "26 slips · grouped by destination bank account",

  // CFP Top-up block (non-revenue) — render only when present. If today
  // has no CFP top-up at all, omit the entire `cfp_topup` object.
  "cfp_topup": {
    "total": 967.50,
    "channels": [
      { "name": "Instant Transfer (CFP top-up)",
        "slips": [ /* slip objects, see below */ ] }
    ]
  },

  // Banks block — one entry per approved Maybank/AmBank account that
  // received money today (§2). Order: AMB first, MBB second, by last-4.
  "banks": [
    {
      "code": "AMB-8135",
      "label": "AmBank 8881058618135 (G4S clearing)",
      "subtotal": 22344.00,
      "channels": [
        {
          "name": "Safeguards",                 // see §9.2 channel taxonomy
          "subtotal": 22344.00,                 // optional; rendered next to channel name in muted text
          "slips": [ /* slip objects */ ]
        }
      ]
    }
  ],

  // Optional explanatory note rendered below the legend, e.g. for the
  // §9.2 Safeguards classification rule when the call was non-trivial.
  "safeguards_rule_note": "<strong>Safeguards classification:</strong> ..."
}
```

The bank-grouped table no longer carries a foot reconciliation row — that role has moved to `section_2b` (the headline reconciliation summary). The `receivables` block from earlier drafts is also gone — receivables (BUDI95 IPTB) and non-bank inflows (CFP voucher redemption) appear in the §2b summary instead, with their evidence (PUKAL, CFP report) named inline.

## Section 2b — Inflow reconciliation summary

Revenue-component list of where today's revenue + non-revenue ended up, framed so the sum reconciles **exactly** with `data.inflow.total` by construction (each row is independently derived from POS / slips / reports).

Recommended row ordering (only rows with `amount > 0` appear in `rows`; approved §2 accounts that received nothing today are named in `silent_accounts` instead, rendered as a footer note — see "silent_accounts" field below):

1. **One row per approved bank account** that had non-cash revenue today (Card + IFT + Cheque routed to that account). Slip evidence cited inline. Accounts with **zero** non-cash revenue are dropped from `rows` and listed in `silent_accounts` instead.
2. **Cash — collected today**. Single line; POS-derived (GreenPOS Cash tender + Buraqmart cash + cash CFP top-up). The amount is today's cash revenue, regardless of whether Safeguards has banked it yet — that timing question lives in §3. The Safeguards slip evidence in §2 proves cash physically banked but doesn't appear here.
3. **CFP Voucher — redemption**. Pre-paid balance consumed against fuel; no bank movement. Evidenced by CFP report redemption lines.
4. **BUDI95 — IPTB-claimable receivable**. Gov subsidy not banked today. Evidenced by PUKAL BUDI95 receipts.
5. **CFP Top-up (non-revenue)**. Direct credit to whichever Maybank account the customer wired to. Evidenced by TTCFP slip(s) — already in §2 CFP Top-up block.

```jsonc
{
  "subtitle": "Headline reconciliation — every component of §1 Total Inflow accounted for, listed per approved bank account...",
  "total_inflow": 49654.60,                   // matches data.inflow.total
  "rows": [
    { "label": "AMB 8881058618135 — non-cash revenue (Card + IFT + Cheque)",
      "amount":    0.00,
      "evidence": "No non-cash revenue routed here today." },
    { "label": "AMB 8881058618146 — non-cash revenue (Card + IFT + Cheque)",
      "amount": 1597.80,
      "evidence": "13 IFT slips RM 524.50 + 3 Merchant slips RM 1,073.30 — see §2 detail." },
    // ... one row per approved account
    { "label": "Cash — collected today (POS Cash tender + Buraqmart cash + cash CFP top-up)",
      "amount": 22363.01,
      "evidence": "GreenPOS Cash + Buraqmart Autocount cash; eventually banked to AMB via Safeguards — timing in §3." },
    { "label": "CFP Voucher — redemption against pre-paid balance (no bank movement)",
      "amount": 13489.96, "evidence": "..." },
    { "label": "BUDI95 — IPTB-claimable receivable (gov claim, not banked today)",
      "amount": 11236.33, "evidence": "..." },
    { "label": "CFP Top-up (non-revenue) — direct credit to MBB 510161015366",
      "amount":   967.50, "evidence": "..." }
  ],
  "silent_accounts": [                        // approved §2 accounts with zero inflow today
    "AMB 8881058618135",
    "AMB 8881058618157",
    "MBB 560166149415",
    "MBB 560166149422"
  ],
  "silent_accounts_note":                     // optional clarifying caveat below the silent list
    "AMB 8881058618135 receives Safeguards cash deposits — those amounts are counted under \"Cash — collected today\" above.",
  "sum_components": 49654.60,                 // arithmetic sum of every row above
  "passed": true,                             // sum_components == total_inflow ?
  "result": "✓ Pass — total inflow reconciles to channel breakdown",
  "finding_n": null                           // set when passed:false
}
```

`silent_accounts` is optional — omit or pass `[]` if every approved account had inflow today. When non-empty, the template renders a footer note under the §2b table naming the silent accounts so the rogue-routing transparency is preserved without printing zero rows.

## Section 2c — Expected bank credits

Per-account view: for each approved §2 bank account that should receive a credit today, the **expected amount** and the **slip-evidenced source**. The operator uses this as a watch-list for tomorrow's bank statements; **actual clearance verification is out of scope** per §6 r.11 (it lives in a separate bank-clearance skill that hasn't shipped yet). Cash via Safeguards normally clears T+0 to T+1; IFT clears same-day; Merchant Settlement clears T+1; cheques clear T+1..T+3.

```jsonc
{
  "subtitle": "Watch-list for tomorrow's bank statements...",
  "rows": [
    { "account": "AMB 8881058618135 (G4S clearing)",
      "amount": 22344.00,
      "source": "Safeguards CDM cash deposit (8 G4S consolidated vouchers, see §2)",
      "expected_clearance": "T+0..T+1" },
    { "account": "AMB 8881058618146",
      "amount": 1597.80,
      "source": "13 IFT Non-CFP slips RM 524.50 + 3 Merchant Settlement slips RM 1,073.30",
      "expected_clearance": "T+0 (IFT) / T+1 (Merchant)" },
    { "account": "MBB 510161015366",
      "amount": 967.50,
      "source": "1 CFP Top-up TTCFP slip via PetrolFox IFT",
      "expected_clearance": "T+0" }
  ],
  "total_to_clear": 24909.30                  // sum of every row.amount above
}
```

### Channel taxonomy (per §9.2)

Allowed channel names under each bank, in order of typical appearance:

- `We Direct Bank-in`
- `Instant Transfer (Non CFP)`
- `Instant Transfer (Lot Rental)`
- `Merchant Settlement`
- `Cheque`
- `BUDI95`
- `Safeguards`

Special rule for Safeguards (§9.2): read the receipt image. If our company bank-account number is **printed on the slip**, classify the row as `We Direct Bank-in` (cash credits straight to that account). Only when our account is **not** on the slip does the row stay as `Safeguards` (G4S central clearing).

### Slip object

```jsonc
{
  "doc":     "12-2617M",                     // freeform doc/receipt ID
  "type":    "TTCFP (CFP top-up)",           // free text — slip-content type
  "amount":  967.50,                         // RM
  "date_ok": true,                           // bool (or null in receivables); → ✓ / ✗ tick
  "uniq_ok": true,                           // bool; → ✓ / ✗ tick
  "acct":    "MBB 510161015366",             // free text, account READ off slip image (§6 r.6)
  "pos_ok":  true,                           // bool, or null → "n/a"
  "in_fr":   "ok" | "agg" | "missing",       // ✓ / ∑ / ✗ per §6 r.12
  "notes":   "Free text. <strong>HTML</strong> allowed (rendered raw)."
}
```

The Cleared column from schema v1 is gone. Bank-clearance verification (Web App ping, CSV fallback, per-slip clearance lookup) moves to a separate skill (working name: bank-clearance-audit).

## Section 3 — Cash highlight (§9.5)

Per §9.5, drop the FR / Computed / Var four-column layout. Replace with a single arithmetic flow plus one comparison line below it.

```jsonc
{
  "opening":    217.24,                      // RM, brought forward from prior business date
  "collected":  33858.07,                    // RM, sum of cash collected from all segments today
  "collected_breakdown": "GreenPOS Cash 33,713.37 + Buraqmart cash 144.70 + CFP cash top-up 0.00",
                                             // optional one-line string, rendered as a muted sub-row
                                             // under "collected" — folds the legend into the table
  "banked_in":  22344.00,                    // RM, sum of CDM / Safeguards cash-deposit slips dated today
  "expected":   11731.31,                    // RM, opening + collected - banked_in (audit-computed)

  // Single comparison line below the arithmetic table (§9.5 option B):
  // FR's printed closing cash vs the audit's expected balance.
  "fr_check": {
    "fr_closing": 11455.18,                  // RM, the FR's printed closing-cash figure
    "variance":     -276.13,                 // RM = fr_closing - expected (signed)
    "passed":       false,
    "result":       "✗ Variance",
    "finding_n":    4                        // int; matches f.n in section_6_findings
  },

  "footer_note": "Free text under the comparison line; HTML allowed."
}
```

If `passed: false` and `finding_n` is missing, the renderer emits a visible `[finding number missing]` placeholder — failing loud beats failing silent.

## Section 3a — FR aggregation (§6 r.12 reconciliation)

Was old `section_2.fr_aggregation`; promoted to its own block alongside §3 since §2 no longer has the FR aggregation table inline.

```jsonc
{
  "rows": [
    { "line": "Safeguards (FR aggregate)",
      "fr_amount": 22344.00, "sum_slips": 22344.00,
      "variance": 0.00, "status": "Clean",
      "is_variance": false,
      "finding_n": null },
    { "line": "Cash in Today (excl Opening)",
      "fr_amount": 11237.94, "sum_slips": 11586.61,
      "variance": 348.67, "status": "Variance",
      "is_variance": true,
      "finding_n": 8 }
  ],
  "total": {
    "fr_amount": 36147.24, "sum_slips": 36495.91,
    "variance":    348.67, "status": "Variance",
    "is_variance": true,
    "finding_n":   8
  }
}
```

Set the whole object to `null` (or omit) when there are no aggregated FR lines. Per §9.3, every row with `is_variance: true` MUST have a non-null `finding_n` referencing a corresponding §6 entry that uses the direction-aware Case A / Case B finding-text template.

## Section 4 — Fuel quantity

Unchanged from schema v1.

```jsonc
{
  "rows": [
    { "product": "RON95 (Petrol)",
      "open_l": "17,176",                       // strings, already formatted
      "deliv_l": "DELIV 16,500",
      "sales_l": "10,948.96",
      "close_l": "22,525",
      "var": "+(178)*" }
  ],
  "footer_note": "Free-text explanation."
}
```

## Section 4b — POS tally

Per §9.6, every `passed: false` row gains a mandatory `finding_n` (matches `f.n` in `section_6_findings`). The template stamps `see FINDING <n>` after the result text on red rows.

```jsonc
[
  { "check": "GreenPOS fuel total",
    "pos": 48542.40, "fr": 48525.00,
    "result": "✗ −17.40",
    "passed": false,
    "finding_n": 6 },
  { "check": "CFP voucher vs GreenPOS",
    "pos": 13489.96, "fr": 13489.96,
    "result": "✓ Verified",
    "passed": true,
    "finding_n": null }
]
```

## Section 6 — Findings

Per §9.4, rendered as Arabic numerals (FINDING 1, 2, 3, ...). The `roman` Jinja filter is no longer wired up. Cross-references elsewhere in the report (`see FINDING 4`) cite the same integer.

```jsonc
[
  { "n": 1,
    "title": "Short bold lead.",
    "body":  "Body sentence with the analysis.",
    "action": "Concrete next step." }
]
```

The LLM owns the ordering (most material first per `SKILL.md` §7). Per §9.3 / §9.5 / §9.6, every red-coloured row in §2 / §3 / §3a / §4b that references a finding number expects that integer to exist here.

## Renderer responsibilities

The renderer:

- Loads `audit.html.j2`, `labels-{en|cn}.json`, the data JSON.
- Reads `templates/audit.css` and inlines it into the rendered HTML as a `<style>` block (the HTML is fully self-contained — required for the production two-step flow where `anthropic-skills:pdf` rasterises the scratch HTML at a different working directory; see SKILL.md §7.1).
- Adds `skill_version` / `skill_updated` from `SKILL.md` frontmatter and `generated_at` from `datetime.now()` if absent. (The `bank_ledger_version` field is gone — bank-clearance verification moved to a separate skill, so sale-audit no longer reads `../bank-ledger/SKILL.md`.)
- Auto-escapes by default; fields documented above as accepting HTML (`section_5_checklist`, `slip.notes`, `cfp_deposit.subtitle`, `safeguards_rule_note`, `section_3_cash.footer_note`) bypass via the template's `|safe` filter and are the LLM's responsibility to keep clean.
- Writes `.html` (no extra deps) or `.pdf` (requires `weasyprint`).
- Never reads files other than the four above (`audit.html.j2`, `labels-{en,cn}.json`, the data JSON, `audit.css`).
