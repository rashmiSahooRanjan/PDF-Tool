import os
from flask import Blueprint, render_template, request, jsonify, send_file, current_app
from werkzeug.utils import secure_filename

from config import Config
from utils.validators import is_allowed_file, validate_magic_bytes, sanitize_safe_filename, is_safe_path
from utils.file_manager import generate_job_id, get_job_upload_dir, get_job_output_dir, cleanup_expired_files
from utils.system_checker import get_system_capabilities
from services.job_service import job_service
from services.utility_service import get_pdf_metadata

main_bp = Blueprint("main", __name__)

@main_bp.route("/")
def index():
    """Render main application dashboard."""
    caps = get_system_capabilities()
    return render_template("index.html", capabilities=caps)

@main_bp.route("/api/health", methods=["GET"])
def health_check():
    """System health check and environmental capabilities."""
    cleanup_expired_files()
    caps = get_system_capabilities()
    return jsonify({
        "status": "healthy",
        "service": "iLovePDF Pro",
        "version": "1.0.0",
        "capabilities": caps
    })

@main_bp.route("/api/upload", methods=["POST"])
def upload_file():
    """
    Handle single or multiple file uploads securely.
    Validates extension and binary magic signatures.
    """
    cleanup_expired_files()
    
    if "file" not in request.files and "files" not in request.files:
        return jsonify({"error": "No file uploaded in request."}), 400
        
    uploaded_files = request.files.getlist("files") or [request.files.get("file")]
    uploaded_files = [f for f in uploaded_files if f and f.filename]
    
    if not uploaded_files:
        return jsonify({"error": "No selected files."}), 400
        
    job_id = generate_job_id()
    upload_dir = get_job_upload_dir(job_id)
    saved_files = []
    
    for f in uploaded_files:
        orig_name = f.filename
        if not is_allowed_file(orig_name):
            return jsonify({
                "error": f"File type for '{orig_name}' is not allowed. Supported: {', '.join(Config.ALLOWED_EXTENSIONS)}"
            }), 400
            
        safe_name = sanitize_safe_filename(orig_name)
        target_path = os.path.join(upload_dir, safe_name)
        
        if not is_safe_path(Config.UPLOAD_FOLDER, target_path):
            return jsonify({"error": "Invalid storage path detected."}), 400
            
        f.save(target_path)
        
        # Binary magic-signature check
        ext = safe_name.rsplit(".", 1)[-1].lower()
        if not validate_magic_bytes(target_path, ext):
            os.remove(target_path)
            return jsonify({
                "error": f"Security validation failed: File content of '{orig_name}' does not match its .{ext} extension."
            }), 400
            
        file_size = os.path.getsize(target_path)
        saved_files.append({
            "filename": safe_name,
            "filepath": target_path,
            "size": file_size,
            "extension": ext
        })
        
    # Inspect metadata if primary file is a PDF
    metadata = None
    first = saved_files[0]
    if first["extension"] == "pdf":
        try:
            metadata = get_pdf_metadata(first["filepath"])
        except Exception:
            metadata = None
            
    job = job_service.create_job(job_id, "upload", first["filename"])
    job_service.set_progress(job_id, 100, "Files uploaded and validated successfully.")
    
    return jsonify({
        "success": True,
        "job_id": job_id,
        "files": saved_files,
        "metadata": metadata
    })

@main_bp.route("/api/jobs/<job_id>", methods=["GET"])
def get_job_status(job_id: str):
    """Poll status of an asynchronous processing job."""
    job = job_service.get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found or expired."}), 404
    return jsonify(job)

@main_bp.route("/api/download/<job_id>", methods=["GET"])
def download_output(job_id: str):
    """
    Serve generated file download associated with job ID.
    Enforces authorization by job ID matching.
    """
    job = job_service.get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found or expired."}), 404
        
    if job.get("status") != "completed":
        return jsonify({"error": "Processing is not yet complete."}), 400
        
    filepath = job.get("output_filepath")
    if not filepath or not os.path.isfile(filepath):
        return jsonify({"error": "Output file not found on disk."}), 404
        
    if not is_safe_path(Config.OUTPUT_FOLDER, filepath):
        return jsonify({"error": "Access denied to requested path."}), 403
        
    download_name = job.get("output_filename") or os.path.basename(filepath)
    mimetype = job.get("output_mimetype") or "application/octet-stream"
    
    return send_file(
        filepath,
        mimetype=mimetype,
        as_attachment=True,
        download_name=download_name
    )

@main_bp.route("/api/metadata", methods=["POST"])
def inspect_pdf():
    """Extract metadata for an uploaded PDF."""
    data = request.get_json() or {}
    job_id = data.get("job_id")
    filename = data.get("filename")
    
    if not job_id:
        return jsonify({"error": "Missing job_id."}), 400
        
    upload_dir = get_job_upload_dir(job_id)
    files = [f for f in os.listdir(upload_dir) if f.lower().endswith(".pdf")]
    if not files:
        return jsonify({"error": "No PDF found in this session."}), 404
        
    target_name = filename if filename in files else files[0]
    filepath = os.path.join(upload_dir, target_name)
    
    try:
        meta = get_pdf_metadata(filepath)
        return jsonify({"success": True, "metadata": meta})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
