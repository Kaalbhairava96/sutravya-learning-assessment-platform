'use strict';
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(process.argv[2]||'assessment-public');
const pages=['index.html','register.html','syllabus.html','sample-papers.html','mock-test.html','awards.html','hackathon.html','hackathon-portal.html','faqs.html','contact.html','login.html','team-prelaunch.html','admin-login.html','admin.html','exam.html'];
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
const homepage=fs.readFileSync(path.join(root,'index.html'),'utf8');
const hackathon=fs.readFileSync(path.join(root,'hackathon.html'),'utf8');
const portal=fs.readFileSync(path.join(root,'hackathon-portal.html'),'utf8');
const faqPage=fs.readFileSync(path.join(root,'faqs.html'),'utf8');
if(!homepage.includes('healthcare-talent-search-badge.svg'))errors.push('index.html: Healthcare Talent Search Exam badge is missing');
if(!homepage.includes('brand-home-hero-premium.svg'))errors.push('index.html: premium medical hero artwork is missing');
for(const asset of ['brand-home-learning-premium.svg','brand-home-hackathon-premium.svg','brand-home-recognition-premium.svg'])if(!homepage.includes(asset))errors.push('index.html: missing coordinated 3D section artwork '+asset);
if(!homepage.includes('Healthcare Talent<br><em>Search Exam 2026</em>'))errors.push('index.html: official HTSE headline is missing');
if(!homepage.includes('qv2-home-partners')||!homepage.includes('qualinova-logo.png')||!homepage.includes('sutravya-logo.png'))errors.push('index.html: organiser and technology partner logo lockup is incomplete');
if(!homepage.includes('25 November 2026'))errors.push('index.html: registration closing date cue is missing');
if((homepage.match(/class="qv2-milestone"/g)||[]).length!==4)errors.push('index.html: homepage should show four event milestones');
if(homepage.split('class="qv2-path-card ').length-1!==4)errors.push('index.html: homepage must show exactly four equal assessment pathway cards');
if(homepage.includes('qv3-pathway-diagram'))errors.push('index.html: old flat pathway diagram remains');
if(!homepage.includes('qv2-home-primary-cta'))errors.push('index.html: prominent registration CTA is missing');
const homepageCss=fs.readFileSync(path.join(root,'styles.css'),'utf8');
if(!homepageCss.includes('body.qv2-home .qv2-home-primary-cta')||!homepageCss.includes('#fff0bd'))errors.push('styles.css: premium gold homepage registration CTA is missing');
if(!homepageCss.includes('.footer-brand-pair>a{background:transparent!important'))errors.push('styles.css: footer logo tiles have not been made transparent');
if(!homepageCss.includes('qv2-event-section .qv2-home-milestones:before'))errors.push('styles.css: connected homepage milestone timeline is missing');

if(!hackathon.includes('data-hackathon-register-form'))errors.push('hackathon.html: separate participant registration form is missing');
if(!hackathon.includes('27 November 2026')||!hackathon.includes('sutravya.connect@gmail.com'))errors.push('hackathon.html: email-only synopsis deadline details are missing');
if(!portal.includes('data-hk-login-form')||!portal.includes('registration_id'))errors.push('hackathon-portal.html: Registration ID and email sign-in flow is missing');
if(/PDF|project upload deadline|upload your project/i.test(hackathon+'\\n'+faqPage))errors.push('Hackathon public copy: obsolete PDF or website-upload submission wording remains');
console.log(JSON.stringify({root,checkedPages:pages.length,contrastRatios:contrastPairs.map(([fg,bg])=>({foreground:fg,background:bg,ratio:Number(contrast(fg,bg).toFixed(2))})),report,errors},null,2));if(errors.length)process.exit(1);
