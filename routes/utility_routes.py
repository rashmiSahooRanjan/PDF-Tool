import os
from pathlib import Path
from flask import Blueprint, render_template, request, jsonify

from config import Config
from utils.file_manager import get_job_upload_dir, get_job_output_dir, find_job_pdf
from utils.system_checker import get_system_capabilities
from services.job_service import job_service
import services.utility_service as utils_srv

utility_bp = Blueprint("utility", __name__)

@utility_bp.route("/utilities")
def utilities_page():
    """Render PDF utilities suite."""
    caps = get_system_capabilities()
    return render_template("utilities.html", capabilities=caps)

@utility_bp.route("/api/pdf/merge", methods=["POST"])
def merge_endpoint():
    """Merge uploaded PDF documents."""
    data = request.get_json() or {}
    job_id = data.get("job_id")
    filenames = data.get("filenames") or []
    
    if not job_id:
        return jsonify({"error": "Missing job_id."}), 400
        
    upload_dir = get_job_upload_dir(job_id)
    if not filenames:
        filenames = [f for f in sorted(os.listdir(upload_dir)) if f.lower().endswith(".pdf")]
        
    if len(filenames) < 2:
        return jsonify({"error": "At least 2 PDF files are required for merging."}), 400
        
    input_paths = [os.path.join(upload_dir, fn) for fn in filenames]
    for p in input_paths:
        if not os.path.isfile(p):
            return jsonify({"error": f"File not found: {os.path.basename(p)}"}), 404
            
    out_dir = get_job_output_dir(job_id)
    output_filename = "docuflex_merged.pdf"
    output_filepath = os.path.join(out_dir, output_filename)
    
    def _run():
        try:
            job_service.update_job(job_id, status="processing", progress=10, message="Merging PDF documents...")
            res = utils_srv.merge_pdfs(input_paths, output_filepath, job_id=job_id)
            job_service.set_completed(
                job_id=job_id,
                output_filepath=res,
                output_filename=output_filename,
                output_mimetype="application/pdf",
                output_size=os.path.getsize(res)
            )
        except Exception as e:
            job_service.set_failed(job_id, str(e))
            
    job_service.submit_task(_run)
    return jsonify({"success": True, "job_id": job_id, "status": "processing"})

@utility_bp.route("/api/pdf/split", methods=["POST"])
def split_endpoint():
    """Split or extract pages from a PDF."""
    data = request.get_json() or {}
    job_id = data.get("job_id")
    page_ranges = data.get("page_ranges", "1")
    filename = data.get("filename")
    
    if not job_id:
        return jsonify({"error": "Missing job_id."}), 400
        
    input_path = find_job_pdf(job_id, filename)
    if not input_path:
        return jsonify({"error": "No PDF found for this job."}), 404
        
    src_name = os.path.basename(input_path)
    out_dir = get_job_output_dir(job_id)
    output_filename = f"{Path(src_name).stem}_extracted.pdf"
    output_filepath = os.path.join(out_dir, output_filename)
    
    def _run():
        try:
            job_service.update_job(job_id, status="processing", progress=15, message="Extracting requested pages...")
            res = utils_srv.split_pdf(input_path, output_filepath, page_ranges, job_id=job_id)
            job_service.set_completed(
                job_id=job_id,
                output_filepath=res,
                output_filename=output_filename,
                output_mimetype="application/pdf",
                output_size=os.path.getsize(res)
            )
        except Exception as e:
            job_service.set_failed(job_id, str(e))
            
    job_service.submit_task(_run)
    return jsonify({"success": True, "job_id": job_id, "status": "processing"})

@utility_bp.route("/api/pdf/rotate", methods=["POST"])
def rotate_endpoint():
    """Rotate PDF pages."""
    data = request.get_json() or {}
    job_id = data.get("job_id")
    rotation = int(data.get("rotation", 90))
    pages = data.get("pages")
    filename = data.get("filename")
    
    if not job_id:
        return jsonify({"error": "Missing job_id."}), 400
        
    input_path = find_job_pdf(job_id, filename)
    if not input_path:
        return jsonify({"error": "No PDF found for this job."}), 404
        
    src_name = os.path.basename(input_path)
    out_dir = get_job_output_dir(job_id)
    output_filename = f"{Path(src_name).stem}_rotated.pdf"
    output_filepath = os.path.join(out_dir, output_filename)
    
    def _run():
        try:
            job_service.update_job(job_id, status="processing", progress=20, message="Applying page rotation...")
            res = utils_srv.rotate_pdf(input_path, output_filepath, rotation=rotation, pages=pages, job_id=job_id)
            job_service.set_completed(
                job_id=job_id,
                output_filepath=res,
                output_filename=output_filename,
                output_mimetype="application/pdf",
                output_size=os.path.getsize(res)
            )
        except Exception as e:
            job_service.set_failed(job_id, str(e))
            
    job_service.submit_task(_run)
    return jsonify({"success": True, "job_id": job_id, "status": "processing"})

@utility_bp.route("/api/pdf/compress", methods=["POST"])
def compress_endpoint():
    """Compress PDF document."""
    data = request.get_json() or {}
    job_id = data.get("job_id")
    level = data.get("level", "medium")
    filename = data.get("filename")
    
    if not job_id:
        return jsonify({"error": "Missing job_id."}), 400
        
    input_path = find_job_pdf(job_id, filename)
    if not input_path:
        return jsonify({"error": "No PDF found for this job."}), 404
        
    src_name = os.path.basename(input_path)
    out_dir = get_job_output_dir(job_id)
    output_filename = f"{Path(src_name).stem}_compressed.pdf"
    output_filepath = os.path.join(out_dir, output_filename)
    
    def _run():
        try:
            job_service.update_job(job_id, status="processing", progress=10, message="Compressing PDF structures...")
            res = utils_srv.compress_pdf(input_path, output_filepath, compression_level=level, job_id=job_id)
            orig_size = os.path.getsize(input_path)
            new_size = os.path.getsize(res)
            savings_pct = round(max(0, (orig_size - new_size) / max(1, orig_size) * 100), 1)
            
            job_service.set_completed(
                job_id=job_id,
                output_filepath=res,
                output_filename=output_filename,
                output_mimetype="application/pdf",
                output_size=new_size
            )
            job_service.update_job(job_id, savings=f"{savings_pct}% reduced")
        except Exception as e:
            job_service.set_failed(job_id, str(e))
            
    job_service.submit_task(_run)
    return jsonify({"success": True, "job_id": job_id, "status": "processing"})

@utility_bp.route("/api/pdf/watermark", methods=["POST"])
def watermark_endpoint():
    """Apply text watermark to PDF."""
    data = request.get_json() or {}
    job_id = data.get("job_id")
    text = data.get("text", "CONFIDENTIAL")
    opacity = float(data.get("opacity", 0.25))
    font_size = int(data.get("font_size", 44))
    angle = int(data.get("angle", 45))
    color = data.get("color", "#94A3B8")
    filename = data.get("filename")
    
    if not job_id:
        return jsonify({"error": "Missing job_id."}), 400
        
    input_path = find_job_pdf(job_id, filename)
    if not input_path:
        return jsonify({"error": "No PDF found for this job."}), 404
        
    src_name = os.path.basename(input_path)
    out_dir = get_job_output_dir(job_id)
    output_filename = f"{Path(src_name).stem}_watermarked.pdf"
    output_filepath = os.path.join(out_dir, output_filename)
    
    def _run():
        try:
            job_service.update_job(job_id, status="processing", progress=20, message="Applying watermark...")
            res = utils_srv.add_watermark(input_path, output_filepath, watermark_text=text, opacity=opacity, font_size=font_size, angle=angle, color_hex=color)
            job_service.set_completed(
                job_id=job_id,
                output_filepath=res,
                output_filename=output_filename,
                output_mimetype="application/pdf",
                output_size=os.path.getsize(res)
            )
        except Exception as e:
            job_service.set_failed(job_id, str(e))
            
    job_service.submit_task(_run)
    return jsonify({"success": True, "job_id": job_id, "status": "processing"})

@utility_bp.route("/api/pdf/page-numbers", methods=["POST"])
@utility_bp.route("/api/pdf/page_numbers", methods=["POST"])
def page_numbers_endpoint():
    """Apply page numbers to PDF."""
    data = request.get_json() or {}
    job_id = data.get("job_id")
    format_str = data.get("format", "Page {page} of {total}")
    position = data.get("position", "bottom-center")
    start_num = int(data.get("start", 1))
    filename = data.get("filename")
    
    if not job_id:
        return jsonify({"error": "Missing job_id."}), 400
        
    input_path = find_job_pdf(job_id, filename)
    if not input_path:
        return jsonify({"error": "No PDF found for this job."}), 404
        
    src_name = os.path.basename(input_path)
    out_dir = get_job_output_dir(job_id)
    output_filename = f"{Path(src_name).stem}_numbered.pdf"
    output_filepath = os.path.join(out_dir, output_filename)
    
    def _run():
        try:
            job_service.update_job(job_id, status="processing", progress=20, message="Adding page numbers...")
            res = utils_srv.add_page_numbers(input_path, output_filepath, format_str=format_str, position=position, start_page=start_num)
            job_service.set_completed(
                job_id=job_id,
                output_filepath=res,
                output_filename=output_filename,
                output_mimetype="application/pdf",
                output_size=os.path.getsize(res)
            )
        except Exception as e:
            job_service.set_failed(job_id, str(e))
            
    job_service.submit_task(_run)
    return jsonify({"success": True, "job_id": job_id, "status": "processing"})

@utility_bp.route("/api/pdf/protect", methods=["POST"])
def protect_endpoint():
    """Password protect PDF."""
    data = request.get_json() or {}
    job_id = data.get("job_id")
    password = data.get("password")
    filename = data.get("filename")
    
    if not job_id:
        return jsonify({"error": "Missing job_id."}), 400
    if not password:
        return jsonify({"error": "Password cannot be empty."}), 400
        
    input_path = find_job_pdf(job_id, filename)
    if not input_path:
        return jsonify({"error": "No PDF found for this job."}), 404
        
    src_name = os.path.basename(input_path)
    out_dir = get_job_output_dir(job_id)
    output_filename = f"{Path(src_name).stem}_protected.pdf"
    output_filepath = os.path.join(out_dir, output_filename)
    
    try:
        res = utils_srv.protect_pdf(input_path, output_filepath, user_pw=password)
        job_service.set_completed(
            job_id=job_id,
            output_filepath=res,
            output_filename=output_filename,
            output_mimetype="application/pdf",
            output_size=os.path.getsize(res)
        )
        return jsonify({"success": True, "job_id": job_id, "status": "completed"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@utility_bp.route("/api/pdf/unlock", methods=["POST"])
def unlock_endpoint():
    """Unlock password protected PDF."""
    data = request.get_json() or {}
    job_id = data.get("job_id")
    password = data.get("password", "")
    filename = data.get("filename")
    
    if not job_id:
        return jsonify({"error": "Missing job_id."}), 400
        
    input_path = find_job_pdf(job_id, filename)
    if not input_path:
        return jsonify({"error": "No PDF found for this job."}), 404
        
    src_name = os.path.basename(input_path)
    out_dir = get_job_output_dir(job_id)
    output_filename = f"{Path(src_name).stem}_unlocked.pdf"
    output_filepath = os.path.join(out_dir, output_filename)
    
    try:
        res = utils_srv.unlock_pdf(input_path, output_filepath, password=password)
        job_service.set_completed(
            job_id=job_id,
            output_filepath=res,
            output_filename=output_filename,
            output_mimetype="application/pdf",
            output_size=os.path.getsize(res)
        )
        return jsonify({"success": True, "job_id": job_id, "status": "completed"})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@utility_bp.route("/api/pdf/remove_pages", methods=["POST"])
def remove_pages_endpoint():
    """Remove specified page numbers or intervals from PDF."""
    data = request.get_json() or {}
    job_id = data.get("job_id")
    pages_to_remove = data.get("pages_to_remove", "1")
    filename = data.get("filename")
    
    if not job_id:
        return jsonify({"error": "Missing job_id."}), 400
        
    input_path = find_job_pdf(job_id, filename)
    if not input_path:
        return jsonify({"error": "No PDF found."}), 404
        
    src_name = os.path.basename(input_path)
    out_dir = get_job_output_dir(job_id)
    output_filename = f"{Path(src_name).stem}_pages_removed.pdf"
    output_filepath = os.path.join(out_dir, output_filename)
    
    try:
        res = utils_srv.remove_pages(input_path, output_filepath, pages_to_remove)
        job_service.set_completed(
            job_id=job_id,
            output_filepath=res,
            output_filename=output_filename,
            output_mimetype="application/pdf",
            output_size=os.path.getsize(res)
        )
        return jsonify({"success": True, "job_id": job_id, "download_url": f"/api/download/{job_id}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@utility_bp.route("/api/pdf/repair", methods=["POST"])
def repair_endpoint():
    """Repair damaged or malformed PDF."""
    data = request.get_json() or {}
    job_id = data.get("job_id")
    filename = data.get("filename")
    
    if not job_id:
        return jsonify({"error": "Missing job_id."}), 400
        
    input_path = find_job_pdf(job_id, filename)
    if not input_path:
        return jsonify({"error": "No PDF found."}), 404
        
    src_name = os.path.basename(input_path)
    out_dir = get_job_output_dir(job_id)
    output_filename = f"{Path(src_name).stem}_repaired.pdf"
    output_filepath = os.path.join(out_dir, output_filename)
    
    try:
        res = utils_srv.repair_pdf(input_path, output_filepath)
        job_service.set_completed(
            job_id=job_id,
            output_filepath=res,
            output_filename=output_filename,
            output_mimetype="application/pdf",
            output_size=os.path.getsize(res)
        )
        return jsonify({"success": True, "job_id": job_id, "download_url": f"/api/download/{job_id}"})
    except Exception as e:
        return jsonify({"error": f"Failed to repair PDF: {str(e)}"}), 500

@utility_bp.route("/api/pdf/crop", methods=["POST"])
def crop_endpoint():
    """Crop PDF page margins."""
    data = request.get_json() or {}
    job_id = data.get("job_id")
    margins = data.get("margins") or {"top": 36, "bottom": 36, "left": 36, "right": 36}
    filename = data.get("filename")
    
    if not job_id:
        return jsonify({"error": "Missing job_id."}), 400
        
    input_path = find_job_pdf(job_id, filename)
    if not input_path:
        return jsonify({"error": "No PDF found."}), 404
        
    src_name = os.path.basename(input_path)
    out_dir = get_job_output_dir(job_id)
    output_filename = f"{Path(src_name).stem}_cropped.pdf"
    output_filepath = os.path.join(out_dir, output_filename)
    
    try:
        res = utils_srv.crop_pdf(input_path, output_filepath, margins)
        job_service.set_completed(
            job_id=job_id,
            output_filepath=res,
            output_filename=output_filename,
            output_mimetype="application/pdf",
            output_size=os.path.getsize(res)
        )
        return jsonify({"success": True, "job_id": job_id, "download_url": f"/api/download/{job_id}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@utility_bp.route("/api/pdf/forms/inspect", methods=["POST"])
def forms_inspect_endpoint():
    """Inspect AcroForms form fields in document."""
    data = request.get_json() or {}
    job_id = data.get("job_id")
    filename = data.get("filename")
    
    if not job_id:
        return jsonify({"error": "Missing job_id."}), 400
        
    input_path = find_job_pdf(job_id, filename)
    if not input_path:
        return jsonify({"error": "No PDF found."}), 404
        
    try:
        report = utils_srv.inspect_pdf_forms(input_path)
        return jsonify({"success": True, "data": report})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@utility_bp.route("/api/pdf/forms/fill", methods=["POST"])
def forms_fill_endpoint():
    """Fill interactive AcroForms form fields."""
    data = request.get_json() or {}
    job_id = data.get("job_id")
    field_data = data.get("fields") or {}
    filename = data.get("filename")
    
    if not job_id:
        return jsonify({"error": "Missing job_id."}), 400
        
    input_path = find_job_pdf(job_id, filename)
    if not input_path:
        return jsonify({"error": "No PDF found."}), 404
        
    src_name = os.path.basename(input_path)
    out_dir = get_job_output_dir(job_id)
    output_filename = f"{Path(src_name).stem}_form_filled.pdf"
    output_filepath = os.path.join(out_dir, output_filename)
    
    try:
        res = utils_srv.fill_pdf_forms(input_path, output_filepath, field_data)
        job_service.set_completed(
            job_id=job_id,
            output_filepath=res,
            output_filename=output_filename,
            output_mimetype="application/pdf",
            output_size=os.path.getsize(res)
        )
        return jsonify({"success": True, "job_id": job_id, "download_url": f"/api/download/{job_id}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@utility_bp.route("/api/pdf/redact_keywords", methods=["POST"])
def redact_keywords_endpoint():
    """Search and permanently redact sensitive terms or presets."""
    data = request.get_json() or {}
    job_id = data.get("job_id")
    keywords = data.get("keywords") or []
    presets = data.get("presets") or [] # e.g. ["email", "ssn", "phone", "credit_card"]
    fill_hex = data.get("fill_color", "#000000")
    filename = data.get("filename")
    
    if not job_id:
        return jsonify({"error": "Missing job_id."}), 400
        
    input_path = find_job_pdf(job_id, filename)
    if not input_path:
        return jsonify({"error": "No PDF found."}), 404
        
    src_name = os.path.basename(input_path)
    out_dir = get_job_output_dir(job_id)
    output_filename = f"{Path(src_name).stem}_redacted.pdf"
    output_filepath = os.path.join(out_dir, output_filename)
    
    try:
        report = utils_srv.redact_pdf_keywords(input_path, output_filepath, keywords, presets, fill_hex)
        job_service.set_completed(
            job_id=job_id,
            output_filepath=output_filepath,
            output_filename=output_filename,
            output_mimetype="application/pdf",
            output_size=os.path.getsize(output_filepath)
        )
        return jsonify({
            "success": True,
            "job_id": job_id,
            "total_redactions": report["total_redactions"],
            "download_url": f"/api/download/{job_id}"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@utility_bp.route("/api/pdf/compare_files", methods=["POST"])
def compare_files_endpoint():
    """Compare two uploaded PDF files."""
    data = request.get_json() or {}
    job_id = data.get("job_id")
    file1 = data.get("file1")
    file2 = data.get("file2")
    
    if not job_id:
        return jsonify({"error": "Missing job_id."}), 400
        
    upload_dir = get_job_upload_dir(job_id)
    files = [f for f in os.listdir(upload_dir) if f.lower().endswith(".pdf")]
    
    if len(files) < 2 and (not file1 or not file2):
        return jsonify({"error": "Two PDF documents are required for comparison."}), 400
        
    p1 = os.path.join(upload_dir, file1 if file1 else files[0])
    p2 = os.path.join(upload_dir, file2 if file2 else files[1])
    
    try:
        report = utils_srv.compare_pdfs(p1, p2)
        return jsonify({"success": True, "comparison": report})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@utility_bp.route("/api/pdf/sign", methods=["POST"])
def sign_endpoint():
    """Stamp digital signature onto PDF document."""
    data = request.get_json() or {}
    job_id = data.get("job_id")
    signature_data = data.get("signature")
    page_number = int(data.get("page", -1))
    x = data.get("x")
    y = data.get("y")
    width = float(data.get("width", 160))
    height = float(data.get("height", 60))
    filename = data.get("filename")
    
    if not job_id:
        return jsonify({"error": "Missing job_id."}), 400
    if not signature_data:
        return jsonify({"error": "Missing signature data."}), 400
        
    input_path = find_job_pdf(job_id, filename)
    if not input_path:
        return jsonify({"error": "No PDF found."}), 404
        
    src_name = os.path.basename(input_path)
    out_dir = get_job_output_dir(job_id)
    output_filename = f"{Path(src_name).stem}_signed.pdf"
    output_filepath = os.path.join(out_dir, output_filename)
    
    try:
        res = utils_srv.sign_pdf(
            input_path=input_path,
            output_path=output_filepath,
            signature_data=signature_data,
            page_number=page_number,
            x=x,
            y=y,
            width=width,
            height=height
        )
        job_service.set_completed(
            job_id=job_id,
            output_filepath=res,
            output_filename=output_filename,
            output_mimetype="application/pdf",
            output_size=os.path.getsize(res)
        )
        return jsonify({"success": True, "job_id": job_id, "download_url": f"/api/download/{job_id}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
