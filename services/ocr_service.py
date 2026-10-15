import os
import io
from typing import Optional, Dict, Any, List

import fitz  # PyMuPDF
from PIL import Image
import numpy as np

from config import Config
from utils.system_checker import find_tesseract, get_tesseract_languages
from services.job_service import job_service

# Lazy-loaded RapidOCR engine instance
_rapid_ocr_instance = None

def get_rapid_ocr():
    global _rapid_ocr_instance
    if _rapid_ocr_instance is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
            _rapid_ocr_instance = RapidOCR()
        except Exception:
            _rapid_ocr_instance = None
    return _rapid_ocr_instance

def setup_tesseract():
    """Configure pytesseract binary path if available."""
    tess_bin = find_tesseract()
    if tess_bin:
        try:
            import pytesseract
            pytesseract.pytesseract.tesseract_cmd = tess_bin
        except Exception:
            pass
    return tess_bin

def _run_rapid_ocr_image(pil_img: Image.Image) -> tuple[str, list]:
    """Run RapidOCR on PIL Image, returns (text_string, list_of_boxes_and_text)."""
    ocr_engine = get_rapid_ocr()
    if not ocr_engine:
        return "", []
    np_img = np.array(pil_img.convert("RGB"))
    result, _ = ocr_engine(np_img)
    if not result:
        return "", []
        
    lines = [item[1] for item in result if len(item) >= 2 and item[1].strip()]
    return "\n".join(lines), result

def extract_text_ocr(input_path: str, lang: str = "eng", job_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Extract text from scanned document (PDF or Image).
    Uses Tesseract OCR if available, otherwise seamlessly falls back to 
    the built-in neural RapidOCR engine and native PDF engine.
    """
    tess_bin = setup_tesseract()
    ext = input_path.rsplit(".", 1)[-1].lower()
    full_text = []
    engine_used = "Tesseract OCR" if tess_bin else "DocuFlex Neural OCR"
    
    if ext in ("jpg", "jpeg", "png"):
        if job_id:
            job_service.set_progress(job_id, 30, f"Scanning image with {engine_used}...")
        img = Image.open(input_path)
        
        if tess_bin:
            try:
                import pytesseract
                text = pytesseract.image_to_string(img, lang=lang)
            except Exception:
                # Fallback to RapidOCR
                text, _ = _run_rapid_ocr_image(img)
        else:
            text, _ = _run_rapid_ocr_image(img)
            
        full_text.append(f"--- Extracted Text ({engine_used}) ---\n{text}")
        
    elif ext == "pdf":
        doc = fitz.open(input_path)
        total_pages = len(doc)
        try:
            for idx, page in enumerate(doc):
                if job_id:
                    pct = int(10 + (idx / max(1, total_pages)) * 80)
                    job_service.set_progress(job_id, pct, f"OCR scanning page {idx + 1} of {total_pages}...")
                    
                page_text = ""
                # First check if the page has digital vector text
                native_text = page.get_text()
                if native_text.strip():
                    page_text = native_text.strip()
                else:
                    # Render high-resolution image for optical recognition
                    pix = page.get_pixmap(dpi=200)
                    pil_img = Image.open(io.BytesIO(pix.tobytes("png")))
                    
                    if tess_bin:
                        try:
                            import pytesseract
                            page_text = pytesseract.image_to_string(pil_img, lang=lang)
                        except Exception:
                            page_text, _ = _run_rapid_ocr_image(pil_img)
                    else:
                        page_text, _ = _run_rapid_ocr_image(pil_img)
                        
                full_text.append(f"--- Page {idx + 1} ---\n{page_text}")
        finally:
            doc.close()
    else:
        raise ValueError(f"OCR is not supported for file extension: {ext}")
        
    combined_result = "\n\n".join(full_text)
    return {
        "text": combined_result,
        "language": lang,
        "engine": engine_used,
        "character_count": len(combined_result)
    }

def create_searchable_pdf(input_path: str, output_path: str, lang: str = "eng", job_id: Optional[str] = None) -> str:
    """
    Generate a searchable PDF with invisible text layer from image or scanned PDF.
    Supports Tesseract if installed, and falls back to RapidOCR + PyMuPDF text layer injection.
    """
    tess_bin = setup_tesseract()
    ext = input_path.rsplit(".", 1)[-1].lower()
    
    if tess_bin:
        try:
            import pytesseract
            if ext in ("jpg", "jpeg", "png"):
                if job_id:
                    job_service.set_progress(job_id, 40, "Generating searchable PDF from image...")
                img = Image.open(input_path)
                pdf_bytes = pytesseract.image_to_pdf_or_hocr(img, extension="pdf", lang=lang)
                with open(output_path, "wb") as f_out:
                    f_out.write(pdf_bytes)
                return output_path
                
            elif ext == "pdf":
                doc = fitz.open(input_path)
                searchable_writer = fitz.open()
                total_pages = len(doc)
                try:
                    for idx, page in enumerate(doc):
                        if job_id:
                            pct = int(10 + (idx / max(1, total_pages)) * 80)
                            job_service.set_progress(job_id, pct, f"OCR processing page {idx + 1} of {total_pages}...")
                        pix = page.get_pixmap(dpi=200)
                        img = Image.open(io.BytesIO(pix.tobytes("png")))
                        single_pdf_bytes = pytesseract.image_to_pdf_or_hocr(img, extension="pdf", lang=lang)
                        page_doc = fitz.open("pdf", single_pdf_bytes)
                        searchable_writer.insert_pdf(page_doc)
                        page_doc.close()
                        
                    searchable_writer.save(output_path)
                    searchable_writer.close()
                    return output_path
                finally:
                    doc.close()
        except Exception:
            pass  # Fall through to RapidOCR layer injection
            
    # Built-in Fallback: Inject invisible text layer with RapidOCR + PyMuPDF
    if ext in ("jpg", "jpeg", "png"):
        img = Image.open(input_path)
        w, h = img.size
        text, boxes = _run_rapid_ocr_image(img)
        
        doc = fitz.open()
        page = doc.new_page(width=w * 0.75, height=h * 0.75)
        # Insert background image
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        page.insert_image(page.rect, stream=img_byte_arr.getvalue())
        
        # Inject invisible text over recognized regions
        scale_x = (w * 0.75) / max(1, w)
        scale_y = (h * 0.75) / max(1, h)
        
        for item in boxes:
            box, b_text, _ = item
            # box: [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
            pt_x = box[0][0] * scale_x
            pt_y = box[2][1] * scale_y
            h_box = abs(box[2][1] - box[0][1]) * scale_y
            page.insert_text(fitz.Point(pt_x, pt_y), b_text, fontsize=max(8, h_box * 0.8), render_mode=3)
            
        doc.save(output_path)
        doc.close()
        return output_path
        
    elif ext == "pdf":
        doc = fitz.open(input_path)
        total_pages = len(doc)
        try:
            for idx, page in enumerate(doc):
                if job_id:
                    pct = int(10 + (idx / max(1, total_pages)) * 80)
                    job_service.set_progress(job_id, pct, f"Generating text layer for page {idx + 1}...")
                    
                # If page already has text, keep as-is
                if not page.get_text().strip():
                    pix = page.get_pixmap(dpi=180)
                    pil_img = Image.open(io.BytesIO(pix.tobytes("png")))
                    _, boxes = _run_rapid_ocr_image(pil_img)
                    
                    scale_x = page.rect.width / max(1, pil_img.width)
                    scale_y = page.rect.height / max(1, pil_img.height)
                    
                    for item in boxes:
                        box, b_text, _ = item
                        pt_x = box[0][0] * scale_x
                        pt_y = box[2][1] * scale_y
                        h_box = abs(box[2][1] - box[0][1]) * scale_y
                        page.insert_text(fitz.Point(pt_x, pt_y), b_text, fontsize=max(8, h_box * 0.8), render_mode=3)
                        
            doc.save(output_path)
            return output_path
        finally:
            doc.close()
            
    raise ValueError(f"Cannot generate searchable PDF for '{ext}' files.")
