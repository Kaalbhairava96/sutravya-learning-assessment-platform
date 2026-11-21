(() => {
  'use strict';
  const apiBase = document.querySelector('meta[name="sutravya-api-base"]')?.content.trim() || '';
  const $ = selector => document.querySelector(selector);
  const $$ = selector => [...document.querySelectorAll(selector)];
  const state = { admin: null, overview: null, selectedTable: '', offset: 0, limit: 25, currentData: null, currentRecord: null };
  const TOKEN_KEY = 'sutravya_admin_access_token';
  const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, ch => ({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  }[ch]));
  const format = value => {
    if (value === null || value === undefined || value === '') return '—';
    if (typeof value === 'object') return JSON.stringify(value);
    if (typeof value === 'boolean') return value ? 'Yes' : 'No';
    return String(value);
  };
  const compact = value => {
    const streamLabels = {mbbs_ug:'Medical UG',mbbs_pg:'Medical PG',mbbs_1st_year:'Medical UG'};
    const text = typeof value === 'string' ? (streamLabels[value] || value) : format(value);
    return text.length > 100 ? text.slice(0, 97) + '…' : text;
  };
  const setGlobal = (message, kind = '') => {
    const node = $('#admin-global-status');
    node.textContent = message;
    node.className = 'admin-global-status' + (kind ? ' is-' + kind : '');
    node.hidden = !message;
  };
  const setStatus = (selector, message, kind = '') => {
    const node = $(selector);
    if (!node) return;
    node.textContent = message;
    node.className = 'admin-login-status' + (kind ? ' is-' + kind : '');
  };
  async function api(path, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (options.body) headers['Content-Type'] = 'application/json';
    if (options.write) headers['X-Admin-Request'] = '1';
    const token = sessionStorage.getItem(TOKEN_KEY);
    if (token) headers.Authorization = 'Bearer ' + token;
    let response;
    try {
      response = await fetch(apiBase + path, {
        method: options.method || 'GET',
        credentials: 'omit',
        cache: 'no-store',
        headers,
        body: options.body ? JSON.stringify(options.body) : undefined
      });
    } catch (error) {
      if(error instanceof TypeError || /failed to fetch|networkerror|load failed/i.test(error.message||'')) throw new Error('The assessment API is currently unreachable. Check the API service connection and use Refresh to retry.');
      throw error;
    }
    let data = {};
    if (response.status !== 204) {
      try { data = await response.json(); } catch { /* Generic API error below. */ }
    }
    if (response.status === 401) {
      sessionStorage.removeItem(TOKEN_KEY);
      location.replace('admin-login.html');
      throw new Error('Your administrator session has expired.');
    }
    if (!response.ok) throw new Error(data.detail || 'The operation could not be completed.');
    return data;
  }
  function switchView(name) {
    $$('[data-view-panel]').forEach(panel => panel.classList.toggle('is-active', panel.dataset.viewPanel === name));
    $$('[data-admin-view]').forEach(button => button.classList.toggle('is-active', button.dataset.adminView === name));
    const titles = { overview:'Operations overview', registrations:'Registrations', database:'Database explorer', slots:'Exam scheduling', results:'Results & release', audit:'Audit history' };
    $('#admin-page-title').textContent = titles[name] || 'Operations overview';
    if (name === 'database' && !state.selectedTable) selectTable('registrations');
    if (name === 'slots') loadSlots();
    if (name === 'results') loadResults();
    if (name === 'audit') loadAudit();
    if (name === 'registrations') loadRegistrationPreview();
  }
  function renderMetrics() {
    const tables = state.overview?.tables || [];
    const count = name => tables.find(table => table.name === name)?.rows || 0;
    $('#admin-metrics').innerHTML = [
      ['Database records', state.overview?.total_rows ?? 0, 'Across managed tables'],
      ['Registrations', count('registrations'), 'Candidate applications'],
      ['Exam attempts', count('exam_attempts'), 'Assessment activity'],
      ['Published results', count('results'), 'Calculated result records']
    ].map(([label, number, sub]) => '<article class="admin-metric-card"><span>'+escapeHtml(label)+'</span><strong>'+Number(number).toLocaleString('en-IN')+'</strong><small>'+escapeHtml(sub)+'</small></article>').join('');
    const db = state.overview?.database || {};
    $('#admin-database-summary').innerHTML = [
      ['Database', db.database_name || '—'], ['Engine', 'PostgreSQL ' + (db.server_version || '—')],
      ['Schema', db.schema_name || '—'], ['Migration', db.schema_revision || '—'],
      ['Managed tables', state.overview?.total_tables || 0], ['Total rows', state.overview?.total_rows || 0]
    ].map(([key,value]) => '<div><small>'+escapeHtml(key)+'</small><b>'+escapeHtml(value)+'</b></div>').join('');
    $('#admin-readiness').innerHTML = '<div class="admin-loading-line">Loading stream summary…</div>';

    $('#admin-database-badges').innerHTML = '<span>'+escapeHtml(db.database_name || 'Database')+'</span><span>'+state.overview.total_tables+' tables</span><span>'+Number(state.overview.total_rows).toLocaleString('en-IN')+' records</span>';
  }
  function renderTableList() {
    const query = ($('#admin-table-filter').value || '').trim().toLowerCase();
    const items = (state.overview?.tables || []).filter(item =>
      item.name.toLowerCase().includes(query) || item.label.toLowerCase().includes(query)
    );
    $('#admin-table-count').textContent = (state.overview?.tables || []).length + ' managed tables';
    $('#admin-table-list').innerHTML = items.map(item =>
      '<button type="button" class="admin-table-item '+(item.name===state.selectedTable?'is-active':'')+'" data-table-name="'+escapeHtml(item.name)+'"><span><b>'+escapeHtml(item.label)+'</b><small>'+escapeHtml(item.name)+(item.restricted?' · protected':'')+'</small></span><strong>'+Number(item.rows).toLocaleString('en-IN')+'</strong></button>'
    ).join('') || '<p class="admin-muted">No matching tables.</p>';
    $$('#admin-table-list [data-table-name]').forEach(button => button.addEventListener('click', () => selectTable(button.dataset.tableName)));
  }
  async function selectTable(name) {
    state.selectedTable = name;
    state.offset = 0;
    renderTableList();
    await loadTable();
  }
  function renderTable(data) {
    state.currentData = data;
    $('#admin-table-kicker').textContent = data.restricted ? 'PROTECTED TABLE' : 'DATABASE TABLE';
    $('#admin-selected-table').textContent = data.label;
    $('#admin-selected-description').textContent = data.notice || data.description || '';
    if (data.restricted) {
      $('#admin-table-content').innerHTML = '<div class="admin-restricted-notice"><b>Protected system data</b><p>'+escapeHtml(data.notice)+'</p><strong>'+Number(data.total).toLocaleString('en-IN')+' rows</strong></div>';
      $('#admin-refresh-table').disabled = false;
      return;
    }
    const columns = data.columns || [];
    const records = data.records || [];
    const header = columns.map(c => '<th>'+escapeHtml(c.name.replaceAll('_',' '))+'</th>').join('');
    const rows = records.map(record => {
      const cells = columns.map(c => '<td title="'+escapeHtml(format(record[c.name]))+'">'+escapeHtml(compact(record[c.name]))+'</td>').join('');
      const edit = data.editable_fields?.length ? '<td><button class="admin-row-edit" type="button" data-record-id="'+escapeHtml(record.id)+'">Edit</button></td>' : '<td><span class="admin-readonly-chip">Read only</span></td>';
      return '<tr>'+cells+edit+'</tr>';
    }).join('');
    const actionHead = '<th>Action</th>';
    const start = data.total ? data.offset + 1 : 0;
    const end = Math.min(data.offset + data.limit, data.total);
    $('#admin-table-content').innerHTML =
      '<div class="admin-table-toolbar"><label class="admin-table-query-label" for="admin-record-search">Search records</label><input id="admin-record-search" type="search" value="'+escapeHtml($('#admin-record-search')?.value || '')+'" placeholder="Search by name, email, registration ID…"><span>'+start+'–'+end+' of '+Number(data.total).toLocaleString('en-IN')+'</span></div>' +
      (records.length ? '<div class="admin-data-table-wrap"><table class="admin-data-table"><thead><tr>'+header+actionHead+'</tr></thead><tbody>'+rows+'</tbody></table></div>' : '<div class="admin-empty-state"><b>No records found</b><span>Try changing the search term or refresh the table.</span></div>') +
      '<div class="admin-pagination"><button type="button" id="admin-page-previous" '+(data.offset<=0?'disabled':'')+'>← Previous</button><span>Page '+(Math.floor(data.offset/data.limit)+1)+' of '+Math.max(1,Math.ceil(data.total/data.limit))+'</span><button type="button" id="admin-page-next" '+(data.offset+data.limit>=data.total?'disabled':'')+'>Next →</button></div>';
    $('#admin-refresh-table').disabled = false;
    $('#admin-record-search').addEventListener('keydown', event => {
      if (event.key === 'Enter') { state.offset = 0; loadTable($('#admin-record-search').value); }
    });
    $('#admin-page-previous').addEventListener('click', () => { state.offset = Math.max(0, state.offset - state.limit); loadTable($('#admin-record-search').value); });
    $('#admin-page-next').addEventListener('click', () => { state.offset += state.limit; loadTable($('#admin-record-search').value); });
    $$('#admin-table-content [data-record-id]').forEach(button => button.addEventListener('click', () => {
      const record = records.find(item => item.id === button.dataset.recordId);
      if (record) openEdit(record, data);
    }));
  }
  async function loadTable(search = '') {
    if (!state.selectedTable) return;
    $('#admin-table-content').innerHTML = '<div class="admin-loading-line">Loading records…</div>';
    try {
      const data = await api('/api/admin/database/tables/'+encodeURIComponent(state.selectedTable)+'?limit='+state.limit+'&offset='+state.offset+'&search='+encodeURIComponent(search));
      renderTable(data);
    } catch (error) {
      $('#admin-table-content').innerHTML = '<div class="admin-empty-state"><b>Unable to load this table</b><span>'+escapeHtml(error.message)+'</span></div>';
    }
  }
  function openEdit(record, data) {
    state.currentRecord = record;
    $('#admin-edit-title').textContent = 'Edit ' + data.label;
    $('#admin-edit-subtitle').textContent = 'Record ' + record.id;
    const types = {
      capacity:'number',time_limit_seconds:'number',is_active:'checkbox',
      starts_at:'datetime-local',ends_at:'datetime-local'
    };
    $('#admin-edit-fields').innerHTML = (data.editable_fields || []).map(field => {
      const value = record[field];
      const type = types[field] || (typeof value === 'object' ? 'textarea' : 'text');
      if (type === 'checkbox') return '<label class="admin-edit-field admin-edit-checkbox"><input type="checkbox" name="'+field+'" '+(value?'checked':'')+'><span>'+escapeHtml(field.replaceAll('_',' '))+'</span></label>';
      let shown = value ?? '';
      if (type === 'datetime-local' && shown) shown = new Date(shown).toISOString().slice(0,16);
      if (type === 'textarea') shown = JSON.stringify(value ?? null, null, 2);
      const control = type === 'textarea'
        ? '<textarea name="'+field+'" rows="4">'+escapeHtml(shown)+'</textarea>'
        : '<input type="'+type+'" name="'+field+'" value="'+escapeHtml(shown)+'" '+(type==='number'?'step="1"':'')+'>';
      return '<label class="admin-edit-field"><span>'+escapeHtml(field.replaceAll('_',' '))+'</span>'+control+'</label>';
    }).join('');
    $('#admin-edit-status').textContent = '';
    $('#admin-edit-modal').hidden = false;
    $('#admin-edit-modal').querySelector('input,textarea')?.focus();
  }
  function closeEdit() {
    $('#admin-edit-modal').hidden = true;
    state.currentRecord = null;
  }
  async function saveEdit(event) {
    event.preventDefault();
    const record = state.currentRecord;
    const data = state.currentData;
    if (!record || !data) return;
    const changes = {};
    const form = new FormData(event.currentTarget);
    for (const field of data.editable_fields || []) {
      const element = event.currentTarget.elements.namedItem(field);
      if (!element) continue;
      if (element.type === 'checkbox') {
        if (element.checked !== Boolean(record[field])) changes[field] = element.checked;
        continue;
      }
      let value = form.get(field);
      if (element.type === 'number') value = Number(value);
      if (element.type === 'datetime-local' && value) value = new Date(value).toISOString();
      if (value !== String(record[field] ?? '')) changes[field] = value;
    }
    if (!Object.keys(changes).length) { setStatus('#admin-edit-status','No changes to save.','warning'); return; }
    const button = event.currentTarget.querySelector('button[type="submit"]');
    button.disabled = true;
    setStatus('#admin-edit-status','Saving and recording changes…');
    try {
      await api('/api/admin/database/tables/'+encodeURIComponent(state.selectedTable)+'/'+encodeURIComponent(record.id), {
        method:'PATCH', write:true, body:{changes}
      });
      closeEdit();
      setGlobal('Record updated. The action has been written to the audit history.','success');
      await refreshOverview();
      await loadTable($('#admin-record-search')?.value || '');
    } catch (error) {
      setStatus('#admin-edit-status',error.message,'error');
    } finally { button.disabled = false; }
  }
  async function refreshOverview() {
    state.overview = await api('/api/admin/database/overview');
    renderMetrics();
    renderTableList();
    await loadStreamSummary();
    return state.overview;
  }
  async function loadStreamSummary() {
    try {
      const summary = await api('/api/admin/assessment/summary');
      const streams = summary.streams || {};
      const labels = {paramedical:'Paramedical',nursing:'Nursing',mbbs_ug:'Medical UG',mbbs_pg:'Medical PG'};
      $('#admin-readiness').innerHTML = Object.entries(labels).map(([key,label]) =>
        '<article><span>'+escapeHtml(label)+'</span><b>'+Number(streams[key] || 0).toLocaleString('en-IN')+'</b><small>Candidate registrations</small></article>'
      ).join('') + (summary.unassigned ? '<article><span>Unassigned</span><b>'+Number(summary.unassigned).toLocaleString('en-IN')+'</b><small>Legacy or unmatched records</small></article>' : '');
    } catch (error) {
      $('#admin-readiness').innerHTML = '<div class="admin-empty-state"><b>Stream summary unavailable</b><span>'+escapeHtml(error.message)+'</span></div>';
    }
  }
  async function loadRegistrationPreview() {
    try {
      const data = await api('/api/admin/database/tables/registrations?limit=8&offset=0');
      const cols = ['registration_id','stream','status','created_at'].filter(key => data.columns.some(c => c.name === key));
      $('#admin-registration-preview').innerHTML = data.records.length
        ? '<div class="admin-data-table-wrap"><table class="admin-data-table"><thead><tr>'+cols.map(c=>'<th>'+escapeHtml(c.replaceAll('_',' '))+'</th>').join('')+'</tr></thead><tbody>'+data.records.map(row=>'<tr>'+cols.map(c=>'<td>'+escapeHtml(compact(row[c]))+'</td>').join('')+'</tr>').join('')+'</tbody></table></div><button class="admin-link-button" data-open-table="registrations">View all registrations →</button>'
        : '<div class="admin-empty-state"><b>No registrations found</b><span>The registration table currently contains no records.</span></div>';
      $$('[data-open-table="registrations"]').forEach(button => button.addEventListener('click', () => { switchView('database'); selectTable('registrations'); }));
    } catch (error) { $('#admin-registration-preview').textContent = error.message; }
  }
  async function loadSlots() {
    try {
      const data = await api('/api/admin/database/tables/exam_slots?limit=100&offset=0');
      const slots = data.records || [];
      $('#admin-assign-slot').innerHTML = '<option value="">Choose a configured slot</option>' + slots.map(slot =>
        '<option value="'+escapeHtml(slot.id)+'">'+escapeHtml(({mbbs_ug:'Medical UG',mbbs_pg:'Medical PG'}[slot.stream] || slot.stream))+' · '+escapeHtml(new Date(slot.starts_at).toLocaleString())+'</option>'
      ).join('');
      const cols = ['stream','starts_at','ends_at','capacity'].filter(key=>data.columns.some(c=>c.name===key));
      $('#admin-slot-table').innerHTML = slots.length
        ? '<div class="admin-data-table-wrap"><table class="admin-data-table"><thead><tr>'+cols.map(c=>'<th>'+escapeHtml(c.replaceAll('_',' '))+'</th>').join('')+'</tr></thead><tbody>'+slots.map(slot=>'<tr>'+cols.map(c=>'<td>'+escapeHtml(compact(slot[c]))+'</td>').join('')+'</tr>').join('')+'</tbody></table></div>'
        : '<div class="admin-empty-state"><b>No exam slots configured</b><span>Create the first future assessment slot above.</span></div>';
    } catch (error) { $('#admin-slot-table').textContent = error.message; }
  }
  async function createSlot(event) {
    event.preventDefault();
    if (!event.currentTarget.reportValidity()) return;
    const startRaw = $('#admin-slot-start').value;
    const endRaw = $('#admin-slot-end').value;
    if (!startRaw || !endRaw) return;
    const localIst = value => new Date(value + ':00+05:30').toISOString();
    const button = event.currentTarget.querySelector('button[type="submit"]');
    button.disabled = true;
    setStatus('#admin-slot-status','Creating examination slot…');
    try {
      const result = await api('/api/admin/assessment/slots', {
        method:'POST', write:true,
        body:{stream:$('#admin-slot-stream').value,starts_at:localIst(startRaw),ends_at:localIst(endRaw),capacity:Number($('#admin-slot-capacity').value)}
      });
      setStatus('#admin-slot-status','Slot created: '+result.slot_id,'success');
      event.currentTarget.reset();
      $('#admin-slot-capacity').value = 1000;
      await refreshOverview();
      await loadSlots();
    } catch (error) { setStatus('#admin-slot-status',error.message,'error'); }
    finally { button.disabled = false; }
  }
  async function assignCandidates(event) {
    event.preventDefault();
    const slot = $('#admin-assign-slot').value;
    const ids = $('#admin-assign-ids').value.split(/[\s,;]+/).map(value=>value.trim()).filter(Boolean);
    if (!slot || !ids.length) { setStatus('#admin-assign-status','Choose a slot and enter at least one registration ID.','error'); return; }
    const button = event.currentTarget.querySelector('button[type="submit"]');
    button.disabled = true;
    try {
      const result = await api('/api/admin/assessment/slots/'+encodeURIComponent(slot)+'/assign', {
        method:'POST', write:true, body:{registration_ids:ids}
      });
      setStatus('#admin-assign-status',result.assigned_count+' candidate(s) assigned to '+result.stream+'.','success');
      $('#admin-assign-ids').value = '';
      await refreshOverview();
      await loadSlots();
    } catch (error) { setStatus('#admin-assign-status',error.message,'error'); }
    finally { button.disabled = false; }
  }
  async function loadResults() {
    try {
      const data = await api('/api/admin/database/tables/results?limit=100&offset=0');
      const rows = data.records || [];
      const cols = ['id','attempt_id','score','approved_at','released_at'].filter(key=>data.columns.some(c=>c.name===key));
      $('#admin-results-table').innerHTML = rows.length
        ? '<div class="admin-data-table-wrap"><table class="admin-data-table"><thead><tr>'+cols.map(c=>'<th>'+escapeHtml(c.replaceAll('_',' '))+'</th>').join('')+'<th>Actions</th></tr></thead><tbody>'+rows.map(row=>
          '<tr>'+cols.map(c=>'<td>'+escapeHtml(compact(row[c]))+'</td>').join('')+'<td class="admin-row-actions">'+
          (row.approved_at ? '<span class="admin-readonly-chip">Approved</span>' : '<button type="button" class="admin-approve-action" data-result-action="approve" data-result-id="'+escapeHtml(row.id)+'">Approve result</button>')+
          (row.released_at ? '<span class="admin-readonly-chip">Released</span>' : (row.approved_at ? '<button type="button" class="admin-release-action" data-result-action="release" data-result-id="'+escapeHtml(row.id)+'">Release to candidate</button>' : '<span class="admin-readonly-chip">Approval required</span>'))+
          '</td></tr>').join('')+'</tbody></table></div>'
        : '<div class="admin-empty-state"><b>No results available</b><span>Results will appear here after candidates complete their assessments.</span></div>';
      $$('#admin-results-table [data-result-action]').forEach(button => button.addEventListener('click', async () => {
        const action = button.dataset.resultAction;
        if (!confirm(action==='release'?'Release this approved result to the candidate?':'Approve this calculated result?')) return;
        button.disabled = true;
        try {
          await api('/api/admin/results/'+encodeURIComponent(button.dataset.resultId)+'/'+action,{method:'POST',write:true});
          setGlobal('Result '+(action==='release'?'released':'approved')+' and recorded in audit history.','success');
          await loadResults();
          await refreshOverview();
        } catch (error) { setGlobal(error.message,'error'); button.disabled = false; }
      }));
    } catch (error) { $('#admin-results-table').textContent = error.message; }
  }
  async function loadAudit() {
    try {
      const data = await api('/api/admin/audit?limit=100');
      $('#admin-audit-table').innerHTML = data.records.length
        ? '<div class="admin-data-table-wrap"><table class="admin-data-table"><thead><tr><th>Time</th><th>Administrator</th><th>Action</th><th>Target</th><th>Record ID</th></tr></thead><tbody>'+data.records.map(row=>
          '<tr><td>'+escapeHtml(new Date(row.created_at).toLocaleString())+'</td><td>'+escapeHtml(row.actor)+'</td><td>'+escapeHtml(row.action)+'</td><td>'+escapeHtml(row.target_type || '—')+'</td><td>'+escapeHtml(row.target_id || '—')+'</td></tr>'
        ).join('')+'</tbody></table></div>'
        : '<div class="admin-empty-state"><b>No audit events yet</b><span>Administrator actions will appear here.</span></div>';
    } catch (error) { $('#admin-audit-table').textContent = error.message; }
  }
  async function logout() {
    const button = $('#admin-logout');
    button.disabled = true;
    try { await api('/api/admin/auth/logout',{method:'POST',write:true}); } catch { /* Expired sessions are redirected by api(). */ }
    sessionStorage.removeItem(TOKEN_KEY);
    location.replace('admin-login.html');
  }
  async function initialise() {
    try {
      const me = await api('/api/admin/auth/me');
      state.admin = me.administrator;
      $('#admin-user-email').textContent = state.admin.email;
      $('#admin-user-role').textContent = state.admin.role;
      $('#admin-user-avatar').textContent = (state.admin.email[0] || 'A').toUpperCase();
      state.overview = await api('/api/admin/database/overview');
      renderMetrics();
      renderTableList();
      $('#admin-auth-redirect').hidden = true;
      $('#admin-portal').hidden = false;
      await loadRegistrationPreview();
      await loadStreamSummary();
    } catch (error) {
      if (!location.pathname.endsWith('admin-login.html')) location.replace('admin-login.html');
    }
  }
  $$('[data-admin-view]').forEach(button => button.addEventListener('click', () => switchView(button.dataset.adminView)));
  $$('[data-open-table]').forEach(button => button.addEventListener('click', () => {
    switchView('database');
    selectTable(button.dataset.openTable);
  }));
  $('#admin-table-filter').addEventListener('input', renderTableList);
  $('#admin-refresh-table').addEventListener('click', () => loadTable($('#admin-record-search')?.value || ''));
  $('#admin-edit-form').addEventListener('submit', saveEdit);
  $('#admin-slot-form').addEventListener('submit', createSlot);
  $('#admin-assign-form').addEventListener('submit', assignCandidates);
  $('#admin-logout').addEventListener('click', logout);
  $('#admin-refresh-audit').addEventListener('click', loadAudit);
  $$('[data-close-edit]').forEach(button => button.addEventListener('click', closeEdit));
  $('#admin-edit-modal').addEventListener('keydown', event => { if (event.key === 'Escape') closeEdit(); });
  document.body.dataset.page='admin.html';
  const adminIcons={
    mail:'<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m4 7 8 6 8-6"/>',
    shield:'<path d="M12 3 20 6v5c0 5-3 8-8 10-5-2-8-5-8-10V6l8-3Z"/><path d="m8 12 3 3 5-6"/>',
    user:'<circle cx="12" cy="8" r="3.5"/><path d="M4.5 20a7.5 7.5 0 0 1 15 0"/>',
    calendar:'<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4m10-4v4M3 10h18"/>',
    institution:'<path d="m3 9 9-5 9 5v11H3z"/><path d="M2 9h20M7 12v5m5-5v5m5-5v5M2 20h20"/>',
    clipboard:'<rect x="5" y="4" width="14" height="18" rx="2"/><path d="M9 4V2h6v2M8 10h8m-8 4h8"/>',
    chart:'<path d="M4 19V5m0 14h17"/><path d="m7 14 4-4 3 2 5-6"/><path d="M16 6h3v3"/>',
    trophy:'<path d="M8 21h8m-4-4v4M7 4h10v5a5 5 0 0 1-10 0V4Z"/><path d="M7 6H3v2a4 4 0 0 0 4 4m10-6h4v2a4 4 0 0 1-4 4"/>',
    check:'<path d="m5 12 4 4L19 6"/>',
    clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.5 2"/>',
    refresh:'<path d="M20 7v5h-5"/><path d="M4.7 9A8 8 0 0 1 18.2 6L20 12M4 17v-5h5"/><path d="M5.8 18A8 8 0 0 0 19.3 15L20 12"/>'
  };
  const adminVisualIcon=name=>{
    const span=document.createElement('span');span.className='form-label-icon';span.setAttribute('aria-hidden','true');
    span.innerHTML='<svg viewBox="0 0 24 24" focusable="false">'+adminIcons[name]+'</svg>';return span;
  };
  const enhanceAdminVisuals=root=>{
    const navNames={overview:'chart',registrations:'clipboard',database:'institution',slots:'calendar',results:'trophy',audit:'shield'};
    root.querySelectorAll('.admin-side-nav button').forEach(button=>{
      const marker=button.querySelector(':scope > span');
      if(!marker||marker.classList.contains('admin-nav-icon'))return;
      const name=navNames[button.dataset.adminView]||'clipboard';
      marker.className='admin-nav-icon';
      marker.setAttribute('aria-hidden','true');
      marker.innerHTML='<svg viewBox="0 0 24 24" focusable="false">'+adminIcons[name]+'</svg>';
    });
    root.querySelectorAll('.admin-metric-card>span').forEach(label=>{
      if(label.querySelector('.admin-metric-icon'))return;
      const text=label.textContent.toLowerCase();
      const name=/database|record/.test(text)?'institution':/registration|candidate/.test(text)?'user':/attempt|exam/.test(text)?'clipboard':/result|published/.test(text)?'trophy':'chart';
      const node=adminVisualIcon(name);node.classList.add('admin-metric-icon');label.prepend(node);
    });
    root.querySelectorAll('.admin-operation-form button[type="submit"],.admin-primary-button,.admin-secondary-button,.admin-logout-button,.admin-link-button,.admin-row-edit,.admin-approve-action,.admin-release-action,.admin-pagination button').forEach(button=>{
      if(button.querySelector('svg,.admin-context-button-icon'))return;
      const text=button.textContent.toLowerCase();
      const name=/sign out|logout/.test(text)?'shield':/refresh|retry|previous|next/.test(text)?'refresh':/approve|release|save|submit|create|assign/.test(text)?'check':/result|award/.test(text)?'trophy':/database|table/.test(text)?'institution':/exam|slot|schedule/.test(text)?'calendar':'clipboard';
      const node=adminVisualIcon(name);node.classList.add('admin-context-button-icon');button.prepend(node);
    });
    root.querySelectorAll('label[for]').forEach(label=>{
      if(label.querySelector('.form-label-icon'))return;
      const key=(label.htmlFor+' '+label.textContent).toLowerCase();
      const name=/email/.test(key)?'mail':/password|token/.test(key)?'shield':/start|end|date|time|capacity/.test(key)?'calendar':/registration|ids|record/.test(key)?'clipboard':/table|database|college|institution/.test(key)?'institution':'user';
      label.prepend(adminVisualIcon(name));
    });
    root.querySelectorAll('.admin-topbar h1,.admin-welcome-band h2').forEach(heading=>{
      if(heading.querySelector('.admin-heading-icon'))return;
      const node=adminVisualIcon(heading.matches('.admin-topbar h1')?'chart':'institution');
      node.classList.add('admin-heading-icon');heading.prepend(node);
    });
    root.querySelectorAll('.admin-operation-form small').forEach(note=>{
      if(!/47\\s*minutes?|duration/i.test(note.textContent)||note.querySelector('.admin-duration-icon'))return;
      const node=adminVisualIcon('clock');node.classList.add('admin-duration-icon');note.prepend(node);
    });
    root.querySelectorAll('.admin-panel-heading h3,.admin-section-intro h2').forEach(heading=>{
      if(heading.querySelector('.admin-heading-icon'))return;
      const key=heading.textContent.toLowerCase();
      const name=/audit|history|record/.test(key)?'clipboard':/slot|schedule|exam/.test(key)?'calendar':/database|table/.test(key)?'institution':/result|approval/.test(key)?'shield':'user';
      const node=adminVisualIcon(name);node.classList.add('admin-heading-icon');heading.prepend(node);
    });
  };
  enhanceAdminVisuals(document);
  if('MutationObserver' in window){
    const adminObserver=new MutationObserver(records=>records.forEach(record=>record.addedNodes.forEach(node=>{
      if(node.nodeType===1)enhanceAdminVisuals(node);
    })));
    adminObserver.observe(document.getElementById('admin-portal'),{childList:true,subtree:true});
  }
  initialise();
})();
