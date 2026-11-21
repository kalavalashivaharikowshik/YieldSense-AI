def test_health_endpoint(client):
    response = client.get("/health")

    assert response.status_code == 200


def test_protected_endpoint_requires_token(client):
    response = client.get("/api/farms")

    assert response.status_code == 401
