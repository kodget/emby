const puppeteer = require('puppeteer-core');
const path = require('path');

(async () => {
  try {
    const browser = await puppeteer.launch({
      executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
      headless: "new"
    });
    
    console.log("Browser launched");
    
    const page1 = await browser.newPage();
    const url1 = 'file:///' + path.resolve('PRD.html').replace(/\\/g, '/');
    console.log("Loading", url1);
    await page1.goto(url1, {waitUntil: 'networkidle0'});
    await page1.pdf({ path: 'PRD.pdf', format: 'A4', printBackground: true, margin: {top: '20px', bottom: '20px', left: '20px', right: '20px'} });
    console.log("PRD.pdf saved");

    const page2 = await browser.newPage();
    const url2 = 'file:///' + path.resolve('TECHNICAL_ARCHITECTURE.html').replace(/\\/g, '/');
    console.log("Loading", url2);
    await page2.goto(url2, {waitUntil: 'networkidle0'});
    await page2.pdf({ path: 'TECHNICAL_ARCHITECTURE.pdf', format: 'A4', printBackground: true, margin: {top: '20px', bottom: '20px', left: '20px', right: '20px'} });
    console.log("TECHNICAL_ARCHITECTURE.pdf saved");

    await browser.close();
    console.log("Done");
  } catch(e) {
    console.error(e);
  }
})();
