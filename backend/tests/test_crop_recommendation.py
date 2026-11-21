import pytest

from app.services.crop_recommendation_service import rank_candidate_crops


def candidate(crop, yields, predicted, scale=1.0):
    return {
        "crop": crop,
        "historical_yields": sorted(value * scale for value in yields),
        "historical_average_yield": sum(yields) * scale / len(yields),
        "historical_record_count": len(yields),
        "predicted_yield": predicted * scale,
    }


def test_ranking_does_not_depend_on_units():
    pulses = candidate("Gram", [0.8, 0.9, 1.0, 1.1, 1.2], predicted=1.15)
    coconut = candidate("Coconut", [8.0, 8.5, 9.0, 9.5, 10.0], predicted=8.2)

    in_tonnes = [c["crop"] for c in rank_candidate_crops([pulses, coconut])]

    # Same history and prediction, but coconut counted in nuts (x1000).
    coconut_in_nuts = candidate(
        "Coconut", [8.0, 8.5, 9.0, 9.5, 10.0], predicted=8.2, scale=1000
    )
    in_nuts = [c["crop"] for c in rank_candidate_crops([pulses, coconut_in_nuts])]

    assert in_tonnes == in_nuts == ["Gram", "Coconut"]


def test_steady_crop_beats_erratic_crop_with_same_percentile():
    steady = candidate("Wheat", [4.0, 4.1, 4.2, 4.3, 4.4], predicted=4.25)
    erratic = candidate("Bajra", [0.2, 1.0, 2.5, 4.0, 6.0], predicted=2.6)

    ranked = rank_candidate_crops([erratic, steady])

    assert ranked[0]["crop"] == "Wheat"
    assert ranked[0]["rank"] == 1


def create_farm(client, headers, state):
    return client.post(
        "/api/farms",
        json={
            "farm_name": f"{state} Farm",
            "state": state,
            "district": "Test District",
            "area_hectares": 2,
        },
        headers=headers,
    ).json()["id"]


@pytest.mark.usefixtures("yield_model", "reference_data")
def test_recommendation_endpoint(client, farmer_headers):
    farm_id = create_farm(client, farmer_headers, "Punjab")

    response = client.post(
        "/api/crop-recommendation",
        json={"farm_id": farm_id, "season": "Rabi", "crop_year": 2020},
        headers=farmer_headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["recommendation_strength"] in {"high", "medium", "low"}
    for option in body["alternatives"]:
        assert option["yield_unit"].endswith("per hectare")
        assert 0 <= option["historical_percentile"] <= 100


@pytest.mark.usefixtures("yield_model", "reference_data")
def test_recommendation_with_too_little_history(client, farmer_headers):
    farm_id = create_farm(client, farmer_headers, "Kerala")

    response = client.post(
        "/api/crop-recommendation",
        json={"farm_id": farm_id, "season": "Rabi", "crop_year": 2020},
        headers=farmer_headers,
    )

    assert response.status_code == 422
    assert "not enough historical records" in response.json()["detail"]


def test_admin_cannot_create_recommendations(client, admin_headers):
    response = client.post(
        "/api/crop-recommendation",
        json={"farm_id": 1, "season": "Rabi", "crop_year": 2020},
        headers=admin_headers,
    )

    assert response.status_code == 403


@pytest.mark.usefixtures("yield_model", "reference_data")
def test_recommendation_history_includes_units(client, farmer_headers):
    farm_id = create_farm(client, farmer_headers, "Punjab")
    client.post(
        "/api/crop-recommendation",
        json={"farm_id": farm_id, "season": "Rabi", "crop_year": 2020},
        headers=farmer_headers,
    )

    history = client.get(
        "/api/crop-recommendation/history", headers=farmer_headers
    ).json()

    assert history["total"] == 1
    assert history["items"][0]["prediction_unit"].endswith("per hectare")
