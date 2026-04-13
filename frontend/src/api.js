export async function runLab() {
  const response = await fetch('/api/lab/run');
  if (!response.ok) {
    throw new Error(`实验编排失败：${response.status}`);
  }
  return response.json();
}
