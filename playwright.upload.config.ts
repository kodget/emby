import { defineConfig } from "@playwright/test";
import base from "./playwright.config";

// Keep upload acceptance independent of other chats' previews and test artifacts.
export default defineConfig({
  ...base,
  outputDir: ".test-results-uploads",
  use: { ...base.use, baseURL: "http://127.0.0.1:3118", trace: "off" },
  webServer: {
    command: "node node_modules/next/dist/bin/next dev --webpack --hostname 127.0.0.1 --port 3118",
    url: "http://127.0.0.1:3118/verify-email",
    reuseExistingServer: false,
    timeout: 240000,
    env: { EMBY_BROWSER_TESTS: "uploads", NEXT_PUBLIC_API_URL: "http://127.0.0.1:8600", NEXT_TELEMETRY_DISABLED: "1" },
  },
});
