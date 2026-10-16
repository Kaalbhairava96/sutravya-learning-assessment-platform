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
