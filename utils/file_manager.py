import os
import time
import shutil
import uuid
from pathlib import Path
from config import Config
from utils.validators import sanitize_safe_filename, is_safe_path

def ensure_storage_dirs():
    """Ensure upload, output, and temp directories exist."""
    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(Config.OUTPUT_FOLDER, exist_ok=True)
    os.makedirs(Config.TEMP_FOLDER, exist_ok=True)

def generate_job_id() -> str:
    """Generate random non-guessable identifier."""
    return uuid.uuid4().hex

def get_job_upload_dir(job_id: str) -> str:
    """Get isolated directory path for uploaded files for a job."""
    ensure_storage_dirs()
    d = os.path.join(Config.UPLOAD_FOLDER, job_id)
    os.makedirs(d, exist_ok=True)
    return d

def get_job_output_dir(job_id: str) -> str:
    """Get isolated directory path for output files for a job."""
    ensure_storage_dirs()
    d = os.path.join(Config.OUTPUT_FOLDER, job_id)
    os.makedirs(d, exist_ok=True)
    return d

def save_uploaded_file(file_storage, job_id: str) -> tuple[str, str]:
    """
    Save incoming file to secure job folder.
    Returns: (saved_filepath, original_sanitized_filename)
    """
    safe_name = sanitize_safe_filename(file_storage.filename or "file")
    upload_dir = get_job_upload_dir(job_id)
    target_path = os.path.join(upload_dir, safe_name)
    
    if not is_safe_path(Config.UPLOAD_FOLDER, target_path):
        raise ValueError("Invalid target filepath detected")
        
    file_storage.save(target_path)
    return target_path, safe_name

def cleanup_expired_files():
    """Delete files older than Config.TEMP_FILE_TTL_SECONDS."""
    now = time.time()
    ttl = Config.TEMP_FILE_TTL_SECONDS
    
    for base_dir in [Config.UPLOAD_FOLDER, Config.OUTPUT_FOLDER, Config.TEMP_FOLDER]:
        if not os.path.exists(base_dir):
            continue
        try:
            for item in os.listdir(base_dir):
                if item == ".gitkeep":
                    continue
                item_path = os.path.join(base_dir, item)
                try:
                    stat = os.stat(item_path)
                    if now - stat.st_mtime > ttl:
                        if os.path.isdir(item_path):
                            shutil.rmtree(item_path, ignore_errors=True)
                        else:
                            os.remove(item_path)
                except Exception:
                    continue
        except Exception:
            continue

def cleanup_job(job_id: str):
    """Immediately remove a job's uploads and outputs."""
    up = os.path.join(Config.UPLOAD_FOLDER, job_id)
    out = os.path.join(Config.OUTPUT_FOLDER, job_id)
    if os.path.isdir(up):
        shutil.rmtree(up, ignore_errors=True)
    if os.path.isdir(out):
        shutil.rmtree(out, ignore_errors=True)

def find_job_pdf(job_id: str, filename: str = None) -> str | None:
    """
    Search for a PDF in a job's upload directory or output directory.
    If filename is specified, looks for that file first.
    Otherwise finds the first available PDF.
    """
    up = os.path.join(Config.UPLOAD_FOLDER, job_id)
    out = os.path.join(Config.OUTPUT_FOLDER, job_id)
    
    if filename:
        for folder in [up, out]:
            if os.path.isdir(folder):
                candidate = os.path.join(folder, filename)
                if os.path.isfile(candidate) and candidate.lower().endswith(".pdf"):
                    return candidate
                    
    if os.path.isdir(up):
        pdfs = [f for f in sorted(os.listdir(up)) if f.lower().endswith(".pdf")]
        if pdfs:
            return os.path.join(up, pdfs[0])
            
    if os.path.isdir(out):
        pdfs = [f for f in sorted(os.listdir(out)) if f.lower().endswith(".pdf")]
        if pdfs:
            return os.path.join(out, pdfs[0])
            
    return None

