from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from database import get_connection
from ocr.ocr_engine import extract_text
from ocr.text_parser import parse_receipt_text
from ocr.document_classifier import classify_document
from ocr.pii_scrubber import scrub_pii
from ocr.utility_parser import parse_utility_bill
import shutil
import os

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def validate_items(items, ocr_total):
    """Flag suspicious prices before saving"""
    validated = []
    for item in items:
        price = item.get("price") or 0
        item["price"] = price
        warning = None

        if ocr_total and price > ocr_total:
            warning = f"Price Rs{price} exceeds receipt total, may be OCR error"
        if price > 10000:
            warning = (warning or "") + " Price unusually high, please verify"
        if price <= 0:
            warning = (warning or "") + " Price missing or zero, please verify"

        if warning:
            item["price_warning"] = warning.strip()

        validated.append(item)

    return [i for i in validated if i["price"] > 0]


def resolve_total(calculated, ocr_total):
    """
    Decide which total to use and what warning to show.
    Returns (total, total_warning)
    """
    if not ocr_total or ocr_total <= 0:
        return calculated, None

    difference = abs(ocr_total - calculated)

    if difference <= ocr_total * 0.10:
        return calculated, None
    elif difference <= 500:
        return ocr_total, (
            f"Some items may be missing or a service charge was not extracted. "
            f"Extracted items sum to Rs{calculated} but receipt shows Rs{ocr_total}. "
            f"Please review before confirming."
        )
    else:
        return ocr_total, (
            f"Significant difference detected (extracted Rs{calculated} "
            f"vs receipt Rs{ocr_total}). Please verify all items and prices."
        )


def save_entry_to_db(cur, user_id, source_name, total, file_path, expense_type, doc_type):
    """Helper to insert expense entry and return entry_id"""
    cur.execute("""
        INSERT INTO expense_entries
            (user_id, source_name, total_amount,
             image_path, entry_type, expense_type, document_type)
        VALUES (%s, %s, %s, %s, 'image', %s, %s)
        RETURNING entry_id
    """, (user_id, source_name, total, file_path, expense_type, doc_type))
    return cur.fetchone()[0]


@router.post("/scan-receipt/{user_id}")
async def scan_receipt(
    user_id: int,
    expense_type: str = Form(default="grocery"),
    file: UploadFile = File(...)
):
    file_path = f"{UPLOAD_DIR}/{file.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        # Step 1 — OCR locally, nothing leaves machine yet
        raw_text = extract_text(file_path)
        if not raw_text:
            raise HTTPException(
                status_code=400,
                detail="Could not extract text from image"
            )

        # Step 2 — Classify document type locally
        doc_type = classify_document(raw_text)
        print(f"=== Document type detected: {doc_type} ===")

        # Step 3 — Scrub PII before sending anywhere
        if doc_type == 'bank':
            safe_text = scrub_pii(raw_text, level='heavy')
        elif doc_type == 'utility':
            safe_text = scrub_pii(raw_text, level='standard')
        else:
            safe_text = raw_text

        # ── UTILITY BILL FLOW ──
        if doc_type == 'utility':
            utility_data = parse_utility_bill(safe_text)

            if "error" in utility_data:
                raise HTTPException(
                    status_code=400,
                    detail=f"Could not parse utility bill: {utility_data['error']}"
                )

            total = (
                utility_data.get("payable_within_due_date") or
                utility_data.get("payable_after_due_date") or 0
            )

            if total <= 0:
                raise HTTPException(
                    status_code=400,
                    detail="Could not extract payable amount from utility bill"
                )

            conn = get_connection()
            cur = conn.cursor()
            try:
                entry_id = save_entry_to_db(
                    cur, user_id,
                    utility_data.get("company", "Utility Bill"),
                    total, file_path, expense_type, "utility"
                )

                cur.execute("""
                    INSERT INTO expense_items
                        (entry_id, item_name, price, quantity)
                    VALUES (%s, %s, %s, %s)
                """, (
                    entry_id,
                    f"{utility_data.get('company', 'Utility')} - {utility_data.get('bill_month', '')}".strip(" -"),
                    total,
                    1
                ))

                conn.commit()

                return {
                    "message": "Utility bill scanned successfully",
                    "entry_id": entry_id,
                    "document_type": "utility",
                    "company": utility_data.get("company"),
                    "bill_month": utility_data.get("bill_month"),
                    "consumer_no": utility_data.get("consumer_no"),
                    "payable_within_due_date": utility_data.get("payable_within_due_date"),
                    "payable_after_due_date": utility_data.get("payable_after_due_date"),
                    "due_date": utility_data.get("due_date"),
                    "total": total,
                    "needs_review": False,
                    "raw_text": raw_text
                }

            except Exception as e:
                conn.rollback()
                raise HTTPException(status_code=500, detail=str(e))
            finally:
                cur.close()
                conn.close()

        # ── REGULAR RECEIPT / BANK SLIP FLOW ──
        parsed = parse_receipt_text(safe_text)

        if not parsed["items"]:
            raise HTTPException(
                status_code=400,
                detail=f"No items found. Raw text: {raw_text[:500]}"
            )

        ocr_total = parsed["total"]
        items = validate_items(parsed["items"], ocr_total)
        calculated_total = round(sum(i["price"] for i in items), 2)
        total, total_warning = resolve_total(calculated_total, ocr_total)

        conn = get_connection()
        cur = conn.cursor()
        try:
            entry_id = save_entry_to_db(
                cur, user_id,
                parsed["store_name"],
                total, file_path, expense_type, doc_type
            )

            for item in items:
                cur.execute("""
                    INSERT INTO expense_items
                        (entry_id, item_name, price, quantity)
                    VALUES (%s, %s, %s, %s)
                """, (
                    entry_id,
                    item["item_name"],
                    item["price"],
                    item["quantity"]
                ))

            conn.commit()

            return {
                "message": "Receipt scanned successfully",
                "entry_id": entry_id,
                "store_name": parsed["store_name"],
                "document_type": doc_type,
                "items": items,
                "total": total,
                "total_warning": total_warning,
                "needs_review": total_warning is not None,
                "raw_text": raw_text
            }

        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            cur.close()
            conn.close()

    finally:
        if os.path.exists(file_path):
            os.remove(file_path)