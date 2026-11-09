/* QualiNova four-category application flow. Fees, status and payments are server-authoritative. */
(() => {
  const form = document.querySelector('#candidate-registration-form');
  if (!form) return;
  const apiBase = document.querySelector('meta[name="sutravya-api-base"]')?.content.trim()
    || (['localhost', '127.0.0.1'].includes(location.hostname) ? 'http://127.0.0.1:8000' : '');
  const $ = selector => document.querySelector(selector);
  const category = $('#reg-category');
  const programme = $('#reg-programme');
  const year = $('#reg-year');
  const yearField = $('[data-year-field]');
  const academicStageField = $('[data-academic-stage-field]');
  const jdnFields = [...document.querySelectorAll('[data-jdn-field]')];
  const reviewPanel = $('[data-review-panel]');
  const otpPanel = $('[data-otp-panel]');
  const paymentPanel = $('[data-payment-panel]');
  const gate = $('[data-registration-gate]');
  const feeAmount = $('[data-fee-amount]');
  const feeCategory = $('[data-fee-category]');
  const feeDescription = $('[data-fee-description]');
  const alertBox = $('[data-register-alert]');
  const reviewAlert = $('[data-review-alert]');
  const otpAlert = $('[data-otp-alert]');
  const otpInput = $('#registration-otp');
  const reviewButton = $('[data-review-button]');
  const sendOtpButton = $('[data-review-send-otp]');
  const verifyButton = $('[data-verify-email]');
  const resendButton = $('[data-resend-otp]');
  const continuePayment = $('[data-continue-payment]');

  const catalogue = {
    nursing: {label:'Nursing', fee:25000, programmes:[
      {id:'bsc_nursing',label:'B.Sc Nursing',years:[1,2,3,4]},
      {id:'msc_nursing',label:'M.Sc Nursing',years:[1,2]}
    ]},
    paramedical: {label:'Paramedical', fee:25000, programmes:[
      {id:'bmlt',label:'BMLT'},{id:'bott',label:'BOTT'},{id:'bhm',label:'BHM'},
      {id:'bopt',label:'B.Opt'},{id:'brit',label:'BRIT'}
    ]},
    mbbs: {label:'MBBS', fee:50000, programmes:[{id:'mbbs',label:'MBBS',years:[1,2,3,4,5]}]},
    jdn: {label:'Junior Doctor Network (JDN)', fee:100000, programmes:[
      {id:'junior_doctor_network',label:'Junior Doctor Network'}
    ]}
  };
  let registrationEnabled = false;
  let paymentEnabled = false;
  let challengeId = null;
  let resendTimer = null;
  let details = null;

  const money = paise => new Intl.NumberFormat('en-IN',{
    style:'currency',currency:'INR',maximumFractionDigits:0
  }).format(paise / 100);
  async function api(path,payload,method='POST') {
    if (!apiBase) throw new Error('The secure registration API is not configured.');
    const response=await fetch(apiBase+path,{
      method,credentials:'include',
      headers:payload ? {'Content-Type':'application/json'} : {},
      body:payload ? JSON.stringify(payload) : undefined
    });
    let data={};
    try { data=await response.json(); } catch {}
    if (!response.ok) throw new Error(data.detail || 'The request could not be completed. Please try again.');
    return data;
  }
  function notice(node,message,error=false) {
    node.textContent=message;
    node.classList.toggle('is-error',error);
    node.classList.add('is-visible');
  }
  function setStep(active) {
    document.querySelectorAll('[data-step-indicator]').forEach(node=>{
      const n=Number(node.dataset.stepIndicator);
      node.classList.toggle('is-current',n===active);
      node.classList.toggle('is-complete',n<active);
    });
  }
  function addOption(select,label,value) { select.add(new Option(label,value)); }
  function setJdnFields(visible) {
    jdnFields.forEach(node=>{
      node.hidden=!visible;
      const control=node.querySelector('input');
      if(control){control.disabled=!visible;control.required=visible && !['reg-council','reg-council-number','reg-experience'].includes(control.id);}
    });
  }
  function refreshAcademicFields() {
    const item=catalogue[category.value];
    const selected=item?.programmes.find(p=>p.id===programme.value);
    const isParamedical=category.value==='paramedical';
    const isJdn=category.value==='jdn';
    const stage=$('#reg-academic-stage');
    yearField.hidden=!selected?.years?.length;
    year.required=Boolean(selected?.years?.length);
    year.disabled=!selected?.years?.length;
    academicStageField.hidden=!isParamedical;
    stage.required=isParamedical;
    stage.disabled=!isParamedical;
    setJdnFields(isJdn);
    year.replaceChildren(new Option('Select year',''));
    (selected?.years || []).forEach(n=>addOption(year,'Year '+n,String(n)));
    feeAmount.textContent=item ? money(item.fee) : 'Choose a category';
    feeCategory.textContent=item?.label || 'Not selected';
    feeDescription.textContent=item
      ? 'The registration server validates the applicable fee before saving your application.'
      : 'The fee is calculated by the server for your selected category.';
  }
  function refreshProgrammes() {
    const item=catalogue[category.value];
    programme.replaceChildren(new Option(item ? 'Select programme' : 'Select category first',''));
    (item?.programmes || []).forEach(p=>addOption(programme,p.label,p.id));
    programme.disabled=!item;
    refreshAcademicFields();
  }
  function collect() {
    const item=catalogue[category.value];
    const selected=item.programmes.find(p=>p.id===programme.value);
    const yearValue=year.value ? Number(year.value) : null;
    const stream={nursing:'nursing',paramedical:'paramedical',mbbs:'mbbs_1st_year',jdn:'jdn'}[category.value];
    return {
      full_name:form.elements.full_name.value.trim(),
      email:form.elements.email.value.trim(),
      mobile:form.elements.mobile.value.trim(),
      category:category.value, programme:programme.value, stream, year:yearValue,
      declaration_accepted:form.elements.consent.checked,
      academic_stage:category.value==='paramedical' ? form.elements.academic_stage.value.trim() : null,
      professional_qualification:category.value==='jdn' ? form.elements.professional_qualification.value.trim() : null,
      designation:category.value==='jdn' ? form.elements.designation.value.trim() : null,
      institution:category.value==='jdn' ? form.elements.institution.value.trim() : null,
      council_name:category.value==='jdn' ? form.elements.council_name.value.trim() : null,
      council_registration_number:category.value==='jdn' ? form.elements.council_registration_number.value.trim() : null,
      years_of_experience:category.value==='jdn' ? form.elements.years_of_experience.value.trim() : null,
      house_number:form.elements.house_number.value.trim(),
      address_line1:form.elements.address_line1.value.trim(),
      address_line2:form.elements.address_line2.value.trim(),
      district:form.elements.district.value.trim(),state:form.elements.state.value.trim(),
      pin_code:form.elements.pin_code.value.trim(),
      programme_label:selected?.label || '',category_label:item.label,fee_paise:item.fee
    };
  }
  function addReviewRow(parent,label,value) {
    const dt=document.createElement('dt');dt.textContent=label;
    const dd=document.createElement('dd');dd.textContent=value || '—';
    parent.append(dt,dd);
  }
  function makeReview(data) {
    const list=$('[data-review-list]');
    list.replaceChildren();
    addReviewRow(list,'Registration category',data.category_label);
    addReviewRow(list,'Programme / course',data.programme_label);
    addReviewRow(list,'Academic year / stage',data.year ? 'Year '+data.year : data.academic_stage || 'Professional network');
    if(data.category==='jdn') {
      addReviewRow(list,'Professional qualification',data.professional_qualification);
      addReviewRow(list,'Role / designation',data.designation);
      addReviewRow(list,'Hospital / institution',data.institution);
      addReviewRow(list,'Medical council',data.council_name || 'Not provided');
      addReviewRow(list,'Council registration number',data.council_registration_number || 'Not provided');
      addReviewRow(list,'Experience',data.years_of_experience || 'Not provided');
    }
    addReviewRow(list,'Full name',data.full_name);
    addReviewRow(list,'Email',data.email);
    addReviewRow(list,'Mobile',data.mobile);
    addReviewRow(list,'House / flat',data.house_number);
    addReviewRow(list,'Address line 1',data.address_line1);
    addReviewRow(list,'Address line 2',data.address_line2 || '—');
    addReviewRow(list,'District',data.district);
    addReviewRow(list,'State',data.state);
    addReviewRow(list,'PIN code',data.pin_code);
    $('[data-review-fee]').textContent=money(data.fee_paise);
    $('[data-review-category]').textContent=data.category_label;
  }
  function startResendCooldown() {
    let seconds=60;
    resendButton.disabled=true;
    resendButton.textContent='Resend code in '+seconds+' seconds';
    clearInterval(resendTimer);
    resendTimer=setInterval(()=>{
      seconds--;
      if(seconds<=0){clearInterval(resendTimer);resendButton.disabled=false;resendButton.textContent='Resend verification code';}
      else resendButton.textContent='Resend code in '+seconds+' seconds';
    },1000);
  }
  async function initialise() {
    try {
      const config=await api('/api/registration/config',undefined,'GET');
      registrationEnabled=config.registration_enabled===true;
      paymentEnabled=config.payment?.enabled===true;
      if(Array.isArray(config.categories)) config.categories.forEach(row=>{
        if(!catalogue[row.id]) return;
        catalogue[row.id].fee=row.fee_paise;
        catalogue[row.id].label=row.label;
        catalogue[row.id].programmes=row.programmes || catalogue[row.id].programmes;
      });
      if(registrationEnabled) {
        $('[data-gate-title]').textContent='Registration is open';
        $('[data-gate-copy]').textContent='Complete the application, review your details and verify your email.';
        gate.classList.add('is-open');reviewButton.disabled=false;
      } else {
        $('[data-gate-title]').textContent='Registration is not open';
        $('[data-gate-copy]').textContent='The registration window is closed or has not yet been opened by the organiser.';
        gate.classList.add('is-paused');reviewButton.disabled=true;
      }
      continuePayment.disabled=!paymentEnabled;
      continuePayment.textContent=paymentEnabled?'Continue to secure payment':'Secure payment setup pending';
      refreshProgrammes();
    } catch(error) {
      $('[data-gate-title]').textContent='Registration service unavailable';
      $('[data-gate-copy]').textContent=error.message;
      gate.classList.add('is-paused');reviewButton.disabled=true;
    }
  }
  category.addEventListener('change',refreshProgrammes);
  programme.addEventListener('change',refreshAcademicFields);
  form.addEventListener('submit',event=>{
    event.preventDefault();alertBox.classList.remove('is-visible','is-error');
    if(!registrationEnabled){notice(alertBox,'Registration is not open. Your details have not been submitted.',true);return;}
    if(!form.reportValidity())return;
    details=collect();makeReview(details);form.hidden=true;reviewPanel.hidden=false;setStep(2);
    reviewPanel.scrollIntoView({behavior:'smooth',block:'start'});
  });
  $('[data-review-back]').addEventListener('click',()=>{
    reviewPanel.hidden=true;form.hidden=false;setStep(1);form.scrollIntoView({behavior:'smooth',block:'start'});
  });
  sendOtpButton.addEventListener('click',async()=>{
    reviewAlert.classList.remove('is-visible','is-error');
    if(!details)return;
    sendOtpButton.disabled=true;sendOtpButton.textContent='Sending verification code…';
    try {
      const payload={...details};
      delete payload.category_label;delete payload.programme_label;delete payload.fee_paise;
      const result=await api('/api/registrations/start',payload);
      if(!result.challenge_id)throw new Error(result.message || 'A verification code could not be requested.');
      challengeId=result.challenge_id;
      $('[data-otp-email]').textContent=details.email;
      reviewPanel.hidden=true;otpPanel.hidden=false;setStep(3);otpInput.focus();startResendCooldown();
      otpPanel.scrollIntoView({behavior:'smooth',block:'start'});
    } catch(error){notice(reviewAlert,error.message,true);}
    finally{sendOtpButton.disabled=false;sendOtpButton.textContent='Confirm & send email code →';}
  });
  verifyButton.addEventListener('click',async()=>{
    otpAlert.classList.remove('is-visible','is-error');
    if(!challengeId || !otpInput.reportValidity())return;
    verifyButton.disabled=true;verifyButton.textContent='Verifying email…';
    try {
      const result=await api('/api/registrations/verify-email',{challenge_id:challengeId,otp:otpInput.value.trim()});
      if(result.candidate_session_established!==true)throw new Error('Email verified, but a secure candidate session could not be established. Please sign in.');
      if(result.registration_status!=='payment_pending' || result.payment_status!=='pending')throw new Error('Unexpected application status. Contact the organiser before proceeding.');
      paymentEnabled=result.payment_enabled===true;
      $('[data-payment-category]').textContent=details.category_label;
      $('[data-payment-programme]').textContent=details.programme_label;
      $('[data-payment-amount]').textContent=money(result.amount_paise);
      $('[data-payment-message]').textContent='No payment has been collected. Your email-verified application is saved as Payment Pending. A Registration ID and exam eligibility will follow only after secure payment verification.';
      continuePayment.disabled=!paymentEnabled;
      continuePayment.textContent=paymentEnabled?'Continue to secure payment':'Secure payment setup pending';
      otpPanel.hidden=true;paymentPanel.hidden=false;setStep(4);
      paymentPanel.scrollIntoView({behavior:'smooth',block:'start'});
    } catch(error){notice(otpAlert,error.message,true);}
    finally{verifyButton.disabled=false;verifyButton.textContent='Verify email and save application →';}
  });
  resendButton.addEventListener('click',async()=>{
    if(!challengeId || resendButton.disabled)return;
    resendButton.disabled=true;
    try {
      const result=await api('/api/registrations/resend-otp',{challenge_id:challengeId});
      challengeId=result.challenge_id;notice(otpAlert,'A new verification code has been sent.');startResendCooldown();
    } catch(error){notice(otpAlert,error.message,true);resendButton.disabled=false;resendButton.textContent='Resend verification code';}
  });
  continuePayment.addEventListener('click',async()=>{
    if(!paymentEnabled)return;
    continuePayment.disabled=true;continuePayment.textContent='Connecting to checkout…';
    try {
      const result=await api('/api/payments/create-order',{});
      if(result.checkout_url)location.assign(result.checkout_url);
      else notice($('[data-payment-message]'),'Payment order created. Checkout details are being prepared.');
    } catch(error){notice($('[data-payment-message]'),error.message,true);}
    finally{continuePayment.disabled=!paymentEnabled;continuePayment.textContent=paymentEnabled?'Continue to secure payment':'Secure payment setup pending';}
  });
  initialise();
})();
