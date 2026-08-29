import { chromium, devices } from "playwright";
const [BASE, OUT] = process.argv.slice(2);
const b = await chromium.launch();
const c = await b.newContext({ ...devices["iPhone 13"] });
const p = await c.newPage();

const failed = [];
p.on("requestfailed", r => failed.push(`FAILED ${r.failure()?.errorText} ${r.url().slice(0,110)}`));
p.on("response", r => { if (r.status() >= 400) failed.push(`HTTP ${r.status()} ${r.url().slice(0,110)}`); });
p.on("pageerror", e => failed.push(`JS ERROR: ${e.message.slice(0,120)}`));

await p.goto(BASE + "/signin", { waitUntil: "load", timeout: 45000 });
await p.waitForTimeout(2000);
await p.fill('input[type="email"], input[name="email"]', "demo@emby.app");
await p.fill('input[type="password"], input[name="password"]', "emby1234");
await p.click('button[type="submit"]');
await p.waitForTimeout(8000);

const info = await p.evaluate(() => {
  const doc = document.documentElement;
  const sheets = [...document.styleSheets].length;
  let tailwindLoaded = false;
  try {
    // A Tailwind utility should resolve to a real computed value.
    const probe = document.createElement("div");
    probe.className = "hidden";
    document.body.appendChild(probe);
    tailwindLoaded = getComputedStyle(probe).display === "none";
    probe.remove();
  } catch {}
  return {
    url: location.pathname,
    innerWidth: window.innerWidth,
    devicePixelRatio: window.devicePixelRatio,
    scrollWidth: doc.scrollWidth,
    stylesheets: sheets,
    tailwindLoaded,
    tabBarVisible: !!document.querySelector('nav[aria-label="Primary"]'),
    sidebarVisible: (() => { const a = document.querySelector("aside[data-collapsed]"); return a ? getComputedStyle(a).display !== "none" : false; })(),
    bodyFont: getComputedStyle(document.body).fontFamily.slice(0, 40),
  };
});
console.log(JSON.stringify(info, null, 2));
console.log("\nnetwork/JS problems:");
console.log(failed.length ? failed.slice(0, 12).map(f => "  " + f).join("\n") : "  none");
await p.screenshot({ path: OUT, fullPage: false });
await b.close();
