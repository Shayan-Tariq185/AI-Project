# Exact historical training interface

`features.csv` has exactly these columns in this order, with no index column.
All 13 are required and non-null for historical rows. The contract permits null
session_key, lap_number and weather_observed_at_utc only in scenario mode;
scenarios never enter the historical training dataset.

| Column | Type / units | Historical meaning |
|---|---|---|
| example_id | Nonempty string | Unique within dataset version; stable lap example key |
| race_id | Nonempty string | Reviewed canonical GP weekend ID |
| session_key | Positive integer; identifier | Exact normal Practice 1, 2 or 3 session |
| driver_number | Positive integer; car number | Race-specific number matching reviewed person crosswalk |
| driver_name | Nonempty string | Display name only |
| driver_id | Nonempty string; category | Stable canonical person ID, independent of name/number |
| circuit_id | Nonempty string; category | Reviewed circuit/layout ID |
| lap_number | Positive integer; lap count | Actual target lap number in that session |
| prediction_time_utc | Timezone-aware ISO 8601 UTC | Target lap start, before GP race start |
| compound | String category | SOFT, MEDIUM, HARD, INTERMEDIATE or WET; also requires reviewed regime support |
| tyre_age_laps | Integer >= 0; completed tire laps | Tire age immediately before target lap starts |
| track_temperature_c | Finite float; degrees Celsius | Latest eligible practice weather observation at cutoff |
| weather_observed_at_utc | Timezone-aware ISO 8601 UTC | Timestamp of that selected observation, <= lap start |

`labels.csv` is a separate file with exactly these columns in this order:

| Column | Type / units | Rule |
|---|---|---|
| example_id | Nonempty string | Unique; exact one-to-one key-set match with features |
| lap_time_actual_seconds | Finite float > 0; seconds | OpenF1 laps.lap_duration for the approved target lap |

The only model features are `compound`, `tyre_age_laps`,
`track_temperature_c`, `circuit_id`, `driver_id`. Keep them in their original
units; do not pre-encode categories or scale numbers. M3 fits preprocessing.
No label, sector duration, finishing result, review flag, raw stint length or
future weather may be appended to features. Preserve metadata in sidecars.

Reject booleans in numeric fields, fractional integer values, infinities, empty
strings, duplicate example IDs and duplicate physical laps under different IDs.
The physical-lap key is (race_id, session_key, driver_id, lap_number).
Within a race, each person has one number/name, each number identifies one person,
and circuit_id is consistent. Names corroborate identity; they are not join keys.

Use explicit UTC offsets (prefer +00:00 or Z). Naive timestamps require M2's
documented conversion before inclusion. Missing numeric data stays null in draft
records, never zero, a median, a guessed value or the text 'unknown'. Missing
historical essential inputs/targets are quarantined, not passed to this schema.
