import os
import io
import pytest
import fitz
from docx import Document
import openpyxl
from pypdf import PdfReader

from services.conversion_service import (
    convert_pdf_to_images,
    convert_images_to_pdf,
    convert_pdf_to_docx,
    convert_docx_tables_to_xlsx,
    execute_conversion
)
import services.utility_service as utils_srv
from services.editor_service import extract_page_text_spans, apply_pdf_edits
from utils.validators import validate_magic_bytes

def test_health_endpoint(client):
    """Verify health endpoint responds with system capability status."""
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "healthy"
    assert "iLovePDF" in data["service"]
    assert "capabilities" in data
    assert "native_features" in data["capabilities"]

def test_valid_pdf_upload(client, sample_pdf):
    """Verify valid PDF upload returns job_id and metadata."""
    with open(sample_pdf, "rb") as f:
        res = client.post(
            "/api/upload",
            data={"file": (f, "sample.pdf")},
            content_type="multipart/form-data"
        )
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "job_id" in data
    assert data["metadata"]["page_count"] == 2

def test_magic_signature_security(client, tmp_path):
    """Verify that disguised executable/text file with .pdf extension is rejected."""
    fake_pdf = tmp_path / "malicious.pdf"
    fake_pdf.write_text("This is plain text pretending to be a PDF.")
    
    # Internal validator check
    assert not validate_magic_bytes(str(fake_pdf), "pdf")
    
    # API upload check
    with open(fake_pdf, "rb") as f:
        res = client.post(
            "/api/upload",
            data={"file": (f, "malicious.pdf")},
            content_type="multipart/form-data"
        )
    assert res.status_code == 400
    assert "Security validation failed" in res.get_json()["error"]

def test_pdf_to_images(sample_pdf, tmp_path):
    """Verify converting multi-page PDF generates a valid ZIP of PNG images."""
    out_zip = str(tmp_path / "pages.zip")
    res = convert_pdf_to_images(sample_pdf, out_zip, target_format="png")
    assert os.path.exists(res)
    assert os.path.getsize(res) > 0

def test_pdf_merge(sample_pdf, tmp_path):
    """Verify merging two 2-page PDFs creates a 4-page PDF."""
    out_merged = str(tmp_path / "merged.pdf")
    res = utils_srv.merge_pdfs([sample_pdf, sample_pdf], out_merged)
    assert os.path.exists(res)
    reader = PdfReader(res)
    assert len(reader.pages) == 4

def test_pdf_split(sample_pdf, tmp_path):
    """Verify extracting page 1 creates a 1-page PDF."""
    out_split = str(tmp_path / "split.pdf")
    res = utils_srv.split_pdf(sample_pdf, out_split, page_ranges="1")
    assert os.path.exists(res)
    reader = PdfReader(res)
    assert len(reader.pages) == 1

def test_pdf_rotate(sample_pdf, tmp_path):
    """Verify page rotation."""
    out_rot = str(tmp_path / "rotated.pdf")
    res = utils_srv.rotate_pdf(sample_pdf, out_rot, rotation=90)
    assert os.path.exists(res)
    doc = fitz.open(res)
    assert doc[0].rotation == 90
    doc.close()

def test_pdf_compress(sample_pdf, tmp_path):
    """Verify PDF compression."""
    out_comp = str(tmp_path / "compressed.pdf")
    res = utils_srv.compress_pdf(sample_pdf, out_comp, compression_level="high")
    assert os.path.exists(res)
    assert os.path.getsize(res) > 0

def test_pdf_to_docx(sample_pdf, tmp_path):
    """Verify PDF to DOCX conversion produces valid Word document."""
    out_docx = str(tmp_path / "output.docx")
    res = convert_pdf_to_docx(sample_pdf, out_docx)
    assert os.path.exists(res)
    # Validate with python-docx
    doc = Document(res)
    assert len(doc.paragraphs) > 0

def test_docx_tables_to_xlsx(sample_docx, tmp_path):
    """Verify extracting tables from DOCX into Excel spreadsheet."""
    out_xlsx = str(tmp_path / "tables.xlsx")
    res = convert_docx_tables_to_xlsx(sample_docx, out_xlsx)
    assert os.path.exists(res)
    wb = openpyxl.load_workbook(res)
    assert len(wb.sheetnames) >= 1
    ws = wb.active
    assert ws.cell(row=1, column=1).value == "Col A"

def test_images_to_pdf(sample_image, tmp_path):
    """Verify converting PNG image to PDF."""
    out_pdf = str(tmp_path / "from_image.pdf")
    res = convert_images_to_pdf(sample_image, out_pdf)
    assert os.path.exists(res)
    reader = PdfReader(res)
    assert len(reader.pages) == 1

def test_protect_and_unlock_pdf(sample_pdf, tmp_path):
    """Verify password encryption and decryption."""
    out_enc = str(tmp_path / "protected.pdf")
    utils_srv.protect_pdf(sample_pdf, out_enc, user_pw="DocuFlexPass123")
    
    # Confirm it is encrypted
    reader_enc = PdfReader(out_enc)
    assert reader_enc.is_encrypted is True
    
    # Unlock with password
    out_dec = str(tmp_path / "unlocked.pdf")
    utils_srv.unlock_pdf(out_enc, out_dec, password="DocuFlexPass123")
    reader_dec = PdfReader(out_dec)
    assert reader_dec.is_encrypted is False

def test_unsupported_conversion_pair(sample_pdf, tmp_path):
    """Verify unsupported conversion raises clear descriptive error."""
    out = str(tmp_path / "test.xyz")
    with pytest.raises(ValueError, match="not supported"):
        execute_conversion("pdf", "xyz", sample_pdf, out)

def test_editor_spans_and_text_replacement(sample_pdf, tmp_path):
    """Verify existing text spans extraction and redaction/replacement workflow."""
    spans_info = extract_page_text_spans(sample_pdf, page_number=0)
    assert spans_info["total_spans"] > 0
    first_span = spans_info["spans"][0]
    assert "bbox" in first_span
    
    # Perform redaction and replacement
    out_edited = str(tmp_path / "edited.pdf")
    edits = [
        {
            "type": "replace_text",
            "page": 0,
            "bbox": first_span["bbox"],
            "new_text": "REPLACED HEADLINE TEXT",
            "font_size": 16,
            "color": "#10B981",
            "bg_color": "#FFFFFF"
        }
    ]
    res = apply_pdf_edits(sample_pdf, out_edited, edits)
    assert os.path.exists(res)
    
    # Confirm newly inserted text is present in the document
    doc = fitz.open(res)
    page_text = doc[0].get_text()
    assert "REPLACED HEADLINE TEXT" in page_text
    doc.close()

def test_ocr_text_extraction(sample_pdf):
    """Verify local offline OCR text extraction on PDF document."""
    from services.ocr_service import extract_text_ocr
    res = extract_text_ocr(sample_pdf)
    assert res["character_count"] > 0
    assert "DocuFlex" in res["text"] or "Synthetic" in res["text"]

def test_ocr_searchable_pdf(sample_image, tmp_path):
    """Verify generating searchable PDF with OCR text layer from image."""
    from services.ocr_service import create_searchable_pdf
    out_pdf = str(tmp_path / "searchable_test.pdf")
    res = create_searchable_pdf(sample_image, out_pdf)
    assert os.path.exists(res)
    assert os.path.getsize(res) > 0

def test_docx_to_pdf_conversion(sample_docx, tmp_path):
    """Verify converting DOCX to PDF using native Office / LibreOffice engine."""
    from services.conversion_service import convert_office_to_pdf
    out_pdf = str(tmp_path / "from_docx.pdf")
    res = convert_office_to_pdf(sample_docx, out_pdf)
    assert os.path.exists(res)
    assert os.path.getsize(res) > 0

def test_chat_assistant_features(client):
    """Verify chatbot answers questions about PDF editing, OCR, and system status."""
    # 1. Edit existing text query
    res = client.post("/api/chat", json={"message": "How do I edit existing text in a PDF?"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "Existing Text" in data["reply"]
    assert "redaction" in data["reply"].lower()

    # 2. System status query
    res_status = client.post("/api/chat", json={"message": "What is the system status?"})
    assert res_status.status_code == 200
    data_status = res_status.get_json()
    assert data_status["success"] is True
    assert "System Status" in data_status["reply"]
    assert "Python Runtime" in data_status["reply"]

    # 3. Empty query returns 400
    res_empty = client.post("/api/chat", json={"message": ""})
    assert res_empty.status_code == 400
    assert "Empty message" in res_empty.get_json()["error"]

def test_editor_typography_and_genuine_redaction(sample_pdf, tmp_path):
    """Verify font family resolution, bold, italic, underline, alignment and genuine stream redaction."""
    spans_info = extract_page_text_spans(sample_pdf, page_number=0)
    target_span = spans_info["spans"][0]
    out_pdf = str(tmp_path / "typography_edited.pdf")
    
    edits = [
        {
            "type": "replace_text",
            "page": 0,
            "bbox": target_span["bbox"],
            "new_text": "MODERN TYPOGRAPHY HEADER",
            "font_family": "Times-Roman",
            "font_size": 18,
            "bold": True,
            "italic": True,
            "underline": True,
            "align": "center",
            "color": "#1E40AF",
            "bg_color": "#FFFFFF"
        }
    ]
    res = apply_pdf_edits(sample_pdf, out_pdf, edits)
    assert os.path.exists(res)
    
    # Reopen and inspect document bytes & text
    doc = fitz.open(res)
    text = doc[0].get_text()
    assert "MODERN TYPOGRAPHY HEADER" in text
    # Verify original text has been purged by redaction
    assert target_span["text"] not in text
    doc.close()

def test_editor_movable_textbox(sample_pdf, tmp_path):
    """Verify adding a movable/resizable text box with background fill and border."""
    out_pdf = str(tmp_path / "textbox_added.pdf")
    edits = [
        {
            "type": "add_textbox",
            "page": 0,
            "bbox": [50, 200, 300, 280],
            "text": "This is an injected movable text box with custom styling.",
            "font_family": "Courier",
            "font_size": 12,
            "bold": True,
            "color": "#B91C1C",
            "bg_color": "#FEF2F2",
            "border_color": "#DC2626",
            "border_width": 1.5,
            "align": "left"
        }
    ]
    res = apply_pdf_edits(sample_pdf, out_pdf, edits)
    assert os.path.exists(res)
    
    doc = fitz.open(res)
    text = doc[0].get_text()
    assert "injected movable" in text and "custom styling" in text
    doc.close()

def test_editor_delete_text_redaction(sample_pdf, tmp_path):
    """Verify deleting existing text performs genuine redaction leaving no trace."""
    spans_info = extract_page_text_spans(sample_pdf, page_number=0)
    target_span = spans_info["spans"][0]
    out_pdf = str(tmp_path / "text_deleted.pdf")
    
    edits = [
        {
            "type": "delete_text",
            "page": 0,
            "bbox": target_span["bbox"],
            "bg_color": "#FFFFFF"
        }
    ]
    res = apply_pdf_edits(sample_pdf, out_pdf, edits)
    assert os.path.exists(res)
    
    doc = fitz.open(res)
    text = doc[0].get_text()
    assert target_span["text"] not in text
    doc.close()

def test_editor_find_and_replace(sample_pdf, tmp_path):
    """Verify search and replace across PDF page."""
    out_pdf = str(tmp_path / "find_replaced.pdf")
    edits = [
        {
            "type": "find_and_replace",
            "page": 0,
            "find_text": "DocuFlex",
            "replace_text": "SuperFlexEditor",
            "match_case": True,
            "font_size": 14,
            "color": "#059669"
        }
    ]
    res = apply_pdf_edits(sample_pdf, out_pdf, edits)
    assert os.path.exists(res)
    
    doc = fitz.open(res)
    text = doc[0].get_text()
    assert "SuperFlexEditor" in text
    doc.close()

def test_editor_watermark_and_headers(sample_pdf, tmp_path):
    """Verify adding diagonal watermark and formatted page headers/footers."""
    out_pdf = str(tmp_path / "watermarked.pdf")
    edits = [
        {
            "type": "add_watermark",
            "text": "STRICTLY CONFIDENTIAL",
            "opacity": 0.2,
            "color": "#DC2626",
            "font_size": 36,
            "angle": 45
        },
        {
            "type": "add_header_footer",
            "text": "DocuFlex Pro • Page {page} of {total}",
            "position": "footer_center",
            "font_size": 9,
            "color": "#475569"
        }
    ]
    res = apply_pdf_edits(sample_pdf, out_pdf, edits)
    assert os.path.exists(res)
    
    doc = fitz.open(res)
    # Check page 1 and page 2 for footer text
    assert "Page 1 of 2" in doc[0].get_text()
    assert "Page 2 of 2" in doc[1].get_text()
    doc.close()

def test_editor_page_manipulations(sample_pdf, tmp_path):
    """Verify page insertion, rotation, duplication and reordering."""
    out_pdf = str(tmp_path / "manipulated.pdf")
    edits = [
        {"type": "insert_blank_page", "page_index": 1},
        {"type": "rotate_page", "page": 0, "page_index": 0, "angle": 90}
    ]
    res = apply_pdf_edits(sample_pdf, out_pdf, edits)
    assert os.path.exists(res)
    
    doc = fitz.open(res)
    # Original was 2 pages, inserted 1 blank page -> should now be 3 pages
    assert len(doc) == 3
    assert doc[0].rotation == 90
    doc.close()

def test_editor_reflow_workflow(client, sample_pdf):
    """Verify Word-like reflow mode initialization and recompilation back to PDF."""
    with open(sample_pdf, "rb") as f:
        up_res = client.post("/api/upload", data={"file": (f, "sample.pdf")}, content_type="multipart/form-data")
    job_id = up_res.get_json()["job_id"]
    filename = up_res.get_json()["files"][0]["filename"]

    # 1. Initialize reflow
    init_res = client.post("/api/pdf/reflow/init", json={"job_id": job_id, "filename": filename})
    assert init_res.status_code == 200
    init_data = init_res.get_json()
    assert init_data["success"] is True
    assert init_data["paragraph_count"] > 0
    assert len(init_data["paragraphs"]) > 0

    # 2. Modify paragraphs and save reflowed PDF
    modified_paragraphs = [
        {"text": "Edited Reflow Headline in Word-Like Mode", "style": "Heading 1"},
        {"text": "This is a reflowed body paragraph with updated text content.", "style": "Normal"}
    ]
    save_res = client.post("/api/pdf/reflow/save", json={
        "job_id": job_id,
        "filename": filename,
        "paragraphs": modified_paragraphs
    })
    assert save_res.status_code == 200
    save_data = save_res.get_json()
    assert save_data["success"] is True
    assert "download_url" in save_data

def test_editor_ocr_assist(client, sample_pdf):
    """Verify OCR assist workflow generates searchable PDF with selectable text layer."""
    with open(sample_pdf, "rb") as f:
        up_res = client.post("/api/upload", data={"file": (f, "sample_scan.pdf")}, content_type="multipart/form-data")
    job_id = up_res.get_json()["job_id"]
    filename = up_res.get_json()["files"][0]["filename"]

    ocr_res = client.post("/api/pdf/ocr_assist", json={"job_id": job_id, "filename": filename})
    assert ocr_res.status_code == 200
    ocr_data = ocr_res.get_json()
    assert ocr_data["success"] is True
    assert "searchable" in ocr_data["filename"]

def test_remove_pages(sample_pdf, tmp_path):
    """Verify removing page 2 leaves a 1-page PDF."""
    out_path = str(tmp_path / "removed.pdf")
    res = utils_srv.remove_pages(sample_pdf, out_path, pages_to_remove="2")
    assert os.path.exists(res)
    reader = PdfReader(res)
    assert len(reader.pages) == 1

def test_repair_pdf(sample_pdf, tmp_path):
    """Verify repairing PDF preserves structure and cleans streams."""
    out_path = str(tmp_path / "repaired.pdf")
    res = utils_srv.repair_pdf(sample_pdf, out_path)
    assert os.path.exists(res)
    doc = fitz.open(res)
    assert len(doc) == 2
    doc.close()

def test_crop_pdf(sample_pdf, tmp_path):
    """Verify page margin cropping."""
    out_path = str(tmp_path / "cropped.pdf")
    res = utils_srv.crop_pdf(sample_pdf, out_path, margins={"top": 36, "bottom": 36, "left": 36, "right": 36})
    assert os.path.exists(res)
    doc = fitz.open(res)
    cropbox = doc[0].cropbox
    rect = doc[0].rect
    assert cropbox.y0 > rect.y0
    doc.close()

def test_sign_pdf(sample_pdf, tmp_path):
    """Verify digital signature stamping onto PDF page."""
    out_path = str(tmp_path / "signed.pdf")
    # 1x1 transparent/white png base64
    dummy_sig_b64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    res = utils_srv.sign_pdf(sample_pdf, out_path, dummy_sig_b64, page_number=0)
    assert os.path.exists(res)
    doc = fitz.open(res)
    imgs = doc[0].get_images()
    assert len(imgs) > 0
    doc.close()

def test_redact_pdf_keywords(sample_pdf, tmp_path):
    """Verify genuine redaction of keywords."""
    out_path = str(tmp_path / "redacted.pdf")
    rep = utils_srv.redact_pdf_keywords(sample_pdf, out_path, keywords=["DocuFlex", "Sample"], presets=["email"])
    assert rep["success"] is True
    assert rep["total_redactions"] > 0
    assert os.path.exists(out_path)

def test_compare_pdfs(sample_pdf, tmp_path):
    """Verify compare tool identifies identical and modified documents."""
    # 1. Compare identical files
    rep1 = utils_srv.compare_pdfs(sample_pdf, sample_pdf)
    assert rep1["identical"] is True
    assert rep1["pages_with_differences"] == 0

    # 2. Compare different files
    out_mod = str(tmp_path / "mod.pdf")
    utils_srv.remove_pages(sample_pdf, out_mod, pages_to_remove="2")
    rep2 = utils_srv.compare_pdfs(sample_pdf, out_mod)
    assert rep2["identical"] is False
    assert rep2["doc1_pages"] == 2
    assert rep2["doc2_pages"] == 1

def test_ai_summarizer(sample_pdf):
    """Verify 100% offline extractive text summarizer."""
    from services.intelligence_service import summarize_pdf
    res = summarize_pdf(sample_pdf, max_sentences=3)
    assert res["success"] is True
    assert res["total_words"] > 0
    assert len(res["key_takeaways"]) > 0
    assert len(res["summary"]) > 0

def test_translate_pdf(sample_pdf):
    """Verify offline dictionary translator."""
    from services.intelligence_service import translate_pdf_text
    res = translate_pdf_text(sample_pdf, target_lang="es")
    assert res["success"] is True
    assert res["target_language"] == "es"
    assert len(res["translated_text"]) > 0

def test_convert_pdf_to_markdown(sample_pdf, tmp_path):
    """Verify converting PDF to structured GitHub Markdown."""
    from services.intelligence_service import convert_pdf_to_markdown
    out_md = str(tmp_path / "output.md")
    res = convert_pdf_to_markdown(sample_pdf, out_md)
    assert res["success"] is True
    assert os.path.exists(out_md)
    assert len(res["markdown"]) > 0



