# M2 verification checklist — five-race 2024 pilot

This package is a review worksheet, not an approval or a corrected dataset. Start here if you are new to the project. M2 verifies forecast-time inputs; M3 will use reviewed data later. No model training is part of this review.

## How to use this package

1. Review one race at a time using the evidence links below. Paths in CSV/JSON files are relative to `modelling/`; links in this document are relative to `verification/`.
2. Record decisions in **issues.csv** (the primary editable review register). Use **verified** when the supplied value/evidence is confirmed, **corrected** when a specific correction is documented for handoff, or **unresolved** when evidence is insufficient. Corrected does not mean the ML feature file has been changed.
3. Fill reviewer, UTC review time, correction details, and evidence/notes. For cutoff issues also fill confirmed_cutoff_utc. The Markdown fields are an optional printable worksheet; copy any decisions back to issues.csv so it remains the single decision register.
4. qualifying_lap_events.csv is a searchable event inventory with its own optional review fields. Reference its issue_id in issues.csv. Retain every event, including any reinstatement; do not assume a deletion is final.
5. Do not mark a race ready merely because collection or contract smoke checks passed. Close or explicitly escalate every unresolved item, then hand decisions to M3. This package contains no automatic race approval mechanism.

Scope: **5 races, 99 driver rows, 12 detected qualifying lap events, 57 review items**. No additional races were fetched. Source version: [CONTRACT.md](../CONTRACT.md); data checks: [pilot quality report](../data/pilot_2024/quality_report.json).

## Immediate attention

- **All five races:** final-grid verification and both forecast cutoffs remain pending; the post-grid cutoff is unknown. Deleted/pit-in/reinstated-lap validity still requires review.
- **Saudi Arabia:** Zhou Guanyu (#24) has null qualifying_position and qualifying_gap_seconds; no valid segment time is recorded. Preserve nulls unless M2 establishes a correction.
- **Australia:** 19 entrants rather than the usual 20. Existing roster, grid and classification agree, but explain the eligible-entry count without inventing a twentieth driver.
- **China:** Practice 1 is the fallback practice source. Verify normal GP sessions, excluding sprint qualifying and the sprint race.
- Detected actions: **12 deleted, 0 reinstated**. No reinstatement was detected in these cached qualifying logs; this is not proof of final validity.

The source manifest records SHA-256 hashes to identify the exact reviewed snapshot. No source CSV, label, cache, quality flag, or model artifact is modified by this package.

## Bahrain 2024

Race ID: `2024_bahrain_gp`. Meeting **1229**; normal qualifying **9468**; GP race **9472**; practice **9467**.

**20 entrants; all issues initially unresolved; M2 approval remains pending.**

Evidence files (links open existing local caches/tables):

- sessions: [sessions_year-2024_country_name-Bahrain.json](../data/2024_bahrain/raw/sessions_year-2024_country_name-Bahrain.json)
- qualifying drivers: [drivers_session_key-9468.json](../data/2024_bahrain/raw/drivers_session_key-9468.json)
- practice drivers: [drivers_session_key-9467.json](../data/2024_bahrain/raw/drivers_session_key-9467.json)
- qualifying laps: [laps_session_key-9468.json](../data/2024_bahrain/raw/laps_session_key-9468.json)
- practice laps: [laps_session_key-9467.json](../data/2024_bahrain/raw/laps_session_key-9467.json)
- qualifying classification: [session_result_session_key-9468.json](../data/2024_bahrain/raw/session_result_session_key-9468.json)
- grid: [starting_grid_session_key-9468.json](../data/2024_bahrain/raw/starting_grid_session_key-9468.json)
- qualifying control: [race_control_session_key-9468.json](../data/2024_bahrain/raw/race_control_session_key-9468.json)
- practice control: [race_control_session_key-9467.json](../data/2024_bahrain/raw/race_control_session_key-9467.json)
- weather: [weather_session_key-9468.json](../data/2024_bahrain/raw/weather_session_key-9468.json)
- race classification: [session_result_session_key-9472.json](../data/2024_bahrain/raw/session_result_session_key-9472.json)
- draft: [draft_entrants.csv](../data/2024_bahrain/draft_entrants.csv)
- post qualifying: [post_qualifying_entrants.csv](../data/2024_bahrain/post_qualifying_entrants.csv)
- post grid: [post_grid_entrants.csv](../data/2024_bahrain/post_grid_entrants.csv)
- labels: [podium_labels.csv](../data/2024_bahrain/podium_labels.csv)
- quality: [quality_report.json](../data/2024_bahrain/quality_report.json)

Review checklist:

### 2024_bahrain_gp-ENTRANTS — Eligible entrants and normal GP sessions

20 entrants; duplicate feature rows=0. Count is 20; this is a coverage check, not eligibility approval.

**M2 check:** Confirm the eligible entrant list at each forecast stage. Explain withdrawals/substitutions and any count difference. Confirm normal Qualifying and Race in this meeting, excluding sprint sessions.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_bahrain_gp-QUALIFYING — Missing qualifying data and classification

Missing feature counts: {"qualifying_position": 0, "qualifying_gap_seconds": 0, "practice_gap_seconds": 0, "qualifying_air_temp_c": 0, "qualifying_track_temp_c": 0, "qualifying_rainfall": 0, "grid_position": 0}. Affected qualifying rows: [].

**M2 check:** Verify normal-GP qualifying classification and confirm no missing qualifying values were overlooked. Never substitute grid positions for qualifying classification.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_bahrain_gp-LAP-VALIDITY — Qualifying valid-lap reconstruction

2 deleted/reinstated messages found. Provisional filtering does not fully resolve pit-in, deleted or reinstated laps. Raw messages are listed individually below.

**M2 check:** Review every event below and the full chronological qualifying race-control log. Match by driver and lap, resolve reinstatements, and check best valid lap across all Q1/Q2/Q3. Recheck the session-fastest reference: changing one driver's fastest valid lap can change every qualifying gap. Record proposed corrections without editing feature CSVs in this package.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_bahrain_gp-PRACTICE — Practice selection, lap validity and driver identity

Selected Practice 3 (9467). Rejected-lap counts: {"pit_out_or_unknown": 84, "invalid_or_missing_duration": 2, "incomplete_sectors": 0}. Identity review flags: [].

**M2 check:** Confirm one common latest comparable practice before normal qualifying (FP3 when present; China uses FP1). Exclude sprint sessions, pit-out/incomplete/pit-in laps and invalid/deleted laps. Confirm driver-number identity, including substitutes; review track-evolution limitations.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_bahrain_gp-WEATHER — Qualifying weather

Shared qualifying weather comes from one cached /weather response; missing counts are included above.

**M2 check:** Confirm qualifying-session air/track-temperature medians and any-rainfall aggregation, shared by all drivers and available by the chosen forecast cutoff.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_bahrain_gp-GRID — Final grid and penalties

Grid integrity: {"populated": 20, "unique_driver_assignments": 20, "positions": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20], "complete_1_to_n": true}. Stored grid_verified=False; no M2 attestation has been supplied.

**M2 check:** Confirm final grid, including penalties and pit-lane arrangements, for every eligible starter. OpenF1 starting_grid is keyed by qualifying session 9468, not race 9472. Structural uniqueness/completeness alone is not final-grid verification. Record source timing and any correction.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_bahrain_gp-CUTOFF-Q — Post-qualifying forecast cutoff remains unverified

Intended session-end cutoff: 2024-03-01T17:00:00+00:00. Historical availability of classification/weather/lap validity at this instant is not established.

**M2 check:** Enter the verified UTC forecast cutoff in confirmed_cutoff_utc; document when every qualifying-stage input was available and whether late corrections were known then. Later retrieval timestamps do not prove earlier availability.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_bahrain_gp-CUTOFF-G — Post-grid forecast cutoff is unresolved

Recorded post-grid cutoff: None (unknown).

**M2 check:** Enter a verified pre-race UTC forecast cutoff in confirmed_cutoff_utc. Establish when the final penalized grid was published and available, and confirm it precedes race start. Keep unresolved if existing evidence is insufficient; do not infer it from race outcomes or scheduled race time.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_bahrain_gp-LABELS — Race classification and separate podium labels

Classification coverage complete=True; missing labels=0; positive podium labels=3; issues=[].

**M2 check:** Audit only the separate labels against the normal Grand Prix race classification. Confirm top three and DNF/DNS/DSQ interpretation; leave ambiguous targets unresolved. Never use this evidence to construct prediction features or filter entrants retrospectively.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_bahrain_gp-LAP-01 — Deleted qualifying lap — #10 Pierre GASLY

UTC message 2024-03-01T16:04:42+00:00; lap 3; reported time 1:32.434; identity basis: CAR number parsed from message. Exact message: CAR 10 (GAS) TIME 1:32.434 DELETED - TRACK LIMITS AT TURN 13 LAP 3 19:03:46

**M2 check:** Resolve this event against the full log and matching lap. Check later reinstatement/deletion and whether it changes best valid pace or the session-wide reference. Record evidence and proposed correction; no automatic feature change.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_bahrain_gp-LAP-02 — Deleted qualifying lap — #20 Kevin MAGNUSSEN

UTC message 2024-03-01T16:30:24+00:00; lap 9; reported time 1:31.170; identity basis: CAR number parsed from message. Exact message: CAR 20 (MAG) TIME 1:31.170 DELETED - TRACK LIMITS AT TURN 7 LAP 9 19:29:18

**M2 check:** Resolve this event against the full log and matching lap. Check later reinstatement/deletion and whether it changes best valid pace or the session-wide reference. Record evidence and proposed correction; no automatic feature change.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

Deleted/reinstated messages are reproduced verbatim above. UTC is the message record timestamp; trailing clock times inside messages are preserved as supplied and are not assumed to be UTC. Driver/lap values parsed from prose remain interpretations for review.

## Saudi Arabia 2024

Race ID: `2024_saudi_arabia_gp`. Meeting **1230**; normal qualifying **9476**; GP race **9480**; practice **9475**.

**20 entrants; all issues initially unresolved; M2 approval remains pending.**

Evidence files (links open existing local caches/tables):

- sessions: [sessions_year-2024_country_name-Saudi Arabia.json](../data/2024_saudi_arabia/raw/sessions_year-2024_country_name-Saudi Arabia.json)
- qualifying drivers: [drivers_session_key-9476.json](../data/2024_saudi_arabia/raw/drivers_session_key-9476.json)
- practice drivers: [drivers_session_key-9475.json](../data/2024_saudi_arabia/raw/drivers_session_key-9475.json)
- qualifying laps: [laps_session_key-9476.json](../data/2024_saudi_arabia/raw/laps_session_key-9476.json)
- practice laps: [laps_session_key-9475.json](../data/2024_saudi_arabia/raw/laps_session_key-9475.json)
- qualifying classification: [session_result_session_key-9476.json](../data/2024_saudi_arabia/raw/session_result_session_key-9476.json)
- grid: [starting_grid_session_key-9476.json](../data/2024_saudi_arabia/raw/starting_grid_session_key-9476.json)
- qualifying control: [race_control_session_key-9476.json](../data/2024_saudi_arabia/raw/race_control_session_key-9476.json)
- practice control: [race_control_session_key-9475.json](../data/2024_saudi_arabia/raw/race_control_session_key-9475.json)
- weather: [weather_session_key-9476.json](../data/2024_saudi_arabia/raw/weather_session_key-9476.json)
- race classification: [session_result_session_key-9480.json](../data/2024_saudi_arabia/raw/session_result_session_key-9480.json)
- draft: [draft_entrants.csv](../data/2024_saudi_arabia/draft_entrants.csv)
- post qualifying: [post_qualifying_entrants.csv](../data/2024_saudi_arabia/post_qualifying_entrants.csv)
- post grid: [post_grid_entrants.csv](../data/2024_saudi_arabia/post_grid_entrants.csv)
- labels: [podium_labels.csv](../data/2024_saudi_arabia/podium_labels.csv)
- quality: [quality_report.json](../data/2024_saudi_arabia/quality_report.json)

Review checklist:

### 2024_saudi_arabia_gp-ENTRANTS — Eligible entrants and normal GP sessions

20 entrants; duplicate feature rows=0. Count is 20; this is a coverage check, not eligibility approval.

**M2 check:** Confirm the eligible entrant list at each forecast stage. Explain withdrawals/substitutions and any count difference. Confirm normal Qualifying and Race in this meeting, excluding sprint sessions.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_saudi_arabia_gp-QUALIFYING — Missing qualifying data and classification

Missing feature counts: {"qualifying_position": 1, "qualifying_gap_seconds": 1, "practice_gap_seconds": 0, "qualifying_air_temp_c": 0, "qualifying_track_temp_c": 0, "qualifying_rainfall": 0, "grid_position": 0}. Affected qualifying rows: [{"driver_number": "24", "driver_name": "ZHOU Guanyu", "qualifying_position": "", "qualifying_gap_seconds": ""}].

**M2 check:** Verify official normal-GP qualifying positions. Preserve nulls when no valid classification/lap exists. For Zhou in Saudi Arabia, review the all-null Q1/Q2/Q3 times and confirm position/gap should remain null; do not substitute grid position.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_saudi_arabia_gp-LAP-VALIDITY — Qualifying valid-lap reconstruction

4 deleted/reinstated messages found. Provisional filtering does not fully resolve pit-in, deleted or reinstated laps. Raw messages are listed individually below.

**M2 check:** Review every event below and the full chronological qualifying race-control log. Match by driver and lap, resolve reinstatements, and check best valid lap across all Q1/Q2/Q3. Recheck the session-fastest reference: changing one driver's fastest valid lap can change every qualifying gap. Record proposed corrections without editing feature CSVs in this package.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_saudi_arabia_gp-PRACTICE — Practice selection, lap validity and driver identity

Selected Practice 3 (9475). Rejected-lap counts: {"pit_out_or_unknown": 64, "invalid_or_missing_duration": 5, "incomplete_sectors": 0}. Identity review flags: [].

**M2 check:** Confirm one common latest comparable practice before normal qualifying (FP3 when present; China uses FP1). Exclude sprint sessions, pit-out/incomplete/pit-in laps and invalid/deleted laps. Confirm driver-number identity, including substitutes; review track-evolution limitations.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_saudi_arabia_gp-WEATHER — Qualifying weather

Shared qualifying weather comes from one cached /weather response; missing counts are included above.

**M2 check:** Confirm qualifying-session air/track-temperature medians and any-rainfall aggregation, shared by all drivers and available by the chosen forecast cutoff.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_saudi_arabia_gp-GRID — Final grid and penalties

Grid integrity: {"populated": 20, "unique_driver_assignments": 20, "positions": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20], "complete_1_to_n": true}. Stored grid_verified=False; no M2 attestation has been supplied.

**M2 check:** Confirm final grid, including penalties and pit-lane arrangements, for every eligible starter. OpenF1 starting_grid is keyed by qualifying session 9476, not race 9480. Structural uniqueness/completeness alone is not final-grid verification. Record source timing and any correction.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_saudi_arabia_gp-CUTOFF-Q — Post-qualifying forecast cutoff remains unverified

Intended session-end cutoff: 2024-03-08T18:00:00+00:00. Historical availability of classification/weather/lap validity at this instant is not established.

**M2 check:** Enter the verified UTC forecast cutoff in confirmed_cutoff_utc; document when every qualifying-stage input was available and whether late corrections were known then. Later retrieval timestamps do not prove earlier availability.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_saudi_arabia_gp-CUTOFF-G — Post-grid forecast cutoff is unresolved

Recorded post-grid cutoff: None (unknown).

**M2 check:** Enter a verified pre-race UTC forecast cutoff in confirmed_cutoff_utc. Establish when the final penalized grid was published and available, and confirm it precedes race start. Keep unresolved if existing evidence is insufficient; do not infer it from race outcomes or scheduled race time.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_saudi_arabia_gp-LABELS — Race classification and separate podium labels

Classification coverage complete=True; missing labels=0; positive podium labels=3; issues=[].

**M2 check:** Audit only the separate labels against the normal Grand Prix race classification. Confirm top three and DNF/DNS/DSQ interpretation; leave ambiguous targets unresolved. Never use this evidence to construct prediction features or filter entrants retrospectively.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_saudi_arabia_gp-LAP-01 — Deleted qualifying lap — #18 Lance STROLL

UTC message 2024-03-08T17:10:28+00:00; lap 6; reported time not given; identity basis: CAR number parsed from message. Exact message: CAR 18 (STR) LAP DELETED - TRACK LIMITS AT TURN 23 LAP 6 20:09:36

**M2 check:** Resolve this event against the full log and matching lap. Check later reinstatement/deletion and whether it changes best valid pace or the session-wide reference. Record evidence and proposed correction; no automatic feature change.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_saudi_arabia_gp-LAP-02 — Deleted qualifying lap — #20 Kevin MAGNUSSEN

UTC message 2024-03-08T17:11:10+00:00; lap 4; reported time 1:56.534; identity basis: CAR number parsed from message. Exact message: CAR 20 (MAG) TIME 1:56.534 DELETED - TRACK LIMITS AT TURN 8 LAP 4 20:04:00

**M2 check:** Resolve this event against the full log and matching lap. Check later reinstatement/deletion and whether it changes best valid pace or the session-wide reference. Record evidence and proposed correction; no automatic feature change.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_saudi_arabia_gp-LAP-03 — Deleted qualifying lap — #38 Oliver BEARMAN

UTC message 2024-03-08T17:19:15+00:00; lap 10; reported time not given; identity basis: CAR number parsed from message. Exact message: CAR 38 (BEA) LAP DELETED - TRACK LIMITS AT TURN 4 LAP 10 20:17:14 (PIT)

**M2 check:** Resolve this event against the full log and matching lap. Check later reinstatement/deletion and whether it changes best valid pace or the session-wide reference. Record evidence and proposed correction; no automatic feature change.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_saudi_arabia_gp-LAP-04 — Deleted qualifying lap — #23 Alexander ALBON

UTC message 2024-03-08T17:20:38+00:00; lap 9; reported time not given; identity basis: CAR number parsed from message. Exact message: CAR 23 (ALB) LAP DELETED - TRACK LIMITS AT TURN 23 LAP 9 20:18:13

**M2 check:** Resolve this event against the full log and matching lap. Check later reinstatement/deletion and whether it changes best valid pace or the session-wide reference. Record evidence and proposed correction; no automatic feature change.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

Deleted/reinstated messages are reproduced verbatim above. UTC is the message record timestamp; trailing clock times inside messages are preserved as supplied and are not assumed to be UTC. Driver/lap values parsed from prose remain interpretations for review.

## Australia 2024

Race ID: `2024_australia_gp`. Meeting **1231**; normal qualifying **9484**; GP race **9488**; practice **9483**.

**19 entrants; all issues initially unresolved; M2 approval remains pending.**

Evidence files (links open existing local caches/tables):

- sessions: [sessions_year-2024_country_name-Australia.json](../data/2024_australia/raw/sessions_year-2024_country_name-Australia.json)
- qualifying drivers: [drivers_session_key-9484.json](../data/2024_australia/raw/drivers_session_key-9484.json)
- practice drivers: [drivers_session_key-9483.json](../data/2024_australia/raw/drivers_session_key-9483.json)
- qualifying laps: [laps_session_key-9484.json](../data/2024_australia/raw/laps_session_key-9484.json)
- practice laps: [laps_session_key-9483.json](../data/2024_australia/raw/laps_session_key-9483.json)
- qualifying classification: [session_result_session_key-9484.json](../data/2024_australia/raw/session_result_session_key-9484.json)
- grid: [starting_grid_session_key-9484.json](../data/2024_australia/raw/starting_grid_session_key-9484.json)
- qualifying control: [race_control_session_key-9484.json](../data/2024_australia/raw/race_control_session_key-9484.json)
- practice control: [race_control_session_key-9483.json](../data/2024_australia/raw/race_control_session_key-9483.json)
- weather: [weather_session_key-9484.json](../data/2024_australia/raw/weather_session_key-9484.json)
- race classification: [session_result_session_key-9488.json](../data/2024_australia/raw/session_result_session_key-9488.json)
- draft: [draft_entrants.csv](../data/2024_australia/draft_entrants.csv)
- post qualifying: [post_qualifying_entrants.csv](../data/2024_australia/post_qualifying_entrants.csv)
- post grid: [post_grid_entrants.csv](../data/2024_australia/post_grid_entrants.csv)
- labels: [podium_labels.csv](../data/2024_australia/podium_labels.csv)
- quality: [quality_report.json](../data/2024_australia/quality_report.json)

Review checklist:

### 2024_australia_gp-ENTRANTS — Eligible entrants and normal GP sessions

19 entrants; duplicate feature rows=0. UNUSUAL COUNT: 19 rather than a usual 20; classification, grid and roster coverage agree, but eligibility still needs review.

**M2 check:** Confirm the eligible entrant list at each forecast stage. Explain withdrawals/substitutions and any count difference. Confirm normal Qualifying and Race in this meeting, excluding sprint sessions.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_australia_gp-QUALIFYING — Missing qualifying data and classification

Missing feature counts: {"qualifying_position": 0, "qualifying_gap_seconds": 0, "practice_gap_seconds": 0, "qualifying_air_temp_c": 0, "qualifying_track_temp_c": 0, "qualifying_rainfall": 0, "grid_position": 0}. Affected qualifying rows: [].

**M2 check:** Verify normal-GP qualifying classification and confirm no missing qualifying values were overlooked. Never substitute grid positions for qualifying classification.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_australia_gp-LAP-VALIDITY — Qualifying valid-lap reconstruction

2 deleted/reinstated messages found. Provisional filtering does not fully resolve pit-in, deleted or reinstated laps. Raw messages are listed individually below.

**M2 check:** Review every event below and the full chronological qualifying race-control log. Match by driver and lap, resolve reinstatements, and check best valid lap across all Q1/Q2/Q3. Recheck the session-fastest reference: changing one driver's fastest valid lap can change every qualifying gap. Record proposed corrections without editing feature CSVs in this package.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_australia_gp-PRACTICE — Practice selection, lap validity and driver identity

Selected Practice 3 (9483). Rejected-lap counts: {"pit_out_or_unknown": 86, "invalid_or_missing_duration": 19, "incomplete_sectors": 26}. Identity review flags: [].

**M2 check:** Confirm one common latest comparable practice before normal qualifying (FP3 when present; China uses FP1). Exclude sprint sessions, pit-out/incomplete/pit-in laps and invalid/deleted laps. Confirm driver-number identity, including substitutes; review track-evolution limitations.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_australia_gp-WEATHER — Qualifying weather

Shared qualifying weather comes from one cached /weather response; missing counts are included above.

**M2 check:** Confirm qualifying-session air/track-temperature medians and any-rainfall aggregation, shared by all drivers and available by the chosen forecast cutoff.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_australia_gp-GRID — Final grid and penalties

Grid integrity: {"populated": 19, "unique_driver_assignments": 19, "positions": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19], "complete_1_to_n": true}. Stored grid_verified=False; no M2 attestation has been supplied.

**M2 check:** Confirm final grid, including penalties and pit-lane arrangements, for every eligible starter. OpenF1 starting_grid is keyed by qualifying session 9484, not race 9488. Structural uniqueness/completeness alone is not final-grid verification. Record source timing and any correction.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_australia_gp-CUTOFF-Q — Post-qualifying forecast cutoff remains unverified

Intended session-end cutoff: 2024-03-23T06:00:00+00:00. Historical availability of classification/weather/lap validity at this instant is not established.

**M2 check:** Enter the verified UTC forecast cutoff in confirmed_cutoff_utc; document when every qualifying-stage input was available and whether late corrections were known then. Later retrieval timestamps do not prove earlier availability.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_australia_gp-CUTOFF-G — Post-grid forecast cutoff is unresolved

Recorded post-grid cutoff: None (unknown).

**M2 check:** Enter a verified pre-race UTC forecast cutoff in confirmed_cutoff_utc. Establish when the final penalized grid was published and available, and confirm it precedes race start. Keep unresolved if existing evidence is insufficient; do not infer it from race outcomes or scheduled race time.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_australia_gp-LABELS — Race classification and separate podium labels

Classification coverage complete=True; missing labels=0; positive podium labels=3; issues=[].

**M2 check:** Audit only the separate labels against the normal Grand Prix race classification. Confirm top three and DNF/DNS/DSQ interpretation; leave ambiguous targets unresolved. Never use this evidence to construct prediction features or filter entrants retrospectively.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_australia_gp-LAP-01 — Deleted qualifying lap — #23 Alexander ALBON

UTC message 2024-03-23T05:03:21+00:00; lap 3; reported time 1:18.709; identity basis: CAR number parsed from message. Exact message: CAR 23 (ALB) TIME 1:18.709 DELETED - TRACK LIMITS AT TURN 10 LAP 3 16:02:35

**M2 check:** Resolve this event against the full log and matching lap. Check later reinstatement/deletion and whether it changes best valid pace or the session-wide reference. Record evidence and proposed correction; no automatic feature change.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_australia_gp-LAP-02 — Deleted qualifying lap — #3 Daniel RICCIARDO

UTC message 2024-03-23T05:18:34+00:00; lap 6; reported time 1:17.466; identity basis: CAR number parsed from message. Exact message: CAR 3 (RIC) TIME 1:17.466 DELETED - TRACK LIMITS AT TURN 5 LAP 6 16:16:44

**M2 check:** Resolve this event against the full log and matching lap. Check later reinstatement/deletion and whether it changes best valid pace or the session-wide reference. Record evidence and proposed correction; no automatic feature change.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

Deleted/reinstated messages are reproduced verbatim above. UTC is the message record timestamp; trailing clock times inside messages are preserved as supplied and are not assumed to be UTC. Driver/lap values parsed from prose remain interpretations for review.

## Japan 2024

Race ID: `2024_japan_gp`. Meeting **1232**; normal qualifying **9492**; GP race **9496**; practice **9491**.

**20 entrants; all issues initially unresolved; M2 approval remains pending.**

Evidence files (links open existing local caches/tables):

- sessions: [sessions_year-2024_country_name-Japan.json](../data/2024_japan/raw/sessions_year-2024_country_name-Japan.json)
- qualifying drivers: [drivers_session_key-9492.json](../data/2024_japan/raw/drivers_session_key-9492.json)
- practice drivers: [drivers_session_key-9491.json](../data/2024_japan/raw/drivers_session_key-9491.json)
- qualifying laps: [laps_session_key-9492.json](../data/2024_japan/raw/laps_session_key-9492.json)
- practice laps: [laps_session_key-9491.json](../data/2024_japan/raw/laps_session_key-9491.json)
- qualifying classification: [session_result_session_key-9492.json](../data/2024_japan/raw/session_result_session_key-9492.json)
- grid: [starting_grid_session_key-9492.json](../data/2024_japan/raw/starting_grid_session_key-9492.json)
- qualifying control: [race_control_session_key-9492.json](../data/2024_japan/raw/race_control_session_key-9492.json)
- practice control: [race_control_session_key-9491.json](../data/2024_japan/raw/race_control_session_key-9491.json)
- weather: [weather_session_key-9492.json](../data/2024_japan/raw/weather_session_key-9492.json)
- race classification: [session_result_session_key-9496.json](../data/2024_japan/raw/session_result_session_key-9496.json)
- draft: [draft_entrants.csv](../data/2024_japan/draft_entrants.csv)
- post qualifying: [post_qualifying_entrants.csv](../data/2024_japan/post_qualifying_entrants.csv)
- post grid: [post_grid_entrants.csv](../data/2024_japan/post_grid_entrants.csv)
- labels: [podium_labels.csv](../data/2024_japan/podium_labels.csv)
- quality: [quality_report.json](../data/2024_japan/quality_report.json)

Review checklist:

### 2024_japan_gp-ENTRANTS — Eligible entrants and normal GP sessions

20 entrants; duplicate feature rows=0. Count is 20; this is a coverage check, not eligibility approval.

**M2 check:** Confirm the eligible entrant list at each forecast stage. Explain withdrawals/substitutions and any count difference. Confirm normal Qualifying and Race in this meeting, excluding sprint sessions.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_japan_gp-QUALIFYING — Missing qualifying data and classification

Missing feature counts: {"qualifying_position": 0, "qualifying_gap_seconds": 0, "practice_gap_seconds": 0, "qualifying_air_temp_c": 0, "qualifying_track_temp_c": 0, "qualifying_rainfall": 0, "grid_position": 0}. Affected qualifying rows: [].

**M2 check:** Verify normal-GP qualifying classification and confirm no missing qualifying values were overlooked. Never substitute grid positions for qualifying classification.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_japan_gp-LAP-VALIDITY — Qualifying valid-lap reconstruction

1 deleted/reinstated messages found. Provisional filtering does not fully resolve pit-in, deleted or reinstated laps. Raw messages are listed individually below.

**M2 check:** Review every event below and the full chronological qualifying race-control log. Match by driver and lap, resolve reinstatements, and check best valid lap across all Q1/Q2/Q3. Recheck the session-fastest reference: changing one driver's fastest valid lap can change every qualifying gap. Record proposed corrections without editing feature CSVs in this package.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_japan_gp-PRACTICE — Practice selection, lap validity and driver identity

Selected Practice 3 (9491). Rejected-lap counts: {"pit_out_or_unknown": 76, "invalid_or_missing_duration": 0, "incomplete_sectors": 1}. Identity review flags: [].

**M2 check:** Confirm one common latest comparable practice before normal qualifying (FP3 when present; China uses FP1). Exclude sprint sessions, pit-out/incomplete/pit-in laps and invalid/deleted laps. Confirm driver-number identity, including substitutes; review track-evolution limitations.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_japan_gp-WEATHER — Qualifying weather

Shared qualifying weather comes from one cached /weather response; missing counts are included above.

**M2 check:** Confirm qualifying-session air/track-temperature medians and any-rainfall aggregation, shared by all drivers and available by the chosen forecast cutoff.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_japan_gp-GRID — Final grid and penalties

Grid integrity: {"populated": 20, "unique_driver_assignments": 20, "positions": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20], "complete_1_to_n": true}. Stored grid_verified=False; no M2 attestation has been supplied.

**M2 check:** Confirm final grid, including penalties and pit-lane arrangements, for every eligible starter. OpenF1 starting_grid is keyed by qualifying session 9492, not race 9496. Structural uniqueness/completeness alone is not final-grid verification. Record source timing and any correction.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_japan_gp-CUTOFF-Q — Post-qualifying forecast cutoff remains unverified

Intended session-end cutoff: 2024-04-06T07:00:00+00:00. Historical availability of classification/weather/lap validity at this instant is not established.

**M2 check:** Enter the verified UTC forecast cutoff in confirmed_cutoff_utc; document when every qualifying-stage input was available and whether late corrections were known then. Later retrieval timestamps do not prove earlier availability.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_japan_gp-CUTOFF-G — Post-grid forecast cutoff is unresolved

Recorded post-grid cutoff: None (unknown).

**M2 check:** Enter a verified pre-race UTC forecast cutoff in confirmed_cutoff_utc. Establish when the final penalized grid was published and available, and confirm it precedes race start. Keep unresolved if existing evidence is insufficient; do not infer it from race outcomes or scheduled race time.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_japan_gp-LABELS — Race classification and separate podium labels

Classification coverage complete=True; missing labels=0; positive podium labels=3; issues=[].

**M2 check:** Audit only the separate labels against the normal Grand Prix race classification. Confirm top three and DNF/DNS/DSQ interpretation; leave ambiguous targets unresolved. Never use this evidence to construct prediction features or filter entrants retrospectively.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_japan_gp-LAP-01 — Deleted qualifying lap — #27 Nico HULKENBERG

UTC message 2024-04-06T06:32:16+00:00; lap 9; reported time 1:30.658; identity basis: CAR number parsed from message. Exact message: CAR 27 (HUL) TIME 1:30.658 DELETED - TRACK LIMITS AT TURN 13 LAP 9 15:29:31

**M2 check:** Resolve this event against the full log and matching lap. Check later reinstatement/deletion and whether it changes best valid pace or the session-wide reference. Record evidence and proposed correction; no automatic feature change.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

Deleted/reinstated messages are reproduced verbatim above. UTC is the message record timestamp; trailing clock times inside messages are preserved as supplied and are not assumed to be UTC. Driver/lap values parsed from prose remain interpretations for review.

## China 2024

Race ID: `2024_china_gp`. Meeting **1233**; normal qualifying **9664**; GP race **9673**; practice **9663**.

**20 entrants; all issues initially unresolved; M2 approval remains pending.**

Evidence files (links open existing local caches/tables):

- sessions: [sessions_year-2024_country_name-China.json](../data/2024_china/raw/sessions_year-2024_country_name-China.json)
- qualifying drivers: [drivers_session_key-9664.json](../data/2024_china/raw/drivers_session_key-9664.json)
- practice drivers: [drivers_session_key-9663.json](../data/2024_china/raw/drivers_session_key-9663.json)
- qualifying laps: [laps_session_key-9664.json](../data/2024_china/raw/laps_session_key-9664.json)
- practice laps: [laps_session_key-9663.json](../data/2024_china/raw/laps_session_key-9663.json)
- qualifying classification: [session_result_session_key-9664.json](../data/2024_china/raw/session_result_session_key-9664.json)
- grid: [starting_grid_session_key-9664.json](../data/2024_china/raw/starting_grid_session_key-9664.json)
- qualifying control: [race_control_session_key-9664.json](../data/2024_china/raw/race_control_session_key-9664.json)
- practice control: [race_control_session_key-9663.json](../data/2024_china/raw/race_control_session_key-9663.json)
- weather: [weather_session_key-9664.json](../data/2024_china/raw/weather_session_key-9664.json)
- race classification: [session_result_session_key-9673.json](../data/2024_china/raw/session_result_session_key-9673.json)
- draft: [draft_entrants.csv](../data/2024_china/draft_entrants.csv)
- post qualifying: [post_qualifying_entrants.csv](../data/2024_china/post_qualifying_entrants.csv)
- post grid: [post_grid_entrants.csv](../data/2024_china/post_grid_entrants.csv)
- labels: [podium_labels.csv](../data/2024_china/podium_labels.csv)
- quality: [quality_report.json](../data/2024_china/quality_report.json)

Review checklist:

### 2024_china_gp-ENTRANTS — Eligible entrants and normal GP sessions

20 entrants; duplicate feature rows=0. Count is 20; this is a coverage check, not eligibility approval.

**M2 check:** Confirm the eligible entrant list at each forecast stage. Explain withdrawals/substitutions and any count difference. Confirm normal Qualifying and Race in this meeting, excluding sprint sessions.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_china_gp-QUALIFYING — Missing qualifying data and classification

Missing feature counts: {"qualifying_position": 0, "qualifying_gap_seconds": 0, "practice_gap_seconds": 0, "qualifying_air_temp_c": 0, "qualifying_track_temp_c": 0, "qualifying_rainfall": 0, "grid_position": 0}. Affected qualifying rows: [].

**M2 check:** Verify normal-GP qualifying classification and confirm no missing qualifying values were overlooked. Never substitute grid positions for qualifying classification.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_china_gp-LAP-VALIDITY — Qualifying valid-lap reconstruction

3 deleted/reinstated messages found. Provisional filtering does not fully resolve pit-in, deleted or reinstated laps. Raw messages are listed individually below.

**M2 check:** Review every event below and the full chronological qualifying race-control log. Match by driver and lap, resolve reinstatements, and check best valid lap across all Q1/Q2/Q3. Recheck the session-fastest reference: changing one driver's fastest valid lap can change every qualifying gap. Record proposed corrections without editing feature CSVs in this package.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_china_gp-PRACTICE — Practice selection, lap validity and driver identity

Selected Practice 1 (9663). Rejected-lap counts: {"pit_out_or_unknown": 71, "invalid_or_missing_duration": 18, "incomplete_sectors": 0}. Identity review flags: [].

**M2 check:** Confirm one common latest comparable practice before normal qualifying (FP3 when present; China uses FP1). Exclude sprint sessions, pit-out/incomplete/pit-in laps and invalid/deleted laps. Confirm driver-number identity, including substitutes; review track-evolution limitations.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_china_gp-WEATHER — Qualifying weather

Shared qualifying weather comes from one cached /weather response; missing counts are included above.

**M2 check:** Confirm qualifying-session air/track-temperature medians and any-rainfall aggregation, shared by all drivers and available by the chosen forecast cutoff.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_china_gp-GRID — Final grid and penalties

Grid integrity: {"populated": 20, "unique_driver_assignments": 20, "positions": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20], "complete_1_to_n": true}. Stored grid_verified=False; no M2 attestation has been supplied.

**M2 check:** Confirm final grid, including penalties and pit-lane arrangements, for every eligible starter. OpenF1 starting_grid is keyed by qualifying session 9664, not race 9673. Structural uniqueness/completeness alone is not final-grid verification. Record source timing and any correction.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_china_gp-CUTOFF-Q — Post-qualifying forecast cutoff remains unverified

Intended session-end cutoff: 2024-04-20T08:00:00+00:00. Historical availability of classification/weather/lap validity at this instant is not established.

**M2 check:** Enter the verified UTC forecast cutoff in confirmed_cutoff_utc; document when every qualifying-stage input was available and whether late corrections were known then. Later retrieval timestamps do not prove earlier availability.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_china_gp-CUTOFF-G — Post-grid forecast cutoff is unresolved

Recorded post-grid cutoff: None (unknown).

**M2 check:** Enter a verified pre-race UTC forecast cutoff in confirmed_cutoff_utc. Establish when the final penalized grid was published and available, and confirm it precedes race start. Keep unresolved if existing evidence is insufficient; do not infer it from race outcomes or scheduled race time.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_china_gp-LABELS — Race classification and separate podium labels

Classification coverage complete=True; missing labels=0; positive podium labels=3; issues=[].

**M2 check:** Audit only the separate labels against the normal Grand Prix race classification. Confirm top three and DNF/DNS/DSQ interpretation; leave ambiguous targets unresolved. Never use this evidence to construct prediction features or filter entrants retrospectively.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_china_gp-LAP-01 — Deleted qualifying lap — #2 Logan SARGEANT

UTC message 2024-04-20T07:07:19+00:00; lap 3; reported time not given; identity basis: CAR number parsed from message. Exact message: CAR 2 (SAR) LAP DELETED - TRACK LIMITS AT TURN 10 LAP 3 15:03:49

**M2 check:** Resolve this event against the full log and matching lap. Check later reinstatement/deletion and whether it changes best valid pace or the session-wide reference. Record evidence and proposed correction; no automatic feature change.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_china_gp-LAP-02 — Deleted qualifying lap — #23 Alexander ALBON

UTC message 2024-04-20T07:09:40+00:00; lap 4; reported time 4:11.475; identity basis: CAR number parsed from message. Exact message: CAR 23 (ALB) TIME 4:11.475 DELETED - TRACK LIMITS AT TURN 1 LAP 4 15:06:55

**M2 check:** Resolve this event against the full log and matching lap. Check later reinstatement/deletion and whether it changes best valid pace or the session-wide reference. Record evidence and proposed correction; no automatic feature change.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

### 2024_china_gp-LAP-03 — Deleted qualifying lap — #11 Sergio PEREZ

UTC message 2024-04-20T07:10:15+00:00; lap 3; reported time not given; identity basis: CAR number parsed from message. Exact message: CAR 11 (PER) LAP DELETED - TRACK LIMITS AT TURN 1 LAP 3 15:06:55

**M2 check:** Resolve this event against the full log and matching lap. Check later reinstatement/deletion and whether it changes best valid pace or the session-wide reference. Record evidence and proposed correction; no automatic feature change.

- Review status: **unresolved** (choose verified / corrected / unresolved)
- Reviewer / reviewed at UTC: ____________________
- Confirmed cutoff UTC, if applicable: ____________________
- Correction details: ____________________
- Evidence and notes: ____________________

Deleted/reinstated messages are reproduced verbatim above. UTC is the message record timestamp; trailing clock times inside messages are preserved as supplied and are not assumed to be UTC. Driver/lap values parsed from prose remain interpretations for review.
