# Source References — IMNCI Rule Table

Every rule in `danger_signs.json` and `combination_rules.json` is derived from the following official government source. This file exists so any reviewer (teammate or judge) can trace a classification back to its origin.

## Primary Source

**IMNCI Chart Booklet for Medical Officers (2023 revision)**
Ministry of Health & Family Welfare, Government of India / National Health Mission
https://nhm.gov.in/images/pdf/programmes/child-health/guidelines/IMNCI-Module-2023-For-Medical-Officers/IMNCI-Chart-booklet-Medical-Officer-2023.pdf

Sections used (page numbers refer to this PDF):
- "Assess and Classify the Sick Young Infant Age Up To 2 Months" — pages 4–8
  - Check for Possible Bacterial Infection (p.4)
  - Check for Jaundice (p.5)
  - Diarrhoea for Dehydration (p.6)
  - Check for Feeding Problem or Low Weight for Age (p.7)
- "Advise the Mother When to Return to Physician" (p.14)

## Secondary / Cross-Reference Source

**HBNC Operational Guidelines (Revised 2014)**
National Health Mission
https://nhm.gov.in/images/pdf/programmes/child-health/guidelines/Revised_Home_Based_New_Born_Care_Operational_Guidelines_2014.pdf

Used to confirm the ASHA visit schedule (day 3, 7, 14, 21, 28, 42) that defines the gap window our system covers between scheduled visits.

## Validation Status

- [x] Cross-checked against source PDF by a second team member (Shreeja) — 09/07/2026
- [ ] Bias/fairness test run against sample sign combinations — pending (owned by Kshitij, see `ethics/bias_report/`)

## Notes on Scope Limitation

This rule table currently only covers the **Sick Young Infant (age up to 2 months)** section of IMNCI — this matches our project's stated focus on newborn danger signs within the HBNC visit window. It does **not** cover the separate "Sick Child (2 months to 5 years)" classification tables in the same booklet. If scope expands later, that section would need to be transcribed separately.

## Disclosed Limitation for Submission

Sign definitions and thresholds have been paraphrased from the source PDF into a machine-readable JSON format for use by the Risk Combination Agent. This is a manual transcription process; before final submission, every rule should be re-verified line-by-line against the source document by a reviewer who did not write the original transcription (see Validation Status above).