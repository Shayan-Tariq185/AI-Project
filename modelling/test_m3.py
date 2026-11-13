import json
import numpy as np
import pandas as pd
import pytest
import m3
from openf1_prototype import pace, Client, build
from pathlib import Path
from uuid import uuid4

@pytest.fixture
def tmp_path():
    # Avoid pytest's Windows chmod of basetemp, which conflicts with managed ACLs.
    path = Path(__file__).resolve().parent / '.test-work' / uuid4().hex
    path.mkdir(parents=True)
    return path

@pytest.fixture
def entrants():
    return pd.DataFrame([{'race_id': 'demo', 'driver_number': n, 'driver_name': f'Driver {n}',
        'qualifying_position': n, 'qualifying_gap_seconds': n/10,
        'practice_gap_seconds': None, 'qualifying_air_temp_c': 24,
        'qualifying_track_temp_c': 35, 'qualifying_rainfall': 0,
        'grid_position': n} for n in range(1, 7)])

@pytest.mark.parametrize('change,match', [
    (lambda d: d.iloc[:2], 'at least three'),
    (lambda d: d.assign(race_id=['x'] + ['demo']*5), 'one race'),
    (lambda d: d.assign(driver_number=1), 'unique'),
    (lambda d: d.drop(columns='practice_gap_seconds'), 'missing required'),
    (lambda d: d.assign(qualifying_gap_seconds=-1), 'nonnegative'),
    (lambda d: d.assign(driver_number=1.5), 'integer'),
    (lambda d: d.assign(qualifying_rainfall=2), '0, 1'),
    (lambda d: d.assign(qualifying_air_temp_c=np.inf), 'finite'),
    (lambda d: d.assign(driver_name=' '), 'nonempty'),
])
def test_invalid(entrants, change, match):
    with pytest.raises(ValueError, match=match):
        m3.validate(change(entrants), 'post_qualifying')

def test_stage_and_grid(entrants):
    with pytest.raises(ValueError, match='invalid stage'):
        m3.validate(entrants, 'race')
    with pytest.raises(ValueError, match='grid_verified'):
        m3.validate(entrants, 'post_grid')
    entrants.attrs['grid_verified'] = True
    m3.validate(entrants, 'post_grid')
    entrants.loc[0, 'grid_position'] = np.nan
    with pytest.raises(ValueError, match='every starter'):
        m3.validate(entrants, 'post_grid')

def test_missing_artifact(entrants, tmp_path, monkeypatch):
    monkeypatch.setattr(m3, 'ARTIFACTS', tmp_path)
    with pytest.raises(FileNotFoundError, match='No trained artifact'):
        m3.predict_podium(entrants, 'post_qualifying')

def test_inference_rejects_results(entrants):
    with pytest.raises(ValueError, match='post-race fields'):
        m3.predict_podium(entrants.assign(is_podium_actual=0), 'post_qualifying')

def test_ties_and_feature_leakage(entrants):
    class Constant:
        classes_ = np.array([0, 1])
        def predict_proba(self, x):
            assert 'grid_position' not in x and m3.TARGET not in x
            return np.array([[.5, .5]]*len(x))
    out = m3.score(entrants.iloc[::-1].assign(is_podium_actual=1), 'post_qualifying', Constant(), 'random_forest')
    assert list(out.driver_number) == list(range(1, 7))
    assert out.is_podium_pick.sum() == 3

def test_training_roundtrip(reviewed_history, tmp_path, monkeypatch):
    monkeypatch.setattr(m3, 'ARTIFACTS', tmp_path / 'artifacts')
    history = reviewed_history
    report = m3.train(history, grid_verified=True)
    assert [report['partitions'][p]['races'] for p in ('train', 'validation', 'test')] == [6, 2, 2]
    assert (m3.ARTIFACTS / 'evaluation.json').exists()
    assert report['model_name'] == 'random_forest'
    for stage in m3.STAGES:
        assert 'winner' not in report[stage]
        race = history[history.race_id == 'race_9'].drop(columns=[m3.TARGET])
        race.attrs = dict(history.attrs)
        out = m3.predict_podium(race, stage)
        assert out.shape == (6, 8)
        assert out.model_name.eq('random_forest').all()
    with pytest.raises(ValueError, match='ten reviewed races'):
        m3.train(history[history.race_id == 'race_0'])


def test_pace():
    def lap(n, duration, pit=False):
        return dict(driver_number=n, lap_duration=duration, is_pit_out_lap=pit,
                    duration_sector_1=20, duration_sector_2=30, duration_sector_3=40)
    assert pace([lap(1, 90), lap(2, 91), lap(3, 80, True), lap(4, None)]) == {1: 0, 2: 1}

def test_offline_missing_sessions(tmp_path):
    client = Client(tmp_path, offline=True)
    data, report = build(client, 2024, 'Bahrain')
    assert data is None and report['blocking']
    assert client.calls[0]['error'] == 'not cached (offline)'

class GridClient:
    def __init__(self, issue=None):
        self.calls = []
        self.issue = issue

    def get(self, endpoint, **params):
        self.calls.append((endpoint, params))
        if endpoint == 'sessions':
            sessions = [
                {'session_name': 'Race', 'session_key': 9472, 'meeting_key': 1229},
                {'session_name': 'Sprint Qualifying', 'session_key': 9000, 'meeting_key': 1229},
                {'session_name': 'Qualifying', 'session_key': 8000, 'meeting_key': 1000},
            ]
            if self.issue != 'missing_normal':
                sessions.append({'session_name': 'Qualifying', 'session_key': 9468, 'meeting_key': 1229,
                                 'date_start': '2024-03-01T16:00:00+00:00', 'date_end': '2024-03-01T17:00:00+00:00'})
            return sessions
        if endpoint == 'drivers':
            return [{'driver_number': n, 'full_name': f'Driver {n}'} for n in range(1, 4)]
        if endpoint == 'starting_grid':
            assert params == {'session_key': 9468}, 'starting_grid must use same-meeting normal qualifying, never race or sprint'
            rows = [{'driver_number': n, 'position': n, 'session_key': 9468, 'meeting_key': 1229} for n in range(1, 4)]
            if self.issue == 'duplicate_driver':
                rows[1]['driver_number'] = 1
            elif self.issue == 'duplicate_position':
                rows[1]['position'] = 1
            elif self.issue == 'wrong_meeting':
                rows[1]['meeting_key'] = 1000
            elif self.issue == 'wrong_session':
                rows[1]['session_key'] = 9472
            elif self.issue == 'unknown_driver':
                rows[1]['driver_number'] = 99
            return rows
        return []

def test_grid_uses_same_meeting_normal_qualifying():
    client = GridClient()
    data, report = build(client, 2024, 'Bahrain')
    assert ('starting_grid', {'session_key': 9468}) in client.calls
    assert list(data.grid_position) == [1, 2, 3]
    assert report['grid_integrity']['complete_1_to_n']
    assert report['grid_verified'] is False

def test_grid_does_not_fall_back_to_sprint_or_other_meeting():
    client = GridClient('missing_normal')
    data, report = build(client, 2024, 'Bahrain')
    assert data is None
    assert not any(endpoint == 'starting_grid' for endpoint, _ in client.calls)

@pytest.mark.parametrize('issue,match', [
    ('duplicate_driver', 'duplicate driver'),
    ('duplicate_position', 'positive unique integers'),
    ('wrong_meeting', 'does not match'),
    ('wrong_session', 'does not match'),
    ('unknown_driver', 'outside'),
])
def test_grid_rejects_invalid_assignments(issue, match):
    with pytest.raises(ValueError, match=match):
        build(GridClient(issue), 2024, 'Bahrain')
