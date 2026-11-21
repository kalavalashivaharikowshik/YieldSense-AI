def test_weather_analysis_requires_login(client):
    assert client.get("/api/weather-analysis/options").status_code == 401
    assert client.get("/api/weather-analysis").status_code == 401


def test_weather_analysis_options_for_signed_in_user(client, farmer_headers):
    response = client.get("/api/weather-analysis/options", headers=farmer_headers)

    assert response.status_code == 200
