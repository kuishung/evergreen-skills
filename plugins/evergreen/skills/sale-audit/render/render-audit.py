#!/usr/bin/env python3
"""
Render an Evergreen sale-audit PDF deterministically.

Inputs (all required):
  --data        Path to audit-data JSON file (schema: see ../templates/audit-data.schema.md)
  --lang        en | cn   (which label pack to use)
  --out         Output path; .pdf to render PDF, .html to write rendered HTML for inspection

Optional:
  --templates   Path to the templates folder (default: sibling ../templates/)
  --skill-version  Override the v… stamp (default: read from ../SKILL.md frontmatter)
  --skill-updated  Override the amended-date stamp (default: read from ../SKILL.md frontmatter)

Examples:
  # Render English HTML for visual inspection (no PDF deps required):
  python render-audit.py --data ../templates/sample-data.json --lang en --out /tmp/audit.html

  # Render the matching PDF (requires `pip install weasyprint`):
  python render-audit.py --data ../templates/sample-data.json --lang en --out /tmp/audit.pdf

Dependencies:
  jinja2       (always)            pip install jinja2
  weasyprint   (PDF output only)   pip install weasyprint
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


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
    data.setdefault("generated_at", datetime.now().strftime("%Y-%m-%d %H:%M"))
    data.setdefault("language", args.lang)

    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(enabled_extensions=("html", "xml", "j2")),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    template = env.get_template("audit.html.j2")
    html = template.render(data=data, labels=labels)

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
