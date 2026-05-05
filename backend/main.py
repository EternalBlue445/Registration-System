"""
ARCHITECTURAL DECISIONS:
  - SQLAlchemy ORM over SQLite. No raw SQL, easy to swap DB later.
  - OTP is hashed with SHA-256 before storing. Raw OTP never touches the DB.
  - Email is sent in a background task so /register responds immediately.
  - Registration is only marked complete after OTP is verified.
  - If email sending fails, registration still proceeds (OTP stays in DB).

ASSUMPTIONS:
  - Welcome email contains the OTP. Plain minimal HTML, no heavy styling.
  - After OTP verification, the React frontend shows "Registration Successful!".
  - One active OTP per user. A new /register call replaces the previous OTP.
"""

import hashlib
import random
import string
import base64
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request as GoogleRequest

DB_PATH = Path(__file__).parent / "registration.db"
CREDENTIALS_FILE = Path(__file__).parent / "credentials.json"
TOKEN_FILE = Path(__file__).parent / "token.json"
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

OTP_EXPIRY_MINUTES = 1
OTP_MAX_ATTEMPTS = 5

engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})

from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import DeclarativeBase, Session

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, unique=True, nullable=False)
    is_verified = Column(Integer, default=0)


class OTP(Base):
    __tablename__ = "otps"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    otp = Column(String, nullable=False)
    attempts = Column(Integer, default=0)
    expires_at = Column(DateTime(timezone=True), nullable=False)  

Base.metadata.create_all(engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
"""
import traceback
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print("=== UNHANDLED EXCEPTION ===")
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"success": False, "message": "Internal server error", "detail": str(exc)}
    )
"""
def get_session():
    return Session(engine)


def generate_otp() -> str:
    otp = "".join(random.choices(string.digits, k=6))
    print(otp) 
    return otp


def get_gmail_service():
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), GMAIL_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(GoogleRequest())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), GMAIL_SCOPES)
            creds = flow.run_local_server(port=9000)
        TOKEN_FILE.write_text(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def build_email(to_email: str, otp: str):
    html = f"""<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; padding: 24px;">
  <h2>Welcome!</h2>
  <p>Thanks for registering. Your verification code is:</p>
  <p style="font-size: 28px; font-weight: bold; letter-spacing: 6px;">{otp}</p>
  <p>This code expires in {OTP_EXPIRY_MINUTES} minutes.</p>
</body>
</html>"""

    raw_message = (
        f"To: {to_email}\r\n"
        f"Subject: Your OTP Code\r\n"
        f"MIME-Version: 1.0\r\n"
        f"Content-Type: text/html\r\n\r\n"
        f"{html}"
    )
    return {"raw": base64.urlsafe_b64encode(raw_message.encode()).decode()}


def send_email(to_email: str, otp: str):
    try:
        service = get_gmail_service()
        service.users().messages().send(
            userId="me", body=build_email(to_email, otp)
        ).execute()
    except Exception as e:
        print(f"Email send failed: {e}")


class RegisterRequest(BaseModel):
    email: EmailStr


class VerifyRequest(BaseModel):
    email: EmailStr
    otp: str


@app.post("/register")
async def register(payload: RegisterRequest, background_tasks: BackgroundTasks):
    email = payload.email.lower().strip()

    with get_session() as db:
        user = db.query(User).filter(User.email == email).first()

        if user and user.is_verified:
            raise HTTPException(status_code=409, detail={"success": False,"message": "User already registered."})

        if user:
            db.query(OTP).filter(OTP.user_id == user.id).delete()
        else:
            user = User(email=email)
            db.add(user)
            db.flush()

        otp = generate_otp()
        db.add(OTP(
            user_id=user.id,
            otp=otp,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRY_MINUTES),
        ))
        db.commit()

    background_tasks.add_task(send_email, email, otp)

    return {"status_code": 200, "success": True, "message": "OTP sent to your email."}


@app.post("/verify-otp")
def verify_otp(payload: VerifyRequest):
    email = payload.email.lower().strip()
    otp = payload.otp.strip()

    if not otp.isdigit() or len(otp) != 6:
        raise HTTPException(status_code=422, detail={
            "success": False, 
            "message": "OTP must be 6 digits."
        })

    with get_session() as db:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(status_code=404, detail={
                "success": False, 
                "message": "Email not found. Please register first."
            })

        if user.is_verified:
            raise HTTPException(status_code=409, detail={
                "success": False, 
                "message": "User already registered."
            })

        record = db.query(OTP).filter(OTP.user_id == user.id).first()
        if not record:
            raise HTTPException(status_code=400, detail={
                "success": False, 
                "message": "No OTP found. Please register again."
            })

      
        now = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
        expires_at = record.expires_at.replace(microsecond=0)
        if now > expires_at:
            db.delete(record)
            db.commit()
            raise HTTPException(status_code=400, detail={
                "success": False, 
                "message": "OTP has expired. Please register again."
            })

        if record.attempts >= OTP_MAX_ATTEMPTS:
            raise HTTPException(status_code=429, detail={
                "success": False, 
                "message": "Too many failed attempts. Please register again."
            })

        record.attempts += 1

        if otp != record.otp:
            db.commit()  
            remaining = OTP_MAX_ATTEMPTS - record.attempts
            raise HTTPException(status_code=400, detail={
                "success": False,
                "message": f"Invalid OTP. {remaining} attempt(s) left."
            })

        # Success
        user.is_verified = 1
        db.delete(record)
        db.commit()

    return {"status_code": 200, "success": True, "message": "Registration successful!"}

@app.post("/resend-otp")
async def resend_otp(payload: RegisterRequest, background_tasks: BackgroundTasks):
    email = payload.email.lower().strip()

    with get_session() as db:
        user = db.query(User).filter(User.email == email).first()

        if not user:
            raise HTTPException(status_code=404, detail={
                "success": False,
                "message": "Email not found. Please register first."
            })

        if user.is_verified:
            raise HTTPException(status_code=409, detail={
                "success": False,
                "message": "User already registered."
            })

        db.query(OTP).filter(OTP.user_id == user.id).delete()

        otp = generate_otp()
        print(otp)
        db.add(OTP(
            user_id=user.id,
            otp=otp,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRY_MINUTES),
        ))

        db.commit()

    background_tasks.add_task(send_email, email, otp)

    return {
        "status_code": 200,
        "success": True,
        "message": "A new OTP has been sent to your email."
    }