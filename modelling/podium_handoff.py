"""Read-only validation of contract-v2 M2 podium handoffs.

A signed-in reviewer is a process responsibility, not inferred from a CSV flag.
This module requires explicit review decisions and checks their local evidence.
"""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd

CONTRACT_VERSION = '2.0'
IDENTITY = ['race_id', 'driver_number', 'driver_name']
KEYS = ['race_id', 'driver_number']
TARGET = 'is_podium_actual'


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def utc(value, label):
    try:
        stamp = pd.Timestamp(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(f'{label} must be a timezone-aware UTC timestamp') from exc
    if pd.isna(stamp) or stamp.tzinfo is None:
        raise ValueError(f'{label} must be a timezone-aware UTC timestamp')
    return stamp.tz_convert('UTC')


def _path(base, relative):
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError('M2 evidence paths must be nonempty relative paths')
    path = (base / relative).resolve()
    if not path.is_relative_to(base) or not path.is_file():
        raise ValueError(f'Missing or out-of-package M2 evidence: {relative}')
    return path


def _matches(actual, approved, columns, label):
    if actual.duplicated(KEYS).any() or approved.duplicated(KEYS).any():
        raise ValueError(f'duplicate race/driver keys in {label}')
    races = set(actual.race_id)
    expected = approved[approved.race_id.isin(races)]
    def canonical(frame):
        frame = frame[columns].copy()
        for column in columns:
            if column not in ('race_id', 'driver_name'):
                frame[column] = pd.to_numeric(frame[column], errors='raise').astype(float)
        return frame.where(pd.notna(frame), np.nan).sort_values(KEYS).reset_index(drop=True)
    try:
        pd.testing.assert_frame_equal(canonical(actual), canonical(expected),
                                      check_dtype=False, check_exact=False, rtol=1e-12, atol=1e-12)
    except (AssertionError, KeyError, TypeError) as exc:
        raise ValueError(f'{label} do not match the approved M2 handoff') from exc


def verify(data, stage, feature_columns, training=False):
    """Resolve attrs without changing predict_podium's two-argument API."""
    paths = data.attrs.get('m2_handoffs', {})
    handoff_path = paths.get(stage) if isinstance(paths, dict) else None
    handoff_path = handoff_path or data.attrs.get('m2_handoff_path')
    if handoff_path is None:
        raise ValueError('An approved M2 handoff is required; set DataFrame.attrs[m2_handoff_path] or m2_handoffs[stage]')
    path = Path(handoff_path).resolve()
    try:
        handoff = json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError, TypeError) as exc:
        raise ValueError(f'Cannot read approved M2 handoff: {path}') from exc
    required = {'handoff_id', 'contract_version', 'task', 'stage_or_mode', 'files',
                'races', 'lineage_path', 'crosswalk_paths', 'quality_report_path',
                'assumption_decisions', 'review_status', 'reviewer',
                'reviewed_at_utc', 'approved_for_modeling'}
    if not isinstance(handoff, dict) or required - set(handoff):
        raise ValueError('M2 handoff is missing contract-v2 fields')
    if (handoff['contract_version'] != CONTRACT_VERSION or handoff['task'] != 'podium'
            or handoff['stage_or_mode'] != stage):
        raise ValueError('M2 handoff has incompatible contract/task/stage')
    if (handoff['approved_for_modeling'] is not True
            or handoff['review_status'] not in ('verified', 'corrected')
            or not isinstance(handoff['reviewer'], str) or not handoff['reviewer'].strip()
            or not isinstance(handoff['handoff_id'], str) or not handoff['handoff_id'].strip()):
        raise ValueError('M2 handoff is not explicitly approved for modeling')
    utc(handoff['reviewed_at_utc'], 'M2 review time')
    if not isinstance(handoff['assumption_decisions'], dict):
        raise ValueError('M2 assumption_decisions must be an object')

    tables, records, hashes = {}, {}, {}
    if not isinstance(handoff['files'], list) or not handoff['files']:
        raise ValueError('M2 handoff requires hashed evidence files')
    for record in handoff['files']:
        if not isinstance(record, dict) or {'role', 'relative_path', 'sha256', 'row_count', 'ordered_columns'} - set(record):
            raise ValueError('Incomplete M2 evidence file record')
        if record['role'] not in ('features', 'labels', 'metadata', 'crosswalk', 'lineage'):
            raise ValueError('Invalid M2 evidence role')
        relative = record['relative_path']
        evidence = _path(path.parent, relative)
        if relative in records:
            raise ValueError('Duplicate M2 evidence path')
        if sha256(evidence) != record['sha256']:
            raise ValueError(f'M2 evidence hash mismatch: {relative}')
        try:
            if evidence.suffix.lower() == '.json':
                value = json.loads(evidence.read_text(encoding='utf-8-sig'))
                table = pd.DataFrame(value if isinstance(value, list) else [value])
            else:
                table = pd.read_csv(evidence, float_precision='round_trip')
        except (ValueError, TypeError, OSError) as exc:
            raise ValueError(f'Cannot read M2 evidence table: {relative}') from exc
        if len(table) != record['row_count'] or list(table.columns) != record['ordered_columns']:
            raise ValueError(f'M2 evidence row/schema mismatch: {relative}')
        tables[relative], records[relative], hashes[relative] = table, record, record['sha256']

    def role_table(role, needed=True):
        matches = [name for name, record in records.items() if record['role'] == role]
        if len(matches) != 1 and (needed or matches):
            raise ValueError(f'M2 handoff requires exactly one {role} table')
        return tables[matches[0]] if matches else None

    def reference(relative, role):
        if relative not in records or records[relative]['role'] != role:
            raise ValueError(f'M2 {role} reference must be included in hashed files: {relative}')
        return tables[relative]

    approved = role_table('features')
    columns = IDENTITY + feature_columns
    if list(approved.columns) != columns:
        raise ValueError('M2 features must have exactly the stage contract columns')
    _matches(data, approved, columns, 'Prediction features')
    labels = role_table('labels', needed=training)
    if labels is not None:
        if list(labels.columns) != KEYS + [TARGET]:
            raise ValueError('M2 labels must be a separate contract label table')
        if labels.duplicated(KEYS).any() or set(map(tuple, labels[KEYS].to_numpy())) != set(map(tuple, approved[KEYS].to_numpy())):
            raise ValueError('M2 labels do not cover exactly the approved feature keys')
        if training:
            _matches(data, labels, KEYS + [TARGET], 'Training labels')

    lineage = reference(handoff['lineage_path'], 'lineage')
    quality = reference(handoff['quality_report_path'], 'metadata')
    if ('unresolved_issues' not in quality or
            any(value != [] for value in quality['unresolved_issues'])):
        raise ValueError('M2 quality report must explicitly record no unresolved issues')
    crosswalks = handoff['crosswalk_paths']
    if not isinstance(crosswalks, list) or not crosswalks:
        raise ValueError('M2 handoff requires reviewed driver crosswalks')
    maps = [reference(name, 'crosswalk') for name in crosswalks]
    driver_maps = [table for table in maps if set(KEYS + ['driver_id', 'review_status']).issubset(table.columns)]
    if not driver_maps:
        raise ValueError('M2 driver crosswalk is missing race/driver identity fields')
    identities = pd.concat(driver_maps, ignore_index=True)
    if identities.duplicated(KEYS).any() or not identities.review_status.isin(['verified', 'corrected']).all():
        raise ValueError('Ambiguous or unresolved M2 driver crosswalk')
    if identities.driver_id.isna().any() or identities.driver_id.astype(str).str.strip().eq('').any():
        raise ValueError('M2 driver_id must be present')
    expected_keys = set(map(tuple, approved[KEYS].to_numpy()))
    if expected_keys != set(map(tuple, identities[KEYS].to_numpy())):
        raise ValueError('M2 eligible driver crosswalk does not cover approved features')

    races = handoff['races']
    if not isinstance(races, list) or not all(isinstance(r, dict) for r in races) or len({r.get('race_id') for r in races}) != len(races):
        raise ValueError('M2 race metadata must be unique')
    race_info = {}
    for race in races:
        if {'race_id', 'race_start_utc', 'source_session_keys', 'eligible_driver_ids', 'prediction_cutoffs_utc'} - set(race):
            raise ValueError('M2 race metadata is incomplete')
        rid = race['race_id']
        start = utc(race['race_start_utc'], f'{rid} race start')
        if not isinstance(race['prediction_cutoffs_utc'], dict):
            raise ValueError('M2 prediction_cutoffs_utc must be an object')
        cutoff = utc(race['prediction_cutoffs_utc'].get(stage), f'{rid} {stage} cutoff')
        if cutoff >= start:
            raise ValueError('M2 prediction cutoff must precede the GP race start')
        sessions = race['source_session_keys']
        if not isinstance(sessions, dict) or not all(isinstance(sessions.get(k), int) and sessions[k] > 0 for k in ('qualifying', 'race')):
            raise ValueError('M2 source_session_keys require qualifying and race keys')
        eligible = race['eligible_driver_ids']
        if not isinstance(eligible, list) or len(set(eligible)) != len(eligible):
            raise ValueError('M2 eligible_driver_ids must be unique')
        if set(eligible) != set(identities.loc[identities.race_id == rid, 'driver_id']):
            raise ValueError('M2 eligible driver IDs do not match reviewed crosswalk')
        if training:
            dates = data.loc[data.race_id == rid, 'race_date']
            if any(utc(value, f'{rid} race_date') != start for value in dates):
                raise ValueError('Training race dates do not match the M2 handoff')
        race_info[rid] = cutoff
    if set(race_info) != set(approved.race_id):
        raise ValueError('M2 race metadata does not cover approved features')

    lineage_columns = {'task', 'row_key', 'field_name', 'selected_source', 'source_record_refs',
                       'derived_from', 'observed_at_utc', 'available_at_utc', 'retrieved_at_utc',
                       'review_status', 'reviewer', 'reviewed_at_utc', 'resolution_notes'}
    if lineage_columns != set(lineage.columns) or not lineage.review_status.isin(['verified', 'corrected']).all():
        raise ValueError('M2 field lineage is incomplete or unresolved')
    covered = set()
    absent = {(record['race_id'], record['driver_number'], column)
              for record in approved.to_dict('records') for column in columns if pd.isna(record[column])}
    for row in lineage.to_dict('records'):
        try:
            key = json.loads(row['row_key'])
            pair = (key['race_id'], key['driver_number'])
            identity = pair + (row['field_name'],)
            if pair not in expected_keys or identity in covered or row['field_name'] not in columns:
                raise ValueError('M2 lineage keys are invalid or duplicated')
            covered.add(identity)
            if identity in absent and (pd.isna(row['resolution_notes']) or not str(row['resolution_notes']).strip()):
                raise ValueError('M2 verified absence requires a missing-value reason')
            if row['task'] != 'podium' or row['selected_source'] not in ('openf1', 'jolpica', 'derived'):
                raise ValueError('M2 lineage has unsupported task/source')
            available = utc(row['available_at_utc'], 'Field availability')
            if available > race_info[pair[0]]:
                raise ValueError('M2 field was unavailable at the prediction cutoff')
            if pd.notna(row['observed_at_utc']) and utc(row['observed_at_utc'], 'Observation time') > race_info[pair[0]]:
                raise ValueError('M2 field observation is after the prediction cutoff')
            refs = json.loads(row['source_record_refs'])
            if not isinstance(refs, list) or not refs:
                raise ValueError('M2 lineage requires cached source references')
            for ref in refs:
                if not isinstance(ref, dict) or {'source', 'relative_path', 'record_key', 'sha256'} - set(ref):
                    raise ValueError('M2 lineage source reference is incomplete')
                source = _path(path.parent, ref['relative_path'])
                if ref['source'] not in ('openf1', 'jolpica', 'derived') or sha256(source) != ref['sha256']:
                    raise ValueError('M2 lineage source hash mismatch')
            if not isinstance(json.loads(row['derived_from']), list):
                raise ValueError('M2 lineage derived_from must be a list')
            if pd.isna(row['reviewer']) or not str(row['reviewer']).strip():
                raise ValueError('M2 lineage reviewer is missing')
            utc(row['reviewed_at_utc'], 'Field review time')
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError('Invalid M2 lineage record') from exc
    if covered != {key + (column,) for key in expected_keys for column in columns}:
        raise ValueError('M2 lineage does not cover every approved feature field')
    return {'handoff_id': handoff['handoff_id'], 'handoff_sha256': sha256(path),
            'source_hashes': hashes, 'assumption_decisions': handoff['assumption_decisions']}
