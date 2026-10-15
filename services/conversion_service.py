import os
import io
import zipfile
import subprocess
from pathlib import Path
from typing import List, Tuple, Optional

import fitz  # PyMuPDF
from PIL import Image
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
import pdfplumber
from pptx import Presentation
from pptx.util import Inches, Pt
from docx import Document

from config import Config
from utils.system_checker import find_libreoffice
from services.job_service import job_service

# Conversion Registry type: dict[(from_ext, to_ext), handler_fn]
CONVERSION_REGISTRY = {}

def register_converter(from_ext: str, to_ext: str):
    def decorator(fn):
        CONVERSION_REGISTRY[(from_ext.lower(), to_ext.lower())] = fn
        return fn
    return decorator


@register_converter("pdf", "docx")
def convert_pdf_to_docx(input_path: str, output_path: str, job_id: Optional[str] = None, **kwargs) -> str:
    """Convert PDF to DOCX using pdf2docx."""
    from pdf2docx import Converter
    
    if job_id:
        job_service.set_progress(job_id, 20, "Analyzing layout and reading PDF...")
        
    cv = Converter(input_path)
    try:
        if job_id:
            job_service.set_progress(job_id, 50, "Synthesizing Word structures & formatting...")
        cv.convert(output_path, start=0, end=None)
        if job_id:
            job_service.set_progress(job_id, 90, "Finalizing DOCX document...")
    finally:
        cv.close()
        
    return output_path


@register_converter("pdf", "pptx")
def convert_pdf_to_pptx(input_path: str, output_path: str, job_id: Optional[str] = None, mode: str = "visual", **kwargs) -> str:
    """
    Convert PDF to PPTX presentation.
    Modes:
      - 'visual': Render pages as sharp full-slide background images.
      - 'editable': Extract text blocks, shapes, and positions onto presentation slides.
    """
    doc = fitz.open(input_path)
    prs = Presentation()
    blank_slide_layout = prs.slide_layouts[6]  # Blank slide
    
    total_pages = len(doc)
    if total_pages > Config.MAX_PAGE_LIMIT:
        raise ValueError(f"Document exceeds maximum supported page limit ({Config.MAX_PAGE_LIMIT}).")
        
    for idx, page in enumerate(doc):
        if job_id:
            pct = int(10 + (idx / max(1, total_pages)) * 80)
            job_service.set_progress(job_id, pct, f"Converting slide {idx + 1} of {total_pages}...")
            
        rect = page.rect
        # Set presentation slide size to match first page aspect ratio
        if idx == 0:
            prs.slide_width = Inches(rect.width / 72.0)
            prs.slide_height = Inches(rect.height / 72.0)
            
        slide = prs.slides.add_slide(blank_slide_layout)
        
        if mode == "editable":
            # Extract text blocks and reconstruct as text boxes
            text_instances = page.get_text("blocks")
            # Also insert rendered background at subtle opacity or keep clean text
            has_elements = False
            for b in text_instances:
                # b: (x0, y0, x1, y1, text, block_no, block_type)
                if len(b) >= 5 and b[4].strip():
                    x0, y0, x1, y1 = b[0], b[1], b[2], b[3]
                    text = b[4].strip()
                    left = Inches(x0 / 72.0)
                    top = Inches(y0 / 72.0)
                    width = Inches(max(10, x1 - x0) / 72.0)
                    height = Inches(max(10, y1 - y0) / 72.0)
                    
                    txBox = slide.shapes.add_textbox(left, top, width, height)
                    tf = txBox.text_frame
                    tf.word_wrap = True
                    tf.text = text
                    has_elements = True
            
            # If page had no text (e.g. pure scanned or artwork), fallback to visual slide
            if not has_elements:
                pix = page.get_pixmap(dpi=150)
                img_bytes = pix.tobytes("png")
                slide.shapes.add_picture(io.BytesIO(img_bytes), 0, 0, width=prs.slide_width, height=prs.slide_height)
        else:
            # High-fidelity visual mode
            pix = page.get_pixmap(dpi=180)
            img_bytes = pix.tobytes("png")
            slide.shapes.add_picture(io.BytesIO(img_bytes), 0, 0, width=prs.slide_width, height=prs.slide_height)
            
    doc.close()
    prs.save(output_path)
    return output_path


@register_converter("pdf", "xlsx")
def convert_pdf_to_xlsx(input_path: str, output_path: str, job_id: Optional[str] = None, **kwargs) -> str:
    """
    Extract tables from PDF into an Excel spreadsheet.
    Preserves rows, columns, and creates formatted worksheets.
    """
    wb = openpyxl.Workbook()
    # Remove default sheet
    wb.remove(wb.active)
    
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
    cell_font = Font(name="Segoe UI", size=10)
    thin_border = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )
    
    table_count = 0
    with pdfplumber.open(input_path) as pdf:
        total_pages = len(pdf.pages)
        for page_idx, page in enumerate(pdf.pages):
            if job_id:
                pct = int(15 + (page_idx / max(1, total_pages)) * 75)
                job_service.set_progress(job_id, pct, f"Scanning tables on page {page_idx + 1}...")
                
            tables = page.extract_tables()
            if not tables:
                # Fallback: extract words/lines as rows if no formal table grid detected
                text_lines = page.extract_text()
                if text_lines:
                    ws = wb.create_sheet(title=f"Page {page_idx + 1} Text")
                    table_count += 1
                    for r_idx, line in enumerate(text_lines.splitlines(), start=1):
                        cell = ws.cell(row=r_idx, column=1, value=line.strip())
                        cell.font = cell_font
                continue
                
            for t_idx, table in enumerate(tables):
                table_count += 1
                sheet_title = f"P{page_idx + 1}_Table{t_idx + 1}"[:31]
                ws = wb.create_sheet(title=sheet_title)
                
                for row_idx, row in enumerate(table, start=1):
                    for col_idx, cell_value in enumerate(row, start=1):
                        clean_val = cell_value.strip() if isinstance(cell_value, str) else cell_value
                        cell = ws.cell(row=row_idx, column=col_idx, value=clean_val)
                        cell.border = thin_border
                        
                        if row_idx == 1:
                            cell.fill = header_fill
                            cell.font = header_font
                            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                        else:
                            cell.font = cell_font
                            cell.alignment = Alignment(vertical="center", wrap_text=True)
                            
                # Auto-adjust column widths
                for col in ws.columns:
                    max_len = max(len(str(cell.value or '')) for cell in col)
                    col_letter = openpyxl.utils.get_column_letter(col[0].column)
                    ws.column_dimensions[col_letter].width = min(50, max(12, max_len + 3))

    if table_count == 0:
        # Create a note sheet if document contained no structured tabular data
        ws = wb.create_sheet(title="Extraction Notice")
        ws.cell(row=1, column=1, value="No tables were identified in the PDF document.")
        ws.cell(row=2, column=1, value="DocuFlex attempted standard grid detection. Ensure your document contains tabular data.")
        
    wb.save(output_path)
    return output_path


@register_converter("pdf", "jpg")
@register_converter("pdf", "jpeg")
@register_converter("pdf", "png")
def convert_pdf_to_images(input_path: str, output_path: str, target_format: str = "png", dpi: int = 150, job_id: Optional[str] = None, **kwargs) -> str:
    """
    Render PDF pages to images.
    If 1 page, saves image directly.
    If multiple pages, packs into a ZIP archive.
    """
    doc = fitz.open(input_path)
    total_pages = len(doc)
    fmt = "jpeg" if target_format.lower() in ("jpg", "jpeg") else "png"
    ext = "jpg" if fmt == "jpeg" else "png"
    
    if total_pages == 1:
        page = doc[0]
        pix = page.get_pixmap(dpi=dpi)
        pix.save(output_path)
        doc.close()
        return output_path
        
    # Multi-page -> Create ZIP archive
    zip_path = output_path if output_path.endswith(".zip") else output_path + ".zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for idx, page in enumerate(doc):
            if job_id:
                pct = int(10 + (idx / max(1, total_pages)) * 80)
                job_service.set_progress(job_id, pct, f"Rendering page {idx + 1} of {total_pages}...")
            pix = page.get_pixmap(dpi=dpi)
            img_data = pix.tobytes(fmt)
            zipf.writestr(f"page_{idx + 1:03d}.{ext}", img_data)
            
    doc.close()
    return zip_path


@register_converter("png", "pdf")
@register_converter("jpg", "pdf")
@register_converter("jpeg", "pdf")
def convert_images_to_pdf(input_paths: List[str] | str, output_path: str, job_id: Optional[str] = None, **kwargs) -> str:
    """Convert one or multiple image files into a single consolidated PDF."""
    if isinstance(input_paths, str):
        input_paths = [input_paths]
        
    pil_images = []
    first_image = None
    
    for idx, path in enumerate(input_paths):
        if job_id:
            pct = int(10 + (idx / max(1, len(input_paths))) * 70)
            job_service.set_progress(job_id, pct, f"Processing image {idx + 1}...")
        img = Image.open(path)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        if first_image is None:
            first_image = img
        else:
            pil_images.append(img)
            
    if first_image:
        first_image.save(output_path, "PDF", resolution=100.0, save_all=True, append_images=pil_images)
    else:
        raise ValueError("No valid image data provided for PDF generation.")
        
    return output_path


@register_converter("docx", "pdf")
@register_converter("xlsx", "pdf")
@register_converter("pptx", "pdf")
def convert_office_to_pdf(input_path: str, output_path: str, job_id: Optional[str] = None, **kwargs) -> str:
    """
    Convert DOCX/XLSX/PPTX to PDF via LibreOffice headless or native Microsoft Office (Word/Excel/PowerPoint).
    """
    ext = input_path.rsplit(".", 1)[-1].lower()
    abs_input = os.path.abspath(input_path)
    abs_output = os.path.abspath(output_path)
    soffice = find_libreoffice()
    
    # 1. Try LibreOffice if available
    if soffice:
        if job_id:
            job_service.set_progress(job_id, 30, "Invoking LibreOffice headless conversion engine...")
            
        out_dir = os.path.dirname(abs_output)
        input_stem = Path(abs_input).stem
        expected_lo_output = os.path.join(out_dir, f"{input_stem}.pdf")
        
        cmd = [
            soffice,
            "--headless",
            "--convert-to", "pdf",
            "--outdir", out_dir,
            abs_input
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if res.returncode == 0:
            if os.path.exists(expected_lo_output) and expected_lo_output != abs_output:
                if os.path.exists(abs_output):
                    os.remove(abs_output)
                os.rename(expected_lo_output, abs_output)
            if os.path.exists(abs_output):
                return abs_output

    # 2. On Windows, use native Microsoft Word / Excel engine
    if os.name == "nt":
        if ext == "docx":
            if job_id:
                job_service.set_progress(job_id, 40, "Converting Word document via native engine...")
            try:
                import pythoncom
                pythoncom.CoInitialize()
                from docx2pdf import convert
                convert(abs_input, abs_output)
                if os.path.exists(abs_output):
                    return abs_output
            except Exception:
                try:
                    import win32com.client
                    word = win32com.client.Dispatch("Word.Application")
                    word.Visible = False
                    doc = word.Documents.Open(abs_input)
                    doc.SaveAs(abs_output, FileFormat=17) # 17 = wdFormatPDF
                    doc.Close(False)
                    word.Quit()
                    if os.path.exists(abs_output):
                        return abs_output
                except Exception:
                    pass
            finally:
                try:
                    pythoncom.CoUninitialize()
                except Exception:
                    pass

        elif ext == "xlsx":
            if job_id:
                job_service.set_progress(job_id, 40, "Converting Excel workbook via native engine...")
            try:
                import pythoncom
                import win32com.client
                pythoncom.CoInitialize()
                excel = win32com.client.Dispatch("Excel.Application")
                excel.Visible = False
                excel.DisplayAlerts = False
                wb = excel.Workbooks.Open(abs_input)
                wb.ExportAsFixedFormat(0, abs_output) # 0 = xlTypePDF
                wb.Close(False)
                excel.Quit()
                if os.path.exists(abs_output):
                    return abs_output
            except Exception:
                pass
            finally:
                try:
                    pythoncom.CoUninitialize()
                except Exception:
                    pass

        elif ext == "pptx":
            if job_id:
                job_service.set_progress(job_id, 40, "Converting PowerPoint presentation via native engine...")
            try:
                import pythoncom
                import win32com.client
                pythoncom.CoInitialize()
                ppt = win32com.client.Dispatch("PowerPoint.Application")
                pres = ppt.Presentations.Open(abs_input, WithWindow=False)
                pres.SaveAs(abs_output, 32) # 32 = ppSaveAsPDF
                pres.Close()
                ppt.Quit()
                if os.path.exists(abs_output):
                    return abs_output
            except Exception:
                pass
            finally:
                try:
                    pythoncom.CoUninitialize()
                except Exception:
                    pass

    # 3. If neither engine succeeded
    raise RuntimeError(
        "Neither LibreOffice nor Microsoft Office was able to process this Office-to-PDF conversion. "
        "Please install LibreOffice (https://www.libreoffice.org) or ensure Microsoft Office is accessible."
    )

@register_converter("html", "pdf")
def convert_html_to_pdf(input_path: str, output_path: str, job_id: Optional[str] = None, **kwargs) -> str:
    """Convert HTML file to PDF locally using PyMuPDF native HTML conversion engine."""
    with open(input_path, "rb") as f:
        html_bytes = f.read()
    doc = fitz.open("html", html_bytes)
    pdf_bytes = doc.convert_to_pdf()
    with open(output_path, "wb") as f_out:
        f_out.write(pdf_bytes)
    doc.close()
    return output_path

@register_converter("pdf", "pdfa")
def convert_pdf_to_pdfa(input_path: str, output_path: str, job_id: Optional[str] = None, **kwargs) -> str:
    """Convert PDF to PDF/A archival standard format."""
    doc = fitz.open(input_path)
    try:
        doc.set_metadata({
            "format": "PDF/A-1b",
            "title": doc.metadata.get("title", "Archived Document"),
            "author": doc.metadata.get("author", "DocuFlex Local Pro")
        })
        doc.save(output_path, deflate=True, garbage=4, clean=True)
    finally:
        doc.close()
    return output_path

@register_converter("pdf", "md")
def convert_pdf_to_md_handler(input_path: str, output_path: str, job_id: Optional[str] = None, **kwargs) -> str:
    """Convert PDF to structured GitHub-Flavored Markdown."""
    from services.intelligence_service import convert_pdf_to_markdown
    res = convert_pdf_to_markdown(input_path, output_path)
    return res["output_path"]


@register_converter("docx", "xlsx")
def convert_docx_tables_to_xlsx(input_path: str, output_path: str, job_id: Optional[str] = None, **kwargs) -> str:
    """
    Extract all tables from a Word (.docx) document into an Excel spreadsheet.
    """
    doc = Document(input_path)
    if not doc.tables:
        raise ValueError("The provided Word document contains no identifiable tables.")
        
    wb = openpyxl.Workbook()
    wb.remove(wb.active)  # remove default sheet
    
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
    cell_font = Font(name="Segoe UI", size=10)
    thin_border = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )
    
    total_tables = len(doc.tables)
    for t_idx, table in enumerate(doc.tables, start=1):
        if job_id:
            pct = int(10 + (t_idx / max(1, total_tables)) * 80)
            job_service.set_progress(job_id, pct, f"Extracting Word table {t_idx} of {total_tables}...")
            
        ws = wb.create_sheet(title=f"Table_{t_idx}"[:31])
        for r_idx, row in enumerate(table.rows, start=1):
            for c_idx, cell in enumerate(row.cells, start=1):
                clean_text = cell.text.strip()
                c = ws.cell(row=r_idx, column=c_idx, value=clean_text)
                c.border = thin_border
                if r_idx == 1:
                    c.fill = header_fill
                    c.font = header_font
                else:
                    c.font = cell_font
                    
        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = openpyxl.utils.get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = min(50, max(12, max_len + 3))
            
    wb.save(output_path)
    return output_path


def execute_conversion(from_ext: str, to_ext: str, input_path: str, output_path: str, job_id: Optional[str] = None, **options) -> str:
    """Lookup and execute conversion handler from registry."""
    key = (from_ext.lower(), to_ext.lower())
    handler = CONVERSION_REGISTRY.get(key)
    if not handler:
        raise ValueError(f"Conversion from '{from_ext.upper()}' to '{to_ext.upper()}' is not supported.")
    return handler(input_path, output_path, job_id=job_id, **options)
