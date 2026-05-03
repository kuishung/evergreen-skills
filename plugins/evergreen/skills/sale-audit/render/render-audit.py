#!/usr/bin/env python3
"""
Render an Evergreen sale-audit PDF deterministically.

PRODUCTION FLOW (used by sale-audit, works in every environment):
  1. Run this script with `--out <scratch>.html` to produce the
     Jinja2-substituted HTML. Only `jinja2` is required.
  2. Hand the resulting HTML to `anthropic-skills:pdf` for the actual
     PDF rasterisation (A4 landscape).

The two-step split is what lets the pipeline run in sandboxed
environments (e.g., Cowork scheduled tasks) that block
`pip install weasyprint` at the network allowlist.

Inputs (all required):
  --data        Path to audit-data JSON file (schema: ../templates/audit-data.schema.md)
  --lang        en | cn   (which label pack to use)
  --out         Output path; .html for the production flow, .pdf only as a
                developer-local shortcut when weasyprint is available.

Optional:
  --templates   Path to the templates folder (default: sibling ../templates/)
  --skill-version  Override the v… stamp (default: read from ../SKILL.md frontmatter)
  --skill-updated  Override the amended-date stamp (default: read from ../SKILL.md frontmatter)

Examples:
  # PRODUCTION step 1 — JSON to HTML (only jinja2 needed):
  python render-audit.py --data ../templates/sample-data.json --lang en --out /tmp/audit.html
  # ... then pass /tmp/audit.html to anthropic-skills:pdf to get the PDF.

  # Developer convenience — direct PDF (requires `pip install weasyprint`,
  # which fails in network-restricted sandboxes; do not use in production):
  python render-audit.py --data ../templates/sample-data.json --lang en --out /tmp/audit.pdf

Dependencies:
  jinja2       (always required)         pip install jinja2
  weasyprint   (developer shortcut only) pip install weasyprint
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def to_roman(n) -> str:
    """Convert an int (or numeric string) to upper-case Roman numerals.

    Used by the findings list so each finding gets a stable, easy-to-cite
    label (FINDING I, II, III, ...). Other rows in the report can then
    cross-reference like "see FINDING IV" without ambiguity.

    Returns the input unchanged if it isn't a positive integer in [1, 3999].
    """
    try:
        n = int(n)
    except (TypeError, ValueError):
        return str(n)
    if n < 1 or n > 3999:
        return str(n)
    pairs = [
        (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
        (100, "C"),  (90,  "XC"), (50,  "L"), (40,  "XL"),
        (10,  "X"),  (9,   "IX"), (5,   "V"), (4,   "IV"),
        (1,   "I"),
    ]
    out = []
    for value, sym in pairs:
        while n >= value:
            out.append(sym)
            n -= value
    return "".join(out)


def read_skill_frontmatter(skill_md_path: Path):
    """Extract version: and updated: lines from SKILL.md frontmatter."""
    if not skill_md_path.exists():
        return None, None
    text = skill_md_path.read_text(encoding="utf-8")
    m = re.search(r"^---\s*\n(.*?)\n---\s*\n", text, flags=re.DOTALL | re.MULTILINE)
    if not m:
        return None, None
    fm = m.group(1)
    version = None
    updated = None
    for line in fm.splitlines():
        line = line.strip()
        if line.startswith("version:"):
            version = line.split(":", 1)[1].strip()
        elif line.startswith("updated:"):
            updated = line.split(":", 1)[1].strip()
    return version, updated


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True, help="Path to audit-data JSON")
    ap.add_argument("--lang", choices=["en", "cn"], default="en")
    ap.add_argument("--out", required=True, help="Output path (.html or .pdf)")
    ap.add_argument("--templates", default=None, help="Path to templates folder")
    ap.add_argument("--skill-version", default=None, help="Override skill version stamp")
    ap.add_argument("--skill-updated", default=None, help="Override skill amended-date stamp")
    args = ap.parse_args()

    try:
        from jinja2 import Environment, FileSystemLoader, select_autoescape
    except ImportError:
        sys.exit("Missing dependency: jinja2 (pip install jinja2)")

    here = Path(__file__).resolve().parent
    templates_dir = Path(args.templates).resolve() if args.templates else (here.parent / "templates").resolve()
    if not templates_dir.exists():
        sys.exit(f"Templates folder not found: {templates_dir}")

    data_path = Path(args.data).resolve()
    out_path = Path(args.out).resolve()

    data = load_json(data_path)
    labels = load_json(templates_dir / f"labels-{args.lang}.json")

    # Merge runtime fields from CLI / SKILL.md, but never overwrite values
    # the caller already wrote into data.
    skill_md = (here.parent / "SKILL.md").resolve()
    fm_version, fm_updated = read_skill_frontmatter(skill_md)
    data.setdefault("skill_version", args.skill_version or fm_version or "unknown")
    data.setdefault("skill_updated", args.skill_updated or fm_updated or "unknown")

    # Bank-clearance verification has moved out of sale-audit into a
    # separate skill (per §9 redesign); the report no longer stamps the
    # bank-ledger release version in its footer. The previous read from
    # ../bank-ledger/SKILL.md is intentionally gone — sale-audit no
    # longer requires the bank-ledger skill to be installed at all.

    data.setdefault("generated_at", datetime.now().strftime("%Y-%m-%d %H:%M"))
    data.setdefault("language", args.lang)

    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(enabled_extensions=("html", "xml", "j2")),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    # to_roman is kept as a defined helper (no-op safety net) but is
    # NOT wired to the template anymore — per §9.4, findings now render
    # as Arabic numerals (FINDING 1, 2, 3 ...). Cross-references in
    # other rows cite the matching integer too. If a future redesign
    # ever wants Roman back, re-add the filter wiring here.
    _ = to_roman  # intentionally unused; keep helper available

    # Read audit.css and inline it into the template. The HTML must be
    # self-contained because step 2 of the production flow hands it to
    # anthropic-skills:pdf at a scratch path; a relative <link href="audit.css">
    # would not resolve and the rasterizer would emit an unstyled "plain"
    # PDF (this regression bit us on 2026-05-01 — see SKILL.md §7.1).
    audit_css_path = templates_dir / "audit.css"
    if not audit_css_path.exists():
        sys.exit(f"audit.css not found at {audit_css_path}")
    audit_css = audit_css_path.read_text(encoding="utf-8")

    template = env.get_template("audit.html.j2")
    html = template.render(data=data, labels=labels, audit_css=audit_css)

    suffix = out_path.suffix.lower()
    if suffix == ".html":
        out_path.write_text(html, encoding="utf-8")
        print(f"Rendered HTML -> {out_path}")
        return

    if suffix == ".pdf":
        try:
            from weasyprint import HTML
        except ImportError:
            sys.exit("PDF output requires weasyprint (pip install weasyprint)")
        # base_url so the <link rel="stylesheet" href="audit.css"> resolves
        # against the templates folder.
        HTML(string=html, base_url=str(templates_dir) + "/").write_pdf(str(out_path))
        print(f"Rendered PDF -> {out_path}")
        return

    sys.exit(f"Unsupported output extension: {suffix} (use .html or .pdf)")


if __name__ == "__main__":
    main()
