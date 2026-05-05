"""
Run with:  pytest tests/test_api.py -v

Gmail is mocked in every test — no credentials needed.
The DB is a temp file that is wiped before each test class.
"""

import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import backend.main as main_module

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
main_module.DB_PATH = Path(_tmp.name)
main_module.engine = main_module.create_engine(
    f"sqlite:///{_tmp.name}", connect_args={"check_same_thread": False}
)
main_module.Base.metadata.create_all(main_module.engine)

from backend.main import OTP, User, app, get_session
from fastapi.testclient import TestClient

client = TestClient(app, raise_server_exceptions=False)


def clear_db():
    with get_session() as db:
        db.query(OTP).delete()
        db.query(User).delete()
        db.commit()


def force_otp(email, otp):
    with get_session() as db:
        user = db.query(User).filter(User.email == email).first()
        record = db.query(OTP).filter(OTP.user_id == user.id).first()
        record.otp = otp
        db.commit()


def expire_otp(email):
    with get_session() as db:
        user = db.query(User).filter(User.email == email).first()
        record = db.query(OTP).filter(OTP.user_id == user.id).first()
        record.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()


@patch("backend.main.send_email")
class TestRegister:
    def setup_method(self):
        clear_db()

    def test_new_user_gets_otp(self, _):
        res = client.post("/register", json={"email": "a@test.com"})
        assert res.status_code == 200
        assert res.json()["success"] is True

    def test_already_verified_returns_409(self, _):
        client.post("/register", json={"email": "b@test.com"})
        force_otp("b@test.com", "111111")
        client.post("/verify-otp", json={"email": "b@test.com", "otp": "111111"})

        res = client.post("/register", json={"email": "b@test.com"})
        assert res.status_code == 409
        assert res.json()["detail"]["success"] is False

    def test_invalid_email_rejected(self, _):
        res = client.post("/register", json={"email": "not-an-email"})
        assert res.status_code == 422


@patch("backend.main.send_email")
class TestVerifyOTP:
    def setup_method(self):
        clear_db()

    def test_correct_otp_completes_registration(self, _):
        client.post("/register", json={"email": "d@test.com"})
        force_otp("d@test.com", "222222")

        res = client.post("/verify-otp", json={"email": "d@test.com", "otp": "222222"})
        assert res.status_code == 200
        assert res.json()["success"] is True
        assert "successful" in res.json()["message"].lower()

    def test_wrong_otp_returns_400(self, _):
        client.post("/register", json={"email": "e@test.com"})
        force_otp("e@test.com", "333333")

        res = client.post("/verify-otp", json={"email": "e@test.com", "otp": "000000"})
        assert res.status_code == 400
        assert res.json()["detail"]["success"] is False

    def test_expired_otp_returns_400(self, _):
        client.post("/register", json={"email": "f@test.com"})
        expire_otp("f@test.com")

        res = client.post("/verify-otp", json={"email": "f@test.com", "otp": "000000"})
        assert res.status_code == 400
        assert "expired" in res.json()["detail"]["message"].lower()

    def test_unknown_email_returns_404(self, _):
        res = client.post("/verify-otp", json={"email": "ghost@test.com", "otp": "123456"})
        assert res.status_code == 404

    def test_too_many_attempts_returns_429(self, _):
        client.post("/register", json={"email": "g@test.com"})
        force_otp("g@test.com", "444444")

        for _ in range(5):
            client.post("/verify-otp", json={"email": "g@test.com", "otp": "000000"})

        res = client.post("/verify-otp", json={"email": "g@test.com", "otp": "444444"})
        assert res.status_code == 429
