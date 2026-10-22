# Initial application schema

This schema is persistence only. It does not implement registration, authentication, allocation, exam delivery, scoring, result approval, or publication.

## Tables and relationships

The eleven requested core entities are implemented, with `question_banks` added so every question belongs to a named, separately manageable bank. All primary keys are UUIDs. Mutable records have UTC-capable `created_at` and `updated_at` timestamps; append-only slot and audit records have `created_at`.

| Table | Main relationships and purpose |
| --- | --- |
| `candidates` | One candidate can have registrations. Only name, email, and phone placeholders are present; contact collection still needs approval. |
| `registrations` | Belongs to a candidate and event key; can be assigned to an exam slot later. |
| `exam_slots` | Event key, start/end timestamps, and optional capacity. Capacity remains null until confirmed. |
| `question_banks` | Groups questions, scoring-rule configurations, and attempts without assuming an unapproved assessment policy. |
| `questions` | Belongs to one question bank; has optional category, explanation, and source reference fields. Inactive by default. |
| `answer_options` | Belongs to a question. `is_correct` is private server-side scoring data, never a candidate response field. |
| `exam_attempts` | Belongs to a registration, slot, and question bank. The application must verify that the selected slot and bank are valid for that registration. |
| `candidate_responses` | Belongs to an attempt and question; selected option is nullable for unanswered questions. |
| `scoring_rules` | Belongs to a question bank. Correct, incorrect, and unanswered points are nullable and have no defaults pending approved scoring rules. |
| `results` | One result per attempt. Decimal score is stored; approval and release timestamps/admin are optional. No rank field is included. |
| `admin_users` | Stores an email, password hash, optional role key, and disabled-by-default account flag. Login and role policy are not implemented. |
| `audit_events` | Append-only action, actor ID, request ID, and target reference. No arbitrary payload field is provided to reduce the chance of storing passwords, tokens, answer keys, or candidate details. |

## Constraints and application responsibilities

- A unique `(candidate_id, event_key)` constraint prevents repeat registration for the same event. Email/phone are not unique because identity and shared-contact rules are not approved.
- A unique `(question_id, identifier)` constraint prevents duplicate option labels. A partial unique index permits at most one `is_correct = true` option per question. **Application-level bank validation must also require exactly one correct option** before a bank can be activated.
- A composite foreign key ensures a selected option belongs to the response's question. Unique `(attempt_id, question_id)` prevents duplicate response rows; the application will update an existing response when a candidate changes an answer.
- Unique `(registration_id, attempt_number)` prevents duplicate attempt numbers, but does not impose a maximum number of attempts. The allowed-attempt policy remains unapproved.
- A unique result `attempt_id` prevents duplicate result records. Decimal `NUMERIC` values are used for points and scores so fractional marks can be represented; precision/scale can be revised after scoring rules are approved.
- Slot end-after-start and positive-if-set capacity checks are database constraints. They do not stop overbooking by themselves.
- **Future slot allocation must be a single database transaction:** lock the target slot row with `SELECT ... FOR UPDATE`, count registrations already assigned while holding that lock, reject if a confirmed capacity is reached, assign the registration, then commit. Every allocation path must take the same lock. PostgreSQL concurrency behavior still needs integration testing.
- Cross-record rules (registration event vs slot event, attempt bank/slot eligibility, exact answer-option count, approved time windows, allowed attempt count, scoring completeness, and result-release policy) require application validation; no exam policies are inferred here.
- `event_key`, slot schedule, capacity, status values, identity fields, scoring values, admin roles, and result approval/release process are placeholders for approved requirements, not policy decisions.

## Sensitive data boundaries

There are no password, OTP, session-token, or candidate-response-text columns. Admin authentication must later store only a reviewed password hash. Correctness is stored on `answer_options` and must only be read by server-side scoring code. Candidate-facing DTOs should explicitly select option identifiers and text, and must not serialize ORM models. The separate written activity is not modeled as an exam response until QualiNova confirms whether it is a separate assessment and approves its workflow.

## Migration

`0002_core_application_schema` follows the empty `0001_backend_foundation` baseline. It creates only these application tables and their own indexes. Downgrade drops only tables introduced in revision 0002, in reverse dependency order. The migration has not been applied to any database.
