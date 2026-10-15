import os
import shutil
import subprocess
from pathlib import Path
from config import Config

def find_libreoffice() -> str | None:
    """Locate LibreOffice soffice binary on Windows/Linux."""
    # 1. Custom configured path
    if Config.LIBREOFFICE_PATH and os.path.isfile(Config.LIBREOFFICE_PATH):
        return Config.LIBREOFFICE_PATH
    
    # 2. In PATH
    which_path = shutil.which("soffice") or shutil.which("libreoffice")
    if which_path:
        return which_path
        
    # 3. Common Windows directories
    common_win_paths = [
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\LibreOffice\program\soffice.exe")
    ]
    for path in common_win_paths:
        if os.path.isfile(path):
            return path
            
    return None

def find_tesseract() -> str | None:
    """Locate Tesseract OCR binary on Windows/Linux."""
    # 1. Custom configured path
    if Config.TESSERACT_PATH and os.path.isfile(Config.TESSERACT_PATH):
        return Config.TESSERACT_PATH
        
    # 2. In PATH
    which_path = shutil.which("tesseract")
    if which_path:
        return which_path
        
    # 3. Common Windows directories
    common_win_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Tesseract-OCR\tesseract.exe"),
        os.path.expandvars(r"%USERPROFILE%\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
        r"C:\tools\tesseract\tesseract.exe",
        r"D:\Tesseract-OCR\tesseract.exe"
    ]
    for path in common_win_paths:
        if os.path.isfile(path):
            return path
            
def find_ms_office() -> bool:
    """Check if Microsoft Word or Excel is installed on Windows."""
    if os.name != "nt":
        return False
    try:
        import winreg
        for app in ("winword.exe", "excel.exe"):
            try:
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, rf"Software\Microsoft\Windows\CurrentVersion\App Paths\{app}")
                val, _ = winreg.QueryValueEx(key, "")
                if val and os.path.isfile(val):
                    return True
            except Exception:
                continue
    except Exception:
        pass
    return False

def get_tesseract_languages() -> list[str]:
    """Retrieve installed OCR languages if Tesseract is available."""
    tess_path = find_tesseract()
    if not tess_path:
        return []
    try:
        res = subprocess.run([tess_path, "--list-langs"], capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            lines = [line.strip() for line in res.stdout.splitlines()[1:] if line.strip()]
            return lines
    except Exception:
        pass
    return ["eng"]

def get_system_capabilities() -> dict:
    """Return runtime capability report for UI and API."""
    libreoffice_bin = find_libreoffice()
    has_ms_office = find_ms_office()
    office_available = libreoffice_bin is not None or has_ms_office
    office_engine = "LibreOffice Headless" if libreoffice_bin else ("Microsoft Office Native (Word/Excel)" if has_ms_office else "None")
    
    tesseract_bin = find_tesseract()
    tess_langs = get_tesseract_languages() if tesseract_bin else ["eng"]
    
    return {
        "python_version": "3.10",
        "libreoffice": {
            "available": office_available,
            "engine": office_engine,
            "path": libreoffice_bin,
            "features": ["DOCX to PDF", "XLSX to PDF", "PPTX to PDF"] if office_available else []
        },
        "tesseract": {
            "available": True,
            "system_binary": tesseract_bin is not None,
            "engine": "Tesseract OCR (System)" if tesseract_bin else "DocuFlex Neural OCR (Built-In)",
            "path": tesseract_bin,
            "languages": tess_langs,
            "features": ["OCR Text Extraction", "Searchable PDF Generation"]
        },
        "native_features": [
            "Word-Like PDF Visual Editor",
            "PDF to Word (DOCX)",
            "PDF to PowerPoint (PPTX - Visual & Editable)",
            "PDF to Excel (XLSX)",
            "PDF to Images (JPG, PNG)",
            "PDF to PDF/A Archival Format",
            "Images to PDF (JPG, PNG)",
            "Word & Excel to PDF (DOCX, XLSX)",
            "PowerPoint to PDF (PPTX)",
            "HTML to PDF",
            "Word tables to Excel (DOCX to XLSX)",
            "PDF Merge, Split, Extract & Remove Pages",
            "PDF Rotate & Organize Pages",
            "PDF Repair & Recovery",
            "PDF Crop Margins",
            "PDF Interactive Forms (Fill & Inspect)",
            "PDF Compression & Optimization",
            "PDF Password Protect & Unlock",
            "PDF Digital Signatures",
            "PDF Sensitive Keyword Redaction",
            "PDF Comparison & Visual Diff",
            "AI Extractive Summarizer",
            "PDF Multilingual Translator",
            "PDF to Markdown Extractor"
        ]
    }
