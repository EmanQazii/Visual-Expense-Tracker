from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from database import get_connection
from ocr.ocr_engine import extract_text
from ocr.text_parser import parse_receipt_text
import shutil
import os

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def validate_items(items, ocr_total):
    """Flag suspicious prices before saving"""
    validated = []
    for item in items:
        price = item["price"]
        warning = None

        # Single item costs more than entire receipt
        if ocr_total and price > ocr_total:
            warning = f"Price Rs{price} exceeds receipt total, may be OCR error"

        # Suspiciously large price
        if price > 10000:
            warning = (warning or "") + " Price unusually high, please verify"

        if warning:
            item["price_warning"] = warning.strip()

        validated.append(item)
    return validated


def resolve_total(calculated, ocr_total):
    """
    Decide which total to use and what warning to show.
    Returns (total, total_warning)
    """
    if not ocr_total or ocr_total <= 0:
        return calculated, None

    difference = abs(ocr_total - calculated)
    threshold_10pct = ocr_total * 0.10

    if difference <= threshold_10pct:
        # Close enough — trust calculated (item sum is more reliable)
        return calculated, None

    elif difference <= 500:
        # Noticeable gap — likely a missing item or service charge
        return ocr_total, (
            f"Some items may be missing or a service charge was not extracted. "
            f"Extracted items sum to Rs{calculated} but receipt shows Rs{ocr_total}. "
            f"Please review before confirming."
        )

    else:
        # Large gap — something seriously wrong with OCR
        return ocr_total, (
            f"Large discrepancy detected (Rs{calculated} extracted vs Rs{ocr_total} on receipt). "
            f"Please verify all items manually."
        )


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
        # Run OCR pipeline
        raw_text = extract_text(file_path)

        if not raw_text:
            raise HTTPException(
                status_code=400,
                detail="Could not extract text from image"
            )

        # Parse text into structured data
        parsed = parse_receipt_text(raw_text)

        if not parsed["items"]:
            raise HTTPException(
                status_code=400,
                detail=f"No items found. Raw text: {raw_text[:500]}"
            )

        ocr_total = parsed["total"]

        # Validate individual item prices
        items = validate_items(parsed["items"], ocr_total)

        # Calculate sum of extracted items
        calculated_total = round(sum(i["price"] for i in items), 2)

        # Resolve which total to use
        total, total_warning = resolve_total(calculated_total, ocr_total)

        # Save to database
        conn = get_connection()
        cur = conn.cursor()

        try:
            cur.execute("""
                INSERT INTO expense_entries
                    (user_id, source_name, total_amount,
                     image_path, entry_type, expense_type)
                VALUES (%s, %s, %s, %s, 'image', %s)
                RETURNING entry_id
            """, (
                user_id,
                parsed["store_name"],
                total,
                file_path,
                expense_type
            ))

            entry_id = cur.fetchone()[0]

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