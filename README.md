# Sutrāvya Learning & Assessment Platform

Public event website and a FastAPI foundation for the Nursing Talent Hunt Exam at Bihar Healthcare Conclave 2026. Qualinova organises the event; Sutrāvya provides assessment technology.

## Public website

The static pages describe the event, awards, syllabus, sample papers, FAQs, contact channels, and candidate email-OTP sign-in. The registration form collects full name, mobile, email, and stream. Its registration flow requires the backend to be deployed and configured; mobile is collected but is not verified. GitHub Pages stages an explicit public-file allowlist and does not package backend configuration, database files, question banks, or answer keys.

## Current backend scope

The backend uses FastAPI, SQLAlchemy, PostgreSQL/Psycopg, and Alembic as one application. It implements email-OTP registration and passwordless login foundations. It does **not** yet implement exam slots, exam delivery, answer saving, scoring, results, or admin workflows. The proposed event date and business policies remain subject to organiser approval.

See [`backend/SCHEMA.md`](backend/SCHEMA.md) for the flow, schema, migration history, rate limits, and unverified operational work.

## Local development (PowerShell)

Use Python 3.11 or newer. From the repository root:

```powershell
Set-Location .\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

Edit the private `backend/.env` locally. Set `APP_ENV=development`, an available PostgreSQL `DATABASE_URL`, and an `OTP_HMAC_PEPPER` with at least 32 UTF-8 bytes. For email delivery, set `RESEND_API_KEY` and `RESEND_FROM_EMAIL` using values from the private Resend account. Do not commit `.env` or paste its values into logs or support messages. No `.env` values are included in this repository.

Start the API from `backend/`:

```powershell
uvicorn app.main:app --reload --no-access-log
```

Serve the static pages from another PowerShell window at `http://127.0.0.1:5500` so browser requests have a normal origin. Configure `CORS_ORIGINS=http://127.0.0.1:5500` in the backend environment. Set the `sutravya-api-base` meta tag on `index.html` and `login.html` only after the API URL is known.

```powershell
Set-Location ..
python -m http.server 5500
```

Liveness check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Before using registration, apply Alembic migrations only to an explicitly selected development/test database:

```powershell
alembic upgrade head
```

In test mode, the existing guard accepts only the approved disposable target `sutravya_m3_test` at `127.0.0.1:55432`. Never point test mode at a shared or production database.

Offline unit tests:

```powershell
python -m unittest discover -s tests -p test_registration.py -v
```

The PostgreSQL integration suite is separate and requires an explicitly configured, verified disposable PostgreSQL database migrated to the current head:

```powershell
# Configure the dedicated variable; do not inherit the generic application DATABASE_URL.
$env:SUTRAVYA_POSTGRES_TEST_DATABASE_URL = 'postgresql+psycopg://sutravya_m3_test:local_only_rehearsal@127.0.0.1:55432/sutravya_m3_test'
python -m unittest discover -s tests -p test_postgres_integration.py -v
```

Never run PostgreSQL integration tests against a shared or production database. The tests verify their guarded database identity and required Alembic revision before executing.

## Email provider setup

The Resend adapter calls the Resend Email API. A live sender requires a Resend account/API key and an authenticated sending domain/from address; verify current provider requirements and account limits before launch. Do not put provider keys in frontend files. `RESEND_API_KEY` belongs only in the backend's secret configuration. The browser API origin must be configured in the `<meta name="sutravya-api-base">` element on the home and candidate sign-in pages, and the backend must allow the static website's exact origin through `CORS_ORIGINS`.

## Safe launch checklist

1. Obtain written confirmation of exam dates, streams, eligibility, registration deadline, slot policy, and candidate communications.
2. Provision a managed PostgreSQL database and private backend hosting; keep the static site on a CDN under a Sutrāvya custom domain, with the API on a sibling subdomain so cookie sessions remain same-site. Set production secrets in the host, not in Git.
3. Review and apply migration `0004_registration_accounts` to the intended production database through an approved deployment window and backup plan.
4. Authenticate the Resend sending domain; verify OTP, confirmation, retry, and bounce/failure behavior using test recipients.
5. Configure exact production CORS origins, HTTPS, Secure/HttpOnly cookie behavior, API base URL, monitoring, rate-limit cleanup, backups, and restore procedure.
6. Run separate PostgreSQL concurrency/integrity tests and a rehearsed registration/login/load test. Verify email enumeration resistance, session expiry/revocation, and recovery.
7. Have an experienced engineer available during the event. No production smoke test, delivery test, load result, backup restore, or production migration is claimed by this implementation.

No paid hosting or provider resources were created by this work.


### Candidate exam engine (implementation branch)

The implementation branch now includes authenticated candidate exam availability,
start/resume, answer persistence, timed submission and post-submission scoring
endpoints. The question banks must be provisioned separately and must contain
100 active MCQs per stream, four options per question, one correct answer, and
an approved `htse_2026` scoring rule. Correct answers are not returned while an
attempt is in progress.

The organiser question-bank/slot management interface, production database
upgrade/backup plan, PostgreSQL integration run, and 1,000-session load test are
still pending. Do not treat this branch as exam-day production-ready.


The implementation branch also includes a noindex organiser page at `/admin.html`
and key-protected organiser APIs for slot creation, same-stream registration
assignment, question-bank import and an aggregate overview. Configure a separate
private `ADMIN_API_KEY` (minimum 32 bytes) in the API service environment before
using the organiser tools. The key is not embedded in the website.


A candidate exam portal is available at `/exam.html`; it is linked from the
candidate sign-in page after an authenticated session is confirmed. It resumes
active attempts and persisted submitted results, saves answers through the API,
and presents the answer review only after submission.


### HTSE common-foundation paper format
The candidate assessment is configured for five common-foundation sections of 20
questions each: Anatomy, Physiology, Biology, Mathematics & Analytical Reasoning,
and English & Communication. The paper uses +1 for correct, −0.25 for incorrect,
and 0 for unanswered. Each question has its own server-enforced timer and shuffled
option order; candidates receive one question at a time and cannot revisit passed
questions. The overall attempt ceiling is 55 minutes, while question-level timers
are individually configured (15–60 seconds).


The candidate portal also requests full-screen mode, blocks page copy/paste, and
records authenticated focus/visibility/full-screen integrity events against the
attempt. These controls are deterrents and audit signals, not a guarantee against
external devices or off-screen assistance.


## Website visual system

- `styles.css` is the shared SUTRAVYA/QualiNova visual system and owns the single brand-token block, component styling, page treatments and responsive rules.
- `layout.css` is a layout-only compatibility module extracted from the prior stylesheet. It contains no colour declarations or brand tokens.
- The public-site build copies only explicitly allowlisted pages, scripts, original partner logos, favicon and page-specific brand illustrations into `assessment-public/`.
- Every public page loads both shared stylesheets and the DM Sans / Manrope typography.
- SUTRAVYA is the primary technology partner identity; QualiNova is clearly identified as event organiser.
- Avoid adding one-off global colour overrides or additional token blocks. Update the canonical tokens in `styles.css`.
