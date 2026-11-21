# M2 Data Dictionary

## Sources

- OpenF1 `/sessions`, `/drivers`, `/laps`, `/weather`, `/session_result`,
  `/starting_grid`, and `/race_control`.
- Jolpica integration is not implemented in this repository snapshot.

## Historical scope

The five-race 2024 pilot contains Bahrain, Saudi Arabia, Australia, Japan,
and China. The data is draft evidence and is not M2-approved training data.

## Core training columns

| Column | Type | Unit | Source | Missing handling |
|---|---|---:|---|---|
| race_id | string | - | Derived from OpenF1 meeting/session | Must be present |
| race_date | ISO UTC timestamp | - | OpenF1 race session | Must be present |
| race_name | string | - | Race identity | Must be present |
| circuit | string | - | OpenF1 circuit_short_name | Must be present |
| season | integer | year | Session metadata | Must be present |
| round | integer | round number | Pilot manifest | Fixed by race scope |
| driver_number | integer | car number | OpenF1 qualifying drivers | Must be unique within race |
| driver_code | string | - | Driver display name | Derived fallback |
| driver_name | string | - | OpenF1 qualifying drivers | Must be present |
| team | string | - | OpenF1 race classification | Audit if missing |
| quali_best_s | float | seconds | Qualifying laps/classification | Null if no valid result |
| quali_gap_s | float | seconds | Driver fastest minus pole | Null if no valid result |
| quali_gap_pct | float | ratio | Gap divided by reference | Null if no valid result |
| practice_best_s | float | seconds | Fastest selected practice lap | Null if no valid lap |
| practice_gap_s | float | seconds | Practice gap to fastest lap | Null if no valid lap |
| quali_air_temp_c | float | Celsius | Median qualifying weather | Null if unavailable |
| quali_track_temp_c | float | Celsius | Median qualifying weather | Null if unavailable |
| quali_humidity | float | percent | Not currently cached | Null |
| quali_rainfall | integer | 0/1 | Qualifying weather | Null if not measured |
| quali_wind_ms | float | m/s | Not currently cached | Null |
| grid_position | integer | position | OpenF1 starting grid for normal qualifying | Null until verified |
| pit_lane_start | integer | 0/1 | Not established by cache | 0 only as an explicit draft default |
| top3_finish | integer | 0/1 | Official Grand Prix race classification | 0 DNF/DNS/DSQ; null if ambiguous |

## Lap table

Lap extraction is blocked until normal-practice `/stints` responses are cached.
No compound or tire-age values are invented. The lap coverage file records this
limitation.

## Known limitations

- The five-race pilot is not approved training evidence.
- Deleted/reinstated laps require FIA/race-control review.
- Final grid timing and penalties require M2 verification.
- Historical forecast cutoffs are not established.
- Jolpica is not implemented.
- Humidity and wind are not cached.
- Pit-lane-start status is not established.
