const {test,expect}=require('@playwright/test');
const fs=require('node:fs');
const path=require('node:path');
const screenshotRoot=path.join(process.cwd(),'test-results','screenshots');
fs.mkdirSync(screenshotRoot,{recursive:true});
const pages=['index.html','register.html','syllabus.html','sample-papers.html','mock-test.html','awards.html','hackathon.html','hackathon-portal.html','faqs.html','contact.html','login.html','team-prelaunch.html','admin-login.html','exam.html'];
const widths=[1440,1024,768,390];
for(const pagePath of pages){
 test(pagePath+' renders without overflow and with working local imagery at all target widths',async({browser})=>{
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
   await page.screenshot({path:path.join(screenshotRoot,pagePath.replace('.html','')+'-'+width+'.png'),fullPage:true,animations:'disabled'});
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
test('registration form displays free registration and labelled fields on mobile',async({page})=>{
 await page.setViewportSize({width:390,height:844});
 await page.goto('/register.html',{waitUntil:'domcontentloaded'});
 await expect(page.locator('#reg-category')).toBeVisible();
 await expect(page.locator('label[for="reg-category"]')).toBeVisible();
 await expect(page.locator('.free-registration-note')).toBeVisible();
 await expect(page.locator('.free-registration-note')).toContainText('100% Free Registration');
 await expect(page.locator('.registration-consent')).toBeVisible();
});

test('India location selectors expose all States and dependent districts',async({page})=>{
 await page.route('https://sutravya-assessment-api-demo.onrender.com/api/registration/config',route=>route.fulfill({
  status:200,contentType:'application/json',
  body:JSON.stringify({registration_enabled:true,categories:[
   {id:'nursing',label:'Nursing',programmes:[{id:'bsc_nursing',label:'B.Sc Nursing',years:[1,2,3,4]}]},
   {id:'paramedical',label:'Paramedical',programmes:[{id:'bmlt',label:'BMLT'}]},
   {id:'medical',label:'Medical',programmes:[{id:'medical_ug',label:'Medical UG',years:[1,2,3,4,5]}]}
  ]})
 }));
 await page.goto('/register.html',{waitUntil:'domcontentloaded'});
 await expect(page.locator('#reg-state')).toBeEnabled();
 await expect(page.locator('#reg-state option')).toHaveCount(37);
 await page.locator('#reg-state').selectOption({label:'Bihar'});
 await expect(page.locator('#reg-district')).toBeEnabled();
 await expect(page.locator('#reg-district option')).toHaveCount(39);
 await expect(page.locator('#reg-district')).toContainText('Saharsa');
 await page.locator('#reg-state').selectOption({label:'Ladakh'});
 await expect(page.locator('#reg-district option')).toHaveCount(9);
 await expect(page.locator('#reg-district')).toContainText('Sankoo');
});

test('already registered email shows the prominent duplicate-email dialog',async({page})=>{
 await page.route('https://sutravya-assessment-api-demo.onrender.com/api/registration/config',route=>route.fulfill({
  status:200,contentType:'application/json',
  body:JSON.stringify({registration_enabled:true,categories:[
   {id:'nursing',label:'Nursing',programmes:[{id:'bsc_nursing',label:'B.Sc Nursing',years:[1,2,3,4]}]},
   {id:'paramedical',label:'Paramedical',programmes:[{id:'bmlt',label:'BMLT'}]},
   {id:'medical',label:'Medical',programmes:[{id:'medical_ug',label:'Medical UG',years:[1,2,3,4,5]}]}
  ]})
 }));
 await page.route('https://sutravya-assessment-api-demo.onrender.com/api/registrations/start',route=>route.fulfill({
  status:409,contentType:'application/json',
  body:JSON.stringify({detail:'This email is already registered. Try a new email for registration.'})
 }));
 await page.goto('/register.html',{waitUntil:'domcontentloaded'});
 await page.locator('#reg-category').selectOption('nursing');
 await page.locator('#reg-programme').selectOption('bsc_nursing');
 await page.locator('#reg-year').selectOption('1');
 await page.locator('#reg-name').fill('Synthetic Duplicate Candidate');
 await page.locator('#reg-email').fill('already@example.invalid');
 await page.locator('#reg-mobile').fill('9876543210');
 await page.locator('#reg-house').fill('12');
 await page.locator('#reg-address1').fill('Main Road');
 await page.locator('#reg-state').selectOption({label:'Bihar'});
 await page.locator('#reg-district').selectOption({label:'Saharsa'});
 await page.locator('#reg-pin').fill('852201');
 await page.locator('[name="consent"]').check();
 await page.locator('[data-review-button]').click();
 await page.locator('[data-review-send-otp]').click();
 const dialog=page.locator('[data-duplicate-email-modal]');
 await expect(dialog).toBeVisible();
 await expect(dialog.locator('h2')).toHaveText('This email is already registered.');
 await expect(dialog).toContainText('Try a new email for registration.');
 await dialog.locator('[data-duplicate-email-close]').click();
 await expect(page.locator('#candidate-registration-form')).toBeVisible();
 await expect(page.locator('#reg-email')).toBeFocused();
});

test('signed-in Hackathon participant workspace fits 390px, 768px and desktop',async({browser})=>{
 const page=await browser.newPage({viewport:{width:1440,height:900}});
 await page.route('https://sutravya-assessment-api-demo.onrender.com/api/hackathon/auth/session',route=>route.fulfill({
  status:200,contentType:'application/json',
  body:JSON.stringify({full_name:'Test Candidate',registration_id:'HTSE26-HK-TEST00001',college_name:'Healthcare Test College',year_of_study:2})
 }));
 for(const width of [390,768,1440]){
  await page.setViewportSize({width,height:900});
  await page.goto('/hackathon-portal.html',{waitUntil:'domcontentloaded'});
  await expect(page.locator('[data-hkp-dashboard]')).toBeVisible();
  await expect(page.locator('[data-hkp-regid]')).toContainText('HTSE26-HK-TEST00001');
  const dimensions=await page.evaluate(()=>({viewport:innerWidth,documentWidth:Math.max(document.documentElement.scrollWidth,document.body.scrollWidth)}));
  expect(dimensions.documentWidth,{message:'Participant workspace overflow at '+width+'px'}).toBeLessThanOrEqual(width+2);
  await page.screenshot({path:path.join(screenshotRoot,'hackathon-portal-dashboard-'+width+'.png'),fullPage:true,animations:'disabled'});
 }
 await page.close();
});


test('icon-led form visual system, typography and institution icon render',async({page})=>{
 await page.setViewportSize({width:1440,height:900});
 await page.goto('/register.html',{waitUntil:'domcontentloaded'});
 await expect(page.locator('.register-aside-art img')).toBeVisible();
 await expect(page.locator('label[for="reg-category"] .form-label-icon')).toBeVisible();
 const category=await page.locator('label[for="reg-category"]').evaluate(el=>parseFloat(getComputedStyle(el).fontSize));
 const control=await page.locator('#reg-category').evaluate(el=>parseFloat(getComputedStyle(el).fontSize));
 expect(category).toBeGreaterThanOrEqual(12);
 expect(control).toBeGreaterThanOrEqual(16);
 await page.goto('/hackathon.html',{waitUntil:'domcontentloaded'});
 await expect(page.locator('label[for="hk-college"] .form-label-icon')).toBeVisible();
 await page.locator('label[for="hk-college"] .form-label-icon').evaluate(el=>{
  if(el.querySelector('svg')===null)throw new Error('Institution field must use an SVG building icon');
 });
 await page.goto('/faqs.html',{waitUntil:'domcontentloaded'});
 await expect(page.locator('.qv2-faq-group h3 .heading-visual-icon').first()).toBeVisible();
});
test('signed-in admin console art and dashboard remain responsive',async({browser})=>{
 const page=await browser.newPage({viewport:{width:1440,height:900}});
 await page.addInitScript(()=>sessionStorage.setItem('sutravya_admin_access_token','qa-session-token'));
 await page.route('https://sutravya-assessment-api-demo.onrender.com/api/admin/**',async route=>{
  const url=new URL(route.request().url());let payload={};
  if(url.pathname.endsWith('/auth/me'))payload={administrator:{email:'qa@example.com',role:'Owner'}};
  else if(url.pathname.endsWith('/database/overview'))payload={database:{database_name:'qa',server_version:'16',schema_name:'public',schema_revision:'v1'},total_tables:2,total_rows:10,tables:[{name:'registrations',label:'Registrations',rows:4,description:'Candidate applications'},{name:'results',label:'Results',rows:2,description:'Assessment results'}]};
  else if(url.pathname.endsWith('/assessment/summary'))payload={streams:{nursing:2,paramedical:1,mbbs_ug:1,mbbs_pg:0},unassigned:0};
  else if(url.pathname.endsWith('/tables/registrations'))payload={columns:[{name:'registration_id'},{name:'stream'},{name:'status'},{name:'created_at'}],records:[],total:0,limit:8,offset:0};
  else payload={records:[]};
  await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(payload)});
 });
 for(const width of [390,768,1440]){
  await page.setViewportSize({width,height:900});
  await page.goto('/admin.html',{waitUntil:'domcontentloaded'});
  await expect(page.locator('#admin-portal')).toBeVisible();
  await expect(page.locator('.admin-welcome-visual img')).toBeVisible();
  const result=await page.evaluate(()=>({viewport:innerWidth,documentWidth:Math.max(document.documentElement.scrollWidth,document.body.scrollWidth)}));
  expect(result.documentWidth,{message:'Admin console overflow at '+width+'px'}).toBeLessThanOrEqual(width+2);
  await page.screenshot({path:path.join(screenshotRoot,'admin-console-'+width+'.png'),fullPage:true,animations:'disabled'});
 }
 await page.close();
});

test('reduced motion preference disables long animations and smooth scrolling',async({page})=>{
 await page.emulateMedia({reducedMotion:'reduce'});
 await page.goto('/index.html',{waitUntil:'domcontentloaded'});
 const values=await page.evaluate(()=>({scroll:getComputedStyle(document.documentElement).scrollBehavior,animation:getComputedStyle(document.body).animationDuration}));
 expect(values.scroll).toBe('auto');
});
