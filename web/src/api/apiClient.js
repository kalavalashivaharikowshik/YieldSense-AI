import axios from "axios";

import {
  SESSION_EXPIRED_EVENT,
  getToken,
  removeToken,
} from "../utils/token";

// A 401 from these endpoints means wrong credentials, not an expired
// session, so it must not log the user out.
const CREDENTIAL_ENDPOINTS = [
  "/auth/login",
  "/auth/token",
  "/auth/change-password",
];

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL;

if (!apiBaseUrl) {
  throw new Error(
    "VITE_API_BASE_URL is missing. Check the web .env file."
  );
}

const apiClient = axios.create({
  baseURL: apiBaseUrl.replace(/\/+$/, ""),
  timeout: 30000,
  headers: {
    "Content-Type": "application/json",
  },
});

apiClient.interceptors.request.use(
  (config) => {
    const token = getToken();

    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    return config;
  },
  (error) => Promise.reject(error)
);

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const requestUrl = error.config?.url ?? "";
    const isCredentialCheck = CREDENTIAL_ENDPOINTS.some((endpoint) =>
      requestUrl.endsWith(endpoint)
    );

    if (
      error.response?.status === 401 &&
      !isCredentialCheck &&
      getToken()
    ) {
      removeToken();
      window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
    }

    return Promise.reject(error);
  }
);

export default apiClient;