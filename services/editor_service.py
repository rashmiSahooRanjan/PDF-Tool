import os
import io
import math
import base64
from typing import List, Dict, Any, Optional, Tuple

import fitz  # PyMuPDF
from PIL import Image

# Standard 14 Base PDF font mappings for PyMuPDF
STANDARD_FONT_MAP = {
    # Helvetica / Sans
    ("helvetica", False, False): "helv",
    ("helvetica", True, False): "hebo",
    ("helvetica", False, True): "heit",
    ("helvetica", True, True): "hebi",
    # Times Roman / Serif
    ("times", False, False): "times",
    ("times", True, False): "tibo",
    ("times", False, True): "tiit",
    ("times", True, True): "tibi",
    # Courier / Monospace
    ("courier", False, False): "cour",
    ("courier", True, False): "cobo",
    ("courier", False, True): "coit",
    ("courier", True, True): "cobi",
}

def hex_to_rgb(hex_str: str) -> tuple[float, float, float]:
    """Convert hex color string like '#FF0000' to RGB tuple (0.0 to 1.0)."""
    if not hex_str:
        return (0.0, 0.0, 0.0)
    h = hex_str.lstrip("#")
    if len(h) == 6:
        return (int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0)
    elif len(h) == 3:
        return (int(h[0]*2, 16) / 255.0, int(h[1]*2, 16) / 255.0, int(h[2]*2, 16) / 255.0)
    return (0.0, 0.0, 0.0)

def resolve_font_spec(font_family: str, bold: bool = False, italic: bool = False) -> Tuple[str, str, bool]:
    """
    Map requested font family and style to standard PyMuPDF font code.
    Returns: (font_code, display_name, is_fallback_used)
    """
    fam = (font_family or "helvetica").lower()
    is_fallback = False
    
    if "time" in fam or "serif" in fam or "roman" in fam or "georgia" in fam or "cambria" in fam:
        base_fam = "times"
        display = "Times-Roman"
    elif "cour" in fam or "mono" in fam or "console" in fam or "typewriter" in fam:
        base_fam = "courier"
        display = "Courier"
    else:
        base_fam = "helvetica"
        display = "Helvetica"
        if fam not in ("helvetica", "arial", "sans-serif", "sans", "helv"):
            is_fallback = True

    font_code = STANDARD_FONT_MAP.get((base_fam, bool(bold), bool(italic)), "helv")
    return font_code, display, is_fallback

def map_alignment(align_str: str) -> int:
    """Map string alignment ('left', 'center', 'right', 'justify') to PyMuPDF alignment constants."""
    a = (align_str or "left").lower().strip()
    if a == "center":
        return fitz.TEXT_ALIGN_CENTER
    elif a == "right":
        return fitz.TEXT_ALIGN_RIGHT
    elif a == "justify":
        return fitz.TEXT_ALIGN_JUSTIFY
    return fitz.TEXT_ALIGN_LEFT

def extract_page_text_spans(input_path: str, page_number: int = 0) -> Dict[str, Any]:
    """
    Extract exact text blocks, lines, and spans with bounding boxes,
    font families, sizes, styles, flags, colors, and scanned page detection.
    """
    doc = fitz.open(input_path)
    try:
        if page_number < 0 or page_number >= len(doc):
            raise IndexError("Page number out of range.")
            
        page = doc[page_number]
        rect = page.rect
        page_dict = page.get_text("dict")
        
        spans_list = []
        blocks_list = []
        span_id_counter = 0
        block_id_counter = 0
        
        for block in page_dict.get("blocks", []):
            if block.get("type") == 0:  # Text block
                block_id_counter += 1
                b_bbox = block.get("bbox", [0, 0, 0, 0])
                block_spans = []
                
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "")
                        if not text.strip():
                            continue
                            
                        bbox = span.get("bbox", [0, 0, 0, 0])
                        color_int = span.get("color", 0)
                        flags = span.get("flags", 0)
                        font_name = span.get("font", "Helvetica")
                        size = round(span.get("size", 12), 2)
                        
                        # Extract RGB from color integer
                        r = ((color_int >> 16) & 255) / 255.0
                        g = ((color_int >> 8) & 255) / 255.0
                        b = (color_int & 255) / 255.0
                        hex_color = f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
                        
                        # Infer bold and italic from flags & font name
                        is_bold = bool(flags & 2 or "bold" in font_name.lower() or "black" in font_name.lower())
                        is_italic = bool(flags & 1 or "italic" in font_name.lower() or "oblique" in font_name.lower())
                        
                        # Standard font resolution
                        _, std_display, is_fallback = resolve_font_spec(font_name, is_bold, is_italic)
                        
                        span_id_counter += 1
                        span_obj = {
                            "id": f"span_{page_number}_{span_id_counter}",
                            "block_id": block_id_counter,
                            "text": text,
                            "bbox": [round(coord, 2) for coord in bbox],
                            "font": font_name,
                            "standard_font": std_display,
                            "is_fallback": is_fallback,
                            "size": size,
                            "flags": flags,
                            "bold": is_bold,
                            "italic": is_italic,
                            "color": hex_color,
                            "color_rgb": [r, g, b]
                        }
                        spans_list.append(span_obj)
                        block_spans.append(span_obj)
                        
                if block_spans:
                    blocks_list.append({
                        "id": f"block_{page_number}_{block_id_counter}",
                        "bbox": [round(c, 2) for c in b_bbox],
                        "span_count": len(block_spans),
                        "text": " ".join(s["text"] for s in block_spans)
                    })
                    
        # Check if page is scanned (has images but very little/no selectable text)
        page_images = page.get_images()
        is_scanned = len(spans_list) == 0 and len(page_images) > 0
        
        return {
            "page_number": page_number,
            "width": round(rect.width, 2),
            "height": round(rect.height, 2),
            "total_spans": len(spans_list),
            "total_blocks": len(blocks_list),
            "is_scanned": is_scanned,
            "image_count": len(page_images),
            "spans": spans_list,
            "blocks": blocks_list
        }
    finally:
        doc.close()

def apply_pdf_edits(input_path: str, output_path: str, operations: List[Dict[str, Any]]) -> str:
    """
    Apply comprehensive visual and structural editing operations to a PDF document:
    - Text replacements (genuine redaction + formatted replacement)
    - Text deletions (genuine stream redaction)
    - Add custom text / movable text boxes
    - Formatting: Font family (Standard 14 Base), size, bold, italic, underline, alignment
    - Add drawings / freehand annotations
    - Highlight / underline / strikethrough
    - Add shapes (rect, circle, line) with border and fill
    - Add images / signatures
    - Find and replace across page or document
    - Headers, footers, page numbering, and watermarks
    - Page manipulations: reorder, rotate, delete, duplicate, insert blank
    """
    doc = fitz.open(input_path)
    try:
        # Pre-process document-level structural operations first (reordering, page deletion, insertion)
        reorder_op = next((op for op in operations if op.get("type") == "reorder_pages"), None)
        if reorder_op:
            new_order = reorder_op.get("new_order", [])
            valid_order = [p for p in new_order if 0 <= p < len(doc)]
            if valid_order and len(valid_order) == len(doc):
                doc.select(valid_order)
                
        for op in operations:
            op_type = op.get("type")
            page_num = op.get("page", 0)
            
            # --- Page Manipulations ---
            if op_type == "delete_page":
                p_del = op.get("page_index", page_num)
                if 0 <= p_del < len(doc) and len(doc) > 1:
                    doc.delete_page(p_del)
                continue
                
            if op_type == "duplicate_page":
                p_dup = op.get("page_index", page_num)
                if 0 <= p_dup < len(doc):
                    doc.insert_pdf(doc, from_page=p_dup, to_page=p_dup, start_at=p_dup + 1)
                continue
                
            if op_type == "insert_blank_page":
                p_idx = op.get("page_index", len(doc))
                w = float(op.get("width", 595.32)) # Standard A4
                h = float(op.get("height", 841.92))
                p_idx = max(0, min(p_idx, len(doc)))
                doc.new_page(p_idx, width=w, height=h)
                continue

            if op_type == "rotate_page":
                p_rot = op.get("page_index", page_num)
                angle = int(op.get("angle", 90))
                if 0 <= p_rot < len(doc):
                    current_rot = doc[p_rot].rotation
                    doc[p_rot].set_rotation((current_rot + angle) % 360)
                continue
                
            # Document-wide watermark operation
            if op_type == "add_watermark":
                wm_text = op.get("text", "CONFIDENTIAL")
                wm_color = hex_to_rgb(op.get("color", "#CCCCCC"))
                wm_opacity = float(op.get("opacity", 0.3))
                wm_fontsize = float(op.get("font_size", 42))
                wm_angle = float(op.get("angle", 45))
                
                for p in doc:
                    p_rect = p.rect
                    center_pt = fitz.Point(p_rect.width / 2, p_rect.height / 2)
                    # Insert diagonal watermark text centered with morph matrix
                    p.insert_text(
                        center_pt,
                        wm_text,
                        fontsize=wm_fontsize,
                        fontname="hebo",
                        color=wm_color,
                        morph=(center_pt, fitz.Matrix(wm_angle)),
                        fill_opacity=wm_opacity
                    )
                continue
                
            # Document-wide Header / Footer operation
            if op_type == "add_header_footer":
                hf_text = op.get("text", "")
                hf_pos = op.get("position", "footer_center")
                hf_size = float(op.get("font_size", 10))
                hf_color = hex_to_rgb(op.get("color", "#666666"))
                
                total_p = len(doc)
                for idx, p in enumerate(doc):
                    page_num_str = str(idx + 1)
                    formatted_text = hf_text.replace("{page}", page_num_str).replace("{total}", str(total_p))
                    p_w = p.rect.width
                    p_h = p.rect.height
                    
                    if hf_pos == "header_left":
                        pt = fitz.Point(40, 30)
                        align = fitz.TEXT_ALIGN_LEFT
                    elif hf_pos == "header_right":
                        pt = fitz.Point(p_w - 40, 30)
                        align = fitz.TEXT_ALIGN_RIGHT
                    elif hf_pos == "header_center":
                        pt = fitz.Point(p_w / 2, 30)
                        align = fitz.TEXT_ALIGN_CENTER
                    elif hf_pos == "footer_left":
                        pt = fitz.Point(40, p_h - 25)
                        align = fitz.TEXT_ALIGN_LEFT
                    elif hf_pos == "footer_right":
                        pt = fitz.Point(p_w - 40, p_h - 25)
                        align = fitz.TEXT_ALIGN_RIGHT
                    else:  # footer_center
                        pt = fitz.Point(p_w / 2, p_h - 25)
                        align = fitz.TEXT_ALIGN_CENTER
                        
                    # Calculate bounding box for textbox
                    box_rect = fitz.Rect(pt.x - 150, pt.y - 10, pt.x + 150, pt.y + 15)
                    p.insert_textbox(box_rect, formatted_text, fontsize=hf_size, fontname="helv", color=hf_color, align=align)
                continue

            # Check valid page number for page-specific operations
            if page_num < 0 or page_num >= len(doc):
                continue
                
            page = doc[page_num]
            
            # --- Text Replacement (Genuine Stream Redaction + Replacement) ---
            if op_type == "replace_text":
                bbox = op.get("bbox")  # [x0, y0, x1, y1]
                new_text = op.get("new_text", "")
                font_family = op.get("font_family", "Helvetica")
                is_bold = bool(op.get("bold", False))
                is_italic = bool(op.get("italic", False))
                is_underline = bool(op.get("underline", False))
                font_size = float(op.get("font_size", 12))
                color_hex = op.get("color", "#000000")
                rgb = hex_to_rgb(color_hex)
                bg_hex = op.get("bg_color", "#FFFFFF")
                bg_rgb = hex_to_rgb(bg_hex)
                align_code = map_alignment(op.get("align", "left"))
                
                # Resolve standard font code (e.g., 'hebo', 'times', 'cobi')
                font_code, _, _ = resolve_font_spec(font_family, is_bold, is_italic)
                
                # 1. Genuine Redaction: Permanently strip original text stream
                rect = fitz.Rect(bbox[0], bbox[1], bbox[2], bbox[3])
                annot = page.add_redact_annot(rect, fill=bg_rgb)
                page.apply_redactions()
                
                # 2. Insert new text if not empty
                if new_text:
                    needed_w = max(rect.width, len(new_text) * font_size * 0.85)
                    needed_h = max(rect.height, font_size * 2.5)
                    text_rect = fitz.Rect(rect.x0, rect.y0, rect.x0 + needed_w, rect.y0 + needed_h)
                    rc = page.insert_textbox(text_rect, new_text, fontsize=font_size, fontname=font_code, color=rgb, align=align_code)
                    if rc < 0:
                        # Fallback to direct text insertion if bounding box constrained
                        page.insert_text(fitz.Point(rect.x0, rect.y0 + font_size), new_text, fontsize=font_size, fontname=font_code, color=rgb)
                    
                    # 3. Underline rule if requested
                    if is_underline:
                        shape = page.new_shape()
                        u_y = rect.y0 + font_size + 1
                        u_w = min(rect.x0 + len(new_text) * font_size * 0.55, text_rect.x1)
                        shape.draw_line(fitz.Point(rect.x0, u_y), fitz.Point(u_w, u_y))
                        shape.finish(color=rgb, width=1.0)
                        shape.commit()
                        
            # --- Text Deletion (Genuine Stream Redaction) ---
            elif op_type == "delete_text":
                bbox = op.get("bbox")
                bg_hex = op.get("bg_color", "#FFFFFF")
                rect = fitz.Rect(bbox[0], bbox[1], bbox[2], bbox[3])
                page.add_redact_annot(rect, fill=hex_to_rgb(bg_hex))
                page.apply_redactions()

            # --- Movable / Resizable Rich Text Box ---
            elif op_type == "add_textbox":
                bbox = op.get("bbox", [50, 50, 250, 150])
                rect = fitz.Rect(bbox[0], bbox[1], bbox[2], bbox[3])
                text = op.get("text", "")
                font_family = op.get("font_family", "Helvetica")
                is_bold = bool(op.get("bold", False))
                is_italic = bool(op.get("italic", False))
                is_underline = bool(op.get("underline", False))
                font_size = float(op.get("font_size", 14))
                color_hex = op.get("color", "#000000")
                rgb = hex_to_rgb(color_hex)
                align_code = map_alignment(op.get("align", "left"))
                
                font_code, _, _ = resolve_font_spec(font_family, is_bold, is_italic)
                
                # Draw background fill & border if specified
                bg_color_hex = op.get("bg_color")
                border_color_hex = op.get("border_color")
                border_width = float(op.get("border_width", 0))
                
                if bg_color_hex or (border_color_hex and border_width > 0):
                    shape = page.new_shape()
                    shape.draw_rect(rect)
                    fill_rgb = hex_to_rgb(bg_color_hex) if bg_color_hex else None
                    stroke_rgb = hex_to_rgb(border_color_hex) if (border_color_hex and border_width > 0) else None
                    shape.finish(color=stroke_rgb, fill=fill_rgb, width=border_width)
                    shape.commit()
                    
                # Insert text in box with margins
                inner_rect = fitz.Rect(rect.x0 + 4, rect.y0 + 4, max(rect.x1 - 4, rect.x0 + 4 + len(text) * font_size * 0.85), max(rect.y1 - 4, rect.y0 + 4 + font_size * 2.5))
                rc = page.insert_textbox(inner_rect, text, fontsize=font_size, fontname=font_code, color=rgb, align=align_code)
                if rc < 0:
                    page.insert_text(fitz.Point(inner_rect.x0, inner_rect.y0 + font_size), text, fontsize=font_size, fontname=font_code, color=rgb)
                
                if is_underline and text:
                    shape = page.new_shape()
                    u_y = rect.y0 + font_size + 5
                    shape.draw_line(fitz.Point(inner_rect.x0, u_y), fitz.Point(min(inner_rect.x1, inner_rect.x0 + len(text) * font_size * 0.55), u_y))
                    shape.finish(color=rgb, width=1.0)
                    shape.commit()

            # --- Simple Insert Text ---
            elif op_type == "add_text":
                x = float(op.get("x", 50))
                y = float(op.get("y", 50))
                text = op.get("text", "")
                font_family = op.get("font_family", "Helvetica")
                font_size = float(op.get("font_size", 14))
                is_bold = bool(op.get("bold", False))
                is_italic = bool(op.get("italic", False))
                color_hex = op.get("color", "#000000")
                rgb = hex_to_rgb(color_hex)
                font_code, _, _ = resolve_font_spec(font_family, is_bold, is_italic)
                
                page.insert_text(fitz.Point(x, y), text, fontsize=font_size, fontname=font_code, color=rgb)
                
            # --- Find & Replace ---
            elif op_type == "find_and_replace":
                find_txt = op.get("find_text", "").strip()
                replace_txt = op.get("replace_text", "")
                match_case = bool(op.get("match_case", False))
                font_size = float(op.get("font_size", 12))
                color_hex = op.get("color", "#000000")
                rgb = hex_to_rgb(color_hex)
                bg_hex = op.get("bg_color", "#FFFFFF")
                bg_rgb = hex_to_rgb(bg_hex)
                
                if find_txt:
                    rects = page.search_for(find_txt)
                    for r in rects:
                        annot = page.add_redact_annot(r, fill=bg_rgb)
                        page.apply_redactions()
                        if replace_txt:
                            page.insert_text(fitz.Point(r.x0, r.y1 - 2), replace_txt, fontsize=font_size, fontname="helv", color=rgb)

            # --- Freehand Drawing ---
            elif op_type == "add_drawing":
                points = op.get("points", [])
                stroke_color = hex_to_rgb(op.get("color", "#EF4444"))
                width = float(op.get("width", 2.0))
                
                if len(points) >= 2:
                    shape = page.new_shape()
                    p0 = fitz.Point(points[0]["x"], points[0]["y"])
                    for pt in points[1:]:
                        p1 = fitz.Point(pt["x"], pt["y"])
                        shape.draw_line(p0, p1)
                        p0 = p1
                    shape.finish(color=stroke_color, width=width)
                    shape.commit()
                    
            # --- Geometric Shapes ---
            elif op_type == "add_shape":
                shape_type = op.get("shape_type", "rect")
                bbox = op.get("bbox", [50, 50, 150, 150])
                rect = fitz.Rect(bbox[0], bbox[1], bbox[2], bbox[3])
                color = hex_to_rgb(op.get("stroke_color", "#2563EB"))
                width = float(op.get("stroke_width", 2.0))
                fill_color = hex_to_rgb(op.get("fill_color", "#FFFFFF")) if op.get("fill") else None
                
                shape = page.new_shape()
                if shape_type == "rect":
                    shape.draw_rect(rect)
                elif shape_type == "circle":
                    shape.draw_oval(rect)
                elif shape_type == "line":
                    shape.draw_line(fitz.Point(bbox[0], bbox[1]), fitz.Point(bbox[2], bbox[3]))
                    
                shape.finish(color=color, fill=fill_color, width=width)
                shape.commit()
                
            # --- Text Markup Annotations ---
            elif op_type in ("highlight", "underline", "strikeout"):
                bbox = op.get("bbox", [50, 50, 150, 65])
                rect = fitz.Rect(bbox[0], bbox[1], bbox[2], bbox[3])
                color = hex_to_rgb(op.get("color", "#FDE047" if op_type == "highlight" else "#EF4444"))
                
                if op_type == "highlight":
                    annot = page.add_highlight_annot(rect)
                elif op_type == "underline":
                    annot = page.add_underline_annot(rect)
                else:
                    annot = page.add_strikeout_annot(rect)
                annot.set_colors(stroke=color)
                annot.update()
                
            # --- Movable Image / Signature ---
            elif op_type in ("add_image", "add_signature"):
                img_b64 = op.get("image_base64", "")
                bbox = op.get("bbox", [50, 50, 150, 100])
                rect = fitz.Rect(bbox[0], bbox[1], bbox[2], bbox[3])
                
                if img_b64:
                    if "," in img_b64:
                        img_b64 = img_b64.split(",", 1)[1]
                    img_bytes = base64.b64decode(img_b64)
                    page.insert_image(rect, stream=img_bytes)
                    
        doc.save(output_path)
        return output_path
    finally:
        doc.close()
