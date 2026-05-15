# ocr/pii_scrubber.py

import re

def scrub_pii(text: str, level: str = 'standard') -> str:
    """
    level = 'standard'  → remove account numbers, CNICs, IBANs
    level = 'heavy'     → also remove amounts, dates, names
    """
    # Always scrub these regardless of level
    text = re.sub(r'\d{5}-\d{7}-\d', '[CNIC]', text)
    text = re.sub(r'PK\d{2}[A-Z0-9]{16,}', '[IBAN]', text)
    text = re.sub(r'\b\d{12,16}\b', '[ACCOUNT]', text)
    text = re.sub(r'(\+92|0)[0-9]{9,10}', '[PHONE]', text)
    text = re.sub(r'[\w.-]+@[\w.-]+\.\w+', '[EMAIL]', text)
    
    if level == 'heavy':
        # Also mask card numbers (16 digits with spaces)
        text = re.sub(r'\b\d{4}[\s-]\d{4}[\s-]\d{4}[\s-]\d{4}\b', 
                      '[CARD]', text)
        # Mask authorization/transaction codes
        text = re.sub(r'(auth|txn|transaction|ref)\s*[:#]?\s*\d+', 
                      r'\1: [CODE]', text, flags=re.IGNORECASE)
        # Mask balance amounts
        text = re.sub(r'(balance|available|withdrawal|deposit)\s*:?\s*[\d,]+\.?\d*', 
                      r'\1: [AMOUNT]', text, flags=re.IGNORECASE)
    
    return text