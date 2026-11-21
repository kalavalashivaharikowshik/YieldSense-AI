// Lets the API client tell the auth context that the server rejected the
// saved token (expired, or revoked after a password change).

const listeners = new Set();

export const sessionEvents = {
  onSessionExpired(listener) {
    listeners.add(listener);

    return () => listeners.delete(listener);
  },

  emitSessionExpired() {
    listeners.forEach((listener) => listener());
  },
};
