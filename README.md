# Sutrāvya Digital Learning & Assessment Platform

Event assessment platform for Bihar Healthcare Conclave 2026, organised by Qualinova, with Sutrāvya as the test and assessment partner.

## Product direction

Build an original, premium assessment experience for nursing students. Major assessment products are workflow benchmarks, not visual templates.

### Candidate journey

1. Event landing and candidate registration
2. Nursing MCQ assessment
3. MCQ score released immediately after submission; rank shown according to event rules
4. Separate digital-health hackathon / idea submission
5. Panel review and later score release

### Organizer and panel tools

- Candidate management and imports
- Question bank, test timing, scoring, and exam-window controls
- Submission monitoring
- Panel assignments, rubric-based review, moderation, and audit trail
- Controlled result release and exports

## Data and infrastructure plan

For a single event, use managed PostgreSQL for candidate records, answers, scores, and reviewer decisions. Keep brochures and candidate uploads in private object storage, saving only references and metadata in the database. Use encrypted connections and backups, role-based admin access, audit score changes, and agree a retention/deletion date with Qualinova before registration opens. Avoid collecting unnecessary sensitive health data.

A managed cloud service should keep operations straightforward for a one-time event. Cost depends on candidate volume, simultaneous exam load, notification needs, upload limits, and data-retention period; confirm those before choosing a provider. This repository is a local prototype: it has no live backend or cloud service yet.

## Current prototype

Open `index.html` locally. The page uses the supplied Sutrāvya logo and conclave brochure. Registration and assessment interactions are prototype-only; submissions are not saved to a production database.

## Build stages

1. Confirm eligibility, registration fields, MCQ rules, and hackathon submission format.
2. Finalize candidate, organizer, and panel journeys and responsive interface.
3. Implement authentication, database, private file storage, and access roles.
4. Build MCQ delivery and scoring, then panel review and moderation.
5. Add result release, exports, privacy notice, retention controls, and monitoring.
6. Deploy and rehearse with sample accounts before opening registration.
