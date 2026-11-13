# M2 dataset readiness checklist

Dataset version / handoff_id: ____________________
Owner / reviewer: ____________________
Review UTC / evidence index: ____________________
Candidate / included / excluded / quarantined counts: ____________________

For each item record evidence path or issue ID; leave unchecked if unresolved.

- [ ] Scope is clean normal Practice 1/2/3 flying laps; no sprint, qualifying or race targets.
- [ ] Dated meeting, exact sessions, GP race start and layout mappings are verified.
- [ ] Practice drivers and substitutes map uniquely to reviewed canonical people and race numbers.
- [ ] All 13 ordered feature columns have the exact types/units; no extra/index/target columns.
- [ ] Separate two-column labels have finite positive seconds and exactly the same unique example IDs.
- [ ] No duplicate physical laps, conflicting numbers/persons/names or mixed layouts within a weekend.
- [ ] Each lap matches exactly one same-session/same-driver stint; overlap/gap conflicts are quarantined.
- [ ] A1 completed-lap age convention, stint boundaries, pit-out numbering and reused tires are evidenced.
- [ ] Compound, age and stint membership were available by lap start, independently of final stint length.
- [ ] Weather uses the latest same-session observation with both observation and availability <= cutoff.
- [ ] A2 freshness limit has a reviewer-approved value/rationale; stale and simultaneous conflicts resolved.
- [ ] Prediction cutoff equals evidenced lap start, is UTC and precedes GP race start.
- [ ] Lap end and target availability are evidenced; no target is available before completion.
- [ ] A3 pit-in/out, completeness, flags/interruption, deletion/reinstatement and wet/dry rules are reviewed.
- [ ] Missing essentials, invalid targets, uncertain timing and unresolved validity remain quarantined.
- [ ] No imputation, guessed times, nearest-future weather, session means or future corrections in features.
- [ ] Input lineage covers all 13 fields per example, with raw record references and matching SHA-256 hashes.
- [ ] Full and loader-compatible race/driver/circuit crosswalks and required sidecars are supplied.
- [ ] Corrections were actually applied in a new dataset version; original evidence is retained.
- [ ] Counts reconcile; exclusion/quarantine/conflict logs and category/regime coverage are reported.
- [ ] Complete weekends stay grouped chronologically; no random lap/stint split or full-data preprocessing.
- [ ] M3 has an explicit sufficiency/evaluation plan; repeated circuit/person/compound coverage is discussed.
- [ ] Manifest file hashes, counts and ordered schemas match final bytes and paths stay inside the package.
- [ ] All issues affecting included rows are resolved; quality report accurately describes the approved subset.
- [ ] Accountable M2 sign-off includes reviewer, UTC and decisions; approval is not inferred from validation.

Decision: draft / quarantined / ready for M3 review: ____________________
Remaining issues and dataset limitations: ____________________
M2 signature / decision UTC: ____________________

Mechanical validation does not complete this checklist. Do not train or collect
data as part of preparing/reviewing these templates.
