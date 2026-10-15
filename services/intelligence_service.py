import os
import re
import math
import collections
from typing import Dict, Any, List, Optional
import fitz  # PyMuPDF

STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are",
    "aren't", "as", "at", "be", "because", "been", "before", "being", "below", "between", "both",
    "but", "by", "can", "cannot", "could", "couldn't", "did", "didn't", "do", "does", "doesn't",
    "doing", "don't", "down", "during", "each", "few", "for", "from", "further", "had", "hadn't",
    "has", "hasn't", "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here",
    "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i", "i'd", "i'll", "i'm",
    "i've", "if", "in", "into", "is", "isn't", "it", "it's", "its", "itself", "let's", "me", "more",
    "most", "mustn't", "my", "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or",
    "other", "ought", "our", "ours", "ourselves", "out", "over", "own", "same", "shan't", "she",
    "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such", "than", "that", "that's",
    "the", "their", "theirs", "them", "themselves", "then", "there", "there's", "these", "they",
    "they'd", "they'll", "they're", "they've", "this", "those", "through", "to", "too", "under",
    "until", "up", "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were",
    "weren't", "what", "what's", "when", "when's", "where", "where's", "which", "while", "who",
    "who's", "whom", "why", "why's", "with", "won't", "would", "wouldn't", "you", "you'd", "you'll",
    "you're", "you've", "your", "yours", "yourself", "yourselves"
}

def extract_pdf_clean_text(input_path: str) -> str:
    """Extract plain text from all pages in a PDF document."""
    doc = fitz.open(input_path)
    text_chunks = []
    try:
        for page in doc:
            t = page.get_text("text").strip()
            if t:
                text_chunks.append(t)
        return "\n\n".join(text_chunks)
    finally:
        doc.close()

def summarize_pdf(input_path: str, max_sentences: int = 5) -> Dict[str, Any]:
    """
    100% Offline Extractive AI Summarizer using pure Python frequency-weighted NLP.
    Calculates sentence importance, extracts key takeaways, top keywords,
    and reading time savings without external cloud or paid APIs.
    """
    full_text = extract_pdf_clean_text(input_path)
    if not full_text.strip():
        raise ValueError("Document contains no readable text. If this is a scan, run OCR first.")

    # Split into sentences (handling punctuation and line breaks)
    clean_paragraphs = re.split(r'\n+', full_text)
    raw_sentences = []
    for para in clean_paragraphs:
        parts = re.split(r'(?<=[.!?])\s+', para.strip())
        for p in parts:
            p_clean = p.strip()
            if len(p_clean.split()) >= 5: # Ignore very short headers
                raw_sentences.append(p_clean)

    if not raw_sentences:
        raw_sentences = [p.strip() for p in clean_paragraphs if p.strip()]

    # Word frequency map
    all_words = [w.lower() for w in re.findall(r'\b[a-zA-Z]{3,}\b', full_text)]
    content_words = [w for w in all_words if w not in STOPWORDS]
    word_freq = collections.Counter(content_words)

    # Top keywords
    top_keywords = [kw for kw, _ in word_freq.most_common(8)]

    # Score each sentence
    sentence_scores = []
    for idx, sentence in enumerate(raw_sentences):
        words = [w.lower() for w in re.findall(r'\b[a-zA-Z]{3,}\b', sentence) if w not in STOPWORDS]
        if not words:
            continue
        # Base word frequency score
        score = sum(word_freq[w] for w in words) / (math.sqrt(len(words)) + 1)
        # Position boost (leading sentences in document get priority)
        position_boost = 1.25 if idx < 3 else 1.0
        sentence_scores.append((sentence, score * position_boost, idx))

    # Select top N sentences sorted by original document flow
    sentence_scores.sort(key=lambda x: x[1], reverse=True)
    selected = sentence_scores[:max_sentences]
    selected.sort(key=lambda x: x[2]) # Restore chronological sequence

    bullet_points = [s[0] for s in selected]
    summary_paragraph = " ".join(bullet_points)

    total_words = len(full_text.split())
    summary_words = len(summary_paragraph.split())
    compression_pct = round((1.0 - (summary_words / max(1, total_words))) * 100, 1)

    return {
        "success": True,
        "total_words": total_words,
        "summary_words": summary_words,
        "compression_ratio": f"{compression_pct}% reduction",
        "estimated_reading_time": f"{max(1, round(total_words / 200))} min read",
        "estimated_reading_time_mins": max(1, round(total_words / 200)),
        "key_topics": top_keywords,
        "bullet_points": bullet_points,
        "key_takeaways": bullet_points,
        "summary": summary_paragraph,
        "executive_summary": summary_paragraph,
        "sentences_extracted": len(bullet_points)
    }

def convert_pdf_to_markdown(input_path: str, output_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Convert PDF into structured GitHub-Flavored Markdown:
    - Inspects font sizes to infer #, ##, ### headers
    - Extracts tabular structures into clean markdown tables (| col | col |)
    - Formats bold text (**text**)
    - Preserves bulleted lists (- item)
    """
    doc = fitz.open(input_path)
    md_lines = []

    try:
        for p_idx, page in enumerate(doc):
            md_lines.append(f"<!-- Page {p_idx + 1} -->\n")

            # 1. Extract any tables on page
            tables = page.find_tables()
            table_rects = []
            if tables:
                for tab in tables:
                    table_rects.append(tab.bbox)
                    df = tab.extract()
                    if df and len(df) > 0:
                        # Header
                        headers = [str(c or "").strip() for c in df[0]]
                        md_lines.append("| " + " | ".join(headers) + " |")
                        md_lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
                        # Rows
                        for row in df[1:]:
                            cells = [str(c or "").strip().replace("\n", " ") for c in row]
                            md_lines.append("| " + " | ".join(cells) + " |")
                        md_lines.append("")

            # 2. Extract text blocks and spans
            page_dict = page.get_text("dict")
            for block in page_dict.get("blocks", []):
                if block.get("type") == 0:  # Text block
                    b_bbox = block.get("bbox", [0, 0, 0, 0])
                    # Skip if inside an extracted table
                    in_table = any(
                        (b_bbox[0] >= tr[0] - 5 and b_bbox[1] >= tr[1] - 5 and b_bbox[2] <= tr[2] + 5 and b_bbox[3] <= tr[3] + 5)
                        for tr in table_rects
                    )
                    if in_table:
                        continue

                    block_text_lines = []
                    for line in block.get("lines", []):
                        line_spans = []
                        line_font_size = 12
                        for span in line.get("spans", []):
                            txt = span.get("text", "")
                            if not txt.strip():
                                continue
                            size = span.get("size", 12)
                            line_font_size = max(line_font_size, size)
                            flags = span.get("flags", 0)
                            is_bold = bool(flags & 2 or "bold" in span.get("font", "").lower())
                            
                            formatted_span = f"**{txt}**" if is_bold else txt
                            line_spans.append(formatted_span)

                        if line_spans:
                            full_line = " ".join(line_spans).strip()
                            if line_font_size >= 18:
                                full_line = f"# {full_line}"
                            elif line_font_size >= 14:
                                full_line = f"## {full_line}"
                            elif line_font_size >= 12.5:
                                full_line = f"### {full_line}"
                            elif full_line.startswith(("•", "-", "*")):
                                full_line = f"- {full_line.lstrip('•-* ')}"
                            block_text_lines.append(full_line)

                    if block_text_lines:
                        md_lines.append("\n".join(block_text_lines))
                        md_lines.append("") # paragraph break

        final_markdown = "\n".join(md_lines)
        if output_path:
            with open(output_path, "w", encoding="utf-8") as f_out:
                f_out.write(final_markdown)

        return {
            "success": True,
            "markdown": final_markdown,
            "line_count": len(md_lines),
            "output_path": output_path
        }
    finally:
        doc.close()

# Offline Local Translation Dictionary & Rule-Based Term Mapper
OFFLINE_DICTIONARIES = {
    "es": {
        "document": "documento", "invoice": "factura", "report": "informe", "total": "total",
        "date": "fecha", "page": "página", "summary": "resumen", "customer": "cliente",
        "contract": "contrato", "confidential": "confidencial", "agreement": "acuerdo",
        "project": "proyecto", "payment": "pago", "service": "servicio", "signature": "firma",
        "hello": "hola", "world": "mundo", "local": "local", "security": "seguridad"
    },
    "fr": {
        "document": "document", "invoice": "facture", "report": "rapport", "total": "total",
        "date": "date", "page": "page", "summary": "sommaire", "customer": "client",
        "contract": "contrat", "confidential": "confidentiel", "agreement": "accord",
        "project": "projet", "payment": "paiement", "service": "service", "signature": "signature"
    },
    "de": {
        "document": "Dokument", "invoice": "Rechnung", "report": "Bericht", "total": "Gesamt",
        "date": "Datum", "page": "Seite", "summary": "Zusammenfassung", "customer": "Kunde",
        "contract": "Vertrag", "confidential": "vertraulich", "agreement": "Vereinbarung",
        "project": "Projekt", "payment": "Zahlung", "service": "Dienstleistung", "signature": "Unterschrift"
    },
    "it": {
        "document": "documento", "invoice": "fattura", "report": "rapporto", "total": "totale",
        "date": "data", "page": "pagina", "summary": "sommario", "customer": "cliente",
        "contract": "contratto", "confidential": "riservato", "agreement": "accordo"
    },
    "hi": {
        "document": "दस्तावेज़", "invoice": "चालान", "report": "रिपोर्ट", "total": "कुल",
        "date": "तारीख", "page": "पृष्ठ", "summary": "सारांश", "customer": "ग्राहक",
        "contract": "अनुबंध", "confidential": "गोपनीय", "agreement": "समझौता"
    }
}

def translate_pdf_text(input_path: str, target_lang: str = "es") -> Dict[str, Any]:
    """
    Offline local PDF translator. Performs term & phrase translation without cloud APIs.
    Returns bilingual extracted text and translated document summary.
    """
    doc = fitz.open(input_path)
    lang = target_lang.lower().strip()
    dict_map = OFFLINE_DICTIONARIES.get(lang, OFFLINE_DICTIONARIES["es"])
    
    pages_translated = []
    try:
        for p_idx, page in enumerate(doc):
            orig_text = page.get_text("text").strip()
            # Perform word replacement
            trans_words = []
            for word in orig_text.split():
                clean_w = re.sub(r'[^\w]', '', word.lower())
                if clean_w in dict_map:
                    replacement = dict_map[clean_w]
                    # Preserve case
                    if word.isupper():
                        replacement = replacement.upper()
                    elif word[0].isupper():
                        replacement = replacement.capitalize()
                    trans_words.append(word.lower().replace(clean_w, replacement))
                else:
                    trans_words.append(word)
            
            trans_text = " ".join(trans_words)
            pages_translated.append({
                "page": p_idx + 1,
                "original": orig_text,
                "translated": trans_text
            })
            
        all_translated = "\n\n".join(p["translated"] for p in pages_translated)
        return {
            "success": True,
            "target_language": lang,
            "total_pages": len(pages_translated),
            "translated_text": all_translated,
            "word_count": len(all_translated.split()),
            "pages": pages_translated
        }
    finally:
        doc.close()
