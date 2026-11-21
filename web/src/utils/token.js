const TOKEN_KEY = "token";

// Fired when the API rejects the stored token (expired, or revoked after
// a password change), so the app can return to the login page.
export const SESSION_EXPIRED_EVENT = "yieldsense:session-expired";

export const saveToken = (token) => {
  localStorage.setItem(TOKEN_KEY, token);
};

export const getToken = () => {
  return localStorage.getItem(TOKEN_KEY);
};

export const removeToken = () => {
  localStorage.removeItem(TOKEN_KEY);
};

export const isAuthenticated = () => {
  return !!getToken();
};
