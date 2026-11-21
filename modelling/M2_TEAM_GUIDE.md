# M2 Data and Race Operations Guide

This document explains the M2 implementation in this repository, where data comes from,
how the code transforms it, and how teammates can check the results locally.

## M2 responsibility

M2 owns data collection, cleaning, verification, and race-weekend handoff data:

- Collect raw OpenF1 API responses.
- Cache raw responses locally.
- Create post-qualifying feature data.
- Create post-grid feature data.
- Create a separate official-podium label table.
- Create race and lap provenance/quality reports.
- Identify missing, deleted, unmatched, or ambiguous data.
- Review all issues before describing a race as M2 approved.
- Hand verified tables and evidence to M3.

M2 does not train the models. M2 does not publish a final prediction.

The main M2 contract is in `CONTRACT.md`, with the proposed contract-v2 details in
`CONTRACT_v2.md`.

## Approved sources

The implementation uses OpenF1 for detailed session, lap, tire, weather, and
classification data.

Jolpica is listed as an approved supplementary source for historical verification,
including qualifying, starting grids, and race results. Jolpica integration is
documented in the contracts, but the current implementation does not contain a
Jolpica API adapter or Jolpica download pipeline.

The current pilot uses cached OpenF1 data only.

## Repository location

Run M2 commands from:

```text
C:\Users\mahru\Downloads\FAST SE\SEMESTER 5\AI\project\AI-Project\modelling
```

OpenF1 collection and race building:

- `openf1_prototype.py`
- `collect_pilot.py`

Lap and podium handoff validation:

- `lap_handoff.py`
- `podium_handoff.py`

Lap package:

- `m2_lap_handoff/`

Verification package:

- `verification/`

## Raw data and caching

The client in `openf1_prototype.py` requests these OpenF1 endpoints:

- `/v1/sessions`
- `/v1/drivers`
- `/v1/laps`
- `/v1/weather`
- `/v1/session_result`
- `/v1/starting_grid`
- `/v1/race_control`

For example:

```text
https://api.openf1.org/v1/laps?session_key=9468
```

Successful JSON responses are saved in:

```text
modelling/data/<race>/raw/
```

Bahrain examples include:

```text
sessions_year-2024_country_name-Bahrain.json
drivers_session_key-9468.json
laps_session_key-9468.json
weather_session_key-9468.json
session_result_session_key-9468.json
starting_grid_session_key-9468.json
race_control_session_key-9468.json
```

The cache behavior is:

- If the matching JSON file exists, load it from disk.
- If it does not exist and network collection is enabled, request it.
- Wait at least 2.1 seconds between live requests.
- Retry HTTP 429 and selected temporary server errors.
- Record HTTP status and collection timestamps in quality reports.
- Never send live requests during offline replay.

## Five-race pilot scope

`collect_pilot.py` is intentionally limited to:

- 2024 Bahrain
- 2024 Saudi Arabia
- 2024 Australia
- 2024 Japan
- 2024 China

It does not expand to every race or season automatically.

The five-race collection logic processes the same session types and meeting keys
for every race. It selects a normal Grand Prix race and normal qualifying session
from the same meeting. Sprint qualifying and sprint race sessions are excluded.

Bahrain uses:

- Meeting: `1229`
- Qualifying: `9468`
- Practice: `9467`
- Race: `9472`

China falls back to Practice 1 because the sprint weekend does not have Practice 3.

## What happens to the data

### Entrants

Entrants come from the qualifying-session driver roster. Race-result driver coverage
is not used to select or remove inference entrants.

The driver number is the race-specific join key. Names are display fields and are
not the primary join mechanism.

### Qualifying pace

For qualifying laps:

1. Reject pit-out laps.
2. Reject laps with missing or invalid duration.
3. Reject laps without three positive sector durations.
4. Find each driver's fastest valid lap.
5. Find the fastest valid lap for the whole qualifying session.
6. Calculate:

```text
qualifying_gap = driver_fastest_lap - session_fastest_lap
```

The session pole driver has a gap near or equal to zero.

Lap deletions and reinstatements remain under M2 review. The race-control messages
are stored in quality reports and the verification worksheet.

### Practice pace

The implementation prefers the latest comparable practice before qualifying:

1. Practice 3, if it exists.
2. Otherwise, the latest prior practice session.

For practice laps:

1. Reject pit-out laps.
2. Reject laps with missing or invalid duration.
3. Reject laps without complete sector durations.
4. Find each driver's fastest valid lap.
5. Find the session-fastest lap.
6. Calculate a practice gap relative to that fastest lap.

Track evolution is a known limitation because lap times change during a session.

### Qualifying weather

The qualifying `/weather` response is summarized as:

- Median air temperature.
- Median track temperature.
- Rainfall flag:
  - `1` if any qualifying observation reports rainfall.
  - `0` if observations exist but none report rainfall.
  - `null` if rainfall was not measured.

The weather values are shared across all drivers in the race.

### Starting grid

The starting-grid request is associated with normal qualifying, not the race.

The implementation checks:

- The meeting key matches.
- The qualifying session key matches.
- Driver assignments are unique.
- Grid positions are unique positive integers.
- Grid positions cover one through the entrant count.
- Grid drivers are not outside the qualifying entrant roster.

These checks verify structure only. They do not replace FIA/M2 final-grid approval.

### Podium labels

Official race classifications create the training target:

- `1` when the classified finishing position is 1, 2, or 3.
- `0` for positions after third.
- `0` for DNF, DNS, or DSQ according to the current contract.
- `null` if the result or status is ambiguous.

Labels are kept in:

```text
podium_labels.csv
```

Labels must never be placed in post-qualifying or post-grid forecast input tables.

## Generated files

For one race:

```text
modelling/data/<race>/draft_entrants.csv
modelling/data/<race>/post_qualifying_entrants.csv
modelling/data/<race>/post_grid_entrants.csv
modelling/data/<race>/podium_labels.csv
modelling/data/<race>/quality_report.json
modelling/data/<race>/raw/
```

After the five-race pilot:

```text
modelling/data/pilot_2024/post_qualifying_features.csv
modelling/data/pilot_2024/post_grid_features.csv
modelling/data/pilot_2024/podium_labels.csv
modelling/data/pilot_2024/race_manifest.csv
modelling/data/pilot_2024/quality_report.json
modelling/data/pilot_2024/offline_quality_report.json
modelling/data/pilot_2024/replay_verification.json
```

The post-qualifying table contains no grid position.

The post-grid table contains the grid position, but it is not M2 approved simply
because the JSON structurally reports one.

## Lap-time M2 package

Lap-time scope is defined in:

- `m2_lap_handoff/README.md`
- `m2_lap_handoff/SCHEMA.md`
- `m2_lap_handoff/SOURCES_AND_JOINS.md`
- `m2_lap_handoff/EVIDENCE.md`
- `m2_lap_handoff/CHECKLIST.md`

Lap rows are restricted to clean normal practice flying laps.

The exact historical lap feature columns are in `m2_lap_handoff/SCHEMA.md`.
Labels are separate and contain:

- `example_id`
- `lap_time_actual_seconds`

Weather matching must use the latest eligible observation available at or before
the prediction cutoff. It must not silently use qualifying-session weather or a
future observation.

Tire age is derived from stint information and lap numbering, but it requires M2
review of the exact convention. Missing or unresolved evidence remains unresolved;
it is not replaced with a median or a guessed value.

## Verification

The verification worksheet is:

```text
modelling/verification/CHECKLIST.md
```

The editable review register is:

```text
modelling/verification/issues.csv
```

Qualifying deletion/reinstatement events are listed in:

```text
modelling/verification/qualifying_lap_events.csv
```

Source hashes are recorded in:

```text
modelling/verification/source_manifest.json
```

Possible review statuses are:

- `verified`
- `corrected`
- `unresolved`

A race is not approved merely because collection or smoke validation passed.

## Environment setup

Open PowerShell and move to the repository:

```powershell
cd "C:\Users\mahru\Downloads\FAST SE\SEMESTER 5\AI\project\AI-Project"
```

Check Python:

```powershell
py --version
```

Install the M2 dependencies:

```powershell
py -m pip install -r modelling\requirements.txt
```

The required packages are pandas, NumPy, scikit-learn, joblib, and pytest.

## Commands to inspect the implementation

Check branch and local changes:

```powershell
git branch --show-current
git status --short --branch
git diff --stat
```

View Bahrain draft data:

```powershell
Get-Content ".\modelling\data\2024_bahrain\draft_entrants.csv"
```

View Bahrain post-qualifying data:

```powershell
Get-Content ".\modelling\data\2024_bahrain\post_qualifying_entrants.csv"
```

View Bahrain post-grid data:

```powershell
Get-Content ".\modelling\data\2024_bahrain\post_grid_entrants.csv"
```

View Bahrain podium labels:

```powershell
Get-Content ".\modelling\data\2024_bahrain\podium_labels.csv"
```

View Bahrain quality report:

```powershell
Get-Content ".\modelling\data\2024_bahrain\quality_report.json"
```

List cached raw files:

```powershell
Get-ChildItem ".\modelling\data\2024_bahrain\raw"
```

## Commands to verify feature tables

Move to the repository root:

```powershell
cd "C:\Users\mahru\Downloads\FAST SE\SEMESTER 5\AI\project\AI-Project"
```

Print feature and label shapes:

```powershell
py -c "import pandas as pd; p=pd.read_csv(r'modelling/data/2024_bahrain/post_qualifying_entrants.csv'); g=pd.read_csv(r'modelling/data/2024_bahrain/post_grid_entrants.csv'); l=pd.read_csv(r'modelling/data/2024_bahrain/podium_labels.csv'); print('Post-qualifying:', p.shape); print('Post-grid:', g.shape); print('Labels:', l.shape); print('Podium labels:', int(l.is_podium_actual.sum()))"
```

Verify unique race/driver keys:

```powershell
py -c "import pandas as pd; p=pd.read_csv(r'modelling/data/2024_bahrain/post_qualifying_entrants.csv'); g=pd.read_csv(r'modelling/data/2024_bahrain/post_grid_entrants.csv'); print('Post-qualifying duplicate keys:', p.duplicated(['race_id','driver_number']).sum()); print('Post-grid duplicate keys:', g.duplicated(['race_id','driver_number']).sum())"
```

Verify that grid positions are complete and unique:

```powershell
py -c "import pandas as pd; g=pd.read_csv(r'modelling/data/2024_bahrain/post_grid_entrants.csv'); print('Rows:', len(g)); print('Unique positions:', g.grid_position.nunique()); print('Missing positions:', g.grid_position.isna().sum())"
```

Check missing feature values:

```powershell
py -c "import pandas as pd; p=pd.read_csv(r'modelling/data/2024_bahrain/post_grid_entrants.csv'); print(p.isna().sum())"
```

Check exact post-qualifying and post-grid columns:

```powershell
py -c "import pandas as pd; p=pd.read_csv(r'modelling/data/2024_bahrain/post_qualifying_entrants.csv'); g=pd.read_csv(r'modelling/data/2024_bahrain/post_grid_entrants.csv'); print('Post-qualifying columns:', p.columns.tolist()); print('Post-grid columns:', g.columns.tolist())"
```

## Offline replay command

Move to the modelling directory:

```powershell
cd "C:\Users\mahru\Downloads\FAST SE\SEMESTER 5\AI\project\AI-Project\modelling"
```

Replay the five-race pilot without network access:

```powershell
py collect_pilot.py --offline
```

Offline replay:

- Loads existing JSON cache files.
- Records missing caches instead of fetching them.
- Rebuilds the pilot feature and label tables.
- Reports offline collection status.

It does not establish M2 approval.

## Live collection command

Only use live collection when the team has approved API access and network use:

```powershell
py openf1_prototype.py --year 2024 --country Bahrain
```

The live collector writes to:

```text
modelling/data/2024_bahrain/
```

It may also return HTTP 401 or another API error. API errors are recorded in the
report and do not mean collection succeeded.

Do not run live collection merely to generate model-training approval.

## Lap handoff validation

This command validates synthetic lap examples and protected source files:

```powershell
cd "C:\Users\mahru\Downloads\FAST SE\SEMESTER 5\AI\project\AI-Project\modelling"
py -B m2_lap_handoff\validate_examples.py
```

It confirms only:

- Exact synthetic lap schemas.
- Matching synthetic label keys.
- Local documentation links.
- Protected-file baseline hashes.

It does not approve real lap data.

## Verification tests

Run the M2 verification package tests:

```powershell
cd "C:\Users\mahru\Downloads\FAST SE\SEMESTER 5\AI\project\AI-Project\modelling"
py -B -m unittest discover -s verification -p test_verification.py -v
```

The tests check:

- Five-race package scope.
- 57 unresolved review items.
- Qualifying lap-event counts.
- Critical review flags.
- Source paths and hashes.
- That package generation does not modify evidence.
- That review worksheet snapshots match.

If a test fails because of line endings or generated evidence differences,
record the failure instead of treating it as M2 approval.

## Current known limitations

The pilot has several unresolved M2 items:

- Deleted and pit-in qualifying laps require review.
- Deleted/reinstated lap events are present in the race-control logs.
- The final starting grid requires official/M2 verification.
- Post-grid publication cutoff is not established.
- Post-qualifying historical publication availability is not established.
- The eligible roster and replacement drivers require M2 review.
- Saudi Arabia has a driver with missing qualifying values.
- Australia has 19 entrants instead of the usual 20.
- China uses Practice 1 because FP3 is unavailable.
- No Jolpica implementation currently corroborates OpenF1.
- The quality reports mark the data as unapproved.

These limitations mean the existing pilot is suitable for implementation,
offline replay, and contract smoke testing, but not for production training.

## M2 approval process

Before handing a race to M3:

1. Review the race in `verification/CHECKLIST.md`.
2. Enter decisions in `verification/issues.csv`.
3. Verify the eligible entrant roster.
4. Verify qualifying positions and gaps.
5. Review practice-session selection and lap validity.
6. Verify weather timing and values.
7. Verify final-grid penalties and publication time.
8. Verify the podium classification and statuses.
9. Close every unresolved quality item.
10. Create a reviewed M2 handoff containing exact table hashes and lineage.
11. Let M3 validate and accept the handoff.

Until those steps are complete, M2 should describe the data as:

```text
collected_draft_requires_M2
```
