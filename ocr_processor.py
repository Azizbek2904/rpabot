"""📸 OCR Processor — FINAL | BTEC L6 | PDP University"""
import re, io, logging
from datetime import datetime
log = logging.getLogger(__name__)
try:
    import pytesseract; from PIL import Image; ENG = "tesseract"
except ImportError:
    ENG = "none"
try:
    from PIL import Image
except: Image = None

class OCRProcessor:
    def __init__(self):
        self.eng = ENG

    def process_receipt(self, b):
        try:
            t = self._ocr(b)
            if not t: return {'amount': 0, 'raw_text': '', 'confidence': 0}
            return {'amount': self._amt(t), 'date': self._date(t), 'raw_text': t[:500], 'confidence': 0.8}
        except Exception as e:
            return {'amount': 0, 'raw_text': str(e), 'confidence': 0}

    def _ocr(self, b):
        if self.eng == "tesseract":
            try: return pytesseract.image_to_string(Image.open(io.BytesIO(b)).convert('L'), lang='uzb+rus+eng')
            except:
                try: return pytesseract.image_to_string(Image.open(io.BytesIO(b)).convert('L'))
                except: return ""
        return ""

    def _amt(self, t):
        for p in [r'(?:summa|amount)\s*[:=]?\s*([\d\s,\.]+)',
                  r'(\d{1,3}(?:[,\s]\d{3})+(?:\.\d{2})?)',
                  r'(\d{5,})']:
            for m in re.findall(p, t, re.IGNORECASE):
                try:
                    v = float(m.replace(',','').replace(' ',''))
                    if v > 1000: return v
                except: continue
        return 0

    def _date(self, t):
        for p in [r'(\d{2}[./]\d{2}[./]\d{4})', r'(\d{4}-\d{2}-\d{2})']:
            m = re.search(p, t)
            if m: return m.group(1)
        return datetime.now().strftime('%Y-%m-%d')

    def process_invoice_pdf(self, b):
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(b)) as pdf:
                t = "\n".join([p.extract_text() or "" for p in pdf.pages])
            if not t: return None
            return {'amount': self._amt(t), 'date': self._date(t), 'raw_text': t[:500]}
        except: return None
