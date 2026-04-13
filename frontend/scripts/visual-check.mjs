import { chromium } from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';

const url = process.env.CHECK_URL || 'http://127.0.0.1:5173';
const screenshotDir = path.resolve('screenshots');
const localPlaywrightLibs = path.join(
  process.env.HOME || '',
  '.local/playwright-libs/root/usr/lib/x86_64-linux-gnu',
);

try {
  await fs.access(localPlaywrightLibs);
  process.env.LD_LIBRARY_PATH = [localPlaywrightLibs, process.env.LD_LIBRARY_PATH].filter(Boolean).join(':');
} catch {
  // System-level browser libraries are already available on many WSL installs.
}

await fs.mkdir(screenshotDir, { recursive: true });

const browser = await chromium.launch();
const viewports = [
  { name: 'desktop', width: 1440, height: 980 },
  { name: 'mobile', width: 390, height: 860 },
];

for (const viewport of viewports) {
  const page = await browser.newPage({ viewport });
  await page.goto(url, { waitUntil: 'networkidle' });
  await page.waitForSelector('canvas.tunnel-canvas');
  await page.waitForTimeout(900);
  const stats = await page.$eval('canvas.tunnel-canvas', (canvas) => {
    const gl = canvas.getContext('webgl2') || canvas.getContext('webgl');
    if (!gl) return { ok: false, reason: 'webgl context missing' };
    const width = canvas.width;
    const height = canvas.height;
    const pixels = new Uint8Array(width * height * 4);
    gl.readPixels(0, 0, width, height, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
    let nonBackground = 0;
    let bright = 0;
    for (let index = 0; index < pixels.length; index += 4) {
      const r = pixels[index];
      const g = pixels[index + 1];
      const b = pixels[index + 2];
      if (Math.abs(r - 247) + Math.abs(g - 248) + Math.abs(b - 251) > 18) {
        nonBackground += 1;
      }
      if (r + g + b > 80) {
        bright += 1;
      }
    }
    const total = width * height;
    return {
      ok: nonBackground / total > 0.015 && bright / total > 0.5,
      nonBackgroundRatio: nonBackground / total,
      brightRatio: bright / total,
    };
  });
  if (!stats.ok) {
    throw new Error(`${viewport.name} canvas check failed: ${JSON.stringify(stats)}`);
  }
  await page.screenshot({ path: path.join(screenshotDir, `${viewport.name}.png`), fullPage: true });
  await page.close();
}

await browser.close();
console.log('visual checks passed');
