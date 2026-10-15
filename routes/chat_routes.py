import re
from flask import Blueprint, request, jsonify
from utils.system_checker import get_system_capabilities

chat_bp = Blueprint("chat", __name__)

DOCUFLEX_KNOWLEDGE = [
    {
        "keywords": ["edit", "existing text", "replace text", "redaction", "change text", "modify text"],
        "title": "Editing Existing Text in PDF",
        "answer": (
            "### ✏️ How to Edit Existing PDF Text in iLovePDF\n\n"
            "iLovePDF features a high-fidelity **Existing Text Inspection & In-Place Replacement** engine:\n\n"
            "1. Open the **[PDF Editor](/editor)** and load your PDF document.\n"
            "2. Click the **'Edit Existing Text'** tool in the top toolbar (highlighted in cyan).\n"
            "3. iLovePDF will scan the page and highlight all detected text spans with dashed boxes.\n"
            "4. **Click on any text span** to open the editing dialog.\n"
            "5. You can view the original text, modify font size and color, and type the replacement text.\n"
            "6. Click **Apply Replacement**, then **Save & Download**.\n\n"
            "> **Privacy & Security Note:** iLovePDF uses true PDF stream redaction. The original text bytes are completely erased from the underlying document rather than merely hidden."
        )
    },
    {
        "keywords": ["word", "docx", "pdf to word", "convert to word"],
        "title": "Converting PDF to Microsoft Word (DOCX)",
        "answer": (
            "### 📘 Converting PDF to Word (.docx)\n\n"
            "iLovePDF uses `pdf2docx` to parse text blocks, tables, fonts, and layouts:\n\n"
            "1. Go to the **[Conversion Studio](/convert)** or Dashboard.\n"
            "2. Upload your PDF and select **PDF to Word**.\n"
            "3. The engine parses the visual structures and outputs an editable `.docx` file.\n"
            "4. The output can be opened in Microsoft Word, LibreOffice Writer, or Google Docs."
        )
    },
    {
        "keywords": ["word to pdf", "excel to pdf", "docx to pdf", "xlsx to pdf", "office to pdf", "libreoffice"],
        "title": "Converting Word & Excel to PDF",
        "answer": (
            "### 📄 Office to PDF Conversions\n\n"
            "iLovePDF supports a dual-engine architecture for converting `.docx` and `.xlsx` to `.pdf`:\n\n"
            "- **Native Microsoft Office Engine:** On Windows with Microsoft Office installed, iLovePDF leverages native Word/Excel automation via COM for 100% authentic layout fidelity.\n"
            "- **LibreOffice Engine:** If LibreOffice is installed, headless conversion mode is automatically utilized.\n\n"
            "Simply upload your `.docx` or `.xlsx` file in the **[Conversion Studio](/convert)** and select **Word & Excel to PDF**."
        )
    },
    {
        "keywords": ["powerpoint", "pptx", "pdf to pptx", "presentation", "slides"],
        "title": "Converting PDF to PowerPoint (PPTX)",
        "answer": (
            "### 📊 PDF to PowerPoint (.pptx)\n\n"
            "iLovePDF offers two conversion strategies:\n\n"
            "1. **Visual Mode:** Renders every PDF page as a sharp, high-resolution background slide image. Perfect for design-heavy documents, posters, and flyers.\n"
            "2. **Editable Mode:** Reconstructs text boxes, shapes, and positions onto individual presentation slides for editing in PowerPoint.\n\n"
            "You can choose your preferred mode when selecting the tool in the **[Conversion Studio](/convert)**."
        )
    },
    {
        "keywords": ["excel", "xlsx", "table", "tables", "pdf to excel", "word to excel", "spreadsheet"],
        "title": "Extracting Tabular Data to Excel",
        "answer": (
            "### 📗 PDF & Word Tables to Excel (.xlsx)\n\n"
            "iLovePDF provides two dedicated tabular extraction engines:\n\n"
            "1. **PDF to Excel:** Uses `pdfplumber` to detect line grids, cell boundaries, and table structures across pages, saving each table into dedicated worksheets with formatted header styling.\n"
            "2. **Word Tables to Excel:** Scans `.docx` documents for embedded tables and exports every table directly into formatted Excel sheets.\n\n"
            "Try it in the **[Conversion Studio](/convert)**."
        )
    },
    {
        "keywords": ["ocr", "scan", "scanned", "tesseract", "searchable", "image to text"],
        "title": "Offline Optical Character Recognition (OCR)",
        "answer": (
            "### 👁️ Offline OCR Studio\n\n"
            "iLovePDF includes a zero-cloud **[OCR Studio](/ocr)** with dual-engine capability:\n\n"
            "- **Built-in Neural OCR (`RapidOCR`):** Powered by an ONNX neural engine running completely locally in Python. Works out-of-the-box on scanned PDFs and images (PNG, JPG) without needing external binaries.\n"
            "- **Tesseract OCR:** Auto-detected if installed on the host system.\n\n"
            "**Two Operation Modes:**\n"
            "1. **Extract Plain Text:** Extracts all readable text and lets you copy or download a `.txt` file.\n"
            "2. **Create Searchable PDF:** Generates a PDF containing an invisible OCR text layer so you can search and copy text while preserving original visuals."
        )
    },
    {
        "keywords": ["merge", "combine", "join"],
        "title": "Merging Multiple PDFs",
        "answer": (
            "### 🔀 Merging PDF Documents\n\n"
            "1. Go to the **[Utilities Suite](/utilities)**.\n"
            "2. In the upload box, select or drop **two or more** PDF documents.\n"
            "3. Click **Merge PDFs**.\n"
            "4. iLovePDF combines the pages in lossless sequence and immediately prepares your download."
        )
    },
    {
        "keywords": ["split", "extract pages", "range"],
        "title": "Splitting and Extracting Pages",
        "answer": (
            "### ✂️ Split & Extract PDF Pages\n\n"
            "1. Select **Split & Extract Pages** in **[Utilities](/utilities)**.\n"
            "2. Specify your target page ranges using comma-separated numbers or hyphenated intervals.\n"
            "   - Example: `1-3, 5, 8-12`\n"
            "3. iLovePDF generates a new, lightweight PDF containing strictly your selected pages."
        )
    },
    {
        "keywords": ["compress", "reduce size", "shrink", "optimize"],
        "title": "Compressing PDF Documents",
        "answer": (
            "### 🗜️ Compressing PDF Documents\n\n"
            "iLovePDF optimizes PDFs locally using stream deflation, garbage collection (deduplicating objects), and smart image downsampling:\n\n"
            "- **Low:** Light compression, maximum visual fidelity.\n"
            "- **Balanced (Recommended):** ~100 DPI image resampling with clean streams. Ideal for email and web.\n"
            "- **High:** Aggressive size reduction down to 72 DPI images."
        )
    },
    {
        "keywords": ["protect", "password", "encrypt", "unlock", "security", "decrypt"],
        "title": "Password Protection & Decryption",
        "answer": (
            "### 🔒 PDF Security & Encryption\n\n"
            "- **Protect PDF:** Encrypts your document with 128-bit AES encryption. Sets an authorized user password required to view the document.\n"
            "- **Unlock PDF:** Removes password protection when you provide the valid document password, outputting an unrestricted copy."
        )
    },
    {
        "keywords": ["watermark", "page numbers", "stamp"],
        "title": "Watermarks & Page Numbers",
        "answer": (
            "### 💧 Watermarks & Page Numbering\n\n"
            "- **Watermark:** Overlays diagonal text across every page with custom text, opacity, and color.\n"
            "- **Page Numbers:** Adds formatted numbering (e.g. `Page {page} of {total}`) to your choice of location (Bottom Center, Bottom Right, Top Right, etc.)."
        )
    },
    {
        "keywords": ["signature", "sign", "draw"],
        "title": "Signatures & Drawing",
        "answer": (
            "### ✍️ Digital Signatures & Annotations\n\n"
            "Inside the **[PDF Editor](/editor)**:\n"
            "- Click **Signature** to open a smooth digital drawing pad. Draw your signature with mouse or touchscreen, click **Apply**, and click anywhere on the page to stamp it.\n"
            "- Click **Pen** to sketch freehand annotations in your choice of color and stroke width.\n"
            "- Click **Highlight** or **Rectangle/Circle** to emphasize sections."
        )
    },
    {
        "keywords": ["privacy", "offline", "security", "cloud", "api", "data"],
        "title": "Privacy & Security Guarantee",
        "answer": (
            "### 🛡️ 100% Local Privacy Guarantee\n\n"
            "iLovePDF processes all documents **entirely on your local computer**:\n\n"
            "- **Zero Cloud APIs:** Your files are never sent to external servers or third-party AI APIs.\n"
            "- **Isolated Temporary Storage:** Files are stored in temporary job folders and cleaned up automatically.\n"
            "- **Binary Signature Sniffing:** Every upload is validated by checking magic byte headers (`%PDF-`, `PK\x03\x04`, etc.) to block disguised malicious files."
        )
    }
]

def find_best_answer(query: str, caps: dict) -> str:
    q = query.lower().strip()
    
    # Check for system status question
    if any(k in q for k in ["status", "system", "health", "capability", "installed", "version"]):
        lo_status = caps.get("libreoffice", {}).get("engine", "Not Available")
        ocr_status = caps.get("tesseract", {}).get("engine", "iLovePDF Neural OCR")
        return (
            f"### ⚙️ iLovePDF System Status\n\n"
            f"- **Python Runtime:** Python {caps.get('python_version', '3.10')} (Local Virtual Environment)\n"
            f"- **Office Engine:** {lo_status}\n"
            f"- **OCR Engine:** {ocr_status}\n"
            f"- **Local PDF.js:** Bundled locally (Offline viewing active)\n"
            f"- **Security:** Local processing active, zero cloud uploads."
        )
        
    # Match against knowledge base
    scored_matches = []
    for item in DOCUFLEX_KNOWLEDGE:
        score = sum(1 for kw in item["keywords"] if re.search(r'\b' + re.escape(kw) + r'\b', q) or kw in q)
        if score > 0:
            scored_matches.append((score, item))
            
    if scored_matches:
        scored_matches.sort(key=lambda x: x[0], reverse=True)
        best = scored_matches[0][1]
        return best["answer"]
        
    # General overview response if no specific keyword matched
    return (
        "### 👋 Welcome to iLovePDF Assistant!\n\n"
        "I can answer any questions about iLovePDF features, conversions, and document editing:\n\n"
        "- **PDF Editor:** In-place existing text replacement, annotations, drawing, shapes, signatures, and page management.\n"
        "- **Conversions:** PDF to Word (DOCX), PowerPoint (PPTX), Excel (XLSX), Images (PNG/JPG), and Office to PDF.\n"
        "- **PDF Utilities:** Merge, split, rotate, compress, watermark, page numbers, and password encryption.\n"
        "- **Offline OCR:** Text extraction & Searchable PDF generation from scanned images and PDFs.\n\n"
        "💡 *Try asking: 'How do I edit existing text?', 'How does PDF to Word work?', or 'Can I run OCR offline?'*"
    )

@chat_bp.route("/api/chat", methods=["POST"])
@chat_bp.route("/api/chat/message", methods=["POST"])
def chat_endpoint():
    """Chatbot API for answering questions about the iLovePDF platform."""
    data = request.get_json() or {}
    message = (data.get("message") or "").strip()
    
    if not message:
        return jsonify({"error": "Empty message."}), 400
        
    caps = get_system_capabilities()
    reply_markdown = find_best_answer(message, caps)
    
    return jsonify({
        "success": True,
        "query": message,
        "reply": reply_markdown,
        "response": reply_markdown
    })
