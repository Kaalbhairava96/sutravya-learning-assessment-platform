(() => {
  const bank = window.HTSE_QUESTION_BANK || {};
  const tabs = [...document.querySelectorAll('[data-sample-tab]')];
  const panels = [...document.querySelectorAll('[data-sample-panel]')];
  if (!tabs.length || !panels.length) return;

  const escapeHTML = (value = '') => String(value).replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const renderStream = key => {
    const panel = panels.find(item => item.dataset.samplePanel === key);
    if (!panel || panel.dataset.rendered === 'true') return;
    const stream = bank[key];
    if (!stream) return;
    const questions = stream.questions.slice(0, 5);
    panel.innerHTML = `<div class="v4-sample-introline"><span>${escapeHTML(stream.label)} practice preview</span><small>5 illustrative questions · answers reveal after selection</small></div>` + questions.map((q, index) => `
      <article class="v4-sample-question" data-sample-question="${index}">
        <div class="v4-sample-qmeta"><span>QUESTION ${String(index + 1).padStart(2,'0')}</span><span>${escapeHTML(q.topic)} · ${escapeHTML(q.difficulty || 'Practice')}</span></div>
        <h3>${escapeHTML(q.question)}</h3>
        <div class="v4-sample-options">${q.options.map((option, optionIndex) => `<button class="v4-sample-option" type="button" data-sample-option="${optionIndex}"><span>${String.fromCharCode(65 + optionIndex)}</span>${escapeHTML(option)}</button>`).join('')}</div>
        <div class="v4-sample-feedback" data-sample-feedback hidden></div>
      </article>`).join('') + `<div class="v4-sample-bottom-cta"><span>Want a complete timed paper?</span><a class="button button-primary" href="mock-test.html">Take the 30-minute mock test →</a></div>`;
    questions.forEach((question, index) => {
      const card = panel.querySelector(`[data-sample-question="${index}"]`);
      const feedback = card.querySelector('[data-sample-feedback]');
      card.querySelectorAll('[data-sample-option]').forEach(button => button.addEventListener('click', () => {
        if (card.dataset.answered === 'true') return;
        card.dataset.answered = 'true';
        const selected = Number(button.dataset.sampleOption);
        const isCorrect = selected === question.answer;
        card.querySelectorAll('[data-sample-option]').forEach((option, optionIndex) => {
          option.disabled = true;
          if (optionIndex === question.answer) option.classList.add('is-correct');
          if (optionIndex === selected && !isCorrect) option.classList.add('is-wrong');
        });
        feedback.hidden = false;
        feedback.className = `v4-sample-feedback ${isCorrect ? 'is-correct' : 'is-wrong'}`;
        feedback.innerHTML = `<b>${isCorrect ? 'Correct — well done.' : 'Not quite. Review the concept.'}</b><p><strong>Answer:</strong> ${escapeHTML(question.options[question.answer])}</p><p>${escapeHTML(question.explanation)}</p>`;
      }));
    });
    panel.dataset.rendered = 'true';
  };
  const activate = key => {
    tabs.forEach(tab => { const active = tab.dataset.sampleTab === key; tab.classList.toggle('is-active', active); tab.setAttribute('aria-selected', String(active)); });
    panels.forEach(panel => { const active = panel.dataset.samplePanel === key; panel.hidden = !active; panel.classList.toggle('is-active', active); });
    if (key !== 'other') renderStream(key);
  };
  tabs.forEach(tab => tab.addEventListener('click', () => activate(tab.dataset.sampleTab)));
  renderStream('paramedical');
})();
