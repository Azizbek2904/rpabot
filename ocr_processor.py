"""
📸 OCR Processor — FIXED
Author: BTEC L6 | PDP University
Fixes: removed duplicate import, added image preprocessing, shared amount extraction
"""
import re
import io
import logging
from datetime import datetime

log = logging.getLogger(__name__)

# Import PIL once
try:
    from PIL import Image, ImageEnhance, ImageFilter
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    Image = None

# Import Tesseract
try:
    import pytesseract
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False

# Import pdfplumber
try:
    import pdfplumber
    HAS_PDF = True
except ImportError:
    HAS_PDF = False


class OCRProcessor:
    """OCR processor for payment receipts (images and PDFs)."""

    def __init__(self):
        self.engine = "tesseract" if (HAS_TESSERACT and HAS_PIL) else "none"
        if self.engine == "none":
            log.warning("⚠️ OCR unavailable: pip install pytesseract Pillow")

    def process_receipt(self, image_bytes):
        """Process receipt image and extract data."""
        try:
            text = self._ocr(image_bytes)
            if not text:
                return {"amount": 0, "raw_text": "", "confidence": 0, "date": ""}

            return {
                "amount": self.extract_amount(text),
                "date": self._extract_date(text),
                "raw_text": text[:500],
                "confidence": 0.8 if len(text) > 20 else 0.3,
            }
        except Exception as e:
            log.error(f"OCR process: {e}")
            return {"amount": 0, "raw_text": str(e), "confidence": 0, "date": ""}

    def process_invoice_pdf(self, pdf_bytes):
        """Process PDF receipt and extract data."""
        if not HAS_PDF:
            log.warning("pdfplumber not installed")
            return None
        try:
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                text = "\n".join([page.extract_text() or "" for page in pdf.pages])
            if not text.strip():
                return None
            return {
                "amount": self.extract_amount(text),
                "date": self._extract_date(text),
                "raw_text": text[:500],
            }
        except Exception as e:
            log.error(f"PDF process: {e}")
            return None

    def _ocr(self, image_bytes):
        """Run OCR on image bytes with preprocessing."""
        if self.engine != "tesseract":
            return ""

        try:
            img = Image.open(io.BytesIO(image_bytes))

            # Preprocessing for better OCR accuracy
            img = img.convert("L")  # Grayscale
            img = ImageEnhance.Contrast(img).enhance(2.0)  # Increase contrast
            img = ImageEnhance.Sharpness(img).enhance(2.0)  # Sharpen
            img = img.filter(ImageFilter.MedianFilter(size=3))  # Reduce noise

            # Auto-rotate if needed
            try:
                osd = pytesseract.image_to_osd(img)
                angle = int(re.search(r"Rotate: (\d+)", osd).group(1))
                if angle:
                    img = img.rotate(-angle, expand=True)
            except Exception:
                pass

            # Try with Uzbek+Russian+English
            try:
                return pytesseract.image_to_string(img, lang="uzb+rus+eng")
            except Exception:
                return pytesseract.image_to_string(img)
        except Exception as e:
            log.error(f"OCR: {e}")
            return ""

    @staticmethod
    def extract_amount(text):
        """Extract monetary amount from text. Shared with AIEngine."""
        patterns = [
            r"(?:summa|amount|sum|jami|total)\s*[:=]?\s*([\d\s,\.]+)",
            r"(\d{1,3}(?:[,\s]\d{3})+(?:\.\d{2})?)",
            r"(\d{5,})",
        ]
        for pattern in patterns:
            for match in re.findall(pattern, text, re.IGNORECASE):
                try:
                    value = float(match.replace(",", "").replace(" ", ""))
                    if value > 1000:
                        return value
                except (ValueError, AttributeError):
                    continue
        return 0

    @staticmethod
    def _extract_date(text):
        """Extract date from text."""
        for pattern in [r"(\d{2}[./]\d{2}[./]\d{4})", r"(\d{4}-\d{2}-\d{2})"]:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return datetime.now().strftime("%Y-%m-%d")
