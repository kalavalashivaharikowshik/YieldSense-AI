from jose import jwt

from app.core.config import settings
from tests.conftest import TEST_PASSWORD, create_user, login

NEW_PASSWORD = "An0therStr0ngOne"


def test_change_password_revokes_old_tokens(client, farmer_headers):
    response = client.post(
        "/api/auth/change-password",
        json={"old_password": TEST_PASSWORD, "new_password": NEW_PASSWORD},
        headers=farmer_headers,
    )

    assert response.status_code == 200
    new_token = response.json()["access_token"]

    assert client.get("/api/auth/me", headers=farmer_headers).status_code == 401
    assert (
        client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {new_token}"},
        ).status_code
        == 200
    )


def test_password_reset_revokes_old_tokens(client, sent_emails):
    create_user("reset@example.com")
    old_headers = login(client, "reset@example.com")

    assert (
        client.post(
            "/api/auth/forgot-password", json={"email": "reset@example.com"}
        ).status_code
        == 200
    )

    code = sent_emails.last_code_for("reset@example.com")
    reset = client.post(
        "/api/auth/reset-password",
        json={
            "email": "reset@example.com",
            "otp_code": code,
            "new_password": NEW_PASSWORD,
        },
    )

    assert reset.status_code == 200
    assert client.get("/api/auth/me", headers=old_headers).status_code == 401
    login(client, "reset@example.com", NEW_PASSWORD)


def test_tokens_without_version_still_work(client):
    """Tokens issued before the version claim existed stay valid."""
    create_user("legacy@example.com")
    legacy_token = jwt.encode(
        {"sub": "legacy@example.com", "role": "farmer", "exp": 4102444800},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )

    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {legacy_token}"},
    )

    assert response.status_code == 200


def test_swagger_token_endpoint(client):
    create_user("swagger@example.com")

    response = client.post(
        "/api/auth/token",
        data={"username": "swagger@example.com", "password": TEST_PASSWORD},
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
