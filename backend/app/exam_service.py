"""Candidate exam delivery, answer persistence and result calculation.

The service deliberately fails closed until an organiser has configured a slot,
100 active questions, four options per question and an approved scoring rule.
Correct answers are never included in an in-progress attempt response.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    AnswerOption,
    AuditEvent,
    Candidate,
    CandidateResponse,
    CandidateSession,
    ExamAttempt,
    ExamSlot,
    Question,
    QuestionBank,
    Registration,
    Result,
    ScoringRule,
)
from app.registration import EVENT_KEY, PUBLIC_REGISTRATION_SOURCE, TEAM_PRELAUNCH_SOURCE

EXAM_MAX_DURATION_SECONDS = 55 * 60
QUESTION_COUNT = 100
OPTIONS_PER_QUESTION = 4
SCORING_RULE_CODE = "htse_2026"


class ExamError(ValueError):
    def __init__(self, code: str, status_code: int = 400) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _candidate_registration(session: Session, raw_token: str | None, *, lock: bool = False):
    if not raw_token:
        raise ExamError("authentication_required", 401)
    digest = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    statement = (
        select(Registration, Candidate)
        .join(Candidate, Candidate.id == Registration.candidate_id)
        .join(CandidateSession, CandidateSession.candidate_id == Candidate.id)
        .where(
            CandidateSession.token_digest == digest,
            CandidateSession.revoked_at.is_(None),
            CandidateSession.expires_at > datetime.now(timezone.utc),
            Candidate.email_verified_at.is_not(None),
            Registration.event_key == EVENT_KEY,
            Registration.is_internal_test.is_(False),
            Registration.registration_source.in_((PUBLIC_REGISTRATION_SOURCE, TEAM_PRELAUNCH_SOURCE)),
            Registration.status == "active",
        )
    )
    if lock:
        statement = statement.with_for_update()
    row = session.execute(statement).first()
    if row is None:
        raise ExamError("eligible_registration_required", 403)
    registration, candidate = row
    slot = session.get(ExamSlot, registration.exam_slot_id) if registration.exam_slot_id else None
    return registration, candidate, slot


def _bank_for_stream(session: Session, stream: str) -> QuestionBank:
    bank = session.scalar(select(QuestionBank).where(QuestionBank.bank_code == stream))
    if bank is None:
        raise ExamError("exam_not_configured", 503)
    return bank


def _question_set(session: Session, bank: QuestionBank) -> list[Question]:
    questions = list(session.scalars(
        select(Question)
        .where(Question.question_bank_id == bank.id, Question.is_active.is_(True))
        .options(selectinload(Question.options))
        .order_by(Question.id)
    ).all())
    if len(questions) != QUESTION_COUNT:
        raise ExamError("question_bank_incomplete", 503)
    for question in questions:
        options = list(question.options)
        if len(options) != OPTIONS_PER_QUESTION or sum(1 for option in options if option.is_correct) != 1:
            raise ExamError("question_bank_invalid", 503)
    return questions


def _scoring_rule(session: Session, bank: QuestionBank) -> ScoringRule:
    rule = session.scalar(select(ScoringRule).where(
        ScoringRule.question_bank_id == bank.id,
        ScoringRule.rule_code == SCORING_RULE_CODE,
    ))
    if (
        rule is None
        or rule.correct_points is None
        or rule.incorrect_points is None
        or rule.unanswered_points is None
        or rule.correct_points != Decimal('1')
        or rule.incorrect_points != Decimal('-0.25')
        or rule.unanswered_points != 0
    ):
        raise ExamError("scoring_rule_not_configured", 503)
    return rule


def _deadline(attempt: ExamAttempt, slot: ExamSlot) -> datetime:
    started = _aware(attempt.started_at)
    return min(started + timedelta(seconds=EXAM_MAX_DURATION_SECONDS), _aware(slot.ends_at))


def _question_payload(session: Session, question: Question, *, reveal: bool) -> dict:
    options = list(question.options)
    payload = {
        "question_id": str(question.id),
        "question_text": question.question_text,
        "category": question.category,
        "options": [
            {"option_id": str(option.id), "identifier": option.identifier, "option_text": option.option_text}
            for option in options
        ],
    }
    if reveal:
        correct = next(option for option in options if option.is_correct)
        payload["correct_option"] = {
            "option_id": str(correct.id),
            "identifier": correct.identifier,
            "option_text": correct.option_text,
        }
        payload["explanation"] = question.explanation
    return payload


def exam_availability(session: Session, raw_token: str | None, *, now: datetime | None = None) -> dict:
    current = _aware(now or datetime.now(timezone.utc))
    registration, _candidate, slot = _candidate_registration(session, raw_token)
    if slot is None:
        return {"eligible": True, "assigned": False, "stream": registration.stream, "message": "Exam slot is not assigned yet."}
    if slot.stream != registration.stream:
        raise ExamError("exam_slot_stream_mismatch", 409)
    bank = session.scalar(select(QuestionBank).where(QuestionBank.bank_code == registration.stream))
    count = 0
    ready = False
    if bank is not None:
        count = int(session.scalar(
            select(func.count(Question.id)).where(
                Question.question_bank_id == bank.id, Question.is_active.is_(True)
            )
        ) or 0)
        try:
            _ordered_questions(session, bank)
            _scoring_rule(session, bank)
            ready = True
        except ExamError:
            ready = False
    return {
        "eligible": True,
        "assigned": True,
        "stream": registration.stream,
        "slot_starts_at": _aware(slot.starts_at).isoformat(),
        "slot_ends_at": _aware(slot.ends_at).isoformat(),
        "opens_now": _aware(slot.starts_at) <= current < _aware(slot.ends_at),
        "question_bank_ready": ready,
        "question_count": count,
    }


def _ordered_questions(session: Session, bank: QuestionBank) -> list[Question]:
    questions = _question_set(session, bank)
    section_order = ("anatomy", "physiology", "biology", "quantitative_reasoning", "english_communication")
    grouped = {section: [] for section in section_order}
    for question in questions:
        if question.section not in grouped:
            raise ExamError("question_bank_invalid", 503)
        grouped[question.section].append(question)
    if any(len(grouped[section]) != 20 for section in section_order):
        raise ExamError("question_bank_invalid", 503)
    ordered = []
    for section in section_order:
        secrets.SystemRandom().shuffle(grouped[section])
        ordered.extend(grouped[section])
    return ordered


def start_exam(session: Session, raw_token: str | None, *, now: datetime | None = None) -> dict:
    current = _aware(now or datetime.now(timezone.utc))
    with session.begin():
        registration, _candidate, slot = _candidate_registration(session, raw_token, lock=True)
        if slot is None:
            raise ExamError("exam_slot_not_assigned", 409)
        if slot.stream != registration.stream:
            raise ExamError("exam_slot_stream_mismatch", 409)
        if not (_aware(slot.starts_at) <= current < _aware(slot.ends_at)):
            raise ExamError("exam_slot_not_open", 409)
        bank = _bank_for_stream(session, registration.stream or "")
        questions = _ordered_questions(session, bank)
        _scoring_rule(session, bank)
        if slot.capacity is not None:
            active_attempts = int(session.scalar(select(func.count(ExamAttempt.id)).where(
                ExamAttempt.exam_slot_id == slot.id,
                ExamAttempt.status == "in_progress",
                ExamAttempt.started_at > current - timedelta(seconds=EXAM_MAX_DURATION_SECONDS),
            )) or 0)
            existing_for_registration = session.scalar(select(ExamAttempt.id).where(
                ExamAttempt.registration_id == registration.id,
                ExamAttempt.status == "in_progress",
            ))
            if active_attempts >= slot.capacity and existing_for_registration is None:
                raise ExamError("exam_slot_capacity_reached", 429)
        existing = session.scalar(select(ExamAttempt).where(
            ExamAttempt.registration_id == registration.id
        ).order_by(ExamAttempt.attempt_number.desc()).with_for_update())
        if existing is not None:
            if existing.status != "in_progress":
                raise ExamError("attempt_already_submitted", 409)
            attempt = existing
        else:
            attempt = ExamAttempt(
                registration_id=registration.id, exam_slot_id=slot.id,
                question_bank_id=bank.id, attempt_number=1,
                status="in_progress", started_at=current,
            )
            session.add(attempt)
            session.flush()
            for position, question in enumerate(questions):
                identifiers = [option.identifier for option in question.options]
                secrets.SystemRandom().shuffle(identifiers)
                session.add(CandidateResponse(
                    attempt_id=attempt.id, question_id=question.id, position=position,
                    option_order=identifiers,
                ))
            session.flush()
        due = _deadline(attempt, slot)
        total_seconds = sum(question.time_limit_seconds for question in questions)
        return {
            "attempt_id": str(attempt.id), "status": attempt.status,
            "total_questions": len(questions), "total_question_time_seconds": total_seconds,
            "overall_deadline": due.isoformat(),
            "remaining_seconds": max(0, int((due - current).total_seconds())),
            "sections": [{"section": section, "question_count": 20} for section in
                ("anatomy", "physiology", "biology", "quantitative_reasoning", "english_communication")],
        }


def get_question(session: Session, raw_token: str | None, *, attempt_id: UUID,
                 position: int, now: datetime | None = None) -> dict:
    current = _aware(now or datetime.now(timezone.utc))
    with session.begin():
        registration, _candidate, _slot = _candidate_registration(session, raw_token, lock=True)
        attempt = session.scalar(select(ExamAttempt).where(
            ExamAttempt.id == attempt_id, ExamAttempt.registration_id == registration.id
        ).with_for_update())
        if attempt is None:
            raise ExamError("attempt_not_found", 404)
        if attempt.status != "in_progress":
            raise ExamError("attempt_not_in_progress", 409)
        slot = session.get(ExamSlot, attempt.exam_slot_id)
        if current >= _deadline(attempt, slot):
            raise ExamError("exam_time_expired", 410)
        responses = session.scalars(select(CandidateResponse).where(
            CandidateResponse.attempt_id == attempt.id
        ).order_by(CandidateResponse.position).with_for_update()).all()
        presented = [row.position for row in responses if row.presented_at is not None]
        active_position = max(presented) if presented else -1
        if position < active_position:
            raise ExamError("question_already_passed", 409)
        if position > active_position + 1:
            raise ExamError("question_sequence_locked", 409)
        if active_position >= 0 and position == active_position + 1:
            previous = next(row for row in responses if row.position == active_position)
            if (
                previous.selected_option_id is None
                and previous.deadline_at is not None
                and current < _aware(previous.deadline_at)
            ):
                raise ExamError("question_time_not_complete", 409)
        response = next((row for row in responses if row.position == position), None)
        if response is None:
            raise ExamError("question_not_found", 404)
        question = session.scalar(select(Question).where(
            Question.id == response.question_id, Question.is_active.is_(True)
        ).options(selectinload(Question.options)))
        if question is None:
            raise ExamError("question_not_found", 404)
        if response.presented_at is None:
            response.presented_at = current
            response.deadline_at = min(
                current + timedelta(seconds=question.time_limit_seconds), _deadline(attempt, slot)
            )
            session.flush()
        deadline = _aware(response.deadline_at)
        options_by_key = {option.identifier: option for option in question.options}
        option_order = response.option_order or ["A", "B", "C", "D"]
        return {
            "question_id": str(question.id), "position": position, "total_questions": QUESTION_COUNT,
            "section": question.section, "category": question.category,
            "difficulty": question.difficulty, "question_text": question.question_text,
            "time_limit_seconds": question.time_limit_seconds,
            "remaining_seconds": max(0, int((deadline - current).total_seconds())),
            "deadline": deadline.isoformat(),
            "selected_option_id": str(response.selected_option_id) if response.selected_option_id else None,
            "answered": response.selected_option_id is not None,
            "options": [
                {"option_id": str(options_by_key[key].id), "identifier": key,
                 "option_text": options_by_key[key].option_text}
                for key in option_order if key in options_by_key
            ],
        }

def record_integrity_event(
    session: Session, raw_token: str | None, *, attempt_id: UUID,
    event_type: str,
) -> dict:
    allowed = {
        "candidate_tab_hidden", "candidate_window_blur", "candidate_fullscreen_exit",
        "candidate_copy_attempt", "candidate_paste_attempt",
    }
    if event_type not in allowed:
        raise ExamError("invalid_integrity_event", 422)
    with session.begin():
        registration, _candidate, _slot = _candidate_registration(session, raw_token, lock=True)
        attempt = session.scalar(select(ExamAttempt).where(
            ExamAttempt.id == attempt_id, ExamAttempt.registration_id == registration.id
        ).with_for_update())
        if attempt is None:
            raise ExamError("attempt_not_found", 404)
        if attempt.status != "in_progress":
            raise ExamError("attempt_not_in_progress", 409)
        session.add(AuditEvent(
            action=event_type, target_type="exam_attempt", target_id=attempt.id,
        ))
        return {"recorded": True}


def skip_question(session: Session, raw_token: str | None, *, attempt_id: UUID,
                  position: int, now: datetime | None = None) -> dict:
    current = _aware(now or datetime.now(timezone.utc))
    with session.begin():
        registration, _candidate, _slot = _candidate_registration(session, raw_token, lock=True)
        attempt = session.scalar(select(ExamAttempt).where(
            ExamAttempt.id == attempt_id, ExamAttempt.registration_id == registration.id
        ).with_for_update())
        if attempt is None:
            raise ExamError("attempt_not_found", 404)
        if attempt.status != "in_progress":
            raise ExamError("attempt_not_in_progress", 409)
        response = session.scalar(select(CandidateResponse).where(
            CandidateResponse.attempt_id == attempt.id,
            CandidateResponse.position == position,
        ).with_for_update())
        if response is None or response.presented_at is None:
            raise ExamError("question_not_presented", 409)
        if response.selected_option_id is not None:
            return {"skipped": False, "answered": True, "position": position}
        if response.deadline_at is None:
            raise ExamError("question_not_presented", 409)
        if current < _aware(response.deadline_at):
            response.deadline_at = current
        return {"skipped": True, "position": position}


def save_answer(
    session: Session, raw_token: str | None, *, attempt_id: UUID,
    question_id: UUID, option_id: UUID, now: datetime | None = None,
) -> dict:
    current = _aware(now or datetime.now(timezone.utc))
    with session.begin():
        registration, _candidate, _slot = _candidate_registration(session, raw_token, lock=True)
        attempt = session.scalar(select(ExamAttempt).where(
            ExamAttempt.id == attempt_id,
            ExamAttempt.registration_id == registration.id,
        ).with_for_update())
        if attempt is None:
            raise ExamError("attempt_not_found", 404)
        if attempt.status != "in_progress":
            raise ExamError("attempt_not_in_progress", 409)
        slot = session.get(ExamSlot, attempt.exam_slot_id)
        question = session.scalar(select(Question).where(
            Question.id == question_id,
            Question.question_bank_id == attempt.question_bank_id,
            Question.is_active.is_(True),
        ))
        option = session.scalar(select(AnswerOption).where(
            AnswerOption.id == option_id,
            AnswerOption.question_id == question_id,
        ))
        if question is None or option is None:
            raise ExamError("invalid_question_or_option", 422)
        response = session.scalar(select(CandidateResponse).where(
            CandidateResponse.attempt_id == attempt.id,
            CandidateResponse.question_id == question.id,
        ).with_for_update())
        if response is None or response.presented_at is None or response.deadline_at is None:
            raise ExamError("question_not_presented", 409)
        active_position = session.scalar(select(func.max(CandidateResponse.position)).where(
            CandidateResponse.attempt_id == attempt.id,
            CandidateResponse.presented_at.is_not(None),
        ))
        if response.position != active_position:
            raise ExamError("question_already_passed", 409)
        if current >= _aware(response.deadline_at):
            raise ExamError("question_time_expired", 410)
        response.selected_option_id = option.id
        response.answered_at = current
        return {"saved": True, "question_id": str(question.id), "position": response.position}


def submit_exam(session: Session, raw_token: str | None, *, attempt_id: UUID, now: datetime | None = None) -> dict:
    current = _aware(now or datetime.now(timezone.utc))
    with session.begin():
        registration, _candidate, _slot = _candidate_registration(session, raw_token, lock=True)
        attempt = session.scalar(select(ExamAttempt).where(
            ExamAttempt.id == attempt_id,
            ExamAttempt.registration_id == registration.id,
        ).with_for_update())
        if attempt is None:
            raise ExamError("attempt_not_found", 404)
        if attempt.status == "submitted":
            result = session.scalar(select(Result).where(Result.attempt_id == attempt.id))
            if result is None:
                raise ExamError("result_not_available", 503)
            return _result_payload(session, attempt, result)
        if attempt.status != "in_progress":
            raise ExamError("attempt_not_in_progress", 409)
        bank = session.get(QuestionBank, attempt.question_bank_id)
        questions = _question_set(session, bank)
        rule = _scoring_rule(session, bank)
        response_rows = {
            row.question_id: row.selected_option_id
            for row in session.scalars(select(CandidateResponse).where(CandidateResponse.attempt_id == attempt.id))
        }
        correct_count = 0
        incorrect_count = 0
        unanswered_count = 0
        for question in questions:
            selected_id = response_rows.get(question.id)
            if selected_id is None:
                unanswered_count += 1
                continue
            selected = next(
                (option for option in question.options if option.id == selected_id),
                None,
            )
            if selected is not None and selected.is_correct:
                correct_count += 1
            else:
                incorrect_count += 1
        score = (
            Decimal(correct_count) * Decimal(rule.correct_points)
            + Decimal(incorrect_count) * Decimal(rule.incorrect_points)
            + Decimal(unanswered_count) * Decimal(rule.unanswered_points)
        )
        attempt.status = "submitted"
        attempt.submitted_at = current
        result = Result(attempt_id=attempt.id, score=score)
        session.add(result)
        session.flush()
        return _result_payload(session, attempt, result)


def _result_payload(session: Session, attempt: ExamAttempt, result: Result) -> dict:
    questions = _question_set(session, session.get(QuestionBank, attempt.question_bank_id))
    response_records = session.scalars(select(CandidateResponse).where(
        CandidateResponse.attempt_id == attempt.id
    )).all()
    response_rows = {row.question_id: row.selected_option_id for row in response_records}
    position_by_question = {row.question_id: row.position for row in response_records}
    questions.sort(key=lambda question: position_by_question.get(question.id, 10_000))
    review = []
    correct_count = 0
    incorrect_count = 0
    unanswered_count = 0
    for question in questions:
        payload = _question_payload(session, question, reveal=True)
        selected_id = response_rows.get(question.id)
        selected = next(
            (option for option in payload["options"] if option["option_id"] == str(selected_id)),
            None,
        )
        correct_id = payload["correct_option"]["option_id"]
        if selected is None:
            unanswered_count += 1
        elif selected["option_id"] == correct_id:
            correct_count += 1
        else:
            incorrect_count += 1
        payload["selected_option"] = selected
        payload["is_correct"] = bool(selected and selected["option_id"] == correct_id)
        review.append(payload)
    return {
        "attempt_id": str(attempt.id),
        "status": "submitted",
        "score": str(result.score),
        "correct_count": correct_count,
        "incorrect_count": incorrect_count,
        "unanswered_count": unanswered_count,
        "total_questions": len(questions),
        "submitted_at": _aware(attempt.submitted_at).isoformat(),
        "review": review,
    }


def get_current_attempt(session: Session, raw_token: str | None, *, now: datetime | None = None) -> dict:
    registration, _candidate, _slot = _candidate_registration(session, raw_token)
    attempt = session.scalar(
        select(ExamAttempt)
        .where(ExamAttempt.registration_id == registration.id)
        .order_by(ExamAttempt.attempt_number.desc())
        .limit(1)
    )
    if attempt is None:
        return {"attempt": None}
    return {"attempt": get_attempt(session, raw_token, attempt_id=attempt.id, now=now)}


def get_attempt(session: Session, raw_token: str | None, *, attempt_id: UUID,
               now: datetime | None = None) -> dict:
    current = _aware(now or datetime.now(timezone.utc))
    registration, _candidate, _slot = _candidate_registration(session, raw_token)
    attempt = session.scalar(select(ExamAttempt).where(
        ExamAttempt.id == attempt_id, ExamAttempt.registration_id == registration.id
    ))
    if attempt is None:
        raise ExamError("attempt_not_found", 404)
    if attempt.status == "submitted":
        result = session.scalar(select(Result).where(Result.attempt_id == attempt.id))
        if result is None:
            raise ExamError("result_not_available", 503)
        return _result_payload(session, attempt, result)
    if attempt.status != "in_progress":
        raise ExamError("attempt_not_in_progress", 409)
    slot = session.get(ExamSlot, attempt.exam_slot_id)
    responses = session.scalars(select(CandidateResponse).where(
        CandidateResponse.attempt_id == attempt.id
    )).all()
    presented = [row.position for row in responses if row.presented_at is not None]
    due = _deadline(attempt, slot)
    return {
        "attempt_id": str(attempt.id), "status": "in_progress",
        "total_questions": QUESTION_COUNT,
        "current_position": max(presented) if presented else 0,
        "deadline": due.isoformat(),
        "remaining_seconds": max(0, int((due - current).total_seconds())),
    }
