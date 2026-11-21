import apiClient from "./apiClient";

// Uses the shared client so weather requests get the same base URL,
// token and session-expiry handling as every other API call.
const weatherAnalysisApi = {
  get(url, config) {
    return apiClient.get(`/weather-analysis${url}`, config);
  },
};

export default weatherAnalysisApi;
