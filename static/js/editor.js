/* ===================================================================
   DocuFlex — Professional Word-Like Visual PDF Editor Controller
   - PDF.js viewing, zoom, thumbnails, page navigation
   - Click & select existing PDF text with genuine stream redaction
   - Typography controls: font family, size, bold, italic, underline, alignment
   - Movable & resizable draggable text boxes
   - Annotations, shapes, drawings, digital signatures, images
   - Find and Replace tool
   - Headers, footers, page numbering, watermarks
   - Page operations: rotate, duplicate, delete, insert blank
   - Undo / Redo history stack
   - Scanned PDF OCR assist workflow
   - Word-like reflow mode (PDF -> DOCX -> fluid editing -> PDF)
   - Original vs Edited comparison inspector
   =================================================================== */

let pdfDoc = null;
let currentJobId = null;
let currentFilename = null;
let currentPageNum = 1;
let totalPages = 1;
let currentScale = 1.25;

// Active Tool & Typography State
let activeTool = "select"; // "select", "inspect_text", "textbox", "draw", "highlight", "shape_rect", "shape_circle", "signature", "image"
let activeFontFamily = "Helvetica";
let activeFontSize = 14;
let isBold = false;
let isItalic = false;
let isUnderline = false;
let activeAlign = "left";
let activeColor = "#000000";

// History Stacks (Undo / Redo)
let operations = [];
let undoneOperations = [];

// DOM References
let renderCanvas = null;
let renderCtx = null;
let annotCanvas = null;
let annotCtx = null;
let textSpanLayer = null;
let activeTextboxLayer = null;

// Drawing & Interaction State
let isDrawing = false;
let currentPoints = [];
let dragStart = null;
let pendingPlacementData = null; // signature or image awaiting canvas click
let selectedSpanForEdit = null;
let activeMovableBox = null;

// Signature Pad
let sigCanvas = null;
let sigCtx = null;
let isSigDrawing = false;

document.addEventListener("DOMContentLoaded", () => {
  renderCanvas = document.getElementById("pdf-render-canvas");
  renderCtx = renderCanvas ? renderCanvas.getContext("2d") : null;
  annotCanvas = document.getElementById("pdf-annotation-canvas");
  annotCtx = annotCanvas ? annotCanvas.getContext("2d") : null;
  textSpanLayer = document.getElementById("text-span-layer");
  activeTextboxLayer = document.getElementById("active-textbox-layer");

  initSignaturePad();
  setupToolbarControls();
  setupCanvasInteractions();
  initEditorDocument();
});

// ===================================================================
// 1. Initialize Document from URL or Upload Fallback
// ===================================================================
async function initEditorDocument() {
  const params = new URLSearchParams(window.location.search);
  currentJobId = params.get("job_id");
  currentFilename = params.get("filename");

  if (!currentJobId || !currentFilename) {
    showToast("Please select a PDF document to begin editing.", "info", 4000);
    const fallbackInput = document.getElementById("editor-pdf-fallback-input");
    fallbackInput.click();
    fallbackInput.onchange = async (e) => {
      if (e.target.files && e.target.files[0]) {
        await uploadEditorPdf(e.target.files[0]);
      }
    };
    return;
  }

  loadPdfDocument();
}

async function uploadEditorPdf(file) {
  const formData = new FormData();
  formData.append("file", file);
  showToast("Uploading document for editor...", "info", 3000);

  try {
    const res = await fetch("/api/upload", { method: "POST", body: formData });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Upload failed.");

    currentJobId = data.job_id;
    currentFilename = data.files[0].filename;
    window.history.replaceState({}, "", `/editor?job_id=${currentJobId}&filename=${encodeURIComponent(currentFilename)}`);
    loadPdfDocument();
  } catch (err) {
    showToast(err.message, "error", 5000);
  }
}

// ===================================================================
// 2. Load and Render PDF with PDF.js
// ===================================================================
async function loadPdfDocument() {
  const docTitleEl = document.getElementById("editor-filename");
  if (docTitleEl) docTitleEl.textContent = currentFilename;

  const url = `/api/pdf/raw/${currentJobId}/${encodeURIComponent(currentFilename)}`;
  showToast("Loading PDF document...", "info", 1500);

  try {
    const loadingTask = pdfjsLib.getDocument(url);
    pdfDoc = await loadingTask.promise;
    totalPages = pdfDoc.numPages;

    await renderPage(currentPageNum);
    generateThumbnails();
  } catch (err) {
    showToast("Failed to render PDF: " + err.message, "error", 6000);
  }
}

async function renderPage(num) {
  if (!pdfDoc) return;
  currentPageNum = Math.max(1, Math.min(num, totalPages));
  updatePageIndicator();

  const page = await pdfDoc.getPage(currentPageNum);
  const viewport = page.getViewport({ scale: currentScale });

  // Size base render canvas
  renderCanvas.width = viewport.width;
  renderCanvas.height = viewport.height;

  // Size annotation overlay canvas
  annotCanvas.width = viewport.width;
  annotCanvas.height = viewport.height;

  const container = document.getElementById("page-stage-container");
  container.style.width = `${viewport.width}px`;
  container.style.height = `${viewport.height}px`;

  // Render PDF.js page
  const renderContext = {
    canvasContext: renderCtx,
    viewport: viewport
  };
  await page.render(renderContext).promise;

  // Redraw any applied edits on the current page
  redrawAnnotations();

  // If text inspection mode is active, load spans
  if (activeTool === "inspect_text") {
    loadTextSpansForCurrentPage();
  } else {
    // Check if page is scanned in the background
    checkScannedStatus();
    clearTextSpanLayer();
  }
}

function updatePageIndicator() {
  const el = document.getElementById("page-indicator");
  if (el) el.textContent = `${currentPageNum} / ${totalPages}`;
}

// ===================================================================
// 3. Thumbnails Sidebar
// ===================================================================
async function generateThumbnails() {
  const sidebar = document.getElementById("editor-sidebar");
  if (!sidebar || !pdfDoc) return;
  sidebar.innerHTML = "";

  for (let i = 1; i <= totalPages; i++) {
    const page = await pdfDoc.getPage(i);
    const thumbViewport = page.getViewport({ scale: 0.22 });

    const card = document.createElement("div");
    card.className = `thumbnail-card ${i === currentPageNum ? "active" : ""}`;
    card.onclick = () => {
      document.querySelectorAll(".thumbnail-card").forEach(c => c.classList.remove("active"));
      card.classList.add("active");
      renderPage(i);
    };

    const canvas = document.createElement("canvas");
    canvas.className = "thumbnail-canvas";
    canvas.width = thumbViewport.width;
    canvas.height = thumbViewport.height;

    const ctx = canvas.getContext("2d");
    page.render({ canvasContext: ctx, viewport: thumbViewport });

    const label = document.createElement("div");
    label.className = "thumbnail-label";
    label.textContent = `Page ${i}`;

    card.appendChild(canvas);
    card.appendChild(label);
    sidebar.appendChild(card);
  }
}

// ===================================================================
// 4. Scanned Page Detection & OCR Assist
// ===================================================================
async function checkScannedStatus() {
  try {
    const res = await fetch("/api/pdf/spans", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        job_id: currentJobId,
        page: currentPageNum - 1,
        filename: currentFilename
      })
    });
    const data = await res.json();
    const banner = document.getElementById("scanned-doc-banner");
    if (data.success && data.data.is_scanned) {
      if (banner) banner.style.display = "flex";
    } else {
      if (banner) banner.style.display = "none";
    }
  } catch (err) {
    // Ignore silent check error
  }
}

document.getElementById("btn-trigger-ocr-assist")?.addEventListener("click", async () => {
  showToast("Running local offline OCR to enable text editing...", "info", 5000);
  try {
    const res = await fetch("/api/pdf/ocr_assist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_id: currentJobId, filename: currentFilename })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "OCR assist failed.");

    currentFilename = data.filename;
    showToast(data.message, "success", 4000);
    document.getElementById("scanned-doc-banner").style.display = "none";
    // Reload document with newly created OCR text layer
    loadPdfDocument();
  } catch (err) {
    showToast("OCR Assist failed: " + err.message, "error", 6000);
  }
});

// ===================================================================
// 5. Direct Existing Text Inspection & In-Place Editing
// ===================================================================
async function loadTextSpansForCurrentPage() {
  clearTextSpanLayer();
  showToast("Inspecting text spans across page...", "info", 1500);

  try {
    const res = await fetch("/api/pdf/spans", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        job_id: currentJobId,
        page: currentPageNum - 1,
        filename: currentFilename
      })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Failed to extract spans.");

    const pageData = data.data;
    const banner = document.getElementById("scanned-doc-banner");
    if (pageData.is_scanned) {
      if (banner) banner.style.display = "flex";
    } else {
      if (banner) banner.style.display = "none";
    }

    const page = await pdfDoc.getPage(currentPageNum);
    const viewport = page.getViewport({ scale: currentScale });

    const pdfW = pageData.width;
    const pdfH = pageData.height;
    const scaleX = viewport.width / pdfW;
    const scaleY = viewport.height / pdfH;

    pageData.spans.forEach(span => {
      const bbox = span.bbox; // [x0, y0, x1, y1]
      const el = document.createElement("div");
      el.className = "interactive-span";
      el.style.left = `${bbox[0] * scaleX}px`;
      el.style.top = `${bbox[1] * scaleY}px`;
      el.style.width = `${Math.max(10, (bbox[2] - bbox[0]) * scaleX)}px`;
      el.style.height = `${Math.max(10, (bbox[3] - bbox[1]) * scaleY)}px`;

      const fontNotice = span.is_fallback ? ` (Fallback to ${span.standard_font})` : "";
      el.title = `Click to edit: "${span.text}"\nFont: ${span.font}${fontNotice}, ${span.size}pt`;

      el.onclick = (e) => {
        e.stopPropagation();
        openTextReplaceModal(span, bbox);
      };

      textSpanLayer.appendChild(el);
    });

    showToast(`Found ${pageData.total_spans} editable text spans. Click any text to modify or redact!`, "success", 3000);
  } catch (err) {
    showToast(err.message, "error", 4000);
  }
}

function clearTextSpanLayer() {
  if (textSpanLayer) textSpanLayer.innerHTML = "";
}

function openTextReplaceModal(span, bbox) {
  selectedSpanForEdit = { span, bbox };
  
  document.getElementById("replace-original-preview").textContent = span.text;
  document.getElementById("replace-new-input").value = span.text;
  document.getElementById("replace-fontsize-input").value = span.size || 12;
  document.getElementById("replace-color-input").value = span.color || "#000000";
  document.getElementById("replace-bg-input").value = "#FFFFFF";

  // Match typography
  const fontSelect = document.getElementById("modal-replace-font");
  if (fontSelect) fontSelect.value = span.standard_font || "Helvetica";
  
  const detectedLabel = document.getElementById("replace-font-detected");
  if (detectedLabel) {
    detectedLabel.textContent = `Original font: ${span.font} ${span.size}pt | Standard mapping: ${span.standard_font}`;
  }

  document.getElementById("modal-replace-bold").checked = !!span.bold;
  document.getElementById("modal-replace-italic").checked = !!span.italic;
  document.getElementById("modal-replace-underline").checked = false;
  document.getElementById("modal-replace-align").value = "left";

  openModal("text-replace-modal");
}

// Confirm Text Replacement
document.getElementById("btn-confirm-replace")?.addEventListener("click", () => {
  if (!selectedSpanForEdit) return;

  const newText = document.getElementById("replace-new-input").value;
  const fFamily = document.getElementById("modal-replace-font").value;
  const fSize = parseFloat(document.getElementById("replace-fontsize-input").value) || 12;
  const col = document.getElementById("replace-color-input").value;
  const bgCol = document.getElementById("replace-bg-input").value;
  const align = document.getElementById("modal-replace-align").value;
  const b = document.getElementById("modal-replace-bold").checked;
  const it = document.getElementById("modal-replace-italic").checked;
  const u = document.getElementById("modal-replace-underline").checked;

  const op = {
    type: "replace_text",
    page: currentPageNum - 1,
    bbox: selectedSpanForEdit.bbox,
    original_text: selectedSpanForEdit.span.text,
    new_text: newText,
    font_family: fFamily,
    font_size: fSize,
    bold: b,
    italic: it,
    underline: u,
    align: align,
    color: col,
    bg_color: bgCol
  };

  recordOperation(op);
  closeModal("text-replace-modal");
  redrawAnnotations();
  showToast("Text replacement queued with genuine redaction!", "success", 2500);
});

// Delete Text Span Permanently
document.getElementById("btn-delete-text-span")?.addEventListener("click", () => {
  if (!selectedSpanForEdit) return;

  const bgCol = document.getElementById("replace-bg-input").value;
  const op = {
    type: "delete_text",
    page: currentPageNum - 1,
    bbox: selectedSpanForEdit.bbox,
    original_text: selectedSpanForEdit.span.text,
    bg_color: bgCol
  };

  recordOperation(op);
  closeModal("text-replace-modal");
  redrawAnnotations();
  showToast("Text permanently redacted and removed!", "success", 2500);
});

// ===================================================================
// 6. Word-Like Movable & Resizable Text Boxes
// ===================================================================
function createMovableTextBox(x, y, initialText = "Type your text here...") {
  if (!activeTextboxLayer) return;

  const pageIdx = currentPageNum - 1;
  const boxW = 200;
  const boxH = 70;

  const boxEl = document.createElement("div");
  boxEl.className = "movable-textbox active";
  boxEl.style.left = `${x}px`;
  boxEl.style.top = `${y}px`;
  boxEl.style.width = `${boxW}px`;
  boxEl.style.height = `${boxH}px`;

  const contentEl = document.createElement("div");
  contentEl.className = "textbox-inner-content";
  contentEl.contentEditable = "true";
  contentEl.textContent = initialText;
  contentEl.style.fontFamily = activeFontFamily;
  contentEl.style.fontSize = `${activeFontSize}px`;
  contentEl.style.color = activeColor;
  contentEl.style.fontWeight = isBold ? "800" : "normal";
  contentEl.style.fontStyle = isItalic ? "italic" : "normal";
  contentEl.style.textDecoration = isUnderline ? "underline" : "none";
  contentEl.style.textAlign = activeAlign;

  const resizeHandle = document.createElement("div");
  resizeHandle.className = "textbox-resize-handle";

  boxEl.appendChild(contentEl);
  boxEl.appendChild(resizeHandle);
  activeTextboxLayer.appendChild(boxEl);

  setTimeout(() => contentEl.focus(), 50);

  // Dragging logic
  let isMoving = false;
  let startX, startY, origLeft, origTop;

  boxEl.addEventListener("mousedown", (e) => {
    if (e.target === resizeHandle || e.target === contentEl) return;
    isMoving = true;
    startX = e.clientX;
    startY = e.clientY;
    origLeft = boxEl.offsetLeft;
    origTop = boxEl.offsetTop;
    e.stopPropagation();
  });

  // Resizing logic
  let isResizing = false;
  let rStartX, rStartY, origW, origH;

  resizeHandle.addEventListener("mousedown", (e) => {
    isResizing = true;
    rStartX = e.clientX;
    rStartY = e.clientY;
    origW = boxEl.offsetWidth;
    origH = boxEl.offsetHeight;
    e.stopPropagation();
  });

  window.addEventListener("mousemove", (e) => {
    if (isMoving) {
      boxEl.style.left = `${origLeft + (e.clientX - startX)}px`;
      boxEl.style.top = `${origTop + (e.clientY - startY)}px`;
    } else if (isResizing) {
      boxEl.style.width = `${Math.max(60, origW + (e.clientX - rStartX))}px`;
      boxEl.style.height = `${Math.max(30, origH + (e.clientY - rStartY))}px`;
    }
  });

  window.addEventListener("mouseup", () => {
    if (isMoving || isResizing) {
      isMoving = false;
      isResizing = false;
    }
  });

  // Save operation when user finishes editing box
  contentEl.addEventListener("blur", () => {
    const textVal = contentEl.textContent.trim();
    if (textVal) {
      const scale = currentScale;
      const pdfX0 = boxEl.offsetLeft / scale;
      const pdfY0 = boxEl.offsetTop / scale;
      const pdfX1 = (boxEl.offsetLeft + boxEl.offsetWidth) / scale;
      const pdfY1 = (boxEl.offsetTop + boxEl.offsetHeight) / scale;

      const op = {
        type: "add_textbox",
        page: pageIdx,
        bbox: [roundNum(pdfX0), roundNum(pdfY0), roundNum(pdfX1), roundNum(pdfY1)],
        text: textVal,
        font_family: activeFontFamily,
        font_size: activeFontSize,
        bold: isBold,
        italic: isItalic,
        underline: isUnderline,
        align: activeAlign,
        color: activeColor,
        bg_color: null,
        border_color: null,
        border_width: 0
      };
      recordOperation(op);
      showToast("Text box added to document!", "success", 2000);
      boxEl.remove();
      redrawAnnotations();
    } else {
      boxEl.remove();
    }
  });
}

// ===================================================================
// 7. Toolbar Controls & Typography Bar Synchronization
// ===================================================================
function setupToolbarControls() {
  // Tool selector buttons
  document.querySelectorAll(".editor-toolbar .tool-btn[data-tool]").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".editor-toolbar .tool-btn[data-tool]").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      activeTool = btn.getAttribute("data-tool");

      if (activeTool === "inspect_text") {
        loadTextSpansForCurrentPage();
      } else {
        clearTextSpanLayer();
      }

      if (activeTool === "signature") {
        openModal("signature-modal");
      } else if (activeTool === "image") {
        document.getElementById("editor-image-input")?.click();
      }
    });
  });

  // Font family selector
  const fontFamSelect = document.getElementById("editor-font-family");
  if (fontFamSelect) {
    fontFamSelect.addEventListener("change", (e) => {
      activeFontFamily = e.target.value;
    });
  }

  // Font size selector
  const fontSizeSelect = document.getElementById("editor-font-size");
  if (fontSizeSelect) {
    fontSizeSelect.addEventListener("change", (e) => {
      activeFontSize = parseFloat(e.target.value) || 14;
    });
  }

  // Typography toggles: Bold, Italic, Underline
  const boldBtn = document.getElementById("btn-toggle-bold");
  if (boldBtn) {
    boldBtn.addEventListener("click", () => {
      isBold = !isBold;
      boldBtn.classList.toggle("active", isBold);
    });
  }

  const italicBtn = document.getElementById("btn-toggle-italic");
  if (italicBtn) {
    italicBtn.addEventListener("click", () => {
      isItalic = !isItalic;
      italicBtn.classList.toggle("active", isItalic);
    });
  }

  const underlineBtn = document.getElementById("btn-toggle-underline");
  if (underlineBtn) {
    underlineBtn.addEventListener("click", () => {
      isUnderline = !isUnderline;
      underlineBtn.classList.toggle("active", isUnderline);
    });
  }

  // Alignment buttons
  const alignBtns = [
    { id: "btn-align-left", val: "left" },
    { id: "btn-align-center", val: "center" },
    { id: "btn-align-right", val: "right" }
  ];
  alignBtns.forEach(a => {
    const el = document.getElementById(a.id);
    if (el) {
      el.addEventListener("click", () => {
        alignBtns.forEach(b => document.getElementById(b.id)?.classList.remove("active"));
        el.classList.add("active");
        activeAlign = a.val;
      });
    }
  });

  // Color picker
  const colorInput = document.getElementById("editor-active-color");
  if (colorInput) {
    colorInput.addEventListener("input", (e) => {
      activeColor = e.target.value;
    });
  }

  // Page Navigator
  document.getElementById("btn-prev-page")?.addEventListener("click", () => {
    if (currentPageNum > 1) renderPage(currentPageNum - 1);
  });
  document.getElementById("btn-next-page")?.addEventListener("click", () => {
    if (currentPageNum < totalPages) renderPage(currentPageNum + 1);
  });

  // Zoom
  document.getElementById("btn-zoom-in")?.addEventListener("click", () => {
    currentScale = Math.min(3.0, currentScale + 0.25);
    updateZoomDisplay();
    renderPage(currentPageNum);
  });
  document.getElementById("btn-zoom-out")?.addEventListener("click", () => {
    currentScale = Math.max(0.5, currentScale - 0.25);
    updateZoomDisplay();
    renderPage(currentPageNum);
  });
  document.getElementById("btn-zoom-fit")?.addEventListener("click", () => {
    const vp = document.getElementById("editor-viewport");
    if (vp && renderCanvas) {
      currentScale = Math.max(0.5, (vp.clientWidth - 48) / (renderCanvas.width / currentScale));
      updateZoomDisplay();
      renderPage(currentPageNum);
    }
  });

  // Undo / Redo
  document.getElementById("btn-undo")?.addEventListener("click", undoOperation);
  document.getElementById("btn-redo")?.addEventListener("click", redoOperation);

  window.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "z") {
      e.preventDefault();
      undoOperation();
    } else if ((e.ctrlKey || e.metaKey) && e.key === "y") {
      e.preventDefault();
      redoOperation();
    }
  });

  // Page Operations
  document.getElementById("btn-rotate-page")?.addEventListener("click", () => {
    const op = { type: "rotate_page", page: currentPageNum - 1, page_index: currentPageNum - 1, angle: 90 };
    recordOperation(op);
    showToast("Page rotated +90°! Queued for save.", "success", 2000);
  });

  document.getElementById("btn-dup-page")?.addEventListener("click", () => {
    const op = { type: "duplicate_page", page: currentPageNum - 1, page_index: currentPageNum - 1 };
    recordOperation(op);
    totalPages++;
    updatePageIndicator();
    showToast("Page duplicated! Queued for save.", "success", 2000);
  });

  document.getElementById("btn-insert-blank-page")?.addEventListener("click", () => {
    const op = { type: "insert_blank_page", page_index: currentPageNum };
    recordOperation(op);
    totalPages++;
    updatePageIndicator();
    showToast("Blank page inserted! Queued for save.", "success", 2000);
  });

  document.getElementById("btn-delete-page")?.addEventListener("click", () => {
    if (totalPages <= 1) {
      showToast("Cannot delete the only page in document.", "warning", 3000);
      return;
    }
    const op = { type: "delete_page", page: currentPageNum - 1, page_index: currentPageNum - 1 };
    recordOperation(op);
    totalPages--;
    currentPageNum = Math.min(currentPageNum, totalPages);
    renderPage(currentPageNum);
    showToast("Page deletion queued for save.", "success", 2000);
  });

  // Modals Openers
  document.getElementById("btn-open-find-replace")?.addEventListener("click", () => openModal("find-replace-modal"));
  document.getElementById("btn-open-watermark")?.addEventListener("click", () => openModal("watermark-modal"));
  document.getElementById("btn-open-reflow")?.addEventListener("click", initWordReflowMode);
  document.getElementById("btn-open-compare")?.addEventListener("click", openCompareModal);

  // Save & Download
  document.getElementById("btn-save-pdf")?.addEventListener("click", saveAndDownloadEditedPdf);

  // Image Upload input
  const imgInput = document.getElementById("editor-image-input");
  if (imgInput) {
    imgInput.onchange = (e) => {
      if (e.target.files && e.target.files[0]) {
        const reader = new FileReader();
        reader.onload = (re) => {
          pendingPlacementData = { type: "image", base64: re.target.result };
          showToast("Click anywhere on the page to stamp your image.", "info", 4000);
        };
        reader.readAsDataURL(e.target.files[0]);
      }
    };
  }

  // Sidebar toggle
  document.getElementById("toggle-sidebar-btn")?.addEventListener("click", () => {
    document.getElementById("editor-sidebar")?.classList.toggle("collapsed");
  });
}

function updateZoomDisplay() {
  const el = document.getElementById("zoom-level");
  if (el) el.textContent = `${Math.round(currentScale * 100)}%`;
}

// ===================================================================
// 8. Canvas Interactions: Freehand Pen, Shapes, Text Box Placement
// ===================================================================
function setupCanvasInteractions() {
  if (!annotCanvas) return;

  annotCanvas.addEventListener("mousedown", onCanvasPointerDown);
  window.addEventListener("mousemove", onCanvasPointerMove);
  window.addEventListener("mouseup", onCanvasPointerUp);

  // Touch Support (iOS & Android)
  annotCanvas.addEventListener("touchstart", (e) => {
    if (e.touches.length > 0) {
      e.preventDefault();
      const t = e.touches[0];
      onCanvasPointerDown({ clientX: t.clientX, clientY: t.clientY });
    }
  }, { passive: false });

  window.addEventListener("touchmove", (e) => {
    if (isDrawing && e.touches.length > 0) {
      e.preventDefault();
      const t = e.touches[0];
      onCanvasPointerMove({ clientX: t.clientX, clientY: t.clientY });
    }
  }, { passive: false });

  window.addEventListener("touchend", () => {
    if (isDrawing) onCanvasPointerUp();
  });
}

function getCanvasCoords(e) {
  const rect = annotCanvas.getBoundingClientRect();
  return {
    x: e.clientX - rect.left,
    y: e.clientY - rect.top
  };
}

function onCanvasPointerDown(e) {
  const pt = getCanvasCoords(e);
  const scale = currentScale;
  const pageIdx = currentPageNum - 1;

  // Stamping Signature or Image
  if (pendingPlacementData) {
    const w = pendingPlacementData.type === "signature" ? 140 : 180;
    const h = pendingPlacementData.type === "signature" ? 60 : 120;
    const op = {
      type: pendingPlacementData.type === "signature" ? "add_signature" : "add_image",
      page: pageIdx,
      bbox: [roundNum(pt.x / scale), roundNum(pt.y / scale), roundNum((pt.x + w) / scale), roundNum((pt.y + h) / scale)],
      image_base64: pendingPlacementData.base64
    };
    recordOperation(op);
    pendingPlacementData = null;
    redrawAnnotations();
    showToast("Placed successfully!", "success", 2000);
    return;
  }

  // Text Box Placement
  if (activeTool === "textbox") {
    createMovableTextBox(pt.x, pt.y);
    return;
  }

  // Freehand Pen
  if (activeTool === "draw") {
    isDrawing = true;
    currentPoints = [{ x: pt.x / scale, y: pt.y / scale }];
    annotCtx.beginPath();
    annotCtx.moveTo(pt.x, pt.y);
    return;
  }

  // Shapes & Highlight drag start
  if (["highlight", "shape_rect", "shape_circle"].includes(activeTool)) {
    isDrawing = true;
    dragStart = { x: pt.x / scale, y: pt.y / scale };
    return;
  }
}

function onCanvasPointerMove(e) {
  if (!isDrawing) return;
  const pt = getCanvasCoords(e);
  const scale = currentScale;

  if (activeTool === "draw") {
    currentPoints.push({ x: pt.x / scale, y: pt.y / scale });
    annotCtx.strokeStyle = activeColor;
    annotCtx.lineWidth = 2.5 * scale;
    annotCtx.lineCap = "round";
    annotCtx.lineTo(pt.x, pt.y);
    annotCtx.stroke();
  } else if (dragStart) {
    redrawAnnotations();
    const x0 = Math.min(dragStart.x, pt.x / scale) * scale;
    const y0 = Math.min(dragStart.y, pt.y / scale) * scale;
    const w = Math.abs(pt.x / scale - dragStart.x) * scale;
    const h = Math.abs(pt.y / scale - dragStart.y) * scale;

    annotCtx.save();
    if (activeTool === "highlight") {
      annotCtx.fillStyle = "rgba(253, 224, 71, 0.4)";
      annotCtx.fillRect(x0, y0, w, h);
    } else if (activeTool === "shape_rect") {
      annotCtx.strokeStyle = activeColor;
      annotCtx.lineWidth = 2 * scale;
      annotCtx.strokeRect(x0, y0, w, h);
    } else if (activeTool === "shape_circle") {
      annotCtx.strokeStyle = activeColor;
      annotCtx.lineWidth = 2 * scale;
      annotCtx.beginPath();
      annotCtx.ellipse(x0 + w/2, y0 + h/2, w/2, h/2, 0, 0, Math.PI * 2);
      annotCtx.stroke();
    }
    annotCtx.restore();
  }
}

function onCanvasPointerUp() {
  if (!isDrawing) return;
  isDrawing = false;
  const scale = currentScale;
  const pageIdx = currentPageNum - 1;

  if (activeTool === "draw" && currentPoints.length >= 2) {
    const op = {
      type: "add_drawing",
      page: pageIdx,
      points: currentPoints,
      color: activeColor,
      width: 2.0
    };
    recordOperation(op);
  } else if (dragStart) {
    const endPt = currentPoints.length > 0 ? currentPoints[currentPoints.length - 1] : dragStart;
    const x0 = Math.min(dragStart.x, endPt.x);
    const y0 = Math.min(dragStart.y, endPt.y);
    const x1 = Math.max(dragStart.x, endPt.x);
    const y1 = Math.max(dragStart.y, endPt.y);

    if (Math.abs(x1 - x0) > 4 && Math.abs(y1 - y0) > 4) {
      if (activeTool === "highlight") {
        const op = { type: "highlight", page: pageIdx, bbox: [roundNum(x0), roundNum(y0), roundNum(x1), roundNum(y1)], color: "#FDE047" };
        recordOperation(op);
      } else if (activeTool === "shape_rect") {
        const op = { type: "add_shape", shape_type: "rect", page: pageIdx, bbox: [roundNum(x0), roundNum(y0), roundNum(x1), roundNum(y1)], stroke_color: activeColor, stroke_width: 2.0 };
        recordOperation(op);
      } else if (activeTool === "shape_circle") {
        const op = { type: "add_shape", shape_type: "circle", page: pageIdx, bbox: [roundNum(x0), roundNum(y0), roundNum(x1), roundNum(y1)], stroke_color: activeColor, stroke_width: 2.0 };
        recordOperation(op);
      }
    }
  }

  dragStart = null;
  currentPoints = [];
  redrawAnnotations();
}

// ===================================================================
// 9. Operations History & Redraw Overlay
// ===================================================================
function recordOperation(op) {
  operations.push(op);
  undoneOperations = []; // Clear redo stack on new action
  updateHistoryButtons();
}

function undoOperation() {
  if (operations.length === 0) return;
  const popped = operations.pop();
  undoneOperations.push(popped);
  updateHistoryButtons();
  redrawAnnotations();
  showToast(`Undid: ${popped.type.replace('_', ' ')}`, "info", 1500);
}

function redoOperation() {
  if (undoneOperations.length === 0) return;
  const restored = undoneOperations.pop();
  operations.push(restored);
  updateHistoryButtons();
  redrawAnnotations();
  showToast(`Redid: ${restored.type.replace('_', ' ')}`, "info", 1500);
}

function updateHistoryButtons() {
  const u = document.getElementById("btn-undo");
  const r = document.getElementById("btn-redo");
  if (u) u.disabled = operations.length === 0;
  if (r) r.disabled = undoneOperations.length === 0;
}

function redrawAnnotations() {
  if (!annotCtx || !annotCanvas) return;
  annotCtx.clearRect(0, 0, annotCanvas.width, annotCanvas.height);

  const pageIdx = currentPageNum - 1;
  const pageOps = operations.filter(op => op.page === pageIdx);

  pageOps.forEach(op => {
    annotCtx.save();

    if (op.type === "replace_text") {
      const [x0, y0, x1, y1] = op.bbox;
      annotCtx.fillStyle = op.bg_color || "#FFFFFF";
      annotCtx.fillRect(x0 * currentScale, y0 * currentScale, (x1 - x0) * currentScale, (y1 - y0) * currentScale);

      if (op.new_text) {
        annotCtx.fillStyle = op.color || "#000000";
        const fStyle = `${op.italic ? 'italic ' : ''}${op.bold ? '800 ' : ''}`;
        annotCtx.font = `${fStyle}${(op.font_size || 12) * currentScale}px ${op.font_family || 'Helvetica'}, sans-serif`;
        annotCtx.fillText(op.new_text, x0 * currentScale, (y1 - 2) * currentScale);

        if (op.underline) {
          annotCtx.strokeStyle = op.color || "#000000";
          annotCtx.lineWidth = 1 * currentScale;
          annotCtx.beginPath();
          annotCtx.moveTo(x0 * currentScale, (y1 + 1) * currentScale);
          annotCtx.lineTo((x0 + op.new_text.length * (op.font_size * 0.55)) * currentScale, (y1 + 1) * currentScale);
          annotCtx.stroke();
        }
      }
    } else if (op.type === "delete_text") {
      const [x0, y0, x1, y1] = op.bbox;
      annotCtx.fillStyle = op.bg_color || "#FFFFFF";
      annotCtx.fillRect(x0 * currentScale, y0 * currentScale, (x1 - x0) * currentScale, (y1 - y0) * currentScale);
    } else if (op.type === "add_textbox") {
      const [x0, y0, x1, y1] = op.bbox;
      annotCtx.fillStyle = op.color || "#000000";
      const fStyle = `${op.italic ? 'italic ' : ''}${op.bold ? '800 ' : ''}`;
      annotCtx.font = `${fStyle}${(op.font_size || 14) * currentScale}px ${op.font_family || 'Helvetica'}, sans-serif`;
      annotCtx.fillText(op.text, (x0 + 4) * currentScale, (y0 + (op.font_size * 1.1)) * currentScale);
    } else if (op.type === "add_drawing") {
      annotCtx.strokeStyle = op.color || "#EF4444";
      annotCtx.lineWidth = (op.width || 2) * currentScale;
      annotCtx.lineCap = "round";
      annotCtx.beginPath();
      op.points.forEach((pt, i) => {
        if (i === 0) annotCtx.moveTo(pt.x * currentScale, pt.y * currentScale);
        else annotCtx.lineTo(pt.x * currentScale, pt.y * currentScale);
      });
      annotCtx.stroke();
    } else if (op.type === "highlight") {
      const [x0, y0, x1, y1] = op.bbox;
      annotCtx.fillStyle = "rgba(253, 224, 71, 0.4)";
      annotCtx.fillRect(x0 * currentScale, y0 * currentScale, (x1 - x0) * currentScale, (y1 - y0) * currentScale);
    } else if (op.type === "add_shape") {
      const [x0, y0, x1, y1] = op.bbox;
      annotCtx.strokeStyle = op.stroke_color || "#EF4444";
      annotCtx.lineWidth = (op.stroke_width || 2) * currentScale;
      if (op.shape_type === "rect") {
        annotCtx.strokeRect(x0 * currentScale, y0 * currentScale, (x1 - x0) * currentScale, (y1 - y0) * currentScale);
      } else if (op.shape_type === "circle") {
        annotCtx.beginPath();
        const w = (x1 - x0) * currentScale;
        const h = (y1 - y0) * currentScale;
        annotCtx.ellipse((x0 * currentScale) + w/2, (y0 * currentScale) + h/2, w/2, h/2, 0, 0, Math.PI * 2);
        annotCtx.stroke();
      }
    } else if (op.type === "add_signature" || op.type === "add_image") {
      const [x0, y0, x1, y1] = op.bbox;
      const img = new Image();
      img.src = op.image_base64;
      annotCtx.drawImage(img, x0 * currentScale, y0 * currentScale, (x1 - x0) * currentScale, (y1 - y0) * currentScale);
    }

    annotCtx.restore();
  });
}

// ===================================================================
// 10. Find & Replace Handler
// ===================================================================
document.getElementById("btn-exec-find-replace")?.addEventListener("click", () => {
  const findTxt = document.getElementById("find-input").value.trim();
  const replTxt = document.getElementById("replace-input").value;
  const matchCase = document.getElementById("find-match-case").checked;

  if (!findTxt) {
    showToast("Please enter text to find.", "warning", 2500);
    return;
  }

  const op = {
    type: "find_and_replace",
    page: currentPageNum - 1,
    find_text: findTxt,
    replace_text: replTxt,
    match_case: matchCase,
    font_size: activeFontSize,
    color: activeColor,
    bg_color: "#FFFFFF"
  };

  recordOperation(op);
  closeModal("find-replace-modal");
  showToast(`Find & Replace scheduled for "${findTxt}"!`, "success", 3000);
});

// ===================================================================
// 11. Headers, Footers, Page Numbers & Watermark Handlers
// ===================================================================
function switchWatermarkTab(tab) {
  document.getElementById("tab-btn-watermark")?.classList.toggle("active", tab === "watermark");
  document.getElementById("tab-btn-headerfooter")?.classList.toggle("active", tab === "headerfooter");
  document.getElementById("section-watermark").style.display = tab === "watermark" ? "block" : "none";
  document.getElementById("section-headerfooter").style.display = tab === "headerfooter" ? "block" : "none";
}

document.getElementById("btn-apply-watermark")?.addEventListener("click", () => {
  const text = document.getElementById("wm-text-input").value.trim() || "CONFIDENTIAL";
  const opac = parseFloat(document.getElementById("wm-opacity-input").value) || 0.25;
  const col = document.getElementById("wm-color-input").value || "#999999";

  const op = {
    type: "add_watermark",
    text: text,
    opacity: opac,
    color: col,
    font_size: 42,
    angle: 45
  };
  recordOperation(op);
  closeModal("watermark-modal");
  showToast(`Watermark "${text}" queued for all pages!`, "success", 3000);
});

document.getElementById("btn-apply-headerfooter")?.addEventListener("click", () => {
  const text = document.getElementById("hf-text-input").value.trim() || "Page {page} of {total}";
  const pos = document.getElementById("hf-pos-select").value || "footer_center";
  const size = parseFloat(document.getElementById("hf-size-input").value) || 10;

  const op = {
    type: "add_header_footer",
    text: text,
    position: pos,
    font_size: size,
    color: "#666666"
  };
  recordOperation(op);
  closeModal("watermark-modal");
  showToast("Header / Footer numbering queued for all pages!", "success", 3000);
});

// ===================================================================
// 12. Word-Like Fluid Reflow Mode
// ===================================================================
async function initWordReflowMode() {
  openModal("word-reflow-modal");
  const listEl = document.getElementById("reflow-paragraphs-list");
  if (!listEl) return;
  listEl.innerHTML = `<div style="text-align:center;padding:30px;color:var(--text-muted);">Reconstructing document structure into editable paragraphs...</div>`;

  try {
    const res = await fetch("/api/pdf/reflow/init", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_id: currentJobId, filename: currentFilename })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Reflow initialization failed.");

    listEl.innerHTML = "";
    data.paragraphs.forEach((p, idx) => {
      const card = document.createElement("div");
      card.className = "reflow-p-card";
      card.innerHTML = `
        <div class="reflow-p-meta">
          <span>Paragraph ${idx + 1} • <strong style="color:var(--primary);">${p.style}</strong></span>
          <button class="btn btn-icon" style="color:var(--accent-rose);font-size:0.8rem;" onclick="this.closest('.reflow-p-card').remove()">Remove</button>
        </div>
        <textarea class="reflow-p-textarea" rows="2">${p.text}</textarea>
      `;
      listEl.appendChild(card);
    });

    showToast(`Extracted ${data.paragraph_count} fluid paragraphs for editing!`, "success", 3000);
  } catch (err) {
    listEl.innerHTML = `<div style="padding:20px;color:var(--accent-rose);text-align:center;">Failed: ${err.message}</div>`;
  }
}

document.getElementById("btn-reflow-add-p")?.addEventListener("click", () => {
  const listEl = document.getElementById("reflow-paragraphs-list");
  if (!listEl) return;
  const count = listEl.querySelectorAll(".reflow-p-card").length + 1;
  const card = document.createElement("div");
  card.className = "reflow-p-card";
  card.innerHTML = `
    <div class="reflow-p-meta">
      <span>Paragraph ${count} • <strong style="color:var(--primary);">Normal</strong></span>
      <button class="btn btn-icon" style="color:var(--accent-rose);font-size:0.8rem;" onclick="this.closest('.reflow-p-card').remove()">Remove</button>
    </div>
    <textarea class="reflow-p-textarea" rows="2" placeholder="Type new paragraph content..."></textarea>
  `;
  listEl.appendChild(card);
  card.querySelector("textarea").focus();
});

document.getElementById("btn-save-reflow")?.addEventListener("click", async () => {
  const listEl = document.getElementById("reflow-paragraphs-list");
  if (!listEl) return;
  const textareas = listEl.querySelectorAll(".reflow-p-textarea");
  const paragraphs = Array.from(textareas).map(ta => ({ text: ta.value.trim() })).filter(p => p.text);

  showToast("Recompiling document to reflowed PDF with native engine...", "info", 5000);
  try {
    const res = await fetch("/api/pdf/reflow/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_id: currentJobId, paragraphs: paragraphs, filename: currentFilename })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Save reflow failed.");

    showToast("Reflowed PDF recompiled successfully! Downloading...", "success", 3000);
    closeModal("word-reflow-modal");
    setTimeout(() => { window.location.href = data.download_url; }, 800);
  } catch (err) {
    showToast("Reflow recompile error: " + err.message, "error", 6000);
  }
});

// ===================================================================
// 13. Original vs Edited Comparison Inspector
// ===================================================================
async function openCompareModal() {
  openModal("compare-modal");
  document.querySelectorAll(".compare-current-page").forEach(el => el.textContent = currentPageNum);

  // Update audit log
  const opCountEl = document.getElementById("compare-op-count");
  const opListEl = document.getElementById("compare-op-list");
  if (opCountEl) opCountEl.textContent = operations.length;
  if (opListEl) {
    if (operations.length === 0) {
      opListEl.innerHTML = `<li>No edits recorded yet. Make changes to inspect differences.</li>`;
    } else {
      opListEl.innerHTML = operations.map((op, i) => `
        <li>
          <strong>#${i + 1} ${op.type.replace('_', ' ').toUpperCase()}</strong>: 
          ${op.original_text ? `"${op.original_text}" ➔ "${op.new_text || '[DELETED]'}"` : (op.text || JSON.stringify(op.bbox || {}))}
        </li>
      `).join("");
    }
  }

  // Render original
  const origCanvas = document.getElementById("compare-original-canvas");
  if (origCanvas && pdfDoc) {
    const origCtx = origCanvas.getContext("2d");
    const page = await pdfDoc.getPage(currentPageNum);
    const vp = page.getViewport({ scale: 0.8 });
    origCanvas.width = vp.width;
    origCanvas.height = vp.height;
    await page.render({ canvasContext: origCtx, viewport: vp }).promise;
  }

  // Render edited simulation
  const editedCanvas = document.getElementById("compare-edited-canvas");
  if (editedCanvas && renderCanvas) {
    const edCtx = editedCanvas.getContext("2d");
    editedCanvas.width = renderCanvas.width;
    editedCanvas.height = renderCanvas.height;
    // Draw base render
    edCtx.drawImage(renderCanvas, 0, 0);
    // Overlay annotations
    if (annotCanvas) edCtx.drawImage(annotCanvas, 0, 0);
  }
}

// ===================================================================
// 14. Signature Drawing Pad
// ===================================================================
function initSignaturePad() {
  sigCanvas = document.getElementById("signature-canvas");
  if (!sigCanvas) return;
  sigCtx = sigCanvas.getContext("2d");
  sigCtx.lineWidth = 2.5;
  sigCtx.lineCap = "round";
  sigCtx.strokeStyle = "#000000";

  sigCanvas.addEventListener("mousedown", (e) => {
    isSigDrawing = true;
    const r = sigCanvas.getBoundingClientRect();
    sigCtx.beginPath();
    sigCtx.moveTo(e.clientX - r.left, e.clientY - r.top);
  });
  sigCanvas.addEventListener("mousemove", (e) => {
    if (!isSigDrawing) return;
    const r = sigCanvas.getBoundingClientRect();
    sigCtx.lineTo(e.clientX - r.left, e.clientY - r.top);
    sigCtx.stroke();
  });
  window.addEventListener("mouseup", () => { isSigDrawing = false; });

  // Touch signature
  sigCanvas.addEventListener("touchstart", (e) => {
    if (e.touches.length > 0) {
      e.preventDefault();
      isSigDrawing = true;
      const r = sigCanvas.getBoundingClientRect();
      const t = e.touches[0];
      sigCtx.beginPath();
      sigCtx.moveTo(t.clientX - r.left, t.clientY - r.top);
    }
  }, { passive: false });
  sigCanvas.addEventListener("touchmove", (e) => {
    if (!isSigDrawing || e.touches.length === 0) return;
    e.preventDefault();
    const r = sigCanvas.getBoundingClientRect();
    const t = e.touches[0];
    sigCtx.lineTo(t.clientX - r.left, t.clientY - r.top);
    sigCtx.stroke();
  }, { passive: false });
  window.addEventListener("touchend", () => { isSigDrawing = false; });

  document.getElementById("btn-clear-sig")?.addEventListener("click", () => {
    sigCtx.clearRect(0, 0, sigCanvas.width, sigCanvas.height);
  });
  document.getElementById("btn-apply-sig")?.addEventListener("click", () => {
    const dataUrl = sigCanvas.toDataURL("image/png");
    pendingPlacementData = { type: "signature", base64: dataUrl };
    closeModal("signature-modal");
    showToast("Click anywhere on the document to stamp your signature.", "info", 4000);
  });
}

// ===================================================================
// 15. Save and Download Edited PDF
// ===================================================================
async function saveAndDownloadEditedPdf() {
  if (operations.length === 0) {
    showToast("No edits have been made yet.", "warning", 3000);
    return;
  }

  showToast("Applying genuine redactions & saving PDF...", "info", 3000);

  try {
    const res = await fetch("/api/pdf/edit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        job_id: currentJobId,
        filename: currentFilename,
        operations: operations
      })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Save failed.");

    showToast("PDF edits saved successfully! Downloading...", "success", 4000);
    setTimeout(() => {
      window.location.href = data.download_url;
    }, 600);
  } catch (err) {
    showToast(err.message, "error", 6000);
  }
}

// Utility: round number
function roundNum(n) {
  return Math.round(n * 100) / 100;
}
