# Sale-audit visual templates

This folder holds the deterministic-rendering layer for `sale-audit` PDFs. Goal: every audit run produces a visually identical PDF (same colours, layout, typography, table widths) regardless of which model is in use or which Claude session executes the run. Only the **data** changes audit-to-audit; the **look** is frozen here.

## Files

| File | Purpose |
|---|---|
| `audit.html.j2` | Jinja2 page template — the structural layout (sections, tables, donut chart, callouts, footer). |
| `audit.css` | Brand palette, typography, table styling, donut chart, share bars, footer position. |
| `labels-en.json` | All English visible strings — section headers, column labels, footer wording, legend text. |
| `labels-cn.json` | All Simplified Chinese visible strings — same keys as `labels-en.json`. |
| `sample-data.json` | Worked example — the BL audit dated 2026-04-25 — that the renderer can fill the template with. |
| `audit-data.schema.md` | Documented JSON contract that the LLM produces. The renderer's input. |
| `preview-bl-en.html` | Static rendering with the CSS as a sibling file. Open in a browser to confirm the look. |
| `preview-bl-en-standalone.html` | Same content, with the CSS inlined into a single self-contained file. Easiest path to preview when only one file can be downloaded. |

The renderer itself lives at `../render/render-audit.py` (one level up).

## How it fits together

```
audit-data JSON  ─┐
                  ├─→  render-audit.py (Jinja2)  →  HTML  ─┐
labels-{en,cn}    ─┘                                       ├─→  anthropic-skills:pdf  →  PDF
                                                  audit.css ┘
```

When `sale-audit` runs (two steps per language):

1. The LLM computes every figure required by `audit-data.schema.md` and writes a JSON file.
2. `render-audit.py --data <json> --lang en --out <path>_EN.html` produces the deterministic English HTML (Jinja2 substitution only — no PDF dependencies).
3. `anthropic-skills:pdf` converts that HTML to the final PDF.
4. Repeat steps 2–3 with `--lang cn`.
5. Same JSON in → byte-identical HTML out → visually-stable PDF out, every time.

**Why two steps?** `weasyprint` is the canonical Python HTML→PDF library but it can't be `pip install`-ed in restricted-egress sandboxes like Cowork's scheduled-task environment (network allowlist blocks PyPI). By keeping Jinja2 substitution as one step and PDF rasterisation as another, the same skill runs anywhere — laptop, Win 11 server, scheduled Cowork — without environment-specific code paths or fallbacks.

## To preview the look without running the renderer

Open `preview-bl-en-standalone.html` in a browser. It has the CSS inlined so it works as a single download. Save the file locally first (the URL approach gets blocked by CDN content-type policies — see issue notes in commit history).

## To preview a fresh render with the actual templating engine

```
pip install jinja2
python ../render/render-audit.py --data sample-data.json --lang en --out /tmp/audit.html
# open /tmp/audit.html in a browser to verify the visual

# To produce a PDF, hand the HTML off to anthropic-skills:pdf — that path
# works everywhere, including sandboxes that block weasyprint.
#
# (For local convenience only, render-audit.py also supports `--out
# <path>.pdf` directly via weasyprint — but that path is NOT what
# sale-audit uses in production; it's a developer shortcut.)
```

## To change the look

- **Colour, font size, margin** → edit `audit.css` only. Every audit re-rendered after that picks up the new look.
- **Section structure (add a row, reorder columns)** → edit `audit.html.j2`.
- **Translate or re-word a label** → edit `labels-en.json` or `labels-cn.json`. No code or template changes needed.
- **New JSON field** → add to `audit-data.schema.md`, reference in `audit.html.j2`, update `sample-data.json` so previews still render.

## Why this folder exists

Earlier flow had the LLM write fresh HTML each audit, interpreting the visual spec from prose. Even with a tight spec, layout drifted run-to-run. By moving HTML and CSS into versioned files in the repo, every run reuses the **exact same template** — drift goes to zero.
