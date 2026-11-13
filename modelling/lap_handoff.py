"""Read-only M2 evidence checks for contract-v2 practice lap regression."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from podium_handoff import sha256, utc

LINEAGE = ['task', 'row_key', 'field_name', 'selected_source', 'source_record_refs',
           'derived_from', 'observed_at_utc', 'available_at_utc', 'retrieved_at_utc',
           'review_status', 'reviewer', 'reviewed_at_utc', 'resolution_notes']


def _path(base, value):
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise ValueError('Lap evidence references must be relative package paths')
    result = (base / value).resolve()
    if not result.is_relative_to(base) or not result.is_file():
        raise ValueError(f'Missing/out-of-package lap evidence: {value}')
    return result


def decisions(value):
    try:
        if any(value[k]['status'] not in ('verified', 'corrected') for k in ('A1', 'A2', 'A3')):
            raise ValueError('M2 lap assumptions A1/A2/A3 remain unresolved')
        if value['A1']['convention'] != 'completed_laps_before_target':
            raise ValueError('Unsupported M2 tire-age convention')
        if value['A2']['matching'] != 'latest_available_at_or_before_cutoff':
            raise ValueError('Unsupported M2 weather matching rule')
        age = value['A2']['max_age_seconds']
        if isinstance(age, bool) or not isinstance(age, (int, float)) or not np.isfinite(age) or age <= 0:
            raise ValueError('M2 must approve a positive weather freshness limit')
        if value['A3']['scope'] != 'clean_normal_practice_flying_laps':
            raise ValueError('Only clean normal practice flying laps are supported')
        if not isinstance(value['A3']['supported_compounds'], list) or not value['A3']['supported_compounds']:
            raise ValueError('M2 must declare supported compound/regime scope')
    except (KeyError, TypeError) as exc:
        raise ValueError('Incomplete M2 lap assumption decisions') from exc
    return value


def load_package(path, context_only=False):
    try:
        path = Path(path).resolve()
        handoff = json.loads(path.read_text(encoding='utf-8-sig'))
    except (TypeError, OSError, ValueError) as exc:
        raise ValueError('A readable M2 lap handoff/context path is required') from exc
    required = {'contract_version', 'task', 'files', 'races', 'crosswalk_paths',
                'quality_report_path', 'assumption_decisions', 'review_status',
                'reviewer', 'reviewed_at_utc', 'approved_for_modeling'}
    if not context_only:
        required |= {'handoff_id', 'stage_or_mode', 'lineage_path'}
    if not isinstance(handoff, dict) or required - set(handoff):
        raise ValueError('Incomplete M2 lap handoff/context')
    if handoff['contract_version'] != '2.0' or handoff['task'] != 'lap_time':
        raise ValueError('Incompatible M2 lap contract/task')
    if not context_only and handoff['stage_or_mode'] != 'historical':
        raise ValueError('Historical lap handoff required for training/scoring')
    if (handoff['approved_for_modeling'] is not True or
            handoff['review_status'] not in ('verified', 'corrected') or
            not isinstance(handoff['reviewer'], str) or not handoff['reviewer'].strip()):
        raise ValueError('M2 lap evidence is not explicitly approved')
    utc(handoff['reviewed_at_utc'], 'M2 lap review time')
    policy = decisions(handoff['assumption_decisions'])
    tables, roles, hashes = {}, {}, {}
    if not isinstance(handoff['files'], list) or not handoff['files']:
        raise ValueError('M2 lap package requires hashed evidence')
    for record in handoff['files']:
        if not isinstance(record, dict) or {'role', 'relative_path', 'sha256', 'row_count', 'ordered_columns'} - set(record):
            raise ValueError('Incomplete lap evidence file record')
        name = record['relative_path']
        source = _path(path.parent, name)
        if name in hashes or record['role'] not in ('features', 'labels', 'metadata', 'lineage', 'crosswalk'):
            raise ValueError('Duplicate or invalid lap evidence record')
        digest = sha256(source)
        if digest != record['sha256']:
            raise ValueError(f'M2 lap evidence hash mismatch: {name}')
        try:
            if source.suffix == '.json':
                obj = json.loads(source.read_text(encoding='utf-8-sig'))
                table = pd.DataFrame(obj if isinstance(obj, list) else [obj])
            else:
                table = pd.read_csv(source, float_precision='round_trip')
        except (OSError, ValueError, TypeError) as exc:
            raise ValueError(f'Cannot read M2 lap evidence: {name}') from exc
        if len(table) != record['row_count'] or list(table.columns) != record['ordered_columns']:
            raise ValueError('M2 lap evidence row count/schema mismatch')
        tables[name], roles[name], hashes[name] = table, record['role'], digest

    def reference(name, role):
        if name not in tables or roles[name] != role:
            raise ValueError(f'M2 lap {role} reference must be hashed')
        return tables[name]

    quality = reference(handoff['quality_report_path'], 'metadata')
    if 'unresolved_issues' not in quality or any(v != [] for v in quality.unresolved_issues):
        raise ValueError('M2 lap quality issues remain unresolved')
    if not isinstance(handoff['crosswalk_paths'], list) or not handoff['crosswalk_paths']:
        raise ValueError('M2 lap identity crosswalks are required')
    maps = [reference(p, 'crosswalk') for p in handoff['crosswalk_paths']]
    driver = [t for t in maps if {'race_id', 'driver_id', 'driver_number', 'driver_name', 'review_status'}.issubset(t)]
    circuits = [t for t in maps if {'race_id', 'circuit_id', 'review_status'}.issubset(t)]
    if not driver or not circuits:
        raise ValueError('M2 lap driver and circuit crosswalks are required')
    driver, circuits = pd.concat(driver, ignore_index=True), pd.concat(circuits, ignore_index=True)
    if driver.duplicated(['race_id', 'driver_id']).any() or driver.duplicated(['race_id', 'driver_number']).any() or circuits.race_id.duplicated().any():
        raise ValueError('Ambiguous M2 lap identity mapping')
    if not driver.review_status.isin(['verified', 'corrected']).all() or not circuits.review_status.isin(['verified', 'corrected']).all():
        raise ValueError('Unresolved M2 lap identity mapping')
    races = {}
    if not isinstance(handoff['races'], list):
        raise ValueError('M2 lap race metadata must be a list')
    for race in handoff['races']:
        if not isinstance(race, dict) or {'race_id', 'race_start_utc', 'source_session_keys', 'eligible_driver_ids', 'prediction_cutoffs_utc'} - set(race):
            raise ValueError('Incomplete M2 lap race metadata')
        rid = race['race_id']
        if rid in races:
            raise ValueError('Duplicate M2 lap race')
        utc(race['race_start_utc'], 'GP race start')
        if set(race['eligible_driver_ids']) != set(driver.loc[driver.race_id == rid, 'driver_id']):
            raise ValueError('M2 lap eligible drivers disagree with crosswalk')
        if len(circuits[circuits.race_id == rid]) != 1:
            raise ValueError('M2 circuit/layout mapping missing')
        races[rid] = race

    def single(role, optional=False):
        matches = [name for name in roles if roles[name] == role]
        if optional and not matches:
            return None
        if len(matches) != 1:
            raise ValueError(f'M2 lap package requires one {role} table')
        return tables[matches[0]]

    return {'document': handoff, 'path': path, 'tables': tables, 'roles': roles,
            'hashes': hashes, 'reference': reference, 'single': single,
            'races': races, 'drivers': driver, 'circuits': circuits, 'policy': policy,
            'handoff_id': handoff.get('handoff_id', handoff.get('context_id')),
            'handoff_sha256': sha256(path)}


def identity_checks(data, package):
    for row in data.to_dict('records'):
        rid = row['race_id']
        if rid not in package['races']:
            raise ValueError(f"Missing reviewed race context for {row['example_id']}")
        race = package['races'][rid]
        if utc(row['prediction_time_utc'], 'Prediction time') >= utc(race['race_start_utc'], 'Race start'):
            raise ValueError(f"Prediction cutoff must precede GP race: {row['example_id']}")
        drivers = package['drivers']
        match = drivers[(drivers.race_id == rid) & (drivers.driver_id == row['driver_id'])]
        circuit = package['circuits'].set_index('race_id').loc[rid, 'circuit_id']
        if (len(match) != 1 or match.iloc[0].driver_number != row['driver_number']
                or match.iloc[0].driver_name != row['driver_name'] or circuit != row['circuit_id']):
            raise ValueError(f"Driver/circuit context mismatch: {row['example_id']}")
        if pd.notna(row['session_key']):
            allowed = race['source_session_keys'].get('practice', [])
            if row['session_key'] not in allowed:
                raise ValueError(f"Not an approved normal practice session: {row['example_id']}")


def weather_checks(data, package):
    """Check latest eligible observation, not nearest or future weather."""
    weather = package['tables'].get('weather.csv')
    if weather is None:
        raise ValueError('M2 package requires hashed weather.csv')
    required = {'session_key', 'date', 'available_at_utc', 'track_temperature'}
    if not required.issubset(weather):
        raise ValueError('M2 practice weather evidence is incomplete')
    weather = weather.copy()
    weather['_date'] = weather.date.map(lambda v: utc(v, 'Weather observation'))
    weather['_available'] = weather.available_at_utc.map(lambda v: utc(v, 'Weather availability'))
    for row in data.to_dict('records'):
        if pd.isna(row['weather_observed_at_utc']):
            continue
        if pd.isna(row['session_key']):
            raise ValueError('Measured scenario weather requires a known practice session')
        cutoff = utc(row['prediction_time_utc'], 'Lap cutoff')
        known = weather[(weather.session_key == row['session_key']) &
                        (weather._date <= cutoff) & (weather._available <= cutoff)]
        if known.empty:
            raise ValueError(f"No weather available at cutoff: {row['example_id']}")
        selected = known[known._date == known._date.max()]
        if selected.track_temperature.nunique(dropna=False) != 1:
            raise ValueError('Conflicting simultaneous practice weather observations')
        observed = utc(row['weather_observed_at_utc'], 'Weather time')
        if observed != selected._date.iloc[0] or not np.isclose(row['track_temperature_c'], selected.track_temperature.iloc[0], rtol=0, atol=1e-9):
            raise ValueError(f"Weather is not the latest eligible observation: {row['example_id']}")
        if (cutoff - observed).total_seconds() > package['policy']['A2']['max_age_seconds']:
            raise ValueError(f"Stale practice weather: {row['example_id']}")


def historical(data, columns, labels=None, require_all=False):
    package = load_package(data.attrs.get('m2_handoff_path'))
    approved = package['single']('features')
    if list(approved.columns) != columns or approved.example_id.duplicated().any():
        raise ValueError('M2 lap features must have the exact contract schema and unique keys')
    if require_all and set(data.example_id) != set(approved.example_id):
        raise ValueError('Training must use the complete approved lap table')
    expected = approved[approved.example_id.isin(data.example_id)]
    def normalize(table):
        table = table[columns].copy()
        for c in ('session_key', 'driver_number', 'lap_number', 'tyre_age_laps', 'track_temperature_c'):
            table[c] = pd.to_numeric(table[c]).astype(float)
        for c in ('prediction_time_utc', 'weather_observed_at_utc'):
            table[c] = table[c].map(lambda v: utc(v, c))
        return table.sort_values('example_id').reset_index(drop=True)
    try:
        pd.testing.assert_frame_equal(normalize(data), normalize(expected), check_dtype=False, rtol=1e-12, atol=1e-12)
    except (AssertionError, KeyError, TypeError) as exc:
        raise ValueError('Lap features do not match approved M2 evidence') from exc
    if labels is not None:
        approved_labels = package['single']('labels')
        if list(approved_labels.columns) != ['example_id', 'lap_time_actual_seconds'] or approved_labels.example_id.duplicated().any():
            raise ValueError('M2 lap labels have an invalid separate schema')
        try:
            pd.testing.assert_frame_equal(labels.sort_values('example_id').reset_index(drop=True),
                approved_labels.sort_values('example_id').reset_index(drop=True), check_dtype=False, rtol=1e-12, atol=1e-12)
        except AssertionError as exc:
            raise ValueError('Lap labels do not match approved M2 evidence') from exc
    identity_checks(data, package)
    weather_checks(data, package)
    examples = package['tables'].get('examples.csv')
    needed = {'example_id', 'session_name', 'clean_flying_lap_verified', 'stint_lap_start',
              'stint_lap_end', 'tyre_age_at_start', 'lap_start_utc', 'lap_end_utc',
              'target_available_at_utc', 'stint_available_at_utc', 'compound'}
    if examples is None or not needed.issubset(examples) or examples.example_id.duplicated().any():
        raise ValueError('M2 clean-lap/stint evidence is incomplete')
    examples = examples.set_index('example_id')
    for row in data.to_dict('records'):
        eid = row['example_id']
        if eid not in examples.index:
            raise ValueError(f'Missing clean-lap evidence: {eid}')
        info = examples.loc[eid]
        cutoff = utc(row['prediction_time_utc'], 'Lap cutoff')
        if info.session_name not in ('Practice 1', 'Practice 2', 'Practice 3') or info.clean_flying_lap_verified != True:
            raise ValueError(f'Not an M2-verified clean practice flying lap: {eid}')
        if utc(info.lap_start_utc, 'Lap start') != cutoff:
            raise ValueError('Historical prediction time must equal target lap start')
        end = utc(info.lap_end_utc, 'Lap end')
        available = utc(info.target_available_at_utc, 'Target availability')
        if end <= cutoff or available < end:
            raise ValueError('Lap target cannot be available before completion')
        if utc(info.stint_available_at_utc, 'Stint availability') > cutoff:
            raise ValueError('Tire/stint information was unavailable at prediction time')
        if not info.stint_lap_start <= row['lap_number'] <= info.stint_lap_end:
            raise ValueError('Ambiguous/out-of-range stint membership')
        expected_age = info.tyre_age_at_start + row['lap_number'] - info.stint_lap_start
        if expected_age != row['tyre_age_laps'] or info.compound != row['compound']:
            raise ValueError('Tire age/compound disagrees with verified stint mapping')
        if row['compound'] not in package['policy']['A3']['supported_compounds']:
            raise ValueError('Compound/regime not approved by M2')

    lineage = package['reference'](package['document']['lineage_path'], 'lineage')
    if set(lineage.columns) != set(LINEAGE):
        raise ValueError('M2 lap lineage schema mismatch')
    wanted = set(data.example_id)
    coverage, source_cache = set(), dict(package['hashes'])
    cutoffs = data.set_index('example_id').prediction_time_utc
    for row in lineage.to_dict('records'):
        try:
            key = json.loads(row['row_key'])
            eid = key['example_id']
            if eid not in wanted:
                continue
            pair = (eid, row['field_name'])
            if pair in coverage or row['field_name'] not in columns:
                raise ValueError('Duplicate/invalid lap lineage field')
            coverage.add(pair)
            if row['task'] != 'lap_time' or row['review_status'] not in ('verified', 'corrected'):
                raise ValueError('Unreviewed lap lineage')
            if row['selected_source'] not in ('openf1', 'jolpica', 'derived'):
                raise ValueError('Unsupported historical lap source')
            cutoff = utc(cutoffs.loc[eid], 'Feature cutoff')
            if utc(row['available_at_utc'], 'Field availability') > cutoff:
                raise ValueError('Lap feature uses future information')
            if pd.notna(row['observed_at_utc']) and utc(row['observed_at_utc'], 'Field observation') > cutoff:
                raise ValueError('Lap feature observation is after its cutoff')
            if pd.isna(row['reviewer']) or not str(row['reviewer']).strip():
                raise ValueError('Lap lineage reviewer missing')
            utc(row['reviewed_at_utc'], 'Field review time')
            refs = json.loads(row['source_record_refs'])
            if not isinstance(refs, list) or not refs or not isinstance(json.loads(row['derived_from']), list):
                raise ValueError('Lap source/derivation references are missing')
            for ref in refs:
                if not isinstance(ref, dict) or {'source', 'relative_path', 'record_key', 'sha256'} - set(ref):
                    raise ValueError('Invalid lap source reference')
                name = ref['relative_path']
                if name not in source_cache:
                    source_cache[name] = sha256(_path(package['path'].parent, name))
                if ref['source'] not in ('openf1', 'jolpica', 'derived') or source_cache[name] != ref['sha256']:
                    raise ValueError('Lap source hash mismatch')
        except (TypeError, KeyError, json.JSONDecodeError) as exc:
            raise ValueError('Malformed M2 lap lineage') from exc
    if coverage != {(eid, c) for eid in wanted for c in columns}:
        raise ValueError('M2 lineage does not cover every lap input field')
    package['examples'] = examples
    return package


def scenario(data):
    package = load_package(data.attrs.get('m2_context_path'), context_only=True)
    identity_checks(data, package)
    weather_checks(data, package) if data.weather_observed_at_utc.notna().any() else None
    provenance = data.attrs.get('scenario_provenance')
    if not isinstance(provenance, dict) or set(provenance) != set(data.example_id):
        raise ValueError('Every scenario requires explicit assumption provenance')
    for row in data.to_dict('records'):
        source = provenance[row['example_id']]
        if not isinstance(source, dict) or source.get('compound') != 'user_scenario' or source.get('tyre_age_laps') != 'user_scenario':
            raise ValueError('Scenario tire inputs must be explicitly hypothetical')
        expected = 'user_scenario' if pd.isna(row['weather_observed_at_utc']) else 'openf1'
        if source.get('track_temperature_c') != expected:
            raise ValueError('Scenario weather provenance does not match assumed/measured mode')
        if row['compound'] not in package['policy']['A3']['supported_compounds']:
            raise ValueError('Scenario compound/regime is not approved')
    return package
