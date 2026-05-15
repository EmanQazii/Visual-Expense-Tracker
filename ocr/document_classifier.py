import re

BANK_PATTERNS = [
    r'\b(ATM|debit|credit)\b',
    r'\bcard\s*no\b',
    r'\baccount\s*no\b',
    r'\btransaction\s*id\b',
    r'\bIBAN\b',
    r'\bwithdrawal\b',
    r'\bdeposit\b',
    r'\bavailable\s*balance\b',
    r'\bauthorization\s*code\b',
    r'\b(HBL|UBL|MCB|ABL|Meezan|Allied|Faysal)\b',
]

UTILITY_PATTERNS = [
    r'\b(IESCO|LESCO|KESC|MEPCO|PESCO|GEPCO|HESCO|QESCO)\b',
    r'\b(SNGPL|SSGC)\b',
    r'\bconsumer\s*(id|no|number)\b',
    r'\bunits\s*consumed\b',
    r'\bmeter\s*rent\b',
    r'\bfuel\s*price\s*adjustment\b',
    r'\belectricity\s*(bill|charges)\b',
    r'\bgas\s*(bill|charges)\b',
    r'\bpayable\s*(within|after)\s*due\s*date\b',
    r'\bislam?abad\s*electric\b',
]

def classify_document(raw_text: str) -> str:
    """Returns: 'bank', 'utility', or 'receipt'"""
    
    bank_score = sum(1 for p in BANK_PATTERNS 
                     if re.search(p, raw_text, re.IGNORECASE))
    utility_score = sum(1 for p in UTILITY_PATTERNS 
                        if re.search(p, raw_text, re.IGNORECASE))

    print(f"=== Classifier: bank_score={bank_score}, utility_score={utility_score} ===")

    if bank_score >= 2:
        return 'bank'
    elif utility_score >= 2:
        return 'utility'
    else:
        return 'receipt'