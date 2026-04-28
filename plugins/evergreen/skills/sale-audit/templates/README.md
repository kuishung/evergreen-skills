# Sale-audit visual templates

This folder holds the deterministic-rendering layer for `sale-audit` PDFs. Goal: every audit run produces a visually identical PDF (same colours, layout, typography, table widths) regardless of which model is in use or which Claude session executes the run. Only the **data** changes audit-to-audit; the **look** is frozen here.

## Files

| File | Purpose | Stage |
|---|---|---|
| `audit.css` | Brand palette, typography, layout grid, table styling, donut chart, share bars, footer stamp. | shipped |
| `preview-bl-en.html` | Static reproduction of the BL audit dated 2026-04-25 (gold-standard reference). Open in a browser to confirm the look. | shipped |
| `audit.html.j2` | Jinja2 template — parameterised version of the preview HTML. | next commit |
| `labels-en.json`, `labels-cn.json` | All visible strings, externalised so EN and CN PDFs share one template. | next commit |
| `sample-data.json` | Realistic audit data the renderer fills the template with. | next commit |
| `render-preview.py` | Python script that loads template + data + labels, renders HTML, writes a PDF. | next commit |

## How to preview the look right now

1. Open `preview-bl-en.html` in any modern browser (Chrome / Edge / Firefox / Safari).
2. The page is laid out as three landscape A4 sheets with the brand palette and table styling.
3. To preview a print-style PDF, use the browser's **Print → Save as PDF**, with paper size set to A4 landscape and margins set to "Default" or "Minimum".

## Why this folder exists

The earlier flow had the LLM write fresh HTML/CSS for every audit, interpreting the visual spec in `SKILL.md` from prose. Even with a tight spec, layout drifted run-to-run. By moving HTML and CSS into versioned files in the repo, every run reuses the **exact same template** — drift goes to zero.

Subsequent commits will:

1. Convert `preview-bl-en.html` into a Jinja2 template with `{% %}` placeholders.
2. Externalise all English / Chinese strings into `labels-*.json`.
3. Add `render-preview.py` so any audit run can produce both PDFs from a single JSON data input.
4. Update `sale-audit/SKILL.md` §7 and §8 so the workflow ends with "produce JSON → invoke renderer → done", rather than "LLM writes HTML each time".

## Editing the look

**Want to change a colour, font size, or margin?** Edit `audit.css` only. Every audit re-rendered after that picks up the new look.

**Want to change a section structure (add a row, reorder columns)?** Edit `audit.html.j2` after it lands. The CSS styling continues to apply automatically.

**Want to translate a label?** Edit `labels-en.json` or `labels-cn.json` after they land. No code or template changes needed.
