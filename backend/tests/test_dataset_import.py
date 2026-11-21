from app.models.agriculture import (
    HistoricalCropYield,
    StateSoilReference,
    StateWeatherReference,
)

YIELD_HEADER = (
    "Crop,Crop_Year,Season,State,Area,Production,"
    "Annual_Rainfall,Fertilizer,Pesticide,Yield\n"
)
YIELD_ROW = "Rice,2010,Kharif,Kerala,100,250,3000,1000,10,2.5\n"


def upload(client, headers, path, content, filename="data.csv"):
    return client.post(
        f"/api/datasets/{path}/import",
        files={"file": (filename, content, "text/csv")},
        headers=headers,
    )


def test_duplicate_rows_in_one_file_are_skipped(client, admin_headers, db):
    response = upload(
        client,
        admin_headers,
        "historical-yield",
        YIELD_HEADER + YIELD_ROW + YIELD_ROW,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["inserted_rows"] == 1
    assert body["skipped_rows"] == 1
    assert db.query(HistoricalCropYield).count() == 1


def test_reimport_skips_existing_rows(client, admin_headers, db):
    upload(client, admin_headers, "historical-yield", YIELD_HEADER + YIELD_ROW)
    again = upload(client, admin_headers, "historical-yield", YIELD_HEADER + YIELD_ROW)

    assert again.json()["skipped_rows"] == 1
    assert db.query(HistoricalCropYield).count() == 1


def test_negative_values_are_reported_as_invalid(client, admin_headers):
    bad_row = "Wheat,2010,Rabi,Kerala,100,250,3000,1000,10,-5\n"

    response = upload(client, admin_headers, "historical-yield", YIELD_HEADER + bad_row)

    assert response.status_code == 200
    assert response.json()["invalid_rows"] == 1
    assert "Yield cannot be negative" in response.json()["errors"][0]["message"]


def test_duplicate_states_in_soil_and_weather_files(client, admin_headers, db):
    soil = "State,N,P,K,pH\nKerala,1,2,3,6\nKerala,4,5,6,7\n"
    weather = (
        "State,Year,avg_temp_c,total_rainfall_mm,avg_humidity_percent\n"
        "Kerala,2010,27,3000,80\nKerala,2010,28,3100,81\n"
    )

    assert upload(client, admin_headers, "soil", soil).status_code == 200
    assert upload(client, admin_headers, "weather", weather).status_code == 200
    assert db.query(StateSoilReference).count() == 1
    assert db.query(StateWeatherReference).count() == 1
    assert db.query(StateSoilReference).one().ph == 7


def test_only_admins_can_import(client, farmer_headers):
    response = upload(client, farmer_headers, "soil", "State,N,P,K,pH\n")

    assert response.status_code == 403


def test_rejects_non_csv_and_oversized_files(client, admin_headers, monkeypatch):
    from app.api.routes import datasets

    assert (
        upload(client, admin_headers, "soil", "x", filename="data.txt").status_code
        == 400
    )

    monkeypatch.setattr(datasets, "MAX_UPLOAD_BYTES", 10)
    response = upload(client, admin_headers, "soil", "State,N,P,K,pH\nKerala,1,2,3,6\n")

    assert response.status_code == 413
