'use strict';
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(process.argv[2]||'assessment-public');
const pages=['index.html','register.html','syllabus.html','sample-papers.html','mock-test.html','awards.html','hackathon.html','faqs.html','contact.html','login.html','team-prelaunch.html','admin-login.html','admin.html','exam.html'];
const errors=[];const report=[];
function rgb(hex){const raw=hex.replace('#','');return [0,2,4].map(i=>parseInt(raw.slice(i,i+2),16)/255).map(v=>v<=.04045?v/12.92:Math.pow((v+.055)/1.055,2.4));}
function luminance(hex){const c=rgb(hex);return .2126*c[0]+.7152*c[1]+.0722*c[2];}
function contrast(a,b){const pair=[luminance(a),luminance(b)].sort((x,y)=>y-x);return (pair[0]+.05)/(pair[1]+.05);}
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
 const controls=[...html.matchAll(/<(input|select|textarea)\b([^>]*)>/gi)];
 for(const [index,m] of controls.entries()){const attrs=m[2],type=(attrs.match(/\btype=["']([^"']+)/i)||[])[1]||'',id=(attrs.match(/\bid=["']([^"']+)/i)||[])[1];if(['hidden','submit','button','reset','image'].includes(type))continue;const hasAria=/\baria-label=["'][^"']+|\baria-labelledby=["'][^"']+/i.test(attrs);const explicit=id&&new RegExp('<label[^>]*for=["\\\']'+id.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+'["\\\']','i').test(html);const lastLabel=html.lastIndexOf('<label',m.index),lastClose=html.lastIndexOf('</label>',m.index);const wrapped=lastLabel>lastClose;if(!hasAria&&!explicit&&!wrapped)errors.push(page+': form control '+(index+1)+' has no programmatic label');}
 const refs=[...html.matchAll(/\b(?:src|href)=["']([^"']+)["']/gi)].map(m=>m[1]);
 for(const ref of refs){if(ref.startsWith('assets/')&&!fs.existsSync(path.join(root,ref)))errors.push(page+': missing local asset '+ref);}
 for(const required of ['styles.css','layout.css']){if(!refs.includes(required))errors.push(page+': missing '+required);else if(!fs.existsSync(path.join(root,required)))errors.push(page+': missing stylesheet file '+required);}
 if(!['admin.html','admin-login.html'].includes(page)&&!/<meta\b(?=[^>]*\bname=["']theme-color["'])(?=[^>]*\bcontent=["']#F7F9F7["'])[^>]*>/i.test(html))errors.push(page+': missing pearl theme metadata');
 if(!/fonts\.googleapis\.com\/css2\?family=DM\+Sans/.test(html)||!html.includes('family=Manrope'))errors.push(page+': missing shared DM Sans / Manrope typography');
 report.push({page,title:titles[0]?.[1]||'',h1Count:headings.length,imageCount:images.length,assetReferences:refs.filter(x=>x.startsWith('assets/')).length});
}
const cssPath=path.join(root,'styles.css'),layoutPath=path.join(root,'layout.css');
if(!fs.existsSync(cssPath))errors.push('styles.css: missing');if(!fs.existsSync(layoutPath))errors.push('layout.css: missing');
if(fs.existsSync(cssPath)){const css=fs.readFileSync(cssPath,'utf8');const roots=[...css.matchAll(/:root\s*\{/g)];if(roots.length!==1)errors.push('styles.css: expected one canonical :root block, found '+roots.length);for(const token of ['--brand-navy:#092D60','--brand-teal:#078F88','--brand-teal-700:#06766F','--brand-emerald:#138168','--brand-pearl:#F7F9F7','--brand-champagne:#C9A45D'])if(!css.includes(token))errors.push('styles.css: missing canonical token '+token);if(/color-scheme\s*:\s*dark/i.test(css))errors.push('styles.css: dark native control scheme found');if(!css.includes('@layer reset, layout, components, pages'))errors.push('styles.css: expected ordered cascade layers');if(!/:focus-visible/.test(css))errors.push('styles.css: visible keyboard focus treatment missing');if(!/prefers-reduced-motion:\s*reduce/.test(css))errors.push('styles.css: reduced-motion support missing');if(!/var\(--brand-teal-700\),var\(--brand-emerald\)/.test(css))errors.push('styles.css: action gradients must use AA-contrast teal');}
if(fs.existsSync(layoutPath)){const css=fs.readFileSync(layoutPath,'utf8');if(/:root\s*\{/i.test(css))errors.push('layout.css: must not contain root tokens');if(/#(?:[0-9a-f]{3,8})\b|rgba?\(|hsla?\(/i.test(css))errors.push('layout.css: visual colour declarations found');}
const contrastPairs=[['#FFFFFF','#06766F'],['#FFFFFF','#138168'],['#253441','#F7F9F7'],['#5E707A','#F7F9F7'],['#061D42','#C9A45D']];
for(const [foreground,background] of contrastPairs){const ratio=contrast(foreground,background);if(ratio<4.5)errors.push('contrast: '+foreground+' on '+background+' is '+ratio.toFixed(2)+':1, below 4.5:1');}
const shell=fs.readFileSync(path.join(root,'site.js'),'utf8');if(/htse-campaign-postcard|function renderContextualPostcard/.test(shell))errors.push('site.js: repeated campaign postcard injection remains');if(!shell.includes('faq-search-input'))errors.push('site.js: FAQ search interaction missing');if(!shell.includes('footer-brand-pair'))errors.push('site.js: co-branded footer lockup missing');if(!shell.includes('aria-expanded'))errors.push('site.js: responsive menu state is not announced');
console.log(JSON.stringify({root,checkedPages:pages.length,contrastRatios:contrastPairs.map(([fg,bg])=>({foreground:fg,background:bg,ratio:Number(contrast(fg,bg).toFixed(2))})),report,errors},null,2));if(errors.length)process.exit(1);
