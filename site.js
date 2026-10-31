/* Shared microsite shell and interactions. Keep event facts in this object. */
const eventConfig = Object.freeze({
  title: 'Healthcare Talent Search Exam 2026',
  shortTitle: 'Healthcare Talent Search Exam',
  examFee: 'Free of Cost',
  registrationOpensLabel: '1 November 2026 at 12:00 AM IST',
  registrationOpensDate: '1 November 2026',
  registrationOpensTime: '12:00 AM IST',
  registrationClosesLabel: '15 November 2026 at 11:59:59 PM IST',
  registrationClosesDate: '15 November 2026',
  registrationClosesTime: '11:59:59 PM IST',
  examDate: '4 December 2026',
  registrationOpensAt: Date.parse('2026-10-31T18:30:00.000Z'), // 1 Nov, 00:00 IST
  registrationClosesAt: Date.parse('2026-11-15T18:29:59.999Z'), // 15 Nov, 23:59:59 IST
  timeZone: 'Asia/Kolkata',
  assessmentStreams: Object.freeze(['Paramedical', 'Nursing', 'MBBS 1st Year']),
  registrationCategories: Object.freeze(['Paramedical', 'Nursing', 'MBBS 1st Year', 'Other']),
  streams: Object.freeze(['Paramedical', 'Nursing', 'MBBS 1st Year', 'Other']),
  prizes: Object.freeze([{place: 1, amount: 50000}, {place: 2, amount: 25000}, {place: 3, amount: 15000}]),
  questionCount: 100,
  durationMinutes: 30,
  negativeMarking: false,
  awardsPublished: true,
  nursingSyllabusApproved: false,
  officialSampleAnswersPublished: false
});

const navigation = [
  ['index.html', 'Home'], ['awards.html', 'Awards & Prizes'],
  ['syllabus.html', 'Syllabus'], ['sample-papers.html', 'Sample Questions'],
  ['mock-test.html', 'Mock Test'], ['faqs.html', 'FAQs'], ['contact.html', 'Contact']
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
    close: '<path d="m6 6 12 12M18 6 6 18"/>'
  };
  return `<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">${paths[name] || paths.arrow}</svg>`;
}

const header = document.querySelector('[data-header]');
if (header) {
  const links = navigation.map(([url, label]) => `<a href="${url}"${url === currentPage ? ' aria-current="page"' : ''}>${label}</a>`).join('');
  header.innerHTML = `<div class="site-topline"></div><header class="site-header"><div class="wrap header-inner"><div class="header-brand-lockup"><a class="brand" href="index.html" aria-label="SUTRAVYA home"><img src="assets/sutravya-logo.png" alt="SUTRAVYA — The Digital Thread of Healthcare"></a><span class="header-brand-divider" aria-hidden="true"></span><a class="partner-brand" href="https://qualinovahub.com" target="_blank" rel="noopener" aria-label="QualiNova, event organiser"><small>EVENT ORGANISER</small><img src="assets/qualinova-logo.png" alt="QualiNova"></a></div><button class="nav-toggle" type="button" aria-label="Open navigation" aria-expanded="false" aria-controls="primary-navigation"><span class="nav-toggle-icon">${icon('menu')}</span><span>Menu</span></button><nav class="primary-nav" id="primary-navigation" aria-label="Main navigation">${links}<a class="nav-register" href="index.html#register">Register now ${icon('arrow')}</a></nav></div></header>`;
  const toggle = header.querySelector('.nav-toggle');
  const nav = header.querySelector('.primary-nav');
  const closeMenu = () => { nav.classList.remove('is-open'); toggle.setAttribute('aria-expanded', 'false'); toggle.setAttribute('aria-label', 'Open navigation'); toggle.querySelector('.nav-toggle-icon').innerHTML = icon('menu'); };
  toggle.addEventListener('click', () => {
    const open = nav.classList.toggle('is-open');
    toggle.setAttribute('aria-expanded', String(open));
    toggle.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
    toggle.querySelector('.nav-toggle-icon').innerHTML = icon(open ? 'close' : 'menu');
  });
  nav.addEventListener('click', event => { if (event.target.closest('a')) closeMenu(); });
  document.addEventListener('keydown', event => { if (event.key === 'Escape') closeMenu(); });
  document.addEventListener('click', event => { if (!header.contains(event.target)) closeMenu(); });
}


function renderContextualPostcard() {
  const main = document.querySelector('main');
  if (!main || currentPage === 'index.html' || currentPage === 'awards.html' || currentPage === 'team-prelaunch.html' || currentPage === 'login.html') return;
  const promos = {
    'syllabus.html': {image:'assets/htse-campaign-postcard.webp', alt:'Healthcare Talent Search Exam emblem with medical cross, ECG, laurel and healthcare learners', eyebrow:'PREPARE WITH PURPOSE', title:'A stronger foundation starts with a clear plan.', copy:'Explore stream-wise practice topics, then put your learning into action with a timed mock test.', cta:'Try the mock test', href:'mock-test.html'},
    'sample-papers.html': {image:'assets/htse-campaign-postcard.webp', alt:'Healthcare Talent Search Exam emblem with medical cross, ECG, laurel and healthcare learners', eyebrow:'PRACTICE MAKES PROGRESS', title:'Get comfortable with the question style.', copy:'Start with short sample questions, understand the reasoning and build confidence before a full practice paper.', cta:'Start a full mock test', href:'mock-test.html'},
    'mock-test.html': {image:'assets/htse-campaign-postcard.webp', alt:'Healthcare Talent Search Exam emblem with medical cross, ECG, laurel and healthcare learners', eyebrow:'YOUR PRACTICE ARENA', title:'One focused session. A clearer view of what to revise.', copy:'Complete 100 questions in 30 minutes, then review your topic-wise practice score and explanations.', cta:'Review the syllabus', href:'syllabus.html'},
    'faqs.html': {image:'assets/htse-campaign-postcard.webp', alt:'Healthcare Talent Search Exam emblem with medical cross, ECG, laurel and healthcare learners', eyebrow:'YOUR NEXT STEP IN HEALTHCARE', title:'Know the format. Prepare with confidence.', copy:'The exam is free of cost, online and has no negative marking. Explore the streams and key dates.', cta:'View awards & prizes', href:'awards.html'},
    'contact.html': {image:'assets/htse-campaign-postcard.webp', alt:'Healthcare Talent Search Exam emblem with medical cross, ECG, laurel and healthcare learners', eyebrow:'RECOGNISING HEALTHCARE KNOWLEDGE', title:'Questions about the exam or prize information?', copy:'Connect with QualiNova, the event organiser, or SUTRAVYA, the assessment and technology partner.', cta:'Explore awards & prizes', href:'awards.html'}
  };
  const promo = promos[currentPage];
  if (!promo) return;
  const section = document.createElement('section');
  section.className = 'section v4-postcard-section';
  section.innerHTML = `<div class="wrap"><article class="v4-campaign-postcard"><div class="v4-postcard-art"><img src="${promo.image}" alt="${promo.alt}" loading="lazy"></div><div class="v4-postcard-copy"><span class="v4-eyebrow">${promo.eyebrow}</span><h2>${promo.title}</h2><p>${promo.copy}</p><a class="button button-gold" href="${promo.href}">${promo.cta} <span aria-hidden="true">→</span></a><div class="v4-postcard-prize-line"><span>1st ₹50,000</span><span>2nd ₹25,000</span><span>3rd ₹15,000</span></div></div></article></div>`;
  main.append(section);
}
renderContextualPostcard();

const footer = document.querySelector('[data-footer]');
if (footer) {
  footer.innerHTML = `<footer class="site-footer"><div class="footer-top"><div class="wrap footer-grid"><div class="footer-brand"><a href="index.html" aria-label="SUTRAVYA home"><img src="assets/sutravya-logo.png" alt="SUTRAVYA"></a><p class="footer-tagline">The Digital Thread of Healthcare</p><p>Assessment and technology partner for the Healthcare Talent Search Exam 2026, organised by QualiNova.</p><a class="footer-site-link" href="https://sutravya.in" target="_blank" rel="noopener">Visit sutravya.in ${icon('arrow')}</a></div><div class="footer-column"><h2>Explore</h2>${navigation.slice(0, 6).map(([url, label]) => `<a href="${url}">${label}</a>`).join('')}</div><div class="footer-column"><h2>Exam details</h2><span>4 December 2026</span><span>Online · ${eventConfig.assessmentStreams.length} assessment streams · ${eventConfig.registrationCategories.length} registration categories</span><span>100 MCQs · 30 minutes</span><span>No negative marking</span><span class="footer-free">Free of cost</span><a href="index.html#register">Registration details ${icon('arrow')}</a></div><div class="footer-column footer-partners"><h2>Event organiser · QualiNova</h2><a href="tel:+919955521842">+91 99555 21842</a><a href="mailto:info@qualinovahub.com">info@qualinovahub.com</a><a href="https://qualinovahub.com" target="_blank" rel="noopener">qualinovahub.com ${icon('arrow')}</a><h2 class="footer-subheading">Assessment &amp; technology partner · SUTRAVYA</h2><a href="tel:+916239646429">+91 62396 46429</a><a href="mailto:sutravya.connect@gmail.com">sutravya.connect@gmail.com</a></div></div></div><div class="footer-bottom"><div class="wrap footer-bottom-inner"><span>© 2026 SUTRAVYA · Healthcare Talent Search Exam 2026</span><span>Event information is subject to official organiser updates.</span><a href="contact.html">Contact</a></div></div></footer>`;
}

function registrationState(now = Date.now()) {
  if (now < eventConfig.registrationOpensAt) return 'before';
  if (now > eventConfig.registrationClosesAt) return 'closed';
  return 'open';
}

function applyCentralEventContent() {
  document.querySelectorAll('[data-event-name]').forEach(node => { node.textContent = eventConfig.title; });
  document.querySelectorAll('[data-event-date]').forEach(node => { node.textContent = eventConfig.examDate; });
  document.querySelectorAll('[data-event-fee]').forEach(node => { node.textContent = eventConfig.examFee; });
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
      : 'The registration period ended on 15 November 2026.';
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
    try { await apiRequest('/api/auth/verify-otp', { email: form.elements.email.value, otp: form.elements.otp.value }); signedIn = true; show('You are signed in. Your secure session will remain active across refreshes.'); form.querySelectorAll('input,button').forEach(control => { control.disabled = true; }); }
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
