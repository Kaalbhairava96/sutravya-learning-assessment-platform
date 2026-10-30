const pages=[['index.html','Home'],['contact.html','Contact'],['login.html','Candidate sign-in']];
const configuredApiBase=document.querySelector('meta[name="sutravya-api-base"]')?.content.trim();
const apiBase=configuredApiBase||(['localhost','127.0.0.1'].includes(location.hostname)?'http://127.0.0.1:8000':'');
async function apiRequest(path,payload,method='POST',extraHeaders={}){if(!apiBase)throw new Error('Registration is not connected to the secure application yet. Please try again later.');const headers={...(payload?{'Content-Type':'application/json'}:{}),...extraHeaders};const response=await fetch(`${apiBase}${path}`,{method,credentials:'include',headers,body:payload?JSON.stringify(payload):undefined});let data={};try{data=await response.json();}catch{}if(!response.ok)throw new Error(data.detail||'The request could not be completed.');return data;}
const current=location.pathname.split('/').pop()||'index.html';
const enhancementStyles=document.createElement('link');enhancementStyles.rel='stylesheet';enhancementStyles.href='visuals.css';document.head.append(enhancementStyles);
const examStyles=document.createElement('link');examStyles.rel='stylesheet';examStyles.href='exam.css';document.head.append(examStyles);
const header=document.querySelector('[data-header]');
if(header){header.innerHTML=`<div class="topline"></div><div class="header"><div class="wrap headerin"><a class="brand" href="index.html" aria-label="Sutrāvya assessment home"><img src="assets/sutravya-logo.png" alt="Sutrāvya — The Digital Thread of Healthcare"></a><button class="navtoggle" aria-label="Open navigation" aria-expanded="false">☰ Menu</button><nav class="nav" aria-label="Main navigation">${pages.map(([url,label])=>`<a href="${url}" class="${url===current?'active':''}">${label}</a>`).join('')}<a class="navcta" href="index.html#register">Register now <span aria-hidden="true">→</span></a></nav></div></div>`;const toggle=header.querySelector('.navtoggle'),nav=header.querySelector('.nav');toggle.addEventListener('click',()=>{const open=nav.classList.toggle('open');toggle.setAttribute('aria-expanded',String(open));});}
const footer=document.querySelector('[data-footer]');
if(footer){footer.innerHTML=`<footer class="footer"><div class="wrap"><div class="footergrid"><div class="footerbrand"><a href="index.html"><img src="assets/sutravya-logo.png" alt="Sutrāvya"></a><p>SUTRĀVYA and QualiNova Assessment 2026 · Online MCQ assessments for three healthcare education streams.</p></div><div><h4>Candidate information</h4><div class="footerlinks"><a href="index.html#register">Registration</a><a href="contact.html">Contact</a><a href="https://sutravya.in" target="_blank" rel="noopener">sutravya.in ↗</a></div></div><div><h4>Assessment format</h4><div class="footerlinks"><span>4 December 2026</span><span>100 MCQs · 30 minutes</span><span>No negative marking</span><span>Exam access will be announced separately</span></div></div></div><div class="copyright"><span>© 2026 SUTRĀVYA · Assessment microsite</span><span>Organised by QualiNova</span></div></div></footer>`;}
const registrationOpensAt=Date.parse('2026-10-31T18:30:00.000Z');
const registrationClosesAt=Date.parse('2026-11-15T18:30:00.000Z');
function registrationWindowState(now=Date.now()){if(now<registrationOpensAt)return 'before';if(now>=registrationClosesAt)return 'closed';return 'open';}
document.querySelectorAll('[data-register-form]').forEach(form=>{
  const note=form.querySelector('.register-note');
  const windowNote=form.querySelector('[data-registration-window-note]');
  const otpStep=form.querySelector('[data-otp-step]');
  const resendBox=form.querySelector('[data-confirmation-resend]');
  const successBox=form.querySelector('[data-registration-success]');
  const otpInput=form.querySelector('#registration-otp');
  const startButton=form.querySelector('[data-start-registration]');
  const internalPanel=form.querySelector('[data-internal-testing-panel]');
  const internalCodeInput=form.querySelector('#internal-access-code');
  const internalFields=form.querySelector('[data-registration-fields]');
  const internalRecordLabel=form.querySelector('[data-internal-record-label]');
  const internalSuccess=form.querySelector('[data-internal-success]');
  let challengeId='';
  let completed=false;
  let internalAccessCode='';
  let challengeIsTeamPrelaunch=false;
  const internalHeaders=()=>registrationWindowState()==='before'?{'X-Internal-Test-Code':internalAccessCode}:{};
  const showMessage=(message,isError=false)=>{if(note){note.textContent=message;note.classList.add('show');note.classList.toggle('error',isError);}};
  const updateRegistrationWindow=()=>{
    const state=registrationWindowState();
    if(windowNote){windowNote.classList.toggle('is-closed',state==='closed');windowNote.textContent=state==='before'?'Official registration opens 1 November 2026 at 12:00 AM IST. Public registration is not open.':state==='closed'?'Registration closed.':'Registration is open until 15 November 2026 at 11:59:59 PM IST.';}
    const before=state==='before',closed=state==='closed';
    if(internalPanel)internalPanel.hidden=!before;
    if(internalFields)internalFields.hidden=before&&!internalAccessCode||closed;
    const unavailable=closed||(before&&!internalAccessCode);
    form.querySelectorAll('[data-registration-field]').forEach(field=>field.querySelectorAll('input,select,textarea').forEach(control=>{control.disabled=unavailable;}));
    if(startButton)startButton.disabled=unavailable||startButton.dataset.busy==='true';
    if(otpInput)otpInput.disabled=closed||(before&&!internalAccessCode);
    form.querySelectorAll('[data-otp-step] button').forEach(button=>{button.disabled=closed||(before&&!internalAccessCode)||button.dataset.busy==='true';});
    if(internalCodeInput)internalCodeInput.disabled=!before||closed;
    const unlock=form.querySelector('[data-unlock-internal]');if(unlock)unlock.disabled=!before||closed;
  };
  const markBusy=(busy)=>{form.querySelectorAll('button:not([data-copy-registration-id]):not([data-resend-confirmation])').forEach(button=>{button.dataset.busy=String(busy);button.disabled=busy;});if(!busy)updateRegistrationWindow();};
  updateRegistrationWindow();
  window.setInterval(updateRegistrationWindow,1000);
  form.querySelector('[data-unlock-internal]')?.addEventListener('click',()=>{
    const value=internalCodeInput?.value||'';
    if(!value){showMessage('Enter your internal team access code to continue.',true);internalCodeInput?.focus();return;}
    internalAccessCode=value;
    if(internalFields)internalFields.hidden=false;
    if(internalRecordLabel)internalRecordLabel.hidden=false;
    updateRegistrationWindow();
    showMessage('Team pre-launch access selected. The server will validate your code when you request the email code.');
  });
  internalCodeInput?.addEventListener('keydown',event=>{if(event.key==='Enter'){event.preventDefault();form.querySelector('[data-unlock-internal]')?.click();}});
  form.addEventListener('submit',async event=>{
    event.preventDefault();
    const windowState=registrationWindowState();
    if(windowState==='closed'||(windowState==='before'&&!internalAccessCode)){updateRegistrationWindow();return;}
    if(challengeId||completed)return;
    if(!form.reportValidity())return;
    markBusy(true);showMessage('Sending your email verification code…');
    try{
      challengeIsTeamPrelaunch=windowState==='before';
      const result=await apiRequest('/api/registrations/start',{
        full_name:form.elements.full_name.value,
        mobile:form.elements.mobile.value,
        email:form.elements.email.value,
        stream:form.elements.stream.value
      },'POST',internalHeaders());
      challengeId=result.challenge_id;
      if(!challengeId){showMessage(result.message||'If this email can be registered, a verification code will be sent.');return;}
      form.querySelectorAll('[data-registration-field]').forEach(field=>{field.hidden=true;});
      if(startButton)startButton.hidden=true;
      if(otpStep)otpStep.hidden=false;
      otpInput?.focus();
      showMessage('If delivery succeeds, enter the 6-digit code sent to your email.');
    }catch(error){showMessage(error.message,true);}
    finally{markBusy(false);}
  });
  form.querySelector('[data-verify-otp]')?.addEventListener('click',async()=>{
    const state=registrationWindowState();
    if(!challengeId||state==='closed'||(state==='before'&&!challengeIsTeamPrelaunch)){updateRegistrationWindow();return;}
    if(!otpInput?.reportValidity())return;
    markBusy(true);showMessage('Verifying your email and completing registration…');
    try{
      const result=await apiRequest('/api/registrations/verify-email',{challenge_id:challengeId,otp:otpInput.value},'POST',internalHeaders());
      completed=true;
      const registrationId=result.registration_id||'';
      form.querySelector('[data-registration-id]').textContent=registrationId;
      if(internalSuccess)internalSuccess.hidden=result.registration_source!=='team_prelaunch';
      form.querySelector('[data-confirmation-message]').textContent=result.confirmation_email_sent?'A confirmation email has been sent.':'Your registration is complete, but the confirmation email could not be sent. You can request it again below.';
      if(successBox)successBox.hidden=false;
      if(resendBox){resendBox.hidden=!registrationId;const idInput=resendBox.querySelector('input');if(idInput)idInput.value=registrationId;}
      if(otpStep)otpStep.hidden=true;
      challengeId='';
      showMessage('Registration saved successfully. Keep your Registration ID for your records.');
    }catch(error){showMessage(error.message,true);}
    finally{markBusy(false);}
  });
  form.querySelector('[data-copy-registration-id]')?.addEventListener('click',async()=>{
    const registrationId=form.querySelector('[data-registration-id]')?.textContent||'';
    if(!registrationId)return;
    try{await navigator.clipboard.writeText(registrationId);showMessage('Registration ID copied. Keep it safe.');}
    catch{showMessage('Copy is unavailable in this browser. Select and copy your Registration ID above.',true);}
  });
  form.querySelector('[data-resend-otp]')?.addEventListener('click',async()=>{
    const state=registrationWindowState();
    if(!challengeId||state==='closed'||(state==='before'&&!challengeIsTeamPrelaunch)){updateRegistrationWindow();return;}
    markBusy(true);showMessage('Requesting a new verification code…');
    try{const result=await apiRequest('/api/registrations/resend-otp',{challenge_id:challengeId},'POST',internalHeaders());challengeId=result.challenge_id;showMessage('A new code has been sent if delivery succeeds.');}
    catch(error){showMessage(error.message,true);}
    finally{markBusy(false);}
  });
  form.querySelector('[data-resend-confirmation]')?.addEventListener('click',async()=>{
    const registrationId=resendBox?.querySelector('input')?.value||'';
    markBusy(true);showMessage('Requesting the confirmation email…');
    try{const result=await apiRequest('/api/registrations/resend-confirmation',{registration_id:registrationId});showMessage(result.message);}
    catch(error){showMessage(error.message,true);}
    finally{markBusy(false);}
  });
});
document.querySelectorAll('[data-login-form]').forEach(form=>{
  const note=form.querySelector('.register-note');const otpStep=form.querySelector('[data-login-otp-step]');
  const resend=form.querySelector('[data-login-resend]');let requested=false;let resendTimer;
  const show=(message,error=false)=>{note.textContent=message;note.classList.add('show');note.classList.toggle('error',error);};
  const startCooldown=()=>{let remaining=60;resend.disabled=true;resend.textContent=`Resend code in ${remaining} seconds`;clearInterval(resendTimer);resendTimer=setInterval(()=>{remaining--;if(remaining<=0){clearInterval(resendTimer);resend.disabled=false;resend.textContent='Resend code';}else resend.textContent=`Resend code in ${remaining} seconds`;},1000);};
  const requestCode=async()=>{show('Requesting a sign-in code…');try{const result=await apiRequest('/api/auth/request-otp',{email:form.elements.email.value});requested=true;otpStep.hidden=false;form.querySelector('#login-otp')?.focus();startCooldown();show(result.message);}catch(error){show(error.message,true);}};
  form.addEventListener('submit',async event=>{event.preventDefault();if(requested)return;const button=form.querySelector('[type="submit"]');button.disabled=true;await requestCode();button.disabled=false;});
  resend?.addEventListener('click',async()=>{if(resend.disabled)return;await requestCode();});
  form.querySelector('[data-login-verify]')?.addEventListener('click',async()=>{const button=form.querySelector('[data-login-verify]');button.disabled=true;show('Verifying your code…');try{await apiRequest('/api/auth/verify-otp',{email:form.elements.email.value,otp:form.elements.otp.value});show('You are signed in. Your secure session will remain active across refreshes.');form.querySelectorAll('input,button').forEach(control=>control.disabled=true);}catch(error){show(error.message,true);}finally{button.disabled=false;}});
});
document.querySelectorAll('[data-sample]').forEach(group=>group.addEventListener('change',()=>{const q=group.closest('.sample-question');const answer=q.querySelector('.answer');if(answer)answer.classList.add('show');}));

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

document.querySelectorAll('.feature,.surface,.award-card,.topic,.faq,.contact-card').forEach((item,index)=>{item.classList.add('reveal-item');item.style.setProperty('--reveal-delay',`${Math.min(index%5,4)*65}ms`);});
if('IntersectionObserver' in window){const observer=new IntersectionObserver(entries=>entries.forEach(entry=>{if(entry.isIntersecting){entry.target.classList.add('is-visible');observer.unobserve(entry.target);}}),{threshold:.12});document.querySelectorAll('.reveal-item').forEach(item=>observer.observe(item));}else document.querySelectorAll('.reveal-item').forEach(item=>item.classList.add('is-visible'));
