# Registration System

A full-stack user registration system with email OTP verification built with FastAPI + React.

## Architecture Overview

```
registration-system/
├── backend/
│   ├── main.py         
│   ├── requirements.txt
│   └── credentials.json
├── frontend/
│   ├── App.jsx      
│   ├── index.css   
│   └── main.jsx    
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── tests/
│   └── test_api.py      # Pytest test suite
├── start.bat            # Windows launcher
└── README.md
```

### Registration Flow

```
User enters email
      │
      ▼
POST /register
  ├─ Already verified? → 409 (User already registered)
  ├─ New / pending?    → Insert/reset user + OTP in DB
  │                       → Return 200 immediately
  │                       → Send email asynchronously (background task)
      │
      ▼
User enters 6-digit OTP
      │
      ▼
POST /verify-otp
  ├─ Not found?        → 404
  ├─ Expired?          → 400
  ├─ Too many tries?   → 429
  ├─ Wrong OTP?        → 400 (remaining attempts shown)
  └─ Correct OTP?      → Mark user verified, delete OTP → 200 ✅
```

---

## Architecture Decisions

| Decision | Rationale |
|---|---|
| **SQLite (SqlAlchemy)** | Database operations were done with SqlAlchemy ORM |
| **FastAPI BackgroundTasks** | Email sends are non-blocking |
| **Re-registration** | Re-registering while pending resets the OTP cleanly |

---

## Prerequisites

- Python
- Node.js
- A Google Cloud project with Gmail API enabled

## Installation & Running

### Backend

```bash
cd backend
pip install -r requirements.txt

uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173)

### Windows (both at once)

```bat
start.bat
```

---

## Running Tests

```bash
# From the project root:
pytest tests/test_api.py -v
```
### What's tested

| Category | Tests |
|---|---|
| Registration flow | New user, already verified (409), pending reset, invalid email |
| OTP verification | Correct OTP, wrong OTP, expired OTP, unknown email, too many attempts |
| Error handling | 404, 409, 422, 429 shapes; `success` field in all responses |
| JSON responses | All success paths include `"success": true` |

---

## API Reference

### `POST /register`
```json
{ "email": "user@example.com" }
```
**200** `{ "success": true, "message": "OTP sent..." }`
**409** `{ "detail": { "success": false, "message": "User already registered" } }`

### `POST /verify-otp`
```json
{ "email": "user@example.com", "otp": "123456" }
```
**200** `{ "success": true, "message": "Registration successful!" }`
**400** `{ "detail": { "success": false, "message": "Invalid OTP. 3 attempt(s) remaining." } }`

### `POST /resend-otp`
```json
{ "email": "user@example.com" }
```
**200** `{ "success": true, "message": "A new OTP has been sent to your email." }`

