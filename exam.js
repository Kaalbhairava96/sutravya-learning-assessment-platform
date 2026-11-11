(() => {
  'use strict';
  const apiBase = document.querySelector('meta[name="sutravya-api-base"]')?.content.trim() || '';
  const content = document.getElementById('exam-content');
  const status = document.getElementById('exam-status');
  const timer = document.getElementById('timer');
  const candidateInfo = document.getElementById('candidate-info');
  let attempt = null;
  let currentPosition = 0;
  let currentQuestion = null;
  let questionInterval = null;
  let overallInterval = null;
  let questionRemaining = 0;
  let overallRemaining = 0;
  let busy = false;
  let moving = false;
  let answeredCount = 0;

  const sectionBlueprints = {
    paramedical:[['anatomy_physiology','Anatomy & Physiology'],['laboratory_sciences','Clinical Laboratory Sciences'],['microbiology_infection_control','Microbiology & Infection Control'],['diagnostic_technology','Diagnostic Technology & Equipment'],['patient_safety_communication','Patient Safety & Communication']],
    nursing:[['nursing_foundations','Nursing Foundations'],['applied_anatomy_physiology','Applied Anatomy & Physiology'],['nutrition_biochemistry','Nutrition & Applied Biochemistry'],['psychology_community','Psychology, Sociology & Community Health'],['infection_safety_ethics','Infection Control, Patient Safety & Ethics']],
    mbbs_ug:[['anatomy','Human Anatomy'],['physiology','Human Physiology'],['biochemistry','Biochemistry'],['foundation_aetcom','Foundation Course, ECE & AETCOM'],['community_research','Community Medicine & Research']],
    mbbs_pg:[['medicine','General Medicine & Clinical Reasoning'],['surgery','General Surgery & Perioperative Care'],['obgyn_paediatrics','Obstetrics, Gynaecology & Paediatrics'],['pathology_pharmacology','Pathology & Pharmacology'],['microbiology_forensic_allied','Microbiology, Forensic & Allied Clinical Subjects']],
    mbbs_1st_year:[['anatomy','Anatomy'],['physiology','Physiology'],['biology','Biology'],['quantitative_reasoning','Mathematics & Analytical Reasoning'],['english_communication','English & Communication']]
  };
  let sections = [];
  const setSections = stream => {
    const source = sectionBlueprints[stream] || sectionBlueprints.paramedical;
    sections = source.map(([key,label],index)=>({key,label,start:index*20,end:(index+1)*20}));
  };
  const message = (text, error = false) => {
    status.textContent = text;
    status.classList.toggle('is-error', error);
    status.classList.toggle('is-success', !error);
  };
  const request = async (path, method = 'GET', body) => {
    if (!apiBase) throw new Error('Assessment API is not configured.');
    const response = await fetch(apiBase + path, {
      method, credentials:'include', cache:'no-store',
      headers: body ? {'Content-Type':'application/json'} : {},
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
    return String(Math.floor(safe / 60)).padStart(2,'0') + ':' + String(safe % 60).padStart(2,'0');
  };
  const stopQuestionTimer = () => { if (questionInterval) clearInterval(questionInterval); questionInterval = null; };
  const stopOverallTimer = () => { if (overallInterval) clearInterval(overallInterval); overallInterval = null; };
  const sectionFor = position => sections.find(section => position >= section.start && position < section.end);
  const renderProgress = () => {
    const currentSection = sectionFor(currentPosition);
    return '<div class="exam-progress"><div class="exam-progress-row"><span>Question ' +
      (currentPosition + 1) + ' of 100</span><b>' + currentSection.label + '</b><span>' +
      Math.round((currentPosition + 1) / 100 * 100) + '%</span></div><div class="exam-progress-track"><i style="width:' +
      ((currentPosition + 1) / 100 * 100) + '%"></i></div><div class="exam-section-strip">' +
      sections.map((section,index) => '<span class="' + (index === sections.indexOf(currentSection) ? 'active' : '') +
      '">' + section.label + '</span>').join('') + '</div></div>';
  };
  const startOverallTimer = seconds => {
    stopOverallTimer();
    overallRemaining = Math.max(0, seconds);
    overallInterval = setInterval(() => {
      overallRemaining = Math.max(0, overallRemaining - 1);
      const node = document.getElementById('overall-clock');
      if (node) node.textContent = formatTime(overallRemaining);
      if (overallRemaining <= 0) {
        stopOverallTimer();
        finish(true).catch(error => message(error.message, true));
      }
    },1000);
  };
  const startQuestionTimer = seconds => {
    stopQuestionTimer();
    questionRemaining = Math.max(0, seconds);
    const node = document.getElementById('question-clock');
    if (node) node.textContent = formatTime(questionRemaining);
    questionInterval = setInterval(() => {
      questionRemaining = Math.max(0, questionRemaining - 1);
      const clock = document.getElementById('question-clock');
      if (clock) clock.textContent = formatTime(questionRemaining);
      if (questionRemaining <= 0) {
        stopQuestionTimer();
        message('Time for this question is over. Moving to the next question.');
        moveNext(true).catch(error => message(error.message, true));
      }
    },1000);
  };
  const renderQuestion = () => {
    if (!currentQuestion) return;
    const q = currentQuestion;
    const section = sectionFor(currentPosition);
    const answered = q.answered || Boolean(q.selected_option_id);
    content.innerHTML = renderProgress() +
      '<div class="exam-question-panel"><div class="exam-question-top"><span class="exam-kicker">' +
      escapeHtml(section.label) + ' · ' + escapeHtml(q.difficulty) + '</span><div class="exam-question-clock"><small>THIS QUESTION</small><strong id="question-clock">' +
      formatTime(questionRemaining) + '</strong></div></div>' +
      '<div class="exam-question-number">QUESTION ' + String(currentPosition + 1).padStart(2,'0') + ' / 100</div>' +
      '<h2 class="exam-question">' + escapeHtml(q.question_text) + '</h2>' +
      '<div class="exam-options">' + q.options.map(option =>
        '<label class="exam-option"><input type="radio" name="answer" value="' + escapeHtml(option.option_id) + '" ' +
        (q.selected_option_id === option.option_id ? 'checked' : '') + '>' +
        '<span><b>' + escapeHtml(option.identifier) + '.</b> ' + escapeHtml(option.option_text) + '</span></label>'
      ).join('') + '</div><div class="exam-actions">' +
      '<span class="exam-saved">' + (answered ? 'Answer saved on server' : 'Select one answer to save') + '</span>' +
      '<button class="exam-button" id="next-question">' + (currentPosition === 99 ? 'Review & submit' : 'Save & continue') + ' →</button>' +
      '</div><p class="exam-muted">Each question has its own server-controlled timer. Once you continue, you cannot return to a previous question.</p></div>';
    content.querySelectorAll('input[name="answer"]').forEach(input => input.addEventListener('change', () => save(input.value)));
    document.getElementById('next-question').addEventListener('click', () => moveNext(false));
  };
  const loadQuestion = async position => {
    if (moving || !attempt || position < 0 || position >= 100) return;
    moving = true;
    stopQuestionTimer();
    currentPosition = position;
    let autoAdvance = false;
    let expiredOverall = false;
    message('Loading question ' + (position + 1) + '…');
    try {
      currentQuestion = await request('/api/exam/attempts/' + attempt.attempt_id + '/questions/' + position);
      questionRemaining = currentQuestion.remaining_seconds;
      renderQuestion();
      startQuestionTimer(questionRemaining);
      message('Your answer is saved securely when selected.');
      autoAdvance = questionRemaining <= 0;
    } catch (error) {
      if (error.message.toLowerCase().includes('time has expired')) expiredOverall = true;
      else message(error.message, true);
    } finally { moving = false; }
    if (expiredOverall) await finish(true);
    else if (autoAdvance) await moveNext(true);
  };
  const logIntegrityEvent = async eventType => {
    if (!attempt || attempt.status !== 'in_progress') return;
    try {
      await request('/api/exam/attempts/' + attempt.attempt_id + '/integrity-events','POST',{event_type:eventType});
    } catch {
      message('Integrity monitoring could not reach the server. Keep the assessment page connected.',true);
    }
  };
  const save = async optionId => {
    if (busy || !currentQuestion || questionRemaining <= 0) return;
    busy = true;
    let autoAdvance = false;
    try {
      await request('/api/exam/attempts/' + attempt.attempt_id + '/answer','PUT',{
        question_id: currentQuestion.question_id, option_id: optionId
      });
      currentQuestion.selected_option_id = optionId;
      currentQuestion.answered = true;
      const saved = document.querySelector('.exam-saved');
      if (saved) saved.textContent = 'Answer saved on server';
      message('Answer saved.');
    } catch (error) {
      message(error.message, true);
      if (error.message.toLowerCase().includes('question time has expired')) {
        stopQuestionTimer();
        autoAdvance = true;
      }
    } finally { busy = false; }
    if (autoAdvance) await moveNext(true);
  };
  const moveNext = async automatic => {
    if (moving || busy || !attempt) return;
    const unanswered = !currentQuestion?.answered && !currentQuestion?.selected_option_id;
    if (!automatic && unanswered) {
      if (!window.confirm('No answer is selected. Skip this question? You cannot return to it.')) return;
      try {
        await request('/api/exam/attempts/' + attempt.attempt_id + '/questions/' + currentPosition + '/skip','POST');
      } catch (error) {
        message(error.message,true);
        return;
      }
    }
    stopQuestionTimer();
    if (currentPosition >= 99) {
      await finish(false);
      return;
    }
    await loadQuestion(currentPosition + 1);
  };
  const start = async () => {
    if (busy) return;
    busy = true;
    try {
      if (document.documentElement.requestFullscreen) {
        try { await document.documentElement.requestFullscreen(); }
        catch { message('Full-screen mode was not available. Your assessment will still be monitored for focus changes.'); }
      }
      attempt = await request('/api/exam/attempts/start','POST');
      if(Array.isArray(attempt.sections)) sections=attempt.sections.map((item,index)=>({key:item.key || item.section,label:item.label || item.key || item.section,start:index*20,end:(index+1)*20}));
      startOverallTimer(attempt.remaining_seconds);
      await loadQuestion(0);
    } catch (error) { message(error.message,true); }
    finally { busy = false; }
  };
  const finish = async automatic => {
    if (!attempt || busy) return;
    if (!automatic && !window.confirm('Submit the complete 100-question assessment? You cannot change answers afterwards.')) return;
    busy = true;
    stopQuestionTimer();
    stopOverallTimer();
    message('Submitting your answers and calculating negative marking…');
    try {
      const result = await request('/api/exam/attempts/' + attempt.attempt_id + '/submit','POST');
      attempt.status = 'submitted';
      renderResult(result);
      timer.textContent = 'Submitted';
      message('Assessment submitted successfully.');
    } catch (error) {
      message(error.message,true);
      if (attempt.status === 'in_progress') {
        startOverallTimer(overallRemaining);
        if (currentQuestion) startQuestionTimer(questionRemaining);
      }
    } finally { busy = false; }
  };
  const renderResult = result => {
    const review = result.review || [];
    const maxScore = 100;
    content.innerHTML = '<div class="exam-result-head"><span class="exam-kicker">HTSE 2026 · RESULT</span><h2>Assessment completed</h2><div class="exam-score">' +
      escapeHtml(result.score) + '<small> / ' + maxScore + '</small></div><p>' +
      result.correct_count + ' correct · ' + result.incorrect_count + ' incorrect · ' +
      result.unanswered_count + ' unanswered</p><p class="exam-muted">Scoring: +1 correct, −0.25 incorrect, 0 unanswered</p></div>' +
      '<h3>Answer review</h3><div class="exam-review">' + review.map((item,index) =>
        '<article class="exam-review-item ' + (item.is_correct ? 'correct' : (item.selected_option ? 'incorrect' : '')) + '">' +
        '<b>Q' + (index + 1) + '. ' + escapeHtml(item.question_text) + '</b>' +
        '<p>Your answer: ' + (item.selected_option ? escapeHtml(item.selected_option.identifier + '. ' + item.selected_option.option_text) : 'Not answered') + '</p>' +
        '<p>Correct answer: <b>' + escapeHtml(item.correct_option.identifier + '. ' + item.correct_option.option_text) + '</b></p>' +
        (item.explanation ? '<p class="exam-muted">' + escapeHtml(item.explanation) + '</p>' : '') +
        '</article>'
      ).join('') + '</div>';
  };
  const showIntro = availability => {
    const slotStart = availability.slot_starts_at
      ? new Date(availability.slot_starts_at).toLocaleString('en-IN',{timeZone:'Asia/Kolkata'}) : 'Not assigned';
    content.innerHTML = '<h2>' + (availability.assigned ? 'Your assessment slot' : 'Slot assignment pending') + '</h2>' +
      '<p class="exam-muted">Stream: ' + escapeHtml(availability.stream) + ' · ' + escapeHtml(slotStart) + '</p>' +
      '<p>100 questions · 5 subject blocks · approximately 47 minutes · +1 / −0.25 / 0 marking.</p>' +
      '<p class="exam-muted">Individual question timers vary from 18 to 45 seconds according to the reading and reasoning required.</p>' +
      '<p class="exam-muted">The assessment opens in full-screen mode. Returning to another tab, leaving full screen, or attempting copy/paste is recorded as an integrity event. No camera recording is used.</p>' +
      '<button id="start-exam" class="exam-button" ' +
      (availability.assigned && availability.opens_now && availability.question_bank_ready ? '' : 'disabled') +
      '>Start assessment</button>';
    document.getElementById('start-exam').addEventListener('click',start);
  };
  const init = async () => {
    try {
      const session = await request('/api/auth/session');
      candidateInfo.textContent = session.full_name + ' · ' + session.registration_id + ' · ' + session.stream;
      setSections(session.stream);
      const availability = await request('/api/exam/availability');
      const current = await request('/api/exam/attempts/current');
      if (current.attempt?.status === 'submitted') {
        attempt = current.attempt;
        timer.textContent = 'Submitted';
        renderResult(current.attempt);
        message('Your submitted result and answer review are available.');
        return;
      }
      if (current.attempt?.status === 'in_progress') {
        attempt = current.attempt;
        startOverallTimer(current.attempt.remaining_seconds);
        await loadQuestion(current.attempt.current_position || 0);
        return;
      }
      showIntro(availability);
      if (availability.opens_now && availability.question_bank_ready) message('Your slot is open. Start when ready.');
    } catch (error) {
      content.innerHTML = '<h2>Sign-in required</h2><p>' + escapeHtml(error.message) +
        '</p><a class="exam-button" href="login.html">Candidate sign in</a>';
      candidateInfo.textContent = 'No active candidate session';
    }
  };
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') logIntegrityEvent('candidate_tab_hidden');
    else if (attempt?.status === 'in_progress') message('Focus returned to the assessment. This event has been recorded.');
  });
  window.addEventListener('blur', () => logIntegrityEvent('candidate_window_blur'));
  document.addEventListener('fullscreenchange', () => {
    if (!document.fullscreenElement && attempt?.status === 'in_progress') {
      logIntegrityEvent('candidate_fullscreen_exit');
      message('Full-screen mode exited. This integrity event has been recorded.',true);
    }
  });
  document.addEventListener('copy', event => {
    if (attempt?.status === 'in_progress') {
      event.preventDefault();
      logIntegrityEvent('candidate_copy_attempt');
      message('Copying is disabled during the assessment.',true);
    }
  });
  document.addEventListener('paste', event => {
    if (attempt?.status === 'in_progress') {
      event.preventDefault();
      logIntegrityEvent('candidate_paste_attempt');
      message('Pasting is disabled during the assessment.',true);
    }
  });
  window.addEventListener('beforeunload', event => {
    if (attempt?.status === 'in_progress') {
      event.preventDefault();
      event.returnValue = '';
    }
  });
  init();
})();
