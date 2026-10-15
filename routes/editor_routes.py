import os
from pathlib import Path
from flask import Blueprint, render_template, request, jsonify, send_file
from docx import Document

from config import Config
from utils.file_manager import get_job_upload_dir, get_job_output_dir
from utils.system_checker import get_system_capabilities
from utils.validators import is_safe_path
from services.job_service import job_service
from services.editor_service import extract_page_text_spans, apply_pdf_edits
from services.conversion_service import convert_pdf_to_docx, convert_office_to_pdf
from services.ocr_service import create_searchable_pdf

editor_bp = Blueprint("editor", __name__)

@editor_bp.route("/editor")
def editor_page():
    """Render interactive PDF visual workspace."""
    caps = get_system_capabilities()
    return render_template("editor.html", capabilities=caps)

@editor_bp.route("/api/pdf/raw/<job_id>")
@editor_bp.route("/api/pdf/raw/<job_id>/<filename>")
def get_raw_pdf(job_id: str, filename: str = None):
    """
    Serve raw PDF binary to PDF.js viewer.
    Checks file presence and path safety.
    """
    upload_dir = get_job_upload_dir(job_id)
    out_dir = get_job_output_dir(job_id)
    
    # Check upload first, then output if looking for edited version
    search_dirs = [upload_dir, out_dir]
    target_filepath = None
    
    for sdir in search_dirs:
        if os.path.exists(sdir):
            files = [f for f in os.listdir(sdir) if f.lower().endswith(".pdf")]
            if filename and filename in files:
                target_filepath = os.path.join(sdir, filename)
                break
            elif not filename and files and not target_filepath:
                target_filepath = os.path.join(sdir, files[0])
                
    if not target_filepath or not os.path.exists(target_filepath):
        return jsonify({"error": "PDF document not found in session."}), 404
        
    return send_file(target_filepath, mimetype="application/pdf")

@editor_bp.route("/api/pdf/spans", methods=["POST"])
def get_spans():
    """Extract page text blocks, spans, fonts, styles, and scanned status."""
    data = request.get_json() or {}
    job_id = data.get("job_id")
    page_num = int(data.get("page", 0))
    filename = data.get("filename")
    
    if not job_id:
        return jsonify({"error": "Missing job_id."}), 400
        
    upload_dir = get_job_upload_dir(job_id)
    files = [f for f in os.listdir(upload_dir) if f.lower().endswith(".pdf")]
    if not files:
        return jsonify({"error": "No PDF found."}), 404
        
    target_name = filename if (filename and filename in files) else files[0]
    filepath = os.path.join(upload_dir, target_name)
    
    try:
        spans_data = extract_page_text_spans(filepath, page_number=page_num)
        return jsonify({"success": True, "data": spans_data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@editor_bp.route("/api/pdf/edit", methods=["POST"])
def edit_pdf_endpoint():
    """
    Save professional edits (text replacement, genuine redaction, textboxes,
    formatting, shapes, signatures, drawings, find/replace, page actions).
    """
    data = request.get_json() or {}
    job_id = data.get("job_id")
    operations = data.get("operations") or []
    filename = data.get("filename")
    
    if not job_id:
        return jsonify({"error": "Missing job_id."}), 400
    if not operations:
        return jsonify({"error": "No editing operations provided."}), 400
        
    upload_dir = get_job_upload_dir(job_id)
    files = [f for f in os.listdir(upload_dir) if f.lower().endswith(".pdf")]
    if not files:
        return jsonify({"error": "No PDF found."}), 404
        
    target_name = filename if (filename and filename in files) else files[0]
    input_path = os.path.join(upload_dir, target_name)
    
    out_dir = get_job_output_dir(job_id)
    output_filename = f"{Path(target_name).stem}_edited.pdf"
    output_filepath = os.path.join(out_dir, output_filename)
    
    try:
        res = apply_pdf_edits(input_path, output_filepath, operations)
        job_service.set_completed(
            job_id=job_id,
            output_filepath=res,
            output_filename=output_filename,
            output_mimetype="application/pdf",
            output_size=os.path.getsize(res)
        )
        return jsonify({
            "success": True,
            "job_id": job_id,
            "filename": output_filename,
            "download_url": f"/api/download/{job_id}",
            "edited_raw_url": f"/api/pdf/raw/{job_id}/{output_filename}"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@editor_bp.route("/api/pdf/ocr_assist", methods=["POST"])
def ocr_assist():
    """
    OCR-Assisted workflow for scanned PDFs:
    Generates a searchable PDF with selectable text layer, enabling in-place editing.
    """
    data = request.get_json() or {}
    job_id = data.get("job_id")
    filename = data.get("filename")
    
    if not job_id:
        return jsonify({"error": "Missing job_id."}), 400
        
    upload_dir = get_job_upload_dir(job_id)
    files = [f for f in os.listdir(upload_dir) if f.lower().endswith(".pdf")]
    if not files:
        return jsonify({"error": "No PDF found."}), 404
        
    target_name = filename if (filename and filename in files) else files[0]
    input_path = os.path.join(upload_dir, target_name)
    
    out_dir = get_job_output_dir(job_id)
    ocr_filename = f"{Path(target_name).stem}_searchable.pdf"
    ocr_filepath = os.path.join(out_dir, ocr_filename)
    
    try:
        create_searchable_pdf(input_path, ocr_filepath)
        # Copy to uploads so editor can continue editing it seamlessly
        dest_upload_path = os.path.join(upload_dir, ocr_filename)
        import shutil
        shutil.copyfile(ocr_filepath, dest_upload_path)
        
        return jsonify({
            "success": True,
            "filename": ocr_filename,
            "message": "OCR text layer created successfully! Document is now fully selectable and editable."
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@editor_bp.route("/api/pdf/reflow/init", methods=["POST"])
def reflow_init():
    """
    Initialize Word-like reflow mode: converts PDF to editable Word document
    and extracts paragraph contents for flowing textual edits.
    """
    data = request.get_json() or {}
    job_id = data.get("job_id")
    filename = data.get("filename")
    
    if not job_id:
        return jsonify({"error": "Missing job_id."}), 400
        
    upload_dir = get_job_upload_dir(job_id)
    files = [f for f in os.listdir(upload_dir) if f.lower().endswith(".pdf")]
    if not files:
        return jsonify({"error": "No PDF found."}), 404
        
    target_name = filename if (filename and filename in files) else files[0]
    input_path = os.path.join(upload_dir, target_name)
    
    out_dir = get_job_output_dir(job_id)
    docx_path = os.path.join(out_dir, f"{Path(target_name).stem}_reflow.docx")
    
    try:
        convert_pdf_to_docx(input_path, docx_path)
        doc = Document(docx_path)
        paragraphs = []
        for idx, p in enumerate(doc.paragraphs):
            t = p.text.strip()
            if t:
                paragraphs.append({
                    "id": idx,
                    "text": p.text,
                    "style": p.style.name if p.style else "Normal"
                })
                
        return jsonify({
            "success": True,
            "paragraph_count": len(paragraphs),
            "paragraphs": paragraphs,
            "note": "Reflow mode allows fluid paragraph editing. Re-saving will reconstruct the PDF layout."
        })
    except Exception as e:
        return jsonify({"error": f"Reflow conversion failed: {str(e)}"}), 500

@editor_bp.route("/api/pdf/reflow/save", methods=["POST"])
def reflow_save():
    """
    Save Word-like reflow edits: creates updated document and converts to PDF.
    """
    data = request.get_json() or {}
    job_id = data.get("job_id")
    paragraphs = data.get("paragraphs") or []
    filename = data.get("filename")
    
    if not job_id:
        return jsonify({"error": "Missing job_id."}), 400
        
    out_dir = get_job_output_dir(job_id)
    reflow_doc = Document()
    
    for p_data in paragraphs:
        text = p_data.get("text", "")
        style = p_data.get("style", "Normal")
        if text.strip():
            reflow_doc.add_paragraph(text)
            
    docx_save_path = os.path.join(out_dir, f"reflow_edited.docx")
    reflow_doc.save(docx_save_path)
    
    pdf_out_name = f"reflow_edited.pdf"
    pdf_out_path = os.path.join(out_dir, pdf_out_name)
    
    try:
        convert_office_to_pdf(docx_save_path, pdf_out_path)
        job_service.set_completed(
            job_id=job_id,
            output_filepath=pdf_out_path,
            output_filename=pdf_out_name,
            output_mimetype="application/pdf",
            output_size=os.path.getsize(pdf_out_path)
        )
        return jsonify({
            "success": True,
            "job_id": job_id,
            "filename": pdf_out_name,
            "download_url": f"/api/download/{job_id}"
        })
    except Exception as e:
        return jsonify({"error": f"Failed to generate reflowed PDF: {str(e)}"}), 500
