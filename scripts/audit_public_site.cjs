'use strict';
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(process.argv[2] || 'assessment-public');
const pages = [
 'index.html','register.html','syllabus.html','sample-papers.html','mock-test.html',
 'awards.html','hackathon.html','faqs.html','contact.html','login.html',
 'team-prelaunch.html','admin.html','exam.html'
];
const errors = [];
const report = [];
for (const page of pages) {
 const file = path.join(root,page);
 if (!fs.existsSync(file)) { errors.push(page+': missing page'); continue; }
 const html=fs.readFileSync(file,'utf8');
 const titles=[...html.matchAll(/<title>([\s\S]*?)<\/title>/gi)];
 const h1=[...html.matchAll(/<h1\b[^>]*>([\s\S]*?)<\/h1>/gi)];
 const images=[...html.matchAll(/<img\b([^>]*)>/gi)];
 if(titles.length!==1)errors.push(page+': expected exactly one title');
 if(h1.length!==1)errors.push(page+': expected exactly one h1, found '+h1.length);
 for(const [index,m] of images.entries()){
  if(!/\balt\s*=/.test(m[1]))errors.push(page+': image '+(index+1)+' is missing alt text');
 }
 const refs=[...html.matchAll(/\b(?:src|href)=["']([^"']+)["']/gi)].map(m=>m[1]);
 for(const ref of refs){
  if(!ref.startsWith('assets/'))continue;
  if(!fs.existsSync(path.join(root,ref)))errors.push(page+': missing local asset '+ref);
 }
 if(!/<meta\b(?=[^>]*\bname=["']theme-color["'])(?=[^>]*\bcontent=["'][^"']+["'])[^>]*>/i.test(html))errors.push(page+': missing theme-color metadata');
 report.push({page,title:titles[0]?.[1]||'',h1Count:h1.length,imageCount:images.length,assetReferenceCount:refs.filter(x=>x.startsWith('assets/')).length});
}
const cssPath=path.join(root,'styles.css');
if(!fs.existsSync(cssPath))errors.push('styles.css: missing');
else{
 const css=fs.readFileSync(cssPath,'utf8');
 for(const selector of ['.qv2-home-hero','.qv3-flow-strip','.qv3-admin-overview','--metallic-gold','--metallic-silver']){
  if(!css.includes(selector))errors.push('styles.css: expected design token or component '+selector+' missing');
 }
}
console.log(JSON.stringify({root,checkedPages:pages.length,report,errors},null,2));
if(errors.length)process.exit(1);
