/* Shared microsite shell and interactions. Keep event facts in this object. */
const eventConfig = Object.freeze({
  title: 'QualiNova Assessment 2026',
  examDate: '4 December 2026',
  registrationOpensAt: Date.parse('2026-10-31T18:30:00.000Z'), // 1 Nov, 00:00 IST
  registrationClosesAt: Date.parse('2026-11-15T18:29:59.999Z'), // 15 Nov, 23:59:59 IST
  timeZone: 'Asia/Kolkata',
  streams: Object.freeze(['Paramedical', 'Nursing', 'MBBS 1st Year']),
  questionCount: 100,
  durationMinutes: 30,
  awardsPublished: false,
  ideaRoundEnabled: false,
  nursingSyllabusApproved: false,
  officialSampleAnswersPublished: false,
  examStartTimeApproved: false
});

const navigation = [
  ['index.html', 'Home'], ['awards.html', 'Scholarship & Awards'],
  ['syllabus.html', 'Syllabus'], ['sample-papers.html', 'Sample Papers'],
  ['faqs.html', 'FAQs'], ['contact.html', 'Contact']
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
  header.innerHTML = `<div class="site-topline"></div><header class="site-header"><div class="wrap header-inner"><a class="brand" href="index.html" aria-label="SUTRAVYA Assessment home"><img src="assets/sutravya-logo.png" alt="SUTRAVYA — The Digital Thread of Healthcare"></a><button class="nav-toggle" type="button" aria-label="Open navigation" aria-expanded="false" aria-controls="primary-navigation"><span class="nav-toggle-icon">${icon('menu')}</span><span>Menu</span></button><nav class="primary-nav" id="primary-navigation" aria-label="Main navigation">${links}<a class="nav-register" href="index.html#register">Register now ${icon('arrow')}</a></nav></div></header>`;
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

const footer = document.querySelector('[data-footer]');
if (footer) {
  footer.innerHTML = `<footer class="site-footer"><div class="footer-top"><div class="wrap footer-grid"><div class="footer-brand"><a href="index.html" aria-label="SUTRAVYA home"><img src="assets/sutravya-logo.png" alt="SUTRAVYA"></a><p class="footer-tagline">The Digital Thread of Healthcare</p><p>Assessment and technology partner for QualiNova Assessment 2026.</p><a class="footer-site-link" href="https://sutravya.in" target="_blank" rel="noopener">Visit sutravya.in ${icon('arrow')}</a></div><div class="footer-column"><h2>Explore</h2>${navigation.slice(0, 5).map(([url, label]) => `<a href="${url}">${label}</a>`).join('')}</div><div class="footer-column"><h2>Assessment</h2><span>4 December 2026</span><span>Online · 3 streams</span><span>100 MCQs · 30 minutes</span><span>No negative marking</span><a href="index.html#register">Registration details ${icon('arrow')}</a></div><div class="footer-column footer-partners"><h2>Event organiser · QualiNova</h2><a href="tel:+919955521842">+91 99555 21842</a><a href="mailto:info@qualinovahub.com">info@qualinovahub.com</a><a href="https://qualinovahub.com" target="_blank" rel="noopener">qualinovahub.com ${icon('arrow')}</a><h2 class="footer-subheading">Assessment partner · SUTRAVYA</h2><a href="tel:+916239646429">+91 62396 46429</a><a href="mailto:sutravya.connect@gmail.com">sutravya.connect@gmail.com</a></div></div></div><div class="footer-bottom"><div class="wrap footer-bottom-inner"><span>© 2026 SUTRAVYA · Assessment microsite</span><span>Event information is subject to official organiser updates.</span><a href="contact.html">Contact</a></div></div></footer>`;
}

function registrationState(now = Date.now()) {
  if (now < eventConfig.registrationOpensAt) return 'before';
  if (now > eventConfig.registrationClosesAt) return 'closed';
  return 'open';
}
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
    ? 'Public registration opens 1 November 2026 at 12:00 AM IST.'
    : state === 'open' ? 'Complete registration by 15 November 2026 at 11:59:59 PM IST.'
      : 'The registration period ended on 15 November 2026.';
  box.classList.toggle('countdown-closed', state === 'closed');
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
  let challengeId = '';
  let completed = false;
  let internalAccessCode = '';
  let challengeIsTeamPrelaunch = false;
  const internalHeaders = () => registrationState() === 'before' ? { 'X-Internal-Test-Code': internalAccessCode } : {};
  const showMessage = (message, isError = false) => {
    if (!note) return;
    note.textContent = message;
    note.classList.add('show');
    note.classList.toggle('error', isError);
  };
  const updateRegistrationWindow = () => {
    const state = registrationState();
    if (windowNote) {
      windowNote.classList.toggle('is-closed', state === 'closed');
      windowNote.classList.toggle('is-open', state === 'open');
      windowNote.textContent = state === 'before' ? 'Public registration opens 1 November 2026 at 12:00 AM IST.' : state === 'closed' ? 'Registration closed on 15 November 2026 at 11:59:59 PM IST.' : 'Registration is open until 15 November 2026 at 11:59:59 PM IST.';
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
