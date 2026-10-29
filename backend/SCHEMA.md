# Backend schema and candidate-account flow

## Current scope

The backend implements email-OTP registration and passwordless candidate authentication. It does not yet implement slot allocation, candidate exam sessions, exam delivery, scoring, results, admin workflows, or registration deadline enforcement. The mobile number is collected and normalized but remains unverified.

## Registration and identity

- A candidate submits full name, mobile, email, and one allowlisted stream: `paramedical`, `nursing`, or `mbbs_1st_year`.
- Email is stripped and lowercased before candidate lookup or persistence. Mobile is normalized to `+91` plus ten digits; it is not verified and is not unique by itself.
- A pending candidate and registration-purpose OTP challenge are persisted before the provider call. The OTP digest is HMAC-SHA-256, bound to the candidate, challenge, channel, and purpose; plaintext exists only in process memory long enough to submit the message.
- Successful verification consumes the challenge, marks email verified, creates the event registration with a random `SUT26-…` ID, and clears `pending_stream` in one database transaction. A partial unique index on `lower(email)` for verified candidates is the database invariant for verified-email uniqueness.
- The unique `(candidate_id, event_key)` constraint prevents duplicate registrations for one candidate/event. A concurrent duplicate email verification can fail at the partial unique index; the transaction rolls back as a whole.
- Confirmation email delivery is attempted only after commit. If it fails, the registration remains complete; the generic resend-confirmation endpoint can retry without creating another registration.

## Passwordless login and sessions

- Login OTP challenges use purpose `login`, separate from `registration_verification`. Only a verified candidate with an event registration is eligible to receive one. The request endpoint uses a generic response for known and unknown emails.
- A correct login code is atomically consumed while a candidate session is created. The browser receives a random opaque token in an HttpOnly cookie; only SHA-256(token) is stored in `candidate_sessions`.
- Sessions expire after 24 hours, can be revoked by logout, and are resolved to candidate/registration data server-side. Candidate identity is never accepted from a client-supplied candidate ID. The cookie is HttpOnly and SameSite=Lax; Secure is enabled in production. For reliable cookie behavior, production website and API should use HTTPS hostnames under the same registrable domain (for example, `assessment.sutravya.in` and `api.sutravya.in`). A GitHub Pages origin talking to an unrelated API domain can be treated as third-party cookies by browsers and is not an approved production arrangement for this session design.
- The API only exposes the authenticated account summary at `/api/auth/session`; it does not yet authorize exam APIs because those do not exist.

## Verification protection and rate limiting

`verification_challenges` stores channel, purpose, keyed destination digest, OTP digest, expiry, attempts, and terminal timestamps. Defaults are six digits, five minutes, five incorrect attempts, and a 60-second resend cooldown. Candidate and challenge rows are locked in a consistent order during verification; PostgreSQL concurrency guarantees still require the dedicated integration suite to run against the disposable database.

`rate_limit_buckets` stores counters by scope and HMAC-keyed subject digest, not raw email or IP. Current application limits are configured in route code and use a one-hour window. Global email submission is capped at 1,000 per hour. These values are initial operational defaults, not a measured abuse-control policy. The structured logger emits safe provider-failure and rate-limit events without recipient, IP, OTP, token, or provider response details. A retention/cleanup job for old buckets should be configured before launch. Behind a reverse proxy, configure trusted proxy handling before relying on client-IP rate limits; the current code deliberately does not trust arbitrary forwarded headers.

## Provider and configuration

Resend is called using its email API over HTTPS. Configure `RESEND_API_KEY` and `RESEND_FROM_EMAIL` only in the backend's private environment. The sending domain/from address must be authenticated and enabled in Resend before live delivery. Keep `OTP_HMAC_PEPPER` private, independent from the provider key, and at least 32 UTF-8 bytes. Configure exact `CORS_ORIGINS` and the API base URL on each static page when the API is deployed. The API key and pepper are excluded from settings representations and logs. `.env.example` contains placeholders only; the actual `backend/.env` is not part of this implementation or review.

Provider calls occur after database transactions commit. If OTP delivery fails, the challenge is invalidated and the API returns a safe unavailable response; it does not claim the code was sent. If confirmation delivery fails after registration commit, the registration remains and can be recovered through the resend endpoint.

## Registration timing decision

The product rule says registration, verification, and slot booking must finish by **15 November 2026, 11:59:59 PM Asia/Kolkata**. This phase does not enforce that deadline. Because slot booking is not implemented, the product owner must confirm whether the final registration step will later include slot assignment before the deadline.

## Schema and migration history

Historical revisions `0001_backend_foundation`, `0002_core_application_schema`, and `0003_secure_verify` are preserved. Revision `0004_registration_accounts` adds `candidates.pending_stream`, the partial verified-email unique index, registration public ID and stream columns, registration/login challenge purposes, candidate sessions, and rate-limit buckets. The migration has not been applied to production. The current disposable database's state must be checked using the approved database rehearsal procedure before applying it there.

The core tables remain: candidates, registrations, exam slots, question banks, questions, answer options, attempts, responses, scoring rules, results, admin users, audit events, and verification challenges. `answer_options.is_correct` remains private server-side data and must not be returned by candidate APIs.

## Remaining operational limits

No real Resend email has been delivered or verified in production. PostgreSQL registration/login concurrency, cookie behavior across the intended hostnames, database backups/restore, rate-limit retention, monitoring/alerting, and load behavior remain unverified. Do not treat this phase as production-ready. No exam functionality is included.
