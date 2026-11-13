"""Regression checks for the v2 podium migration; training is synthetic only."""
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import RandomForestClassifier
import m3
from podium_handoff import sha256


def input_race(history, stage='post_qualifying'):
    race = history.loc[history.race_id == 'race_9',
                       ['race_id', 'driver_number', 'driver_name'] + m3.features(stage)].copy()
    race.attrs = dict(history.attrs)
    return race


def edit_handoff(history, stage, edit):
    path = Path(history.attrs['m2_handoffs'][stage])
    value = json.loads(path.read_text())
    edit(value)
    path.write_text(json.dumps(value))
    return path


def refresh_record(history, stage, name):
    path = Path(history.attrs['m2_handoffs'][stage])
    evidence = path.parent / name
    table = pd.DataFrame([json.loads(evidence.read_text())]) if evidence.suffix == '.json' else pd.read_csv(evidence)
    def update(value):
        record = next(r for r in value['files'] if r['relative_path'] == name)
        record.update(sha256=sha256(evidence), row_count=len(table), ordered_columns=list(table.columns))
    edit_handoff(history, stage, update)


@pytest.fixture
def trained(reviewed_history, tmp_path, monkeypatch):
    monkeypatch.setattr(m3, 'ARTIFACTS', tmp_path / 'artifacts/v2/podium')
    report = m3.train(reviewed_history, grid_verified=True)
    return reviewed_history, report


def test_random_forest_only():
    for stage in m3.STAGES:
        model = m3.pipeline(stage)
        assert isinstance(model.named_steps['model'], RandomForestClassifier)
        assert model.named_steps['model'].get_params()['max_depth'] == 4
        assert list(model.named_steps['preprocess'].transformers[0][1].named_steps) == ['impute']
        with pytest.raises(ValueError, match='Only random_forest'):
            m3.pipeline(stage, 'logistic_regression')


def test_m1_signature_and_schema(trained):
    import inspect
    history, report = trained
    assert list(inspect.signature(m3.predict_podium).parameters) == ['race_data', 'stage']
    expected = ['race_id', 'driver_number', 'driver_name', 'podium_probability',
                'predicted_rank', 'is_podium_pick', 'stage', 'model_name']
    for stage in m3.STAGES:
        out = m3.predict_podium(input_race(history, stage), stage)
        assert list(out.columns) == expected
        assert out.model_name.eq('random_forest').all()
        assert out.is_podium_pick.sum() == 3
        assert out.podium_probability.between(0, 1).all()
        assert out.predicted_rank.tolist() == list(range(1, 7))
        assert 'winner' not in report[stage] and 'tie_policy' not in report[stage]
        meta = json.loads((m3.ARTIFACTS / f'{stage}.json').read_text())
        assert meta['contract_version'] == '2.0'
        assert meta['task'] == 'podium' and meta['model_name'] == 'random_forest'
        assert meta['features'] == m3.features(stage)
        assert meta['training_handoff_ids'][0].startswith('SYNTHETIC-ONLY')
        assert meta['preprocessing']['scaling'] is None


def test_imputation_uses_only_training_history(make_reviewed_history, tmp_path, monkeypatch):
    history = make_reviewed_history(test_shift=10000)
    monkeypatch.setattr(m3, 'ARTIFACTS', tmp_path / 'models')
    report = m3.train(history, grid_verified=True)
    training_ids = report['partitions']['train']['race_ids']
    validation_ids = report['partitions']['validation']['race_ids']
    test_ids = report['partitions']['test']['race_ids']
    assert set(training_ids).isdisjoint(validation_ids + test_ids)
    assert set(validation_ids).isdisjoint(test_ids)
    expected = history[history.race_id.isin(training_ids + validation_ids)].practice_gap_seconds.median()
    for stage in m3.STAGES:
        model = joblib.load(m3.ARTIFACTS / f'{stage}.joblib')
        imputer = model.named_steps['preprocess'].named_transformers_['numeric'].named_steps['impute']
        assert imputer.statistics_[m3.features(stage).index('practice_gap_seconds')] == pytest.approx(expected)
        assert list(model.feature_names_in_) == m3.features(stage)
        metrics = report[stage]['test']
        assert metrics['baseline_races'] == 2
        assert metrics['classification_threshold'] == .5
        assert 0 <= metrics['average_precision'] <= 1
        assert 0 <= metrics['brier_score'] <= 1


def test_all_null_training_feature_is_not_fabricated(make_reviewed_history, tmp_path, monkeypatch):
    history = make_reviewed_history(all_null=True)
    monkeypatch.setattr(m3, 'ARTIFACTS', tmp_path / 'models')
    with pytest.raises(ValueError, match='all-null training features'):
        m3.train(history, grid_verified=True)
    assert not m3.ARTIFACTS.exists()


@pytest.mark.parametrize('field,value', [
    ('contract_version', '1.0'), ('task', 'lap_time'),
    ('model_name', 'logistic_regression'), ('stage', 'post_grid'),
    ('features', m3.BASE + ['grid_position']), ('versions', {}),
])
def test_incompatible_metadata_rejected_before_unpickle(trained, monkeypatch, field, value):
    history, _ = trained
    path = m3.ARTIFACTS / 'post_qualifying.json'
    meta = json.loads(path.read_text())
    meta[field] = value
    path.write_text(json.dumps(meta))
    monkeypatch.setattr(m3.joblib, 'load', lambda _: pytest.fail('Incompatible pickle was deserialized'))
    with pytest.raises(m3.ArtifactCompatibilityError, match='Incompatible artifact'):
        m3.predict_podium(input_race(history), 'post_qualifying')


@pytest.mark.parametrize('contents', [None, '{not-json', '[]'])
def test_missing_or_malformed_metadata(entrants, tmp_path, monkeypatch, contents):
    monkeypatch.setattr(m3, 'ARTIFACTS', tmp_path)
    (tmp_path / 'post_qualifying.joblib').write_bytes(b'not a pickle')
    if contents is not None:
        (tmp_path / 'post_qualifying.json').write_text(contents)
    monkeypatch.setattr(m3.joblib, 'load', lambda _: pytest.fail('Bad metadata must fail before unpickling'))
    with pytest.raises(m3.ArtifactCompatibilityError, match='Incompatible artifact'):
        m3.predict_podium(entrants, 'post_qualifying')


def test_legacy_directory_is_not_a_fallback(entrants, tmp_path, monkeypatch):
    legacy = tmp_path / 'legacy'
    legacy.mkdir()
    (legacy / 'post_qualifying.joblib').write_bytes(b'old artifact')
    monkeypatch.setattr(m3, 'LEGACY_ARTIFACTS', legacy)
    monkeypatch.setattr(m3, 'ARTIFACTS', legacy / 'v2/podium')
    with pytest.raises(m3.ArtifactCompatibilityError, match='Incompatible legacy artifact'):
        m3.predict_podium(entrants, 'post_qualifying')


def test_corrupted_pipeline_hash(trained):
    history, _ = trained
    path = m3.ARTIFACTS / 'post_qualifying.joblib'
    path.write_bytes(path.read_bytes() + b'corruption')
    with pytest.raises(m3.ArtifactCompatibilityError, match='hash mismatch'):
        m3.predict_podium(input_race(history), 'post_qualifying')


def test_wrong_pipeline_schema_is_rejected(trained):
    history, _ = trained
    path = m3.ARTIFACTS / 'post_qualifying.joblib'
    path.write_bytes((m3.ARTIFACTS / 'post_grid.joblib').read_bytes())
    meta_path = path.with_suffix('.json')
    meta = json.loads(meta_path.read_text())
    meta['artifact_sha256'] = sha256(path)
    meta_path.write_text(json.dumps(meta))
    with pytest.raises(m3.ArtifactCompatibilityError, match='matching input schema'):
        m3.predict_podium(input_race(history), 'post_qualifying')


def test_unverified_history_cannot_train(reviewed_history, tmp_path, monkeypatch):
    history = reviewed_history.copy()
    history.attrs.clear()
    monkeypatch.setattr(m3, 'ARTIFACTS', tmp_path / 'models')
    with pytest.raises(ValueError, match='approved M2 handoff'):
        m3.train(history, grid_verified=True)
    assert not m3.ARTIFACTS.exists()


def test_missing_handoff_at_prediction(trained):
    history, _ = trained
    race = input_race(history)
    race.attrs.clear()
    with pytest.raises(ValueError, match='approved M2 handoff'):
        m3.predict_podium(race, 'post_qualifying')


@pytest.mark.parametrize('mutation,match', [
    (lambda h: h.update(approved_for_modeling=False), 'not explicitly approved'),
    (lambda h: h.update(review_status='unresolved'), 'not explicitly approved'),
    (lambda h: h.update(contract_version='1.0'), 'incompatible contract/task/stage'),
    (lambda h: h['races'][0]['prediction_cutoffs_utc'].update(post_qualifying='2024-01-01T15:00:00+00:00'), 'cutoff must precede'),
])
def test_handoff_approval_and_cutoffs(reviewed_history, tmp_path, monkeypatch, mutation, match):
    edit_handoff(reviewed_history, 'post_qualifying', mutation)
    monkeypatch.setattr(m3, 'ARTIFACTS', tmp_path / 'models')
    with pytest.raises(ValueError, match=match):
        m3.train(reviewed_history, grid_verified=True)
    assert not m3.ARTIFACTS.exists()


def test_changed_evidence_hash_blocks_training(reviewed_history, tmp_path, monkeypatch):
    path = Path(reviewed_history.attrs['m2_handoffs']['post_qualifying']).parent / 'features.csv'
    path.write_text(path.read_text() + '\n')
    monkeypatch.setattr(m3, 'ARTIFACTS', tmp_path / 'models')
    with pytest.raises(ValueError, match='evidence hash mismatch'):
        m3.train(reviewed_history, grid_verified=True)


def test_future_lineage_observation_blocks_training(reviewed_history, tmp_path, monkeypatch):
    directory = Path(reviewed_history.attrs['m2_handoffs']['post_qualifying']).parent
    path = directory / 'lineage.csv'
    table = pd.read_csv(path)
    table.loc[0, 'available_at_utc'] = '2024-01-01T13:00:00+00:00'
    table.to_csv(path, index=False)
    refresh_record(reviewed_history, 'post_qualifying', 'lineage.csv')
    monkeypatch.setattr(m3, 'ARTIFACTS', tmp_path / 'models')
    with pytest.raises(ValueError, match='unavailable at the prediction cutoff'):
        m3.train(reviewed_history, grid_verified=True)


def test_request_must_match_approved_features(trained):
    history, _ = trained
    race = input_race(history).reset_index(drop=True)
    race.loc[0, 'qualifying_gap_seconds'] += 1
    with pytest.raises(ValueError, match='do not match the approved M2 handoff'):
        m3.predict_podium(race, 'post_qualifying')


def test_naive_training_dates_rejected(reviewed_history):
    history = reviewed_history.copy()
    history['race_date'] = history.race_date.str.replace('+00:00', '', regex=False)
    with pytest.raises(ValueError, match='timezone-aware UTC timestamp'):
        m3.train(history, grid_verified=True)


def test_duplicate_grid_positions_rejected(entrants):
    entrants.attrs['grid_verified'] = True
    entrants.loc[0, 'grid_position'] = 2
    with pytest.raises(ValueError, match='unique grid'):
        m3.validate(entrants, 'post_grid')


def test_incomplete_baseline_is_reported(entrants):
    class Constant:
        classes_ = np.array([0, 1])
        def predict_proba(self, data):
            return np.array([[.5, .5]] * len(data))
    data = entrants.assign(is_podium_actual=(entrants.driver_number <= 3).astype(int))
    data['qualifying_position'] = np.nan
    result = m3.evaluate(data, 'post_qualifying', Constant())
    assert result['baseline_races'] == 0
    assert result['baseline_unavailable_races'] == ['demo']
    assert result['baseline_mean_correct_picks'] is None
