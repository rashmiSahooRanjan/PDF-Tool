/* ===================================================================
   DocuFlex — Dashboard & Main Application Logic
   Complete 33-Tool Local PDF Suite Handler
   =================================================================== */

let currentJobId = null;
let currentUploadedFiles = [];
let activeToolAction = null;

// Global state for interactive modals
let signPadInited = false;
let isDrawingSign = false;
let signCtx = null;
let cameraStream = null;
let scannedImages = [];
let lastSummaryResult = "";
let lastTranslationResult = "";
let lastMarkdownResult = "";

// 1. File Upload & Drag-and-Drop Initialization
document.addEventListener("DOMContentLoaded", () => {
  const dropzone = document.getElementById("main-dropzone");
  const fileInput = document.getElementById("file-input");

  if (dropzone && fileInput) {
    dropzone.addEventListener("click", (e) => {
      if (e.target.tagName !== "BUTTON" && !e.target.closest("button")) {
        fileInput.click();
      }
    });

    ["dragenter", "dragover"].forEach(eventName => {
      dropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.add("drag-over");
      });
    });

    ["dragleave", "drop"].forEach(eventName => {
      dropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.remove("drag-over");
      });
    });

    dropzone.addEventListener("drop", (e) => {
      const dt = e.dataTransfer;
      if (dt.files && dt.files.length > 0) {
        handleFiles(dt.files);
      }
    });

    fileInput.addEventListener("change", (e) => {
      if (e.target.files && e.target.files.length > 0) {
        handleFiles(e.target.files);
      }
    });
  }

  // Load Recent Jobs from Local Storage
  renderRecentJobs();

  // Category Filtering
  initCategoryTabs();

  // Auto-launch tool if URL query param present (e.g. from Mega Menu ?tool=...)
  const urlParams = new URLSearchParams(window.location.search);
  const toolParam = urlParams.get("tool");
  if (toolParam) {
    setTimeout(() => {
      selectTool(toolParam);
    }, 200);
  }
});

// 2. Handle Selected Files
async function handleFiles(fileList) {
  const formData = new FormData();
  for (let i = 0; i < fileList.length; i++) {
    formData.append("files", fileList[i]);
  }

  showToast(`Uploading ${fileList.length} document(s)...`, "info", 2000);

  try {
    const res = await fetch("/api/upload", {
      method: "POST",
      body: formData
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.error || "File upload failed.");
    }

    currentJobId = data.job_id;
    currentUploadedFiles = data.files;

    displayUploadedPreview(data.files, data.metadata);
    showToast("Document(s) successfully verified and ready!", "success", 3000);

    // If an action was preselected, execute its configured modal/runner
    if (activeToolAction) {
      const pendingTool = activeToolAction;
      activeToolAction = null;
      executeToolAction(pendingTool);
    }
  } catch (err) {
    showToast(err.message, "error", 5000);
  }
}

// 3. Display Uploaded Document Preview
function displayUploadedPreview(files, metadata) {
  const previewCard = document.getElementById("file-preview-card");
  if (!previewCard) return;

  const firstFile = files[0];
  const titleEl = document.getElementById("preview-file-title");
  const metaEl = document.getElementById("preview-file-meta");

  if (titleEl) {
    titleEl.textContent = files.length === 1 ? firstFile.filename : `${firstFile.filename} (+${files.length - 1} more)`;
  }

  if (metaEl) {
    let detailsStr = `${formatBytes(firstFile.size)} • ${firstFile.extension.toUpperCase()}`;
    if (metadata && metadata.page_count) {
      detailsStr += ` • ${metadata.page_count} Pages (${metadata.dimensions})`;
      if (metadata.is_encrypted) {
        detailsStr += ` • 🔒 Password Protected`;
      }
    }
    metaEl.textContent = detailsStr;
  }

  previewCard.style.display = "block";
}

function clearCurrentFile() {
  currentJobId = null;
  currentUploadedFiles = [];
  const previewCard = document.getElementById("file-preview-card");
  if (previewCard) previewCard.style.display = "none";
  const fileInput = document.getElementById("file-input");
  if (fileInput) fileInput.value = "";
  activeToolAction = null;
  showToast("File session cleared.", "info", 2000);
}

// 4. Trigger Tool Selection & Execution
function selectTool(toolKey) {
  activeToolAction = toolKey;

  // Tools that can initiate without pre-selected main file:
  if (toolKey === "scan-to-pdf") {
    openScanModal();
    return;
  }
  if (toolKey === "compare-pdf" && (!currentJobId || currentUploadedFiles.length === 0)) {
    openCompareModal();
    return;
  }

  // If no file uploaded yet, prompt user to select document
  if (!currentJobId || currentUploadedFiles.length === 0) {
    const fileInput = document.getElementById("file-input");
    if (fileInput) {
      showToast("Please select your document first to continue.", "info", 3000);
      fileInput.click();
    }
    return;
  }

  executeToolAction(toolKey);
}

function executeToolAction(toolKey) {
  const firstFile = currentUploadedFiles[0];
  const ext = firstFile ? firstFile.extension.toLowerCase() : "";

  switch (toolKey) {
    // === 1. ORGANIZE PDF ===
    case "merge-pdf":
      if (currentUploadedFiles.length < 2) {
        showToast("Merge requires 2 or more PDF files. Please select additional files.", "warning", 3500);
        document.getElementById("file-input").click();
        return;
      }
      startMerge();
      break;

    case "split-pdf":
    case "extract-pages":
      openModal("split-options-modal");
      break;

    case "remove-pages":
      openModal("remove-pages-modal");
      break;

    case "organize-pdf":
      if (ext !== "pdf") {
        showToast("Organize tool requires a PDF document.", "warning");
        return;
      }
      window.location.href = `/editor?job_id=${currentJobId}&filename=${encodeURIComponent(firstFile.filename)}&mode=organize`;
      break;

    case "scan-to-pdf":
      openScanModal();
      break;

    // === 2. OPTIMIZE PDF ===
    case "compress-pdf":
      openModal("compress-options-modal");
      break;

    case "repair-pdf":
      openModal("repair-options-modal");
      break;

    case "ocr-pdf":
    case "ocr-extract":
      window.location.href = `/ocr?job_id=${currentJobId}&filename=${encodeURIComponent(firstFile.filename)}`;
      break;

    // === 3. CONVERT TO PDF ===
    case "jpg-to-pdf":
    case "images-to-pdf":
    case "word-to-pdf":
    case "docx-to-pdf":
    case "pptx-to-pdf":
    case "excel-to-pdf":
    case "xlsx-to-pdf":
    case "html-to-pdf":
      startConversion("pdf");
      break;

    // === 4. CONVERT FROM PDF ===
    case "pdf-to-jpg":
      startConversion("jpg");
      break;

    case "pdf-to-png":
      startConversion("png");
      break;

    case "pdf-to-word":
      startConversion("docx");
      break;

    case "pdf-to-pptx":
      openModal("pptx-options-modal");
      break;

    case "pdf-to-excel":
      startConversion("xlsx");
      break;

    case "pdf-to-pdfa":
      startConversion("pdfa");
      break;

    // === 5. EDIT PDF ===
    case "rotate-pdf":
      openModal("rotate-options-modal");
      break;

    case "page-numbers":
      openModal("pagenum-options-modal");
      break;

    case "watermark-pdf":
      openModal("watermark-options-modal");
      break;

    case "crop-pdf":
      openModal("crop-options-modal");
      break;

    case "edit-pdf":
      if (ext !== "pdf") {
        showToast("PDF Visual Editor requires a PDF document.", "warning");
        return;
      }
      window.location.href = `/editor?job_id=${currentJobId}&filename=${encodeURIComponent(firstFile.filename)}`;
      break;

    case "pdf-forms":
      openFormsModal();
      break;

    // === 6. PDF SECURITY ===
    case "unlock-pdf":
      openModal("unlock-options-modal");
      break;

    case "protect-pdf":
      openModal("protect-options-modal");
      break;

    case "sign-pdf":
      openSignModal();
      break;

    case "redact-pdf":
      openModal("redact-options-modal");
      break;

    case "compare-pdf":
      openCompareModal();
      break;

    // === 7. PDF INTELLIGENCE ===
    case "ai-summarizer":
      openSummarizeModal();
      break;

    case "translate-pdf":
      openTranslateModal();
      break;

    case "pdf-to-markdown":
      openMarkdownModal();
      break;

    default:
      showToast(`Launching ${toolKey}...`, "info", 2000);
  }
}

// 5. Asynchronous Conversion Runner
async function startConversion(targetFormat, options = {}) {
  closeAllModals();
  openJobProgressModal(`Converting Document to ${targetFormat.toUpperCase()}...`);

  try {
    const res = await fetch("/api/convert", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        job_id: currentJobId,
        target_format: targetFormat,
        options: options
      })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Failed to start conversion.");

    // Start polling job status
    pollJobStatus(currentJobId);
  } catch (err) {
    updateJobError(err.message);
  }
}

// 6. Utility Execution Handlers
async function startMerge() {
  closeAllModals();
  openJobProgressModal("Merging PDF Documents...");
  try {
    const res = await fetch("/api/pdf/merge", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_id: currentJobId })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Merge failed.");
    pollJobStatus(currentJobId);
  } catch (err) {
    updateJobError(err.message);
  }
}

async function submitSplit() {
  const range = document.getElementById("split-range-input").value || "1";
  closeAllModals();
  openJobProgressModal("Extracting Pages...");

  try {
    const res = await fetch("/api/pdf/split", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        job_id: currentJobId,
        page_ranges: range
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Split failed.");
    pollJobStatus(currentJobId);
  } catch (err) {
    updateJobError(err.message);
  }
}

async function submitRemovePages() {
  const pages = document.getElementById("remove-pages-input").value || "1";
  closeAllModals();
  openJobProgressModal("Removing Pages...");

  try {
    const res = await fetch("/api/pdf/remove_pages", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        job_id: currentJobId,
        pages_to_remove: pages
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Failed to remove pages.");
    pollJobStatus(currentJobId);
  } catch (err) {
    updateJobError(err.message);
  }
}

async function submitRotate() {
  const angle = document.getElementById("rotate-angle-select").value || 90;
  closeAllModals();
  openJobProgressModal("Rotating Document...");

  try {
    const res = await fetch("/api/pdf/rotate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        job_id: currentJobId,
        rotation: parseInt(angle)
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Rotate failed.");
    pollJobStatus(currentJobId);
  } catch (err) {
    updateJobError(err.message);
  }
}

async function submitCompress() {
  const level = document.getElementById("compress-level-select").value || "medium";
  closeAllModals();
  openJobProgressModal("Compressing PDF...");

  try {
    const res = await fetch("/api/pdf/compress", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        job_id: currentJobId,
        level: level
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Compression failed.");
    pollJobStatus(currentJobId);
  } catch (err) {
    updateJobError(err.message);
  }
}

async function submitWatermark() {
  const text = document.getElementById("watermark-text-input").value || "CONFIDENTIAL";
  const opacity = document.getElementById("watermark-opacity-input").value || 0.25;
  const color = document.getElementById("watermark-color-input").value || "#94A3B8";
  closeAllModals();
  openJobProgressModal("Applying Watermark...");

  try {
    const res = await fetch("/api/pdf/watermark", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        job_id: currentJobId,
        text: text,
        opacity: parseFloat(opacity),
        color: color
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Watermark failed.");
    pollJobStatus(currentJobId);
  } catch (err) {
    updateJobError(err.message);
  }
}

async function submitPageNumbers() {
  const formatStr = document.getElementById("pagenum-format-select").value || "Page {page} of {total}";
  const position = document.getElementById("pagenum-position-select").value || "bottom-center";
  closeAllModals();
  openJobProgressModal("Adding Page Numbers...");

  try {
    const res = await fetch("/api/pdf/page-numbers", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        job_id: currentJobId,
        format: formatStr,
        position: position
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Failed to add page numbers.");
    pollJobStatus(currentJobId);
  } catch (err) {
    updateJobError(err.message);
  }
}

async function submitCrop() {
  const top = parseFloat(document.getElementById("crop-top-input").value) || 0;
  const bottom = parseFloat(document.getElementById("crop-bottom-input").value) || 0;
  const left = parseFloat(document.getElementById("crop-left-input").value) || 0;
  const right = parseFloat(document.getElementById("crop-right-input").value) || 0;
  closeAllModals();
  openJobProgressModal("Cropping Margins...");

  try {
    const res = await fetch("/api/pdf/crop", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        job_id: currentJobId,
        margins: { top, bottom, left, right }
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Crop failed.");
    pollJobStatus(currentJobId);
  } catch (err) {
    updateJobError(err.message);
  }
}

async function submitRepair() {
  closeAllModals();
  openJobProgressModal("Repairing PDF Streams & XREF...");

  try {
    const res = await fetch("/api/pdf/repair", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_id: currentJobId })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Repair failed.");
    pollJobStatus(currentJobId);
  } catch (err) {
    updateJobError(err.message);
  }
}

async function submitProtect() {
  const pw = document.getElementById("protect-password-input").value;
  if (!pw) {
    showToast("Password cannot be empty.", "warning");
    return;
  }
  closeAllModals();
  openJobProgressModal("Encrypting PDF...");

  try {
    const res = await fetch("/api/pdf/protect", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        job_id: currentJobId,
        password: pw
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Encryption failed.");
    pollJobStatus(currentJobId);
  } catch (err) {
    updateJobError(err.message);
  }
}

async function submitUnlock() {
  const pw = document.getElementById("unlock-password-input").value;
  closeAllModals();
  openJobProgressModal("Decrypting PDF...");

  try {
    const res = await fetch("/api/pdf/unlock", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        job_id: currentJobId,
        password: pw
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Decryption failed.");
    pollJobStatus(currentJobId);
  } catch (err) {
    updateJobError(err.message);
  }
}

// 7. Sign PDF Canvas & Submission
function openSignModal() {
  openModal("sign-options-modal");
  const canvas = document.getElementById("sign-canvas");
  if (!canvas) return;
  signCtx = canvas.getContext("2d");
  if (!signPadInited) {
    initSignatureEvents(canvas);
    signPadInited = true;
  }
}

function initSignatureEvents(canvas) {
  function getPos(e) {
    const rect = canvas.getBoundingClientRect();
    const clientX = e.touches ? e.touches[0].clientX : e.clientX;
    const clientY = e.touches ? e.touches[0].clientY : e.clientY;
    return {
      x: (clientX - rect.left) * (canvas.width / rect.width),
      y: (clientY - rect.top) * (canvas.height / rect.height)
    };
  }

  function startDraw(e) {
    isDrawingSign = true;
    const pos = getPos(e);
    signCtx.beginPath();
    signCtx.moveTo(pos.x, pos.y);
    signCtx.strokeStyle = document.getElementById("sign-color") ? document.getElementById("sign-color").value : "#000000";
    signCtx.lineWidth = 2.5;
    signCtx.lineCap = "round";
    signCtx.lineJoin = "round";
  }

  function drawMove(e) {
    if (!isDrawingSign) return;
    if (e.cancelable) e.preventDefault();
    const pos = getPos(e);
    signCtx.lineTo(pos.x, pos.y);
    signCtx.stroke();
  }

  function endDraw() {
    isDrawingSign = false;
  }

  canvas.addEventListener("mousedown", startDraw);
  canvas.addEventListener("mousemove", drawMove);
  window.addEventListener("mouseup", endDraw);
  canvas.addEventListener("touchstart", startDraw, { passive: false });
  canvas.addEventListener("touchmove", drawMove, { passive: false });
  window.addEventListener("touchend", endDraw);
}

function clearSignaturePad() {
  const canvas = document.getElementById("sign-canvas");
  if (canvas && signCtx) {
    signCtx.clearRect(0, 0, canvas.width, canvas.height);
  }
}

async function submitSignature() {
  const canvas = document.getElementById("sign-canvas");
  if (!canvas) return;
  const sigData = canvas.toDataURL("image/png");
  closeAllModals();
  openJobProgressModal("Applying Digital Signature...");

  try {
    const res = await fetch("/api/pdf/sign", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        job_id: currentJobId,
        signature: sigData
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Signature stamping failed.");
    pollJobStatus(currentJobId);
  } catch (err) {
    updateJobError(err.message);
  }
}

// 8. Redaction Handler
async function submitRedact() {
  const presets = [];
  if (document.getElementById("preset-email")?.checked) presets.push("email");
  if (document.getElementById("preset-phone")?.checked) presets.push("phone");
  if (document.getElementById("preset-ssn")?.checked) presets.push("ssn");
  if (document.getElementById("preset-card")?.checked) presets.push("credit_card");

  const keywordsRaw = document.getElementById("redact-keywords-input")?.value || "";
  const keywords = keywordsRaw.split(",").map(s => s.trim()).filter(Boolean);

  if (presets.length === 0 && keywords.length === 0) {
    showToast("Select at least one preset pattern or enter keywords to redact.", "warning");
    return;
  }

  closeAllModals();
  openJobProgressModal("Applying Permanent Redactions...");

  try {
    const res = await fetch("/api/pdf/redact_keywords", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        job_id: currentJobId,
        presets: presets,
        keywords: keywords,
        fill_color: "#000000"
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Redaction failed.");
    pollJobStatus(currentJobId);
  } catch (err) {
    updateJobError(err.message);
  }
}

// 9. Compare PDFs Handler
function openCompareModal() {
  openModal("compare-options-modal");
  const upSec = document.getElementById("compare-upload-section");
  const resSec = document.getElementById("compare-results-section");
  if (upSec) upSec.style.display = "block";
  if (resSec) resSec.style.display = "none";
}

async function submitCompare() {
  const f2 = document.getElementById("compare-file2-input");
  if (!f2 || !f2.files || f2.files.length === 0) {
    showToast("Please select the second PDF document to compare.", "warning");
    return;
  }

  if (!currentJobId || currentUploadedFiles.length === 0) {
    showToast("Please upload the first document on the main dropzone first.", "warning");
    return;
  }

  showToast("Uploading comparison document...", "info", 2000);
  const formData = new FormData();
  formData.append("files", f2.files[0]);

  try {
    const uploadRes = await fetch("/api/upload", {
      method: "POST",
      body: formData
    });
    const uploadData = await uploadRes.json();
    if (!uploadRes.ok) throw new Error(uploadData.error || "Upload of second document failed.");

    const res = await fetch("/api/pdf/compare_files", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        job_id: currentJobId,
        file1: currentUploadedFiles[0].filename,
        file2: uploadData.files[0].filename
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Comparison failed.");

    const rep = data.comparison;
    document.getElementById("compare-upload-section").style.display = "none";
    document.getElementById("compare-results-section").style.display = "block";

    const meta = document.getElementById("compare-summary-meta");
    const diffBox = document.getElementById("compare-diff-box");

    meta.innerHTML = rep.identical
      ? `<span style="color:var(--accent-emerald);">✅ Documents are identical! (Pages: ${rep.doc1_pages})</span>`
      : `<span style="color:var(--accent-amber);">⚠️ Differences found across ${rep.pages_with_differences} page(s). Doc1: ${rep.doc1_pages} pages, Doc2: ${rep.doc2_pages} pages.</span>`;

    if (rep.differences.length === 0) {
      diffBox.innerHTML = `No textual differences detected between the two PDF documents.`;
    } else {
      diffBox.innerHTML = rep.differences.map(d => `
        <div style="margin-bottom:12px;border-bottom:1px solid var(--border-subtle);padding-bottom:8px;">
          <strong>Page ${d.page} (${d.changes} line modifications):</strong>
          <pre style="margin-top:6px;">${d.diff_lines.map(line => {
            const cls = line.startsWith("+") ? "diff-line-add" : (line.startsWith("-") ? "diff-line-del" : "");
            return `<div class="${cls}">${escapeHtml(line)}</div>`;
          }).join("")}</pre>
        </div>
      `).join("");
    }
  } catch (err) {
    showToast(err.message, "error", 5000);
  }
}

// 10. Forms Inspection & Filling Handler
async function openFormsModal() {
  openModal("forms-options-modal");
  const loading = document.getElementById("forms-loading-state");
  const content = document.getElementById("forms-content-state");
  const container = document.getElementById("forms-fields-container");
  if (loading) loading.style.display = "block";
  if (content) content.style.display = "none";

  try {
    const res = await fetch("/api/pdf/forms/inspect", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_id: currentJobId })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Failed to inspect forms.");

    if (loading) loading.style.display = "none";
    if (content) content.style.display = "block";

    if (!data.data || !data.data.has_forms || data.data.field_count === 0) {
      container.innerHTML = `<div style="text-align:center;padding:20px;color:var(--text-muted);">No interactive AcroForms form fields were detected in this document. You can use the PDF Editor to add text fields!</div>`;
      return;
    }

    container.innerHTML = `
      <table class="form-fields-table">
        <thead>
          <tr>
            <th>Page</th>
            <th>Field Name</th>
            <th>Type</th>
            <th>Value</th>
          </tr>
        </thead>
        <tbody>
          ${data.data.fields.map(f => `
            <tr>
              <td>P.${f.page}</td>
              <td><strong>${escapeHtml(f.name)}</strong></td>
              <td><span class="tool-badge">${f.type}</span></td>
              <td>
                <input type="text" class="form-input form-field-val" data-name="${escapeHtml(f.name)}" value="${escapeHtml(f.value)}" style="height:34px;padding:4px 8px;">
              </td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;
  } catch (e) {
    if (loading) loading.innerHTML = `<span style="color:var(--accent-rose);">Error: ${e.message}</span>`;
  }
}

async function submitFillForms() {
  const inputs = document.querySelectorAll(".form-field-val");
  const fieldData = {};
  inputs.forEach(inp => {
    fieldData[inp.getAttribute("data-name")] = inp.value;
  });

  closeAllModals();
  openJobProgressModal("Filling Form Fields...");

  try {
    const res = await fetch("/api/pdf/forms/fill", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_id: currentJobId, fields: fieldData })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Failed to fill form.");
    pollJobStatus(currentJobId);
  } catch (err) {
    updateJobError(err.message);
  }
}

// 11. AI Summarizer Handler
function openSummarizeModal() {
  openModal("summarize-options-modal");
  const ctrl = document.getElementById("summarize-controls");
  const res = document.getElementById("summarize-results");
  if (ctrl) ctrl.style.display = "block";
  if (res) res.style.display = "none";
}

async function submitSummarize() {
  const sentences = document.getElementById("summarize-sentences-select").value || 5;
  const controls = document.getElementById("summarize-controls");
  const results = document.getElementById("summarize-results");
  const stats = document.getElementById("summarize-stats");
  const content = document.getElementById("summarize-text-content");

  content.innerHTML = `<span class="pulse-dot"></span> Analyzing document text and extracting key points locally...`;
  controls.style.display = "none";
  results.style.display = "block";

  try {
    const res = await fetch("/api/intelligence/summarize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_id: currentJobId, sentences: parseInt(sentences) })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Failed to generate summary.");

    stats.innerHTML = `
      <span>📄 Total Words: <strong>${data.total_words}</strong></span> • 
      <span>⏱️ Reading Time: <strong>${data.estimated_reading_time_mins} min</strong></span> • 
      <span>💡 Extracted Points: <strong>${data.sentences_extracted}</strong></span>
    `;

    lastSummaryResult = `## Executive Summary\n\n${data.summary}\n\n### Key Takeaways\n${data.key_takeaways.map(t => `- ${t}`).join("\n")}`;

    content.innerHTML = `
      <h4 style="margin-bottom:8px;font-size:1rem;color:var(--primary);">Executive Summary</h4>
      <p style="margin-bottom:14px;line-height:1.6;">${data.summary}</p>
      <h4 style="margin-bottom:8px;font-size:1rem;color:var(--primary);">Key Takeaways</h4>
      <ul style="padding-left:18px;line-height:1.6;">
        ${data.key_takeaways.map(t => `<li style="margin-bottom:6px;">${escapeHtml(t)}</li>`).join("")}
      </ul>
    `;
  } catch (err) {
    content.innerHTML = `<span style="color:var(--accent-rose);">Error: ${err.message}</span>`;
  }
}

function copySummaryToClipboard() {
  if (lastSummaryResult) {
    navigator.clipboard.writeText(lastSummaryResult);
    showToast("Summary copied to clipboard!", "success", 2500);
  }
}

// 12. Translate Handler
function openTranslateModal() {
  openModal("translate-options-modal");
  const ctrl = document.getElementById("translate-controls");
  const res = document.getElementById("translate-results");
  if (ctrl) ctrl.style.display = "block";
  if (res) res.style.display = "none";
}

async function submitTranslate() {
  const lang = document.getElementById("translate-lang-select").value || "es";
  const controls = document.getElementById("translate-controls");
  const results = document.getElementById("translate-results");
  const meta = document.getElementById("translate-meta");
  const preview = document.getElementById("translate-preview-box");

  controls.style.display = "none";
  results.style.display = "block";
  preview.innerHTML = `<span class="pulse-dot"></span> Translating text locally into ${lang.toUpperCase()}...`;

  try {
    const res = await fetch("/api/intelligence/translate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_id: currentJobId, target_language: lang })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Translation failed.");

    meta.innerHTML = `Target Language: <strong>${data.target_language.toUpperCase()}</strong> • Translated ${data.word_count || 0} words`;
    lastTranslationResult = data.translated_text;
    preview.innerText = data.translated_text || "No text available.";
  } catch (err) {
    preview.innerHTML = `<span style="color:var(--accent-rose);">Error: ${err.message}</span>`;
  }
}

function copyTranslationToClipboard() {
  if (lastTranslationResult) {
    navigator.clipboard.writeText(lastTranslationResult);
    showToast("Translation copied to clipboard!", "success", 2500);
  }
}

// 13. PDF to Markdown Handler
async function openMarkdownModal() {
  openModal("markdown-options-modal");
  const area = document.getElementById("markdown-preview-area");
  const dlBtn = document.getElementById("markdown-download-btn");
  area.innerHTML = `<span class="pulse-dot"></span> Converting PDF structure to GitHub Markdown...`;

  try {
    const res = await fetch("/api/intelligence/markdown", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_id: currentJobId })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Markdown conversion failed.");

    lastMarkdownResult = data.markdown;
    area.innerHTML = `<pre style="white-space:pre-wrap;font-family:'JetBrains Mono',monospace;">${escapeHtml(data.markdown)}</pre>`;
    if (dlBtn) {
      dlBtn.onclick = () => {
        window.location.href = data.download_url;
      };
    }
  } catch (err) {
    area.innerHTML = `<span style="color:var(--accent-rose);">Error: ${err.message}</span>`;
  }
}

function copyMarkdownToClipboard() {
  if (lastMarkdownResult) {
    navigator.clipboard.writeText(lastMarkdownResult);
    showToast("Markdown copied to clipboard!", "success", 2500);
  }
}

// 14. Scan to PDF (Camera & Mobile Capture)
async function openScanModal() {
  openModal("scan-pdf-modal");
  const video = document.getElementById("camera-video");
  try {
    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
      cameraStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 }, height: { ideal: 1080 } },
        audio: false
      });
      if (video) video.srcObject = cameraStream;
    }
  } catch (e) {
    showToast("Camera access unavailable. You can use 'Import Photo' to add scans from files.", "info", 4000);
  }

  const fallback = document.getElementById("scan-file-fallback");
  if (fallback) {
    fallback.onchange = (e) => {
      if (e.target.files) {
        Array.from(e.target.files).forEach(file => {
          const reader = new FileReader();
          reader.onload = (evt) => {
            scannedImages.push(evt.target.result);
            renderScannedReel();
          };
          reader.readAsDataURL(file);
        });
      }
    };
  }
}

function stopCamera() {
  if (cameraStream) {
    cameraStream.getTracks().forEach(track => track.stop());
    cameraStream = null;
  }
}

function captureCameraPage() {
  const video = document.getElementById("camera-video");
  const canvas = document.getElementById("camera-capture-canvas");
  if (!video || !canvas || !cameraStream) {
    const fb = document.getElementById("scan-file-fallback");
    if (fb) fb.click();
    return;
  }

  canvas.width = video.videoWidth || 1280;
  canvas.height = video.videoHeight || 720;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
  const dataUrl = canvas.toDataURL("image/jpeg", 0.92);
  scannedImages.push(dataUrl);
  renderScannedReel();
  showToast(`Page ${scannedImages.length} captured!`, "success", 1500);
}

function renderScannedReel() {
  const reel = document.getElementById("scanned-reel");
  const countEl = document.getElementById("scan-page-count");
  if (countEl) countEl.textContent = scannedImages.length;
  if (!reel) return;

  reel.innerHTML = scannedImages.map((src, i) => `
    <div style="position:relative;display:inline-block;">
      <img src="${src}" class="scanned-thumb" alt="Page ${i+1}">
      <span style="position:absolute;bottom:4px;right:4px;background:rgba(0,0,0,0.7);color:#fff;font-size:10px;padding:1px 4px;border-radius:4px;">P.${i+1}</span>
    </div>
  `).join("");
}

function clearScannedPages() {
  scannedImages = [];
  renderScannedReel();
}

async function compileScannedToPDF() {
  if (scannedImages.length === 0) {
    showToast("Please capture or import at least 1 page first.", "warning");
    return;
  }

  stopCamera();
  closeAllModals();
  openJobProgressModal("Compiling Scanned Pages into PDF...");

  const formData = new FormData();
  scannedImages.forEach((dataUrl, idx) => {
    const arr = dataUrl.split(",");
    const mime = arr[0].match(/:(.*?);/)[1];
    const bstr = atob(arr[1]);
    let n = bstr.length;
    const u8arr = new Uint8Array(n);
    while (n--) {
      u8arr[n] = bstr.charCodeAt(n);
    }
    const blob = new Blob([u8arr], { type: mime });
    formData.append("files", blob, `scan_page_${idx+1}.jpg`);
  });

  try {
    const uploadRes = await fetch("/api/upload", {
      method: "POST",
      body: formData
    });
    const uploadData = await uploadRes.json();
    if (!uploadRes.ok) throw new Error(uploadData.error || "Failed to upload scanned pages.");

    currentJobId = uploadData.job_id;
    currentUploadedFiles = uploadData.files;

    startConversion("pdf");
  } catch (err) {
    updateJobError(err.message);
  }
}

// 15. Polling Mechanism for Asynchronous Tasks
function pollJobStatus(jobId) {
  const interval = setInterval(async () => {
    try {
      const res = await fetch(`/api/jobs/${jobId}`);
      if (!res.ok) throw new Error("Job tracking unreachable.");
      const job = await res.json();

      updateProgressBar(job.progress || 0, job.message || "Processing...");

      if (job.status === "completed") {
        clearInterval(interval);
        onJobCompleted(job);
      } else if (job.status === "failed") {
        clearInterval(interval);
        updateJobError(job.error || "Task processing failed.");
      }
    } catch (e) {
      clearInterval(interval);
      updateJobError(e.message);
    }
  }, 750);
}

function openJobProgressModal(title) {
  const modal = document.getElementById("job-progress-modal");
  const titleEl = document.getElementById("job-modal-title");
  const bar = document.getElementById("job-progress-bar");
  const msg = document.getElementById("job-progress-msg");
  const pct = document.getElementById("job-progress-pct");
  const btnGroup = document.getElementById("job-completed-actions");

  if (titleEl) titleEl.textContent = title;
  if (bar) bar.style.width = "5%";
  if (msg) msg.textContent = "Initializing...";
  if (pct) pct.textContent = "5%";
  if (btnGroup) btnGroup.style.display = "none";

  if (modal) modal.classList.add("active");
}

function updateProgressBar(percent, message) {
  const bar = document.getElementById("job-progress-bar");
  const msg = document.getElementById("job-progress-msg");
  const pct = document.getElementById("job-progress-pct");

  if (bar) bar.style.width = `${percent}%`;
  if (msg) msg.textContent = message;
  if (pct) pct.textContent = `${percent}%`;
}

function onJobCompleted(job) {
  updateProgressBar(100, "Done! Your document is ready.");
  const btnGroup = document.getElementById("job-completed-actions");
  const dlBtn = document.getElementById("job-download-btn");

  if (dlBtn) {
    dlBtn.onclick = () => {
      window.location.href = `/api/download/${job.job_id}`;
    };
  }

  if (btnGroup) btnGroup.style.display = "flex";

  // Automatically trigger download
  setTimeout(() => {
    window.location.href = `/api/download/${job.job_id}`;
  }, 600);

  // Store in LocalStorage Recent Jobs
  saveRecentJob({
    job_id: job.job_id,
    filename: job.output_filename,
    operation: job.operation,
    size: job.output_size,
    date: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  });

  showToast("File processed and ready for download!", "success", 4000);
}

function updateJobError(errorMsg) {
  const msg = document.getElementById("job-progress-msg");
  if (msg) {
    msg.innerHTML = `<span style="color:var(--accent-rose);font-weight:700;">Error: ${escapeHtml(errorMsg)}</span>`;
  }
  showToast(errorMsg, "error", 6000);
}

// 16. Recent Jobs in LocalStorage
function saveRecentJob(jobData) {
  let list = JSON.parse(localStorage.getItem("docuflex_recent_jobs") || "[]");
  list.unshift(jobData);
  if (list.length > 6) list = list.slice(0, 6);
  localStorage.setItem("docuflex_recent_jobs", JSON.stringify(list));
  renderRecentJobs();
}

function renderRecentJobs() {
  const container = document.getElementById("recent-jobs-list");
  if (!container) return;

  const list = JSON.parse(localStorage.getItem("docuflex_recent_jobs") || "[]");
  if (list.length === 0) {
    container.innerHTML = `<p style="color:var(--text-dim);font-size:0.9rem;">No processed documents yet.</p>`;
    return;
  }

  container.innerHTML = list.map(item => `
    <div class="recent-job-row">
      <div class="recent-job-info">
        <div style="width:36px;height:36px;border-radius:6px;background:rgba(99,102,241,0.15);display:flex;align-items:center;justify-content:center;color:var(--primary);">
          📄
        </div>
        <div>
          <h5 style="font-size:0.95rem;font-weight:700;">${escapeHtml(item.filename)}</h5>
          <p style="font-size:0.8rem;color:var(--text-dim);">${formatBytes(item.size || 0)} • ${item.date}</p>
        </div>
      </div>
      <a href="/api/download/${item.job_id}" class="btn btn-primary btn-sm">
        Download
      </a>
    </div>
  `).join("");
}

// 17. Modal Management
function openModal(id) {
  closeAllModals();
  const m = document.getElementById(id);
  if (m) m.classList.add("active");
}

function closeModal(id) {
  const m = document.getElementById(id);
  if (m) m.classList.remove("active");
}

function closeAllModals() {
  document.querySelectorAll(".modal-overlay").forEach(m => m.classList.remove("active"));
}

// 18. Category Tabs Filter
function initCategoryTabs() {
  const tabs = document.querySelectorAll(".category-tabs .tab-btn");
  const cards = document.querySelectorAll(".tool-card");

  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      tabs.forEach(t => t.classList.remove("active"));
      tab.classList.add("active");

      const category = tab.getAttribute("data-category");
      cards.forEach(card => {
        if (category === "all" || card.getAttribute("data-category") === category) {
          card.style.display = "flex";
        } else {
          card.style.display = "none";
        }
      });
    });
  });
}

function escapeHtml(text) {
  if (!text) return "";
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
