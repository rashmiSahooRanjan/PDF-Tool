import pytest
import re
from app import create_app

@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def test_landing_page_mega_menu_and_categories(client):
    res = client.get("/")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    
    # Verify 7 categories
    categories = [
        "ORGANIZE PDF",
        "OPTIMIZE PDF",
        "CONVERT TO PDF",
        "CONVERT FROM PDF",
        "EDIT PDF",
        "PDF SECURITY",
        "PDF INTELLIGENCE"
    ]
    for cat in categories:
        assert cat in html, f"Category '{cat}' missing from landing page"

    # Verify key 33 tools are represented
    tools = [
        "Merge PDF", "Split PDF", "Remove pages", "Extract pages", "Organize PDF", "Scan to PDF",
        "Compress PDF", "Repair PDF", "OCR PDF",
        "JPG to PDF", "WORD to PDF", "POWERPOINT to PDF", "EXCEL to PDF", "HTML to PDF",
        "PDF to JPG", "PDF to WORD", "PDF to POWERPOINT", "PDF to EXCEL", "PDF to PDF/A",
        "Rotate PDF", "Add page numbers", "Add watermark", "Crop PDF", "Edit PDF", "PDF forms",
        "Unlock PDF", "Protect PDF", "Sign PDF", "Redact PDF", "Compare PDF",
        "AI Summarizer", "Translate PDF", "PDF to Markdown"
    ]
    for tool in tools:
        assert tool.lower() in html.lower(), f"Tool '{tool}' not found in landing page HTML"

def test_editor_page_structure(client):
    res = client.get("/editor")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    
    # Check essential editor elements
    assert "editor-container" in html or "editor" in html.lower()
    assert "pdf-viewer" in html or "pdf-canvas" in html or "page" in html.lower()
    assert "zoom" in html.lower()
    assert "download" in html.lower()

def test_chat_api(client):
    res = client.post("/api/chat/message", json={"message": "How do I merge two PDF files?"})
    assert res.status_code == 200
    data = res.get_json()
    assert "reply" in data or "response" in data
    answer = data.get("reply") or data.get("response")
    assert len(answer) > 20
    assert "merge" in answer.lower() or "pdf" in answer.lower()

def test_static_assets_exist(client):
    assets = [
        "/static/css/style.css",
        "/static/css/editor.css",
        "/static/js/app.js",
        "/static/js/editor.js",
        "/static/js/chat.js",
        "/static/js/theme.js"
    ]
    for asset in assets:
        res = client.get(asset)
        assert res.status_code == 200, f"Static asset {asset} returned {res.status_code}"
