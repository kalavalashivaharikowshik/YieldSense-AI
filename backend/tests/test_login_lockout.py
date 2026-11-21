from app.core.config import settings
from app.models.user import User
from tests.conftest import TEST_PASSWORD, create_user


def attempt(client, password):
    return client.post(
        "/api/auth/login",
        json={"email": "lock@example.com", "password": password},
    )


def test_account_locks_after_repeated_failures(client, db):
    create_user("lock@example.com")

    for _ in range(settings.LOGIN_MAX_FAILED_ATTEMPTS):
        assert attempt(client, "wrong-password").status_code == 401

    locked = attempt(client, TEST_PASSWORD)

    assert locked.status_code == 429
    assert "Retry-After" in locked.headers


def test_lock_expires(client, db):
    from datetime import timedelta

    from app.services.auth_service import utc_now

    create_user("lock@example.com")

    for _ in range(settings.LOGIN_MAX_FAILED_ATTEMPTS):
        attempt(client, "wrong-password")

    user = db.query(User).filter(User.email == "lock@example.com").one()
    user.locked_until = utc_now() - timedelta(seconds=1)
    db.commit()

    assert attempt(client, TEST_PASSWORD).status_code == 200


def test_successful_login_resets_counter(client, db):
    create_user("lock@example.com")

    attempt(client, "wrong-password")
    attempt(client, "wrong-password")
    assert attempt(client, TEST_PASSWORD).status_code == 200

    db.expire_all()
    user = db.query(User).filter(User.email == "lock@example.com").one()

    assert user.failed_login_attempts == 0


def test_unknown_email_gets_generic_error(client):
    response = client.post(
        "/api/auth/login",
        json={"email": "nobody@example.com", "password": "whatever-pass"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"
