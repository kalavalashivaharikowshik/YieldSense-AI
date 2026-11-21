import { create } from "axios";

import { config } from "../constants/config";
import { sessionEvents } from "../storage/sessionEvents";
import { tokenStorage } from "../storage/tokenStorage";

// A 401 from these endpoints means wrong credentials, not an expired
// session, so it must not sign the user out.
const CREDENTIAL_ENDPOINTS = [
  "/auth/login",
  "/auth/token",
  "/auth/change-password",
];

const apiClient = create({
  baseURL: config.apiBaseUrl,
  timeout: 30000,
  headers: {
    "Content-Type": "application/json",
  },
});

apiClient.interceptors.request.use(
  async (requestConfig) => {
    const token = await tokenStorage.get();

    if (token) {
      requestConfig.headers.Authorization =
        `Bearer ${token}`;
    }

    return requestConfig;
  },
  (error) => Promise.reject(error)
);

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const requestUrl = error.config?.url ?? "";
    const isCredentialCheck = CREDENTIAL_ENDPOINTS.some((endpoint) =>
      requestUrl.endsWith(endpoint)
    );

    if (error.response?.status === 401 && !isCredentialCheck) {
      await tokenStorage.remove();
      // Without this the app stayed on protected screens with every
      // request failing until it was restarted.
      sessionEvents.emitSessionExpired();
    }

    return Promise.reject(error);
  }
);

export default apiClient;