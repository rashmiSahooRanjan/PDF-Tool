import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

class Config:
    SECRET_KEY = os.environ.get("DOCUFLEX_SECRET_KEY", "docuflex-dev-insecure-secret-key-2026")
    
    # Upload & Storage settings
    UPLOAD_FOLDER = os.environ.get("DOCUFLEX_UPLOAD_FOLDER", str(BASE_DIR / "uploads"))
    OUTPUT_FOLDER = os.environ.get("DOCUFLEX_OUTPUT_FOLDER", str(BASE_DIR / "outputs"))
    TEMP_FOLDER = os.environ.get("DOCUFLEX_TEMP_FOLDER", str(BASE_DIR / "temp"))
    
    # Max file size: 64 MB
    MAX_CONTENT_LENGTH = 64 * 1024 * 1024
    
    # Max pages for processing (safety limit against DoS / resource exhaustion)
    MAX_PAGE_LIMIT = 300
    
    # Temporary file retention (in seconds: 2 hours)
    TEMP_FILE_TTL_SECONDS = 7200
    
    # Supported extensions
    ALLOWED_EXTENSIONS = {
        "pdf", "docx", "xlsx", "pptx", "jpg", "jpeg", "png", "html", "htm", "md", "txt"
    }
    
    # Allowed MIME types
    ALLOWED_MIMETYPES = {
        "application/pdf": "pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
        "image/jpeg": "jpg",
        "image/png": "png",
        "text/html": "html",
        "text/markdown": "md",
        "text/plain": "txt"
    }
    
    # External tool custom paths (can be set via env vars)
    LIBREOFFICE_PATH = os.environ.get("LIBREOFFICE_PATH", "")
    TESSERACT_PATH = os.environ.get("TESSERACT_PATH", "")
    
    # Flask options
    DEBUG = os.environ.get("FLASK_DEBUG", "True").lower() in ("true", "1", "yes")
    JSON_SORT_KEYS = False

class TestingConfig(Config):
    TESTING = True
    UPLOAD_FOLDER = str(BASE_DIR / "tests" / "test_uploads")
    OUTPUT_FOLDER = str(BASE_DIR / "tests" / "test_outputs")
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024
