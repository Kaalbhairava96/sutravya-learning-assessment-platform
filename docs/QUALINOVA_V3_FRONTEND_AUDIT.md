# QualiNova V3 — Detailed Frontend Audit

**Reviewed:** 11 November 2026  
**Branch:** `registration-launch`  
**Basis:** HTML/CSS/JS source inspection, asset-reference checks, CI static-site build and automated page audit.  
**Important limitation:** These are source/design-architecture ratings. No real-browser screenshot, responsive-device session, Lighthouse, Core Web Vitals or cross-browser rendering test was completed in this review. They are not measured visual performance scores.

## Executive assessment

**Provisional source/design score: 9.2/10.** The main strengths are a unified metallic visual language, four separate assessment pathways, diagram-led user journeys, concise page-level information architecture, mobile stacking rules, accessible image descriptions and repeatable CI checks.

The score is provisional because the final visual rendering still needs direct browser verification. The biggest remaining risks are long-form forms, the exam question workspace on narrow screens, live asset/rendering differences, and academic/policy content approval rather than colour treatment.

## Section-by-section ratings

### 1. Homepage — 9.3/10

| Section | Rating | Audit |
|---|---:|---|
| Main hero | 9.4 | Clear proposition, brand lock-up, metallic healthcare hero visual, two primary journeys and aligned copy/art composition. |
| Statistics band | 9.1 | Four high-scan metrics; verify numbers and labels against the final organiser specification before publication. |
| Assessment pathways | 9.3 | Four-way visual pathway map supported by separate Nursing, Paramedical and MBBS UG/PG cards. |
| Learning journey | 9.5 | Diagram-led sequence from syllabus to sample questions, mock and subject insight; the strongest explanatory section. |
| Innovation/Hackathon | 9.3 | Strong visual and concise progression into the Hackathon. |
| Awards & recognition | 9.1 | Separate academic and Hackathon recognition concepts; ensure only approved benefit claims remain. |
| Important dates | 9.3 | Timeline format improves scanning; venue/schedule caveats remain visible. |
| Final CTA | 9.3 | Clear close and registration action with a restrained dark graphite section. |

### 2. Registration — 9.1/10

| Section | Rating | Audit |
|---|---:|---|
| Hero | 9.3 | Large registration workflow visual, clear three-category entry and useful fee facts. |
| Progress/sidebar | 9.2 | Four steps make the process understandable; useful security note. |
| Candidate form | 9.0 | Form-first UI is appropriate for data entry; field density and conditional UG/PG states require mobile browser testing. |
| Review & declaration | 9.0 | Clear confirmation checkpoint before OTP. |
| Email OTP | 9.1 | Separate state reduces ambiguity; test resend, expiry and error messages in a live browser. |
| Application status | 9.0 | Correctly keeps payment pending until provider integration is added. Payment remains excluded from V3. |

### 3. Syllabus — 9.3/10

| Section | Rating | Audit |
|---|---:|---|
| Hero/pathway art | 9.2 | Clear introduction to the four practice pathways. |
| Academic framing | 9.1 | Explains how the syllabus relates to practice. |
| Pathway tabs | 9.4 | Four clear, keyboard-operable tabs. |
| Subject cards/counts | 9.4 | Actual subject-wise practice-bank counts are shown instead of claiming an artificial equal distribution. |
| Mock CTA | 9.4 | Diagram connects study coverage with practice and score review. |

### 4. Sample Questions — 9.2/10

| Section | Rating | Audit |
|---|---:|---|
| Hero | 9.2 | Distinguishes sample practice from official examination content. |
| Practice-loop diagram | 9.3 | Gives a visual reason to use samples before the full mock. |
| Pathway tabs | 9.3 | Four separate pathways and accessible tab semantics. |
| Question cards/options | 9.2 | Subject labels and answer feedback are connected to the bank. |
| Practice disclaimer | 9.2 | Correctly states that samples are illustrative, not official papers. |

### 5. Mock Test — 9.2/10

| Section | Rating | Audit |
|---|---:|---|
| Hero | 9.1 | Communicates the practice purpose and four pathways. |
| Stream selection | 9.3 | Separate pathway controls for four independent banks. |
| Four-step flow | 9.2 | Makes the practice sequence explicit. |
| Question workspace | 9.3 | Functional question area, option selection and navigator are prioritised over decorative art. |
| Timer/progress | 9.2 | Clear timed practice and progress cues. |
| Results/subject review | 9.2 | Score, explanations and subject-wise review; practice-only disclaimer remains important. |

### 6. Awards & Recognition — 9.2/10

| Section | Rating | Audit |
|---|---:|---|
| Hero | 9.3 | Premium recognition visual and clear split between assessment and Hackathon. |
| Recognition tracks | 9.2 | Academic and Hackathon tracks separated for clarity. |
| Startup enablement | 9.1 | Helpful support categories; avoid language that implies guaranteed seed funding. |
| Development journey | 9.2 | Four-step progression from validation to launch. |
| Terms/conditions | 9.3 | Important approval and eligibility caveats are visible. |

### 7. Healthcare Innovation Hackathon — 9.3/10

| Section | Rating | Audit |
|---|---:|---|
| Hero | 9.4 | Strong metallic illustration and clear challenge proposition. |
| Problem framing | 9.3 | Explains the need to start with a real healthcare problem. |
| Four-step flow | 9.4 | Identify → Design → Prototype → Present is clear and visual. |
| Milestone timeline | 9.2 | Submission and presentation milestones are easy to scan. |
| Awards | 9.1 | Top-three recognition is separated from the support pathway; award values remain approval-dependent. |
| Startup Launchpad | 9.3 | Technical, healthcare, business and potential funding support are organised into a clear pathway. |
| Submission CTA | 9.2 | Useful next step and patient-data caution. |

### 8. FAQs — 9.2/10

| Section | Rating | Audit |
|---|---:|---|
| Hero | 9.2 | Candidate-help purpose is clear and supported by an illustration. |
| Support path | 9.2 | Four-step support categories guide candidates to the relevant answer area. |
| FAQ groups | 9.1 | Logical grouping by registration, exam, Hackathon and support. |
| Contact CTA | 9.2 | Clear route to the support teams. |

### 9. Contact — 9.2/10

| Section | Rating | Audit |
|---|---:|---|
| Hero | 9.2 | Partner relationship is explained beside a metallic connection visual. |
| Partner cards | 9.1 | Organiser and technology partner are distinct. |
| Logo display | 9.3 | Original supplied logos are preserved. |
| Contact methods | 9.2 | Phone, email and website actions are easy to find. |

### 10. Candidate Login — 9.1/10

| Section | Rating | Audit |
|---|---:|---|
| Hero/security visual | 9.2 | Clear account-verification proposition. |
| Login panel | 9.0 | Functional one-time email flow remains the primary task. |
| Security context | 9.1 | Expiry and access limitations are explained. |

### 11. Authorised Team Pre-launch — 9.1/10

| Section | Rating | Audit |
|---|---:|---|
| Restricted-access hero | 9.2 | Purpose and access restriction are clear. |
| Access/OTP context | 9.1 | Explains the server-validated process. |
| Registration form | 9.0 | Reuses the candidate flow; should remain noindex and server-protected. |

### 12. Assessment Admin — 9.1/10

| Section | Rating | Audit |
|---|---:|---|
| Admin hero | 9.1 | Gold/silver system aligned with the public site. |
| Operations overview | 9.2 | Visual explains slots, question bank and secure control. |
| Slot creation | 9.1 | Distinct form and capacity field. |
| Candidate assignment | 9.0 | Functional, utilitarian task; keep IDs and statuses easy to scan. |
| Question-bank import | 9.1 | Clear five-block import rule and validation steps. |

### 13. Candidate Exam Portal — 9.2/10

| Section | Rating | Audit |
|---|---:|---|
| Exam header | 9.1 | Restrained visual support does not compete with the examination. |
| Timer/status | 9.2 | Timer remains prominent and readable. |
| Section/progress indicators | 9.1 | Clear progress representation. |
| Question card | 9.3 | The question itself has visual priority and ample reading space. |
| Answer controls | 9.2 | Clear selected-state treatment and controls. |
| Submit/status/review | 9.1 | Functional priority is correct; verify under timed real-session conditions. |

## Cross-site technical audit

| Area | Result | Notes |
|---|---|---|
| Public HTML page coverage | Pass | 13 pages included in automated audit. |
| Page title/H1 structure | Pass | Exactly one title and one H1 per audited page. |
| Image alternative text | Pass | Every image in audited pages has an alt attribute. |
| Static asset references | Pass | Local image references resolve in the built public bundle. |
| Theme metadata | Pass | Every page has theme-color metadata. |
| JavaScript syntax | Pass | Site, registration, exam, mock, sample and admin scripts checked by CI. |
| Practice-bank integrity | Pass | Four 100-question banks and subject mapping validated. |
| Static publication allowlist | Pass | Linux build completed successfully; Windows allowlist updated as well. |
| Backend unit tests | Pass | Full backend suite passed on latest PR run. |
| Accessibility automation | Partial | Alt text, headings, keyboard tab behavior, focus states and reduced motion are covered in source; no full axe/WCAG browser audit. |
| Real viewport rendering | Not measured | Needs desktop, tablet and mobile browser screenshots. |
| Lighthouse/Core Web Vitals | Not measured | Do not infer scores from source inspection. |
| Live end-to-end flows | Not measured | Registration OTP, real exam, admin operations and payment remain separate production verification tasks. |

## Highest-priority follow-up checks

1. Capture real screenshots at 1440px desktop, 1024px tablet, 768px small tablet and 390px mobile for the homepage, registration, syllabus, sample, mock and exam pages.
2. Run Lighthouse and accessibility checks in a browser after deployment; inspect layout shift, font loading, image dimensions, tap targets and colour contrast.
3. Walk the registration conditional fields for Nursing, Paramedical, MBBS UG and MBBS PG on mobile.
4. Run sample-question and mock-test interactions end to end in all four pathways.
5. Review the MBBS PG sampler with qualified faculty; it is broad clinical-foundations practice, not a specialty-specific official paper.
6. Keep payment provider integration separately gated; the V3 work does not activate or alter payment collection.

## Overall rating

- **Source/design architecture:** 9.2/10 provisional.
- **Rendered visual quality:** pending direct browser inspection.
- **Production readiness:** visual source and CI gates pass; end-to-end candidate flow and actual browser rendering still require verification.


## Follow-up implementation — 11 November 2026

The V3 follow-up consolidates the nine prior global token blocks into one canonical `:root` block, sets the browser-native control scheme to light, and places retained page selectors and responsive rules inside a named `@layer legacy` compatibility layer. This is a safe migration step, not a claim that all historical selectors have already been deleted: selector retirement depends on rendered desktop/tablet/mobile verification, which is still pending.

The FAQ section's duplicate `class` attribute was corrected. The CI page audit now checks duplicate HTML attributes, exactly one token block, the named compatibility layer and the light control scheme in addition to the existing title, heading, image-alt, local-asset and theme metadata checks.
