"""
OCR service — layer 5 of the architecture (Tesseract).

Reads a scanned/photographed discharge summary and returns raw text.
This is the first stage of the document pipeline; its output feeds the
NLP / Medical NER stage (nlp_service.py) and then the LLM stage
(llm_service.py).
"""
import io

import pytesseract
from PIL import Image


def extract_text(file_bytes: bytes) -> str:
    """Run Tesseract OCR on an uploaded image (JPEG/PNG/etc.) and return the extracted text."""
    image = Image.open(io.BytesIO(file_bytes))
    if image.mode != "RGB":
        image = image.convert("RGB")
    text = pytesseract.image_to_string(image)
    return text.strip()
