/**
 * Study planner persistence checks.
 *
 * The reported failure was that plans did not survive a refresh, because the planner was
 * pure client-side Redux and never called the API. These checks drive a real browser and
 * assert the opposite: what you add is still there after a full page reload, and so is a
 * completion tick.
 *
 *   EMBY_TOKEN=... node scripts/verify_planner.mjs <baseUrl>
 */
import { chromium } from "playwright";

const BASE = process.argv[2] || "http://127.0.0.1:3000";

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
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
await ctx.addInitScript(
  ([t, p]) => { try { sessionStorage.setItem("token", t); sessionStorage.setItem("refreshToken", t); sessionStorage.setItem("user", p); } catch {} },
  [process.env.EMBY_TOKEN || "demo", JSON.stringify(PROFILE)],
);
const page = await ctx.newPage();
page.on("pageerror", (e) => console.log(`  ! page error: ${e.message}`));

// Track that the planner is actually talking to the server at all.
let hitSchedule = false;
page.on("response", (r) => {
  if (r.url().includes("/api/schedule/")) hitSchedule = true;
});

console.log("\nPlanner — loads from the server");
await page.goto(`${BASE}/study-plan`, { waitUntil: "load" });
await page.waitForTimeout(3000);

check("page renders", /Study Plan/i.test((await page.textContent("body")) ?? ""));
check("calls /api/schedule/ (it never did before)", hitSchedule);

const marker = `Persist check ${Date.now().toString().slice(-6)}`;

console.log("\nPlanner — an added item survives a reload");
// Create through the same API the UI uses, then prove the UI reads it back.
const created = await page.evaluate(async (title) => {
  const token = sessionStorage.getItem("token");
  const res = await fetch(`${window.location.origin.replace("3000", "8000")}/api/schedule/`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({
      activity_type: "read",
      title,
      scheduled_date: new Date().toISOString().slice(0, 10),
      estimated_minutes: 20,
    }),
  });
  return res.ok ? await res.json() : null;
}, marker);

check("item created via the API", Boolean(created?.id), created ? "" : "create failed");

await page.reload({ waitUntil: "load" });
await page.waitForTimeout(3000);
const afterReload = (await page.textContent("body")) ?? "";
check("item is still there after a full reload", afterReload.includes(marker));

console.log("\nPlanner — completion sticks");
if (created?.id) {
  await page.evaluate(async (id) => {
    const token = sessionStorage.getItem("token");
    await fetch(`${window.location.origin.replace("3000", "8000")}/api/schedule/${id}/complete/`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });
  }, created.id);

  await page.reload({ waitUntil: "load" });
  await page.waitForTimeout(3000);

  // A completed item renders with a line-through title.
  const struck = await page
    .locator(`text=${marker}`)
    .first()
    .evaluate((el) => getComputedStyle(el).textDecorationLine)
    .catch(() => "");
  check("completion survives a reload", /line-through/.test(struck), struck || "no style read");

  // Tidy up so repeated runs do not accumulate rows.
  await page.evaluate(async (id) => {
    const token = sessionStorage.getItem("token");
    await fetch(`${window.location.origin.replace("3000", "8000")}/api/schedule/${id}/`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });
  }, created.id);
}

await browser.close();
console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
