/* Shared microsite shell and interactions. Keep event facts in this object. */
const eventConfig = Object.freeze({
  title: 'Healthcare Talent Search Examination 2026',
  shortTitle: 'Healthcare Talent Search Examination',
  registrationOpensLabel: '1 November 2026 at 12:00 AM IST',
  registrationOpensDate: '1 November 2026',
  registrationOpensTime: '12:00 AM IST',
  registrationClosesLabel: '1 December 2026 at 11:59:59 PM IST',
  registrationClosesDate: '1 December 2026',
  registrationClosesTime: '11:59:59 PM IST',
  examDate: '6 December 2026',
  examStartsAt: Date.parse('2026-12-06T10:00:00+05:30'),
  examEndsAt: Date.parse('2026-12-06T18:00:00+05:30'),
  examVenue: 'Online Examination · Start from anywhere in India',
  registrationOpensAt: Date.parse('2026-10-31T18:30:00.000Z'), // 1 Nov, 00:00 IST
  registrationClosesAt: Date.parse('2026-12-01T18:29:59.999Z'), // 1 Dec, 23:59:59 IST
  timeZone: 'Asia/Kolkata',
  assessmentStreams: Object.freeze(['Nursing', 'Paramedical', 'Pharmacy']),
  registrationCategories: Object.freeze(['Nursing', 'Paramedical', 'Pharmacy']),
  streams: Object.freeze(['Nursing', 'Paramedical', 'Pharmacy']),
  questionCount: 100,
  durationMinutes: 30,
  negativeMarking: true,
  awardsPublished: true,
  nursingSyllabusApproved: false,
  officialSampleAnswersPublished: false
});

const navigation = [
  ['index.html', 'Home'], ['syllabus.html', 'Syllabus'], ['sample-papers.html', 'Sample MCQs'],
  ['mock-test.html', 'Mock Tests'], ['hackathon.html', 'Hackathon'], ['hackathon-portal.html', 'Participant Portal'], ['awards.html', 'Awards'],
  ['faqs.html', 'FAQs'], ['register.html', 'Register'], ['contact.html', 'Contact']
];
const currentPage = location.pathname.split('/').pop() || 'index.html';
const configuredApiBase = document.querySelector('meta[name="sutravya-api-base"]')?.content.trim();
const apiBase = configuredApiBase || (['localhost', '127.0.0.1'].includes(location.hostname) ? 'http://127.0.0.1:8000' : '');

async function apiRequest(path, payload, method = 'POST', extraHeaders = {}) {
  if (!apiBase) throw new Error('Registration is not connected to the secure application yet. Please try again later.');
  const headers = { ...(payload ? { 'Content-Type': 'application/json' } : {}), ...extraHeaders };
  const response = await fetch(`${apiBase}${path}`, {
    method, credentials: 'include', headers,
    body: payload ? JSON.stringify(payload) : undefined
  });
  let data = {};
  try { data = await response.json(); } catch { /* Keep the generic network message. */ }
  if (!response.ok) throw new Error(data.detail || 'The request could not be completed.');
  return data;
}

function icon(name) {
  const paths = {
    arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
    phone: '<path d="M7 3h3l2 5-2 2a15 15 0 0 0 4 4l2-2 5 2v3c0 1-1 2-2 2A16 16 0 0 1 5 5c0-1 1-2 2-2Z"/>',
    mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m4 7 8 6 8-6"/>',
    globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a15 15 0 0 1 0 18M12 3a15 15 0 0 0 0 18"/>',
    shield: '<path d="M12 3 20 6v5c0 5-3 8-8 10-5-2-8-5-8-10V6l8-3Z"/><path d="m8 12 3 3 5-6"/>',
    menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
    close: '<path d="m6 6 12 12M18 6 6 18"/>',
    whatsapp: '<path d="M20.5 3.5a10.1 10.1 0 0 0-15.8 12.8l-1.2 4.2 4.3-1.1a10.1 10.1 0 1 0 12.7-15.9Z"/><path d="M8.5 7.7c.2-.4.4-.4.6-.4h.5c.2 0 .4.1.5.4l.8 1.8c.1.2.1.4-.1.6l-.6.7c-.2.2-.2.4-.1.6a7.4 7.4 0 0 0 3.1 3.1c.2.1.4.1.6-.1l.7-.8c.2-.2.4-.2.6-.1l1.7.8c.3.1.4.3.4.5 0 .3-.2 1-.6 1.3-.4.4-1.1.6-1.7.5a10.2 10.2 0 0 1-4.5-2.2 10 10 0 0 1-3.1-3.8c-.4-.8-.6-1.6-.3-2.2.3-.5.8-.9 1.1-1.1Z"/>',
    institution: '<path d="m3 9 9-5 9 5v11H3z"/><path d="M2 9h20M7 12v5m5-5v5m5-5v5M2 20h20"/>',
    user: '<circle cx="12" cy="8" r="3.5"/><path d="M4.5 20a7.5 7.5 0 0 1 15 0"/>',
    calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4m10-4v4M3 10h18M7 14h3m-3 3h7"/>',
    map: '<path d="M20 10c0 5-8 11-8 11S4 15 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="2.4"/>',
    book: '<path d="M4 4.5A2.5 2.5 0 0 1 6.5 2H20v18H6.5A2.5 2.5 0 0 0 4 22Z"/><path d="M4 5v14a2.5 2.5 0 0 1 2.5-2.5H20M8 7h8m-8 3h8"/>',
    clipboard: '<rect x="5" y="4" width="14" height="18" rx="2"/><path d="M9 4V2h6v2M8 10h8m-8 4h8m-8 4h5"/>',
    graduation: '<path d="m2 9 10-5 10 5-10 5L2 9Z"/><path d="M6 11v5c3.5 3 8.5 3 12 0v-5m4-2v7"/>',
    key: '<circle cx="8" cy="15" r="5"/><path d="m11.5 11.5 9-9m-3 3 3 3m-6 0 3 3"/>',
    trophy: '<path d="M8 21h8m-4-4v4M7 4h10v5a5 5 0 0 1-10 0V4Z"/><path d="M7 6H3v2a4 4 0 0 0 4 4m10-6h4v2a4 4 0 0 1-4 4"/>',
    lightbulb: '<path d="M9 18h6m-5 3h4m-5-6a7 7 0 1 1 6 0c-.8.6-1 1.1-1 2H10c0-.9-.2-1.4-1-2Z"/>',
    chart: '<path d="M4 19V5m0 14h17"/><path d="m7 14 4-4 3 2 5-6"/><path d="M16 6h3v3"/>',
    refresh: '<path d="M20 7v5h-5"/><path d="M4.7 9A8 8 0 0 1 18.2 6L20 12M4 17v-5h5"/><path d="M5.8 18A8 8 0 0 0 19.3 15L20 12"/>',
    search: '<circle cx="10.8" cy="10.8" r="6.8"/><path d="m16 16 5 5"/>',
    download: '<path d="M12 3v12m-5-5 5 5 5-5"/><path d="M4 17v4h16v-4"/>',
    lock: '<rect x="4" y="10" width="16" height="11" rx="2"/><path d="M8 10V7a4 4 0 1 1 8 0v3m-4 4v3"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.5 2"/>',
    check: '<path d="m5 12 4 4L19 6"/>'
  };
  return `<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">${paths[name] || paths.arrow}</svg>`;
}

function initHumanVisuals() {
  if (!document.body) return;
  document.body.dataset.page = currentPage;
  const makeIcon = (name, className) => {
    const node=document.createElement('span');
    node.className=className;
    node.setAttribute('aria-hidden','true');
    node.innerHTML=icon(name);
    return node;
  };
  const fieldIcon = label => {
    const field = (label.htmlFor || '').toLowerCase();
    const text = label.textContent.toLowerCase();
    if (/college|institution|university|school|campus/.test(field+' '+text)) return 'institution';
    if (/email|mail|otp|verification|code/.test(field+' '+text)) return 'mail';
    if (/mobile|phone|telephone/.test(field+' '+text)) return 'phone';
    if (/year|semester|stage|date|time/.test(field+' '+text)) return 'calendar';
    if (/address|district|state|pin|postal|location/.test(field+' '+text)) return 'map';
    if (/password|token|secure|access/.test(field+' '+text)) return 'shield';
    if (/name|candidate|participant/.test(field+' '+text)) return 'user';
    if (/category|programme|program|stream|subject/.test(field+' '+text)) return 'book';
    if (/registration|application|declaration/.test(field+' '+text)) return 'clipboard';
    return 'clipboard';
  };
  document.querySelectorAll('label[for]').forEach(label => {
    if (label.querySelector('.form-label-icon')) return;
    label.prepend(makeIcon(fieldIcon(label),'form-label-icon'));
  });
  document.querySelectorAll('.form-section-title').forEach(section => {
    if (section.querySelector('.form-section-visual')) return;
    const title=section.querySelector('b')?.textContent.toLowerCase()||'';
    const name=/academic|education/.test(title)?'graduation':/personal|candidate/.test(title)?'user':/address|location/.test(title)?'map':/email|verification/.test(title)?'mail':/category|programme/.test(title)?'book':'clipboard';
    const marker=section.querySelector(':scope > span');
    if(marker) marker.classList.add('form-section-number');
    const content=section.querySelector('div');
    if(content) section.insertBefore(makeIcon(name,'form-section-visual'),content);
  });
  document.querySelectorAll('.qv2-hack-field-group').forEach(group => {
    if(group.querySelector('.form-section-visual'))return;
    const title=group.textContent.toLowerCase();
    const name=/academic/.test(title)?'graduation':/address/.test(title)?'map':'user';
    group.prepend(makeIcon(name,'form-section-visual'));
  });
  document.querySelectorAll('.qv2-faq-group h3,.contact-card h3,.contact-intent h3,.awards-track-card h3,.qv2-subject-card h4,.qv2-section h2,.section h2,.section-heading h2,.v4-section-heading h2,.admin-panel-heading h3,.admin-section-intro h2,.admin-login-panel h2,.admin-welcome-band h2,.register-panel-head h2').forEach(heading=>{
    if(heading.querySelector('.heading-visual-icon'))return;
    const text=heading.textContent.toLowerCase();
    const name=/award|recognition|excellence|merit|result/.test(text)?'trophy':/hackathon|startup|innovation|idea|prototype/.test(text)?'lightbulb':/address|contact|support|help|login|email/.test(text)?'mail':/registration|eligibility|application/.test(text)?'clipboard':/exam|schedule|date|milestone|time/.test(text)?'calendar':/database|institution|college|university|school|table/.test(text)?'institution':/security|secure|access|protected/.test(text)?'shield':/syllabus|practice|subject|anatomy|nursing|medical|paramedical|laboratory|academic|learning/.test(text)?'graduation':'book';
    heading.prepend(makeIcon(name,'heading-visual-icon'));
  });
  document.querySelectorAll('button.button,button.qv2-button,a.button,a.qv2-button,.nav-register,.admin-primary-button,.admin-secondary-button,.admin-logout-button,.admin-login-submit,.admin-retry-button').forEach(control=>{
    if(control.querySelector('svg,.button-context-icon'))return;
    const text=control.textContent.toLowerCase();
    const name=/register|application|apply/.test(text)?'clipboard':/verify|email|code|otp/.test(text)?'mail':/sign out|log out|logout|login|sign in|secure/.test(text)?'shield':/contact|call|phone/.test(text)?'phone':/refresh|retry|update|time|duration/.test(text)?'clock':/save|submit|create|confirm|approve|release/.test(text)?'check':/test|practice|start|explore|syllabus|continue/.test(text)?'graduation':/award|recognition/.test(text)?'trophy':/search|find/.test(text)?'search':/database|table/.test(text)?'institution':'book';
    if(name)control.prepend(makeIcon(name,'button-context-icon'));
  });
  document.querySelectorAll('.register-step,.login-context-card,.qv2-milestone,.awards-winner-summary article').forEach((card,index)=>{
    card.classList.add('human-visual-card');
    card.style.setProperty('--visual-index',String(index%6));
  });
  document.querySelectorAll('.register-security-note>span,.registration-gate>.gate-mark').forEach(node=>{
    if(node.querySelector('svg'))return;
    node.innerHTML=icon('shield');
    node.setAttribute('aria-hidden','true');
  });
  document.querySelectorAll('.qv2-hack-free-badge').forEach(node=>{
    if(node.querySelector('svg'))return;
    node.prepend(makeIcon(node.textContent.includes('₹')?'check':'shield','badge-visual-icon'));
  });

  const contextualIcon = (target, name, className='ui-context-icon') => {
    if (!target || target.querySelector(':scope > .'+className)) return;
    target.prepend(makeIcon(name, className));
  };
  const iconForContext = value => {
    const text = String(value || '').toLowerCase();
    if (/47\\s*min|minute|duration|time|deadline|closes|opens/.test(text)) return 'clock';
    if (/date|nov|dec|calendar|schedule|slot/.test(text)) return 'calendar';
    if (/mcq|question|assessment|exam|test|score|result/.test(text)) return 'clipboard';
    if (/pathway|subject|syllabus|academic|medical|nursing|paramedical|learning|study/.test(text)) return 'graduation';
    if (/innovation|hackathon|idea|prototype|startup|design/.test(text)) return 'lightbulb';
    if (/award|recognition|merit|bcmr|trophy|winner/.test(text)) return 'trophy';
    if (/email|mail|otp|verification/.test(text)) return 'mail';
    if (/phone|call|contact/.test(text)) return 'phone';
    if (/free|secure|safety|protected|privacy/.test(text)) return 'shield';
    if (/candidate|participant|team|account|profile/.test(text)) return 'user';
    if (/location|address|district|state|venue/.test(text)) return 'map';
    return 'book';
  };

  document.querySelectorAll('.qv2-stats>div').forEach(card => {
    const value = card.querySelector('b');
    const label = card.querySelector('span');
    contextualIcon(value, iconForContext((label?.textContent || '')+' '+(value?.textContent || '')), 'metric-context-icon');
  });
  document.querySelectorAll('.qv2-card-tags span,.v4-hero-chips span,.qv2-hero-facts>span,.awards-track-tag,.qv2-recog-points>span,.faq-filter-chips button').forEach(node => {
    contextualIcon(node, iconForContext(node.textContent), 'metadata-context-icon');
  });
  document.querySelectorAll('.v4-score-stats>div').forEach(card => {
    const label=card.querySelector('span');
    const value=card.querySelector('b');
    contextualIcon(value, iconForContext(label?.textContent || ''), 'metric-context-icon');
  });
  document.querySelectorAll('.qv3-flow-step').forEach(step => {
    const title = step.querySelector('b');
    contextualIcon(title, iconForContext(title?.textContent || step.textContent), 'step-context-icon');
  });
  document.querySelectorAll('.qv2-hack-principles article h3,.login-flow-steps article b,.exam-access-steps article b').forEach(title => {
    contextualIcon(title, iconForContext(title.textContent), 'step-context-icon');
  });
  document.querySelectorAll('.qv2-event-notice').forEach(node => {
    contextualIcon(node, 'clock', 'notice-context-icon');
  });
  document.querySelectorAll('.v4-timer small').forEach(node => {
    contextualIcon(node, 'clock', 'notice-context-icon');
  });
  document.querySelectorAll('.footer-exam-note').forEach(node => {
    const parts = [...node.querySelectorAll('b,span')];
    parts.forEach(part => contextualIcon(part, iconForContext(part.textContent), 'footer-note-icon'));
  });
  document.querySelectorAll('.qv2-hack-application-steps>span,.register-step,.registration-progress-step').forEach(step => {
    const title = step.querySelector('small,b');
    if (title) contextualIcon(title, iconForContext(title.textContent), 'step-context-icon');
  });
  document.querySelectorAll('.admin-side-nav button').forEach(button => {
    const view = button.dataset.adminView || '';
    const names = {overview:'chart',registrations:'clipboard',database:'institution',slots:'calendar',results:'trophy',audit:'shield'};
    const marker = button.querySelector(':scope > span');
    if (marker && !marker.querySelector('svg')) {
      marker.innerHTML = icon(names[view] || 'book');
      marker.classList.add('admin-nav-icon');
    }
  });
  document.querySelectorAll('.admin-login-feature-list i').forEach(node => {
    if (!node.querySelector('svg')) node.innerHTML = icon('check');
  });

}

const header = document.querySelector('[data-header]');
if (header) {
  const navLink = ([url,label]) => '<a class="nav-link'+(url==='admin-login.html'?' nav-admin-link':'')+'" href="'+url+'"'+(url===currentPage ? ' aria-current="page"' : '')+'>'+label+'</a>';
  const preparation = ['syllabus.html','sample-papers.html','mock-test.html'];
  const innovation = ['hackathon.html','hackathon-portal.html','awards.html'];
  const inPreparation = preparation.includes(currentPage);
  const inInnovation = innovation.includes(currentPage);
  header.innerHTML = '<div class="site-topline"></div><header class="site-header"><div class="wrap header-inner">' +
    '<div class="header-brand-lockup"><a class="brand" href="index.html" aria-label="SUTRAVYA home"><img src="assets/sutravya-logo.png" alt="SUTRAVYA — The Digital Thread of Healthcare"></a>' +
    '<span class="header-brand-divider" aria-hidden="true"></span><a class="partner-brand" href="https://qualinovahub.com" target="_blank" rel="noopener" aria-label="QualiNova, event organiser"><small>EVENT ORGANISER</small><img src="assets/qualinova-logo.png" alt="QualiNova Solutions"></a></div>' +
    '<button class="nav-toggle" type="button" aria-label="Open navigation" aria-expanded="false" aria-controls="primary-navigation"><span class="nav-toggle-icon">'+icon('menu')+'</span><span>Menu</span></button>' +
    '<nav class="primary-nav" id="primary-navigation" aria-label="Main navigation">' + navLink(['index.html','Home']) +
    '<details class="nav-dropdown"><summary '+(inPreparation?'aria-current="page"':'')+'>Preparation</summary><div class="nav-dropdown-menu">' +
    navLink(['syllabus.html','Syllabus'])+navLink(['sample-papers.html','Sample MCQs'])+navLink(['mock-test.html','Mock Tests'])+'</div></details>' +
    '<details class="nav-dropdown"><summary '+(inInnovation?'aria-current="page"':'')+'>Innovation</summary><div class="nav-dropdown-menu">' +
    navLink(['hackathon.html','Hackathon'])+navLink(['hackathon-portal.html','Participant Portal'])+navLink(['awards.html','Awards &amp; Recognition'])+'</div></details>' +
    navLink(['faqs.html','Help Centre'])+navLink(['contact.html','Contact'])+navLink(['admin-login.html','Admin']) +
    '<a class="nav-register" href="register.html"'+(currentPage==='register.html'?' aria-current="page"':'')+'>Register now '+icon('arrow')+'</a></nav></div></header>';
  const toggle=header.querySelector('.nav-toggle');
  const nav=header.querySelector('.primary-nav');
  const closeMenu=({restoreFocus=false}={})=>{
    nav.classList.remove('is-open');
    nav.querySelectorAll('.nav-dropdown[open]').forEach(item=>item.removeAttribute('open'));
    toggle.setAttribute('aria-expanded','false');
    toggle.setAttribute('aria-label','Open navigation');
    toggle.querySelector('.nav-toggle-icon').innerHTML=icon('menu');
    if(restoreFocus)toggle.focus();
  };
  toggle.addEventListener('click',()=>{
    const open=nav.classList.toggle('is-open');
    toggle.setAttribute('aria-expanded',String(open));
    toggle.setAttribute('aria-label',open?'Close navigation':'Open navigation');
    toggle.querySelector('.nav-toggle-icon').innerHTML=icon(open?'close':'menu');
  });
  nav.addEventListener('click',event=>{if(event.target.closest('a'))closeMenu();});
  document.addEventListener('keydown',event=>{if(event.key==='Escape'&&nav.classList.contains('is-open'))closeMenu({restoreFocus:true});});
  document.addEventListener('click',event=>{if(!header.contains(event.target)){nav.querySelectorAll('.nav-dropdown[open]').forEach(item=>item.removeAttribute('open'));closeMenu();}});
}

const footer=document.querySelector('[data-footer]');
if(footer){
  const contactLink=(url,kind,value,label)=>'<a class="footer-contact-link" href="'+url+'"'+(kind==='whatsapp'?' target="_blank" rel="noopener"':'')+'><span class="footer-contact-icon footer-icon-'+kind+'">'+icon(kind)+'</span><span><small>'+label+'</small><b>'+value+'</b></span><span class="footer-contact-arrow" aria-hidden="true">↗</span></a>';
  footer.innerHTML='<footer class="site-footer"><div class="footer-top"><div class="wrap footer-grid">' +
    '<div class="footer-brand"><div class="footer-brand-pair" aria-label="SUTRAVYA and QualiNova event partnership">' +
    '<a class="footer-sutravya-logo" href="https://sutravya.in" target="_blank" rel="noopener" aria-label="SUTRAVYA website"><img src="assets/sutravya-logo.png" alt="SUTRAVYA — The Digital Thread of Healthcare"></a>' +
    '<span class="footer-brand-handshake" aria-hidden="true"><img src="assets/handshake.svg" alt=""></span><a class="footer-qualinova-logo" href="https://qualinovahub.com" target="_blank" rel="noopener" aria-label="QualiNova website"><img src="assets/qualinova-logo.png" alt="QualiNova Solutions — event organiser"></a></div>' +
    '<p class="footer-tagline">The Digital Thread of Healthcare</p><p>Assessment and technology partner for the Healthcare Talent Search Exam 2026, organised by QualiNova.</p>' +
    '<a class="footer-site-link" href="https://sutravya.in" target="_blank" rel="noopener">Visit sutravya.in '+icon('arrow')+'</a></div>' +
    '<div class="footer-column"><h2>Explore</h2>'+navigation.slice(0,7).map(([url,label])=>'<a href="'+url+'">'+label+'</a>').join('')+'</div>' +
    '<div class="footer-column"><h2>Candidate access</h2><a href="register.html">Healthcare exam registration '+icon('arrow')+'</a><a href="login.html">Candidate sign-in '+icon('arrow')+'</a><a href="hackathon.html#hackathon-register">Free Hackathon registration '+icon('arrow')+'</a><a href="hackathon-portal.html">Hackathon participant portal '+icon('arrow')+'</a><div class="footer-exam-note"><b>6 December 2026</b><span>Healthcare Talent Search Exam</span><span>100 MCQs · 30 minutes</span></div></div>' +
    '<div class="footer-column footer-partners"><h2>Connect with SUTRAVYA</h2>'+
    contactLink('tel:+916239646429','phone','+91 62396 46429','CALL SUTRAVYA')+
    contactLink('mailto:sutravya.connect@gmail.com','mail','sutravya.connect@gmail.com','EMAIL SUTRAVYA')+
    contactLink('https://wa.me/916239646429','whatsapp','WhatsApp support','WHATSAPP SUTRAVYA')+
    '<h2 class="footer-subheading">Event organiser · QualiNova</h2>'+
    contactLink('tel:+919911350649','phone','+91 99113 50649','CALL QUALINOVA')+
    contactLink('https://wa.me/919911350649','whatsapp','WhatsApp support','WHATSAPP QUALINOVA')+
    contactLink('mailto:info@qualinovahub.com','mail','info@qualinovahub.com','EMAIL QUALINOVA')+
    '</div></div></div><div class="footer-bottom"><div class="wrap footer-bottom-inner"><span>© 2026 SUTRAVYA · Healthcare Talent Search Exam 2026</span><span>Event information is subject to official organiser updates.</span><a href="contact.html">Contact '+icon('arrow')+'</a></div></div></footer>';
}

function initFaqSearch(){
  const input=document.getElementById('faq-search-input');
  const groups=[...document.querySelectorAll('.qv2-faq-group')];
  if(!input||!groups.length)return;
  const count=document.querySelector('[data-faq-count]');
  const empty=document.querySelector('[data-faq-empty]');
  const entries=groups.map(group=>({group,heading:group.querySelector('h3'),details:[...group.querySelectorAll('details')]}));
  const filter=()=>{
    const query=input.value.trim().toLocaleLowerCase();
    let visibleCount=0;
    entries.forEach(({group,heading,details})=>{
      let groupCount=0;
      details.forEach(detail=>{const visible=!query||detail.textContent.toLocaleLowerCase().includes(query);detail.hidden=!visible;if(visible)groupCount++;});
      group.hidden=groupCount===0;
      if(heading)heading.hidden=groupCount===0;
      visibleCount+=groupCount;
    });
    if(count)count.textContent=query?visibleCount+' matching '+(visibleCount===1?'question':'questions'):visibleCount+' questions';
    if(empty)empty.hidden=visibleCount!==0;
  };
  input.addEventListener('input',filter);
  filter();
}
initFaqSearch();
function registrationState(now = Date.now()) {
  if (now < eventConfig.registrationOpensAt) return 'before';
  if (now > eventConfig.registrationClosesAt) return 'closed';
  return 'open';
}

function applyCentralEventContent() {
  document.querySelectorAll('[data-event-name]').forEach(node => { node.textContent = eventConfig.title; });
  document.querySelectorAll('[data-event-date]').forEach(node => { node.textContent = eventConfig.examDate; });
  document.querySelectorAll('[data-event-question-count]').forEach(node => { node.textContent = String(eventConfig.questionCount); });
  document.querySelectorAll('[data-event-duration]').forEach(node => { node.textContent = String(eventConfig.durationMinutes); });
  document.querySelectorAll('[data-event-stream-count]').forEach(node => { node.textContent = String(eventConfig.assessmentStreams.length); });
  document.querySelectorAll('[data-registration-category-count]').forEach(node => { node.textContent = String(eventConfig.registrationCategories.length); });
  document.querySelectorAll('[data-registration-open-date]').forEach(node => { node.textContent = eventConfig.registrationOpensDate; });
  document.querySelectorAll('[data-registration-open-time]').forEach(node => { node.textContent = eventConfig.registrationOpensTime; });
  document.querySelectorAll('[data-registration-close-date]').forEach(node => { node.textContent = eventConfig.registrationClosesDate; });
  document.querySelectorAll('[data-registration-close-time]').forEach(node => { node.textContent = eventConfig.registrationClosesTime; });
}
applyCentralEventContent();

function initCampaignCarousel() {
  const carousel = document.querySelector('[data-campaign-carousel]');
  if (!carousel) return;
  const slides = [...carousel.querySelectorAll('[data-campaign-slide]')];
  const dots = [...carousel.querySelectorAll('[data-campaign-dot]')];
  const previous = carousel.querySelector('[data-campaign-prev]');
  const next = carousel.querySelector('[data-campaign-next]');
  const toggle = carousel.querySelector('[data-campaign-toggle]');
  const toggleIcon = carousel.querySelector('[data-campaign-toggle-icon]');
  const toggleLabel = carousel.querySelector('[data-campaign-toggle-label]');
  if (slides.length !== 3 || dots.length !== 3) return;

  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  let active = 0;
  let timer = null;
  let userPaused = reducedMotion.matches;
  let hoverPaused = false;
  let focusPaused = false;
  let pointerStart = null;

  const isPaused = () => userPaused || hoverPaused || focusPaused || document.hidden || reducedMotion.matches;
  const syncPauseControl = () => {
    const paused = isPaused();
    carousel.classList.toggle('is-paused', paused);
    toggle?.setAttribute('aria-pressed', String(userPaused));
    toggle?.setAttribute('aria-label', userPaused ? 'Play automatic slides' : 'Pause automatic slides');
    if (toggleIcon) toggleIcon.textContent = userPaused ? '▶' : 'Ⅱ';
    if (toggleLabel) toggleLabel.textContent = userPaused ? 'Play automatic slides' : 'Pause automatic slides';
  };
  const stop = () => { if (timer) window.clearInterval(timer); timer = null; };
  const schedule = () => {
    stop();
    syncPauseControl();
    if (!isPaused()) timer = window.setInterval(() => show(active + 1), 6000);
  };
  function show(index) {
    active = (index + slides.length) % slides.length;
    slides.forEach((slide, i) => {
      const current = i === active;
      slide.hidden = !current;
      slide.classList.toggle('is-active', current);
      slide.setAttribute('aria-hidden', String(!current));
    });
    dots.forEach((dot, i) => {
      const current = i === active;
      dot.classList.toggle('is-active', current);
      dot.setAttribute('aria-pressed', String(current));
    });
    carousel.dataset.activeSlide = String(active + 1);
    if (timer) schedule();
  }

  previous?.addEventListener('click', () => { show(active - 1); schedule(); });
  next?.addEventListener('click', () => { show(active + 1); schedule(); });
  dots.forEach(dot => dot.addEventListener('click', () => { show(Number(dot.dataset.campaignDot)); schedule(); }));
  toggle?.addEventListener('click', () => { userPaused = !userPaused; schedule(); });
  carousel.addEventListener('pointerenter', () => { hoverPaused = true; schedule(); });
  carousel.addEventListener('pointerleave', () => { hoverPaused = false; schedule(); });
  carousel.addEventListener('focusin', event => {
    if (event.target.matches(':focus-visible')) { focusPaused = true; schedule(); }
  });
  carousel.addEventListener('focusout', () => {
    window.setTimeout(() => {
      focusPaused = [...carousel.querySelectorAll(':focus')].some(element => element.matches(':focus-visible'));
      schedule();
    }, 0);
  });
  carousel.addEventListener('keydown', event => {
    if (event.altKey || event.ctrlKey || event.metaKey) return;
    if (event.key === 'ArrowLeft') { event.preventDefault(); show(active - 1); schedule(); }
    if (event.key === 'ArrowRight') { event.preventDefault(); show(active + 1); schedule(); }
  });
  carousel.addEventListener('pointerdown', event => {
    if (event.pointerType === 'touch') pointerStart = { x: event.clientX, y: event.clientY };
  }, { passive: true });
  carousel.addEventListener('pointerup', event => {
    if (!pointerStart) return;
    const dx = event.clientX - pointerStart.x;
    const dy = event.clientY - pointerStart.y;
    if (Math.abs(dx) > 48 && Math.abs(dx) > Math.abs(dy) * 1.25) {
      show(active + (dx < 0 ? 1 : -1));
      schedule();
    }
    pointerStart = null;
  }, { passive: true });
  carousel.addEventListener('pointercancel', () => { pointerStart = null; });
  document.addEventListener('visibilitychange', schedule);
  reducedMotion.addEventListener?.('change', event => {
    if (event.matches) userPaused = true;
    schedule();
  });
  show(0);
  schedule();
}
initCampaignCarousel();

function updateRegistrationSlideStatus() {
  const status = document.querySelector('[data-registration-slide-status]');
  if (!status) return;
  const state = registrationState();
  status.textContent = state === 'before' ? 'REGISTRATION OPENS 1 NOVEMBER'
    : state === 'open' ? 'REGISTRATION IS OPEN'
      : 'REGISTRATION CLOSED';
  status.dataset.state = state;
}
updateRegistrationSlideStatus();
function formatRemaining(milliseconds) {
  const total = Math.max(0, Math.floor(milliseconds / 1000));
  return { days: Math.floor(total / 86400), hours: Math.floor(total % 86400 / 3600), minutes: Math.floor(total % 3600 / 60), seconds: total % 60 };
}
function updateCountdown() {
  const box = document.querySelector('[data-registration-countdown]');
  if (!box) return;
  const now = Date.now();
  const state = registrationState(now);
  const target = state === 'before' ? eventConfig.registrationOpensAt : eventConfig.registrationClosesAt;
  const remaining = formatRemaining(state === 'closed' ? 0 : Math.max(0, target - now));
  box.setAttribute('aria-label', state === 'before' ? 'Time until registration opens' : state === 'open' ? 'Time until registration closes' : 'Registration is closed');
  for (const [key, value] of Object.entries(remaining)) {
    const slot = box.querySelector(`[data-count-${key}]`);
    if (slot) slot.textContent = String(value).padStart(2, '0');
  }
  const title = document.querySelector('[data-window-title]');
  const description = document.querySelector('[data-window-description]');
  if (title) title.textContent = state === 'before' ? 'Registration opens soon' : state === 'open' ? 'Registration is open' : 'Registration is closed';
  if (description) description.textContent = state === 'before'
    ? `Public registration opens ${eventConfig.registrationOpensLabel}.`
    : state === 'open' ? `Complete registration by ${eventConfig.registrationClosesLabel}.`
      : 'The registration period ended on 6 December 2026.';
  box.classList.toggle('countdown-closed', state === 'closed');
  updateRegistrationSlideStatus();
}
updateCountdown();
window.setInterval(updateCountdown, 1000);

document.querySelectorAll('[data-register-form]').forEach(form => {
  const note = form.querySelector('.register-note');
  const windowNote = form.querySelector('[data-registration-window-note]');
  const otpStep = form.querySelector('[data-otp-step]');
  const resendBox = form.querySelector('[data-confirmation-resend]');
  const successBox = form.querySelector('[data-registration-success]');
  const otpInput = form.querySelector('#registration-otp');
  const startButton = form.querySelector('[data-start-registration]');
  const internalPanel = form.querySelector('[data-internal-testing-panel]');
  const internalCodeInput = form.querySelector('#internal-access-code');
  const internalFields = form.querySelector('[data-registration-fields]');
  const internalRecordLabel = form.querySelector('[data-internal-record-label]');
  const internalSuccess = form.querySelector('[data-internal-success]');
  const progressSteps = [...form.querySelectorAll('[data-reg-progress]')];
  const updateProgress = current => {
    progressSteps.forEach((step, index) => {
      const number = index + 1;
      step.classList.toggle('is-complete', number < current);
      if (number === current) step.setAttribute('aria-current', 'step');
      else step.removeAttribute('aria-current');
    });
  };
  updateProgress(1);
  let challengeId = '';
  let completed = false;
  let internalAccessCode = '';
  let challengeIsTeamPrelaunch = false;
  // Preserve pre-launch authorization for the lifetime of a challenge. A team
  // candidate may request OTP before midnight IST and verify it after public opening.
  const internalHeaders = () => (challengeIsTeamPrelaunch || registrationState() === 'before') && internalAccessCode
    ? { 'X-Internal-Test-Code': internalAccessCode }
    : {};
  const showMessage = (message, isError = false) => {
    if (!note) return;
    note.textContent = message;
    note.classList.add('show');
    note.classList.toggle('error', isError);
  };
  const updateRegistrationWindow = () => {
    const state = registrationState();
    updateRegistrationSlideStatus();
    if (windowNote) {
      windowNote.classList.toggle('is-closed', state === 'closed');
      windowNote.classList.toggle('is-open', state === 'open');
      const message = state === 'before' ? `Public registration opens ${eventConfig.registrationOpensLabel}.` : state === 'closed' ? `Registration closed on ${eventConfig.registrationClosesLabel}.` : `Registration is open until ${eventConfig.registrationClosesLabel}.`;
      // Only update this live status when the registration state/message changes.
      if (windowNote.textContent !== message) windowNote.textContent = message;
    }
    const before = state === 'before';
    const closed = state === 'closed';
    if (internalPanel) internalPanel.hidden = !before;
    if (internalFields) internalFields.hidden = (before && !internalAccessCode) || closed;
    const unavailable = closed || (before && !internalAccessCode);
    form.querySelectorAll('[data-registration-field]').forEach(field => field.querySelectorAll('input,select,textarea').forEach(control => { control.disabled = unavailable; }));
    if (startButton) startButton.disabled = unavailable || startButton.dataset.busy === 'true';
    if (otpInput) otpInput.disabled = closed || (before && !internalAccessCode);
    form.querySelectorAll('[data-otp-step] button').forEach(button => { button.disabled = closed || (before && !internalAccessCode) || button.dataset.busy === 'true'; });
    if (internalCodeInput) internalCodeInput.disabled = !before || closed;
    const unlock = form.querySelector('[data-unlock-internal]');
    if (unlock) unlock.disabled = !before || closed;
  };
  const markBusy = busy => {
    form.querySelectorAll('button:not([data-copy-registration-id]):not([data-resend-confirmation])').forEach(button => { button.dataset.busy = String(busy); button.disabled = busy; });
    if (!busy) updateRegistrationWindow();
  };
  updateRegistrationWindow();
  window.setInterval(updateRegistrationWindow, 1000);
  form.querySelector('[data-unlock-internal]')?.addEventListener('click', () => {
    const value = internalCodeInput?.value || '';
    if (!value) { showMessage('Enter your internal team access code to continue.', true); internalCodeInput?.focus(); return; }
    internalAccessCode = value;
    if (internalFields) internalFields.hidden = false;
    if (internalRecordLabel) internalRecordLabel.hidden = false;
    updateRegistrationWindow();
    showMessage('Team pre-launch access selected. The server will validate your code when you request the email code.');
  });
  internalCodeInput?.addEventListener('keydown', event => { if (event.key === 'Enter') { event.preventDefault(); form.querySelector('[data-unlock-internal]')?.click(); } });
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const state = registrationState();
    if (state === 'closed' || (state === 'before' && !internalAccessCode)) { updateRegistrationWindow(); return; }
    if (challengeId || completed || !form.reportValidity()) return;
    markBusy(true); showMessage('Sending your email verification code…');
    try {
      challengeIsTeamPrelaunch = state === 'before';
      const result = await apiRequest('/api/registrations/start', {
        full_name: form.elements.full_name.value,
        mobile: form.elements.mobile.value,
        email: form.elements.email.value,
        stream: form.elements.stream.value
      }, 'POST', internalHeaders());
      challengeId = result.challenge_id;
      if (!challengeId) { showMessage(result.message || 'If this email can be registered, a verification code will be sent.'); return; }
      form.querySelectorAll('[data-registration-field]').forEach(field => { field.hidden = true; });
      if (startButton) startButton.hidden = true;
      if (otpStep) otpStep.hidden = false;
      updateProgress(2);
      otpInput?.focus();
      showMessage('If delivery succeeds, enter the 6-digit code sent to your email.');
    } catch (error) { showMessage(error.message, true); }
    finally { markBusy(false); }
  });
  form.querySelector('[data-verify-otp]')?.addEventListener('click', async () => {
    const state = registrationState();
    if (!challengeId || state === 'closed' || (state === 'before' && !challengeIsTeamPrelaunch)) { updateRegistrationWindow(); return; }
    if (!otpInput?.reportValidity()) return;
    markBusy(true); showMessage('Verifying your email and completing registration…');
    try {
      const result = await apiRequest('/api/registrations/verify-email', { challenge_id: challengeId, otp: otpInput.value }, 'POST', internalHeaders());
      completed = true;
      updateProgress(3);
      // The challenge is complete; discard the internal access code from page memory.
      internalAccessCode = '';
      challengeIsTeamPrelaunch = false;
      const registrationId = result.registration_id || '';
      form.querySelector('[data-registration-id]').textContent = registrationId;
      if (internalSuccess) internalSuccess.hidden = result.registration_source !== 'team_prelaunch';
      form.querySelector('[data-confirmation-message]').textContent = result.confirmation_email_sent ? 'A confirmation email has been sent.' : 'Your registration is complete, but the confirmation email could not be sent. You can request it again below.';
      if (successBox) successBox.hidden = false;
      if (resendBox) { resendBox.hidden = !registrationId; const idInput = resendBox.querySelector('input'); if (idInput) idInput.value = registrationId; }
      if (otpStep) otpStep.hidden = true;
      challengeId = '';
      showMessage('Registration saved successfully. Keep your Registration ID for your records.');
    } catch (error) { showMessage(error.message, true); }
    finally { markBusy(false); }
  });
  form.querySelector('[data-copy-registration-id]')?.addEventListener('click', async () => {
    const registrationId = form.querySelector('[data-registration-id]')?.textContent || '';
    if (!registrationId) return;
    try { await navigator.clipboard.writeText(registrationId); showMessage('Registration ID copied. Keep it safe.'); }
    catch { showMessage('Copy is unavailable in this browser. Select and copy your Registration ID above.', true); }
  });
  form.querySelector('[data-resend-otp]')?.addEventListener('click', async () => {
    const state = registrationState();
    if (!challengeId || state === 'closed' || (state === 'before' && !challengeIsTeamPrelaunch)) { updateRegistrationWindow(); return; }
    markBusy(true); showMessage('Requesting a new verification code…');
    try { const result = await apiRequest('/api/registrations/resend-otp', { challenge_id: challengeId }, 'POST', internalHeaders()); challengeId = result.challenge_id; showMessage('A new code has been sent if delivery succeeds.'); }
    catch (error) { showMessage(error.message, true); }
    finally { markBusy(false); }
  });
  form.querySelector('[data-resend-confirmation]')?.addEventListener('click', async () => {
    const registrationId = resendBox?.querySelector('input')?.value || '';
    markBusy(true); showMessage('Requesting the confirmation email…');
    try { const result = await apiRequest('/api/registrations/resend-confirmation', { registration_id: registrationId }); showMessage(result.message); }
    catch (error) { showMessage(error.message, true); }
    finally { markBusy(false); }
  });
});

document.querySelectorAll('[data-login-form]').forEach(form => {
  const examAccess = form.querySelector('[data-exam-access]');
  const revealExamAccess = async () => {
    try {
      const account = await apiRequest('/api/auth/session', undefined, 'GET');
      const eligibleStream = ['nursing', 'paramedical', 'pharmacy'].includes(account.stream);
      const examEligible = eligibleStream && account.registration_status === 'active';
      if (examAccess) examAccess.hidden = !examEligible;
      const card = form.parentElement.querySelector('[data-candidate-application]');
      if (card) {
        card.hidden = false;
        card.querySelector('[data-application-name]').textContent = account.full_name || 'Candidate';
        card.querySelector('[data-application-status]').textContent = (account.registration_status || 'active').replaceAll('_', ' ');
        const idRow = card.querySelector('[data-application-id-row]');
        if (idRow) idRow.hidden = !account.registration_id;
        const id = card.querySelector('[data-application-id]');
        if (id) id.textContent = account.registration_id || '—';
        const message = card.querySelector('[data-application-message]');
        if (message) message.textContent = 'Your free candidate registration is confirmed.';
        card.querySelector('[data-candidate-logout]')?.addEventListener('click', async () => {
          try { await apiRequest('/api/auth/logout', {}, 'POST'); }
          finally { location.reload(); }
        });
      }
    } catch { if (examAccess) examAccess.hidden = true; }
  };
  revealExamAccess();
  const note = form.querySelector('.register-note');
  const otpStep = form.querySelector('[data-login-otp-step]');
  const resend = form.querySelector('[data-login-resend]');
  let requested = false;
  let resendTimer;
  const show = (message, error = false) => { note.textContent = message; note.classList.add('show'); note.classList.toggle('error', error); };
  const startCooldown = () => {
    let remaining = 60;
    resend.disabled = true;
    resend.textContent = `Resend code in ${remaining} seconds`;
    clearInterval(resendTimer);
    resendTimer = setInterval(() => {
      remaining--;
      if (remaining <= 0) { clearInterval(resendTimer); resend.disabled = false; resend.textContent = 'Resend code'; }
      else resend.textContent = `Resend code in ${remaining} seconds`;
    }, 1000);
  };
  const requestCode = async () => {
    show('Requesting a sign-in code…');
    try { const result = await apiRequest('/api/auth/request-otp', { email: form.elements.email.value }); requested = true; otpStep.hidden = false; form.querySelector('#login-otp')?.focus(); startCooldown(); show(result.message); }
    catch (error) { show(error.message, true); }
  };
  form.addEventListener('submit', async event => { event.preventDefault(); if (requested || !form.reportValidity()) return; const button = form.querySelector('[type="submit"]'); button.disabled = true; await requestCode(); button.disabled = false; });
  resend?.addEventListener('click', async () => { if (resend.disabled) return; await requestCode(); });
  form.querySelector('[data-login-verify]')?.addEventListener('click', async () => {
    const button = form.querySelector('[data-login-verify]');
    if (!form.querySelector('#login-otp')?.reportValidity()) return;
    button.disabled = true; show('Verifying your code…');
    let signedIn = false;
    try { await apiRequest('/api/auth/verify-otp', { email: form.elements.email.value, otp: form.elements.otp.value }); signedIn = true; setLoginStep(3); await revealExamAccess(); show('You are signed in. Your secure session will remain active across refreshes.'); form.querySelectorAll('input,button').forEach(control => { control.disabled = true; }); }
    catch (error) { show(error.message, true); }
    finally { if (!signedIn) button.disabled = false; }
  });
});


// Keep publication states driven by the single event configuration object.
const awardsGrid = document.querySelector('.award-preview-grid');
if (awardsGrid) {
  document.body.dataset.awardsStatus = eventConfig.awardsPublished ? 'published' : 'pending';
  awardsGrid.querySelectorAll('.award-preview').forEach(card => card.classList.toggle('is-pending', !eventConfig.awardsPublished));
}
const nursingFramework = document.querySelector('.syllabus-stream-ready');
if (nursingFramework) {
  nursingFramework.classList.toggle('is-proposed', !eventConfig.nursingSyllabusApproved);
  document.body.dataset.nursingSyllabusStatus = eventConfig.nursingSyllabusApproved ? 'approved' : 'proposed';
}

document.querySelectorAll('[data-sample]').forEach(group => group.addEventListener('change', event => {
  const pending = group.querySelector('.answer-pending');
  if (pending && !eventConfig.officialSampleAnswersPublished) pending.hidden = false;
}));

document.querySelectorAll('.faq-list').forEach(list => {
  list.querySelectorAll('details').forEach(item => item.addEventListener('toggle', () => {
    if (item.open) list.querySelectorAll('details[open]').forEach(other => { if (other !== item) other.open = false; });
  }));
});

document.querySelectorAll('.stream-card,.highlight-card,.award-preview,.syllabus-stream,.question-card,.contact-card,.faq,.feature,.surface,.topic').forEach((item, index) => {
  item.classList.add('reveal-item');
  item.style.setProperty('--reveal-delay', `${Math.min(index % 5, 4) * 55}ms`);
});
if ('IntersectionObserver' in window && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
  const observer = new IntersectionObserver(entries => entries.forEach(entry => {
    if (entry.isIntersecting) { entry.target.classList.add('is-visible'); observer.unobserve(entry.target); }
  }), { threshold: 0.1 });
  document.querySelectorAll('.reveal-item').forEach(item => observer.observe(item));
} else document.querySelectorAll('.reveal-item').forEach(item => item.classList.add('is-visible'));

initHumanVisuals();


function initExamCountdown() {
  const panel = document.querySelector('[data-event-countdown]');
  if (!panel) return;
  const target = eventConfig.examStartsAt;
  const close = eventConfig.examEndsAt;
  const fields = {
    days: panel.querySelector('[data-countdown-days]'),
    hours: panel.querySelector('[data-countdown-hours]'),
    minutes: panel.querySelector('[data-countdown-minutes]'),
    seconds: panel.querySelector('[data-countdown-seconds]'),
    status: panel.querySelector('[data-countdown-status]')
  };
  const pad = value => String(value).padStart(2, '0');
  const update = () => {
    const now = Date.now();
    const remaining = Math.max(0, target - now);
    const days = Math.floor(remaining / 86400000);
    const hours = Math.floor((remaining % 86400000) / 3600000);
    const minutes = Math.floor((remaining % 3600000) / 60000);
    const seconds = Math.floor((remaining % 60000) / 1000);
    if (fields.days) fields.days.textContent = pad(days);
    if (fields.hours) fields.hours.textContent = pad(hours);
    if (fields.minutes) fields.minutes.textContent = pad(minutes);
    if (fields.seconds) fields.seconds.textContent = pad(seconds);
    if (fields.status) {
      if (now < target) {
        fields.status.textContent = 'The online assessment opens on Sunday, 6 December 2026 at 10:00 AM IST.';
        panel.dataset.countdownState = 'upcoming';
      } else if (now < close) {
        fields.status.textContent = 'The examination window is now open. Sign in to your candidate account to begin your 30-minute attempt.';
        panel.dataset.countdownState = 'open';
      } else {
        fields.status.textContent = 'The 6 December 2026 examination window has closed.';
        panel.dataset.countdownState = 'closed';
      }
    }
  };
  update();
  window.setInterval(update, 1000);
}
initExamCountdown();
