import { chromium } from "playwright";
const URL_ = process.argv[2];
const b = await chromium.launch();
const p = await b.newPage();
const fontFiles = [];
p.on("response", r => { const u = r.url(); if (/\.(woff2?|ttf|otf)(\?|$)/i.test(u)) fontFiles.push(u); });
await p.goto(URL_, { waitUntil: "networkidle", timeout: 60000 });
await p.waitForTimeout(2500);
const info = await p.evaluate(() => {
  const seen = new Map();
  const sample = (el) => {
    const cs = getComputedStyle(el);
    const key = cs.fontFamily;
    if (!key) return;
    const txt = (el.textContent || "").trim().slice(0, 40);
    if (!seen.has(key)) seen.set(key, { count: 0, weights: new Set(), sizes: new Set(), sample: txt });
    const e = seen.get(key);
    e.count++; e.weights.add(cs.fontWeight); e.sizes.add(cs.fontSize);
  };
  sample(document.body);
  for (const el of document.querySelectorAll("h1,h2,h3,h4,p,span,a,button,li,div")) sample(el);
  return {
    families: [...seen.entries()].map(([f, v]) => ({
      family: f, count: v.count,
      weights: [...v.weights].sort(), sizes: [...v.sizes].slice(0, 8), sample: v.sample,
    })).sort((a,b)=>b.count-a.count).slice(0, 8),
    links: [...document.querySelectorAll('link[rel="stylesheet"], link[rel="preload"][as="font"]')].map(l=>l.href).filter(h=>/font/i.test(h)),
  };
});
console.log("FONT FILES LOADED:");
[...new Set(fontFiles)].forEach(f => console.log("  " + f));
console.log("\nSTYLESHEET/FONT LINKS:");
info.links.forEach(l => console.log("  " + l));
console.log("\nCOMPUTED FAMILIES (most used first):");
for (const f of info.families) {
  console.log(`  ${f.family}`);
  console.log(`     used ${f.count}x | weights ${f.weights.join(",")} | sizes ${f.sizes.join(",")}`);
}
await b.close();
