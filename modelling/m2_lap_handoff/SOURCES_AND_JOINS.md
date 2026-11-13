# Source extraction and joining procedure

These are the project's required OpenF1 mappings, not a new downloader. Preserve
the exact raw responses, request parameters, retrieval UTC and source revisions
when M2 obtains data under its separately authorized workflow.

| Information | OpenF1 evidence / derivation | Required review |
|---|---|---|
| Weekend and session | sessions/meeting evidence; meeting_key, session_key, dates, session_name and circuit context | Same canonical dated GP meeting; exact Practice 1/2/3; not sprint/qualifying/race |
| Person and car number | drivers for the exact practice session; driver_number and display fields | Reviewed race-person crosswalk; account for practice-only substitutes and number reuse |
| Circuit/layout | Session/meeting circuit evidence and M2 circuit crosswalk | Stable layout-aware circuit_id; no country/name-only match |
| Lap start and duration | laps: session_key, driver_number, lap_number, date_start, lap_duration | date_start must be evidenced as target lap start; lap_duration is seconds and target only |
| Compound and tire age | stints: session_key, driver_number, stint_number, lap_start, lap_end, compound, tyre_age_at_start | Unique interval membership, reused tires, numbering convention and as-of availability |
| Track temperature | weather: session_key, date, track_temperature | Celsius; additionally establish available_at_utc, freshness and conflict resolution |
| Clean-lap eligibility | Lap completeness, pit evidence, session/race-control flags and deletion/reinstatement logs | Full chronological adjudication; record evidence and exclusions |

1. **Fix weekend/session scope.** Map the dated meeting to race_id and layout.
   Record normal practice session keys and GP race start separately. Multiple
   normal practice sessions may be included: the podium task's single-common-
   practice rule does not restrict this lap-time dataset. Keep all sessions of a
   weekend together for later temporal splitting. Never join on event name alone.
2. **Resolve identity.** Join session drivers to laps on
   (session_key, driver_number), many laps to one driver. Map to a reviewed
   (race_id, driver_number) -> driver_id/name crosswalk. If substitutions conflict
   with the implementation's one-person-per-number-per-weekend constraint,
   quarantine and ask M3 to resolve support; do not force the qualifying roster
   onto practice laps or merge people. Map race_id to one reviewed circuit_id.
3. **Deduplicate laps.** Require a unique
   (session_key, driver_number, lap_number) source lap, matching canonical keys.
   Preserve conflicting revisions in evidence; resolve them explicitly instead
   of keeping the first/last row silently. Assign a stable example_id.
4. **Attach exactly one stint.** Restrict to the same session and driver, then
   require stint.lap_start <= target lap_number <= stint.lap_end. Reject zero or
   multiple matching intervals, missing bounds, conflicting compounds or ambiguous
   numbering. Retain stint_number in evidence, outside the feature table.
   Use the A1 convention only after M2 confirms it:

       tyre_age_laps = tyre_age_at_start + (lap_number - stint_lap_start)

   First numbered stint lap has the reported starting age; do not add one.
   Preserve reused-tire starting age, including cross-session reuse. Check pit-out
   counting and boundary cases with raw evidence. Final lap_end can audit membership
   later but cannot prove membership/compound/age was known at target start.
5. **Attach weather backward in time.** For the same practice session, filter
   observations to date <= prediction_time_utc AND available_at_utc <= that cutoff.
   Select the greatest observation date, not the greatest retrieval timestamp.
   Simultaneous conflicting temperatures require resolution. Store its date as
   weather_observed_at_utc and temperature as track_temperature_c. Enforce an
   explicitly M2-approved positive maximum age in seconds. Do not choose the
   example fixture's 120 seconds as a default policy. Never use future-nearest
   matching, forward interpolation, lap means, session medians or qualifying weather.
6. **Separate target.** Join the approved source lap duration to example_id into
   labels.csv only. Establish lap_end_utc > lap_start_utc and
   target_available_at_utc >= lap_end_utc. Reconcile start/end/duration discrepancies
   with source semantics; do not invent timestamps to make them agree.

Before exporting, audit join cardinalities and report input/matched/ambiguous/
missing/excluded counts by weekend, session and reason. Any many-to-many join is
a review failure, not an invitation to deduplicate the expanded output.

# Validity, missing records and leakage

M2's A3 policy must identify complete timed normal practice flying laps and exclude
pit-out, pit-in, incomplete, invalid/deleted and non-comparable laps affected by
flags, interruptions or documented conditions. Audit later reinstatements against
the full chronological log. A finite duration or complete sectors alone does not
prove a clean lap. Declare dry/wet and compound support explicitly; allowed schema
categories are not evidence of model support. Preserve excluded candidates and reasons.

The prediction cutoff is lap start, not lap end, session end or retrieval time.
Every feature needs evidence of availability at or before that cutoff. An event
timestamp alone is insufficient. Unknown availability remains unresolved even if
the historical API returns a populated field. Stints without availability evidence
remain quarantined or explicitly retrospective-only outside the ready dataset.

Later clean-lap review may decide target eligibility, but that review decision,
duration, sectors, final stint length, later pit stop, race outcome and future
weather never become predictors. Historical accuracy is conditional on this clean
subset. Keep targets and target-availability provenance separate from input lineage.

Quarantine missing input/target, ambiguous identity/stint, stale/missing weather,
unknown timing or unresolved validity. Do not impute or manufacture these values.
Apply corrections only in a newly versioned export, preserving old evidence.
An unresolved non-null value is also unready. Quarantining must be visible in
coverage and reviewed exclusions rather than silently dropping inconvenient laps.

Supply chronological complete weekend groups, not a random lap split. M3 owns
the evaluation plan and train-only preprocessing. The implementation's five-weekend
minimum only permits its 60/20/20 split; it establishes no real-data sufficiency.
Discuss repeated circuit/person/compound coverage with M3: unseen categories are
unsupported, and more laps at five distinct circuits do not solve that limitation.
