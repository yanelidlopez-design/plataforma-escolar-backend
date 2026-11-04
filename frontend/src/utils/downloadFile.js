export async function downloadFile(response, fallbackFilename) {
  const blob = response.data;
  if (blob.type?.includes('application/json')) {
    const body = JSON.parse(await blob.text());
    throw new Error(body.detail || body.error || 'No se pudo generar el archivo.');
  }

  const disposition = response.headers['content-disposition'] || '';
  const filename = disposition.match(/filename="?([^";]+)"?/i)?.[1] || fallbackFilename;
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => window.URL.revokeObjectURL(url), 1000);
}
