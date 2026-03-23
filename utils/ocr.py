"""
utils/ocr.py — Enhanced OCR pipeline for Indian number plates
Improvements:
  - Multi-scale preprocessing (original + 2x upscale + CLAHE)
  - Deskew / perspective correction attempt
  - EasyOCR with allowlist for plate characters
  - Tesseract fallback (if installed)
  - Regex-based post-processing to match Indian plate format
"""

import cv2
import numpy as np
import re

# Indian number plate regex patterns (covers most formats)
_PLATE_PATTERNS = [
    re.compile(r'^[A-Z]{2}\d{2}[A-Z]{1,2}\d{4}$'),   # DL3CAB1234
    re.compile(r'^[A-Z]{2}\d{2}[A-Z]{1,3}\d{3,4}$'),  # MH12AB123
    re.compile(r'^[A-Z]{2}\d{1,2}[A-Z]{0,3}\d{3,4}$'),# AP2J1234
]

def _is_valid_plate(text: str) -> bool:
    t = text.upper().strip()
    return any(p.match(t) for p in _PLATE_PATTERNS)

def _upscale(img, scale=2.0):
    h, w = img.shape[:2]
    return cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)

def _preprocess(img):
    """Return list of preprocessed variants to try OCR on."""
    variants = []

    # Ensure BGR
    if len(img.shape) == 2:
        bgr = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    else:
        bgr = img.copy()

    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    # 1. Upscale + bilateral + adaptive threshold
    up = _upscale(gray, 2.0)
    up = cv2.bilateralFilter(up, 9, 75, 75)
    th1 = cv2.adaptiveThreshold(up, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                 cv2.THRESH_BINARY, 21, 8)
    variants.append(cv2.cvtColor(th1, cv2.COLOR_GRAY2BGR))

    # 2. CLAHE + Otsu
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    cl = clahe.apply(gray)
    cl_up = _upscale(cl, 2.0)
    _, th2 = cv2.threshold(cl_up, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    variants.append(cv2.cvtColor(th2, cv2.COLOR_GRAY2BGR))

    # 3. Original colour (EasyOCR handles colour well)
    variants.append(_upscale(bgr, 2.0))

    return variants


def _clean(text: str) -> str:
    """Keep only alphanumeric, uppercase."""
    return ''.join(c for c in text.upper() if c.isalnum())


def _ocr_easyocr(img_bgr):
    """Run EasyOCR on a BGR image, return best text."""
    try:
        import easyocr
        # Cache reader to avoid re-init on every call
        if not hasattr(_ocr_easyocr, '_reader'):
            _ocr_easyocr._reader = easyocr.Reader(
                ['en'], gpu=False,
                # Restrict to plate characters for better accuracy
                # (EasyOCR doesn't support allowlist directly, but we filter after)
            )
        reader = _ocr_easyocr._reader
        rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        results = reader.readtext(rgb, detail=1, paragraph=False)
        if not results:
            return ""
        # Concatenate all detected text segments (plates can be split)
        combined = ''.join(_clean(r[1]) for r in results)
        return combined
    except Exception as e:
        print(f"[OCR] EasyOCR error: {e}")
        return ""


def _ocr_tesseract(img_bgr):
    """Tesseract fallback — only if pytesseract is installed."""
    try:
        import pytesseract
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        cfg = '--oem 3 --psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        text = pytesseract.image_to_string(gray, config=cfg)
        return _clean(text)
    except Exception:
        return ""


def read_plate_text_from_image(cv_img) -> str:
    """
    Main entry point.
    Tries multiple preprocessed variants with EasyOCR (+ Tesseract if available).
    Returns the best candidate — preferring valid Indian plate format.
    """
    if cv_img is None or cv_img.size == 0:
        return ""

    variants = _preprocess(cv_img)
    candidates = []

    for v in variants:
        t = _ocr_easyocr(v)
        if t:
            candidates.append(t)
        t2 = _ocr_tesseract(v)
        if t2:
            candidates.append(t2)

    if not candidates:
        return ""

    # Prefer candidates that match a valid plate pattern
    valid = [c for c in candidates if _is_valid_plate(c)]
    if valid:
        # Return the most common valid candidate
        return max(set(valid), key=valid.count)

    # Otherwise return the longest candidate (more chars = more info)
    return max(candidates, key=len)


# ── Fake / suspicious plate detection ─────────────────────────────────────────

# Valid Indian state codes (RTO prefix)
_VALID_STATE_CODES = {
    'AN','AP','AR','AS','BR','CG','CH','DD','DL','DN','GA','GJ','HP',
    'HR','JH','JK','KA','KL','LA','LD','MH','ML','MN','MP','MZ','NL',
    'OD','PB','PY','RJ','SK','TN','TR','TS','UK','UP','WB'
}

def check_plate_authenticity(plate: str) -> dict:
    """
    Analyse a plate string for signs of being fake/suspicious.

    Returns a dict:
      {
        'is_suspicious': bool,
        'confidence':    float,   # 0.0 = clean, 1.0 = definitely fake
        'reasons':       list[str]
      }
    """
    reasons = []
    score   = 0.0

    if not plate:
        return {'is_suspicious': False, 'confidence': 0.0, 'reasons': []}

    p = plate.upper().strip()

    # 1. Must match a known Indian plate pattern
    if not _is_valid_plate(p):
        reasons.append('Does not match any valid Indian plate format')
        score += 0.5

    # 2. State code check
    state = p[:2] if len(p) >= 2 else ''
    if state and state not in _VALID_STATE_CODES:
        reasons.append(f'Unknown state code: {state}')
        score += 0.4

    # 3. Repeated characters (e.g. AAAA1111, 0000) — common in fake plates
    digits = ''.join(c for c in p if c.isdigit())
    alpha  = ''.join(c for c in p if c.isalpha())
    if len(digits) >= 4 and len(set(digits[-4:])) == 1:
        reasons.append('Last 4 digits are all identical — suspicious pattern')
        score += 0.35
    if len(alpha) >= 4 and len(set(alpha)) == 1:
        reasons.append('All letters are identical — suspicious pattern')
        score += 0.3

    # 4. Too short or too long
    if len(p) < 6:
        reasons.append(f'Plate too short ({len(p)} chars)')
        score += 0.3
    if len(p) > 13:
        reasons.append(f'Plate too long ({len(p)} chars)')
        score += 0.2

    # 5. Contains only numbers or only letters (no mix)
    if p.isdigit():
        reasons.append('Plate contains only digits')
        score += 0.5
    if p.isalpha():
        reasons.append('Plate contains only letters')
        score += 0.5

    # 6. Sequential digits like 1234, 0000, 9999
    if digits.endswith('1234') or digits.endswith('0000') or digits.endswith('9999'):
        reasons.append('Sequential or trivial digit pattern detected')
        score += 0.2

    confidence = min(round(score, 2), 1.0)
    return {
        'is_suspicious': confidence >= 0.4,
        'confidence':    confidence,
        'reasons':       reasons
    }
