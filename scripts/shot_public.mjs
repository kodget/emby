import { chromium } from "playwright";
const BASE = process.argv[2], OUT = process.argv[3];
const b = await chromium.launch();
for (const [vp, viewport] of [["desktop",{width:1440,height:900}],["mobile",{width:390,height:844}]]) {
  const c = await b.newContext({ viewport, deviceScaleFactor: 2 });
  const p = await c.newPage();
  for (const [name, route, y] of [["landing","/",0],["landing-steeple","/",2400],["landing-pricing","/",3600],["premium","/premium",0]]) {
    await p.goto(BASE+route, { waitUntil: "load", timeout: 45000 });
    await p.waitForTimeout(1200);
    if (y) await p.evaluate((yy)=>window.scrollTo(0,yy), y);
    await p.waitForTimeout(700);
    await p.screenshot({ path: `${OUT}/${name}-${vp}.png` });
    console.log("  ", name, vp);
  }
  await c.close();
}
await b.close();
