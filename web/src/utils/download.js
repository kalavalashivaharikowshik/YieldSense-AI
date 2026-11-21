export function getDownloadFilename(contentDisposition, fallbackFilename) {
  if (!contentDisposition) {
    return fallbackFilename;
  }

  const utf8Match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/);

  if (utf8Match?.[1]) {
    return decodeURIComponent(utf8Match[1]);
  }

  const normalMatch = contentDisposition.match(/filename="?([^";]+)"?/);

  return normalMatch?.[1] || fallbackFilename;
}

export function downloadBlob(blob, filename) {
  const downloadUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");

  anchor.href = downloadUrl;
  anchor.download = filename;

  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();

  // Revoking right after click() can cancel the download in Safari and
  // Firefox, so give the browser a moment to start it first.
  setTimeout(() => URL.revokeObjectURL(downloadUrl), 1000);
}
