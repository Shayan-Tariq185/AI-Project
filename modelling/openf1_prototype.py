"""Read-only OpenF1 smoke collector; all output is local, draft, and unverified."""
import argparse
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError
import pandas as pd
from m3 import BASE

ROOT = Path(__file__).resolve().parent
IDENTITY = ['race_id', 'driver_number', 'driver_name']

def stage_tables(data):
    """Only contract-required columns; traceability stays in draft/report files."""
    return {'post_qualifying': data[IDENTITY + BASE].copy(),
            'post_grid': data[IDENTITY + BASE + ['grid_position']].copy()}

class Client:
    # Shared across clients: a five-race run must not reset its request budget.
    last_request = 0
    def __init__(self, directory, offline=False):
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True)
        self.offline = offline
        self.calls = []
        self.last = 0

    def get(self, endpoint, **params):
        url = 'https://api.openf1.org/v1/' + endpoint + '?' + urlencode(params)
        path = self.directory / (endpoint + '_' + '_'.join(f'{k}-{v}' for k, v in params.items()) + '.json')
        if path.exists():
            result = json.loads(path.read_text())
            self.calls.append({'url': url, 'rows': len(result), 'cached': True})
            return result
        if self.offline:
            self.calls.append({'url': url, 'error': 'not cached (offline)'})
            return []
        for attempt in range(3):
            time.sleep(max(0, 2.1 - (time.monotonic() - Client.last_request)))
            try:
                self.last = time.monotonic()
                Client.last_request = self.last
                with urlopen(Request(url, headers={'User-Agent': 'M3-OpenF1-prototype/1.0'}), timeout=40) as response:
                    status = response.status
                    result = json.load(response)
                if not isinstance(result, list):
                    raise ValueError('expected JSON array')
                path.write_text(json.dumps(result, indent=2))
                self.calls.append({'url': url, 'rows': len(result), 'cached': False, 'http_status': status, 'retrieved_at_utc': datetime.now(timezone.utc).isoformat()})
                return result
            except (HTTPError, URLError, TimeoutError, ValueError) as exc:
                retryable = not isinstance(exc, HTTPError) or exc.code in (429, 500, 502, 503, 504)
                if retryable and attempt < 2:
                    time.sleep(3 * (attempt + 1))
                    continue
                self.calls.append({'url': url, 'error': str(exc), 'http_status': exc.code if isinstance(exc, HTTPError) else None})
                return []

def pace(laps):
    """Provisional valid-lap filter; deleted laps still require race-control/FIA review."""
    best = {}
    for lap in laps:
        duration = lap.get('lap_duration')
        sectors = [lap.get(f'duration_sector_{i}') for i in (1, 2, 3)]
        if lap.get('is_pit_out_lap') is not False or not isinstance(duration, (float, int)) or not math.isfinite(duration) or duration <= 0:
            continue
        if not all(isinstance(v, (int, float)) and math.isfinite(v) and v > 0 for v in sectors):
            continue
        number = lap['driver_number']
        best[number] = min(best.get(number, float('inf')), duration)
    fastest = min(best.values()) if best else 0
    return {k: v-fastest for k, v in best.items()}

def build(client, year, country):
    sessions = client.get('sessions', year=year, country_name=country)
    races = [s for s in sessions if s.get('session_name') == 'Race']
    if len(races) != 1:
        return None, {'blocking': ['Expected exactly one normal Grand Prix Race session; inspect API requests.']}
    race = races[0]
    same_meeting = [s for s in sessions if s.get('meeting_key') == race['meeting_key']]
    qualifying = [s for s in same_meeting if s.get('session_name') == 'Qualifying']
    if len(qualifying) != 1:
        return None, {'blocking': ['Normal qualifying session missing or ambiguous.']}
    q = qualifying[0]
    practices = sorted([s for s in same_meeting if s.get('session_type') == 'Practice' and s['date_end'] < q['date_start']], key=lambda s: s['date_start'])
    practice = next((s for s in reversed(practices) if s['session_name'] == 'Practice 3'), practices[-1] if practices else None)
    # Entrant/display features come exclusively from pre-race qualifying data.
    # Never use race-result coverage or the post-race drivers table to select rows.
    drivers = client.get('drivers', session_key=q['session_key'])
    qlaps = client.get('laps', session_key=q['session_key'])
    plaps = client.get('laps', session_key=practice['session_key']) if practice else []
    weather = client.get('weather', session_key=q['session_key'])
    classification = client.get('session_result', session_key=q['session_key'])
    # OpenF1 associates starting grids with normal qualifying, not the race.
    grid = client.get('starting_grid', session_key=q['session_key'])
    result = client.get('session_result', session_key=race['session_key'])
    control = client.get('race_control', session_key=q['session_key'])
    # A complete-looking in-lap is not evidence of a valid qualifying time.
    # Explicitly empty official Q1/Q2/Q3 times override the provisional lap filter.
    no_valid_qualifying_lap = set()
    for row in classification:
        if 'duration' in row:
            durations = row['duration'] if isinstance(row['duration'], list) else [row['duration']]
            if not any(isinstance(v, (int, float)) and math.isfinite(v) and v > 0 for v in durations):
                no_valid_qualifying_lap.add(row['driver_number'])
    qp = pace([lap for lap in qlaps if lap['driver_number'] not in no_valid_qualifying_lap])
    pp = pace(plaps)
    if len({r['driver_number'] for r in classification}) != len(classification):
        raise ValueError('duplicate driver assignment in qualifying classification')
    positions = {r['driver_number']: r.get('position') for r in classification}
    grids = {}
    grid_positions = set()
    for row in grid:
        if row.get('meeting_key') != race['meeting_key'] or row.get('session_key') != q['session_key']:
            raise ValueError('starting_grid response does not match the selected meeting/normal qualifying session')
        number, position = row['driver_number'], row.get('position')
        if number in grids:
            raise ValueError('duplicate driver assignment in starting_grid response')
        if not isinstance(position, int) or isinstance(position, bool) or position < 1 or position in grid_positions:
            raise ValueError('starting_grid positions must be positive unique integers')
        grids[number] = position
        grid_positions.add(position)
    weather_frame = pd.DataFrame(weather)
    def median(column):
        return float(pd.to_numeric(weather_frame[column], errors='coerce').median()) if column in weather_frame and weather_frame[column].notna().any() else None
    rainfall = [w['rainfall'] for w in weather if w.get('rainfall') is not None]
    rain = int(any(v > 0 for v in rainfall)) if rainfall else None
    race_id = f"{year}_{country.lower().replace(' ', '_')}_gp"
    records = []
    seen = set()
    for driver in drivers:
        number = driver['driver_number']
        if number in seen:
            raise ValueError('duplicate driver records from API require review')
        seen.add(number)
        records.append({'race_id': race_id, 'driver_number': number, 'driver_name': driver.get('full_name'),
                        'qualifying_position': positions.get(number), 'qualifying_gap_seconds': qp.get(number),
                        'practice_gap_seconds': pp.get(number), 'qualifying_air_temp_c': median('air_temperature'),
                        'qualifying_track_temp_c': median('track_temperature'), 'qualifying_rainfall': rain,
                        'grid_position': grids.get(number), 'meeting_key': race['meeting_key'],
                        'qualifying_session_key': q['session_key'], 'race_session_key': race['session_key'],
                        'year': year, 'data_source': 'OpenF1 draft; M2 review required', 'as_of_utc': q['date_end'],
                        'team_name': driver.get('team_name')})
    data = pd.DataFrame(records)
    if set(grids) - seen:
        raise ValueError('starting_grid contains drivers outside the selected entrant list')
    report = {'race_id': race_id, 'entrants': len(records), 'practice_session': practice,
              'qualifying_session': q, 'race_session': race, 'grid_verified': False,
              'grid_source_session_key': q['session_key'],
              'grid_integrity': {'populated': sum(n in grids for n in seen),
                                 'unique_driver_assignments': len(grids),
                                 'positions': sorted(grid_positions),
                                 'complete_1_to_n': grid_positions == set(range(1, len(records)+1)) and set(grids) == seen},
              'race_result_rows': len(result), 'race_control_rows': len(control),
              'entrant_source_session_key': q['session_key'],
              'qualifying_no_recorded_valid_lap_drivers': sorted(no_valid_qualifying_lap),
              'missing_columns_or_values': {c: int(data[c].isna().sum()) for c in data if data[c].isna().any()},
              'blocking': ['Lap deletions and official qualifying classification require M2/FIA review.',
                           'Final starting grid and complete eligible entrant list require M2 verification.',
                           'Historical API retrieval does not establish availability at forecast cutoff; as_of_utc is the intended cutoff.',
                           'Race result statuses require review before creating training targets.'],
              'limitations': ['Pace reflects track evolution; best laps across all qualifying segments are used.',
                              'Pit-out/incomplete laps excluded, but pit-in and deleted-lap validity are not fully established by this draft filter.',
                              'One race is a data smoke test only; no performance claim or production artifact.']}
    return data, report

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--year', type=int, default=2024)
    parser.add_argument('--country', default='Bahrain')
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()
    # Restrict path components to prevent output escaping this directory.
    if not args.country.replace(' ', '').isalpha() or not 2023 <= args.year <= 2100:
        parser.error('country must contain letters/spaces; year must be 2023..2100')
    output = ROOT / 'data' / f'{args.year}_{args.country.lower().replace(" ", "_")}'
    client = Client(output / 'raw', args.offline)
    data, report = build(client, args.year, args.country)
    report['requests'] = client.calls
    if data is not None:
        data.to_csv(output / 'draft_entrants.csv', index=False)
        for stage, table in stage_tables(data).items():
            table.to_csv(output / f'{stage}_entrants.csv', index=False)
        report['status'] = 'draft_requires_M2_review'
    else:
        report['status'] = 'blocked_by_missing_sessions'
    report_name = 'offline_report.json' if args.offline else 'report.json'
    (output / report_name).write_text(json.dumps(report, indent=2, allow_nan=False))
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0 if data is not None and len(data) >= 3 else 1

if __name__ == '__main__':
    raise SystemExit(main())
