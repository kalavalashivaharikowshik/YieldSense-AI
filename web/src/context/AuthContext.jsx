import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import authApi from "../api/authApi";
import { AuthContext } from "./auth-context";
import {
  SESSION_EXPIRED_EVENT,
  getToken,
  removeToken,
  saveToken,
} from "../utils/token";

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [initializing, setInitializing] = useState(true);
  // True when a saved session could not be checked because the server
  // was unreachable (offline, timeout, cold start).
  const [connectionError, setConnectionError] = useState(false);

  const loadCurrentUser = useCallback(async () => {
    const token = getToken();

    if (!token) {
      setUser(null);
      return null;
    }

    try {
      const response = await authApi.get("/me");

      setUser(response.data);
      setConnectionError(false);

      return response.data;
    } catch (error) {
      setConnectionError(error.response?.status !== 401);

      // Only a rejected token ends the session. A timeout, an offline
      // device or a server cold start must not log the user out.
      if (error.response?.status === 401) {
        removeToken();
        setUser(null);
      }

      throw error;
    }
  }, []);

  useEffect(() => {
    const handleSessionExpired = () => {
      setUser(null);
    };

    window.addEventListener(
      SESSION_EXPIRED_EVENT,
      handleSessionExpired
    );

    return () => {
      window.removeEventListener(
        SESSION_EXPIRED_EVENT,
        handleSessionExpired
      );
    };
  }, []);

  useEffect(() => {
    const initializeAuthentication = async () => {
      try {
        await loadCurrentUser();
      } catch {
        // A rejected token was already removed. For network errors the
        // token is kept and the user can retry once back online.
      } finally {
        setInitializing(false);
      }
    };

    initializeAuthentication();
  }, [loadCurrentUser]);

  const login = useCallback(async (credentials) => {
    const loginResponse = await authApi.post(
      "/login",
      credentials
    );

    saveToken(loginResponse.data.access_token);

    try {
      const userResponse = await authApi.get("/me");

      setUser(userResponse.data);

      return userResponse.data;
    } catch (error) {
      removeToken();
      setUser(null);

      throw error;
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await authApi.post("/logout");
    } finally {
      removeToken();
      setUser(null);
    }
  }, []);

  const refreshUser = useCallback(async () => {
    return loadCurrentUser();
  }, [loadCurrentUser]);

  const retryConnection = useCallback(async () => {
    setInitializing(true);

    try {
      await loadCurrentUser();
    } catch {
      // connectionError is updated by loadCurrentUser.
    } finally {
      setInitializing(false);
    }
  }, [loadCurrentUser]);

  const updateUser = useCallback((updatedUser) => {
    setUser(updatedUser);
  }, []);

  const value = useMemo(
    () => ({
      user,
      initializing,
      connectionError,
      retryConnection,
      isAuthenticated: Boolean(user),
      isAdmin: user?.role === "admin",
      isFarmer: user?.role === "farmer",
      login,
      logout,
      refreshUser,
      updateUser,
    }),
    [
      user,
      initializing,
      connectionError,
      retryConnection,
      login,
      logout,
      refreshUser,
      updateUser,
    ]
  );

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}