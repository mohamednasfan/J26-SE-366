# Clinical evidence and independent validation register

**Status: NOT CLINICALLY APPROVED.** This register is an auditable handoff for qualified clinical reviewers. It does not certify MedSafe-AI or approve any drug dosing threshold.

## Review record required for each medicine and indication

| Field | Reviewer must document |
| --- | --- |
| Exact ingredient and product | Product identifier, dosage form, strength and concentration |
| Clinical context | Route, indication, population, age, weight and applicable renal/hepatic considerations |
| Source evidence | Official source HTTPS URL, precise label section, publication/revision date, retrieval date |
| Dose interpretation | Administered single-dose and daily-dose ceiling, units, frequency assumptions, mg/kg basis if applicable |
| Scope and exclusions | When the rule must abstain, including PRN or missing concentration |
| Professional approval | Reviewer identity, credentials, institution, signed approval date and version |
| Independent verification | Second reviewer, adjudication of discrepancies, version and approval date |
| Revalidation | Expiry date and re-review after labeling changes |

## Approval and release gates

1. Pharmacist or prescribing clinician independently verifies each source against the exact formulation and patient population.
2. A separate qualified reviewer checks the transcribed numerical values, units, source context, contraindications and exceptions.
3. Only then may a signed and versioned record be added to the external JSON registry and deployed with MEDSAFE_REVIEWED_RULES.
4. Test threshold boundaries, unit conversions, incorrect routes, missing age/weight, uncertain medicine names, incomplete schedules and expired rules.
5. Use a separately adjudicated held-out clinical case set with both positive and negative cases to estimate sensitivity, specificity, precision, recall, age-classification accuracy and abstention rates.
6. Record cohort provenance, class counts, confidence intervals, errors, conflicts and model version. Do not use synthetic fixtures as evidence of clinical performance.
7. Obtain the institution's required ethics, data protection, clinical governance and deployment approvals before handling identifiable patient records or using outputs in patient care.

## Current project evidence

- The reviewed real-drug registry shipped in this repository is empty (`reviewed_rules_EMPTY.json`).
- DailyMed/openFDA evidence excerpts are unverified source material, not clinician-approved dose ceilings.
- No independent clinical adjudication or sign-off is recorded in the repository.
- Missing evidence must return NOT_EVALUATED / UNABLE_TO_VALIDATE, not a reassuring negative.
- All results are research screening flags, not diagnoses or dispensing authorization.

**Approval decision:** BLOCKED until signed professional evidence and independent evaluation are supplied.
