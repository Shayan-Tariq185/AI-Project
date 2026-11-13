import json
from pathlib import Path
from uuid import uuid4
import pandas as pd
import pytest
from collect_pilot import COUNTRIES, collect_pilot, classification_labels, lap_quality
from openf1_prototype import IDENTITY, stage_tables
from m3 import BASE

@pytest.fixture
def pilot_root():
    root = Path(__file__).resolve().parent / '.test-work' / uuid4().hex
    for i, country in enumerate(COUNTRIES):
        raw = root / 'data' / ('2024_' + country.lower().replace(' ', '_')) / 'raw'
        raw.mkdir(parents=True)
        meeting, q, race, practice = 100+i, 200+i, 300+i, 400+i
        def save(endpoint, params, rows):
            name = endpoint + '_' + '_'.join(f'{k}-{v}' for k, v in params.items()) + '.json'
            (raw / name).write_text(json.dumps(rows))
        sessions = [
            dict(session_key=race, meeting_key=meeting, session_name='Race', session_type='Race', date_start=f'2024-0{i+1}-03T12:00:00+00:00', date_end=f'2024-0{i+1}-03T14:00:00+00:00'),
            dict(session_key=q, meeting_key=meeting, session_name='Qualifying', session_type='Qualifying', date_start=f'2024-0{i+1}-02T12:00:00+00:00', date_end=f'2024-0{i+1}-02T13:00:00+00:00'),
            dict(session_key=practice, meeting_key=meeting, session_name='Practice 1' if country == 'China' else 'Practice 3', session_type='Practice', date_start=f'2024-0{i+1}-01T12:00:00+00:00', date_end=f'2024-0{i+1}-01T13:00:00+00:00'),
            dict(session_key=9000, meeting_key=meeting, session_name='Sprint', session_type='Race'),
            dict(session_key=9001, meeting_key=meeting, session_name='Sprint Qualifying', session_type='Qualifying'),
            dict(session_key=9002, meeting_key=9999, session_name='Qualifying', session_type='Qualifying'),
        ]
        save('sessions', {'year': 2024, 'country_name': country}, sessions)
        drivers = [dict(driver_number=n, full_name=f'Driver {n}', team_name='Team') for n in (44, 11, 22, 33)]
        for key in (q, practice):
            save('drivers', {'session_key': key}, drivers)
            laps = [dict(driver_number=n, lap_duration=90+n/100, is_pit_out_lap=False,
                         duration_sector_1=30, duration_sector_2=30, duration_sector_3=30) for n in (11, 22, 33, 44)]
            save('laps', {'session_key': key}, laps)
            save('race_control', {'session_key': key}, [])
        save('weather', {'session_key': q}, [dict(air_temperature=20, track_temperature=30, rainfall=0)])
        grid = [dict(driver_number=n, position=p, session_key=q, meeting_key=meeting) for p, n in enumerate((33, 11, 44, 22), 1)]
        save('starting_grid', {'session_key': q}, grid)
        for key in (q, race):
            rows = [dict(driver_number=n, position=p, session_key=key, meeting_key=meeting, dnf=False, dns=False, dsq=False) for p, n in enumerate((11, 22, 33, 44), 1)]
            save('session_result', {'session_key': key}, rows)
    return root

def test_five_race_offline_collection(pilot_root):
    report = collect_pilot(pilot_root, offline=True)
    assert report['races_collected_successfully'] == 5
    assert report['post_grid']['driver_rows'] == 20
    assert report['post_grid']['missing_by_feature'] == dict.fromkeys(BASE + ['grid_position'], 0)
    output = pilot_root / 'data/pilot_2024'
    for stage in ('post_qualifying', 'post_grid'):
        features = pd.read_csv(output / f'{stage}_features.csv')
        assert list(features.columns) == IDENTITY + BASE + (['grid_position'] if stage == 'post_grid' else [])
        assert not features.duplicated(['race_id', 'driver_number']).any()
        assert 'is_podium_actual' not in features
    labels = pd.read_csv(output / 'podium_labels.csv')
    assert list(labels.columns) == ['race_id', 'driver_number', 'is_podium_actual']
    assert labels.groupby('race_id').is_podium_actual.sum().eq(3).all()
    china = report['races'][-1]
    assert china['practice_session']['session_name'] == 'Practice 1'
    assert all(r['requires_M2_verification'] for r in report['races'])
    requests = [c for r in report['races'] for c in r['requests']]
    assert not any('error' in c for c in requests)
    assert not any('9000' in c['url'] or '9001' in c['url'] or '9002' in c['url'] for c in requests)
    # A race-session roster is deliberately not cached. Feature collection must
    # depend only on the pre-race qualifying roster.
    assert all('drivers?session_key=3' not in c['url'] for c in requests)
    frames = pd.read_csv(output / 'post_grid_features.csv')
    assert frames.loc[frames.driver_number == 33, 'grid_position'].eq(1).all()

def test_outcome_changes_cannot_change_features(pilot_root):
    collect_pilot(pilot_root, offline=True)
    output = pilot_root / 'data/pilot_2024'
    before = {s: (output / f'{s}_features.csv').read_bytes() for s in ('post_qualifying', 'post_grid')}
    path = pilot_root / 'data/2024_bahrain/raw/session_result_session_key-300.json'
    rows = json.loads(path.read_text())
    for row in rows:
        row['position'] = 5 - row['position']
    path.write_text(json.dumps(rows))
    collect_pilot(pilot_root, offline=True)
    for stage, content in before.items():
        assert (output / f'{stage}_features.csv').read_bytes() == content
    labels = pd.read_csv(output / 'podium_labels.csv')
    assert labels.loc[(labels.race_id == '2024_bahrain_gp') & (labels.driver_number == 11), 'is_podium_actual'].item() == 0

def test_missing_grid_and_result_remain_missing(pilot_root):
    raw = pilot_root / 'data/2024_japan/raw'
    (raw / 'starting_grid_session_key-203.json').write_text('[]')
    path = raw / 'session_result_session_key-303.json'
    path.write_text(json.dumps(json.loads(path.read_text())[:-1]))
    report = collect_pilot(pilot_root, offline=True)
    assert report['races_collected_successfully'] == 4
    japan = report['races'][3]
    assert japan['missing_by_feature']['grid_position'] == 4
    assert japan['labels_missing'] == 1
    assert japan['source_coverage']['race_classification']['missing_entrant_drivers'] == [44]
    assert japan['requires_M2_verification']

def test_missing_sessions_does_not_abort_other_races(pilot_root):
    (pilot_root / 'data/2024_australia/raw/sessions_year-2024_country_name-Australia.json').write_text('[]')
    report = collect_pilot(pilot_root, offline=True)
    assert report['races_with_feature_tables'] == 4
    assert report['races_collected_successfully'] == 4
    assert report['races'][2]['collection_status'] == 'failed_requires_M2'

def test_ambiguous_labels_never_imputed():
    data = pd.DataFrame({'race_id': ['demo']*4, 'driver_number': [1, 2, 3, 4]})
    labels, issues = classification_labels(data, [
        dict(driver_number=1, position=1, dnf=False, dns=False, dsq=False),
        dict(driver_number=2, position=None, dnf=False, dns=True, dsq=False),
        dict(driver_number=3, position=3, dnf=None, dns=False, dsq=False),
    ])
    assert labels.is_podium_actual.iloc[0] == 1
    assert labels.is_podium_actual.iloc[1] == 0
    assert labels.is_podium_actual.iloc[2:].isna().all()
    assert len(issues) == 2

def test_duplicate_classification_is_ambiguous():
    data = pd.DataFrame({'race_id': ['demo'], 'driver_number': [1]})
    row = dict(driver_number=1, position=1, dnf=False, dns=False, dsq=False)
    labels, issues = classification_labels(data, [row, row])
    assert labels.is_podium_actual.isna().all() and len(issues) == 1

def test_lap_validity_is_flagged():
    laps = [dict(driver_number=1, is_pit_out_lap=True),
            dict(driver_number=2, is_pit_out_lap=False, lap_duration=None),
            dict(driver_number=3, is_pit_out_lap=False, lap_duration=90)]
    quality = lap_quality(laps, [{'message': 'CAR 3 LAP TIME DELETED'}])
    assert quality['rejected_laps'] == dict(pit_out_or_unknown=1, invalid_or_missing_duration=1, incomplete_sectors=1)
    assert quality['fully_verified'] is False
    assert len(quality['lap_deletion_or_reinstatement_messages']) == 1

def test_no_classified_valid_qualifying_lap_is_null(pilot_root):
    raw = pilot_root / 'data/2024_saudi_arabia/raw'
    path = raw / 'session_result_session_key-201.json'
    rows = json.loads(path.read_text())
    rows[0].update(position=None, duration=[None, None, None])
    path.write_text(json.dumps(rows))
    report = collect_pilot(pilot_root, offline=True)
    features = pd.read_csv(pilot_root / 'data/pilot_2024/post_qualifying_features.csv')
    row = features.loc[(features.race_id == '2024_saudi_arabia_gp') & (features.driver_number == 11)].iloc[0]
    assert pd.isna(row.qualifying_position) and pd.isna(row.qualifying_gap_seconds)
    assert report['races'][1]['qualifying_no_recorded_valid_lap_drivers'] == [11]
