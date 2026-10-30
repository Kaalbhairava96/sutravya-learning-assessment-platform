# Backend schema and candidate-account flow

## Current scope

The backend implements email-OTP registration and passwordless candidate authentication. It does not yet implement slot allocation, candidate exam sessions, exam delivery, scoring, results, or admin workflows. Registration timing is enforced server-side in Asia/Kolkata. The mobile number is collected and normalized but remains unverified.

## Registration and identity

- Before 1 November 2026, authorised team members use the same registration form, endpoints, email OTP, candidate record, Registration ID, and account access as public candidates. `INTERNAL_TEST_MODE=true` plus the private `INTERNAL_TEST_ACCESS_CODE` only authorises starting or continuing the registration journey before opening. New team registrations are ordinary active registrations with `is_internal_test=false` and `registration_source='team_prelaunch'`; after public opening, the code is no longer required, including for a pending team OTP. At the closing deadline, all registration actions are rejected.

- A candidate submits full name, mobile, email, and one allowlisted stream: `paramedical`, `nursing`, or `mbbs_1st_year`.
- Historical rows with `is_internal_test=true` retain that flag and are classified as `legacy_internal_test`; they are excluded from official login and team/public export filters. A real registration for the same candidate/event may coexist with the retained legacy row.
- Email is stripped and lowercased before candidate lookup or persistence. Mobile is normalized to `+91` plus ten digits; it is not verified and is not unique by itself.
- A pending candidate and registration-purpose OTP challenge are persisted before the provider call. The OTP digest is HMAC-SHA-256, bound to the candidate, challenge, channel, and purpose; plaintext exists only in process memory long enough to submit the message.
- Successful verification consumes the challenge, marks email verified, creates the event registration with a random `SUT26-…` ID, records the challenge's `registration_source`, and clears `pending_stream` in one database transaction. A partial unique index on `lower(email)` for verified candidates is the database invariant for verified-email uniqueness.
- The partial unique index `uq_registrations_candidate_event_official` prevents duplicate non-internal registrations for one candidate/event while allowing a preserved legacy test row beside one real registration. A concurrent duplicate email verification can fail at this index; the transaction rolls back as a whole.
- Confirmation email delivery is attempted only after commit. If it fails, the registration remains complete; the generic resend-confirmation endpoint can retry without creating another registration.

## Passwordless login and sessions

- Login OTP challenges use purpose `login`, separate from `registration_verification`. Only a verified candidate with a non-internal, non-legacy event registration is eligible to receive one. Legacy internal-only candidates and legacy OTP challenges cannot authenticate. The request endpoint uses a generic response for known and unknown emails.
- A correct login code is atomically consumed while a candidate session is created. The browser receives a random opaque token in an HttpOnly cookie; only SHA-256(token) is stored in `candidate_sessions`.
- Sessions expire after 24 hours, can be revoked by logout, and are resolved to candidate/registration data server-side. Candidate identity is never accepted from a client-supplied candidate ID. The cookie is HttpOnly and SameSite=Lax; Secure is enabled in production. For reliable cookie behavior, production website and API should use HTTPS hostnames under the same registrable domain (for example, `assessment.sutravya.in` and `api.sutravya.in`). A GitHub Pages origin talking to an unrelated API domain can be treated as third-party cookies by browsers and is not an approved production arrangement for this session design.
- The API only exposes the authenticated account summary at `/api/auth/session`; it does not yet authorize exam APIs because those do not exist.

## Verification protection and rate limiting

`verification_challenges` stores channel, purpose, keyed destination digest, OTP digest, expiry, attempts, and terminal timestamps. Defaults are six digits, five minutes, five incorrect attempts, and a 60-second resend cooldown. Candidate and challenge rows are locked in a consistent order during verification; PostgreSQL concurrency guarantees still require the dedicated integration suite to run against the disposable database.

`rate_limit_buckets` stores counters by scope and HMAC-keyed subject digest, not raw email or IP. Current application limits are configured in route code and use a one-hour window. Global email submission is capped at 1,000 per hour. These values are initial operational defaults, not a measured abuse-control policy. The structured logger emits safe provider-failure and rate-limit events without recipient, IP, OTP, token, or provider response details. A retention/cleanup job for old buckets should be configured before launch. Behind a reverse proxy, configure trusted proxy handling before relying on client-IP rate limits; the current code deliberately does not trust arbitrary forwarded headers.

## Provider and configuration

Resend is called using its email API over HTTPS. Configure `RESEND_API_KEY` and `RESEND_FROM_EMAIL` only in the backend's private environment. The sending domain/from address must be authenticated and enabled in Resend before live delivery. Keep `OTP_HMAC_PEPPER` private, independent from the provider key, and at least 32 UTF-8 bytes. Configure exact `CORS_ORIGINS` and the API base URL on each static page when the API is deployed. The API key and pepper are excluded from settings representations and logs. `.env.example` contains placeholders only; the actual `backend/.env` is not part of this implementation or review.

Provider calls occur after database transactions commit. If OTP delivery fails, the challenge is invalidated and the API returns a safe unavailable response; it does not claim the code was sent. If confirmation delivery fails after registration commit, the registration remains and can be recovered through the resend endpoint.

## Organiser registration export

There is no existing admin authentication route. `GET /api/admin/registrations/export` is protected by the private `REGISTRATION_EXPORT_KEY`, which must be at least 32 characters and is compared in constant time. Omit `source` or use `source=all` to export all event registrations; the accepted filters are `team_prelaunch` and `public_registration`. The UTF-8-BOM CSV contains registration ID, candidate contact fields, stream, IST registration timestamp, email/mobile verification state, and source. Text cells are protected against spreadsheet formula execution. The key is accepted only in `X-Registration-Export-Key`; request logs do not include headers or exported data. Use `scripts/export_registrations.ps1` from an organiser's local PowerShell session; its prompt is secure and it writes into the local Downloads folder by default.

## Registration timing

Registration start, email verification, and OTP resend are enforced by the server through **15 November 2026, 11:59:59 PM Asia/Kolkata**. Slot allocation is not implemented, so the later booking step still needs to be integrated with this deadline.

## Schema and migration history

Historical revisions `0001_backend_foundation` through `0006_reg_source` are preserved. Revision `0007_legacy_classification` corrects historical flagged rows to `legacy_internal_test` in both registrations and verification challenges, preserving flags, candidate identities, Registration IDs, OTP records, and registration uniqueness. It safely replaces the source check constraints and supports fresh installations as well as databases already at 0006. Downgrade fails closed while legacy rows exist. Inspect the current revision before applying `upgrade head`.

The core tables remain: candidates, registrations, exam slots, question banks, questions, answer options, attempts, responses, scoring rules, results, admin users, audit events, and verification challenges. `answer_options.is_correct` remains private server-side data and must not be returned by candidate APIs.

## Remaining operational limits

No real Resend email has been delivered or verified in production. PostgreSQL registration/login concurrency, cookie behavior across the intended hostnames, database backups/restore, rate-limit retention, monitoring/alerting, and load behavior remain unverified. Do not treat this phase as production-ready. No exam functionality is included.
