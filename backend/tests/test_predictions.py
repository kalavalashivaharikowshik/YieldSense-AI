import pytest


def create_farm(client, headers, state, area):
    response = client.post(
        "/api/farms",
        json={
            "farm_name": f"{state} Farm {area} ha",
            "state": state,
            "district": "Test District",
            "area_hectares": area,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text

    return response.json()["id"]


def predict(client, headers, farm_id, **overrides):
    body = {
        "farm_id": farm_id,
        "crop": "Coconut",
        "crop_year": 2018,
        "season": "Whole Year",
        **overrides,
    }

    return client.post("/api/predictions", json=body, headers=headers)


@pytest.mark.usefixtures("yield_model", "reference_data")
def test_prediction_does_not_depend_on_farm_size(client, farmer_headers):
    small = create_farm(client, farmer_headers, "Kerala", 2)
    large = create_farm(client, farmer_headers, "Kerala", 200)

    small_result = predict(client, farmer_headers, small, fertilizer=140, pesticide=0.3)
    large_result = predict(client, farmer_headers, large, fertilizer=140, pesticide=0.3)

    assert small_result.status_code == 201, small_result.text
    small_yield = small_result.json()["predicted_yield"]

    # Yield per hectare is the same for both farms; only production scales.
    assert small_yield == pytest.approx(large_result.json()["predicted_yield"])
    assert large_result.json()["estimated_production"] == pytest.approx(
        small_result.json()["estimated_production"] * 100
    )

    # Kerala's historical coconut yield is in the thousands (nuts per
    # hectare); before this fix a 2-hectare farm was predicted at ~12.
    assert small_yield > 1000


@pytest.mark.usefixtures("yield_model", "reference_data")
def test_fertilizer_and_pesticide_default_to_typical_rates(client, farmer_headers):
    farm_id = create_farm(client, farmer_headers, "Punjab", 3)

    response = predict(client, farmer_headers, farm_id, crop="Wheat", season="Rabi")

    assert response.status_code == 201, response.text
    body = response.json()
    assert 90 <= body["fertilizer"] <= 200
    assert "Typical historical rates were used" in body["explanation"]


@pytest.mark.usefixtures("yield_model", "reference_data")
def test_out_of_range_rate_is_rejected_or_warned(client, farmer_headers):
    farm_id = create_farm(client, farmer_headers, "Punjab", 3)

    too_much = predict(
        client, farmer_headers, farm_id, crop="Wheat", season="Rabi", fertilizer=5000
    )
    unusual = predict(
        client, farmer_headers, farm_id, crop="Wheat", season="Rabi", fertilizer=600
    )

    assert too_much.status_code == 422
    assert unusual.status_code == 201
    assert "Fertilizer (kg per hectare)" in unusual.json()["explanation"]


@pytest.mark.usefixtures("yield_model", "reference_data")
def test_units_follow_the_crop(client, farmer_headers):
    kerala = create_farm(client, farmer_headers, "Kerala", 2)
    punjab = create_farm(client, farmer_headers, "Punjab", 2)

    coconut = predict(client, farmer_headers, kerala).json()
    wheat = predict(
        client, farmer_headers, punjab, crop="Wheat", season="Rabi"
    ).json()

    assert coconut["prediction_unit"] == "nuts per hectare"
    assert coconut["production_unit"] == "nuts"
    assert wheat["prediction_unit"] == "metric tons per hectare"


def test_crop_unit_lookup():
    from app.services.crop_units import get_crop_unit

    assert get_crop_unit("Cotton(Lint)").production_unit.startswith("bales")
    assert get_crop_unit(" coconut ").production_unit == "nuts"
    assert get_crop_unit("Rice").is_tonnes
