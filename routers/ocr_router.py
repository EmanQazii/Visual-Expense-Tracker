from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from database import get_connection
from ocr.ocr_engine import extract_text
from ocr.text_parser import parse_receipt_text
import shutil
import os

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/scan-receipt/{user_id}")
async def scan_receipt(
    user_id: int,
    expense_type: str = Form(default="grocery"),
    file: UploadFile = File(...)
):
    # Save uploaded file temporarily
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
        # Save to database with transaction
        conn = get_connection()
        cur = conn.cursor()

        try:
            # Calculate total from items (more reliable than OCR read)
            calculated_total = round(sum(
                i["price"] for i in parsed["items"]
            ), 2)

            # Compare with OCR-read total if available
            ocr_total = parsed["total"]
            total_warning = None

            if ocr_total and ocr_total > 0:
                difference = abs(calculated_total - ocr_total)
                # If difference is more than 5% flag a warning
                if difference > (calculated_total * 0.05):
                    total_warning = (
                        f"OCR read total Rs{ocr_total} but "
                        f"calculated total from items is Rs{calculated_total}. "
                        f"Please verify."
                    )
                total = calculated_total
            else:
                total = calculated_total

            # Insert entry
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

            # Insert items
            for item in parsed["items"]:
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
                "items": parsed["items"],
                "total": total,
                "total_warning": total_warning,
                "raw_text": raw_text
            }

        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            cur.close()
            conn.close()

    finally:
        # Clean up temp file
        if os.path.exists(file_path):
            os.remove(file_path)