# Audit data — JSON contract

The renderer (`../render/render-audit.py`) takes one JSON object and renders it via `audit.html.j2` using either `labels-en.json` or `labels-cn.json`. The LLM running `sale-audit` produces this JSON each run; the renderer is deterministic, so any two runs over the same JSON produce byte-identical PDFs.

`sample-data.json` in this folder is a complete worked example matching the BL audit dated 2026-04-25.

## Top-level fields

| Field | Type | Notes |
|---|---|---|
| `schema_version` | int | Pin to `1` for now. Renderer reads but does not currently version-gate. |
| `language` | `"en"` \| `"cn"` | Echoed into `<html lang="…">`; the `--lang` CLI flag overrides which label pack is loaded. |
| `skill_version` | string | Filled at render time from `SKILL.md` frontmatter `version:` if absent. |
| `skill_updated` | string | Filled at render time from `SKILL.md` frontmatter `updated:` if absent. |
| `generated_at` | string `YYYY-MM-DD HH:MM` | Filled by `datetime.now()` if absent. Footer reads this. |
| `station` | object | `code` (`"TK"`/`"BS"`/`"BL"`), `name_long`, `name_long_cn`. |
| `business_date` | string `YYYY-MM-DD` | Date being audited. |
| `meta` | object | `prepared_by`, `fund_report_status`, `bank_stmts_status`. |
| `delivery` | object \| null | `{occurred: bool, summary: string}`. Yellow callout above Section 1 when `occurred=true`. |
| `inflow` | object | `{total, revenue, cfp_deposit}`, all numeric. |
| `revenue` | object | See **Revenue object** below. |
| `cfp_deposit` | object | See **CFP Deposit object** below. |
| `donut_slices` | array | See **Donut slices** below. |
| `section_2` | object | See **Section 2 object** below. |
| `section_3_cash` | object | See **Cash highlight** below. |
| `section_4_fuel` | object | See **Fuel quantity** below. |
| `section_4b_pos_tally` | array | One row per check; see below. |
| `section_5_checklist` | string | HTML allowed (`<strong>`); rendered as a paragraph. |
| `section_6_findings` | array | One bullet per finding; see below. |

## Revenue object

```jsonc
{
  "total": 60447.93,                       // RM
  "segments": [
    { "name": "...", "amount": 0.0, "share_pct": 0.0 },
    ...
  ],
  "footer_note": "Free text below the segment table (italic).",
  "channels": [
    { "name": "Cash", "amount": 0.0, "slips_count": 21, "slips_text": "21",
      "pct_revenue": 37.8, "notes": "..." },
    ...
  ],
  "channels_total": { "amount": 0.0, "slips_count": 33, "pct_revenue": 100.0 }
}
```

`slips_text` is for the channel-totals "# slips" cell; useful when the count itself isn't a plain integer (`"—"` for BUDI95).

## CFP Deposit object

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

## Donut slices

Order matters — slices render clockwise in array order. Sum of `pct` should equal 100.0. The four standard slice colour vars are:

| Channel       | `color_var`         |
|---------------|---------------------|
| Cash          | `--slice-cash`      |
| Merchant      | `--slice-merchant`  |
| CFP voucher   | `--slice-cfp`       |
| BUDI95        | `--slice-budi`      |

```jsonc
"donut_slices": [
  { "label": "Cash",        "color_var": "--slice-cash",     "pct": 37.8 },
  { "label": "Merchant",    "color_var": "--slice-merchant", "pct":  1.7 },
  { "label": "CFP voucher", "color_var": "--slice-cfp",      "pct": 22.3 },
  { "label": "BUDI95",      "color_var": "--slice-budi",     "pct": 38.3 }
]
```

## Section 2 object

```jsonc
{
  "subtitle": "25 slips · all individual, no aggregation in FR slip rows",
  "deferred_note": "§6.11 deferred for ...",   // null/omit if not deferred
  "slips": [
    {
      "doc": "01-5351",
      "type": "Safeguard CDM",
      "amount": 6270.00,
      "date_ok": true,                          // bool -> ✓ / ✗
      "uniq_ok": true,                          // bool -> ✓ / ✗
      "acct": "✓ AMB(G4S)",                     // free text (template doesn't tickify)
      "pos_ok": true,                           // bool, or null -> "n/a"
      "cleared": {
        "kind": "verified" | "deferred" | "missing",
        "text": "✓" | "partial G4S" | "✗ no match" | "defer T+1"
      },
      "in_fr": "ok" | "agg" | "missing",        // ✓ / ∑ / ✗
      "notes": "Free text. <strong>HTML</strong> tags allowed."
    }
  ],
  "fr_aggregation": [
    { "line": "Safeguards (FR aggregate)",
      "fr_amount": 22344.00, "sum_slips": 22344.00,
      "variance": 0.00, "status": "Clean", "is_variance": false },
    { "line": "Cash in Today (excl Opening)",
      "fr_amount": 11237.94, "sum_slips": 11586.61,
      "variance": 348.67, "status": "Variance", "is_variance": true }
  ]
}
```

Set `fr_aggregation: []` if no aggregated FR lines exist; the section is omitted in that case.

## Cash highlight (Section 3)

```jsonc
{
  "rows": [
    { "item": "Opening cash",  "fr": 217.24, "computed": 217.24,
      "var": null, "is_variance": false, "is_total": false },
    ...
    { "item": "Closing cash",  "fr": 11455.18, "computed": 11586.61,
      "var": -131.43, "is_variance": true,  "is_total": true }
  ],
  "footer_note": "Free-text explanation paragraph below the table."
}
```

`var: null` renders as `—`. `is_variance: true` paints the row red. `is_total: true` bolds + adds a top border.

## Fuel quantity (Section 4)

```jsonc
{
  "rows": [
    { "product": "RON95 (Petrol)",
      "open_l": "17,176",                       // strings — already-formatted
      "deliv_l": "DELIV 16,500",
      "sales_l": "10,948.96",
      "close_l": "22,525",
      "var": "+(178)*" }
  ],
  "footer_note": "Free-text explanation."
}
```

The L-fields are rendered verbatim (string), so you can include qualifiers like `"DELIV 16,500"` or asterisks.

## POS tally (Section 4b)

```jsonc
[
  { "check": "GreenPOS fuel total", "pos": 48542.40, "fr": 48525.00,
    "result": "✗ −17.40", "passed": false },
  { "check": "CFP voucher vs GreenPOS", "pos": 13489.96, "fr": 13489.96,
    "result": "✓ Verified", "passed": true }
]
```

`passed: false` paints the row red and the result text gets the `tickbox.x` style.

## Findings (Section 6)

```jsonc
[
  { "n": 1,
    "title": "Short bold lead.",
    "body": "Body sentence with the analysis.",
    "action": "Concrete next step." }
]
```

`n` is just the display number; the LLM owns the ordering (most material first per `SKILL.md` §7).

## Renderer responsibilities

The renderer:

- Loads `audit.html.j2`, `labels-{en|cn}.json`, the data JSON.
- Adds `skill_version` / `skill_updated` from `SKILL.md` frontmatter and `generated_at` from `datetime.now()` if absent (so the LLM doesn't have to compute them).
- Auto-escapes by default; fields documented above as accepting HTML (`section_5_checklist`, `slip.notes`) bypass via the template's `|safe` filter and are the LLM's responsibility to keep clean.
- Writes `.html` (no extra deps) or `.pdf` (requires `weasyprint`).
- Never reads files other than the three above and the sibling `audit.css`.
