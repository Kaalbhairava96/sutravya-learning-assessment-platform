# SUTRĀVYA / QualiNova Assessment 2026 Registration Launch Runbook

## Scope and approved dates

This microsite supports candidate registration only. The exam engine and exam login are not available through this launch. The backend remains responsible for accepting or rejecting registration actions; the browser date check is only a usability aid.

- Registration opens: **1 November 2026, 12:00 AM IST** (inclusive).
- Registration closes: **15 November 2026, 11:59:59 PM IST** (inclusive; the window closes at midnight starting 16 November).
- Examination date: **4 December 2026**.
- Streams: Paramedical, Nursing, and MBBS 1st Year.
- Each stream: separate 100-MCQ paper, 30 minutes, no negative marking. Score display is after exam submission; exam delivery is outside this release.

The API gates registration start, registration OTP verification, and registration OTP resend using Asia/Kolkata server-side time. Pending OTP challenges cannot complete registration after the deadline. The UI also disables registration outside the window.

## Team pre-launch registration

In the API service's private Render environment, set `INTERNAL_TEST_MODE=true` and create a high-entropy `INTERNAL_TEST_ACCESS_CODE` (at least 16 characters). Never put that code in this repository, static-host settings, screenshots, or public issue reports. Before opening, the landing page presents a clearly separated team access panel, then uses the same official candidate form, registration endpoints, email OTP, ID generation, and database journey. The browser sends the access code only in the `X-Internal-Test-Code` HTTPS request header. The API rate-limits attempts and compares the code in constant time. A completed team registration is active, is eligible for ordinary candidate login, and has `registration_source=team_prelaunch`; it is not a test-only registration.

At **1 November 2026, 00:00 IST**, the access code is no longer required. Pending team OTP challenges can still be completed without the code and keep their `team_prelaunch` source. Disable `INTERNAL_TEST_MODE` and remove its code from Render by the opening time as an operational cleanup; server date enforcement independently makes the gate unnecessary. At and after the closing deadline, the backend rejects all registration start, verification, and resend requests. Apply migration `0007_legacy_classification` before deploying the matching backend code. It reclassifies historical flagged records as `legacy_internal_test` without changing their flags or IDs.

## Frontend and API configuration

The registration and candidate account sign-in pages use the public API base `https://sutravya-assessment-api-demo.onrender.com`. Browser API requests include credentials. Do not add API keys or other secrets to HTML, JavaScript, CSS, or static-host environment variables.

The microsite output is assembled by the explicit allowlist in `scripts/build_assessment_site.sh`. It stages only `index.html`, `contact.html`, `login.html`, the required styles/scripts, and required public images into the ignored `assessment-public/` directory. Do not configure a static host to publish the repository root.

Local bundle check from the repository root:

```bash
bash scripts/build_assessment_site.sh
```

Inspect `assessment-public/` before upload. The builder fails if an unexpected or restricted file is present. Its output directory is ignored by Git.

## Backend update order

This code revision requires Alembic `0008_registration_serial_ids`. First inspect the production database's current Alembic revision. Back up the managed database and run the approved migration job to `head`; verify the resulting revision is `0008_registration_serial_ids` before rolling out the matching backend code. Do not run the migration from a developer shell against an unverified or shared database.

## Dedicated assessment subdomain deployment

The existing `.github/workflows/pages.yml` deploys only on pushes to `main` (or manual dispatch), stages the existing Pages allowlist, and invokes GitHub Pages configuration. The active working branch is `registration-launch`. **Do not merge this branch to `main` or run that workflow until the repository’s current Pages custom domain and ownership are confirmed.** Do not change the GitHub Pages custom domain for the existing SUTRAVYA homepage.

Recommended isolated deployment procedure:

1. In Render, create a **separate Static Site** connected to this repository and the `registration-launch` branch. This must be a new static-site service; do not change the existing `sutravya.in` site or the API service.
2. Set the build command to `bash scripts/build_assessment_site.sh` and the publish directory to `assessment-public`.
3. Deploy the preview URL first. Confirm the registration page, contact page, sign-in page, logo/assets, responsive layout, and API base URL.
4. In that static site’s custom-domain settings, add exactly `assessment.sutravya.in`. Configure the DNS record type and target exactly as Render specifies for that service, then wait for domain verification and TLS provisioning. Do not alter apex-domain DNS records.
5. Before opening registration, update the API service’s existing `CORS_ORIGINS` value by **preserving every current origin** and appending `https://assessment.sutravya.in` as another comma-separated exact origin. Do not replace the existing list with only the new origin. Save the Render setting and redeploy/restart the API as Render requires. No CORS value is changed by this runbook.
6. In the API service's private environment, set `REGISTRATION_EXPORT_KEY` to a separate high-entropy value of at least 32 characters. Do not set it on the static site.
7. Verify the deployed static page over HTTPS, then confirm browser API requests use the configured API host and include credentials. Check the browser console and network panel for CORS errors.

The static site build contains no backend package, `.env`, database, question bank, answer key, or candidate records. The GitHub Pages workflow remains unchanged and is not the deployment path for this subdomain.

## Registration smoke test

### Before opening

- Check the page shows “Registration opens 1 November 2026” and the public form is disabled. If authorised team early registration is intentionally enabled, configure the two private backend variables and use the panel; this creates a real active candidate registration and sends a real OTP email. Never use disposable data on production.
- Check API health and confirm a registration attempt is rejected before opening.
- Run the local automated tests below. They use mocked time and mocked email delivery.
- Confirm the final CORS origin list is preserved and includes the exact HTTPS microsite origin.

## Organiser CSV export

The API has no admin login yet, so the export endpoint uses a dedicated `REGISTRATION_EXPORT_KEY` kept only in the API service's private environment. An organiser can download all registrations or one source from Windows PowerShell:

```powershell
.\scripts\export_registrations.ps1 -Source all
.\scripts\export_registrations.ps1 -Source team_prelaunch
.\scripts\export_registrations.ps1 -Source public_registration
```

The script prompts for the key without echoing it and saves a UTF-8-BOM CSV under the local Downloads folder by default. Choose an access-controlled local folder, do not commit or email the CSV, and delete it when the organiser's approved retention period ends. The endpoint returns only registration/contact/export fields and protects text fields from spreadsheet formulas.

### During the open window

Use only an organiser-approved, controlled email address and mobile number for a production smoke registration. A successful smoke test creates a real candidate registration record and sends real email; coordinate this with the data owner and retain/identify the test record under the agreed process. Verify OTP delivery, OTP completion, the visible Registration ID, its copy action, and the confirmation-email message. Do not use a candidate’s personal information for smoke testing.

Check each stream’s displayed label and exam-format details on the page. Automated tests verify that the API accepts all three API stream identifiers. Do not attempt exam login or test-taking; those features are not in this release.

## Local automated checks

From the repository root, run the offline suites from `backend/`:

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m unittest discover -s tests -p test_auth_api.py -v
..\.venv\Scripts\python.exe -m unittest discover -s tests -p test_registration.py -v
..\.venv\Scripts\python.exe -m unittest discover -s tests -p test_models.py -v
..\.venv\Scripts\python.exe -m unittest discover -s tests -p test_verification.py -v
```

Run PostgreSQL integration tests only against the positively verified disposable integration database using the repository’s existing test-only database variable and guard. Do not point these tests at production or a shared database.

## Rollback

1. If the microsite deployment is faulty, roll back to the last known-good deployment in the **assessment static-site service** or disable that service. Do not roll back or repoint the existing `sutravya.in` homepage.
2. If DNS has already been changed, keep `assessment.sutravya.in` on the assessment service’s maintenance/previous deployment until the rollback is verified. Remove or change only the subdomain record if the owner requests it; leave apex records untouched.
3. Keep the API CORS allowlist unchanged while any deployed assessment frontend uses the subdomain. If the microsite is permanently retired, remove only `https://assessment.sutravya.in` after confirming no active client depends on it; preserve all other `CORS_ORIGINS` entries.
4. Registration is closed by backend time enforcement after the deadline. Do not attempt to reopen it by changing only frontend JavaScript.

## Launch acceptance checklist

- [ ] `assessment.sutravya.in` serves the separate microsite over HTTPS.
- [ ] `sutravya.in` and its current hosting/domain configuration remain unchanged.
- [ ] Registration API base is correct on both registration and candidate sign-in pages.
- [ ] Existing CORS origins are preserved and the exact assessment origin is present.
- [ ] Registration opens/closes as scheduled in IST; OTP verify and resend are rejected outside the window.
- [ ] Registration success shows and copies the Registration ID.
- [ ] No award claims, digital-health challenge, or exam-taking availability is presented on the launch landing page.
- [ ] Organiser confirms all event dates, stream details, contact information, and privacy/retention handling before public promotion.
