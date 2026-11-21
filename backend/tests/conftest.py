"""Shared pytest fixtures.

Tests run against a throwaway SQLite database by default. Set
TEST_DATABASE_URL to a PostgreSQL URL to run the same suite against
PostgreSQL (CI does this).
"""

import os
import tempfile
from collections.abc import Iterator

import pytest

_TEMP_DIR = tempfile.mkdtemp(prefix="yieldsense-tests-")

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    f"sqlite:///{_TEMP_DIR}/test.db",
)
os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-long-enough")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
os.environ.setdefault("LOG_FILE", f"{_TEMP_DIR}/app.log")
os.environ["RUN_MIGRATIONS_ON_STARTUP"] = "false"
os.environ["PRELOAD_MODEL_ON_STARTUP"] = "false"

from fastapi.testclient import TestClient  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402
from app.models import (  # noqa: E402,F401
    agriculture,
    crop_recommendation,
    farm,
    prediction,
)
from app.models.user import Role, User  # noqa: E402

TEST_PASSWORD = "Str0ngPassw0rd!"


class SentEmails:
    def __init__(self) -> None:
        self.messages: list[dict[str, str]] = []

    def last_code_for(self, email: str) -> str:
        for message in reversed(self.messages):
            if message["recipient_email"] == email:
                return message["otp_code"]

        raise AssertionError(f"No OTP email was sent to {email}")


@pytest.fixture(autouse=True)
def database() -> Iterator[None]:
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    session = SessionLocal()
    session.add_all([Role(name="farmer"), Role(name="admin")])
    session.commit()
    session.close()

    yield

    Base.metadata.drop_all(engine)


@pytest.fixture
def db():
    session = SessionLocal()

    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def sent_emails(monkeypatch) -> SentEmails:
    outbox = SentEmails()

    async def fake_send(recipient_email, recipient_name, otp_code):
        outbox.messages.append(
            {
                "recipient_email": recipient_email,
                "recipient_name": recipient_name,
                "otp_code": otp_code,
            }
        )

    from app.api.routes import auth as auth_routes

    monkeypatch.setattr(
        auth_routes,
        "send_verification_otp_email",
        fake_send,
    )
    monkeypatch.setattr(
        auth_routes,
        "send_password_reset_otp_email",
        fake_send,
    )

    return outbox


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(fastapi_app) as test_client:
        yield test_client


def create_user(
    email: str,
    role_name: str = "farmer",
    password: str = TEST_PASSWORD,
    verified: bool = True,
) -> User:
    session = SessionLocal()

    try:
        role = session.query(Role).filter(Role.name == role_name).one()
        user = User(
            full_name=f"Test {role_name.title()}",
            email=email,
            hashed_password=hash_password(password),
            role_id=role.id,
            is_verified=verified,
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        return user
    finally:
        session.close()


def login(client: TestClient, email: str, password: str = TEST_PASSWORD) -> dict:
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text

    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def farmer_headers(client) -> dict:
    create_user("farmer@example.com")

    return login(client, "farmer@example.com")


@pytest.fixture
def admin_headers(client) -> dict:
    create_user("admin@example.com", role_name="admin")

    return login(client, "admin@example.com")


@pytest.fixture
def farm_payload() -> dict:
    return {
        "farm_name": "Green Acres",
        "state": "Punjab",
        "district": "Ludhiana",
        "area_hectares": 2.5,
    }
