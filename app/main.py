from fastapi import FastAPI
from app.routers import auth
from app.routers import expenses

app = FastAPI(title="Expense Tracker API")

app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(expenses.router, prefix="/expenses", tags=["Expenses"])

@app.get("/")
def root():
    return {"message": "Expense Tracker API is running"}