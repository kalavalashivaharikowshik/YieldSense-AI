def test_health_endpoint(client):
    response = client.get("/health")

    assert response.status_code == 200


def test_protected_endpoint_requires_token(client):
    response = client.get("/api/farms")

    assert response.status_code == 401


def test_cors_exposes_download_filename(client):
    response = client.get(
        "/health",
        headers={"Origin": "http://localhost:5173"},
    )

    exposed = response.headers.get("access-control-expose-headers", "")

    assert "Content-Disposition" in exposed
