import { chromium, devices } from "playwright";
const [OUT, ...urls] = process.argv.slice(2);
const P={id:4,username:"demo@emby.app",email:"demo@emby.app",first_name:"Ada",last_name:"Okoro",full_name:"Ada Okoro",name:"Ada Okoro",onboarding_completed:true,email_verified:true,class_role:"student",class_head_verified:false,subscription_tier:"free",platform_role:"user"};
const b=await chromium.launch();
const c=await b.newContext({...devices["iPhone 13"]});
await c.addInitScript(([t,p])=>{try{sessionStorage.setItem("token",t);sessionStorage.setItem("refreshToken",t);sessionStorage.setItem("user",p);}catch{}},[process.env.EMBY_TOKEN||"demo",JSON.stringify(P)]);
const pg=await c.newPage();
for (const u of urls){
  await pg.goto(u,{waitUntil:"load",timeout:40000});
  await pg.waitForTimeout(2600);
  const name=(new URL(u).pathname.replace(/\//g,"_"))||"_root";
  await pg.screenshot({path:`${OUT}/${name}.png`});
  console.log("  "+new URL(u).pathname);
}
await b.close();
