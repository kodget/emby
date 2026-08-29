/**
 * Interactive checks for behaviour a screenshot cannot prove.
 *
 * Covers the explicit layout requirements: the desktop sidebar collapses to an icon rail
 * and remembers that across navigation and reload, the mobile tab bar is present and the
 * More sheet opens, and the shell survives on routes that previously rendered bare.
 *
 *   node scripts/verify_ui.mjs <baseUrl>
 */
import { chromium } from "playwright";

const BASE = process.argv[2] || "http://127.0.0.1:3000";

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

let pass = 0;
let fail = 0;
function check(name, ok, detail = "") {
  if (ok) {
    pass++;
    console.log(`  PASS  ${name}`);
  } else {
    fail++;
    console.log(`  FAIL  ${name}${detail ? ` — ${detail}` : ""}`);
  }
}

const browser = await chromium.launch();

async function makeContext(viewport, isMobile) {
  const ctx = await browser.newContext({
    viewport,
    isMobile,
    hasTouch: isMobile,
    deviceScaleFactor: 2,
  });
  await ctx.addInitScript(
    ([token, profile]) => {
      try {
        sessionStorage.setItem("token", token);
        sessionStorage.setItem("refreshToken", token);
        sessionStorage.setItem("user", profile);
      } catch {}
    },
    [process.env.EMBY_TOKEN || "demo", JSON.stringify(PROFILE)],
  );
  return ctx;
}

// ---------------------------------------------------------------- desktop
console.log("\nDesktop — collapsible sidebar (requirement 15)");
{
  const ctx = await makeContext({ width: 1440, height: 900 }, false);
  const page = await ctx.newPage();
  await page.goto(`${BASE}/dashboard`, { waitUntil: "load" });
  await page.waitForTimeout(1200);

  const aside = page.locator("aside[data-collapsed]");
  check("sidebar renders", (await aside.count()) === 1);

  const wideBox = await aside.boundingBox();
  check("starts expanded", (wideBox?.width ?? 0) > 200, `width=${wideBox?.width}`);

  await page.click('button[aria-label="Collapse sidebar"]');
  await page.waitForTimeout(600);
  const narrowBox = await aside.boundingBox();
  check("collapses to an icon rail", (narrowBox?.width ?? 999) < 100, `width=${narrowBox?.width}`);

  const labelVisible = await page.locator('aside a:has-text("Analytics")').first().isVisible().catch(() => false);
  check("labels hidden when collapsed", !labelVisible);

  const tooltip = await page.locator('aside a[title="Analytics"]').count();
  check("collapsed items keep an accessible label", tooltip > 0);

  // Persistence across navigation
  await page.goto(`${BASE}/quiz`, { waitUntil: "load" });
  await page.waitForTimeout(1000);
  const afterNav = await page.locator("aside[data-collapsed]").boundingBox();
  check("stays collapsed after navigating", (afterNav?.width ?? 999) < 100, `width=${afterNav?.width}`);

  // Persistence across a full reload
  await page.reload({ waitUntil: "load" });
  await page.waitForTimeout(1000);
  const afterReload = await page.locator("aside[data-collapsed]").boundingBox();
  check("stays collapsed after reload", (afterReload?.width ?? 999) < 100, `width=${afterReload?.width}`);

  await page.click('button[aria-label="Expand sidebar"]');
  await page.waitForTimeout(600);
  const reExpanded = await page.locator("aside[data-collapsed]").boundingBox();
  check("expands again", (reExpanded?.width ?? 0) > 200, `width=${reExpanded?.width}`);

  // Requirement 10: analytics must keep the app shell.
  await page.goto(`${BASE}/analytics`, { waitUntil: "load" });
  await page.waitForTimeout(1200);
  check("sidebar still present on /analytics", (await page.locator("aside[data-collapsed]").count()) === 1);

  await page.goto(`${BASE}/class/curriculum`, { waitUntil: "load" });
  await page.waitForTimeout(1200);
  check("sidebar still present on /class/*", (await page.locator("aside[data-collapsed]").count()) === 1);

  await ctx.close();
}

// ----------------------------------------------------------------- mobile
console.log("\nMobile — app-style navigation");
{
  const ctx = await makeContext({ width: 390, height: 844 }, true);
  const page = await ctx.newPage();
  await page.goto(`${BASE}/dashboard`, { waitUntil: "load" });
  await page.waitForTimeout(1400);

  const tabbar = page.locator('nav[aria-label="Primary"]');
  check("bottom tab bar renders", await tabbar.isVisible());

  const sidebarHidden = await page.locator("aside[data-collapsed]").isVisible().catch(() => false);
  check("desktop sidebar hidden on mobile", !sidebarHidden);

  for (const label of ["Home", "Learn", "Practice", "Review", "More"]) {
    check(`tab "${label}" present`, (await tabbar.locator(`text=${label}`).count()) > 0);
  }

  await page.click('button:has-text("More")');
  await page.waitForTimeout(800);
  const sheet = page.locator('div[role="dialog"][aria-label="More"]');
  check("More sheet opens", await sheet.isVisible());
  check("sheet lists Analytics", (await sheet.locator("text=Analytics").count()) > 0);

  await page.keyboard.press("Escape");
  await page.waitForTimeout(600);
  check("Escape closes the sheet", !(await sheet.isVisible().catch(() => false)));

  await ctx.close();
}

await browser.close();
console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
