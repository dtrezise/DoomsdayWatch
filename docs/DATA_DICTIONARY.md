# Data dictionary and maintenance

UTF-8 CSV with headers. IDs are stable strings, never recycled. Dates use ISO 8601; year/month precision is allowed for uncertain event dates. Empty values mean unknown/not assessed. The dataset's initial research cutoff is November 1, 2026; collection dates must not be substituted for event dates.

| Table | Primary key | Meaning and relationships |
|---|---|---|
| events | event_id | Chronological occurrence or alleged occurrence, location, sector, event date, first reported date and status. `first_reported` is the earliest report identified in this project, not a guaranteed earliest-ever publication. |
| claims | claim_id | One testable proposition linked to event, optional research lead and supporting source. Evidence note gives scope and locator; verified_at is populated only for verified claims. |
| sources | source_id | URL or local provenance path; publication/access dates, publisher, source type, retrieval result, independence group and locator. Blank archive_url means no archive captured. |
| leads | lead_id | Preserved research lead, priority, current status, next action and review date. Priority is investigative importance, not threat likelihood. |
| anomalies | anomaly_id | Candidate linked to lead; five separate qualitative dimensions, baseline gap, alternatives and interpretation. `not_assessable` means no defensible measured anomaly yet. |
| baselines | baseline_id | Sector/year/metric, value, units, geography, source, coverage status and limitations. `verified_context` is a checked milestone, not a completed statistical baseline. `missing` rows identify collection needs. |
| watchlist | indicator_id | Proposed indicator, source family, baseline state, review trigger, cadence, last check and enablement status. Currently disabled. |
| verification_log | check_id | Append-only record of dated retrieval/check attempt, source ID, outcome and next step. |

Verification statuses: unverified, partially_verified, verified, contradicted, withdrawn. Evidence classes: confirmed_fact, reported_claim, analytical_inference, speculation. Confidence: not_assessed, low, moderate, high. See METHODOLOGY.md for definitions.

A claim row currently references one source. Add separately identified corroborating propositions/evidence rows as needed, sharing the event ID; do not duplicate a claim merely to inflate support. For larger evidence sets, introduce a versioned claim-source junction table and update the validator/report builder together. Independence groups identify common upstream sources; do not count rows as independent confirmations.

For material revisions, add a verification-log entry and correction entry, preserve the prior version in Git, and update dependent assessments. Do not silently turn an unverified lead into a confirmed event. Source access flags such as snippet_only_fetch_403 or dynamic_incomplete describe collection limitations rather than truth values.

Anomaly dimensions should use not_assessed/low/moderate/high with supporting rationale when populated. Values are qualitative and must not be summed into a probability. Promote a candidate only after adding comparable historical and observed measurements with explicit units and denominators; extend the schema to retain those measurements before changing status.
