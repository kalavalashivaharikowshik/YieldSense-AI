from tests.conftest import create_user


def test_forgot_password_response_is_identical(client):
    create_user("exists@example.com")

    known = client.post(
        "/api/auth/forgot-password", json={"email": "exists@example.com"}
    )
    unknown = client.post(
        "/api/auth/forgot-password", json={"email": "ghost@example.com"}
    )

    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()


def test_send_otp_response_is_identical(client):
    create_user("pending@example.com", verified=False)

    known = client.post("/api/auth/send-otp", json={"email": "pending@example.com"})
    unknown = client.post("/api/auth/send-otp", json={"email": "ghost@example.com"})

    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()


def test_reset_password_unknown_email_matches_missing_otp(client):
    create_user("exists@example.com")
    body = {"otp_code": "123456", "new_password": "BrandNewPass123"}

    known = client.post(
        "/api/auth/reset-password", json={**body, "email": "exists@example.com"}
    )
    unknown = client.post(
        "/api/auth/reset-password", json={**body, "email": "ghost@example.com"}
    )

    assert known.status_code == unknown.status_code == 400
    assert known.json() == unknown.json()


def test_register_and_verify_flow(client, sent_emails):
    response = client.post(
        "/api/auth/register",
        json={
            "full_name": "New Farmer",
            "email": "new@example.com",
            "password": "Str0ngPassw0rd!",
        },
    )

    assert response.status_code == 201

    blocked = client.post(
        "/api/auth/login",
        json={"email": "new@example.com", "password": "Str0ngPassw0rd!"},
    )
    assert blocked.status_code == 403

    verify = client.post(
        "/api/auth/verify-otp",
        json={
            "email": "new@example.com",
            "otp_code": sent_emails.last_code_for("new@example.com"),
        },
    )

    assert verify.status_code == 200
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "new@example.com", "password": "Str0ngPassw0rd!"},
        ).status_code
        == 200
    )
