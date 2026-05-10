import pytesseract
import cv2
from ocr.preprocessor import preprocess

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def extract_text(image_path):
    cleaned = preprocess(image_path)
    config = '--psm 6 --oem 3'
    raw_text = pytesseract.image_to_string(cleaned, config=config)
    return raw_text.strip()