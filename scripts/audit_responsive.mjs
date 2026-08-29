/**
 * Responsive audit.
 *
 * Loads every route at phone width and reports, per page, whether the document scrolls
 * sideways — and if so, exactly which elements are wider than the viewport. Horizontal
 * overflow is the single clearest signal of a layout that was never built for a phone,
 * and naming the offending element makes it fixable rather than a vague "it's broken".
 *
 *   EMBY_TOKEN=... node scripts/audit_responsive.mjs <baseUrl> [width]
 */
import { chromium } from "playwright";

const BASE = process.argv[2] || "http://127.0.0.1:3000";
const WIDTH = Number(process.argv[3] || 390);

const PROFILE = {
  id: 4, username: "demo@emby.app", email: "demo@emby.app",
  first_name: "Ada", last_name: "Okoro", full_name: "Ada Okoro", name: "Ada Okoro",
  onboarding_completed: true, email_verified: true, class_role: "student",
  class_head_verified: false, subscription_tier: "free", platform_role: "user",
};

const ROUTES = [
  "/", "/dashboard", "/courses", "/read", "/quiz", "/steeplechase", "/histology",
  "/flashcards", "/flashcards/manage", "/decks", "/analytics", "/study-plan",
  "/battles", "/battles/create", "/community", "/profile", "/settings",
  "/premium", "/session", "/brainstorming", "/class", "/class/curriculum",
];

const browser = await chromium.launch();
const ctx = await browser.newContext({
  viewport: { width: WIDTH, height: 844 },
  isMobile: true,
  hasTouch: true,
  deviceScaleFactor: 2,
});
await ctx.addInitScript(
  ([t, p]) => {
    try {
      sessionStorage.setItem("token", t);
      sessionStorage.setItem("refreshToken", t);
      sessionStorage.setItem("user", p);
    } catch {}
  },
  [process.env.EMBY_TOKEN || "demo", JSON.stringify(PROFILE)],
);

const page = await ctx.newPage();
const broken = [];

for (const route of ROUTES) {
  try {
    await page.goto(BASE + route, { waitUntil: "load", timeout: 30000 });
  } catch {
    console.log(`  ${route.padEnd(22)} LOAD FAILED`);
    continue;
  }
  await page.waitForTimeout(1800);

  const result = await page.evaluate((vw) => {
    const doc = document.documentElement;
    const overflow = doc.scrollWidth - vw;

    // Name the widest offenders so the fix is obvious.
    const culprits = [];
    if (overflow > 2) {
      for (const el of document.querySelectorAll("body *")) {
        const r = el.getBoundingClientRect();
        if (r.width === 0 || r.height === 0) continue;
        if (r.right > vw + 2 || r.left < -2) {
          const style = getComputedStyle(el);
          if (style.position === "fixed") continue; // off-canvas drawers are fine
          culprits.push({
            tag: el.tagName.toLowerCase(),
            cls: (el.className && String(el.className).slice(0, 70)) || "",
            right: Math.round(r.right),
            width: Math.round(r.width),
          });
        }
      }
    }
    culprits.sort((a, b) => b.right - a.right);

    // Also flag text that will be unreadably small on a phone.
    let tiny = 0;
    for (const el of document.querySelectorAll("p, span, li, td, label, button, a")) {
      const t = (el.textContent || "").trim();
      if (!t || t.length < 4) continue;
      const fs = parseFloat(getComputedStyle(el).fontSize);
      if (fs && fs < 11) tiny++;
    }

    return { overflow, culprits: culprits.slice(0, 3), tiny, scrollWidth: doc.scrollWidth };
  }, WIDTH);

  const status = result.overflow > 2 ? `OVERFLOW +${result.overflow}px` : "ok";
  console.log(`  ${route.padEnd(22)} ${status}${result.tiny > 8 ? `  (${result.tiny} tiny-text nodes)` : ""}`);
  if (result.overflow > 2) {
    broken.push({ route, ...result });
    for (const c of result.culprits) {
      console.log(`      <${c.tag}> w=${c.width} right=${c.right}  ${c.cls}`);
    }
  }
}

await browser.close();
console.log(`\n  ${broken.length} of ${ROUTES.length} routes overflow at ${WIDTH}px`);
