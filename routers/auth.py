from fastapi import APIRouter, HTTPException
from database import get_connection
from models.schemas import UserRegister, UserLogin
from passlib.context import CryptContext

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

@router.post("/register")
def register(user: UserRegister):
    conn = get_connection()
    cur = conn.cursor()
    try:
        # Check if email already exists
        cur.execute("SELECT user_id FROM users WHERE email = %s", (user.email,))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="Email already registered")

        hashed = pwd_context.hash(user.password[:72])

        cur.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (%s, %s, %s) RETURNING user_id",
            (user.name, user.email, hashed)
        )
        user_id = cur.fetchone()[0]
        conn.commit()
        return {"message": "User registered successfully", "user_id": user_id}

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

@router.post("/login")
def login(user: UserLogin):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT user_id, password_hash FROM users WHERE email = %s",
            (user.email,)
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")

        if not pwd_context.verify(user.password, row[1]):
            raise HTTPException(status_code=401, detail="Incorrect password")

        return {"message": "Login successful", "user_id": row[0]}

    finally:
        cur.close()
        conn.close()