/* QualiNova free candidate registration: application, review and email verification. */
(() => {
  const form = document.querySelector("#candidate-registration-form");
  if (!form) return;

  const apiBase = document.querySelector('meta[name="sutravya-api-base"]')?.content.trim()
    || (["localhost", "127.0.0.1"].includes(location.hostname) ? "http://127.0.0.1:8000" : "");
  const $ = selector => document.querySelector(selector);
  const category = $("#reg-category");
  const programme = $("#reg-programme");
  const year = $("#reg-year");
  const yearField = $("[data-year-field]");
  const academicStageField = $("[data-academic-stage-field]");
  const reviewPanel = $("[data-review-panel]");
  const otpPanel = $("[data-otp-panel]");
  const successPanel = $("[data-registration-success]");
  const gate = $("[data-registration-gate]");
  const alertBox = $("[data-register-alert]");
  const reviewAlert = $("[data-review-alert]");
  const otpAlert = $("[data-otp-alert]");
  const otpInput = $("#registration-otp");
  const reviewButton = $("[data-review-button]");
  const sendOtpButton = $("[data-review-send-otp]");
  const verifyButton = $("[data-verify-email]");
  const resendButton = $("[data-resend-otp]");
  const stateSelect = $("#reg-state");
  const districtSelect = $("#reg-district");
  const pinInput = $("#reg-pin");
  const duplicateEmailModal = $("[data-duplicate-email-modal]");
  const duplicateEmailClose = $("[data-duplicate-email-close]");
  const emailInput = $("#reg-email");
  const resendConfirmationButton = $("[data-resend-confirmation]");
  const successMessage = $("[data-registration-success-message]");

  const catalogue = {
    nursing: {label:"Nursing", programmes:[
      {id:"bsc_nursing",label:"B.Sc Nursing",years:[1,2,3,4]},
      {id:"msc_nursing",label:"M.Sc Nursing",years:[1,2]}
    ]},
    paramedical: {label:"Paramedical", programmes:[
      {id:"bmlt",label:"BMLT"},{id:"bott",label:"BOTT"},{id:"bhm",label:"BHM"},
      {id:"bopt",label:"B.Opt"},{id:"brit",label:"BRIT"}
    ]},
    pharmacy: {label:"Pharmacy", programmes:[
      {id:"dpharm",label:"D.Pharm",years:[1,2]},
      {id:"bpharm",label:"B.Pharm",years:[1,2,3,4]},
      {id:"pharmd",label:"Pharm.D",years:[1,2,3,4,5,6]},
      {id:"mpharm",label:"M.Pharm",years:[1,2]}
    ]}}
  };

  let registrationEnabled = false;
  let challengeId = null;
  let resendTimer = null;
  let details = null;
  let locationData = null;
  let completedRegistrationId = null;

  async function api(path, payload, method="POST") {
    if (!apiBase) throw new Error("The secure registration service is not configured.");
    const response = await fetch(apiBase + path, {
      method,
      credentials:"include",
      headers:payload ? {"Content-Type":"application/json"} : {},
      body:payload ? JSON.stringify(payload) : undefined
    });
    let data = {};
    try { data = await response.json(); } catch {}
    if (!response.ok) {
      const error = new Error(data.detail || "The request could not be completed. Please try again.");
      error.status = response.status;
      error.detail = data.detail || "";
      throw error;
    }
    return data;
  }

  function notice(node, message, error=false) {
    node.textContent = message;
    node.classList.toggle("is-error", error);
    node.classList.add("is-visible");
  }


  let validationAttempted = false;
  let pinLookupSequence = 0;
  let verifiedPinSignature = "";

  function validationWrapper(field) {
    return field.closest(".field, .registration-consent") || field.parentElement;
  }

  function showFieldMessage(field, message, state="error") {
    const wrapper = validationWrapper(field);
    if (!wrapper) return;
    wrapper.classList.toggle("has-validation-error", state === "error");
    wrapper.classList.toggle("has-validation-pending", state === "pending");
    field.setAttribute("aria-invalid", state === "error" ? "true" : "false");
    let node = field._validationMessageNode;
    if (!node) {
      node = document.createElement("small");
      node.className = "field-validation-message";
      if (field.type === "checkbox" && wrapper.classList.contains("registration-consent")) {
        wrapper.insertAdjacentElement("afterend", node);
      } else {
        wrapper.append(node);
      }
      field._validationMessageNode = node;
    }
    node.className = "field-validation-message" + (state === "pending" ? " is-pending" : "");
    node.textContent = message;
  }

  function clearFieldMessage(field) {
    const wrapper = validationWrapper(field);
    wrapper?.classList.remove("has-validation-error", "has-validation-pending");
    field.removeAttribute("aria-invalid");
    if (field._validationMessageNode) {
      field._validationMessageNode.remove();
      delete field._validationMessageNode;
    }
  }

  function validateField(field) {
    if (!field || field.disabled || field.type === "hidden" || field.closest("[hidden]")) {
      if (field) {
        field.setCustomValidity("");
        clearFieldMessage(field);
      }
      return true;
    }

    field.setCustomValidity("");
    const value = field.type === "checkbox" ? field.checked : String(field.value ?? "").trim();
    let message = "";

    if (field.required && field.type === "checkbox" && !value) {
      message = "Please accept the declaration to continue.";
    } else if (field.required && field.type !== "checkbox" && !value) {
      message = "This field is required.";
    } else if (field.name === "full_name" && value && value.length < 2) {
      message = "Enter your full name (at least 2 characters).";
    } else if (field.name === "mobile" && value && !/^[6-9][0-9]{9}$/.test(value)) {
      message = "Enter a valid 10-digit Indian mobile number.";
    } else if (field.name === "pin_code" && value && !/^[1-9][0-9]{5}$/.test(value)) {
      message = "Enter a valid 6-digit PIN code.";
    } else if (field.validity && !field.validity.valid) {
      if (field.validity.typeMismatch) message = "Enter a valid email address.";
      else if (field.validity.patternMismatch) message = "Enter a value in the required format.";
      else if (field.validity.tooLong) message = "This value is too long.";
      else if (field.validity.tooShort) message = "This value is too short.";
      else message = field.validationMessage || "Please check this field.";
    }

    if (message) {
      field.setCustomValidity(message);
      showFieldMessage(field, message);
      return false;
    }
    clearFieldMessage(field);
    return true;
  }

  function validateAllFields() {
    const controls = [...form.querySelectorAll("input, select, textarea")]
      .filter(field => field.type !== "hidden" && !field.disabled && !field.closest("[hidden]"));
    let firstInvalid = null;
    controls.forEach(field => {
      if (!validateField(field) && !firstInvalid) firstInvalid = field;
    });
    if (firstInvalid) {
      firstInvalid.focus();
      firstInvalid.scrollIntoView({behavior:"smooth", block:"center"});
      return false;
    }
    return true;
  }

  function invalidatePinValidation() {
    pinLookupSequence += 1;
    verifiedPinSignature = "";
    if (pinInput._validationMessageNode?.classList.contains("is-pending")) clearFieldMessage(pinInput);
  }

  async function checkPinAgainstLocation() {
    if (!validateField(pinInput)) return false;
    if (!stateSelect.value || !districtSelect.value) return false;

    const pin = pinInput.value.trim();
    const state = stateSelect.value;
    const district = districtSelect.value;
    const signature = [pin, state, district].join("|");
    if (verifiedPinSignature === signature) return true;

    const sequence = ++pinLookupSequence;
    showFieldMessage(pinInput, "Verifying PIN code against the selected district…", "pending");
    try {
      const result = await api("/api/registration/validate-pin", {
        pin_code:pin,
        state,
        district
      });
      if (sequence !== pinLookupSequence) return false;
      if (result.valid !== true) throw new Error(result.message || "PIN code does not match the selected address.");
      verifiedPinSignature = signature;
      clearFieldMessage(pinInput);
      return true;
    } catch (error) {
      if (sequence === pinLookupSequence) {
        showFieldMessage(pinInput, error.message || "PIN code could not be verified. Please check it and try again.");
      }
      return false;
    }
  }

  function populateStates() {
    stateSelect.replaceChildren(new Option("Choose State / UT", ""));
    locationData.states.forEach(state => {
      stateSelect.add(new Option(state.name, state.name));
    });
    stateSelect.disabled = false;
    populateDistricts("");
  }

  function populateDistricts(stateName) {
    districtSelect.replaceChildren(new Option(stateName ? "Choose district" : "Select State / UT first", ""));
    const selected = locationData?.states.find(state => state.name === stateName);
    (selected?.districts || []).forEach(district => {
      districtSelect.add(new Option(district, district));
    });
    districtSelect.disabled = !selected;
  }

  function showDuplicateEmailPopup() {
    if (!duplicateEmailModal) return;
    duplicateEmailModal.hidden = false;
    document.body.classList.add("registration-modal-open");
    duplicateEmailClose.focus();
  }

  function closeDuplicateEmailPopup() {
    if (!duplicateEmailModal) return;
    duplicateEmailModal.hidden = true;
    document.body.classList.remove("registration-modal-open");
    reviewPanel.hidden = true;
    otpPanel.hidden = true;
    successPanel.hidden = true;
    form.hidden = false;
    setStep(1);
    emailInput.focus();
    emailInput.select();
  }

  function setStep(active) {
    document.querySelectorAll("[data-step-indicator]").forEach(node => {
      const number = Number(node.dataset.stepIndicator);
      node.classList.toggle("is-current", number === active);
      node.classList.toggle("is-complete", number < active);
    });
  }

  function refreshAcademicFields() {
    const item = catalogue[category.value];
    const selected = item?.programmes.find(option => option.id === programme.value);
    const isParamedical = category.value === "paramedical";
    const stage = $("#reg-academic-stage");
    const hasYear = Boolean(selected?.years?.length);

    yearField.hidden = !hasYear;
    year.required = hasYear;
    year.disabled = !hasYear;
    academicStageField.hidden = !isParamedical;
    stage.required = isParamedical;
    stage.disabled = !isParamedical;
    year.replaceChildren(new Option("Select year", ""));
    (selected?.years || []).forEach(value => year.add(new Option("Year " + value, String(value))));
  }

  function refreshProgrammes() {
    const item = catalogue[category.value];
    programme.replaceChildren(new Option(item ? "Select programme" : "Select category first", ""));
    (item?.programmes || []).forEach(option => programme.add(new Option(option.label, option.id)));
    programme.disabled = !item;
    refreshAcademicFields();
  }

  function collect() {
    const item = catalogue[category.value];
    const selected = item.programmes.find(option => option.id === programme.value);
    const yearValue = year.value ? Number(year.value) : null;
    const stream = category.value;

    return {
      payload: {
        full_name:form.elements.full_name.value.trim(),
        email:form.elements.email.value.trim(),
        mobile:form.elements.mobile.value.trim(),
        category:category.value,
        programme:programme.value,
        stream,
        year:yearValue,
        declaration_accepted:form.elements.consent.checked,
        academic_stage:category.value === "paramedical" ? form.elements.academic_stage.value.trim() : null,
        house_number:form.elements.house_number.value.trim(),
        address_line1:form.elements.address_line1.value.trim(),
        address_line2:form.elements.address_line2.value.trim(),
        district:form.elements.district.value.trim(),
        state:form.elements.state.value.trim(),
        pin_code:form.elements.pin_code.value.trim()
      },
      category_label:item.label,
      programme_label:selected?.label || "",
      academic_label:yearValue ? "Year " + yearValue : form.elements.academic_stage.value.trim()
    };
  }

  function addReviewRow(parent, label, value) {
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = value || "—";
    parent.append(dt, dd);
  }

  function makeReview(data) {
    const payload = data.payload;
    const list = $("[data-review-list]");
    list.replaceChildren();
    addReviewRow(list, "Registration category", data.category_label);
    addReviewRow(list, "Programme / course", data.programme_label);
    addReviewRow(list, "Academic year / stage", data.academic_label);
    addReviewRow(list, "Full name", payload.full_name);
    addReviewRow(list, "Email", payload.email);
    addReviewRow(list, "Mobile", payload.mobile);
    addReviewRow(list, "House / flat", payload.house_number);
    addReviewRow(list, "Address line 1", payload.address_line1);
    addReviewRow(list, "Address line 2", payload.address_line2 || "—");
    addReviewRow(list, "District", payload.district);
    addReviewRow(list, "State", payload.state);
    addReviewRow(list, "PIN code", payload.pin_code);
  }

  function startResendCooldown() {
    let seconds = 60;
    resendButton.disabled = true;
    resendButton.textContent = "Resend code in " + seconds + " seconds";
    clearInterval(resendTimer);
    resendTimer = setInterval(() => {
      seconds--;
      if (seconds <= 0) {
        clearInterval(resendTimer);
        resendButton.disabled = false;
        resendButton.textContent = "Resend verification code";
      } else {
        resendButton.textContent = "Resend code in " + seconds + " seconds";
      }
    }, 1000);
  }

  async function initialise() {
    try {
      const [config, locationResponse] = await Promise.all([
        api("/api/registration/config", undefined, "GET"),
        fetch("assets/india-states-districts.json", {cache:"force-cache"})
      ]);
      if (!locationResponse.ok) throw new Error("State and district list could not be loaded. Please refresh the page.");
      locationData = await locationResponse.json();
      if (!Array.isArray(locationData.states) || locationData.states.length !== 36) {
        throw new Error("The State / UT list is incomplete. Please refresh the page.");
      }
      populateStates();
      registrationEnabled = config.registration_enabled === true;
      if (Array.isArray(config.categories)) {
        config.categories.forEach(row => {
          if (!catalogue[row.id]) return;
          catalogue[row.id].label = row.label;
          catalogue[row.id].programmes = row.programmes || catalogue[row.id].programmes;
        });
      }
      if (registrationEnabled) {
        $("[data-gate-title]").textContent = "Registration is open";
        $("[data-gate-copy]").textContent = "Complete the application and verify your email to confirm your free registration.";
        gate.classList.add("is-open");
        reviewButton.disabled = false;
      } else {
        $("[data-gate-title]").textContent = "Registration is not open";
        $("[data-gate-copy]").textContent = "The organiser's registration window is currently closed or has not yet opened.";
        gate.classList.add("is-paused");
        reviewButton.disabled = true;
      }
      refreshProgrammes();
    } catch (error) {
      $("[data-gate-title]").textContent = "Registration service unavailable";
      $("[data-gate-copy]").textContent = error.message;
      gate.classList.add("is-paused");
      reviewButton.disabled = true;
    }
  }

  category.addEventListener("change", refreshProgrammes);
  programme.addEventListener("change", refreshAcademicFields);
  stateSelect.addEventListener("change", () => {
    populateDistricts(stateSelect.value);
    invalidatePinValidation();
    if (validationAttempted) {
      validateField(stateSelect);
      validateField(districtSelect);
    }
  });
  districtSelect.addEventListener("change", () => {
    invalidatePinValidation();
    if (validationAttempted) validateField(districtSelect);
    if (/^[1-9][0-9]{5}$/.test(pinInput.value.trim()) && stateSelect.value && districtSelect.value) {
      checkPinAgainstLocation();
    }
  });
  pinInput.addEventListener("input", () => {
    invalidatePinValidation();
    if (validationAttempted || pinInput.getAttribute("aria-invalid") === "true") validateField(pinInput);
  });
  pinInput.addEventListener("blur", () => {
    if (validateField(pinInput) && stateSelect.value && districtSelect.value) checkPinAgainstLocation();
  });
  form.querySelectorAll("input, select, textarea").forEach(field => {
    field.addEventListener("blur", () => validateField(field));
    field.addEventListener("input", () => {
      if (field !== pinInput && (validationAttempted || field.getAttribute("aria-invalid") === "true")) validateField(field);
    });
    field.addEventListener("change", () => {
      if (field !== stateSelect && field !== districtSelect && field !== pinInput && (validationAttempted || field.getAttribute("aria-invalid") === "true")) validateField(field);
    });
  });

  let emailCheckSequence = 0;
  emailInput.addEventListener("blur", async () => {
    const email = emailInput.value.trim();
    if (!registrationEnabled || !email || !emailInput.validity.valid) return;
    const sequence = ++emailCheckSequence;
    try {
      const result = await api("/api/registrations/check-email", {email});
      if (
        sequence === emailCheckSequence
        && emailInput.value.trim() === email
        && result.already_registered === true
      ) {
        showDuplicateEmailPopup();
      }
    } catch {
      // The final registration-start endpoint performs the authoritative check.
    }
  });
  duplicateEmailClose.addEventListener("click", closeDuplicateEmailPopup);
  duplicateEmailModal.addEventListener("click", event => {
    if (event.target === duplicateEmailModal) closeDuplicateEmailPopup();
  });
  document.addEventListener("keydown", event => {
    if (event.key === "Escape" && duplicateEmailModal && !duplicateEmailModal.hidden) closeDuplicateEmailPopup();
  });

  form.addEventListener("submit", async event => {
    event.preventDefault();
    alertBox.classList.remove("is-visible", "is-error");
    if (!registrationEnabled) {
      notice(alertBox, "Registration is not open. Your details have not been submitted.", true);
      return;
    }
    validationAttempted = true;
    if (!validateAllFields()) {
      notice(alertBox, "Please correct the highlighted fields before continuing.", true);
      return;
    }

    reviewButton.disabled = true;
    reviewButton.setAttribute("aria-busy", "true");
    const originalButtonText = reviewButton.textContent;
    reviewButton.textContent = "Verifying address…";
    try {
      const pinIsValid = await checkPinAgainstLocation();
      if (!pinIsValid) {
        notice(alertBox, pinInput._validationMessageNode?.textContent || "Please verify the PIN code and selected address.", true);
        pinInput.focus();
        pinInput.scrollIntoView({behavior:"smooth", block:"center"});
        return;
      }
      details = collect();
      makeReview(details);
      form.hidden = true;
      reviewPanel.hidden = false;
      setStep(2);
      reviewPanel.scrollIntoView({behavior:"smooth",block:"start"});
    } finally {
      reviewButton.disabled = !registrationEnabled;
      reviewButton.removeAttribute("aria-busy");
      reviewButton.textContent = originalButtonText;
    }
  });

  $("[data-review-back]").addEventListener("click", () => {
    reviewPanel.hidden = true;
    form.hidden = false;
    setStep(1);
    form.scrollIntoView({behavior:"smooth",block:"start"});
  });

  sendOtpButton.addEventListener("click", async () => {
    reviewAlert.classList.remove("is-visible", "is-error");
    if (!details) return;
    sendOtpButton.disabled = true;
    sendOtpButton.textContent = "Sending verification code…";
    try {
      const result = await api("/api/registrations/start", details.payload);
      if (!result.challenge_id) throw new Error(result.message || "A verification code could not be requested.");
      challengeId = result.challenge_id;
      $("[data-otp-email]").textContent = details.payload.email;
      reviewPanel.hidden = true;
      otpPanel.hidden = false;
      setStep(3);
      otpInput.focus();
      startResendCooldown();
      otpPanel.scrollIntoView({behavior:"smooth",block:"start"});
    } catch (error) {
      if (error.status === 409 && /already registered/i.test(error.message)) {
        showDuplicateEmailPopup();
      } else {
        notice(reviewAlert, error.message, true);
      }
    } finally {
      sendOtpButton.disabled = false;
      sendOtpButton.textContent = "Confirm & send email code →";
    }
  });

  verifyButton.addEventListener("click", async () => {
    otpAlert.classList.remove("is-visible", "is-error");
    if (!challengeId || !otpInput.reportValidity()) return;
    verifyButton.disabled = true;
    verifyButton.textContent = "Verifying email…";
    try {
      const result = await api("/api/registrations/verify-email", {
        challenge_id:challengeId,
        otp:otpInput.value.trim()
      });
      if (result.candidate_session_established !== true || !result.registration_id || result.registration_status !== "active") {
        throw new Error("Email verification could not complete your registration. Please contact the organiser.");
      }
      completedRegistrationId = result.registration_id;
      $("[data-registration-id]").textContent = result.registration_id;
      $("[data-success-category]").textContent = details.category_label;
      $("[data-success-programme]").textContent = details.programme_label;
      successMessage.textContent = result.confirmation_email_sent
        ? "Your registration is complete and your Registration ID is saved. A confirmation email has been submitted to your verified inbox."
        : "Your registration is complete and your Registration ID is saved. The confirmation email could not be sent yet. Use the retry button below.";
      successMessage.classList.toggle("is-error", !result.confirmation_email_sent);
      resendConfirmationButton.hidden = result.confirmation_email_sent;
      otpPanel.hidden = true;
      successPanel.hidden = false;
      setStep(4);
      successPanel.scrollIntoView({behavior:"smooth",block:"start"});
    } catch (error) {
      notice(otpAlert, error.message, true);
    } finally {
      verifyButton.disabled = false;
      verifyButton.textContent = "Verify email and complete free registration →";
    }
  });

  resendConfirmationButton.addEventListener("click", async () => {
    if (!completedRegistrationId || resendConfirmationButton.disabled) return;
    resendConfirmationButton.disabled = true;
    resendConfirmationButton.textContent = "Sending confirmation email…";
    try {
      const result = await api("/api/registrations/resend-confirmation", {
        registration_id:completedRegistrationId
      });
      if (result.confirmation_email_sent) {
        successMessage.textContent = "Your registration confirmation email has been sent. Please check your inbox and spam folder.";
        successMessage.classList.remove("is-error");
        resendConfirmationButton.hidden = true;
      } else {
        successMessage.textContent = result.message || "The confirmation email could not be sent. Please try again later.";
        successMessage.classList.add("is-error");
      }
    } catch (error) {
      successMessage.textContent = error.message;
      successMessage.classList.add("is-error");
    } finally {
      resendConfirmationButton.disabled = false;
      resendConfirmationButton.textContent = "Resend registration confirmation email";
    }
  });

  resendButton.addEventListener("click", async () => {
    if (!challengeId || resendButton.disabled) return;
    resendButton.disabled = true;
    try {
      const result = await api("/api/registrations/resend-otp", {challenge_id:challengeId});
      challengeId = result.challenge_id;
      notice(otpAlert, "A new verification code has been sent.");
      startResendCooldown();
    } catch (error) {
      notice(otpAlert, error.message, true);
      resendButton.disabled = false;
      resendButton.textContent = "Resend verification code";
    }
  });

  initialise();
})();
