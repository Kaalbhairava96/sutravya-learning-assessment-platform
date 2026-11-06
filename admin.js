(() => {
  'use strict';
  const apiBase = document.querySelector('meta[name="sutravya-api-base"]')?.content.trim() || '';
  const keyInput = document.getElementById('admin-key');
  const overview = document.getElementById('overview');
  let adminKey = '';

  const status = (id, message, isError = false) => {
    const node = document.getElementById(id);
    node.textContent = message;
    node.style.color = isError ? '#a22d2d' : '#246044';
  };
  const request = async (path, {method = 'GET', body} = {}) => {
    if (!apiBase) throw new Error('API base URL is not configured.');
    if (!adminKey) throw new Error('Connect with the private administrator key first.');
    const response = await fetch(apiBase + path, {
      method,
      credentials: 'omit',
      headers: {
        'X-Admin-Key': adminKey,
        ...(body ? {'Content-Type': 'application/json'} : {})
      },
      body: body ? JSON.stringify(body) : undefined
    });
    let data = {};
    try { data = await response.json(); } catch {}
    if (!response.ok) throw new Error(data.detail || 'The request could not be completed.');
    return data;
  };
  const istIso = value => {
    if (!value) throw new Error('Complete both slot timestamps.');
    const date = new Date(value + ':00+05:30');
    if (Number.isNaN(date.getTime())) throw new Error('Invalid slot timestamp.');
    return date.toISOString();
  };
  const renderOverview = data => {
    const streams = Object.entries(data.streams || {});
    const streamCards = streams.map(([stream, item]) =>
      '<div class="admin-stream"><strong>' + stream.replaceAll('_', ' ') + '</strong>' +
      '<span>' + item.registrations + ' registrations</span><br><span>' +
      item.question_count + ' active questions</span></div>'
    ).join('');
    const slotCards = (data.slots || []).map(slot =>
      '<div class="admin-stream"><strong>' + slot.stream + '</strong><span>' +
      slot.id + '</span><br><span>Capacity: ' + slot.capacity + '</span></div>'
    ).join('');
    overview.innerHTML =
      '<div class="admin-metrics"><div class="admin-metric"><strong>' + data.attempts +
      '</strong><span>Exam attempts</span></div><div class="admin-metric"><strong>' +
      data.results + '</strong><span>Results</span></div><div class="admin-metric"><strong>' +
      (data.slots || []).length + '</strong><span>Exam slots</span></div></div>' +
      '<div class="admin-streams">' + streamCards + '</div>' +
      (slotCards ? '<h3 style="margin:18px 0 8px">Configured slots</h3><div class="admin-streams">' + slotCards + '</div>' : '');
  };
  document.getElementById('connect').addEventListener('click', async () => {
    adminKey = keyInput.value.trim();
    try {
      const data = await request('/api/admin/assessment/overview');
      renderOverview(data);
      status('slot-status', 'Administrator access verified.');
    } catch (error) {
      adminKey = '';
      overview.textContent = '';
      status('slot-status', error.message, true);
    }
  });
  document.getElementById('slot-form').addEventListener('submit', async event => {
    event.preventDefault();
    try {
      const payload = {
        stream: document.getElementById('slot-stream').value,
        starts_at: istIso(document.getElementById('slot-start').value),
        ends_at: istIso(document.getElementById('slot-end').value),
        capacity: Number(document.getElementById('slot-capacity').value)
      };
      const data = await request('/api/admin/assessment/slots', {method: 'POST', body: payload});
      status('slot-status', 'Slot created: ' + data.slot_id);
      renderOverview(await request('/api/admin/assessment/overview'));
    } catch (error) { status('slot-status', error.message, true); }
  });
  document.getElementById('assign-form').addEventListener('submit', async event => {
    event.preventDefault();
    try {
      const registrationIds = document.getElementById('registration-ids').value
        .split(/[\s,;]+/).map(value => value.trim()).filter(Boolean);
      const slotId = document.getElementById('assign-slot').value.trim();
      const data = await request('/api/admin/assessment/slots/' + encodeURIComponent(slotId) + '/assign', {
        method: 'POST', body: {registration_ids: registrationIds}
      });
      status('assign-status', data.assigned_count + ' registrations assigned to ' + data.stream + '.');
      renderOverview(await request('/api/admin/assessment/overview'));
    } catch (error) { status('assign-status', error.message, true); }
  });
  document.getElementById('import-bank').addEventListener('click', async () => {
    const file = document.getElementById('question-file').files[0];
    if (!file) { status('import-status', 'Choose the approved question-bank JSON file.', true); return; }
    try {
      const payload = JSON.parse(await file.text());
      const data = await request('/api/admin/assessment/question-banks/import', {method: 'POST', body: payload});
      status('import-status', 'Imported ' + data.question_count + ' questions for ' + data.stream + '.');
      renderOverview(await request('/api/admin/assessment/overview'));
    } catch (error) { status('import-status', error.message, true); }
  });
  window.addEventListener('pagehide', () => { adminKey = ''; });
})();
