import {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import { authService } from "../services/authService";
import { sessionEvents } from "../storage/sessionEvents";
import { tokenStorage } from "../storage/tokenStorage";

export const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [initializing, setInitializing] = useState(true);
  // True when a saved session could not be checked because the server
  // could not be reached (weak signal, offline, server starting up).
  const [connectionError, setConnectionError] = useState(false);

  const loadCurrentUser = useCallback(async () => {
    const token = await tokenStorage.get();

    if (!token) {
      setUser(null);
      return null;
    }

    try {
      const currentUser = await authService.getCurrentUser();
      setUser(currentUser);
      setConnectionError(false);
      return currentUser;
    } catch (error) {
      // Only a rejected token ends the session. Farmers on a weak mobile
      // connection were signed out every time a request timed out.
      if (error.response?.status === 401) {
        await tokenStorage.remove();
        setUser(null);
        setConnectionError(false);
      } else {
        setConnectionError(true);
      }

      throw error;
    }
  }, []);

  useEffect(() => {
    return sessionEvents.onSessionExpired(() => {
      setUser(null);
    });
  }, []);

  useEffect(() => {
    const initializeAuth = async () => {
      try {
        await loadCurrentUser();
      } catch {
        // A rejected token was removed inside loadCurrentUser; for network
        // errors the token is kept so the user can retry.
      } finally {
        setInitializing(false);
      }
    };

    initializeAuth();
  }, [loadCurrentUser]);

  const login = useCallback(async (credentials) => {
    const result = await authService.login(credentials);

    await tokenStorage.save(result.access_token);

    try {
      const currentUser = await authService.getCurrentUser();
      setUser(currentUser);

      return currentUser;
    } catch (error) {
      await tokenStorage.remove();
      setUser(null);
      throw error;
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await authService.logout();
    } finally {
      await tokenStorage.remove();
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
      // connectionError is updated inside loadCurrentUser.
    } finally {
      setInitializing(false);
    }
  }, [loadCurrentUser]);

  const changePassword = useCallback(async (payload) => {
    const result = await authService.changePassword(payload);

    // The API signs out every other session when the password changes
    // and returns a new token for this one.
    if (result?.access_token) {
      await tokenStorage.save(result.access_token);
    }

    return result;
  }, []);

  const updateUserProfile = useCallback(async (payload) => {
    const updatedUser = await authService.updateProfile(payload);
    setUser(updatedUser);

    return updatedUser;
  }, []);

  const value = useMemo(
    () => ({
      user,
      initializing,
      connectionError,
      retryConnection,
      isAuthenticated: Boolean(user),
      login,
      logout,
      refreshUser,
      updateUserProfile,
      changePassword,
    }),
    [
      user,
      initializing,
      connectionError,
      retryConnection,
      login,
      logout,
      refreshUser,
      updateUserProfile,
      changePassword,
    ]
  );

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}