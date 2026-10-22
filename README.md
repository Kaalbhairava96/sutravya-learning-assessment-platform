# Sutrāvya Learning Assessment Platform

Candidate information site and assessment platform prototype for the Nursing Talent Hunt Exam at Bihar Healthcare Conclave 2026. The event is organised by Qualinova; Sutrāvya is the test and assessment partner.

## Public information pages

- `index.html` — event and exam overview, registration interface preview, and exam details postcard
- `awards.html` — ₹50,000 / ₹25,000 / ₹10,000 top-three cash awards
- `syllabus.html` — proposed nursing syllabus framework, marked pending nursing-panel approval
- `sample-papers.html` — illustrative MCQ questions with answer explanations
- `faqs.html` — candidate questions and answer details
- `contact.html` — organiser, assessment partner, and support-channel information
- `styles.css`, `site.js` — shared responsive design and page interactions
- `assets/sutravya-logo.png` — supplied Sutrāvya logo

## Event details in this prototype

- Nursing Talent Hunt Exam: 4 November 2026, 11:00 AM IST, online
- Bihar Healthcare Conclave: 11 December 2026
- MCQ score is shown after submission; candidate result screens are intended to show scores only
- Digital-health idea activity is independent and evaluated by a panel; its score is released separately

The year 2026 is inferred from the conclave and current project context. Confirm before public launch if the exam date refers to a different year.

## Current limitations

This is a static front-end prototype. The registration form does not save or transmit candidate data. There is no authentication, live exam engine, database, admin panel, or panel-review workflow yet. The final syllabus blueprint, question counts, duration, scoring rules, eligibility, and official contact channels must be confirmed with Qualinova before publication.

## Data and infrastructure direction

For the event application, use managed PostgreSQL for candidate records, exam answers, scores, and reviewer decisions. Store uploaded project files in private object storage and keep file references in the database. Add role-based access, encrypted connections and backups, an audit trail for score changes, and a retention/deletion schedule agreed with the organisers.

## Run locally

Open `index.html` in a browser, or serve this folder with any static HTTP server. The Google Fonts import needs network access; the page otherwise uses system fallbacks.

## Backend foundation (local only)

The API is a separate FastAPI application in `backend/`. The public HTML pages remain static and continue to deploy through GitHub Pages. The Pages workflow now stages an explicit allowlist of the existing site files, so backend code, local configuration, database files, question-bank files, answer keys, and candidate data are not included in its artifact.

### Backend choice

Two practical options were reviewed:

- **FastAPI with PostgreSQL:** Python’s straightforward application structure, strong PostgreSQL support through Psycopg 3, and Alembic migrations make this a small, maintainable starting point.
- **Express with PostgreSQL:** also mature and flexible, but introduces a separate Node backend toolchain and additional choices for validation and migration conventions alongside this static frontend.

This project uses **FastAPI, SQLAlchemy, Alembic, and Psycopg 3**. It is one backend application, not a set of services. Alembic contains an empty baseline followed by a core application-schema migration; the schema migration has not been applied to a database. See [`backend/SCHEMA.md`](backend/SCHEMA.md) for tables, constraints, pending decisions, and application-level integrity requirements. No database is provisioned or contacted by the health endpoint.

### Local setup (PowerShell)

Use Python 3.11 or newer. From the repository root:

```powershell
Set-Location .\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

Edit `backend/.env` and set `DATABASE_URL` to a PostgreSQL URL using the `postgresql+psycopg://` scheme. Keep this file private; it is ignored by Git and excluded from the Pages artifact. Startup fails with a safe configuration error if the URL is missing or invalid. Startup validates configuration but does not connect to PostgreSQL. `/health` is a liveness endpoint and remains independent of database availability.

Start the local API (from `backend/`):

```powershell
uvicorn app.main:app --reload --no-access-log
```

Check health in another terminal:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Run tests (no database needed):

```powershell
python -m unittest discover -s tests -v
```

Apply migrations only after you have configured an available local PostgreSQL database (from `backend/`):

```powershell
alembic upgrade head
```

Migration commands require a reachable configured PostgreSQL database. The API health endpoint and tests do not. The project has not been deployed and no paid hosting or database resources have been created.

### Test database safety

`APP_ENV=test` accepts only `postgresql+psycopg` URLs for the exact disposable database `sutravya_m3_test` at `127.0.0.1:55432`. URL query options and fragments are rejected so they cannot redirect a connection. This validation runs when settings are constructed, before SQLAlchemy receives a URL or Alembic opens a connection. Unit tests use an explicit in-memory SQLite engine for schema checks and do not use the application database URL.

Development and production retain the existing URL policy: PostgreSQL/Psycopg URL scheme, a host, and a database name are required, while a remote host and non-test database name remain allowed for intentional deployment configuration. Keep deployment credentials in the host's secret configuration; this validation does not prove that a non-test URL is a production or development database.

For a future local PostgreSQL rehearsal, start Docker Desktop and use a disposable container with no mounted volume, mapped only to loopback port `55432`, database `sutravya_m3_test`, then provide that exact URL to Alembic. Stop and remove the disposable container after the rehearsal. Do not point test mode at a shared or production database.
