(() => {
  const bank = window.HTSE_QUESTION_BANK || {};
  const streamButtons = [...document.querySelectorAll('[data-mock-stream]')];
  const testPanel = document.querySelector('#mock-test-panel');
  const intro = document.querySelector('#mock-start');
  const resultsPanel = document.querySelector('#mock-results');
  if (!streamButtons.length || !testPanel || !resultsPanel) return;

  const totalSeconds = 30 * 60;
  const state = { streamKey: null, questions: [], current: 0, answers: new Map(), review: new Set(), deadline: 0, interval: null, submitted: false };
  const $ = selector => document.querySelector(selector);
  const escapeHTML = (value = '') => String(value).replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const shuffle = items => { const copy = [...items]; for (let i=copy.length-1;i>0;i--) { const j=Math.floor(Math.random()*(i+1)); [copy[i],copy[j]]=[copy[j],copy[i]]; } return copy; };
  const formatTime = seconds => `${String(Math.floor(seconds / 60)).padStart(2,'0')}:${String(seconds % 60).padStart(2,'0')}`;
  const answeredCount = () => state.answers.size;
  const activeQuestion = () => state.questions[state.current];

  function start(streamKey) {
    const stream = bank[streamKey];
    if (!stream || stream.questions.length !== 100) {
      window.alert('This practice paper is not available yet. Please contact the organiser for stream mapping.');
      return;
    }
    if (state.interval) window.clearInterval(state.interval);
    state.streamKey = streamKey;
    state.questions = shuffle(stream.questions);
    state.current = 0;
    state.answers = new Map();
    state.review = new Set();
    state.deadline = Date.now() + totalSeconds * 1000;
    state.submitted = false;
    intro.hidden = true;
    resultsPanel.hidden = true;
    testPanel.hidden = false;
    $('[data-test-title]').textContent = `${stream.label} Practice Mock Test`;
    $('[data-test-subtitle]').textContent = '100 questions · 30 minutes · 1 mark per correct answer · no negative marking';
    renderNavigator();
    renderQuestion();
    updateTimer();
    state.interval = window.setInterval(updateTimer, 1000);
    testPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function updateTimer() {
    if (state.submitted) return;
    const remaining = Math.max(0, Math.ceil((state.deadline - Date.now()) / 1000));
    const timer = $('[data-test-timer]');
    timer.textContent = formatTime(remaining);
    timer.closest('.v4-timer').classList.toggle('is-warning', remaining <= 300);
    if (remaining <= 0) submit(true);
  }

  function renderQuestion() {
    const q = activeQuestion();
    if (!q) return;
    $('[data-question-index]').textContent = `QUESTION ${state.current + 1} OF 100`;
    $('[data-question-topic]').textContent = `${q.topic} · ${q.difficulty || 'Practice'}`;
    $('[data-question-text]').textContent = q.question;
    const chosen = state.answers.get(state.current);
    $('[data-answer-options]').innerHTML = q.options.map((option, index) => {
      const selected = chosen === index;
      return `<button type="button" class="v4-answer-option ${selected ? 'is-selected' : ''}" data-answer-option="${index}" aria-pressed="${selected}"><span>${String.fromCharCode(65 + index)}</span><b>${escapeHTML(option)}</b></button>`;
    }).join('');
    $('[data-answer-options]').querySelectorAll('[data-answer-option]').forEach(button => button.addEventListener('click', () => {
      if (state.submitted) return;
      state.answers.set(state.current, Number(button.dataset.answerOption));
      renderQuestion();
      renderNavigator();
    }));
    const marked = state.review.has(state.current);
    $('[data-mark-review]').classList.toggle('is-marked', marked);
    $('[data-mark-review]').textContent = marked ? '★ Marked for review' : '☆ Mark for review';
    $('[data-prev-question]').disabled = state.current === 0;
    $('[data-next-question]').textContent = state.current === 99 ? 'Review answers →' : 'Next →';
    const progress = ((state.current + 1) / 100) * 100;
    $('[data-test-progress]').style.width = `${progress}%`;
  }

  function renderNavigator() {
    const grid = $('[data-question-grid]');
    grid.innerHTML = state.questions.map((_, index) => {
      const answered = state.answers.has(index);
      const review = state.review.has(index);
      const current = state.current === index;
      return `<button type="button" class="v4-qnav ${answered ? 'is-answered' : ''} ${review ? 'is-review' : ''} ${current ? 'is-current' : ''}" data-qnav="${index}" aria-label="Question ${index + 1}${answered ? ', answered' : ''}${review ? ', marked for review' : ''}" aria-current="${current ? 'step' : 'false'}">${index + 1}</button>`;
    }).join('');
    grid.querySelectorAll('[data-qnav]').forEach(button => button.addEventListener('click', () => { state.current = Number(button.dataset.qnav); renderQuestion(); renderNavigator(); }));
    $('[data-answered-count]').textContent = `${answeredCount()} / 100 answered`;
  }

  function submit(auto = false, confirmed = false) {
    if (state.submitted) return;
    if (!auto && !confirmed) {
      const missing = 100 - answeredCount();
      const prompt = missing ? `You have ${missing} unanswered question(s). Submit your practice test now?` : 'Submit your practice test now?';
      if (!window.confirm(prompt)) return;
    }
    state.submitted = true;
    if (state.interval) window.clearInterval(state.interval);
    const correct = state.questions.reduce((sum, q, index) => sum + (state.answers.get(index) === q.answer ? 1 : 0), 0);
    const wrong = [...state.answers.entries()].filter(([index, answer]) => answer !== state.questions[index].answer).length;
    const unanswered = 100 - state.answers.size;
    const percent = correct;
    $('[data-results-stream]').textContent = `${bank[state.streamKey].label} · ${auto ? 'Time expired — test auto-submitted' : 'Submitted successfully'} · Practice mode`;
    $('[data-score]').textContent = String(correct);
    $('[data-correct]').textContent = String(correct);
    $('[data-wrong]').textContent = String(wrong);
    $('[data-unanswered]').textContent = String(unanswered);
    $('[data-percent]').textContent = `${percent}%`;
    $('[data-score-ring]').style.setProperty('--score-angle', `${percent * 3.6}deg`);
    buildTopicBreakdown();
    buildAnswerReview();
    $('[data-review-toggle]').textContent = 'Review answers ↓';
    $('[data-answer-review]').hidden = true;
    testPanel.hidden = true;
    resultsPanel.hidden = false;
    resultsPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function buildTopicBreakdown() {
    const groups = new Map();
    state.questions.forEach((q, index) => {
      if (!groups.has(q.topic)) groups.set(q.topic, { total: 0, correct: 0 });
      const group = groups.get(q.topic); group.total++;
      if (state.answers.get(index) === q.answer) group.correct++;
    });
    $('[data-topic-breakdown]').innerHTML = `<div class="v4-topic-breakdown-head"><h3>Topic-wise practice review</h3><p>Use this to identify areas for revision, not as an official competency score.</p></div><div class="v4-topic-breakdown-grid">${[...groups.entries()].map(([topic, data]) => `<div class="v4-topic-score"><div><b>${escapeHTML(topic)}</b><span>${data.correct}/${data.total}</span></div><i><span style="width:${data.total ? data.correct/data.total*100 : 0}%"></span></i></div>`).join('')}</div>`;
  }

  function buildAnswerReview() {
    $('[data-answer-review]').innerHTML = `<h3>Answer review</h3>${state.questions.map((q, index) => {
      const userAnswer = state.answers.has(index) ? state.answers.get(index) : null;
      const isCorrect = userAnswer === q.answer;
      const label = userAnswer === null ? 'Not answered' : (isCorrect ? 'Correct' : 'Incorrect');
      return `<article class="v4-review-item ${isCorrect ? 'is-correct' : (userAnswer === null ? 'is-unanswered' : 'is-wrong')}"><div class="v4-review-meta"><span>QUESTION ${index + 1} · ${escapeHTML(q.topic)}</span><b>${label}</b></div><h4>${escapeHTML(q.question)}</h4><p><strong>Your answer:</strong> ${userAnswer === null ? 'Not answered' : escapeHTML(q.options[userAnswer])}</p><p><strong>Correct answer:</strong> ${escapeHTML(q.options[q.answer])}</p><p class="v4-review-explanation">${escapeHTML(q.explanation)}</p></article>`;
    }).join('')}`;
  }

  streamButtons.forEach(button => button.addEventListener('click', () => start(button.dataset.mockStream)));
  $('[data-prev-question]').addEventListener('click', () => { if (state.current > 0) { state.current--; renderQuestion(); renderNavigator(); } });
  $('[data-next-question]').addEventListener('click', () => { if (state.current < 99) { state.current++; renderQuestion(); renderNavigator(); } else { const unanswered = 100 - answeredCount(); const message = unanswered ? `You have ${unanswered} unanswered question(s). Submit your practice test now?` : 'You have reached the end of the paper. Submit your practice test now?'; if (window.confirm(message)) submit(false, true); } });
  $('[data-mark-review]').addEventListener('click', () => { state.review.has(state.current) ? state.review.delete(state.current) : state.review.add(state.current); renderQuestion(); renderNavigator(); });
  $('[data-submit-test]').addEventListener('click', () => submit(false));
  $('[data-retake]').addEventListener('click', () => start(state.streamKey));
  $('[data-review-toggle]').addEventListener('click', event => { const panel = $('[data-answer-review]'); panel.hidden = !panel.hidden; event.currentTarget.textContent = panel.hidden ? 'Review answers ↓' : 'Hide answer review ↑'; if (!panel.hidden) panel.scrollIntoView({ behavior: 'smooth', block: 'start' }); });
})();
