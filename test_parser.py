# test_parser.py
from dotenv import load_dotenv
load_dotenv()

from ocr.text_parser import parse_receipt_text

fake_ocr = """
IMTIAZ SUPER STORE
NTN: 1234567

1  Milk 1L          Rs 180
2  Bread             Rs 95
3  Eggs 12pcs       Rs 320

Total: Rs 595
"""

result = parse_receipt_text(fake_ocr)
print(result)