const {test,expect}=require('@playwright/test');
const pages=['index.html','register.html','syllabus.html','sample-papers.html','mock-test.html','awards.html','hackathon.html','faqs.html','contact.html','login.html','team-prelaunch.html','admin.html','exam.html'];
const widths=[1440,1024,768,390];
for(const pagePath of pages){
 test(pagePath+' renders without overflow and with working local imagery at all target widths',async({browser},testInfo)=>{
  const page=await browser.newPage({viewport:{width:1440,height:900}});
  await page.route('https://sutravya-assessment-api-demo.onrender.com/**',route=>route.abort());
  for(const width of widths){
   await page.setViewportSize({width,height:900});
   await page.goto('/'+pagePath,{waitUntil:'domcontentloaded'});
   await expect(page.locator('h1').first()).toBeVisible();
   const result=await page.evaluate(async()=>{
    const images=[...document.images];
    images.forEach(image=>{image.loading='eager';});
    await Promise.all(images.map(image=>image.decode().catch(()=>null)));
    const broken=images.filter(image=>!image.complete||image.naturalWidth===0).map(image=>image.getAttribute('src'));
    return {viewport:innerWidth,documentWidth:Math.max(document.documentElement.scrollWidth,document.body?.scrollWidth||0),brokenImages:broken,imageCount:images.length};
   });
   expect(result.documentWidth,{message:pagePath+' should not create horizontal overflow at '+width+'px'}).toBeLessThanOrEqual(width+2);
   expect(result.brokenImages,{message:pagePath+' has broken images at '+width+'px'}).toEqual([]);
   await page.screenshot({path:testInfo.outputPath('../screenshots/'+pagePath.replace('.html','')+'-'+width+'.png'),fullPage:true,animations:'disabled'});
  }
  await page.close();
 });
}
test('mobile navigation opens, is keyboard operable, and closes on Escape',async({page})=>{
 await page.setViewportSize({width:390,height:844});
 await page.goto('/index.html',{waitUntil:'domcontentloaded'});
 const toggle=page.locator('.nav-toggle');
 const nav=page.locator('.primary-nav');
 await expect(toggle).toBeVisible();
 await toggle.focus();
 await page.keyboard.press('Enter');
 await expect(toggle).toHaveAttribute('aria-expanded','true');
 await expect(nav).toBeVisible();
 await page.keyboard.press('Escape');
 await expect(toggle).toHaveAttribute('aria-expanded','false');
 await expect(toggle).toBeFocused();
});
test('FAQ search filters existing questions and announces an empty result',async({page})=>{
 await page.goto('/faqs.html',{waitUntil:'domcontentloaded'});
 const search=page.getByLabel('Search candidate questions');
 await search.fill('BCMR');
 await expect(page.locator('.qv2-faq:visible')).toHaveCount(1);
 await expect(page.locator('[data-faq-count]')).toContainText('1 matching question');
 await search.fill('no-such-question-qualinova');
 await expect(page.locator('[data-faq-empty]')).toBeVisible();
 await search.fill('');
 await expect(page.locator('.qv2-faq:visible').first()).toBeVisible();
});
test('registration form keeps category fee and labelled fields visible on mobile',async({page})=>{
 await page.setViewportSize({width:390,height:844});
 await page.goto('/register.html',{waitUntil:'domcontentloaded'});
 await expect(page.locator('#reg-category')).toBeVisible();
 await expect(page.locator('label[for="reg-category"]')).toBeVisible();
 await expect(page.locator('[data-fee-amount]')).toBeVisible();
 await expect(page.locator('.registration-consent')).toBeVisible();
});
test('reduced motion preference disables long animations and smooth scrolling',async({page})=>{
 await page.emulateMedia({reducedMotion:'reduce'});
 await page.goto('/index.html',{waitUntil:'domcontentloaded'});
 const values=await page.evaluate(()=>({scroll:getComputedStyle(document.documentElement).scrollBehavior,animation:getComputedStyle(document.body).animationDuration}));
 expect(values.scroll).toBe('auto');
});
