"""
Node War - Automated Guidebook & Handbook Document Generator
=============================================================
Converts Markdown guidebooks in docs/ into:
1. Microsoft Word (.docx) documents with professional corporate/esports styling.
2. High-resolution PDF (.pdf) documents via headless Microsoft Edge print engine.
"""

from __future__ import annotations
import os
import re
import sys
import shutil
import subprocess
from typing import List, Dict, Tuple, Optional

import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import nsdecls, qn

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS_DIR = os.path.join(PROJECT_ROOT, "docs")

# Color Palette: Deep Esports Royal
NAVY = RGBColor(30, 58, 138)       # #1E3A8A
ROYAL_BLUE = RGBColor(37, 99, 235)  # #2563EB
SLATE = RGBColor(51, 65, 85)        # #334155
CHARCOAL = RGBColor(30, 41, 59)     # #1E293B
GOLD = RGBColor(217, 119, 6)        # #D97706
CODE_BG = "F8FAFC"
HEADER_BG = "1E3A8A"
ALT_ROW_BG = "F1F5F9"
BORDER_COLOR = "CBD5E1"


def set_cell_background(cell, color_hex: str):
    """Sets background color of a Word table cell."""
    tcPr = cell._element.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color_hex}"/>')
    tcPr.append(shd)


def set_cell_margins(cell, top=100, bottom=100, left=140, right=140):
    """Sets cell padding in dxa (1 pt = 20 dxa)."""
    tcPr = cell._element.get_or_add_tcPr()
    tcMar = parse_xml(
        f'<w:tcMar {nsdecls("w")}>'
        f'<w:top w:w="{top}" w:type="dxa"/>'
        f'<w:bottom w:w="{bottom}" w:type="dxa"/>'
        f'<w:left w:w="{left}" w:type="dxa"/>'
        f'<w:right w:w="{right}" w:type="dxa"/>'
        f'</w:tcMar>'
    )
    tcPr.append(tcMar)


def build_docx_from_markdown(md_path: str, docx_path: str, title: str, subtitle: str):
    """Parses markdown file and constructs a beautifully styled docx file."""
    with open(md_path, "r", encoding="utf-8") as f:
        md_text = f.read()

    doc = docx.Document()

    # Page Margins (0.75 inch)
    for section in doc.sections:
        section.top_margin = Inches(0.75)
        section.bottom_margin = Inches(0.75)
        section.left_margin = Inches(0.75)
        section.right_margin = Inches(0.75)

    # Base Normal style
    style_normal = doc.styles["Normal"]
    style_normal.font.name = "Arial"
    style_normal.font.size = Pt(10)
    style_normal.font.color.rgb = CHARCOAL
    style_normal.paragraph_format.line_spacing = 1.2
    style_normal.paragraph_format.space_after = Pt(5)

    # Document Header Title
    title_p = doc.add_paragraph()
    title_p.paragraph_format.space_before = Pt(4)
    title_p.paragraph_format.space_after = Pt(2)
    run_title = title_p.add_run(title)
    run_title.font.name = "Arial"
    run_title.font.size = Pt(20)
    run_title.font.bold = True
    run_title.font.color.rgb = NAVY

    sub_p = doc.add_paragraph()
    sub_p.paragraph_format.space_after = Pt(12)
    run_sub = sub_p.add_run(subtitle)
    run_sub.font.name = "Arial"
    run_sub.font.size = Pt(10.5)
    run_sub.font.italic = True
    run_sub.font.color.rgb = SLATE

    # Horizontal Divider Bar
    div_p = doc.add_paragraph()
    div_p.paragraph_format.space_after = Pt(12)
    run_div = div_p.add_run("―" * 55)
    run_div.font.color.rgb = ROYAL_BLUE
    run_div.font.size = Pt(8)

    # Parse lines
    lines = md_text.splitlines()
    in_code_block = False
    code_lines = []
    in_table = False
    table_lines = []

    def flush_table():
        nonlocal table_lines, in_table
        if not table_lines:
            return
        rows_data = []
        for tl in table_lines:
            cells = [c.strip() for c in tl.strip().strip("|").split("|")]
            if all(set(c).issubset({"-", ":", " "}) for c in cells):
                continue  # separator line
            rows_data.append(cells)
        if not rows_data:
            table_lines = []
            in_table = False
            return

        col_count = max(len(r) for r in rows_data)
        table = doc.add_table(rows=len(rows_data), cols=col_count)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER

        for r_idx, row in enumerate(rows_data):
            for c_idx in range(col_count):
                cell_text = row[c_idx] if c_idx < len(row) else ""
                cell = table.cell(r_idx, c_idx)
                cell.text = cell_text
                set_cell_margins(cell, top=80, bottom=80, left=110, right=110)

                p = cell.paragraphs[0]
                p.paragraph_format.space_after = Pt(2)
                p.paragraph_format.space_before = Pt(2)
                p.paragraph_format.line_spacing = 1.1

                if r_idx == 0:
                    set_cell_background(cell, HEADER_BG)
                    for run in p.runs:
                        run.font.bold = True
                        run.font.color.rgb = RGBColor(255, 255, 255)
                        run.font.size = Pt(8.5)
                else:
                    if r_idx % 2 == 1:
                        set_cell_background(cell, ALT_ROW_BG)
                    for run in p.runs:
                        run.font.size = Pt(8.5)
                        run.font.color.rgb = CHARCOAL

        doc.add_paragraph().paragraph_format.space_after = Pt(6)
        table_lines = []
        in_table = False

    def flush_code():
        nonlocal code_lines, in_code_block
        if not code_lines:
            return
        code_text = "\n".join(code_lines)
        code_table = doc.add_table(rows=1, cols=1)
        code_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = code_table.cell(0, 0)
        set_cell_background(cell, CODE_BG)
        set_cell_margins(cell, top=100, bottom=100, left=140, right=140)
        p = cell.paragraphs[0]
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.line_spacing = 1.15
        run = p.add_run(code_text)
        run.font.name = "Consolas"
        run.font.size = Pt(8)
        run.font.color.rgb = CHARCOAL
        doc.add_paragraph().paragraph_format.space_after = Pt(6)
        code_lines = []
        in_code_block = False

    i = 0
    while i < len(lines):
        line = lines[i]

        # Code block fence
        if line.strip().startswith("```"):
            if in_code_block:
                flush_code()
            else:
                if in_table:
                    flush_table()
                in_code_block = True
                code_lines = []
            i += 1
            continue

        if in_code_block:
            code_lines.append(line)
            i += 1
            continue

        # Table row
        if line.strip().startswith("|") and line.strip().endswith("|"):
            in_table = True
            table_lines.append(line)
            i += 1
            continue
        elif in_table:
            flush_table()

        # Skip main markdown H1 (handled by custom header title)
        if line.startswith("# ") and i < 3:
            i += 1
            continue
        if line.startswith("**Autonomous") or line.startswith("*Document Version") or line.startswith("**A Systematic"):
            i += 1
            continue
        if line.strip() == "---":
            i += 1
            continue

        # Headings
        if line.startswith("## "):
            h = doc.add_paragraph()
            h.paragraph_format.space_before = Pt(14)
            h.paragraph_format.space_after = Pt(4)
            run = h.add_run(line[3:].strip())
            run.font.name = "Arial"
            run.font.size = Pt(13)
            run.font.bold = True
            run.font.color.rgb = NAVY
            i += 1
            continue

        if line.startswith("### "):
            h = doc.add_paragraph()
            h.paragraph_format.space_before = Pt(10)
            h.paragraph_format.space_after = Pt(3)
            run = h.add_run(line[4:].strip())
            run.font.name = "Arial"
            run.font.size = Pt(11)
            run.font.bold = True
            run.font.color.rgb = ROYAL_BLUE
            i += 1
            continue

        if line.startswith("#### "):
            h = doc.add_paragraph()
            h.paragraph_format.space_before = Pt(8)
            h.paragraph_format.space_after = Pt(2)
            run = h.add_run(line[5:].strip())
            run.font.name = "Arial"
            run.font.size = Pt(10)
            run.font.bold = True
            run.font.color.rgb = SLATE
            i += 1
            continue

        # Blockquote / Alert callout
        if line.startswith("> "):
            callout_text = line[2:].strip()
            j = i + 1
            while j < len(lines) and lines[j].startswith("> "):
                callout_text += " " + lines[j][2:].strip()
                j += 1
            i = j

            c_table = doc.add_table(rows=1, cols=1)
            c_table.alignment = WD_TABLE_ALIGNMENT.CENTER
            cell = c_table.cell(0, 0)
            set_cell_background(cell, "EFF6FF")
            set_cell_margins(cell, top=80, bottom=80, left=140, right=140)
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.space_before = Pt(0)
            run = p.add_run(callout_text)
            run.font.italic = True
            run.font.size = Pt(9.5)
            run.font.color.rgb = NAVY
            doc.add_paragraph().paragraph_format.space_after = Pt(5)
            continue

        # Bullet List Item
        if line.strip().startswith("- ") or line.strip().startswith("* "):
            content = line.strip()[2:]
            bp = doc.add_paragraph(style="List Bullet")
            bp.paragraph_format.space_after = Pt(2.5)
            bp.paragraph_format.space_before = Pt(0)
            _add_markdown_styled_runs(bp, content)
            i += 1
            continue

        # Numbered List Item
        match_num = re.match(r"^(\d+)\.\s+(.*)$", line.strip())
        if match_num:
            content = match_num.group(2)
            np = doc.add_paragraph(style="List Number")
            np.paragraph_format.space_after = Pt(2.5)
            np.paragraph_format.space_before = Pt(0)
            _add_markdown_styled_runs(np, content)
            i += 1
            continue

        # Normal Paragraph
        if line.strip():
            p = doc.add_paragraph()
            _add_markdown_styled_runs(p, line.strip())

        i += 1

    if in_table:
        flush_table()
    if in_code_block:
        flush_code()

    doc.save(docx_path)
    print(f"✓ Generated Word document: {docx_path}")


def _add_markdown_styled_runs(paragraph, text: str):
    """Splits inline markdown bold, italic, code spans into Word runs."""
    tokens = re.split(r"(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*)", text)
    for token in tokens:
        if not token:
            continue
        if token.startswith("`") and token.endswith("`"):
            code_str = token[1:-1]
            run = paragraph.add_run(code_str)
            run.font.name = "Consolas"
            run.font.size = Pt(9)
            run.font.color.rgb = RGBColor(180, 83, 9)
        elif token.startswith("**") and token.endswith("**"):
            bold_str = token[2:-2]
            run = paragraph.add_run(bold_str)
            run.font.bold = True
            run.font.color.rgb = CHARCOAL
        elif token.startswith("*") and token.endswith("*"):
            italic_str = token[1:-1]
            run = paragraph.add_run(italic_str)
            run.font.italic = True
            run.font.color.rgb = SLATE
        else:
            clean_str = token.replace("$", "")
            run = paragraph.add_run(clean_str)
            run.font.color.rgb = CHARCOAL


def build_html_for_pdf(md_path: str, html_path: str, title: str, subtitle: str, badge: str):
    """Builds an executive HTML document formatted specifically for print to PDF."""
    with open(md_path, "r", encoding="utf-8") as f:
        md_text = f.read()

    # Enable table parsing in markdown-it-py!
    from markdown_it import MarkdownIt
    md = MarkdownIt().enable('table')
    content_html = md.render(md_text)

    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

  @page {{
    size: A4 portrait;
    margin: 14mm 12mm 14mm 12mm;
    @bottom-right {{
      content: counter(page);
      font-family: 'Inter', sans-serif;
      font-size: 8pt;
      color: #64748b;
    }}
  }}

  * {{
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }}

  body {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    color: #1e293b;
    background: #ffffff;
    line-height: 1.5;
    font-size: 9.5pt;
    padding: 0;
  }}

  .header-banner {{
    border-bottom: 3px solid #1e3a8a;
    padding-bottom: 10px;
    margin-bottom: 16px;
  }}

  .header-badge {{
    display: inline-block;
    background: #1e3a8a;
    color: #ffffff;
    font-size: 7.5pt;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    padding: 2.5px 7px;
    border-radius: 3px;
    margin-bottom: 6px;
  }}

  h1 {{
    font-size: 18pt;
    font-weight: 800;
    color: #1e3a8a;
    line-height: 1.2;
    margin-bottom: 3px;
  }}

  .subtitle {{
    font-size: 10pt;
    font-weight: 500;
    color: #475569;
    margin-bottom: 5px;
  }}

  .meta-bar {{
    font-size: 8pt;
    color: #64748b;
  }}

  h2 {{
    font-size: 12pt;
    font-weight: 700;
    color: #1e3a8a;
    margin-top: 18px;
    margin-bottom: 6px;
    border-bottom: 1px solid #e2e8f0;
    padding-bottom: 3px;
    page-break-after: avoid;
  }}

  h3 {{
    font-size: 10.5pt;
    font-weight: 700;
    color: #2563eb;
    margin-top: 12px;
    margin-bottom: 4px;
    page-break-after: avoid;
  }}

  h4 {{
    font-size: 9.5pt;
    font-weight: 600;
    color: #334155;
    margin-top: 8px;
    margin-bottom: 3px;
    page-break-after: avoid;
  }}

  p {{
    margin-bottom: 7px;
  }}

  ul, ol {{
    margin-left: 18px;
    margin-bottom: 8px;
  }}

  li {{
    margin-bottom: 2.5px;
  }}

  table {{
    width: 100%;
    border-collapse: collapse;
    margin: 10px 0 14px 0;
    font-size: 8pt;
    page-break-inside: avoid;
  }}

  th {{
    background: #1e3a8a;
    color: #ffffff;
    font-weight: 700;
    text-align: left;
    padding: 5px 8px;
    border: 1px solid #1e3a8a;
    white-space: nowrap;
  }}

  td {{
    padding: 4.5px 8px;
    border: 1px solid #cbd5e1;
    color: #1e293b;
    vertical-align: top;
  }}

  tr:nth-child(even) td {{
    background: #f8fafc;
  }}

  pre {{
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-left: 3.5px solid #2563eb;
    border-radius: 4px;
    padding: 7px 10px;
    margin: 8px 0 12px 0;
    font-family: 'JetBrains Mono', 'Consolas', monospace;
    font-size: 7.5pt;
    line-height: 1.35;
    color: #0f172a;
    overflow-x: hidden;
    white-space: pre-wrap;
    word-break: break-word;
    page-break-inside: avoid;
  }}

  code {{
    font-family: 'JetBrains Mono', 'Consolas', monospace;
    font-size: 8pt;
    background: #f1f5f9;
    color: #b45309;
    padding: 1px 3.5px;
    border-radius: 3px;
  }}

  pre code {{
    background: transparent;
    color: inherit;
    padding: 0;
    white-space: pre-wrap;
  }}

  blockquote {{
    background: #eff6ff;
    border-left: 3.5px solid #2563eb;
    padding: 6px 12px;
    margin: 8px 0 10px 0;
    border-radius: 0 4px 4px 0;
    font-size: 9pt;
    color: #1e3a8a;
    page-break-inside: avoid;
  }}

  hr {{
    border: none;
    border-top: 1px solid #e2e8f0;
    margin: 14px 0;
  }}

  strong {{
    font-weight: 700;
    color: #0f172a;
  }}

  .footer {{
    margin-top: 24px;
    border-top: 1px solid #cbd5e1;
    padding-top: 6px;
    font-size: 7.5pt;
    color: #94a3b8;
    text-align: center;
  }}
</style>
</head>
<body>

<div class="header-banner">
  <div class="header-badge">{badge}</div>
  <h1>{title}</h1>
  <div class="subtitle">{subtitle}</div>
  <div class="meta-bar">Campus AI Hackathon Series • Official Participant Release • Confidential Competition Material</div>
</div>

{content_html}

<div class="footer">
  Autonomous AI Simulation Tournament • Participant Manual • All Rights Reserved
</div>

</body>
</html>"""

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(full_html)
    print(f"✓ Generated HTML print source: {html_path}")


def convert_html_to_pdf_via_edge(html_path: str, pdf_path: str):
    """Executes Microsoft Edge in headless mode to convert HTML to a high-res PDF."""
    edge_paths = [
        shutil.which("msedge"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        shutil.which("chrome"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    ]
    browser_bin = next((p for p in edge_paths if p and os.path.exists(p)), None)
    if not browser_bin:
        print("⚠️ Warning: Neither Microsoft Edge nor Google Chrome found. Skipping PDF generation.")
        return False

    abs_html = os.path.abspath(html_path)
    abs_pdf = os.path.abspath(pdf_path)

    cmd = [
        browser_bin,
        "--headless",
        "--disable-gpu",
        "--run-all-compositor-stages-before-draw",
        "--no-pdf-header-footer",
        f"--print-to-pdf={abs_pdf}",
        f"file:///{abs_html}"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if res.returncode == 0 and os.path.exists(abs_pdf) and os.path.getsize(abs_pdf) > 0:
        print(f"✓ Generated High-Resolution PDF ({os.path.getsize(abs_pdf):,} bytes): {pdf_path}")
        return True
    else:
        print(f"❌ PDF generation failed: {res.stderr}")
        return False


def main():
    print("=" * 65)
    print("   NODE WAR - PARTICIPANT GUIDEBOOK & HANDBOOK COMPILER")
    print("=" * 65)

    docs = [
        {
            "id": "game_guidebook",
            "md": os.path.join(DOCS_DIR, "NODE_WAR_OFFICIAL_GAME_GUIDEBOOK.md"),
            "docx": os.path.join(DOCS_DIR, "NODE_WAR_OFFICIAL_GAME_GUIDEBOOK.docx"),
            "html": os.path.join(DOCS_DIR, "NODE_WAR_OFFICIAL_GAME_GUIDEBOOK.html"),
            "pdf": os.path.join(DOCS_DIR, "NODE_WAR_OFFICIAL_GAME_GUIDEBOOK.pdf"),
            "title": "NODE WAR // Official Competitor Guidebook",
            "subtitle": "Rules, Economics, Lanchester Combat, Dynamic Supply Lines & API Reference",
            "badge": "OFFICIAL PARTICIPANT MANUAL"
        },
        {
            "id": "engineering_handbook",
            "md": os.path.join(DOCS_DIR, "COMPETITIVE_BOT_ENGINEERING_HANDBOOK.md"),
            "docx": os.path.join(DOCS_DIR, "COMPETITIVE_BOT_ENGINEERING_HANDBOOK.docx"),
            "html": os.path.join(DOCS_DIR, "COMPETITIVE_BOT_ENGINEERING_HANDBOOK.html"),
            "pdf": os.path.join(DOCS_DIR, "COMPETITIVE_BOT_ENGINEERING_HANDBOOK.pdf"),
            "title": "THE ART OF TOURNAMENT BOT CRAFT",
            "subtitle": "A Systematic Engineering Playbook & Architectural Framework for Strategy Bot Tournaments",
            "badge": "COMPETITIVE STRATEGY HANDBOOK"
        }
    ]

    for d in docs:
        print(f"\nProcessing {d['title']}...")
        if not os.path.exists(d["md"]):
            print(f"❌ Source markdown not found: {d['md']}")
            continue

        build_docx_from_markdown(d["md"], d["docx"], d["title"], d["subtitle"])
        build_html_for_pdf(d["md"], d["html"], d["title"], d["subtitle"], d["badge"])
        convert_html_to_pdf_via_edge(d["html"], d["pdf"])

    print("\n" + "=" * 65)
    print("🎉 ALL DOCUMENTS SUCCESSFULLY GENERATED!")
    print("=" * 65)


if __name__ == "__main__":
    main()
