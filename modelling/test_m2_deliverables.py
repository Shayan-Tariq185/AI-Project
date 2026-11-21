import pandas as pd

from build_m2_deliverables import ROOT


def test_m2_pilot_deliverables():
    training = pd.read_csv(ROOT / 'data' / 'training_table.csv')
    assert training['race_id'].nunique() == 5
    assert len(training) == 99
    assert training.duplicated(['race_id', 'driver_number']).sum() == 0
    assert training.groupby('race_id')['top3_finish'].sum().eq(3).all()


def test_m2_sample_and_schedule():
    sample = pd.read_csv(ROOT / 'data' / 'sample_race.csv')
    schedule = pd.read_csv(ROOT / 'data' / 'schedule.csv')
    assert len(sample) == 20
    assert len(schedule) == 5


def test_m2_lap_quarantine():
    lap = pd.read_csv(ROOT / 'data' / 'lap' / 'lap_table.csv')
    assert lap.empty


def test_m2_pilot_feature_invariants():
    training = pd.read_csv(ROOT / 'data' / 'training_table.csv')
    assert (training['quali_gap_s'].dropna() >= 0).all()
    assert (training.groupby('race_id')['top3_finish'].sum() == 3).all()
