import os
from pathlib import Path
from flask import Blueprint, request, jsonify

from config import Config
from utils.file_manager import get_job_upload_dir, get_job_output_dir, find_job_pdf
from services.job_service import job_service
from services.intelligence_service import summarize_pdf, translate_pdf_text, convert_pdf_to_markdown

intelligence_bp = Blueprint("intelligence", __name__)

@intelligence_bp.route("/api/intelligence/summarize", methods=["POST"])
def summarize_endpoint():
    """Extract key takeaways and executive summary from PDF."""
    data = request.get_json() or {}
    job_id = data.get("job_id")
    sentences_count = int(data.get("sentences", 5))
    filename = data.get("filename")

    if not job_id:
        return jsonify({"error": "Missing job_id."}), 400

    filepath = find_job_pdf(job_id, filename)
    if not filepath:
        return jsonify({"error": "No PDF found."}), 404

    try:
        summary_result = summarize_pdf(filepath, max_sentences=sentences_count)
        return jsonify(summary_result)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@intelligence_bp.route("/api/intelligence/translate", methods=["POST"])
def translate_endpoint():
    """Offline translation of document content."""
    data = request.get_json() or {}
    job_id = data.get("job_id")
    target_lang = data.get("target_language", "es")
    filename = data.get("filename")

    if not job_id:
        return jsonify({"error": "Missing job_id."}), 400

    filepath = find_job_pdf(job_id, filename)
    if not filepath:
        return jsonify({"error": "No PDF found."}), 404

    try:
        trans_res = translate_pdf_text(filepath, target_lang=target_lang)
        return jsonify(trans_res)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@intelligence_bp.route("/api/intelligence/markdown", methods=["POST"])
def markdown_endpoint():
    """Convert PDF to structured GitHub-Flavored Markdown."""
    data = request.get_json() or {}
    job_id = data.get("job_id")
    filename = data.get("filename")

    if not job_id:
        return jsonify({"error": "Missing job_id."}), 400

    filepath = find_job_pdf(job_id, filename)
    if not filepath:
        return jsonify({"error": "No PDF found."}), 404

    target_name = os.path.basename(filepath)
    out_dir = get_job_output_dir(job_id)
    md_name = f"{Path(target_name).stem}.md"
    md_path = os.path.join(out_dir, md_name)

    try:
        res = convert_pdf_to_markdown(filepath, md_path)
        job_service.set_completed(
            job_id=job_id,
            output_filepath=md_path,
            output_filename=md_name,
            output_mimetype="text/markdown",
            output_size=os.path.getsize(md_path)
        )
        return jsonify({
            "success": True,
            "job_id": job_id,
            "filename": md_name,
            "markdown": res["markdown"][:3000], # preview snippet
            "download_url": f"/api/download/{job_id}"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
