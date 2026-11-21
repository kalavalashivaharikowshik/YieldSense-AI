def test_weather_analysis_requires_login(client):
    assert client.get("/api/weather-analysis/options").status_code == 401
    assert client.get("/api/weather-analysis").status_code == 401


def test_weather_analysis_options_for_signed_in_user(client, farmer_headers):
    response = client.get("/api/weather-analysis/options", headers=farmer_headers)

    assert response.status_code == 200


def test_trend_uses_all_years_not_just_endpoints():
    from app.services.weather_analysis_service import trend_change

    years = [2010, 2011, 2012, 2013, 2014]
    # Flat rainfall with one unusually dry final year.
    rainfall = [1000, 1010, 990, 1005, 600]

    endpoint_change = rainfall[-1] - rainfall[0]

    assert endpoint_change == -400
    assert -400 < trend_change(years, rainfall) < 0


def test_trend_of_steady_increase():
    from app.services.weather_analysis_service import trend_change

    assert trend_change([2000, 2001, 2002], [25.0, 25.5, 26.0]) == 1.0


def test_weather_analysis_with_data(client, farmer_headers, reference_data):
    response = client.get(
        "/api/weather-analysis",
        params={"state": "Punjab", "start_year": 2000, "end_year": 2020},
        headers=farmer_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["trend"]["start_year"] == 2000
