from app.services.email_service import EmailDeliveryError
from tests.conftest import create_user


def test_email_failure_returns_503(client, monkeypatch):
    from app.api.routes import auth as auth_routes

    async def failing_send(recipient_email, recipient_name, otp_code):
        raise EmailDeliveryError("SMTP is down")

    monkeypatch.setattr(auth_routes, "send_password_reset_otp_email", failing_send)
    create_user("mail@example.com")

    response = client.post(
        "/api/auth/forgot-password", json={"email": "mail@example.com"}
    )

    assert response.status_code == 503
