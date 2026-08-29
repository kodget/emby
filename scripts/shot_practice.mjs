import { chromium } from "playwright";
const [BASE, OUT] = process.argv.slice(2);
const P = {id:4,username:"demo",email:"demo@emby.app",first_name:"Ada",last_name:"Okoro",full_name:"Ada Okoro",name:"Ada Okoro",onboarding_completed:true,email_verified:true,class_role:"student",class_head_verified:false,subscription_tier:"free",platform_role:"user"};
const b = await chromium.launch();
const c = await b.newContext({viewport:{width:430,height:932},isMobile:true,hasTouch:true,deviceScaleFactor:2});
await c.addInitScript(([t,p])=>{try{sessionStorage.setItem("token",t);sessionStorage.setItem("refreshToken",t);sessionStorage.setItem("user",p);}catch{}},[process.env.EMBY_TOKEN||"demo",JSON.stringify(P)]);
const pg = await c.newPage();
await pg.goto(BASE+"/steeplechase",{waitUntil:"load"}); await pg.waitForTimeout(2800);
await pg.screenshot({path:`${OUT}/setup.png`}); console.log("setup");
await pg.locator('button:has-text("Start")').first().click(); await pg.waitForTimeout(3000);
await pg.screenshot({path:`${OUT}/station.png`}); console.log("station");
await pg.fill("#main-answer","radial nerve");
const opt = pg.locator('button[aria-pressed="false"]');
await pg.click('button:has-text("Submit answer")'); await pg.waitForTimeout(2200);
await pg.screenshot({path:`${OUT}/reveal.png`}); console.log("reveal");
// blitz through the rest to reach results
for (let i=0;i<8;i++){
  const next = pg.locator('button:has-text("Next station"), button:has-text("Finish round")');
  if (await next.count()===0) break;
  await next.first().click(); await pg.waitForTimeout(1800);
  if (await pg.locator("#main-answer").count()){ await pg.fill("#main-answer","median nerve"); await pg.click('button:has-text("Submit answer")'); await pg.waitForTimeout(1600); }
  else break;
}
const fin = pg.locator('button:has-text("Finish round")');
if (await fin.count()) { await fin.first().click(); await pg.waitForTimeout(3500); }
await pg.screenshot({path:`${OUT}/results.png`}); console.log("results");
await b.close();
