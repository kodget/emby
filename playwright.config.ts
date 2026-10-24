import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/browser",
  fullyParallel: false,
  workers: 1,
  timeout: 60000,
  expect: { timeout: 15000 },
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:3100",
    browserName: "chromium",
    ...(process.platform === "win32" ? { channel: "msedge" } : {}),
    headless: true,
    serviceWorkers: "block",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  webServer: {
    command: "npm run dev -- --hostname 127.0.0.1 --port 3100",
    url: "http://127.0.0.1:3100/verify-email",
    reuseExistingServer: false,
    timeout: 240000,
    env: { EMBY_BROWSER_TESTS: "1", NEXT_PUBLIC_API_URL: "http://127.0.0.1:8600", NEXT_TELEMETRY_DISABLED: "1" },
  },
});
