/**
 * Visual verification harness.
 *
 * Boots a browser against a running Emby server, signs in by seeding the same
 * sessionStorage keys the real auth flow writes, and captures each route at both a phone
 * and a desktop viewport. Used to check the UI actually looks right rather than merely
 * type-checking.
 *
 *   node scripts/screenshot.mjs [baseUrl] [outDir]
 */
import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";

const BASE = process.argv[2] || "http://127.0.0.1:3000";
const OUT = process.argv[3] || "./.screenshots";

// Mirrors what lib/guards.ts checks: a token plus a profile that has finished
// onboarding and, if a class head, been verified.
const PROFILE = {
  id: 4,
  username: "demo",
  email: "demo@emby.app",
  first_name: "Ada",
  last_name: "Okoro",
  full_name: "Ada Okoro",
  name: "Ada Okoro",
  onboarding_completed: true,
  email_verified: true,
  class_role: "student",
  class_head_verified: false,
  subscription_tier: "free",
  platform_role: "user",
};

const ROUTES = [
  ["dashboard", "/dashboard"],
  ["quiz", "/quiz"],
  ["steeplechase", "/steeplechase"],
  ["flashcards", "/flashcards"],
  ["analytics", "/analytics"],
  ["courses", "/courses"],
  ["landing", "/"],
];

const VIEWPORTS = [
  ["mobile", { width: 390, height: 844 }, 3],
  ["desktop", { width: 1440, height: 900 }, 2],
];

fs.mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch();
let captured = 0;

for (const [vpName, viewport, dpr] of VIEWPORTS) {
  const context = await browser.newContext({
    viewport,
    deviceScaleFactor: dpr,
    isMobile: vpName === "mobile",
    hasTouch: vpName === "mobile",
  });

  // Seed auth for every document in this context before any app code runs.
  await context.addInitScript(
    ([token, profile]) => {
      try {
        sessionStorage.setItem("token", token);
        sessionStorage.setItem("refreshToken", token);
        sessionStorage.setItem("user", profile);
      } catch {}
    },
    [process.env.EMBY_TOKEN || "demo-token-for-screenshots", JSON.stringify(PROFILE)],
  );

  const page = await context.newPage();
  page.on("pageerror", (e) => console.log(`  ! ${vpName} page error: ${e.message}`));

  for (const [name, route] of ROUTES) {
    try {
      await page.goto(`${BASE}${route}`, { waitUntil: "networkidle", timeout: 45000 });
    } catch {
      // networkidle can never settle if something polls; a load event is enough.
      await page.goto(`${BASE}${route}`, { waitUntil: "load", timeout: 45000 });
    }
    // Let entrance animations settle so screenshots aren't caught mid-transition.
    await page.waitForTimeout(1400);

    const file = path.join(OUT, `${name}-${vpName}.png`);
    await page.screenshot({ path: file, fullPage: false });
    captured++;
    console.log(`  captured ${path.basename(file)}  (${page.url().replace(BASE, "")})`);
  }

  await context.close();
}

await browser.close();
console.log(`\n${captured} screenshots -> ${OUT}`);
