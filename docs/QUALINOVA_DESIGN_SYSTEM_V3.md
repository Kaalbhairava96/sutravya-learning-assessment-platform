# QUALINOVA × SUTRAVYA — Frontend Design System V3

**Status:** implemented on branch `qualinova-metallic-gold-silver-v3`; do not merge without the CI gate.
**Purpose:** use this standard for all future QualiNova HTSE pages and candidate/admin interfaces.

## Brand and surface language

- **Primary surfaces:** glossy champagne gold, brushed silver, pearl/ivory and warm metallic neutrals.
- **Text:** graphite/charcoal for readable contrast; soft warm grey for supporting copy.
- **Brand accents:** retain the SUTRAVYA mark as supplied. Restrict any logo-derived navy, teal and yellow to small identity accents, active/focus indicators or partner marks; do not use large blue or violet page backgrounds.
- **Finish:** layered metallic gradients, controlled highlights, shallow embossing, glass/metal panels, fine borders and restrained shadows. Avoid flat yellow fills, excessive glitter, or low-contrast silver text.
- **Page background:** each public page should use a pearl/ivory base with gold and silver glossy lighting; darker graphite/bronze sections are reserved for emphasis, footer and selected innovation panels.
- **Logo handling:** do not recolour or redraw the SUTRAVYA and QualiNova logo files. The site uses the supplied logo artwork. The new favicon preserves the S mark in a gold/silver treatment with a small teal identity accent.

## Composition and typography

- **Hero proportion target:** approximately 35% copy and 65% visual/illustration on desktop. Use responsive stacking at mobile widths instead of forcing side-by-side columns.
- **Section pattern:** short explanatory copy paired with a meaningful diagram, illustration, subject map, workflow or visual card group wherever it materially clarifies the information.
- **Text:** concise and illustrative, with short headings, labelled facts, bullets or structured cards. Keep long legal/policy explanations in readable panels rather than overlaid on imagery.
- **Alignment:** align text baselines, section headings, diagrams and call-to-action controls to a consistent grid. Avoid detached floating visuals with no explanatory relationship.
- **Accessibility:** every meaningful image needs concise alt text; decorative icons use empty/hidden semantics. Keep keyboard focus visible, controls labelled and interactive tabs keyboard-operable. Respect reduced-motion preferences.
- **Responsive:** desktop, tablet and mobile are separate layout modes. On mobile, stack the visual and copy; preserve readable form controls and minimum tap targets.

## Shared components

- Header: pearl glass surface, metallic separator, gold CTA.
- Buttons: champagne metal primary, silver/pearl secondary, graphite text.
- Cards: pearl-to-silver gradients, subtle metallic border and restrained shadow.
- Flow diagrams: labelled steps, clear sequence, no reliance on colour alone.
- Forms: clear field labels, spacious controls and fee/status information separated from payment provider integration.
- Exam/admin controls: retain functional clarity and high legibility; decorative imagery must never crowd the candidate question or timer.

## Asset rules

- Store original page illustrations in `assets/metallic-*.svg`.
- Keep the Linux and Windows allowlists in sync whenever assets are added.
- Do not replace supplied brand logos with generated substitutes.
- Reuse an asset only where its semantic meaning matches the page; do not repeat the registration diagram as an unrelated sample-question illustration.

## Scope constraints

- This theme specification changes appearance and public informational presentation only.
- Payment provider integration is out of scope and must remain separately planned.
- Do not make unapproved claims about awards, accreditation, credit points, event venues, or financing.
- Do not use the provisional MBBS PG practice sampler as an official specialty-specific paper.
