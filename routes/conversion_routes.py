import os
from pathlib import Path
from flask import Blueprint, render_template, request, jsonify

from config import Config
from utils.file_manager import get_job_upload_dir, get_job_output_dir
from utils.system_checker import get_system_capabilities
from services.job_service import job_service
from services.conversion_service import execute_conversion

conversion_bp = Blueprint("conversion", __name__)

MIME_TYPE_MAP = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
    "pdfa": "application/pdf",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "zip": "application/zip",
    "md": "text/markdown"
}

@conversion_bp.route("/convert")
def convert_page():
    """Render document conversion workspace."""
    caps = get_system_capabilities()
    return render_template("convert.html", capabilities=caps)

@conversion_bp.route("/api/convert", methods=["POST"])
def convert_document():
    """
    Launch asynchronous conversion for uploaded document.
    """
    data = request.get_json() or {}
    job_id = data.get("job_id")
    target_format = (data.get("target_format") or "").lower().strip()
    options = data.get("options") or {}
    
    if not job_id:
        return jsonify({"error": "Missing required job_id."}), 400
    if not target_format:
        return jsonify({"error": "Missing target format."}), 400
        
    upload_dir = get_job_upload_dir(job_id)
    files = [f for f in os.listdir(upload_dir) if os.path.isfile(os.path.join(upload_dir, f))]
    if not files:
        return jsonify({"error": "No uploaded files found for this job."}), 404
        
    source_filename = data.get("filename") or files[0]
    source_filepath = os.path.join(upload_dir, source_filename)
    
    if not os.path.isfile(source_filepath):
        return jsonify({"error": f"File '{source_filename}' not found."}), 404
        
    source_ext = source_filename.rsplit(".", 1)[-1].lower()
    stem = Path(source_filename).stem
    
    # Determine target filename & output path
    out_dir = get_job_output_dir(job_id)
    if target_format == "pdfa":
        output_filename = f"{stem}_archival_PDFA.pdf"
    elif target_format == "md":
        output_filename = f"{stem}_converted.md"
    else:
        output_filename = f"{stem}_converted.{target_format}"
    output_filepath = os.path.join(out_dir, output_filename)
    
    # Initialize job tracking
    job_service.update_job(
        job_id,
        operation=f"convert_{source_ext}_to_{target_format}",
        status="processing",
        progress=5,
        message=f"Starting conversion from {source_ext.upper()} to {target_format.upper()}..."
    )
    
    # Run conversion asynchronously
    def _run_conversion():
        try:
            res_path = execute_conversion(
                from_ext=source_ext,
                to_ext=target_format,
                input_path=source_filepath,
                output_path=output_filepath,
                job_id=job_id,
                **options
            )
            final_name = os.path.basename(res_path)
            final_ext = final_name.rsplit(".", 1)[-1].lower()
            mimetype = MIME_TYPE_MAP.get(final_ext, "application/octet-stream")
            file_size = os.path.getsize(res_path)
            
            job_service.set_completed(
                job_id=job_id,
                output_filepath=res_path,
                output_filename=final_name,
                output_mimetype=mimetype,
                output_size=file_size
            )
        except Exception as e:
            job_service.set_failed(job_id, str(e))
            
    job_service.submit_task(_run_conversion)
    
    return jsonify({
        "success": True,
        "job_id": job_id,
        "message": f"Conversion job started: {source_ext.upper()} to {target_format.upper()}",
        "status": "processing"
    })
