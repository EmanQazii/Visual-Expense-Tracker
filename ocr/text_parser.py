# text_parser.py

from groq import Groq
import json
import re
import os

client = Groq(api_key=os.environ["GROQ_API_KEY"])

SYSTEM_PROMPT = """You are a receipt parser. Extract structured data from OCR text of Pakistani receipts.

Return ONLY valid JSON, no markdown, no explanation:
{
  "store_name": "string or null",
  "items": [
    {"item_name": "string", "price": number, "quantity": number}
  ],
  "total": number or null
}

Rules:
- price is the TOTAL price for that line (qty x unit price)
- quantity defaults to 1 if not shown or if garbled, never use 0
- Ignore headers, footers, addresses, tax lines, NTN/FBR numbers
- Handle Rs, PKR, or bare numbers as prices
- If OCR garbled a word but its clearly an item, include your best guess
- Return empty items array if truly nothing found, never fabricate items
- CRITICAL: Lines containing Total, Totals, Sales Tax, Net Amount,
  Payment, Balance, Subtotal, Service Charges are NOT items, ignore them completely
- CRITICAL: T.Bill, T Bill, TBill, POS.S.Fee, NetBill, Net Bill, Cash Rec,
  Cash Return, RUPEES, Products Quantity, FBR Invoice are NOT items, ignore them
- CRITICAL: Never duplicate items. Each product code (10-digit number) = one item only
- The last price column is the net amount for that item
- If a line looks like a running total or summary, skip it
- Clean item names: remove trailing single characters, symbols, or noise
- Clean store names: fix obvious OCR mistakes like ? instead of z, 0 instead of O
- CRITICAL for total: Use Net Amount or Gross Total as the total, NOT Payment Received
  or Cash Received. Payment Received is what the customer paid, not what was owed.
  Priority order: Net Amount > Gross Total > Subtotal > first Total found"""


def clean_ocr_noise(text: str) -> str:
    """Remove common OCR noise characters from receipt text"""
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        # Remove lone noise characters at start/end of lines
        line = re.sub(r'^\s*[|\\!\/\[\]{}]\s*', '', line)
        line = re.sub(r'\s*[|\\!\/\[\]{}]\s*$', '', line)
        
        # Remove lines that are just noise (no alphanumeric content)
        if not re.search(r'[a-zA-Z0-9]', line):
            continue
            
        # Remove lines that are just single characters
        if len(line.strip()) <= 1:
            continue
            
        cleaned_lines.append(line.strip())
    
    return '\n'.join(cleaned_lines)


def parse_receipt_text(raw_text: str) -> dict:
    if not raw_text or not raw_text.strip():
        return {"store_name": None, "items": [], "total": None, "raw_text": raw_text}

    # Clean before sending to LLM
    cleaned_text = clean_ocr_noise(raw_text)

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Parse this receipt OCR text:\n\n{cleaned_text}"}
            ],
            temperature=0,
            max_tokens=1024
        )

        response_text = response.choices[0].message.content.strip()
        response_text = re.sub(r'^```(?:json)?\s*', '', response_text)
        response_text = re.sub(r'\s*```$', '', response_text)

        parsed = json.loads(response_text)

        return {
            "store_name": parsed.get("store_name"),
            "items": parsed.get("items", []),
            "total": parsed.get("total"),
            "raw_text": raw_text  # keep original raw for debugging
        }

    except json.JSONDecodeError:
        return {
            "store_name": None,
            "items": [],
            "total": None,
            "raw_text": raw_text,
            "parse_error": "Model returned non-JSON"
        }
    except Exception as e:
        return {
            "store_name": None,
            "items": [],
            "total": None,
            "raw_text": raw_text,
            "parse_error": str(e)
        }
