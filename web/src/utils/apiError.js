export function getApiErrorMessage(
  error,
  fallback = "Something went wrong"
) {
  const detail = error?.response?.data?.detail;

  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    return detail
      .map((item) => item.msg || "Invalid input")
      .join(", ");
  }

  if (error?.code === "ECONNABORTED") {
    return "The request timed out. Please try again.";
  }

  if (!error?.response) {
    return "Unable to connect to the server. Check your internet connection and try again.";
  }

  if (error.response.status === 401) {
    return "Your session has expired. Please log in again.";
  }

  if (error.response.status === 403) {
    return "You do not have permission to perform this action.";
  }

  const status = error.response.status;

  if (status === 404) {
    return "The requested record was not found.";
  }

  if (status === 413) {
    return "The file is too large to upload.";
  }

  if (status === 429) {
    return "Too many attempts. Please wait a moment and try again.";
  }

  if (status >= 500) {
    return "The server had a problem. Please try again shortly.";
  }

  return fallback;
}