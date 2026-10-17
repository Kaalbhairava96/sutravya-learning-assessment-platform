const pages=[['index.html','Home'],['awards.html','Scholarship & Awards'],['syllabus.html','Syllabus'],['sample-papers.html','Sample Papers'],['faqs.html','FAQs'],['contact.html','Contact']];
const current=location.pathname.split('/').pop()||'index.html';
const enhancementStyles=document.createElement('link');enhancementStyles.rel='stylesheet';enhancementStyles.href='visuals.css';document.head.append(enhancementStyles);
const examStyles=document.createElement('link');examStyles.rel='stylesheet';examStyles.href='exam.css';document.head.append(examStyles);
const header=document.querySelector('[data-header]');
if(header){header.innerHTML=`<div class="topline"></div><div class="header"><div class="wrap headerin"><a class="brand" href="index.html" aria-label="Sutrāvya home"><img src="assets/sutravya-logo.png" alt="Sutrāvya — The Digital Thread of Healthcare"></a><button class="navtoggle" aria-label="Open navigation" aria-expanded="false">☰ Menu</button><nav class="nav" aria-label="Main navigation">${pages.map(([url,label])=>`<a href="${url}" class="${url===current?'active':''}">${label}</a>`).join('')}<a class="navcta" href="index.html#register">Register now <span aria-hidden="true">→</span></a></nav></div></div>`;const toggle=header.querySelector('.navtoggle'),nav=header.querySelector('.nav');toggle.addEventListener('click',()=>{const open=nav.classList.toggle('open');toggle.setAttribute('aria-expanded',String(open));});}
const footer=document.querySelector('[data-footer]');
if(footer){footer.innerHTML=`<footer class="footer"><div class="wrap"><div class="footergrid"><div class="footerbrand"><a href="index.html"><img src="assets/sutravya-logo.png" alt="Sutrāvya"></a><p>Nursing Talent Hunt Exam: a nursing knowledge assessment and digital-health idea challenge delivered by Sutrāvya for Bihar Healthcare Conclave 2026.</p></div><div><h4>Exam information</h4><div class="footerlinks"><a href="awards.html">Awards</a><a href="syllabus.html">Syllabus</a><a href="sample-papers.html">Sample papers</a><a href="faqs.html">FAQs</a></div></div><div><h4>About this event</h4><div class="footerlinks"><span>Organised by Qualinova</span><span>Assessment partner: Sutrāvya</span><a href="https://sutravya.in" target="_blank" rel="noopener">sutravya.in ↗</a><a href="contact.html">Contact</a></div></div></div><div class="copyright"><span>© 2026 Sutrāvya · Nursing Talent Hunt Exam</span><span>Built for Bihar Healthcare Conclave 2026</span></div></div></footer>`;}
document.querySelectorAll('[data-register-form]').forEach(form=>form.addEventListener('submit',e=>{e.preventDefault();const note=form.querySelector('.register-note');if(note){note.textContent='The registration screen is a prototype. Candidate registration will be connected to secure storage before the exam opens.';note.classList.add('show');}}));
document.querySelectorAll('[data-sample]').forEach(group=>group.addEventListener('change',()=>{const q=group.closest('.sample-question');const answer=q.querySelector('.answer');if(answer)answer.classList.add('show');}));

// Homepage visual refresh: keep the homepage focused on the exam, not the award table.
if(current==='index.html'){
  document.querySelector('.award-strip')?.remove();
  const stats=document.querySelector('.hero-stats');
  if(stats)stats.innerHTML='<div class="hero-stat"><strong>MCQ</strong><span>Nursing knowledge</span></div><div class="hero-stat"><strong>IDEA</strong><span>Digital health</span></div><div class="hero-stat"><strong>2 STAGES</strong><span>Scored separately</span></div>';
  const heroCopy=document.querySelector('.hero-grid > div:first-child');
  const intro=heroCopy?.querySelector('.hero-sub');
  if(heroCopy&&intro){heroCopy.classList.add('hero-copy');const figure=document.createElement('figure');figure.className='hero-illustration';figure.innerHTML='<img src="assets/nurse-tech.svg" alt="Illustration of a nursing student beside a digital health monitor"><figcaption>CARE + TECHNOLOGY</figcaption>';intro.after(figure);}
  const partnerSection=document.querySelector('.section.white');
  if(partnerSection)partnerSection.innerHTML='<div class="wrap"><div class="sectionhead"><span class="eyebrow">ONE SHARED PURPOSE</span><h2>Better together, for better healthcare.</h2><p>QualiNova’s healthcare and medical education expertise meets Sutrāvya’s digital assessment experience.</p></div><div class="partnership-card"><div class="partner-logo"><span class="pill">EVENT ORGANISER</span><img src="assets/qualinova-logo.png" alt="QualiNova Solutions Pvt. Ltd."><p>Quality Institutions. Sustainable Impact.</p></div><div class="handshake-art"><img src="assets/handshake.svg" alt="Illustrated handshake representing the QualiNova and Sutrāvya partnership"><span>IN PARTNERSHIP</span></div><div class="partner-logo"><span class="pill">ASSESSMENT PARTNER</span><img class="sutravya-partner-logo" src="assets/sutravya-logo.png" alt="Sutrāvya — The Digital Thread of Healthcare"><p>Digital learning &amp; assessment for healthcare.</p></div></div></div>';
}

// Awards page poster uses the hand-drawn nursing illustration and the user-supplied award values.
if(current==='awards.html'){
  const awards=document.querySelector('.award-cards');
  if(awards)awards.insertAdjacentHTML('beforebegin','<section class="poster-ad"><div class="poster-copy"><span class="eyebrow">QUALINOVA × SUTRĀVYA PRESENT</span><h2>Nursing Talent<br><em>Hunt Exam 2026</em></h2><p>Show your nursing knowledge. Share a digital-health idea. Step into the future of care.</p><div class="poster-meta"><span>4 DEC 2026</span><span>11:00 AM IST</span><span>ONLINE</span></div></div><img src="assets/nurse-tech.svg" alt="Original illustration of a nurse using a digital health monitor"><div class="poster-prizes"><b>TOP 3 CASH AWARDS</b><span>₹50,000</span><span>₹25,000</span><span>₹10,000</span></div></section>');
}

if(current==='contact.html'){
  const contact=document.querySelector('.contact-cards');
  if(contact)contact.outerHTML='<section class="partner-contact-board" aria-label="QualiNova and Sutrāvya contact details"><article class="partner-contact"><span class="pill">EVENT ORGANISER</span><img src="assets/qualinova-logo.png" alt="QualiNova Solutions Pvt. Ltd."><table class="contact-table"><tbody><tr><th><span aria-hidden="true">☎</span> Phone</th><td><a href="tel:+919955521842">+91 99555 21842</a></td><td><a class="contact-action" href="tel:+919955521842">Call</a></td></tr><tr><th><span aria-hidden="true">◉</span> Email</th><td><a href="mailto:info@qualinovahub.com">info@qualinovahub.com</a></td><td><a class="contact-action" href="mailto:info@qualinovahub.com">Email</a></td></tr><tr><th><span aria-hidden="true">↗</span> Website</th><td>qualinovahub.com</td><td><a class="contact-action" href="https://www.qualinovahub.com/" target="_blank" rel="noopener">Visit</a></td></tr></tbody></table></article><div class="contact-handshake"><img src="assets/handshake.svg" alt="Handshake showing the partnership"><b>IN PARTNERSHIP</b></div><article class="partner-contact"><span class="pill">ASSESSMENT PARTNER</span><img class="sutravya-contact-logo" src="assets/sutravya-logo.png" alt="Sutrāvya — The Digital Thread of Healthcare"><table class="contact-table"><tbody><tr><th><span aria-hidden="true">☎</span> Phone</th><td><a href="tel:+916239646429">+91 62396 46429</a></td><td><a class="contact-action" href="tel:+916239646429">Call</a></td></tr><tr><th><span aria-hidden="true">◉</span> WhatsApp</th><td>Message our team</td><td><a class="contact-action whatsapp-action" href="https://wa.me/916239646429" target="_blank" rel="noopener">Chat</a></td></tr><tr><th><span aria-hidden="true">✉</span> Email</th><td><a href="mailto:sutravya.connect@gmail.com">sutravya.connect@gmail.com</a></td><td><a class="contact-action" href="mailto:sutravya.connect@gmail.com">Email</a></td></tr></tbody></table></article></section><div class="partner-motto"><b>QualiNova</b><span>Quality Institutions. Sustainable Impact.</span><span class="motto-dot">·</span><b>Sutrāvya</b><span>The Digital Thread of Healthcare</span></div>';
}

// Persistent animated exam card on every page; the homepage hero also gets the live countdown.
const examCard=document.createElement('aside');
examCard.className='exam-promo';
examCard.setAttribute('aria-label','Nursing Talent Hunt Exam 2026 details');
examCard.innerHTML='<div class="exam-promo-art"><img src="assets/nurse-tech.svg" alt="Nursing student using digital healthcare technology"></div><div class="exam-promo-copy"><span class="eyebrow">QUALINOVA × SUTRĀVYA</span><h2>Nursing Talent Hunt Exam <em>2026</em></h2><p>Show your nursing knowledge. Share your idea for the future of digital healthcare.</p><div class="exam-promo-meta"><span>📅 4 December 2026</span><span>◷ 11:00 AM IST</span><span>⌘ Online</span></div></div><a class="exam-promo-button" href="index.html#register">Explore the exam <span aria-hidden="true">→</span></a>';
const contentStart=document.querySelector('main .content');
const insertionPoint=contentStart?.previousElementSibling?.classList.contains('pagehero')?contentStart.previousElementSibling:document.querySelector('main .hero');
if(insertionPoint)insertionPoint.after(examCard);
else document.querySelector('main')?.prepend(examCard);

// Give every information page its own original, non-generated vector illustration.
const pageVisuals={
  'awards.html':['assets/awards-hero.svg','Recognition for nursing talent'],
  'syllabus.html':['assets/syllabus-hero.svg','Explore the learning map'],
  'sample-papers.html':['assets/sample-hero.svg','Try a practice question'],
  'faqs.html':['assets/faq-hero.svg','We’re here to help'],
  'contact.html':['assets/contact-hero.svg','Talk to the event team']
};
if(pageVisuals[current]){
  const hero=document.querySelector('.pagehero .wrap');
  if(hero){const nodes=[...hero.children];const copy=document.createElement('div');copy.className='pagehero-copy';nodes.forEach(node=>copy.append(node));const art=document.createElement('figure');art.className='pagehero-art';art.innerHTML=`<img src="${pageVisuals[current][0]}" alt="${pageVisuals[current][1]}"><figcaption>${pageVisuals[current][1]}</figcaption>`;hero.append(copy,art);}
}

// Small interactions make the exam date and learning cards feel responsive.
if(current==='index.html'){
  const poster=document.querySelector('.poster');
  if(poster){poster.insertAdjacentHTML('afterbegin','<div class="countdown-chip"><span class="countdown-dot"></span><span id="exam-countdown" aria-live="polite">Countdown to exam</span></div>');const display=document.getElementById('exam-countdown');const examAt=Date.parse('2026-12-04T11:00:00+05:30');const update=()=>{const remaining=examAt-Date.now();if(remaining<=0){display.textContent='Exam day is here';return;}const days=Math.floor(remaining/86400000),hours=Math.floor(remaining%86400000/3600000),minutes=Math.floor(remaining%3600000/60000),seconds=Math.floor(remaining%60000/1000);display.textContent=`${days} days · ${String(hours).padStart(2,'0')} hrs · ${String(minutes).padStart(2,'0')} min · ${String(seconds).padStart(2,'0')} sec left`;};update();setInterval(update,1000);}
}

document.querySelectorAll('.feature,.surface,.award-card,.topic,.faq,.contact-card').forEach((item,index)=>{item.classList.add('reveal-item');item.style.setProperty('--reveal-delay',`${Math.min(index%5,4)*65}ms`);});
if('IntersectionObserver' in window){const observer=new IntersectionObserver(entries=>entries.forEach(entry=>{if(entry.isIntersecting){entry.target.classList.add('is-visible');observer.unobserve(entry.target);}}),{threshold:.12});document.querySelectorAll('.reveal-item').forEach(item=>observer.observe(item));}else document.querySelectorAll('.reveal-item').forEach(item=>item.classList.add('is-visible'));
