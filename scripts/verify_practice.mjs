/**
 * End-to-end check of the practice flow against a live backend.
 *
 * Drives a real browser through setup → round → results and asserts the behaviour that
 * only shows up when the pieces run together: the timer counting down, answers not being
 * present in the page before submission, feedback appearing after, and the free-tier
 * allowance being displayed.
 *
 *   EMBY_TOKEN=... node scripts/verify_practice.mjs <baseUrl>
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
const check = (name, ok, detail = "") => {
  if (ok) {
    pass++;
    console.log(`  PASS  ${name}`);
  } else {
    fail++;
    console.log(`  FAIL  ${name}${detail ? ` — ${detail}` : ""}`);
  }
};

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 430, height: 900 }, isMobile: true, hasTouch: true });
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

const page = await ctx.newPage();
page.on("pageerror", (e) => console.log(`  ! page error: ${e.message}`));

console.log("\nSteeplechase — setup");
await page.goto(`${BASE}/steeplechase`, { waitUntil: "load" });
await page.waitForTimeout(2500);

const body = await page.textContent("body");
check("setup screen renders", /Steeplechase/i.test(body ?? ""));
check("shows the 30-second rule", /30 seconds/i.test(body ?? ""));
// The allowance line differs by tier; either wording proves the server-supplied
// entitlement reached the UI.
check(
  "shows the server-supplied allowance",
  /free rounds left this month|Unlimited rounds/i.test(body ?? ""),
);
check("offers sections", (await page.locator('button[aria-pressed]').count()) > 0);

const startBtn = page.locator('button:has-text("Start")');
check("start button present", (await startBtn.count()) > 0);

console.log("\nSteeplechase — round");
await startBtn.first().click();
await page.waitForTimeout(3000);

const runBody = (await page.textContent("body")) ?? "";
check("station counter shows", /Station 1\s*\/\s*\d+/i.test(runBody));
check("timer is running", /0:[0-2]\d/.test(runBody));
check("answer input present", (await page.locator("#main-answer").count()) === 1);
check("specimen image rendered", (await page.locator("figure img").count()) === 1);

// The correct answer must not be anywhere in the DOM before submitting.
const html = (await page.content()).toLowerCase();
check(
  "no answer leaked before submit",
  !html.includes("accepted_answers") && !html.includes("correct_index"),
);

// Timer must actually decrement.
const t1 = (runBody.match(/0:(\d\d)/) || [])[1];
await page.waitForTimeout(2600);
const t2 = ((await page.textContent("body")) ?? "").match(/0:(\d\d)/)?.[1];
check("timer counts down", Number(t2) < Number(t1), `${t1} -> ${t2}`);

console.log("\nSteeplechase — answering");
await page.fill("#main-answer", "radial nerve");
await page.click('button:has-text("Submit answer")');
await page.waitForTimeout(2000);

const afterBody = (await page.textContent("body")) ?? "";
check("feedback shown after submit", /Correct|Not quite/i.test(afterBody));
check("timer pauses on feedback", /Paused/i.test(afterBody));
check("advance control appears", /Next station|Finish round/i.test(afterBody));

console.log("\nHistology — same flow, different pool");
await page.goto(`${BASE}/histology`, { waitUntil: "load" });
await page.waitForTimeout(2500);
const histBody = (await page.textContent("body")) ?? "";
check(
  "histology screen renders",
  /Histology/i.test(histBody) && /(30 seconds|No stations ready)/i.test(histBody),
);

await browser.close();
console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
