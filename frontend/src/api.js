export async function runLab(files = {}) {
  const selectedFiles = Object.entries(files).filter(([, file]) => file);
  const requestOptions = selectedFiles.length
    ? {
        method: 'POST',
        body: selectedFiles.reduce((formData, [fieldName, file]) => {
          formData.append(fieldName, file);
          return formData;
        }, new FormData()),
      }
    : undefined;
  const response = await fetch('/api/lab/run', requestOptions);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.error || `实验编排失败：${response.status}`);
  }
  return response.json();
}
