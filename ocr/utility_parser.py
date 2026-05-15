from groq import Groq
import json
import re
import os

client = Groq(api_key=os.environ["GROQ_API_KEY"])

UTILITY_PROMPT = """You are parsing a Pakistani utility bill (electricity, gas, or water).
Extract ONLY these specific fields.

Return ONLY valid JSON, no markdown, no explanation:
{
  "utility_type": "electricity|gas|water|other",
  "company": "string or null",
  "bill_month": "string or null",
  "consumer_no": "string or null",
  "payable_within_due_date": number or null,
  "payable_after_due_date": number or null,
  "due_date": "string or null"
}

Rules:
- payable_within_due_date is the amount if paid on time
- payable_after_due_date is the amount if paid late  
- Ignore all charge breakdowns, taxes, surcharges, units consumed
- For company look for: IESCO, LESCO, KESC, SNGPL, SSGC, GEPCO, MEPCO, PESCO
- consumer_no may be labeled as Consumer ID, Reference No, Account No, CNIC
- bill_month format: MMM YYYY like Jul 2022
- If a field cannot be found return null, never guess"""


def parse_utility_bill(raw_text: str) -> dict:
    if not raw_text or not raw_text.strip():
        return {"error": "Empty text"}

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": UTILITY_PROMPT},
                {"role": "user", "content": f"Parse this utility bill OCR text:\n\n{raw_text}"}
            ],
            temperature=0,
            max_tokens=512
        )

        response_text = response.choices[0].message.content.strip()
        response_text = re.sub(r'^```(?:json)?\s*', '', response_text)
        response_text = re.sub(r'\s*```$', '', response_text)

        parsed = json.loads(response_text)

        # Validate we got at least an amount
        if not parsed.get("payable_within_due_date") and not parsed.get("payable_after_due_date"):
            return {"error": "Could not extract payable amount from bill"}

        return parsed

    except json.JSONDecodeError:
        return {"error": "Model returned non-JSON"}
    except Exception as e:
        return {"error": str(e)}