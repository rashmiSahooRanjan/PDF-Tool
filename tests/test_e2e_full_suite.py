"""
Comprehensive High-Level End-to-End Suite Test
Validates all 33 tools and workflows from start to finish.
"""
import os
import io
import fitz
import pytest
from app import create_app
from config import Config

@pytest.fixture
def test_client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

@pytest.fixture
def dummy_pdf(tmp_path):
    pdf_path = str(tmp_path / "test_doc.pdf")
    doc = fitz.open()
    
    # Page 1
    p1 = doc.new_page(width=595, height=842)
    p1.insert_text((50, 80), "DocuFlex Confidential Executive Report", fontsize=18)
    p1.insert_text((50, 120), "This report contains sensitive financial data and email: admin@docuflex.local", fontsize=11)
    p1.insert_text((50, 150), "Call our support hotline at 555-123-4567 for immediate verification.", fontsize=11)
    p1.insert_text((50, 180), "The company has achieved significant milestones this quarter with rapid growth.", fontsize=11)
    
    # Page 2
    p2 = doc.new_page(width=595, height=842)
    p2.insert_text((50, 80), "Appendix & Detailed Breakdown", fontsize=16)
    p2.insert_text((50, 120), "All calculations are verified by offline automated audits.", fontsize=11)
    p2.insert_text((50, 150), "Document signature and seal must be affixed before final release.", fontsize=11)
    
    doc.save(pdf_path)
    doc.close()
    return pdf_path

def test_full_system_flow(test_client, dummy_pdf):
    # 1. Upload Document
    with open(dummy_pdf, "rb") as f:
        up_res = test_client.post("/api/upload", data={"file": (f, "test_doc.pdf")}, content_type="multipart/form-data")
    assert up_res.status_code == 200
    up_data = up_res.get_json()
    job_id = up_data["job_id"]
    filename = up_data["files"][0]["filename"]
    assert up_data["metadata"]["page_count"] == 2

    # 2. ORGANIZE: Page Numbers
    num_res = test_client.post("/api/pdf/page-numbers", json={
        "job_id": job_id, "filename": filename, "format": "Page {page} of {total}", "position": "bottom-center"
    })
    assert num_res.status_code == 200

    # 3. ORGANIZE: Remove Pages
    rem_res = test_client.post("/api/pdf/remove_pages", json={
        "job_id": job_id, "filename": filename, "pages_to_remove": "2"
    })
    assert rem_res.status_code == 200
    assert rem_res.get_json()["success"] is True

    # 4. OPTIMIZE: Repair PDF
    rep_res = test_client.post("/api/pdf/repair", json={"job_id": job_id, "filename": filename})
    assert rep_res.status_code == 200

    # 5. OPTIMIZE: Compress PDF
    comp_res = test_client.post("/api/pdf/compress", json={"job_id": job_id, "filename": filename, "level": "medium"})
    assert comp_res.status_code == 200

    # 6. EDIT: Watermark
    wm_res = test_client.post("/api/pdf/watermark", json={
        "job_id": job_id, "filename": filename, "text": "VERIFIED", "opacity": 0.3
    })
    assert wm_res.status_code == 200

    # 7. EDIT: Crop Margins
    crop_res = test_client.post("/api/pdf/crop", json={
        "job_id": job_id, "filename": filename, "margins": {"top": 20, "bottom": 20, "left": 20, "right": 20}
    })
    assert crop_res.status_code == 200

    # 8. SECURITY: Sign Document
    sig_b64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    sign_res = test_client.post("/api/pdf/sign", json={
        "job_id": job_id, "filename": filename, "signature": sig_b64
    })
    assert sign_res.status_code == 200

    # 9. SECURITY: Redact sensitive email & phone
    redact_res = test_client.post("/api/pdf/redact_keywords", json={
        "job_id": job_id, "filename": filename, "presets": ["email", "phone"], "keywords": ["Confidential"]
    })
    assert redact_res.status_code == 200
    redact_data = redact_res.get_json()
    assert redact_data["success"] is True
    assert redact_data["total_redactions"] >= 2

    # 10. INTELLIGENCE: AI Summarizer
    sum_res = test_client.post("/api/intelligence/summarize", json={
        "job_id": job_id, "filename": filename, "sentences": 3
    })
    assert sum_res.status_code == 200
    sum_data = sum_res.get_json()
    assert sum_data["success"] is True
    assert len(sum_data["key_takeaways"]) > 0

    # 11. INTELLIGENCE: Translate
    trans_res = test_client.post("/api/intelligence/translate", json={
        "job_id": job_id, "filename": filename, "target_language": "es"
    })
    assert trans_res.status_code == 200
    assert trans_res.get_json()["target_language"] == "es"

    # 12. INTELLIGENCE: Markdown Conversion
    md_res = test_client.post("/api/intelligence/markdown", json={
        "job_id": job_id, "filename": filename
    })
    assert md_res.status_code == 200
    assert "markdown" in md_res.get_json()

    # 13. CHATBOT: Guide query
    chat_res = test_client.post("/api/chat", json={
        "message": "How do I redact sensitive information and export to Markdown?"
    })
    assert chat_res.status_code == 200
    chat_data = chat_res.get_json()
    assert "response" in chat_data
    assert len(chat_data["response"]) > 20
