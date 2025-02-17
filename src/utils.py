import re
import unicodedata
from datetime import datetime

def clean_eng_ocr_text(text: str) -> str:
    """Clean and normalize English OCR output text."""
    # Remove special character patterns
    text = re.sub(r'[!®°©]\s*', '', text)
    text = re.sub(r'[\[\d+\]|\d+!l\d+!|\(\d+\[\d+\]|\d{1,2}:\d{1,2}(?::\d{1,2})?]', '', text)
    
    # Replace single newlines with spaces
    text = re.sub(r'([^\n])\n([^\n])', r'\1 \2', text)
    text = text.strip()
    text = re.sub(r'\s+', ' ', text)
    
    return text

def clean_chi_ocr_text(text: str) -> str:
    """Clean and normalize Chinese OCR output text."""
    if not text:
        return ""
    text = unicodedata.normalize('NFKC', text)
    text = re.sub(r'\d{1,2}:\d{1,2}(?::\d{1,2})?', '', text)
    text = re.sub(r'\s+', '', text)
    return text.strip()

def is_chinese(text: str) -> bool:
    """Check if text is primarily Chinese."""
    chinese_chars = sum('\u4e00' <= char <= '\u9fff' for char in text)
    return chinese_chars > len(text) * 0.9

def create_safe_filename(text: str, max_length: int = 50, extension: str = 'mp3') -> str:
    """Create a safe filename from text content."""
    if not text:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f"audio_{timestamp}.{extension}"
    
    # Get first line
    first_line = text.split('\n')[0].strip()
    safe_text = first_line[:max_length]
    
    # Remove invalid filename characters but preserve Chinese
    safe_text = re.sub(r'[<>:"/\\|?*]', '', safe_text)
    
    if is_chinese(safe_text):
        # For Chinese text, keep original characters
        safe_text = safe_text[:10]  # Limit Chinese characters
    else:
        # For non-Chinese text, normalize and convert to ASCII
        safe_text = re.sub(r'[^a-zA-Z0-9\s-]', '', safe_text)
        safe_text = safe_text.strip().replace(' ', '_').lower()
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f"{safe_text}_{timestamp}.{extension}" 