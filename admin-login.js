(() => {
  'use strict';
  const apiBase = document.querySelector('meta[name="sutravya-api-base"]')?.content.trim() || '';
  const $ = selector => document.querySelector(selector);
  const loading = $('#admin-auth-loading');
  const content = $('#admin-login-content');
  const loginForm = $('#admin-login-form');
  const setupForm = $('#admin-setup-form');
  const status = $('#admin-login-status');
  const TOKEN_KEY = 'sutravya_admin_access_token';
  const setStatus = (message, kind = '') => {
    status.textContent = message;
    status.className = 'admin-login-status' + (kind ? ' is-' + kind : '');
  };
  const request = async (path, options = {}) => {
    if (!apiBase) throw new Error('The assessment API is not configured.');
    const headers = { ...(options.headers || {}) };
    if (options.body) headers['Content-Type'] = 'application/json';
    if (options.write) headers['X-Admin-Request'] = '1';
    const token = sessionStorage.getItem(TOKEN_KEY);
    if (token) headers.Authorization = 'Bearer ' + token;
    const response = await fetch(apiBase + path, {
      method: options.method || 'GET',
      credentials: 'omit',
      cache: 'no-store',
      headers,
      body: options.body ? JSON.stringify(options.body) : undefined
    });
    let data = {};
    if (response.status !== 204) {
      try { data = await response.json(); } catch { /* A generic response is handled below. */ }
    }
    if (!response.ok) throw new Error(data.detail || 'The request could not be completed.');
    return data;
  };
  const showLogin = () => {
    $('#admin-login-eyebrow').textContent = 'WELCOME BACK';
    $('#admin-login-title').textContent = 'Administrator sign in';
    $('#admin-login-intro').textContent = 'Sign in with your administrator account to open the private console.';
    loginForm.hidden = false;
    setupForm.hidden = true;
  };
  const showSetup = () => {
    $('#admin-login-eyebrow').textContent = 'FIRST-TIME SECURE SETUP';
    $('#admin-login-title').textContent = 'Create the owner account';
    $('#admin-login-intro').textContent = 'Use the one-time setup token supplied by the service owner. This setup can only be completed once.';
    loginForm.hidden = true;
    setupForm.hidden = false;
  };
  async function initialise() {
    try {
      const me = await request('/api/admin/auth/me');
      if (me.administrator) { location.replace('admin.html'); return; }
    } catch { /* Not signed in yet. */ }
    try {
      const state = await request('/api/admin/auth/status');
      loading.hidden = true;
      content.hidden = false;
      if (state.setup_required) {
        if (state.setup_available) showSetup();
        else {
          $('#admin-login-eyebrow').textContent = 'SETUP NOT CONFIGURED';
          $('#admin-login-title').textContent = 'Owner setup is locked';
          $('#admin-login-intro').textContent = 'A service owner must configure the one-time administrator bootstrap token and session secret on the API service before creating the first account.';
          loginForm.hidden = true;
          setupForm.hidden = true;
          setStatus('Administrator access is not yet configured on the server.', 'warning');
        }
      } else if (state.login_available) showLogin();
      else {
        showLogin();
        setStatus('Administrator sign-in is temporarily unavailable.', 'warning');
      }
    } catch (error) {
      loading.hidden = true;
      content.hidden = false;
      showLogin();
      setStatus(error.message, 'error');
    }
  }
  loginForm.addEventListener('submit', async event => {
    event.preventDefault();
    if (!loginForm.reportValidity()) return;
    const button = loginForm.querySelector('button[type="submit"]');
    button.disabled = true;
    setStatus('Verifying your administrator credentials…');
    try {
      const result = await request('/api/admin/auth/login', {
        method: 'POST', write: true,
        body: { email: $('#admin-email').value.trim(), password: $('#admin-password').value }
      });
      if (!result.access_token) throw new Error('The API did not return an administrator session token.');
      sessionStorage.setItem(TOKEN_KEY, result.access_token);
      setStatus('Sign in successful. Opening the console…', 'success');
      location.replace('admin.html');
    } catch (error) {
      setStatus(error.message, 'error');
      $('#admin-password').value = '';
      $('#admin-password').focus();
    } finally {
      button.disabled = false;
    }
  });
  setupForm.addEventListener('submit', async event => {
    event.preventDefault();
    if (!setupForm.reportValidity()) return;
    const password = $('#admin-setup-password').value;
    if (password !== $('#admin-setup-confirm').value) {
      setStatus('The two passwords do not match.', 'error');
      $('#admin-setup-confirm').focus();
      return;
    }
    const button = setupForm.querySelector('button[type="submit"]');
    button.disabled = true;
    setStatus('Creating the first owner account…');
    try {
      const result = await request('/api/admin/auth/setup', {
        method: 'POST', write: true,
        headers: { 'X-Admin-Bootstrap-Token': $('#admin-bootstrap-token').value.trim() },
        body: { email: $('#admin-setup-email').value.trim(), password }
      });
      if (!result.access_token) throw new Error('The API did not return an administrator session token.');
      sessionStorage.setItem(TOKEN_KEY, result.access_token);
      $('#admin-bootstrap-token').value = '';
      $('#admin-setup-password').value = '';
      $('#admin-setup-confirm').value = '';
      setStatus('Owner account created. Opening the console…', 'success');
      location.replace('admin.html');
    } catch (error) {
      setStatus(error.message, 'error');
    } finally {
      button.disabled = false;
    }
  });
  initialise();
})();
