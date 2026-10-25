import { defineConfig } from "@playwright/test";
import uploadConfig from "./playwright.upload.config";

const server = uploadConfig.webServer;
if (!server || Array.isArray(server)) throw new Error("Expected one isolated browser test server.");

// Reuse the isolated test preview when repeating a repair journey after a cold build.
export default defineConfig({
  ...uploadConfig,
  grep: /production repair/,
  timeout: 180000,
  expect: { ...uploadConfig.expect, timeout: 60000 },
  webServer: { ...server, reuseExistingServer: true },
});
