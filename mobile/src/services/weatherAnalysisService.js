import apiClient from "../api/apiClient";

// The API serves weather analysis under /api/weather-analysis. The base
// URL already ends in /api, so the shared client is used directly. The
// old code stripped /api and called /weather-analysis, which returned
// 404 after the backend route moved under /api.

export async function getWeatherAnalysisOptions() {
  const response = await apiClient.get("/weather-analysis/options");

  return response.data;
}

export async function getWeatherAnalysis({ state, startYear, endYear }) {
  const response = await apiClient.get("/weather-analysis", {
    params: {
      state,
      start_year: startYear,
      end_year: endYear,
    },
  });

  return response.data;
}
