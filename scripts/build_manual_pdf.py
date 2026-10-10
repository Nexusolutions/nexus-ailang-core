#!/usr/bin/env python3
"""Build PDF from the VS Code manual markdown."""
import sys, os

PDF_SKILL_DIR = "/home/z/my-project/skills/pdf"
_scripts = os.path.join(PDF_SKILL_DIR, "scripts")
if _scripts not in sys.path:
    sys.path.insert(0, _scripts)

from pathlib import Path

# Read the markdown
md_path = Path("/home/z/my-project/download/Manual_Usuario_VSCode.md")
md_content = md_path.read_text(encoding="utf-8")

# Use pandoc to convert to HTML, then weasyprint to PDF
import subprocess

html_path = Path("/home/z/my-project/scripts/manual_vscode.html")
html_path.parent.mkdir(parents=True, exist_ok=True)

# CSS for the PDF
CSS = """
@page { size: A4; margin: 20mm 18mm 20mm 18mm; @bottom-center { content: "Nexus AILang-Core — Manual de Usuario · " counter(page) " / " counter(pages); font-size: 9pt; color: #666; } }
html, body { font-family: 'Noto Sans', 'DejaVu Sans', sans-serif; font-size: 10pt; line-height: 1.5; color: #1a1a2e; background: #fff; }
h1 { font-size: 22pt; border-bottom: 3px solid #00d4ff; padding-bottom: 6pt; margin-top: 0; color: #0d1117; }
h2 { font-size: 16pt; border-bottom: 1.5px solid #cbd5e1; padding-bottom: 3pt; margin-top: 22pt; color: #1e293b; }
h3 { font-size: 12pt; margin-top: 16pt; color: #334155; }
h4 { font-size: 11pt; color: #475569; }
p { margin: 4pt 0 6pt 0; }
strong { color: #0d1117; }
code { font-family: 'DejaVu Sans Mono', monospace; font-size: 9pt; background: #f1f5f9; padding: 1pt 4pt; border-radius: 2pt; color: #be123c; }
pre { background: #0d1117; color: #e2e8f0; padding: 10pt 12pt; border-radius: 6pt; font-size: 8.5pt; line-height: 1.4; overflow-x: auto; page-break-inside: avoid; }
pre code { background: transparent; color: inherit; padding: 0; }
table { border-collapse: collapse; width: 100%; margin: 8pt 0 14pt 0; font-size: 9pt; }
th, td { border: 0.5pt solid #cbd5e1; padding: 4pt 6pt; text-align: left; }
th { background: #1e293b; color: #f8fafc; font-weight: 600; }
tbody tr:nth-child(even) { background: #f8fafc; }
hr { border: 0; border-top: 1px solid #cbd5e1; margin: 14pt 0; }
blockquote { border-left: 3pt solid #f59e0b; background: #fffbeb; padding: 4pt 10pt; margin: 8pt 0; color: #78350f; }
a { color: #1d4ed8; text-decoration: none; }
"""

# Convert MD to HTML via pandoc
subprocess.run([
    "pandoc",
    str(md_path),
    "-f", "gfm+pipe_tables+raw_html",
    "-t", "html5",
    "--standalone",
    "--metadata", "title=Manual de Usuario — Nexus AILang-Core en VS Code",
    "--metadata", "author=Enrique Jimenez Garcia",
    "-o", str(html_path),
], check=True)

# Generate PDF via weasyprint
from weasyprint import HTML, CSS as WCSS
output_pdf = "/home/z/my-project/download/Manual_Usuario_VSCode.pdf"

HTML(filename=str(html_path)).write_pdf(
    stylesheets=[WCSS(string=CSS)],
    presentational_hints=True,
)

# Check result
size = os.path.getsize(output_pdf)
print(f"PDF generated: {output_pdf} ({size // 1024} KB)")
