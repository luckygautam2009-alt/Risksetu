const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:process.env.PLAYWRIGHT_CHANNEL||'chrome'});
 const context=await browser.newContext();const page=await context.newPage();
 await page.goto('http://127.0.0.1:8000');
 await page.getByText('73.2',{exact:false}).first().waitFor();
 await page.evaluate(()=>navigator.serviceWorker.ready);
 await page.waitForFunction(()=>navigator.serviceWorker.controller!==null);
 await context.setOffline(true);
 await page.reload({waitUntil:'domcontentloaded'});
 await page.getByRole('heading',{name:'Your surroundings, understood.'}).waitFor();
 await page.getByText('73.2',{exact:false}).first().waitFor();
 await page.getByRole('button',{name:'Emergency information',exact:false}).click();
 await page.getByRole('heading',{name:'Emergency information',exact:true}).waitFor();
 await browser.close();console.log('PWA smoke passed: first-visit asset precache, offline reload, cached risk data, emergency information.');
})().catch(e=>{console.error(e);process.exit(1)});
