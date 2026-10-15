import os
from pathlib import Path
from flask import Blueprint, render_template, request, jsonify

from config import Config
from utils.file_manager import get_job_upload_dir, get_job_output_dir
from utils.system_checker import get_system_capabilities, get_tesseract_languages, find_tesseract
from services.job_service import job_service
from services.ocr_service import extract_text_ocr, create_searchable_pdf

ocr_bp = Blueprint("ocr", __name__)

@ocr_bp.route("/ocr")
def ocr_page():
    """Render OCR Studio interface."""
    caps = get_system_capabilities()
    return render_template("ocr.html", capabilities=caps)

@ocr_bp.route("/api/ocr/languages")
def ocr_languages():
    """List available OCR languages."""
    langs = get_tesseract_languages() if find_tesseract() else []
    return jsonify({"available": find_tesseract() is not None, "languages": langs})

@ocr_bp.route("/api/pdf/ocr", methods=["POST"])
def run_ocr():
    """
    Run OCR on scanned PDF or image.
    Modes:
      - 'extract_text': returns raw extracted text string
      - 'searchable_pdf': creates a new searchable PDF document with text layer
    """
    data = request.get_json() or {}
    job_id = data.get("job_id")
    mode = data.get("mode", "extract_text")
    lang = data.get("language", "eng")
    filename = data.get("filename")
    
    if not job_id:
        return jsonify({"error": "Missing job_id."}), 400
        
    upload_dir = get_job_upload_dir(job_id)
    files = [f for f in os.listdir(upload_dir) if os.path.isfile(os.path.join(upload_dir, f))]
    if not files:
        return jsonify({"error": "No files found for this job."}), 404
        
    src_name = filename if (filename and filename in files) else files[0]
    input_path = os.path.join(upload_dir, src_name)
    stem = Path(src_name).stem
    
    if mode == "extract_text":
        try:
            result = extract_text_ocr(input_path, lang=lang, job_id=job_id)
            # Also save as a text file in outputs
            out_dir = get_job_output_dir(job_id)
            txt_filename = f"{stem}_ocr_extracted.txt"
            txt_filepath = os.path.join(out_dir, txt_filename)
            with open(txt_filepath, "w", encoding="utf-8") as f:
                f.write(result["text"])
                
            job_service.set_completed(
                job_id=job_id,
                output_filepath=txt_filepath,
                output_filename=txt_filename,
                output_mimetype="text/plain; charset=utf-8",
                output_size=os.path.getsize(txt_filepath)
            )
            return jsonify({
                "success": True,
                "job_id": job_id,
                "extracted_text": result["text"],
                "character_count": result["character_count"],
                "download_url": f"/api/download/{job_id}"
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 400
            
    elif mode == "searchable_pdf":
        out_dir = get_job_output_dir(job_id)
        output_filename = f"{stem}_searchable.pdf"
        output_filepath = os.path.join(out_dir, output_filename)
        
        def _run_searchable():
            try:
                job_service.update_job(job_id, status="processing", progress=15, message="Generating searchable OCR text layer...")
                res = create_searchable_pdf(input_path, output_filepath, lang=lang, job_id=job_id)
                job_service.set_completed(
                    job_id=job_id,
                    output_filepath=res,
                    output_filename=output_filename,
                    output_mimetype="application/pdf",
                    output_size=os.path.getsize(res)
                )
            except Exception as e:
                job_service.set_failed(job_id, str(e))
                
        job_service.submit_task(_run_searchable)
        return jsonify({"success": True, "job_id": job_id, "status": "processing"})
        
    return jsonify({"error": "Unknown OCR mode."}), 400
