import pytesseract
import cv2
from ocr.preprocessor import preprocess

# Tell pytesseract where Tesseract is installed on Windows
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def extract_text(image_path):
    """
    Full pipeline: preprocess image then extract text.
    Returns raw text string from Tesseract.
    """
    # Run DIP pipeline
    cleaned = preprocess(image_path)

    # Tesseract config:
    # --psm 6 = assume single block of text (good for receipts)
    # --oem 3 = use LSTM neural network engine
    config = '--psm 6 --oem 3'

    raw_text = pytesseract.image_to_string(cleaned, config=config)
    return raw_text.strip()