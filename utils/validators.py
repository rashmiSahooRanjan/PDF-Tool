import os
from pathlib import Path
from werkzeug.utils import secure_filename
from config import Config

# Magic signatures for binary inspection
MAGIC_SIGNATURES = {
    "pdf": [b"%PDF-"],
    "png": [b"\x89PNG\r\n\x1a\n"],
    "jpg": [b"\xff\xd8\xff"],
    "jpeg": [b"\xff\xd8\xff"],
    "zip_office": [b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"], # DOCX, XLSX, PPTX are zipped XML
}

def get_file_extension(filename: str) -> str:
    """Extract lowercase file extension without dot."""
    if "." in filename:
        return filename.rsplit(".", 1)[1].lower()
    return ""

def is_allowed_file(filename: str) -> bool:
    """Check if extension is in configured allowed list."""
    ext = get_file_extension(filename)
    return ext in Config.ALLOWED_EXTENSIONS

def validate_magic_bytes(filepath: str, expected_ext: str) -> bool:
    """
    Validate binary file header matches expected extension.
    Protects against disguised executable or script uploads.
    """
    if not os.path.exists(filepath):
        return False
    
    expected_ext = expected_ext.lower()
    
    try:
        with open(filepath, "rb") as f:
            header = f.read(32)
            
        if expected_ext == "pdf":
            return any(header.startswith(sig) for sig in MAGIC_SIGNATURES["pdf"])
        elif expected_ext in ("jpg", "jpeg"):
            return any(header.startswith(sig) for sig in MAGIC_SIGNATURES["jpg"])
        elif expected_ext == "png":
            return any(header.startswith(sig) for sig in MAGIC_SIGNATURES["png"])
        elif expected_ext in ("docx", "xlsx", "pptx"):
            return any(header.startswith(sig) for sig in MAGIC_SIGNATURES["zip_office"])
        elif expected_ext in ("html", "htm", "md", "txt"):
            # Ensure not an executable binary (MZ for exe or \x7fELF)
            return not (header.startswith(b"MZ") or header.startswith(b"\x7fELF"))
        else:
            return False
    except Exception:
        return False

def sanitize_safe_filename(original_name: str) -> str:
    """Clean filename to eliminate traversal risks and special characters."""
    base = os.path.basename(original_name)
    safe = secure_filename(base)
    if not safe:
        safe = "document"
    return safe

def is_safe_path(base_dir: str, path: str) -> bool:
    """Prevent directory traversal attack by verifying resolved path."""
    try:
        base = Path(base_dir).resolve()
        target = Path(path).resolve()
        return base in target.parents or base == target
    except Exception:
        return False
