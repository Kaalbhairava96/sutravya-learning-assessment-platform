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
  document.body.dataset.page='admin-login.html';
  const adminIconPaths={
    mail:'<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m4 7 8 6 8-6"/>',
    shield:'<path d="M12 3 20 6v5c0 5-3 8-8 10-5-2-8-5-8-10V6l8-3Z"/><path d="m8 12 3 3 5-6"/>',
    key:'<circle cx="8" cy="15" r="5"/><path d="m11.5 11.5 9-9m-3 3 3 3"/>',
    user:'<circle cx="12" cy="8" r="3.5"/><path d="M4.5 20a7.5 7.5 0 0 1 15 0"/>'
  };
  const addAdminLabelIcons=root=>{
    root.querySelectorAll('label[for]').forEach(label=>{
      if(label.querySelector('.form-label-icon'))return;
      const id=(label.htmlFor||'').toLowerCase(),text=label.textContent.toLowerCase();
      const name=/email/.test(id+' '+text)?'mail':/token|password|confirm/.test(id+' '+text)?'shield':'user';
      const node=document.createElement('span');node.className='form-label-icon';node.setAttribute('aria-hidden','true');
      node.innerHTML='<svg viewBox="0 0 24 24" focusable="false">'+adminIconPaths[name]+'</svg>';label.prepend(node);
    });
  };
  addAdminLabelIcons(document);
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
    if(retryButton)retryButton.hidden=true;
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
