# OTP Registration System

A full-stack user registration system with email OTP verification built with FastAPI + React.

---

## Architecture Overview

```
otp-registration/
├── backend/
│   ├── main.py          # FastAPI app — all routes, DB, email logic
│   ├── requirements.txt
│   └── registration.db  # Created automatically on first run
├── frontend/
│   ├── src/
│   │   ├── App.jsx      # All React screens (email → OTP → result)
│   │   ├── index.css    # Global styles
│   │   └── main.jsx     # Entry point
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── tests/
│   └── test_api.py      # Pytest test suite
├── conftest.py
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
| **SQLite (no ORM)** | Zero extra dependencies, full SQL control, perfect for self-contained demos |
| **Gmail API (not SMTP)** | No relay needed, OAuth2, reliable delivery, works within Google's ecosystem |
| **FastAPI BackgroundTasks** | Email sends are non-blocking; `/register` returns in <50ms regardless of Gmail latency |
| **OTP stored as SHA-256 hash** | Raw OTPs never persist. SHA-256 is sufficient for 6-digit codes with TTL + lockout |
| **Pending → Verified state machine** | Atomic, recoverable. Re-registering while pending resets the OTP cleanly |
| **CORS open (`*`)** | Acceptable for local dev. Restrict in production |

## Trade-offs

- **SQLite single-writer**: Fine for low traffic. Swap to PostgreSQL for concurrent load.
- **SHA-256 vs bcrypt**: Faster, but rate-limiting (5 attempts) and TTL (10 min) compensate.
- **No OTP in response**: The OTP is only delivered via email — never in the API response body.
- **Email failure is non-fatal**: The OTP stays in the DB; the user can hit `/resend-otp`.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SENDER_EMAIL` | `me` | Gmail address to send from (`me` = the authenticated account) |

---

## Prerequisites

- Python 3.11+
- Node.js 18+
- A Google Cloud project with Gmail API enabled (see below)

---

## Gmail API Setup

### Step 1 — Enable Gmail API
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select an existing one)
3. Navigate to **APIs & Services → Library**
4. Search for **Gmail API** and click **Enable**

### Step 2 — Create OAuth 2.0 Credentials
1. Go to **APIs & Services → Credentials**
2. Click **Create Credentials → OAuth client ID**
3. Application type: **Desktop app**
4. Name it anything (e.g., `OTP Registration`)
5. Click **Create**
6. Download the JSON file and rename it to **`credentials.json`**
7. Place `credentials.json` inside the `backend/` folder

### Step 3 — First Run (Authorize)
On the very first run of the backend, a browser window will open asking you to authorize the app.
After you approve, a `token.json` file is saved in `backend/` and reused on subsequent runs.

> **Tip**: If you get a "This app isn't verified" warning, click **Advanced → Go to … (unsafe)** for local testing.

---

## Installation & Running

### Backend

```bash
cd backend
pip install -r requirements.txt

# Place credentials.json here first!

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
pip install -r backend/requirements.txt
pytest tests/test_api.py -v
```

Tests use a temporary SQLite DB and mock `send_otp_email` — no Gmail credentials needed.

### What's tested

| Category | Tests |
|---|---|
| Registration flow | New user, already verified (409), pending reset, invalid email, email-failure tolerance |
| OTP verification | Correct OTP, wrong OTP, expired OTP, unknown email, too many attempts, malformed OTP |
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

### `GET /health`
**200** `{ "status": "ok" }`
