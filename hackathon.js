/* Healthcare Innovation Hackathon registration and participant portal. */
(() => {
  'use strict';
  const $ = (selector, root = document) => root.querySelector(selector);
  const api = (path, payload, method = 'POST') => apiRequest(path, payload, method);
  const setMessage = (node, message, error = false) => {
    if (!node) return;
    node.textContent = message || '';
    node.classList.toggle('is-error', Boolean(error));
    node.classList.toggle('is-visible', Boolean(message));
  };
  const setBusy = (button, busy, label) => {
    if (!button) return;
    if (busy) {
      button.dataset.originalLabel = button.innerHTML;
      button.disabled = true;
      button.textContent = label;
    } else {
      button.disabled = false;
      if (button.dataset.originalLabel) {
        button.innerHTML = button.dataset.originalLabel;
        delete button.dataset.originalLabel;
      }
    }
  };

  const registrationForm = $('[data-hackathon-register-form]');
  if (registrationForm) {
    const message = $('[data-hk-register-message]');
    const otpPanel = $('[data-hk-otp-panel]');
    const successPanel = $('[data-hk-success]');
    const sendButton = $('[data-hk-send-otp]');
    const verifyButton = $('[data-hk-verify-otp]');
    const otpMessage = $('[data-hk-otp-message]');
    const otpInput = $('#hk-otp');
    let challengeId = null;
    let submittedEmail = '';

    registrationForm.addEventListener('submit', async event => {
      event.preventDefault();
      setMessage(message, '');
      if (!registrationForm.reportValidity()) return;
      const data = new FormData(registrationForm);
      const payload = {
        full_name: String(data.get('full_name') || '').trim(),
        email: String(data.get('email') || '').trim(),
        mobile: String(data.get('mobile') || '').trim(),
        college_name: String(data.get('college_name') || '').trim(),
        year_of_study: Number(data.get('year_of_study')),
        address: String(data.get('address') || '').trim(),
        pin_code: String(data.get('pin_code') || '').trim()
      };
      submittedEmail = payload.email;
      setBusy(sendButton, true, 'Sending verification code…');
      try {
        const result = await api('/api/hackathon/registrations/start', payload);
        if (!result.challenge_id) throw new Error('The verification code could not be requested. Please try again.');
        challengeId = result.challenge_id;
        $('[data-hk-otp-email]').textContent = submittedEmail;
        registrationForm.hidden = true;
        otpPanel.hidden = false;
        otpInput.focus();
        otpPanel.scrollIntoView({ behavior: 'smooth', block: 'center' });
      } catch (error) {
        setMessage(message, error.message || 'Registration could not be started. Please try again.', true);
      } finally {
        setBusy(sendButton, false);
      }
    });

    verifyButton.addEventListener('click', async () => {
      setMessage(otpMessage, '');
      if (!challengeId || !otpInput.reportValidity()) return;
      setBusy(verifyButton, true, 'Verifying email…');
      try {
        const result = await api('/api/hackathon/registrations/verify-email', {
          challenge_id: challengeId,
          otp: otpInput.value.trim()
        });
        if (!result.registration_id) throw new Error('Email verification succeeded, but a Registration ID was not returned. Contact SUTRAVYA support.');
        $('[data-hk-registration-id]').textContent = result.registration_id;
        const copy = $('[data-hk-success] p:nth-of-type(2)');
        if (copy) {
          copy.textContent = result.confirmation_email_sent && result.submission_instructions_email_sent
            ? 'Your registration confirmation and synopsis-submission instructions have been emailed to you.'
            : 'Your Registration ID is active. One of the automatic emails could not be delivered; please contact SUTRAVYA support for the submission instructions.';
        }
        otpPanel.hidden = true;
        successPanel.hidden = false;
        successPanel.scrollIntoView({ behavior: 'smooth', block: 'center' });
        challengeId = null;
      } catch (error) {
        setMessage(otpMessage, error.message || 'The code could not be verified. Check it and try again.', true);
      } finally {
        setBusy(verifyButton, false);
      }
    });
  }

  const loginForm = $('[data-hk-login-form]');
  if (loginForm) {
    const loginMessage = $('[data-hkp-login-message]');
    const otpMessage = $('[data-hkp-otp-message]');
    const otpPanel = $('[data-hkp-otp-panel]');
    const dashboard = $('[data-hkp-dashboard]');
    const loginButton = $('button[type="submit"]', loginForm);
    const verifyButton = $('[data-hkp-verify]');
    const otpInput = $('#hkp-otp');
    let challengeId = null;

    const showDashboard = profile => {
      $('[data-hkp-name]').textContent = profile.full_name || 'participant';
      $('[data-hkp-regid]').textContent = profile.registration_id || '—';
      $('[data-hkp-college]').textContent = profile.college_name || '—';
      $('[data-hkp-year]').textContent = 'Year ' + (profile.year_of_study || '—');
      loginForm.hidden = true;
      otpPanel.hidden = true;
      dashboard.hidden = false;
    };

    loginForm.addEventListener('submit', async event => {
      event.preventDefault();
      setMessage(loginMessage, '');
      if (!loginForm.reportValidity()) return;
      const payload = {
        registration_id: String(loginForm.elements.registration_id.value || '').trim(),
        email: String(loginForm.elements.email.value || '').trim()
      };
      setBusy(loginButton, true, 'Checking registration…');
      try {
        const result = await api('/api/hackathon/auth/request-otp', payload);
        if (!result.challenge_id) throw new Error('The Registration ID and email could not be matched. Check both details or contact SUTRAVYA support.');
        challengeId = result.challenge_id;
        loginForm.hidden = true;
        otpPanel.hidden = false;
        otpInput.focus();
      } catch (error) {
        setMessage(loginMessage, error.message || 'A sign-in code could not be requested.', true);
      } finally {
        setBusy(loginButton, false);
      }
    });

    verifyButton.addEventListener('click', async () => {
      setMessage(otpMessage, '');
      if (!challengeId || !otpInput.reportValidity()) return;
      setBusy(verifyButton, true, 'Verifying your sign-in…');
      try {
        await api('/api/hackathon/auth/verify-otp', {
          challenge_id: challengeId,
          otp: otpInput.value.trim()
        });
        const profile = await api('/api/hackathon/auth/session', null, 'GET');
        showDashboard(profile);
      } catch (error) {
        setMessage(otpMessage, error.message || 'Sign-in could not be completed. Request a new code.', true);
      } finally {
        setBusy(verifyButton, false);
      }
    });

    const logoutButton = $('[data-hkp-logout]');
    logoutButton.addEventListener('click', async () => {
      logoutButton.disabled = true;
      try {
        await api('/api/hackathon/auth/logout');
        dashboard.hidden = true;
        loginForm.hidden = false;
        loginForm.reset();
        otpInput.value = '';
        challengeId = null;
      } catch (error) {
        logoutButton.disabled = false;
        alert(error.message || 'Sign out could not be completed.');
      }
    });

    api('/api/hackathon/auth/session', null, 'GET')
      .then(showDashboard)
      .catch(() => { /* A signed-out participant sees the sign-in form. */ });
  }
})();
