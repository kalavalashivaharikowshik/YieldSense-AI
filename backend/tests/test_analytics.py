from app.models.prediction import YieldPrediction
from tests.conftest import create_user, login


def add_prediction(db, user_id, farm_id, crop, predicted_yield, area=2.0):
    db.add(
        YieldPrediction(
            user_id=user_id,
            farm_id=farm_id,
            farm_name="Analytics Farm",
            state="Kerala",
            crop=crop,
            crop_year=2020,
            season="Whole Year",
            area_hectares=area,
            annual_rainfall=3000,
            fertilizer=140,
            pesticide=0.3,
            nitrogen=1,
            phosphorus=1,
            potassium=1,
            ph=6,
            average_temperature_c=27,
            total_rainfall_mm=3000,
            average_humidity_percent=80,
            predicted_yield=predicted_yield,
            estimated_production=predicted_yield * area,
            model_name="test",
            model_version="1",
            prediction_unit="metric tons per hectare",
            production_unit="metric tons",
            yield_category="average",
            yield_category_label="Average Yield",
            yield_category_description="test",
        )
    )
    db.commit()


def test_averages_ignore_crops_with_other_units(client, db, farm_payload):
    user = create_user("analytics@example.com")
    headers = login(client, "analytics@example.com")
    farm_id = client.post("/api/farms", json=farm_payload, headers=headers).json()["id"]

    add_prediction(db, user.id, farm_id, "Rice", 3.0)
    add_prediction(db, user.id, farm_id, "Wheat", 5.0)
    add_prediction(db, user.id, farm_id, "Coconut", 7000.0)

    dashboard = client.get("/api/analytics/dashboard", headers=headers).json()
    summary = client.get("/api/predictions/summary", headers=headers).json()

    assert dashboard["summary"]["total_predictions"] == 3
    assert dashboard["summary"]["average_predicted_yield"] == 4.0
    assert summary["average_predicted_yield"] == 4.0
    assert summary["maximum_predicted_yield"] == 5.0

    coconut = next(item for item in dashboard["crops"] if item["crop"] == "Coconut")
    assert coconut["yield_unit"] == "nuts per hectare"
