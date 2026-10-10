#!/usr/bin/env python3
"""
Build a single PDF combining the three AILang audit deliverables:
  1. AUDIT_REPORT.md
  2. ROADMAP.md
  3. CONFORMANCE_MATRIX.md

Pipeline: markdown -> pandoc -> HTML -> weasyprint -> PDF.

WeasyPrint is chosen over LaTeX because the source contains Spanish text,
emoji-style status markers (✅ ⚠️ ❌ 🔴 🟠 🟡), and many wide tables;
WeasyPrint handles CSS+tables cleanly without LaTeX font hell.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# --- Paths -------------------------------------------------------------------

DOWNLOAD_DIR = Path("/home/z/my-project/download")
SCRIPTS_DIR = Path("/home/z/my-project/scripts")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)

INPUTS = [
    DOWNLOAD_DIR / "AUDIT_REPORT.md",
    DOWNLOAD_DIR / "ROADMAP.md",
    DOWNLOAD_DIR / "CONFORMANCE_MATRIX.md",
]
OUTPUT_PDF = DOWNLOAD_DIR / "AILang_Audit_Complete.pdf"
COMBINED_MD = SCRIPTS_DIR / "ailang_audit_combined.md"

# --- CSS for WeasyPrint ------------------------------------------------------

CSS = r"""
@page {
    size: A4 landscape;
    margin: 18mm 14mm 18mm 14mm;
    @bottom-center {
        content: "AILang Audit · " counter(page) " / " counter(pages);
        font-family: 'Noto Sans', 'DejaVu Sans', sans-serif;
        font-size: 9pt;
        color: #6b7280;
    }
    @top-right {
        content: "Confidencial · Auditoría técnica";
        font-family: 'Noto Sans', 'DejaVu Sans', sans-serif;
        font-size: 8pt;
        color: #9ca3af;
    }
}
@page :first {
    @top-right { content: ""; }
    @bottom-center { content: ""; }
}

html, body {
    font-family: 'Noto Sans', 'DejaVu Sans', sans-serif;
    font-size: 9.5pt;
    line-height: 1.45;
    color: #1f2937;
    background: #ffffff;
}

h1, h2, h3, h4, h5, h6 {
    font-family: 'Noto Sans', 'DejaVu Sans', sans-serif;
    color: #0f172a;
    page-break-after: avoid;
    page-break-inside: avoid;
}
h1 {
    font-size: 22pt;
    border-bottom: 3px solid #0f172a;
    padding-bottom: 6pt;
    margin-top: 0;
    margin-bottom: 14pt;
    page-break-before: always;
}
h1:first-of-type { page-break-before: avoid; }
h2 {
    font-size: 15pt;
    border-bottom: 1.5px solid #cbd5e1;
    padding-bottom: 3pt;
    margin-top: 22pt;
    margin-bottom: 10pt;
    color: #1e293b;
}
h3 {
    font-size: 12pt;
    margin-top: 16pt;
    margin-bottom: 6pt;
    color: #334155;
}
h4 {
    font-size: 10.5pt;
    margin-top: 12pt;
    margin-bottom: 4pt;
    color: #475569;
}

p {
    margin: 4pt 0 6pt 0;
    orphans: 3;
    widows: 3;
}

strong { color: #0f172a; font-weight: 700; }
em { color: #334155; }

code, pre, tt {
    font-family: 'DejaVu Sans Mono', 'Liberation Mono', monospace;
    font-size: 8.5pt;
}
code {
    background: #f1f5f9;
    padding: 0.5pt 3pt;
    border-radius: 2pt;
    color: #be123c;
}
pre {
    background: #0f172a;
    color: #e2e8f0;
    padding: 8pt 10pt;
    border-radius: 4pt;
    overflow-x: auto;
    page-break-inside: avoid;
    font-size: 8pt;
    line-height: 1.35;
    margin: 8pt 0;
}
pre code {
    background: transparent;
    color: inherit;
    padding: 0;
}

table {
    border-collapse: collapse;
    width: 100%;
    margin: 8pt 0 14pt 0;
    font-size: 8.2pt;
    page-break-inside: auto;
}
thead { display: table-header-group; }
tr { page-break-inside: avoid; }
th, td {
    border: 0.5pt solid #cbd5e1;
    padding: 3pt 5pt;
    text-align: left;
    vertical-align: top;
}
th {
    background: #1e293b;
    color: #f8fafc;
    font-weight: 600;
    font-size: 8pt;
}
tbody tr:nth-child(even) { background: #f8fafc; }

/* Make wide tables horizontally compact */
table code { font-size: 7.5pt; }

hr {
    border: 0;
    border-top: 1px solid #cbd5e1;
    margin: 14pt 0;
}

ul, ol {
    margin: 4pt 0 8pt 0;
    padding-left: 18pt;
}
li { margin: 2pt 0; }

blockquote {
    border-left: 3pt solid #f59e0b;
    background: #fffbeb;
    padding: 4pt 10pt;
    margin: 8pt 0;
    color: #78350f;
}

a { color: #1d4ed8; text-decoration: none; }
a:hover { text-decoration: underline; }

/* Section divider between the three documents */
.doc-divider {
    page-break-before: always;
    border-top: 4px double #0f172a;
    padding-top: 8pt;
    margin-top: 24pt;
}
"""

# --- Build -------------------------------------------------------------------

def combine_markdown() -> None:
    """Concatenate the three markdown files with explicit document dividers."""
    parts = []
    for i, path in enumerate(INPUTS):
        if not path.exists():
            print(f"ERROR: missing input {path}", file=sys.stderr)
            sys.exit(1)
        text = path.read_text(encoding="utf-8")
        if i > 0:
            parts.append("\n\n<div class='doc-divider'></div>\n\n")
        parts.append(text)
    COMBINED_MD.write_text("".join(parts), encoding="utf-8")
    print(f"Combined markdown -> {COMBINED_MD} ({COMBINED_MD.stat().st_size} bytes)")


def render_pdf() -> None:
    """Use pandoc to convert markdown -> standalone HTML, then weasyprint to PDF."""
    html_path = SCRIPTS_DIR / "ailang_audit_combined.html"
    css_path = SCRIPTS_DIR / "ailang_audit.css"
    css_path.write_text(CSS, encoding="utf-8")

    # 1. Markdown -> HTML5 with pandoc (preserves tables, code blocks, etc.)
    pandoc_cmd = [
        "pandoc",
        str(COMBINED_MD),
        "-f", "gfm+pipe_tables+raw_html",
        "-t", "html5",
        "--standalone",
        "--metadata", "title=AILang — Auditoría Completa del Repositorio",
        "--metadata", "author=Arquitecto de Lenguajes / Ingeniero Senior de Compiladores",
        "--metadata", "date=2026-10-10",
        "-o", str(html_path),
    ]
    print("Running:", " ".join(pandoc_cmd))
    subprocess.run(pandoc_cmd, check=True)
    print(f"HTML -> {html_path} ({html_path.stat().st_size} bytes)")

    # 2. HTML -> PDF with WeasyPrint
    from weasyprint import HTML, CSS as WCSS
    pdf_bytes = HTML(filename=str(html_path)).write_pdf(
        stylesheets=[WCSS(string=CSS)],
        presentational_hints=True,
    )
    OUTPUT_PDF.write_bytes(pdf_bytes)
    print(f"PDF -> {OUTPUT_PDF} ({OUTPUT_PDF.stat().st_size} bytes)")


def main() -> int:
    combine_markdown()
    render_pdf()
    # Quick verification
    size_kb = OUTPUT_PDF.stat().st_size // 1024
    print(f"\nOK: produced {OUTPUT_PDF.name} ({size_kb} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
