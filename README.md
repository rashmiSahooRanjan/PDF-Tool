# iLovePDF Pro — All-in-One Local PDF Editor & Document Processing Platform

iLovePDF Pro is a high-performance, privacy-first document processing platform built with **Python 3.10**, **Flask**, **PyMuPDF**, and **vanilla HTML5/CSS3/JavaScript**. All processing occurs **100% locally** on your machine with **zero cloud dependencies** and **no paid APIs**.

---

## 🌟 Key Features

### 1. Professional Word-Like PDF Editor
- **PDF.js Canvas Viewport:** Fast, sharp document rendering with zoom (50%–300%), fit to width, page indicator, and interactive thumbnail sidebar navigation.
- **Direct Text Click & In-Place Editing:** Click any existing text block or span on the PDF page to modify its text, adjust font styling, or permanently delete it.
- **Genuine PDF Redaction:** Never covers text with deceptive white boxes; uses true PyMuPDF redaction annotations (`add_redact_annot()` and `apply_redactions()`) to purge original byte streams.
- **Word-Like Typography Controls:**
  - **Standard 14 Base PDF Fonts:** Helvetica (Sans), Times-Roman (Serif), and Courier (Monospace). Automatic fallback detection for custom fonts with honest user notifications.
  - **Font Size & Formatting:** Stepper from 8pt to 72pt, **Bold** (`B`), *Italic* (`I`), and <u>Underline</u> (`U`).
  - **Paragraph Alignment:** Left, Center, and Right alignment within bounded text regions.
  - **Color Picker:** Palette for text color and redaction background fills.
- **Draggable & Resizable Movable Text Boxes:** Insert rich text boxes anywhere on the page with boundary drag handles and live typing.
- **Find & Replace:** Search text across pages and perform single or batch replacements with genuine stream redactions.
- **Headers, Footers, Page Numbers & Watermarks:** Add running headers/footers with `{page}` and `{total}` tokens, or diagonal translucent watermarks.
- **Page Management:** Rotate pages (+90°), duplicate pages, insert blank pages, and delete pages.
- **Word Reflow Mode:** For text-heavy documents requiring paragraph reflow, converts PDF to DOCX using `pdf2docx`, provides fluid paragraph editing, and recompiles back to PDF via LibreOffice / MS Office COM.
- **OCR-Assisted Scanned PDF Editing:** Automatically detects image-only pages and provides one-click OCR to inject an editable/selectable text layer.
- **Original vs Edited Comparison:** Side-by-side visual diff inspector comparing original PDF against current modifications with an audit log of all applied edits.
- **Editing History (Undo / Redo):** Stack tracking all operations with `Ctrl+Z` and `Ctrl+Y` keyboard shortcuts.

### 2. Document Format Conversions
- **PDF to Word (.docx):** Powered by `pdf2docx`, reconstructing text blocks, tables, and formatting.
- **PDF to PowerPoint (.pptx):** Visual mode (high-res slide images) or Editable mode (text boxes & shape elements).
- **PDF to Excel (.xlsx):** Scans and extracts structured tabular data and cell grids with `pdfplumber` and `openpyxl`.
- **PDF to Images (.png, .jpg):** High-resolution page rendering (single pages or multi-page ZIP archives).
- **Images to PDF:** Combines multiple JPG and PNG images into a single consolidated PDF.
- **Word Tables to Excel (.docx to .xlsx):** Extracts all embedded tables in a Word document into formatted Excel worksheets.
- **Office to PDF (.docx, .xlsx to .pdf):** High-fidelity conversion via headless LibreOffice.

### 3. PDF Utilities Suite
- **Merge PDFs:** Combines multiple documents in chosen order.
- **Split & Extract:** Extracts specific page numbers or ranges (e.g. `1-3, 5, 8-10`).
- **Rotate Pages:** Clockwise rotation by 90°, 180°, or 270°.
- **Compress PDF:** Stream deflation, garbage collection, and image downsampling (Low, Balanced, High).
- **Watermark:** Customizable diagonal text watermarks with opacity and color control.
- **Page Numbers:** Formatted page numbering headers or footers (`Page {page} of {total}`).
- **Password Protection & Unlock:** Military-grade 128-bit AES encryption and decryption.

### 4. Offline OCR Studio
- **Text Extraction:** Extracts plain text from scanned PDFs or images via local Tesseract or built-in RapidOCR neural engine.
- **Searchable PDF:** Generates PDF with an invisible selectable OCR text layer.
- **Language Selection:** Auto-detects installed Tesseract language packs (`eng`, etc.).

### 5. Interactive iLovePDF Pro Assistant Chatbot
- **Intelligent Offline Guide:** Embedded floating AI assistant widget available on all pages.
- **Complete Project Explanations:** Explains every single tool, document conversion pipeline, visual editing redactions, OCR workflows, and security features.
- **Live System Status:** Informs users about active Python runtime, local engines (MS Office COM, LibreOffice, RapidOCR, Tesseract), and offline privacy.
- **Quick-Access Suggestion Chips:** Instant single-click prompts for common tasks and explanations.

### 6. 100% All-Device Mobile Responsiveness (Android & iPhone)
- **Universal Mobile Layout:** Optimized for small phone viewports (320px–480px), medium devices, tablets, and desktops.
- **Mobile Slide-in Navigation Drawer:** Touch-friendly hamburger menu with quick-access links.
- **iOS Safari & Android Chrome Optimization:** Viewport-fit cover, safe-area-insets, 16px input fonts (preventing iOS auto-zoom), and horizontal overflow lock.
- **Touch-Action Canvas Support:** Freehand annotation and signature drawing support native touch events (`touchstart`, `touchmove`, `touchend`) with `touch-action: none`.

---

## 📋 System Prerequisites

| Component | Status | Notes |
| :--- | :--- | :--- |
| **Python** | 3.10.x | Installed in local `venv` |
| **PyMuPDF / pypdf** | Installed | Core local PDF rendering, manipulation & editing |
| **pdf2docx / docx / pptx / openpyxl** | Installed | Document parsers & generators |
| **PDF.js** | Bundled | Bundled locally in `static/vendor/pdfjs/` for 100% offline viewing |
| **Tesseract OCR** | Optional | Required for OCR studio & searchable PDF generation |
| **LibreOffice / MS Office** | **Active** | Supports native Word/Excel engine or LibreOffice headless mode |

---

## 🚀 Quickstart: How to Run the Project

### 1. Open Windows PowerShell
Navigate to the project folder:
```powershell
cd "d:\PDF project"
```

### 2. Activate the Python 3.10 Virtual Environment
```powershell
.\venv\Scripts\Activate.ps1
```
*(If PowerShell restricts script execution, run: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`)*

### 3. Start the iLovePDF Pro Server
```powershell
python app.py
```
Or directly using the virtual environment's Python:
```powershell
.\venv\Scripts\python.exe app.py
```

### 4. Open in Your Browser
Visit:
```
http://127.0.0.1:5000
```

---

## 🛠️ Installing Optional System Tools

### 1. Tesseract OCR (For Offline OCR Studio)
1. Download the Windows installer from [UB-Mannheim Tesseract](https://github.com/UB-Mannheim/tesseract/wiki).
2. Install to the default directory: `C:\Program Files\Tesseract-OCR`.
3. iLovePDF Pro will automatically detect it. Alternatively, set an environment variable:
   ```powershell
   $env:TESSERACT_PATH = "C:\Program Files\Tesseract-OCR\tesseract.exe"
   ```

### 2. LibreOffice (For Office-to-PDF Conversions)
1. Download LibreOffice from [libreoffice.org](https://www.libreoffice.org/download/download/).
2. Install to the default path: `C:\Program Files\LibreOffice\program\soffice.exe`.
3. iLovePDF Pro automatically detects LibreOffice. Alternatively, set an environment variable:
   ```powershell
   $env:LIBREOFFICE_PATH = "C:\Program Files\LibreOffice\program\soffice.exe"
   ```

---

## 🧪 Running Automated Tests

All automated tests are written with `pytest` and verify conversions, security signatures, utilities, and editor text replacement on synthetic test documents:

```powershell
.\venv\Scripts\pytest.exe -v tests/test_docuflex.py
```

**Results:**
- **26 Passed / 26 Total (100% Pass Rate)**

---

## 📝 Word-Like PDF Editor Usage & Realistic Limitations

1. **Direct In-Place Editing vs Fixed Layout**:
   - Standard PDF files store text as fixed absolute-coordinate positioning operators (`TJ`/`Tj`). When replacing words, iLovePDF Pro automatically adjusts the line bounding box. If replacement text is significantly longer than original text, line-wrapping within the box will occur or text will overflow its original column.
2. **Word Reflow Mode**:
   - For contracts, books, and articles that require paragraph-level text reflowing across pages, click the **Word Reflow Mode** button. iLovePDF Pro will convert the PDF into an editable Word document structure (`.docx`), allow fluid editing of paragraphs, and recompile back to PDF via LibreOffice / MS Office.
3. **Genuine Stream Redaction**:
   - When text is deleted or replaced, iLovePDF Pro applies authentic PyMuPDF redaction annotations (`add_redact_annot()` and `apply_redactions()`). The original characters are permanently expunged from the binary stream.
4. **Standard 14 PDF Base Fonts & Fallbacks**:
   - PyMuPDF natively writes the standard PDF Base 14 fonts: **Helvetica**, **Times-Roman**, and **Courier** with full support for Bold, Italic, and Underline. If a document contains proprietary embedded fonts, iLovePDF Pro detects them and honestly informs the user that standard fallback rendering is utilized.
5. **Scanned PDF OCR Assist**:
   - If an opened page has no selectable text (scanned flat imagery), iLovePDF Pro shows an automatic banner allowing the user to run the offline OCR engine (`RapidOCR` / `Tesseract`) in one click, generating a searchable PDF with selectable and editable text.

## 📁 Project Architecture

```
d:/PDF project/
├── app.py                      # Flask application factory & server entry point
├── config.py                   # App configuration, limits & storage paths
├── requirements.txt            # Python 3.10 pinned dependencies
├── README.md                   # This master documentation
├── .gitignore                  # Git exclusions (venv, uploads, outputs, caches)
├── routes/
│   ├── main_routes.py          # Dashboard, health check, uploads & downloads
│   ├── editor_routes.py        # PDF raw stream, text spans & edit saver
│   ├── conversion_routes.py    # Document conversions (PDF/Office/Image)
│   ├── utility_routes.py       # Merge, split, compress, watermark, protect
│   └── ocr_routes.py           # OCR text extraction & searchable PDF
├── services/
│   ├── conversion_service.py   # Registry of document format handlers
│   ├── editor_service.py       # PyMuPDF-based text redaction, shapes, drawings
│   ├── utility_service.py      # PDF manipulation (merge, split, compress, protect)
│   ├── ocr_service.py          # Tesseract extraction & OCR layer integration
│   └── job_service.py          # Thread pool background job tracker
├── utils/
│   ├── file_manager.py         # Secure session folders & automatic TTL cleanup
│   ├── validators.py           # Magic-byte security validation & safe paths
│   └── system_checker.py       # Detection of LibreOffice & Tesseract
├── static/
│   ├── css/
│   │   ├── style.css           # Design system tokens, dual theme, micro-animations
│   │   └── editor.css          # PDF editor canvas, toolbar & modal styles
│   ├── js/
│   │   ├── app.js              # Uploads, modals, async polling & recent jobs
│   │   ├── editor.js           # PDF.js visual canvas controller & redactions
│   │   └── theme.js            # Light/Dark mode toggle & toast notifications
│   └── vendor/
│       └── pdfjs/              # Bundled local PDF.js (pdf.min.js, pdf.worker.min.js)
├── templates/
│   ├── base.html               # Master layout with navigation & toast shelf
│   ├── index.html              # Main dashboard with categorized tool cards
│   ├── editor.html             # PDF visual editor workspace
│   ├── convert.html            # Format conversion studio
│   ├── utilities.html          # PDF utilities suite
│   └── ocr.html                # Offline OCR Studio
├── tests/
│   ├── conftest.py             # Test fixtures & synthetic document generators
│   └── test_docuflex.py        # Automated test suite
├── uploads/                    # Upload storage
└── outputs/                    # Output generation storage
```

---

## 🔒 Security & Privacy Guarantees
- **Local Isolation:** Documents never leave your device.
- **Magic Signature Inspection:** Uploaded files undergo binary header inspection (`%PDF-`, `PK\x03\x04`, `PNG`, etc.) to prevent disguised malicious file execution.
- **Path Traversal Defense:** All paths are resolved and strictly confined within authorized workspace boundaries.
- **Non-Exposing Identifiers:** UUID4 job IDs prevent sequential document guessing or exposing server storage structures.
- **True Redaction:** Text editing eliminates original text character streams completely from the PDF byte stream rather than merely covering them.
