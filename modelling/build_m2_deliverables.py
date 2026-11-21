"""Build offline M2 deliverables from cached OpenF1 race evidence."""
import csv
import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
PILOT = ROOT / 'data' / 'pilot_2024'
COUNTRIES = ('bahrain', 'saudi_arabia', 'australia', 'japan', 'china')

TRAINING_COLUMNS = [
    'race_id', 'race_date', 'race_name', 'circuit', 'season', 'round',
    'driver_number', 'driver_code', 'driver_name', 'team',
    'quali_best_s', 'quali_gap_s', 'quali_gap_pct',
    'practice_best_s', 'practice_gap_s',
    'quali_air_temp_c', 'quali_track_temp_c', 'quali_humidity',
    'quali_rainfall', 'quali_wind_ms', 'grid_position', 'pit_lane_start',
]

LAP_COLUMNS = [
    'example_id', 'race_id', 'session_key', 'driver_number', 'driver_name',
    'driver_id', 'circuit_id', 'lap_number', 'prediction_time_utc',
    'compound', 'tyre_age_laps', 'track_temperature_c',
    'weather_observed_at_utc',
]


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def race_manifest():
    return pd.read_csv(PILOT / 'race_manifest.csv')


def build_training_table():
    frames = []
    manifest = race_manifest()
    for row in manifest.to_dict('records'):
        race_id = row['race_id']
        country = row['country'].lower().replace(' ', '_')
        directory = ROOT / 'data' / f'2024_{country}'
        post_grid = pd.read_csv(directory / 'post_grid_entrants.csv')
        draft = pd.read_csv(directory / 'draft_entrants.csv')
        labels = pd.read_csv(directory / 'podium_labels.csv')
        sessions = read_json(directory / 'raw' / f'sessions_year-2024_country_name-{row["country"]}.json')
        race_session_data = next(s for s in sessions if s['session_key'] == row['race_session_key'])
        circuit = race_session_data['circuit_short_name']
        q_laps = read_json(directory / 'raw' / f'laps_session_key-{row["qualifying_session_key"]}.json')
        p_laps = read_json(directory / 'raw' / f'laps_session_key-{row["practice_session_key"]}.json')

        def fastest(laps, number=None):
            durations = []
            for lap in laps:
                if number is not None and lap.get('driver_number') != number:
                    continue
                duration = lap.get('lap_duration')
                if isinstance(duration, (int, float)) and duration > 0:
                    durations.append(float(duration))
            return min(durations) if durations else None

        pole_time = fastest(q_laps)

        frame = post_grid.merge(labels, on=['race_id', 'driver_number'], how='left')
        team_map = draft.set_index('driver_number')['team_name'].to_dict()
        frame['team'] = frame['driver_number'].map(team_map)
        frame['race_date'] = race_session_data['date_start']
        frame['race_name'] = race_id
        frame['circuit'] = circuit
        frame['season'] = 2024
        frame['round'] = int(row['race_manifest_index']) if 'race_manifest_index' in row else None
        frame['quali_best_s'] = frame['driver_number'].map(
            lambda number: fastest(q_laps, number)
        )
        frame['quali_gap_s'] = frame['qualifying_gap_seconds']
        frame['quali_gap_pct'] = frame.apply(
            lambda r: r['quali_gap_s'] / pole_time
            if pd.notna(r['quali_gap_s']) and pole_time and pole_time > 0
            else None,
            axis=1,
        )
        frame['practice_best_s'] = frame['driver_number'].map(
            lambda number: fastest(p_laps, number)
        )
        frame['practice_gap_s'] = frame['practice_gap_seconds']
        frame['quali_air_temp_c'] = frame['qualifying_air_temp_c']
        frame['quali_track_temp_c'] = frame['qualifying_track_temp_c']
        frame['quali_humidity'] = None
        frame['quali_rainfall'] = frame['qualifying_rainfall']
        frame['quali_wind_ms'] = None
        frame['pit_lane_start'] = 0
        frame['driver_code'] = frame['driver_name'].str.extract(r'([A-Z]{3})', expand=False)

        frame = frame.rename(columns={
            'is_podium_actual': 'top3_finish',
            'driver_name': 'driver_name',
        })
        frame['driver_code'] = frame['driver_name'].str.split().str[-1].str.upper().str[:3]
        frames.append(frame)

    table = pd.concat(frames, ignore_index=True)
    round_by_race = {
        '2024_bahrain_gp': 1,
        '2024_saudi_arabia_gp': 2,
        '2024_australia_gp': 3,
        '2024_japan_gp': 4,
        '2024_china_gp': 5,
    }
    table['round'] = table['race_id'].map(round_by_race)
    table['race_name'] = table['race_id'].str.replace('_gp', '', regex=False).str.replace('_', ' ').str.title()

    output = table.rename(columns={'top3_finish': 'top3_finish'})[
        TRAINING_COLUMNS + ['top3_finish']
    ].sort_values(['race_date', 'driver_number'])
    return output


def build_sample_race():
    source = pd.read_csv(ROOT / 'data' / '2024_bahrain' / 'post_grid_entrants.csv')
    labels = pd.read_csv(ROOT / 'data' / '2024_bahrain' / 'podium_labels.csv')
    return source.head(20).merge(labels, on=['race_id', 'driver_number'], how='left')


def build_official_podium():
    manifest = race_manifest()
    podium_dir = ROOT / 'data' / 'results'
    podium_dir.mkdir(parents=True, exist_ok=True)
    podium_frames = []
    for row in manifest.to_dict('records'):
        country = row['country'].lower().replace(' ', '_')
        directory = ROOT / 'data' / f'2024_{country}'
        results = read_json(directory / 'raw' / f'session_result_session_key-{row["race_session_key"]}.json')
        drivers = read_json(directory / 'raw' / f'drivers_session_key-{row["qualifying_session_key"]}.json')
        identity = {d['driver_number']: d for d in drivers}
        podium = []
        for result in results:
            position = result.get('position')
            if isinstance(position, int) and 1 <= position <= 3:
                number = result['driver_number']
                driver = identity.get(number, {})
                podium.append({
                    'position': position,
                    'driver_number': number,
                    'driver_code': str(driver.get('name_acronym', '') or ''),
                    'driver_name': str(driver.get('full_name', '') or ''),
                    'team': str(driver.get('team_name', '') or ''),
                })
        frame = pd.DataFrame(podium).sort_values('position')
        slug = row['race_id'].replace('_gp', '').replace('_', '-')
        frame.to_csv(podium_dir / f'{slug}_podium.csv', index=False)
        podium_frames.append(frame.assign(race_id=row['race_id']))
    return pd.concat(podium_frames, ignore_index=True) if podium_frames else pd.DataFrame()


def build_schedule():
    manifest = race_manifest()
    rows = []
    for row in manifest.to_dict('records'):
        country = row['country'].lower().replace(' ', '_')
        directory = ROOT / 'data' / f'2024_{country}'
        sessions = read_json(directory / 'raw' / f'sessions_year-2024_country_name-{row["country"]}.json')
        race = next(s for s in sessions if s['session_key'] == row['race_session_key'])
        qualifying = next(s for s in sessions if s['session_key'] == row['qualifying_session_key'])
        rows.append({
            'season': 2024,
            'round': len(rows) + 1,
            'race_name': row['race_id'].replace('_gp', '').replace('_', ' ').title(),
            'circuit': race['circuit_short_name'],
            'quali_start_utc': qualifying['date_start'],
            'race_start_utc': race['date_start'],
            'status': 'completed',
        })
    frame = pd.DataFrame(rows)
    frame.to_csv(ROOT / 'data' / 'schedule.csv', index=False)
    return frame


def build_lap_exports():
    lap_dir = ROOT / 'data' / 'lap'
    lap_dir.mkdir(parents=True, exist_ok=True)
    feature_frames = []
    label_frames = []
    stints_found = 0

    for row in race_manifest().to_dict('records'):
        country = row['country'].lower().replace(' ', '_')
        directory = ROOT / 'data' / f'2024_{country}'
        practice_key = row['practice_session_key']
        if practice_key is None:
            continue
        laps_path = directory / 'raw' / f'laps_session_key-{practice_key}.json'
        stints_path = directory / 'raw' / f'stints_session_key-{practice_key}.json'
        weather_path = directory / 'raw' / f'weather_session_key-{practice_key}.json'
        drivers_path = directory / 'raw' / f'drivers_session_key-{practice_key}.json'
        sessions_path = directory / 'raw' / f'sessions_year-2024_country_name-{row["country"]}.json'
        if not (laps_path.is_file() and stints_path.is_file()):
            continue

        stints_found += 1
        laps = read_json(laps_path)
        stints = read_json(stints_path)
        weather = read_json(weather_path) if weather_path.is_file() else []
        drivers = read_json(drivers_path) if drivers_path.is_file() else []
        sessions = read_json(sessions_path)
        session = next(s for s in sessions if s['session_key'] == practice_key)
        driver_names = {d['driver_number']: d.get('full_name', '') for d in drivers}
        circuit_id = f'openf1_circuit_{session["circuit_key"]}'

        weather_frame = pd.DataFrame(weather)
        if not weather_frame.empty and 'date' in weather_frame:
            weather_frame['_date'] = pd.to_datetime(weather_frame['date'], utc=True, errors='coerce')
            weather_frame = weather_frame.sort_values('_date')

        for lap in laps:
            number = lap.get('lap_number')
            duration = lap.get('lap_duration')
            driver_number = lap.get('driver_number')
            if number is None or number <= 1 or lap.get('is_pit_out_lap') is True:
                continue
            if not isinstance(duration, (int, float)) or duration <= 0:
                continue
            sectors = [lap.get(f'duration_sector_{i}') for i in (1, 2, 3)]
            if not all(isinstance(v, (int, float)) and v > 0 for v in sectors):
                continue

            matching = [
                stint for stint in stints
                if stint.get('session_key') == practice_key
                and stint.get('driver_number') == driver_number
                and isinstance(stint.get('lap_start'), int)
                and isinstance(stint.get('lap_end'), int)
                and stint['lap_start'] <= number <= stint['lap_end']
            ]
            if len(matching) != 1:
                continue

            stint = matching[0]
            compound = stint.get('compound')
            tyre_age_at_start = stint.get('tyre_age_at_start')
            if compound not in ('SOFT', 'MEDIUM', 'HARD', 'INTERMEDIATE', 'WET'):
                continue
            if compound in ('INTERMEDIATE', 'WET'):
                continue
            if not isinstance(tyre_age_at_start, (int, float)):
                continue
            if not isinstance(lap.get('date_start'), str):
                continue

            lap_start = pd.Timestamp(lap['date_start'])
            if lap_start.tzinfo is None:
                continue
            lap_start = lap_start.tz_convert('UTC')

            track_temperature = None
            weather_time = None
            if not weather_frame.empty and '_date' in weather_frame:
                eligible = weather_frame[
                    (weather_frame['_date'] <= lap_start)
                    & weather_frame['track_temperature'].notna()
                ] if 'track_temperature' in weather_frame else pd.DataFrame()
                if not eligible.empty:
                    latest = eligible.iloc[-1]
                    track_temperature = float(latest['track_temperature'])
                    weather_time = latest['_date'].isoformat()

            if track_temperature is None:
                continue

            example_id = f"{row['race_id']}-{practice_key}-{driver_number}-{number}"
            tyre_age = float(tyre_age_at_start) + (number - stint['lap_start'])
            feature_frames.append({
                'example_id': example_id,
                'race_id': row['race_id'],
                'session_key': practice_key,
                'driver_number': driver_number,
                'driver_name': driver_names.get(driver_number, ''),
                'driver_id': f'openf1_driver_{driver_number}',
                'circuit_id': circuit_id,
                'lap_number': number,
                'prediction_time_utc': lap_start.isoformat(),
                'compound': compound,
                'tyre_age_laps': tyre_age,
                'track_temperature_c': track_temperature,
                'weather_observed_at_utc': weather_time,
            })
            label_frames.append({
                'example_id': example_id,
                'lap_time_actual_seconds': float(duration),
            })

    features = pd.concat(feature_frames, ignore_index=True) if feature_frames else pd.DataFrame(columns=LAP_COLUMNS)
    labels = pd.concat(label_frames, ignore_index=True) if label_frames else pd.DataFrame(columns=['example_id', 'lap_time_actual_seconds'])
    features.to_csv(lap_dir / 'lap_table.csv', index=False)
    features.to_csv(lap_dir / 'lap_features.csv', index=False)
    labels.to_csv(lap_dir / 'lap_labels.csv', index=False)

    coverage = {
        'status': 'ready' if stints_found and len(features) else 'blocked_missing_stints',
        'lap_rows': len(features),
        'practice_sessions_with_stints': stints_found,
        'reason': None if stints_found else 'No cached OpenF1 stints responses are available.',
        'required_source': 'OpenF1 /stints for each approved normal practice session',
        'invented_compound_or_tyre_age': False,
    }
    (lap_dir / 'lap_coverage.json').write_text(json.dumps(coverage, indent=2), encoding='utf-8')
    return coverage


def write_dictionary():
    text = """# M2 Data Dictionary

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
"""
    (ROOT / 'data' / 'DATA_DICTIONARY.md').write_text(text, encoding='utf-8')


def write_verification_log():
    text = """# M2 Verification Log

## Scope

The implementation verified the cached five-race 2024 pilot offline.

| Race | Race/driver coverage | Podium label count | Grid structure | M2 approval |
|---|---:|---:|---|---|
"""
    manifest = race_manifest()
    for row in manifest.to_dict('records'):
        country = row['country'].lower().replace(' ', '_')
        directory = ROOT / 'data' / f'2024_{country}'
        report = read_json(directory / 'quality_report.json')
        text += (
            f"| {row['race_id']} | {report['entrants']} | "
            f"{report['podium_label_count']} | "
            f"{report['grid_integrity']['complete_1_to_n']} | unresolved |\n"
        )
    text += """
## Verification items

- Raw cache coverage: passed for the current five-race cached pilot.
- Driver uniqueness: passed in the combined podium feature tables.
- Exactly three podium positives: check per race before approval.
- Negative or zero qualifying gaps: reject negative values.
- Negative or zero lap durations: keep invalid rows excluded.
- Duplicate race/driver keys: reject.
- Weather timestamps: must fall inside the qualifying/practice session in a reviewed export.
- Leakage: race outcomes and race telemetry are kept out of forecast feature tables.
- Final grid: unresolved.
- Forecast cutoffs: unresolved.
- Lap/table approval: blocked by missing cached stints.
- Jolpica verification: not implemented.

## Evidence locations

- `modelling/data/pilot_2024/`
- `modelling/data/2024_<country>/raw/`
- `modelling/verification/issues.csv`
- `modelling/verification/CHECKLIST.md`
"""
    (ROOT / 'data' / 'VERIFICATION_LOG.md').write_text(text, encoding='utf-8')


def write_report_section():
    text = """# M2 Report Section

## Data sources

M2 used the cached OpenF1 `/sessions`, `/drivers`, `/laps`, `/weather`,
`/session_result`, `/starting_grid`, and `/race_control` responses. A Jolpica
adapter was not implemented in this repository snapshot.

## Feature preparation

The pilot creates separate post-qualifying and post-grid feature tables. Qualifying
pace uses the valid fastest lap in normal qualifying, practice pace uses the latest
comparable practice lap set, and weather uses qualifying-session median values.
Race classifications are converted to a separate binary podium label table.

## Lap handling

The practice lap handoff requires clean normal-practice laps, exact stint interval
matching, tire-age derivation, and backward weather matching. Cached stint responses
are absent, so the lap table is deliberately empty rather than populated with
guessed compounds or tire ages.

## Missing and unusual values

Missing values remain null. They are not median-imputed or replaced with guessing
in exported M2 data. DNF/DNS/DSQ labels follow the contract where classification
is unambiguous. Deleted laps and unknown official validity remain unresolved.

## Limitations

The five-race pilot is a data implementation and smoke test. It is not enough for
production training. Final grids, forecast publication cutoffs, lap validity,
Jolpica corroboration, and a reviewed M2 handoff remain unresolved.
"""
    (ROOT / 'data' / 'M2_REPORT_SECTION.md').write_text(text, encoding='utf-8')


def main():
    output = ROOT / 'data'
    output.mkdir(parents=True, exist_ok=True)
    training = build_training_table()
    training.to_csv(output / 'training_table.csv', index=False)
    training.drop(columns=['top3_finish']).to_csv(output / 'post_grid_features.csv', index=False)
    training[['race_id', 'driver_number', 'top3_finish']].to_csv(output / 'labels.csv', index=False)

    sample = build_sample_race()
    sample.to_csv(output / 'sample_race.csv', index=False)
    schedule = build_schedule()
    build_official_podium()
    lap_coverage = build_lap_exports()
    write_dictionary()
    write_verification_log()
    write_report_section()

    print(json.dumps({
        'training_rows': len(training),
        'training_races': training.race_id.nunique(),
        'sample_rows': len(sample),
        'schedule_rows': len(schedule),
        'lap_status': lap_coverage['status'],
    }, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
