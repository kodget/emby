/**
 * Brain Battle join-by-code checks, driven through a real browser.
 *
 *   EMBY_TOKEN=... BATTLE_CODE=ABC123 node scripts/verify_battles.mjs <baseUrl>
 */
import { chromium } from "playwright";

const BASE = process.argv[2] || "http://127.0.0.1:3000";
const CODE = process.env.BATTLE_CODE || "";

const PROFILE = {
  id: 4, username: "demo", email: "demo@emby.app",
  first_name: "Ada", last_name: "Okoro", full_name: "Ada Okoro", name: "Ada Okoro",
  onboarding_completed: true, email_verified: true, class_role: "student",
  class_head_verified: false, subscription_tier: "free", platform_role: "user",
};

let pass = 0, fail = 0;
const check = (name, ok, detail = "") => {
  if (ok) { pass++; console.log(`  PASS  ${name}`); }
  else { fail++; console.log(`  FAIL  ${name}${detail ? ` — ${detail}` : ""}`); }
};

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 430, height: 930 }, isMobile: true, hasTouch: true });
await ctx.addInitScript(
  ([t, p]) => { try { sessionStorage.setItem("token", t); sessionStorage.setItem("refreshToken", t); sessionStorage.setItem("user", p); } catch {} },
  [process.env.EMBY_TOKEN || "demo", JSON.stringify(PROFILE)],
);
const page = await ctx.newPage();
page.on("pageerror", (e) => console.log(`  ! page error: ${e.message}`));

console.log("\nBattles — page");
await page.goto(`${BASE}/battles`, { waitUntil: "load" });
await page.waitForTimeout(2500);

const body = (await page.textContent("body")) ?? "";
check("join card present", /Join a battle/i.test(body));
check("host route offered", /Host a battle/i.test(body));
check("code input present", (await page.locator("#battle-code").count()) === 1);

// The page no longer forces its own dark theme.
const bg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
check("uses the app theme, not a hardcoded dark page", !/rgb\(10, ?10, ?10\)/.test(bg), bg);

console.log("\nBattles — code validation");
await page.fill("#battle-code", "ZZZZZZ");
await page.waitForTimeout(2500);
check("rejects an unknown code", /No battle with that code/i.test((await page.textContent("body")) ?? ""));
check(
  "join stays disabled for a bad code",
  await page.locator('button:has-text("Join battle")').isDisabled(),
);

if (CODE) {
  console.log("\nBattles — a real code");
  await page.fill("#battle-code", "");
  // Typed lowercase on purpose: the field should normalise it.
  await page.fill("#battle-code", CODE.toLowerCase());
  await page.waitForTimeout(2500);

  const value = await page.inputValue("#battle-code");
  check("input normalises to uppercase", value === CODE.toUpperCase(), value);

  const after = (await page.textContent("body")) ?? "";
  check("previews the battle before joining", /question/i.test(after) && !/No battle with that code/i.test(after));
  check(
    "join becomes available",
    !(await page.locator('button:has-text("Join battle")').isDisabled()),
  );
}

await browser.close();
console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
