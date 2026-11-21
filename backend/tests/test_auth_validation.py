import pytest

from tests.conftest import TEST_PASSWORD


@pytest.mark.parametrize("password", ["", "short", "        ", "x" * 73])
def test_register_rejects_weak_passwords(client, password):
    response = client.post(
        "/api/auth/register",
        json={
            "full_name": "New Farmer",
            "email": "new@example.com",
            "password": password,
        },
    )

    assert response.status_code == 422


def test_register_rejects_overlong_name_and_bad_phone(client):
    base = {"email": "new@example.com", "password": TEST_PASSWORD}

    long_name = client.post(
        "/api/auth/register", json={**base, "full_name": "N" * 101}
    )
    bad_phone = client.post(
        "/api/auth/register",
        json={**base, "full_name": "New Farmer", "phone": "9" * 40},
    )

    assert long_name.status_code == 422
    assert bad_phone.status_code == 422


def test_change_password_rejects_weak_new_password(client, farmer_headers):
    response = client.post(
        "/api/auth/change-password",
        json={"old_password": TEST_PASSWORD, "new_password": ""},
        headers=farmer_headers,
    )

    assert response.status_code == 422


def test_profile_phone_is_normalized_and_unique(client, farmer_headers):
    from tests.conftest import create_user, login

    first = client.put(
        "/api/auth/profile",
        json={"phone": "+91 98765-43210"},
        headers=farmer_headers,
    )

    assert first.status_code == 200
    assert first.json()["phone"] == "+919876543210"

    create_user("second@example.com")
    second_headers = login(client, "second@example.com")

    duplicate = client.put(
        "/api/auth/profile",
        json={"phone": "+919876543210"},
        headers=second_headers,
    )

    assert duplicate.status_code == 400
