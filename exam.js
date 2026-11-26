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
  let completedPositions = new Set();
  let answeredPositions = new Set();
  let skippedPositions = new Set();
  let visitedPositions = new Set();

  const sectionBlueprints = {
    nursing:[['anatomy','Anatomy'],['physiology','Physiology'],['biochemistry','Biochemistry'],['healthcare_it','Healthcare IT'],['oet_english','Healthcare English (OET-style)']],
    paramedical:[['anatomy','Anatomy'],['physiology','Physiology'],['biochemistry','Biochemistry'],['healthcare_it','Healthcare IT'],['oet_english','Healthcare English (OET-style)']],
    pharmacy:[['anatomy','Anatomy'],['physiology','Physiology'],['biochemistry','Biochemistry'],['healthcare_it','Healthcare IT'],['oet_english','Healthcare English (OET-style)']]
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
      sections.map((section,index) => {
        const state=index<sections.indexOf(currentSection)?'complete':index===sections.indexOf(currentSection)?'active':'upcoming';
        const status=state==='complete'?'section completed':state==='active'?'current section':'not yet reached';
        return '<span class="'+state+'" aria-label="'+escapeHtml(section.label)+', '+status+'"><i aria-hidden="true">'+String(index+1).padStart(2,'0')+'</i>'+escapeHtml(section.label)+'</span>';
      }).join('') + '</div><p class="exam-navigator-note">Sequential assessment · previous questions lock when you continue</p></div>';
  };
  const startOverallTimer = seconds => {
    stopOverallTimer();
    overallRemaining = Math.max(0, seconds);
    document.body.classList.add("exam-in-progress");
    const label=document.getElementById("timer-label"); if(label)label.textContent="TIME REMAINING";
    if(timer)timer.textContent=formatTime(overallRemaining);
    overallInterval = setInterval(() => {
      overallRemaining = Math.max(0, overallRemaining - 1);
      const node = document.getElementById('overall-clock');
      if (node) node.textContent = formatTime(overallRemaining);
      if(timer)timer.textContent=formatTime(overallRemaining);
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
  const renderQuestionNavigator = () => {
    const answered=answeredPositions.size;
    const skipped=skippedPositions.size;
    const visited=visitedPositions.size;
    return '<aside class="exam-question-navigator" aria-label="Question status navigator">' +
      '<div class="exam-question-navigator-head"><b>Question navigator</b><span>Jump to any question</span></div>' +
      '<p class="exam-question-navigator-count">'+answered+' answered · '+skipped+' unanswered · '+Math.max(0,100-visited)+' not visited</p>' +
      '<div class="exam-question-nav-grid">' + Array.from({length:100},(_,index)=>{
        const current=index===currentPosition;
        const isAnswered=answeredPositions.has(index);
        const wasVisited=visitedPositions.has(index);
        const state=current?'current':isAnswered?'answered':wasVisited?'visited':'upcoming';
        const label='Question '+(index+1)+', '+(state==='current'?'current question':state==='answered'?'answered':state==='visited'?'visited, unanswered':'not visited');
        return '<button type="button" class="exam-question-nav-item is-'+state+'" data-jump-question="'+index+'" aria-label="'+label+'" aria-current="'+(current?'step':'false')+'">'+(index+1)+'</button>';
      }).join('') + '</div><div class="exam-question-nav-legend"><span><i class="is-answered"></i> Answered</span><span><i class="is-visited"></i> Visited, unanswered</span><span><i class="is-current"></i> Current</span><span><i class="is-upcoming"></i> Not visited</span></div>' +
      '<p class="exam-question-nav-locked">You can revisit questions and change answers at any time before submitting or the 30-minute timer expires.</p></aside>';
  };
  const renderQuestion = () => {
    if (!currentQuestion) return;
    const q = currentQuestion;
    const section = sectionFor(currentPosition);
    const answered = q.answered || Boolean(q.selected_option_id);
    content.innerHTML = renderProgress() +
      '<div class="exam-active-layout"><div class="exam-question-panel"><div class="exam-question-top"><span class="exam-kicker">' +
      escapeHtml(section.label) + ' · ' + escapeHtml(q.difficulty || 'Assessment') + '</span><div class="exam-question-clock"><small>OVERALL TIME LEFT</small><strong id="overall-clock">' +
      formatTime(overallRemaining) + '</strong></div></div>' +
      '<div class="exam-question-number">QUESTION ' + String(currentPosition + 1).padStart(2,'0') + ' / 100</div>' +
      '<h2 class="exam-question">' + escapeHtml(q.question_text) + '</h2>' +
      '<div class="exam-options">' + q.options.map(option =>
        '<label class="exam-option"><input type="radio" name="answer" value="' + escapeHtml(option.option_id) + '" ' +
        (q.selected_option_id === option.option_id ? 'checked' : '') + '>' +
        '<span><b>' + escapeHtml(option.identifier) + '.</b> ' + escapeHtml(option.option_text) + '</span></label>'
      ).join('') + '</div><div class="exam-actions">' +
      '<span class="exam-saved">' + (answered ? 'Answer saved on server · You can change it' : 'Select an answer or leave this question unanswered') + '</span>' +
      '<div class="exam-question-nav-actions"><button class="exam-button exam-button-secondary" id="previous-question" '+(currentPosition===0?'disabled':'')+'>← Previous</button>' +
      '<button class="exam-button" id="next-question">' + (currentPosition === 99 ? 'Review & submit' : 'Next question →') + '</button></div>' +
      '</div><p class="exam-muted">You have 30 minutes for all 100 questions. Move freely between questions, change answers, and leave any question unanswered.</p></div>' + renderQuestionNavigator() + '</div>';
    content.querySelectorAll('input[name="answer"]').forEach(input => input.addEventListener('change', () => save(input.value)));
    document.getElementById('previous-question').addEventListener('click', () => { if(currentPosition>0) loadQuestion(currentPosition-1); });
    document.getElementById('next-question').addEventListener('click', () => moveNext(false));
    content.querySelectorAll('[data-jump-question]').forEach(button => button.addEventListener('click', () => loadQuestion(Number(button.dataset.jumpQuestion))));
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
      visitedPositions.add(position);
      if (currentQuestion.answered || currentQuestion.selected_option_id) { answeredPositions.add(position); skippedPositions.delete(position); completedPositions.add(position); }
      else { answeredPositions.delete(position); skippedPositions.add(position); }
      renderQuestion();
      
      message('Your answer is saved securely when selected.');
      autoAdvance = false;
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
    if (busy || !currentQuestion || overallRemaining <= 0) return;
    busy = true;
    try {
      await request('/api/exam/attempts/' + attempt.attempt_id + '/answer','PUT',{
        question_id: currentQuestion.question_id, option_id: optionId
      });
      currentQuestion.selected_option_id = optionId;
      currentQuestion.answered = true;
      answeredPositions.add(currentPosition);
      skippedPositions.delete(currentPosition);
      visitedPositions.add(currentPosition);
      completedPositions.add(currentPosition);
      const saved = document.querySelector('.exam-saved');
      if (saved) saved.textContent = 'Answer saved on server · You can change it';
      const navCount=content.querySelector('.exam-question-navigator-count');
      if(navCount)navCount.textContent=answeredPositions.size+' answered · '+skippedPositions.size+' unanswered · '+Math.max(0,100-visitedPositions.size)+' not visited';
      content.querySelectorAll('[data-jump-question]').forEach(button=>{
        if(Number(button.dataset.jumpQuestion)===currentPosition)button.className='exam-question-nav-item is-answered';
      });
      message('Answer saved. You can change it before submitting.');
    } catch (error) {
      message(error.message, true);
      if (error.message.toLowerCase().includes('exam time has expired')) await finish(true);
    } finally { busy = false; }
  };
  const moveNext = async automatic => {
    if (moving || busy || !attempt) return;
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
      document.body.classList.remove('exam-in-progress');
      const label=document.getElementById('timer-label'); if(label)label.textContent='SESSION STATUS';
      timer.textContent = 'Submitted';
      message('Assessment submitted successfully.');
    } catch (error) {
      message(error.message,true);
      if (attempt.status === 'in_progress') {
        startOverallTimer(overallRemaining);
  
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
      '<p>100 questions · 5 common subjects · 30 minutes total · +1 / −0.25 / 0 marking.</p>' +
      '<p class="exam-muted">Self-paced assessment: start any time between 10:00 AM and 6:00 PM IST on 6 December 2026. Your 30-minute timer begins when you start.</p>' +
      '<div class="exam-access-guidance"><b>How your self-paced window works</b><span>Start any time between 10:00 AM and 6:00 PM IST on Sunday, 6 December 2026. Once started, you have 30 minutes total. You may revisit questions and change answers until submission or time expiry.</span></div>' +
      (availability.question_bank_ready ? '' : '<div class="exam-bank-pending" role="status"><b>Official examination paper is being finalised.</b><span>The assessment remains locked until the organiser loads the confidential question bank. Your registration and slot assignment are محفوظ.</span></div>') +
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
      content.innerHTML = '<div class="exam-signin-required"><span aria-hidden="true">🔐</span><span class="exam-kicker">SECURE CANDIDATE ACCESS</span><h2>Sign-in required</h2><p>Your examination is available only to a signed-in candidate with an eligible registration and assigned slot. Sign in using the email registered with your application.</p><a class="exam-button" href="login.html">Candidate sign in →</a><a class="exam-text-link" href="register.html">Not registered yet? View registration</a></div>';
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
