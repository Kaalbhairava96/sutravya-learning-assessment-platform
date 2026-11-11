'use strict';
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(process.argv[2]||'assessment-public');
const pages=['index.html','register.html','syllabus.html','sample-papers.html','mock-test.html','awards.html','hackathon.html','faqs.html','contact.html','login.html','team-prelaunch.html','admin.html','exam.html'];
const errors=[];const report=[];
for(const page of pages){
 const file=path.join(root,page);if(!fs.existsSync(file)){errors.push(page+': missing page');continue;}
 const html=fs.readFileSync(file,'utf8');
 const tags=[...html.matchAll(/<[a-z][^>]*>/gi)];
 for(const [index,tag] of tags.entries()){const names=[...tag[0].matchAll(/\s([a-z][a-z0-9:_-]*)\s*=/gi)].map(m=>m[1].toLowerCase());const seen=new Set();for(const name of names){if(seen.has(name))errors.push(page+': tag '+(index+1)+' has duplicate '+name+' attribute');seen.add(name);}}
 const titles=[...html.matchAll(/<title>([\s\S]*?)<\/title>/gi)];
 const headings=[...html.matchAll(/<h1\b[^>]*>([\s\S]*?)<\/h1>/gi)];
 const images=[...html.matchAll(/<img\b([^>]*)>/gi)];
 if(titles.length!==1)errors.push(page+': expected exactly one title');
 if(headings.length!==1)errors.push(page+': expected exactly one h1, found '+headings.length);
 for(const [index,m] of images.entries()){const alt=(m[1].match(/\balt\s*=\s*["']([^"']*)["']/i)||[])[1];if(alt===undefined)errors.push(page+': image '+(index+1)+' is missing alt text');else if(alt.trim().length<5)errors.push(page+': image '+(index+1)+' has an unhelpful alt description');}
 const refs=[...html.matchAll(/\b(?:src|href)=["']([^"']+)["']/gi)].map(m=>m[1]);
 for(const ref of refs){if(ref.startsWith('assets/')&&!fs.existsSync(path.join(root,ref)))errors.push(page+': missing local asset '+ref);}
 for(const required of ['styles.css','layout.css']){if(!refs.includes(required))errors.push(page+': missing '+required);else if(!fs.existsSync(path.join(root,required)))errors.push(page+': missing stylesheet file '+required);}
 if(!/<meta\b(?=[^>]*\bname=["']theme-color["'])(?=[^>]*\bcontent=["']#F7F9F7["'])[^>]*>/i.test(html))errors.push(page+': missing pearl theme metadata');
 report.push({page,title:titles[0]?.[1]||'',h1Count:headings.length,imageCount:images.length,assetReferences:refs.filter(x=>x.startsWith('assets/')).length});
}
const cssPath=path.join(root,'styles.css'),layoutPath=path.join(root,'layout.css');
if(!fs.existsSync(cssPath))errors.push('styles.css: missing');if(!fs.existsSync(layoutPath))errors.push('layout.css: missing');
if(fs.existsSync(cssPath)){const css=fs.readFileSync(cssPath,'utf8');const roots=[...css.matchAll(/:root\s*\{/g)];if(roots.length!==1)errors.push('styles.css: expected one canonical :root block, found '+roots.length);for(const token of ['--brand-navy:#092D60','--brand-teal:#078F88','--brand-emerald:#138168','--brand-pearl:#F7F9F7','--brand-champagne:#C9A45D'])if(!css.includes(token))errors.push('styles.css: missing canonical token '+token);if(/color-scheme\s*:\s*dark/i.test(css))errors.push('styles.css: dark native control scheme found');if(!css.includes('@layer reset, layout, components, pages'))errors.push('styles.css: expected ordered cascade layers');}
if(fs.existsSync(layoutPath)){const css=fs.readFileSync(layoutPath,'utf8');if(/:root\s*\{/i.test(css))errors.push('layout.css: must not contain root tokens');if(/#(?:[0-9a-f]{3,8})\b|rgba?\(|hsla?\(/i.test(css))errors.push('layout.css: visual colour declarations found');}
const shell=fs.readFileSync(path.join(root,'site.js'),'utf8');if(/htse-campaign-postcard|function renderContextualPostcard/.test(shell))errors.push('site.js: repeated campaign postcard injection remains');if(!shell.includes('faq-search-input'))errors.push('site.js: FAQ search interaction missing');if(!shell.includes('footer-brand-pair'))errors.push('site.js: co-branded footer lockup missing');
console.log(JSON.stringify({root,checkedPages:pages.length,report,errors},null,2));if(errors.length)process.exit(1);
