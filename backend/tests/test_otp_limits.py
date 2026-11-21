from datetime import UTC, datetime, timedelta

from app.core.config import settings
from app.models.user import EmailOTP, User
from tests.conftest import create_user


def _backdate_all_otps(db, minutes):
    for otp in db.query(EmailOTP).all():
        otp.last_sent_at = otp.last_sent_at - timedelta(minutes=minutes)
    db.commit()


def test_daily_otp_send_cap(client, db):
    create_user("otp@example.com")

    for _ in range(settings.OTP_MAX_SENDS_PER_DAY):
        response = client.post(
            "/api/auth/forgot-password", json={"email": "otp@example.com"}
        )
        assert response.status_code == 200, response.text
        _backdate_all_otps(db, minutes=5)

    blocked = client.post(
        "/api/auth/forgot-password", json={"email": "otp@example.com"}
    )

    assert blocked.status_code == 429


def test_daily_failed_attempt_cap(client, db, sent_emails):
    user = create_user("otp@example.com")
    now = datetime.now(UTC).replace(tzinfo=None)

    db.add(
        EmailOTP(
            user_id=user.id,
            purpose="password_reset",
            otp_hash="x",
            expires_at=now - timedelta(minutes=1),
            failed_attempts=settings.OTP_MAX_FAILED_ATTEMPTS_PER_DAY,
            created_at=now - timedelta(minutes=30),
            last_sent_at=now - timedelta(minutes=30),
            is_active=False,
        )
    )
    db.commit()

    client.post("/api/auth/forgot-password", json={"email": "otp@example.com"})
    code = sent_emails.last_code_for("otp@example.com")

    response = client.post(
        "/api/auth/reset-password",
        json={
            "email": "otp@example.com",
            "otp_code": code,
            "new_password": "BrandNewPass123",
        },
    )

    assert response.status_code == 429
    assert db.query(User).count() == 1
