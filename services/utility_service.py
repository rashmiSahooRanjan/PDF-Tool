import os
import io
import math
from typing import List, Dict, Any, Optional

import fitz  # PyMuPDF
from PIL import Image
from pypdf import PdfReader, PdfWriter

from config import Config
from services.job_service import job_service

def get_pdf_metadata(input_path: str) -> Dict[str, Any]:
    """Extract page count, size, and document metadata."""
    doc = fitz.open(input_path)
    try:
        page_count = len(doc)
        first_page = doc[0] if page_count > 0 else None
        width = round(first_page.rect.width, 1) if first_page else 0
        height = round(first_page.rect.height, 1) if first_page else 0
        
        meta = doc.metadata or {}
        return {
            "page_count": page_count,
            "title": meta.get("title", "") or "Untitled",
            "author": meta.get("author", "") or "Unknown",
            "subject": meta.get("subject", ""),
            "creator": meta.get("creator", ""),
            "producer": meta.get("producer", ""),
            "creation_date": meta.get("creationDate", ""),
            "mod_date": meta.get("modDate", ""),
            "is_encrypted": doc.is_encrypted,
            "dimensions": f"{width} x {height} pt",
            "file_size": os.path.getsize(input_path)
        }
    finally:
        doc.close()

def merge_pdfs(input_paths: List[str], output_path: str, job_id: Optional[str] = None) -> str:
    """Merge multiple PDF files into one in given sequence."""
    if not input_paths:
        raise ValueError("No files provided for merging.")
        
    writer = PdfWriter()
    total = len(input_paths)
    
    for idx, path in enumerate(input_paths):
        if job_id:
            pct = int(10 + (idx / total) * 80)
            job_service.set_progress(job_id, pct, f"Merging document {idx + 1} of {total}...")
        reader = PdfReader(path)
        if reader.is_encrypted:
            raise ValueError(f"File '{os.path.basename(path)}' is password protected. Unlock it first.")
        for page in reader.pages:
            writer.add_page(page)
            
    with open(output_path, "wb") as f_out:
        writer.write(f_out)
        
    return output_path

def parse_page_range(range_str: str, total_pages: int) -> List[int]:
    """
    Parse page selection string like '1-3, 5, 8-10' into 0-indexed list of page integers.
    """
    if not range_str or range_str.strip().lower() == "all":
        return list(range(total_pages))
        
    pages = set()
    parts = [p.strip() for p in range_str.split(",") if p.strip()]
    for part in parts:
        if "-" in part:
            sub = part.split("-")
            start = int(sub[0].strip())
            end = int(sub[1].strip())
            for p in range(max(1, start), min(total_pages, end) + 1):
                pages.add(p - 1)
        else:
            p = int(part.strip())
            if 1 <= p <= total_pages:
                pages.add(p - 1)
                
    return sorted(list(pages))

def split_pdf(input_path: str, output_path: str, page_ranges: str, job_id: Optional[str] = None) -> str:
    """Extract specified page range into a new PDF."""
    reader = PdfReader(input_path)
    total_pages = len(reader.pages)
    
    target_pages = parse_page_range(page_ranges, total_pages)
    if not target_pages:
        raise ValueError(f"No valid pages selected from range: '{page_ranges}'. Total pages: {total_pages}.")
        
    writer = PdfWriter()
    for idx, p_num in enumerate(target_pages):
        if job_id:
            pct = int(10 + (idx / len(target_pages)) * 80)
            job_service.set_progress(job_id, pct, f"Extracting page {p_num + 1}...")
        writer.add_page(reader.pages[p_num])
        
    with open(output_path, "wb") as f_out:
        writer.write(f_out)
        
    return output_path

def rotate_pdf(input_path: str, output_path: str, rotation: int = 90, pages: Optional[List[int]] = None, job_id: Optional[str] = None) -> str:
    """Rotate specified pages (or all pages) clockwise by degree angle (90, 180, 270)."""
    doc = fitz.open(input_path)
    try:
        total = len(doc)
        target_indices = pages if pages is not None else list(range(total))
        for idx in target_indices:
            if 0 <= idx < total:
                page = doc[idx]
                page.set_rotation((page.rotation + rotation) % 360)
        doc.save(output_path)
    finally:
        doc.close()
    return output_path

def reorder_pdf(input_path: str, output_path: str, new_order: List[int], job_id: Optional[str] = None) -> str:
    """Reorder and duplicate/remove pages based on 0-indexed list of page indices."""
    doc = fitz.open(input_path)
    try:
        new_doc = fitz.open()
        for idx in new_order:
            if 0 <= idx < len(doc):
                new_doc.insert_pdf(doc, from_page=idx, to_page=idx)
        new_doc.save(output_path)
        new_doc.close()
    finally:
        doc.close()
    return output_path

def compress_pdf(input_path: str, output_path: str, compression_level: str = "medium", job_id: Optional[str] = None) -> str:
    """
    Compress PDF using stream deflation, object deduplication, and image optimization.
    compression_level: 'low' (preserve quality), 'medium' (balanced), 'high' (maximum size reduction)
    """
    dpi_target = 150 if compression_level == "low" else (100 if compression_level == "medium" else 72)
    quality = 80 if compression_level == "low" else (65 if compression_level == "medium" else 50)
    
    doc = fitz.open(input_path)
    try:
        total = len(doc)
        for p_idx, page in enumerate(doc):
            if job_id:
                pct = int(10 + (p_idx / max(1, total)) * 70)
                job_service.set_progress(job_id, pct, f"Compressing page {p_idx + 1} of {total}...")
                
            # Iterate images in the page to downsample high-res photos
            for img in page.get_images(full=True):
                xref = img[0]
                try:
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]
                    
                    pil_img = Image.open(io.BytesIO(image_bytes))
                    if pil_img.width > 1200 or pil_img.height > 1200 or compression_level == "high":
                        # Resize proportionally
                        ratio = min(1200 / max(1, pil_img.width), 1200 / max(1, pil_img.height))
                        if ratio < 1.0 or compression_level == "high":
                            new_size = (max(1, int(pil_img.width * ratio)), max(1, int(pil_img.height * ratio)))
                            pil_img = pil_img.resize(new_size, Image.Resampling.LANCZOS)
                            
                        out_io = io.BytesIO()
                        if pil_img.mode in ("RGBA", "P"):
                            pil_img = pil_img.convert("RGB")
                        pil_img.save(out_io, format="JPEG", quality=quality, optimize=True)
                        doc.update_stream(xref, out_io.getvalue())
                except Exception:
                    continue
                    
        # Save with maximal garbage collection and stream deflation
        doc.save(
            output_path,
            garbage=4,
            deflate=True,
            deflate_images=True,
            deflate_fonts=True,
            clean=True
        )
    finally:
        doc.close()
        
    return output_path

def add_watermark(input_path: str, output_path: str, watermark_text: str, opacity: float = 0.25, font_size: int = 48, angle: int = 45, color_hex: str = "#94A3B8") -> str:
    """Overlay customizable diagonal watermark text across all pages."""
    doc = fitz.open(input_path)
    try:
        # Convert hex color to RGB tuple (0.0 to 1.0)
        h = color_hex.lstrip("#")
        if len(h) == 6:
            r, g, b = tuple(int(h[i:i+2], 16) / 255.0 for i in (0, 2, 4))
        else:
            r, g, b = (0.5, 0.5, 0.5)
            
        for page in doc:
            rect = page.rect
            center_x = rect.width / 2.0
            center_y = rect.height / 2.0
            
            # Insert rotated watermark text
            page.insert_text(
                fitz.Point(center_x - (len(watermark_text) * font_size * 0.25), center_y),
                watermark_text,
                fontsize=font_size,
                fontname="helv",
                color=(r, g, b),
                fill_opacity=opacity,
                rotate=angle
            )
            
        doc.save(output_path)
    finally:
        doc.close()
        
    return output_path

def add_page_numbers(input_path: str, output_path: str, format_str: str = "Page {page} of {total}", position: str = "bottom-center", start_page: int = 1) -> str:
    """
    Append formatted page numbering to all pages.
    Positions: 'bottom-center', 'bottom-right', 'bottom-left', 'top-right'
    """
    doc = fitz.open(input_path)
    try:
        total = len(doc)
        for idx, page in enumerate(doc):
            curr_num = start_page + idx
            label = format_str.replace("{page}", str(curr_num)).replace("{total}", str(total + start_page - 1))
            rect = page.rect
            
            fontsize = 10
            y_pad = 28
            x_pad = 36
            
            if position == "bottom-right":
                pt = fitz.Point(rect.width - x_pad - (len(label) * 6), rect.height - y_pad)
            elif position == "bottom-left":
                pt = fitz.Point(x_pad, rect.height - y_pad)
            elif position == "top-right":
                pt = fitz.Point(rect.width - x_pad - (len(label) * 6), y_pad)
            else: # bottom-center
                pt = fitz.Point((rect.width / 2.0) - (len(label) * 3), rect.height - y_pad)
                
            page.insert_text(pt, label, fontsize=fontsize, fontname="helv", color=(0.3, 0.35, 0.4))
            
        doc.save(output_path)
    finally:
        doc.close()
    return output_path

def protect_pdf(input_path: str, output_path: str, user_pw: str, owner_pw: Optional[str] = None) -> str:
    """Encrypt PDF with user/owner passwords and AES encryption."""
    reader = PdfReader(input_path)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    owner = owner_pw if owner_pw else user_pw
    writer.encrypt(user_password=user_pw, owner_password=owner, use_128bit=True)
    with open(output_path, "wb") as f_out:
        writer.write(f_out)
    return output_path

def unlock_pdf(input_path: str, output_path: str, password: str) -> str:
    """Decrypt password-protected PDF given authorized credentials."""
    reader = PdfReader(input_path)
    if not reader.is_encrypted:
        # Not encrypted, copy directly
        with open(input_path, "rb") as fin, open(output_path, "wb") as fout:
            fout.write(fin.read())
        return output_path
        
    decrypt_res = reader.decrypt(password)
    if decrypt_res == 0:
        raise ValueError("Incorrect password provided. Unable to decrypt document.")
        
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
        
    with open(output_path, "wb") as f_out:
        writer.write(f_out)
    return output_path

def sign_pdf(input_path: str, output_path: str, signature_data: str, page_number: int = -1, x: Optional[float] = None, y: Optional[float] = None, width: float = 160, height: float = 60) -> str:
    """
    Stamp a drawn/typed base64 signature image onto a PDF page.
    Default placement is bottom-right on the last page.
    """
    import base64
    doc = fitz.open(input_path)
    try:
        total = len(doc)
        if total == 0:
            raise ValueError("PDF document has no pages.")
        target_idx = (total - 1) if page_number == -1 or page_number >= total else max(0, page_number)
        page = doc[target_idx]
        rect = page.rect
        
        pos_x = (rect.width - width - 50) if x is None else float(x)
        pos_y = (rect.height - height - 60) if y is None else float(y)
        sig_rect = fitz.Rect(pos_x, pos_y, pos_x + width, pos_y + height)
        
        # Strip data URL header if present
        raw_b64 = signature_data
        if "," in raw_b64:
            raw_b64 = raw_b64.split(",", 1)[1]
            
        img_bytes = base64.b64decode(raw_b64)
        page.insert_image(sig_rect, stream=img_bytes)
        doc.save(output_path)
    finally:
        doc.close()
    return output_path

def remove_pages(input_path: str, output_path: str, pages_to_remove: str) -> str:
    """Remove specified page numbers or ranges (e.g. '1, 3, 5-7') from PDF."""
    reader = PdfReader(input_path)
    total_pages = len(reader.pages)
    to_delete = set(parse_page_range(pages_to_remove, total_pages))
    
    writer = PdfWriter()
    kept_count = 0
    for idx in range(total_pages):
        if idx not in to_delete:
            writer.add_page(reader.pages[idx])
            kept_count += 1
            
    if kept_count == 0:
        raise ValueError("Cannot remove all pages from document. At least one page must remain.")
        
    with open(output_path, "wb") as f_out:
        writer.write(f_out)
    return output_path

def repair_pdf(input_path: str, output_path: str, job_id: Optional[str] = None) -> str:
    """
    Repair damaged, malformed, or corrupted PDF files by rebuilding the xref table,
    sanitizing stream dictionaries, fixing broken lengths, and deduplicating objects.
    """
    doc = fitz.open(input_path, filetype="pdf")
    try:
        doc.save(
            output_path,
            garbage=4,
            clean=True,
            deflate=True,
            deflate_images=True,
            deflate_fonts=True
        )
    finally:
        doc.close()
    return output_path

def crop_pdf(input_path: str, output_path: str, margins: Dict[str, float], pages: Optional[List[int]] = None) -> str:
    """
    Crop PDF pages by applying margin insets (top, bottom, left, right in points).
    """
    top = float(margins.get("top", 0))
    bottom = float(margins.get("bottom", 0))
    left = float(margins.get("left", 0))
    right = float(margins.get("right", 0))
    
    doc = fitz.open(input_path)
    try:
        total = len(doc)
        target_indices = pages if pages is not None else list(range(total))
        for idx in target_indices:
            if 0 <= idx < total:
                page = doc[idx]
                r = page.rect
                new_rect = fitz.Rect(
                    r.x0 + left,
                    r.y0 + top,
                    max(r.x0 + left + 20, r.x1 - right),
                    max(r.y0 + top + 20, r.y1 - bottom)
                )
                page.set_cropbox(new_rect)
        doc.save(output_path)
    finally:
        doc.close()
    return output_path

def inspect_pdf_forms(input_path: str) -> Dict[str, Any]:
    """Inspect and list all interactive AcroForms form fields in document."""
    doc = fitz.open(input_path)
    fields = []
    try:
        for p_idx, page in enumerate(doc):
            for widget in page.widgets():
                fields.append({
                    "page": p_idx + 1,
                    "name": widget.field_name,
                    "type": widget.field_type_string,
                    "value": widget.field_value or "",
                    "rect": [round(c, 1) for c in widget.rect]
                })
        return {
            "has_forms": len(fields) > 0,
            "field_count": len(fields),
            "fields": fields
        }
    finally:
        doc.close()

def fill_pdf_forms(input_path: str, output_path: str, field_data: Dict[str, Any]) -> str:
    """Fill interactive PDF form fields with provided key-value dictionary."""
    doc = fitz.open(input_path)
    try:
        for page in doc:
            for widget in page.widgets():
                fname = widget.field_name
                if fname in field_data:
                    widget.field_value = str(field_data[fname])
                    widget.update()
        doc.save(output_path)
    finally:
        doc.close()
    return output_path

def redact_pdf_keywords(input_path: str, output_path: str, keywords: List[str], presets: Optional[List[str]] = None, fill_hex: str = "#000000") -> Dict[str, Any]:
    """
    Search and permanently redact sensitive keywords and regex patterns
    (e.g., SSN, Email, Phone numbers, Credit Cards).
    """
    import re
    PRESET_PATTERNS = {
        "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        "phone": r'\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b',
        "ssn": r'\b\d{3}-\d{2}-\d{4}\b',
        "credit_card": r'\b(?:\d{4}[-\s]?){3}\d{4}\b'
    }
    
    # Parse fill color
    h = fill_hex.lstrip("#")
    if len(h) == 6:
        fill_rgb = tuple(int(h[i:i+2], 16) / 255.0 for i in (0, 2, 4))
    else:
        fill_rgb = (0.0, 0.0, 0.0)
        
    doc = fitz.open(input_path)
    total_redactions = 0
    
    try:
        # Collect terms to redact
        search_terms = [k.strip() for k in keywords if k.strip()]
        
        # Add regex matches for active presets
        if presets:
            for preset_name in presets:
                pat = PRESET_PATTERNS.get(preset_name.lower())
                if pat:
                    for page in doc:
                        text = page.get_text()
                        for match in re.findall(pat, text):
                            if match not in search_terms:
                                search_terms.append(match)
                                
        for page in doc:
            for term in search_terms:
                rects = page.search_for(term)
                for r in rects:
                    page.add_redact_annot(r, fill=fill_rgb)
                    total_redactions += 1
            page.apply_redactions()
            
        doc.save(output_path)
        return {
            "success": True,
            "output_path": output_path,
            "total_redactions": total_redactions,
            "terms_redacted": search_terms
        }
    finally:
        doc.close()

def compare_pdfs(pdf1_path: str, pdf2_path: str) -> Dict[str, Any]:
    """Compare two PDF files for textual and structural differences."""
    import difflib
    doc1 = fitz.open(pdf1_path)
    doc2 = fitz.open(pdf2_path)
    try:
        pcount1 = len(doc1)
        pcount2 = len(doc2)
        
        diffs = []
        max_p = max(pcount1, pcount2)
        
        for i in range(max_p):
            t1 = doc1[i].get_text().splitlines(keepends=True) if i < pcount1 else []
            t2 = doc2[i].get_text().splitlines(keepends=True) if i < pcount2 else []
            
            p_diff = list(difflib.unified_diff(t1, t2, fromfile=f"Doc1 Page {i+1}", tofile=f"Doc2 Page {i+1}"))
            if p_diff:
                diffs.append({
                    "page": i + 1,
                    "changes": len([l for l in p_diff if l.startswith("+") or l.startswith("-")]),
                    "diff_lines": p_diff[:30]
                })
                
        return {
            "identical": len(diffs) == 0 and pcount1 == pcount2,
            "doc1_pages": pcount1,
            "doc2_pages": pcount2,
            "pages_with_differences": len(diffs),
            "differences": diffs
        }
    finally:
        doc1.close()
        doc2.close()

