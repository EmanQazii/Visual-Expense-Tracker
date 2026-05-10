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
- quantity defaults to 1 if not shown
- Ignore headers, footers, addresses, tax lines, NTN/FBR numbers
- Handle Rs, PKR, or bare numbers as prices
- If OCR garbled a word but its clearly an item, include your best guess
- Return empty items array if truly nothing found, never fabricate items"""


def parse_receipt_text(raw_text: str) -> dict:
    if not raw_text or not raw_text.strip():
        return {"store_name": None, "items": [], "total": None, "raw_text": raw_text}

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Parse this receipt OCR text:\n\n{raw_text}"}
            ],
            temperature=0,        # zero temp = consistent outputs, no creativity
            max_tokens=1024
        )

        response_text = response.choices[0].message.content.strip()

        # Strip markdown fences if model adds them anyway
        response_text = re.sub(r'^```(?:json)?\s*', '', response_text)
        response_text = re.sub(r'\s*```$', '', response_text)

        parsed = json.loads(response_text)

        return {
            "store_name": parsed.get("store_name"),
            "items": parsed.get("items", []),
            "total": parsed.get("total"),
            "raw_text": raw_text
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