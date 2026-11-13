"""Synthetic evidence fixtures only. These are not M2 approvals of real races."""
import json
from pathlib import Path
from uuid import uuid4
import pandas as pd
import pytest
import m3
from podium_handoff import sha256

LINEAGE_COLUMNS = ['task', 'row_key', 'field_name', 'selected_source', 'source_record_refs',
                   'derived_from', 'observed_at_utc', 'available_at_utc', 'retrieved_at_utc',
                   'review_status', 'reviewer', 'reviewed_at_utc', 'resolution_notes']


@pytest.fixture
def tmp_path():
    path = Path(__file__).resolve().parent / '.test-work' / uuid4().hex
    path.mkdir(parents=True)
    return path


@pytest.fixture
def make_reviewed_history(tmp_path):
    def make(all_null=False, test_shift=0):
        root = tmp_path / uuid4().hex
        root.mkdir()
        rows = []
        for i in range(10):
            for number in range(1, 7):
                rows.append({'race_id': f'race_{i}', 'driver_number': number,
                             'driver_name': f'Synthetic Driver {number}',
                             'qualifying_position': number, 'qualifying_gap_seconds': number / 10,
                             'practice_gap_seconds': None if all_null or number == 6 else number / 5 + i / 100 + (test_shift if i >= 8 else 0),
                             'qualifying_air_temp_c': 24, 'qualifying_track_temp_c': 35,
                             'qualifying_rainfall': 0, 'grid_position': number,
                             'race_date': f'2024-{i+1:02d}-01T14:00:00+00:00',
                             m3.TARGET: int(number <= 3)})
        data = pd.DataFrame(rows)
        paths = {}
        for stage in m3.STAGES:
            directory = root / stage
            directory.mkdir()
            columns = ['race_id', 'driver_number', 'driver_name'] + m3.features(stage)
            data[columns].to_csv(directory / 'features.csv', index=False)
            data[['race_id', 'driver_number', m3.TARGET]].to_csv(directory / 'labels.csv', index=False)
            identities = data[['race_id', 'driver_number']].copy()
            identities['driver_id'] = identities.driver_number.map(lambda n: f'synthetic_driver_{n}')
            identities['review_status'] = 'verified'
            identities.to_csv(directory / 'crosswalk.csv', index=False)
            (directory / 'quality.json').write_text(json.dumps({
                'unresolved_issues': [], 'fixture_only': 'SYNTHETIC: not a real M2 approval'}))
            refs = json.dumps([{'source': 'derived', 'relative_path': 'features.csv',
                                'record_key': 'synthetic fixture only', 'sha256': sha256(directory / 'features.csv')}])
            lineage = []
            races = []
            for i in range(10):
                rid = f'race_{i}'
                cutoff = f'2024-{i+1:02d}-01T12:00:00+00:00'
                races.append({'race_id': rid, 'race_start_utc': f'2024-{i+1:02d}-01T14:00:00+00:00',
                              'source_session_keys': {'qualifying': 100+i, 'race': 200+i},
                              'eligible_driver_ids': [f'synthetic_driver_{n}' for n in range(1, 7)],
                              'prediction_cutoffs_utc': {stage: cutoff}})
                for number in range(1, 7):
                    for column in columns:
                        lineage.append({'task': 'podium',
                                        'row_key': json.dumps({'race_id': rid, 'driver_number': number}),
                                        'field_name': column, 'selected_source': 'derived',
                                        'source_record_refs': refs, 'derived_from': '[]',
                                        'observed_at_utc': cutoff, 'available_at_utc': cutoff,
                                        'retrieved_at_utc': '2025-01-01T00:00:00+00:00',
                                        'review_status': 'verified', 'reviewer': 'SYNTHETIC TEST FIXTURE',
                                        'reviewed_at_utc': '2025-01-01T00:00:00+00:00',
                                        'resolution_notes': 'Synthetic workflow test, not real race verification'})
            pd.DataFrame(lineage, columns=LINEAGE_COLUMNS).to_csv(directory / 'lineage.csv', index=False)
            records = []
            for name, role in [('features.csv', 'features'), ('labels.csv', 'labels'),
                               ('crosswalk.csv', 'crosswalk'), ('quality.json', 'metadata'),
                               ('lineage.csv', 'lineage')]:
                path = directory / name
                table = pd.DataFrame([json.loads(path.read_text())]) if path.suffix == '.json' else pd.read_csv(path)
                records.append({'role': role, 'relative_path': name, 'sha256': sha256(path),
                                'row_count': len(table), 'ordered_columns': list(table.columns)})
            handoff = {'handoff_id': f'SYNTHETIC-ONLY-{stage}-{root.name}', 'contract_version': '2.0',
                       'task': 'podium', 'stage_or_mode': stage, 'files': records, 'races': races,
                       'lineage_path': 'lineage.csv', 'crosswalk_paths': ['crosswalk.csv'],
                       'quality_report_path': 'quality.json', 'assumption_decisions': {},
                       'review_status': 'verified', 'reviewer': 'SYNTHETIC TEST FIXTURE',
                       'reviewed_at_utc': '2025-01-01T00:00:00+00:00', 'approved_for_modeling': True}
            path = directory / 'handoff.json'
            path.write_text(json.dumps(handoff, indent=2))
            paths[stage] = str(path)
        data.attrs['m2_handoffs'] = paths
        data.attrs['grid_verified'] = True
        return data
    return make


@pytest.fixture
def reviewed_history(make_reviewed_history):
    return make_reviewed_history()


@pytest.fixture
def entrants():
    return pd.DataFrame([{'race_id': 'demo', 'driver_number': n, 'driver_name': f'Driver {n}',
        'qualifying_position': n, 'qualifying_gap_seconds': n/10,
        'practice_gap_seconds': None, 'qualifying_air_temp_c': 24,
        'qualifying_track_temp_c': 35, 'qualifying_rainfall': 0,
        'grid_position': n} for n in range(1, 7)])