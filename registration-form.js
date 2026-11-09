(() => {
const form=document.getElementById('htse-registration-form');
if(!form)return;
const fees={nursing:250,paramedical:250,mbbs:500,jdn:1000};
const labels={nursing:'Nursing',paramedical:'Paramedical',mbbs:'MBBS',jdn:'Junior Doctor Network (JDN)'};
const programmes={nursing:['B.Sc Nursing','M.Sc Nursing'],paramedical:['BMLT','BOTT','BHM','B.Opt','BRIT'],mbbs:['MBBS'],jdn:['Junior Doctor Network']};
const years={nursing:['1st Year','2nd Year','3rd Year','4th Year'],paramedical:['1st Year','2nd Year','3rd Year','4th Year'],mbbs:['1st Year','2nd Year','3rd Year','4th Year','5th Year']};
const states=['Andhra Pradesh','Arunachal Pradesh','Assam','Bihar','Chhattisgarh','Goa','Gujarat','Haryana','Himachal Pradesh','Jharkhand','Karnataka','Kerala','Madhya Pradesh','Maharashtra','Manipur','Meghalaya','Mizoram','Nagaland','Odisha','Punjab','Rajasthan','Sikkim','Tamil Nadu','Telangana','Tripura','Uttar Pradesh','Uttarakhand','West Bengal','Andaman and Nicobar Islands','Chandigarh','Dadra and Nagar Haveli and Daman and Diu','Delhi','Jammu and Kashmir','Ladakh','Lakshadweep','Puducherry'];
['state','institution-state'].forEach(id=>{const el=document.getElementById(id);states.forEach(s=>el.add(new Option(s,s)));});
const categoryInputs=[...form.querySelectorAll('input[name="category"]')];
const programme=document.getElementById('programme'),year=document.getElementById('academic-year');
const programmeFields=document.getElementById('programme-fields'),yearWrap=document.getElementById('year-wrap'),jdnFields=document.getElementById('jdn-fields'),jdnStatus=document.getElementById('jdn-status');
const feeCategory=document.getElementById('fee-category'),feeAmount=document.getElementById('fee-amount'),feeNote=document.getElementById('fee-note');
function setOptions(el,items,placeholder){el.innerHTML='';el.add(new Option(placeholder,''));items.forEach(v=>el.add(new Option(v,v)));el.disabled=!items.length;el.required=items.length>0;}
function updateCategory(){
 const c=categoryInputs.find(x=>x.checked)?.value||'';
 programmeFields.hidden=!c;programmeFields.querySelectorAll('select').forEach(x=>x.disabled=!c);
 jdnFields.hidden=c!=='jdn';jdnStatus.disabled=c!=='jdn';jdnStatus.required=c==='jdn';
 setOptions(programme,programmes[c]||[],'Select programme');
 const showYear=!!c&&c!=='jdn';yearWrap.hidden=!showYear;setOptions(year,years[c]||[],'Select year');
 feeCategory.textContent=c?labels[c]:'Not selected';feeAmount.textContent=c?'₹'+fees[c].toLocaleString('en-IN'):'₹0';
 feeNote.textContent=c?'Applicable registration fee for '+labels[c]+'. Payment collection will be enabled after gateway integration.':'Choose a registration category above to view the applicable fee.';
 form.dataset.selectedFee=c?String(fees[c]):'';
}
categoryInputs.forEach(x=>x.addEventListener('change',updateCategory));
programme.addEventListener('change',()=>{const c=categoryInputs.find(x=>x.checked)?.value;let options=years[c]||[];if(c==='nursing'&&programme.value==='M.Sc Nursing')options=['1st Year','2nd Year'];setOptions(year,options,'Select year');});
const message=document.getElementById('form-message');
form.addEventListener('submit',e=>{
 e.preventDefault();message.className='rf-form-message';message.textContent='';
 if(!form.reportValidity()){message.textContent='Please complete all required fields and review the highlighted information.';message.classList.add('show','error');return;}
 const c=categoryInputs.find(x=>x.checked)?.value;
 if(!c){message.textContent='Please select a registration category.';message.classList.add('show','error');return;}
 const data=Object.fromEntries(new FormData(form).entries());
 data.registration_fee_inr=fees[c];data.registration_category=labels[c];
 const summary=['Registration category: '+labels[c],'Programme: '+(data.programme||'—'),'Academic year: '+(data.academic_year||'—'),'Candidate: '+data.full_name,'Email: '+data.email,'Mobile: +91 '+data.mobile,'Institution: '+data.institution_name,'Registration fee: ₹'+fees[c].toLocaleString('en-IN')];
 message.innerHTML='<strong>Form validation successful.</strong><br>'+summary.map(x=>x.replace(/[&<>"]/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[ch]))).join('<br>')+'<br><br><b>Note:</b> This is a form preview only. Registration submission, OTP verification and payment are not connected yet.';
 message.classList.add('show');
 message.scrollIntoView({behavior:'smooth',block:'nearest'});
});
updateCategory();
})();