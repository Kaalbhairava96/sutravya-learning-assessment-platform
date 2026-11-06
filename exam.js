(() => {
  'use strict';
  const apiBase = document.querySelector('meta[name="sutravya-api-base"]')?.content.trim() || '';
  const content = document.getElementById('exam-content');
  const status = document.getElementById('exam-status');
  const timer = document.getElementById('timer');
  const candidateInfo = document.getElementById('candidate-info');
  let attempt = null;
  let currentIndex = 0;
  let countdown = null;
  let remaining = 0;
  let busy = false;

  const message = (text, error = false) => {
    status.textContent = text;
    status.style.color = error ? '#a22d2d' : '#456176';
  };
  const request = async (path, method = 'GET', body) => {
    if (!apiBase) throw new Error('Assessment API is not configured.');
    const response = await fetch(apiBase + path, {
      method,
      credentials: 'include',
      cache: 'no-store',
      headers: body ? {'Content-Type': 'application/json'} : {},
      body: body ? JSON.stringify(body) : undefined
    });
    let data = {};
    try { data = await response.json(); } catch {}
    if (!response.ok) throw new Error(data.detail || 'Assessment request could not be completed.');
    return data;
  };
  const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  }[char]));
  const formatTime = seconds => {
    const safe = Math.max(0, seconds);
    return String(Math.floor(safe / 60)).padStart(2, '0') + ':' + String(safe % 60).padStart(2, '0');
  };
  const stopTimer = () => { if (countdown) clearInterval(countdown); countdown = null; };
  const startTimer = seconds => {
    stopTimer();
    remaining = Math.max(0, seconds);
    timer.textContent = formatTime(remaining);
    countdown = setInterval(() => {
      remaining = Math.max(0, remaining - 1);
      timer.textContent = formatTime(remaining);
      if (remaining === 0) {
        stopTimer();
        submit(true).catch(error => message(error.message, true));
      }
    }, 1000);
  };
  const showIntro = (availability) => {
    const start = availability.slot_starts_at ? new Date(availability.slot_starts_at).toLocaleString('en-IN', {timeZone:'Asia/Kolkata'}) : '';
    content.innerHTML = '<h2>' + (availability.assigned ? 'Your assessment slot' : 'Slot assignment pending') + '</h2>' +
      '<p class="exam-muted">' + (availability.assigned
        ? 'Stream: ' + escapeHtml(availability.stream) + ' · ' + escapeHtml(start)
        : 'Your registration is eligible. The organiser has not assigned an exam slot yet.') + '</p>' +
      '<p>' + (availability.question_bank_ready
        ? 'Your paper is ready: 100 MCQs, 30 minutes, no negative marking.'
        : 'The organiser is still preparing your question paper. Please check again later.') + '</p>' +
      '<button id="start-exam" class="exam-button" ' +
      (availability.assigned && availability.opens_now && availability.question_bank_ready ? '' : 'disabled') +
      '>Start / resume assessment</button>';
    document.getElementById('start-exam').addEventListener('click', start);
  };
  const renderQuestion = () => {
    if (!attempt || attempt.status !== 'in_progress') return;
    const question = attempt.questions[currentIndex];
    const answered = attempt.questions.filter(item => item.selected_option_id).length;
    content.innerHTML =
      '<div class="exam-q-meta"><span>Question ' + (currentIndex + 1) + ' of ' + attempt.questions.length +
      '</span><span>' + answered + ' answered</span></div>' +
      '<h2 class="exam-question">' + escapeHtml(question.question_text) + '</h2>' +
      '<div class="exam-options">' + question.options.map(option =>
        '<label class="exam-option"><input type="radio" name="answer" value="' + escapeHtml(option.option_id) + '" ' +
        (question.selected_option_id === option.option_id ? 'checked' : '') + '>' +
        '<span><b>' + escapeHtml(option.identifier) + '.</b> ' + escapeHtml(option.option_text) + '</span></label>'
      ).join('') + '</div>' +
      '<div class="exam-actions"><button class="exam-button secondary" id="previous" ' + (currentIndex === 0 ? 'disabled' : '') + '>Previous</button>' +
      '<button class="exam-button secondary" id="next" ' + (currentIndex === attempt.questions.length - 1 ? 'disabled' : '') + '>Next</button>' +
      '<button class="exam-button" id="submit">Submit assessment</button></div>' +
      '<p class="exam-muted">Answers are saved when you select an option. Keep this page open until submission is confirmed.</p>' +
      '<div class="exam-nav">' + attempt.questions.map((item, index) =>
        '<button type="button" data-question-index="' + index + '" class="' +
        (index === currentIndex ? 'current ' : '') + (item.selected_option_id ? 'answered' : '') +
        '" aria-label="Go to question ' + (index + 1) + '">' + (index + 1) + '</button>'
      ).join('') + '</div>';
    content.querySelectorAll('input[name="answer"]').forEach(input => input.addEventListener('change', () => save(input.value)));
    document.getElementById('previous').addEventListener('click', () => { currentIndex--; renderQuestion(); });
    document.getElementById('next').addEventListener('click', () => { currentIndex++; renderQuestion(); });
    document.getElementById('submit').addEventListener('click', () => submit(false));
    content.querySelectorAll('[data-question-index]').forEach(button => button.addEventListener('click', () => {
      currentIndex = Number(button.dataset.questionIndex);
      renderQuestion();
    }));
  };
  const save = async optionId => {
    if (busy || remaining <= 0) return;
    const question = attempt.questions[currentIndex];
    busy = true;
    try {
      await request('/api/exam/attempts/' + attempt.attempt_id + '/answer', 'PUT', {
        question_id: question.question_id, option_id: optionId
      });
      question.selected_option_id = optionId;
      message('Answer saved.');
      renderQuestion();
    } catch (error) {
      message(error.message + ' Your previous saved answer is unchanged.', true);
      renderQuestion();
    } finally {
      busy = false;
      if (remaining <= 0 && attempt?.status === 'in_progress') {
        submit(true).catch(error => message(error.message, true));
      }
    }
  };
  const start = async () => {
    if (busy) return;
    busy = true;
    message('Opening your assessment…');
    try {
      attempt = await request('/api/exam/attempts/start', 'POST');
      currentIndex = 0;
      startTimer(attempt.remaining_seconds);
      renderQuestion();
      message('Assessment started. Your answers are saved as you go.');
    } catch (error) { message(error.message, true); }
    finally { busy = false; }
  };
  const submit = async automatic => {
    if (!attempt || attempt.status !== 'in_progress' || busy) return;
    if (!automatic && !window.confirm('Submit your assessment now? You cannot change answers after submission.')) return;
    busy = true;
    stopTimer();
    message('Submitting and calculating your result…');
    try {
      const result = await request('/api/exam/attempts/' + attempt.attempt_id + '/submit', 'POST');
      attempt.status = 'submitted';
      renderResult(result);
      timer.textContent = 'Submitted';
      message('Your assessment has been submitted successfully.');
    } catch (error) {
      message(error.message, true);
      if (!automatic && remaining > 0) startTimer(remaining);
    } finally { busy = false; }
  };
  const renderResult = result => {
    const review = result.review || [];
    content.innerHTML = '<span class="exam-muted">ASSESSMENT RESULT</span><h2>Submission complete</h2>' +
      '<div class="exam-score">' + escapeHtml(result.score) + '</div>' +
      '<p>' + result.correct_count + ' correct · ' + result.incorrect_count + ' incorrect · ' +
      result.unanswered_count + ' unanswered out of ' + result.total_questions + '</p>' +
      '<p class="exam-muted">Submitted: ' + escapeHtml(new Date(result.submitted_at).toLocaleString('en-IN', {timeZone:'Asia/Kolkata'})) + '</p>' +
      '<h3>Answer review</h3><div class="exam-review">' + review.map((item, index) =>
        '<article class="exam-review-item ' + (item.is_correct ? 'correct' : (item.selected_option ? 'incorrect' : '')) + '">' +
        '<b>Q' + (index + 1) + '. ' + escapeHtml(item.question_text) + '</b>' +
        '<p>Your answer: ' + (item.selected_option ? escapeHtml(item.selected_option.identifier + '. ' + item.selected_option.option_text) : 'Not answered') + '</p>' +
        '<p>Correct answer: <b>' + escapeHtml(item.correct_option.identifier + '. ' + item.correct_option.option_text) + '</b></p>' +
        (item.explanation ? '<p class="exam-muted">' + escapeHtml(item.explanation) + '</p>' : '') +
        '</article>'
      ).join('') + '</div>';
  };
  const init = async () => {
    try {
      const session = await request('/api/auth/session');
      candidateInfo.textContent = session.full_name + ' · ' + session.registration_id + ' · ' + session.stream;
      const availability = await request('/api/exam/availability');
      const current = await request('/api/exam/attempts/current');
      if (current.attempt?.status === 'submitted') {
        attempt = current.attempt;
        timer.textContent = 'Submitted';
        renderResult(current.attempt);
        message('Your submitted assessment and answer review are available.');
        return;
      }
      if (current.attempt?.status === 'in_progress') {
        attempt = current.attempt;
        currentIndex = 0;
        startTimer(attempt.remaining_seconds);
        renderQuestion();
        message('Your saved assessment has been resumed.');
        return;
      }
      showIntro(availability);
      if (availability.opens_now && availability.question_bank_ready) message('Your slot is open. Start your assessment when ready.');
    } catch (error) {
      content.innerHTML = '<h2>Sign-in required</h2><p>' + escapeHtml(error.message) + '</p><a class="exam-button" href="login.html">Candidate sign in</a>';
      candidateInfo.textContent = 'No active candidate session';
    }
  };
  init();
})();
