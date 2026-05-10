from fastapi import FastAPI
from routers import auth
from routers import expenses
from routers import auth, expenses, ocr_router

app = FastAPI(title="Expense Tracker API")

app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(expenses.router, prefix="/expenses", tags=["Expenses"])
app.include_router(ocr_router.router, prefix="/ocr", tags=["OCR"])

@app.get("/")
def root():
    return {"message": "Expense Tracker API is running"}