from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import date

# Auth
class UserRegister(BaseModel):
    name: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

# Expense Items
class ExpenseItemInput(BaseModel):
    item_name: str
    price: float
    quantity: int = 1
    category_id: Optional[int] = None

# Manual Entry
class ManualEntryInput(BaseModel):
    source_name: Optional[str] = None
    entry_date: Optional[date] = None
    expense_type: str = "other"
    items: List[ExpenseItemInput]