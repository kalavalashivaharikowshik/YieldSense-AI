def test_create_and_list_farm(client, farmer_headers, farm_payload):
    response = client.post("/api/farms", json=farm_payload, headers=farmer_headers)

    assert response.status_code == 201, response.text
    assert response.json()["farm_name"] == "Green Acres"

    listing = client.get("/api/farms", headers=farmer_headers)

    assert listing.status_code == 200
    assert listing.json()["total"] == 1


def test_whitespace_only_farm_name_is_rejected(
    client, farmer_headers, farm_payload
):
    farm_payload["farm_name"] = "   "

    response = client.post("/api/farms", json=farm_payload, headers=farmer_headers)

    assert response.status_code == 422

    listing = client.get("/api/farms", headers=farmer_headers)

    assert listing.status_code == 200
    assert listing.json()["total"] == 0


def test_farm_text_is_whitespace_normalized(client, farmer_headers, farm_payload):
    farm_payload["farm_name"] = "  Green    Acres  "
    farm_payload["village"] = "   "

    response = client.post("/api/farms", json=farm_payload, headers=farmer_headers)

    assert response.status_code == 201
    assert response.json()["farm_name"] == "Green Acres"
    assert response.json()["village"] is None


def test_update_rejects_null_required_fields(client, farmer_headers, farm_payload):
    farm_id = client.post(
        "/api/farms", json=farm_payload, headers=farmer_headers
    ).json()["id"]

    for body in ({"farm_name": None}, {"area_hectares": None}, {"state": "  "}):
        response = client.put(
            f"/api/farms/{farm_id}", json=body, headers=farmer_headers
        )
        assert response.status_code == 422, body

    response = client.put(
        f"/api/farms/{farm_id}",
        json={"farm_name": "Renamed Farm"},
        headers=farmer_headers,
    )

    assert response.status_code == 200
    assert response.json()["farm_name"] == "Renamed Farm"


def test_farmer_cannot_access_other_farmers_farm(client, farm_payload):
    from tests.conftest import create_user, login

    create_user("owner@example.com")
    create_user("other@example.com")
    owner = login(client, "owner@example.com")
    other = login(client, "other@example.com")

    farm_id = client.post("/api/farms", json=farm_payload, headers=owner).json()["id"]

    assert client.get(f"/api/farms/{farm_id}", headers=other).status_code == 403
