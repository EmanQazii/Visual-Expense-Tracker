from fastapi import APIRouter, HTTPException
from app.database import get_connection
from app.models.schemas import ManualEntryInput

router = APIRouter()

@router.post("/add-manual/{user_id}")
def add_manual_expense(user_id: int, entry: ManualEntryInput):
    # Validate items exist
    if not entry.items:
        raise HTTPException(status_code=400, detail="At least one item is required")

    for item in entry.items:
        if item.price <= 0:
            raise HTTPException(status_code=400, detail=f"Invalid price for item: {item.item_name}")

    conn = get_connection()
    cur = conn.cursor()

    try:
        # BEGIN TRANSACTION
        total = sum(i.price * i.quantity for i in entry.items)

        # Insert entry
        cur.execute("""
            INSERT INTO expense_entries 
                (user_id, source_name, entry_date, total_amount, entry_type, expense_type)
            VALUES (%s, %s, %s, %s, 'manual', %s)
            RETURNING entry_id
        """, (user_id, entry.source_name, entry.entry_date, total, entry.expense_type))

        entry_id = cur.fetchone()[0]

        # Insert all items
        for item in entry.items:
            cur.execute("""
                INSERT INTO expense_items 
                    (entry_id, item_name, price, quantity, category_id)
                VALUES (%s, %s, %s, %s, %s)
            """, (entry_id, item.item_name, item.price, item.quantity, item.category_id))

        # COMMIT  only if everything succeeded
        conn.commit()
        return {
            "message": "Expense added successfully",
            "entry_id": entry_id,
            "total": total
        }

    except HTTPException:
        raise
    except Exception as e:
        # ROLLBACK  if anything failed, nothing gets saved
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()


@router.get("/get-expenses/{user_id}")
def get_expenses(user_id: int):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT 
                e.entry_id,
                e.source_name,
                e.entry_date,
                e.total_amount,
                e.expense_type,
                e.entry_type
            FROM expense_entries e
            WHERE e.user_id = %s
            ORDER BY e.entry_date DESC
        """, (user_id,))

        rows = cur.fetchall()
        expenses = []
        for row in rows:
            expenses.append({
                "entry_id": row[0],
                "source_name": row[1],
                "entry_date": str(row[2]),
                "total_amount": float(row[3]) if row[3] else 0,
                "expense_type": row[4],
                "entry_type": row[5]
            })
        return {"expenses": expenses}

    finally:
        cur.close()
        conn.close()