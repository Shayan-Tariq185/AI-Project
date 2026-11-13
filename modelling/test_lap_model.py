"""Synthetic-only tests for contract-v2 lap-time prediction."""
import inspect
import json
from pathlib import Path
import shutil
from uuid import uuid4
from unittest.mock import patch
import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LinearRegression
from sklearn.dummy import DummyRegressor
import lap_model as lm
import lap_handoff
from lap_synthetic import create_dataset, scenario_input
from podium_handoff import sha256


@pytest.fixture(scope='module')
def base_model():
    root = Path(__file__).resolve().parent / '.test-work' / ('lap_tests_'+uuid4().hex)
    data, labels = create_dataset(root / 'evidence')
    with patch.object(lm, 'ARTIFACTS', root / 'artifacts'):
        report = lm.train_lap_model(data, labels)
    return root, data, labels, report


@pytest.fixture
def trained(base_model, tmp_path, monkeypatch):
    root, data, labels, report = base_model
    shutil.copytree(root / 'artifacts', tmp_path / 'artifacts')
    monkeypatch.setattr(lm, 'ARTIFACTS', tmp_path / 'artifacts')
    return root, data, labels, report


@pytest.fixture
def make_data(tmp_path):
    def make(**kwargs):
        return create_dataset(tmp_path / uuid4().hex, **kwargs)
    return make


def update_record(data, filename):
    path = Path(data.attrs['m2_handoff_path'])
    handoff = json.loads(path.read_text())
    file = path.parent / filename
    table = pd.DataFrame([json.loads(file.read_text())]) if file.suffix == '.json' else pd.read_csv(file)
    record = next(r for r in handoff['files'] if r['relative_path'] == filename)
    record.update(sha256=sha256(file), row_count=len(table), ordered_columns=list(table.columns))
    path.write_text(json.dumps(handoff))


def test_pipeline_and_contract(base_model):
    root, data, labels, report = base_model
    model = joblib.load(root / 'artifacts/linear_regression.joblib')
    assert isinstance(model.named_steps['model'], LinearRegression)
    preprocess = model.named_steps['preprocess']
    encoder = preprocess.named_transformers_['categorical']
    assert encoder.drop == 'first' and encoder.handle_unknown == 'error'
    assert list(model.feature_names_in_) == lm.FEATURES
    assert preprocess.named_transformers_['numeric'].n_features_in_ == 2
    assert list(inspect.signature(lm.predict_lap_time).parameters) == ['lap_data']
    assert [report['partitions'][k]['races'] for k in ('train','validation','test')] == [6,2,2]
    sets = [set(report['partitions'][k]['race_ids']) for k in ('train','validation','test')]
    assert sets[0].isdisjoint(sets[1] | sets[2]) and sets[1].isdisjoint(sets[2])
    assert report['test']['rows'] == 24 and report['test']['predicted_rows'] == 24
    assert report['test']['baseline']['rows'] == 24
    assert set(report['test']['metrics']) == {'mae','rmse','median_absolute_error','signed_bias','r2'}


def test_synthetic_scenario_api(trained):
    root, _, _, _ = trained
    output = lm.predict_lap_time(scenario_input(root / 'evidence'))
    assert list(output.columns) == lm.OUTPUT_COLUMNS
    assert output.predicted_lap_time_seconds.item() == pytest.approx(85.5)
    assert output.is_hypothetical.item()
    assert output.model_name.item() == 'linear_regression'
    assert output.support_status.item() == 'within_training_numeric_ranges'


def test_historical_order_and_persistence(trained):
    _, data, _, _ = trained
    subset = data.iloc[[119,118,117]].copy()
    subset.attrs = dict(data.attrs)
    output = lm.predict_lap_time(subset)
    assert output.example_id.tolist() == subset.example_id.tolist()
    assert not output.is_hypothetical.any()
    model = joblib.load(lm.ARTIFACTS / 'linear_regression.joblib')
    np.testing.assert_allclose(output.predicted_lap_time_seconds, model.predict(subset[lm.FEATURES]))
    meta = json.loads((lm.ARTIFACTS / 'linear_regression.json').read_text())
    assert meta['contract_version'] == '2.0' and meta['task'] == 'lap_time'
    assert meta['training_handoff_ids'][0].startswith('SYNTHETIC-LAP-ONLY')
    assert meta['features'] == lm.FEATURES
    assert meta['assumption_decisions']['A2']['max_age_seconds'] == 120


@pytest.mark.parametrize('column,value,match', [
    ('driver_name',' ','nonempty'), ('tyre_age_laps',-1,'integer/range'),
    ('tyre_age_laps',1.5,'integer/range'), ('driver_number',True,'booleans'),
    ('compound','SUPERSOFT','Unknown tire'), ('track_temperature_c',np.inf,'finite'),
    ('track_temperature_c',None,'finite'), ('prediction_time_utc','2024-09-01T10:00:00','timezone-aware'),
    ('weather_observed_at_utc','2024-09-01T11:00:00+00:00','Future weather'),
])
def test_invalid_values(base_model, column, value, match):
    root, _, _, _ = base_model
    data = scenario_input(root / 'evidence')
    data[column] = value
    with pytest.raises(ValueError, match=match):
        lm.validate(data)


def test_exact_schema_and_explicit_mode(base_model):
    root, _, _, _ = base_model
    data = scenario_input(root / 'evidence')
    for bad in (data.assign(lap_time_actual_seconds=90), data.drop(columns='compound'), data[lm.INPUT_COLUMNS[::-1]]):
        with pytest.raises(ValueError, match='exactly the ordered'):
            lm.validate(bad)
    data.attrs.clear()
    with pytest.raises(ValueError, match='attrs'):
        lm.validate(data)
    duplicate = pd.concat([data,data], ignore_index=True)
    duplicate.attrs['mode'] = 'scenario'
    with pytest.raises(ValueError, match='Duplicate example_id'):
        lm.validate(duplicate)


def test_historical_required_keys_and_weather(base_model):
    _, data, _, _ = base_model
    for column in ('session_key','lap_number','weather_observed_at_utc'):
        invalid = data.iloc[:1].copy()
        invalid[column] = None
        with pytest.raises(ValueError):
            lm.validate(invalid)


def test_numeric_extrapolation_and_nonpositive_error(trained):
    root, _, _, _ = trained
    data = scenario_input(root / 'evidence')
    data['tyre_age_laps'] = 30
    assert lm.predict_lap_time(data).support_status.item() == 'numeric_extrapolation'
    data['track_temperature_c'] = -1e8
    with pytest.raises(ValueError, match='not clipped'):
        lm.predict_lap_time(data)


def test_scenario_provenance_and_cutoff(trained):
    root, _, _, _ = trained
    data = scenario_input(root / 'evidence')
    data.attrs.pop('scenario_provenance')
    with pytest.raises(ValueError, match='assumption provenance'):
        lm.predict_lap_time(data)
    data = scenario_input(root / 'evidence')
    data['prediction_time_utc'] = '2024-09-04T10:00:00+00:00'
    with pytest.raises(ValueError, match='precede GP race'):
        lm.predict_lap_time(data)


def test_missing_artifact(base_model, tmp_path, monkeypatch):
    root, _, _, _ = base_model
    monkeypatch.setattr(lm, 'ARTIFACTS', tmp_path / 'absent')
    with pytest.raises(FileNotFoundError, match='No trained lap-time artifact'):
        lm.predict_lap_time(scenario_input(root / 'evidence'))


@pytest.mark.parametrize('field,value', [
    ('contract_version','1.0'), ('task','podium'), ('model_name','random_forest'),
    ('features', ['track_temperature_c']), ('versions', {}), ('scope','race_laps'),
])
def test_incompatible_metadata_before_unpickle(trained, monkeypatch, field, value):
    root, _, _, _ = trained
    path = lm.ARTIFACTS / 'linear_regression.json'
    meta = json.loads(path.read_text()); meta[field]=value
    path.write_text(json.dumps(meta))
    monkeypatch.setattr(lm.joblib, 'load', lambda _: pytest.fail('Bad artifact was unpickled'))
    with pytest.raises(lm.LapArtifactCompatibilityError):
        lm.predict_lap_time(scenario_input(root / 'evidence'))


def test_missing_metadata_and_hash(trained):
    root, _, _, _ = trained
    metadata = lm.ARTIFACTS / 'linear_regression.json'
    contents = metadata.read_text(); metadata.unlink()
    with pytest.raises(lm.LapArtifactCompatibilityError, match='metadata'):
        lm.predict_lap_time(scenario_input(root / 'evidence'))
    metadata.write_text(contents)
    path = lm.ARTIFACTS / 'linear_regression.joblib'
    path.write_bytes(path.read_bytes()+b'tamper')
    with pytest.raises(lm.LapArtifactCompatibilityError, match='hash mismatch'):
        lm.predict_lap_time(scenario_input(root / 'evidence'))


def test_wrong_estimator_payload(trained):
    root, data, labels, _ = trained
    path = lm.ARTIFACTS / 'linear_regression.joblib'
    wrong = DummyRegressor().fit(np.ones((3,1)), [80,81,82])
    joblib.dump(wrong, path)
    meta_path = path.with_suffix('.json')
    meta = json.loads(meta_path.read_text()); meta['artifact_sha256']=sha256(path)
    meta_path.write_text(json.dumps(meta))
    with pytest.raises(lm.LapArtifactCompatibilityError, match='LinearRegression'):
        lm.predict_lap_time(scenario_input(root / 'evidence'))


def test_no_unverified_or_scenario_training(make_data, tmp_path, monkeypatch):
    data, labels = make_data()
    monkeypatch.setattr(lm, 'ARTIFACTS', tmp_path / 'models')
    unapproved = data.copy(); unapproved.attrs['m2_handoff_path']=None
    with pytest.raises(ValueError, match='M2'):
        lm.train_lap_model(unapproved, labels)
    scenario = scenario_input(Path(data.attrs['m2_handoff_path']).parent)
    with pytest.raises(ValueError, match='scenarios cannot train'):
        lm.train_lap_model(scenario, labels)
    assert not lm.ARTIFACTS.exists()


def test_labels_are_separate_and_never_imputed(base_model):
    _, data, labels, _ = base_model
    for bad in (labels.iloc[:-1], labels.assign(lap_time_actual_seconds=np.nan),
                labels.assign(lap_time_actual_seconds=-1), labels.assign(extra=0)):
        with pytest.raises(ValueError):
            lm.validate_labels(bad, data.example_id)


def test_reviewed_tire_age_and_future_stint_metadata(make_data):
    data, _ = make_data()
    directory = Path(data.attrs['m2_handoff_path']).parent
    path = directory / 'examples.csv'
    table = pd.read_csv(path)
    table.loc[0,'tyre_age_at_start'] += 1
    table.to_csv(path,index=False); update_record(data,'examples.csv')
    with pytest.raises(ValueError, match='Tire age/compound'):
        lap_handoff.historical(lm.validate(data),lm.INPUT_COLUMNS)
    table.loc[0,'tyre_age_at_start'] -= 1
    table.loc[0,'stint_available_at_utc'] = '2030-01-01T00:00:00+00:00'
    table.to_csv(path,index=False); update_record(data,'examples.csv')
    with pytest.raises(ValueError, match='unavailable at prediction'):
        lap_handoff.historical(lm.validate(data),lm.INPUT_COLUMNS)


def test_latest_weather_and_staleness_are_verified(make_data):
    data, _ = make_data()
    path = Path(data.attrs['m2_handoff_path'])
    value = json.loads(path.read_text())
    value['assumption_decisions']['A2']['max_age_seconds']=10
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match='Stale practice weather'):
        lap_handoff.historical(lm.validate(data),lm.INPUT_COLUMNS)
    value['assumption_decisions']['A2']['max_age_seconds']=120
    path.write_text(json.dumps(value))
    weather_path = path.parent / 'weather.csv'
    weather = pd.read_csv(weather_path)
    future = weather.iloc[:1].copy()
    future['date']='2030-01-01T00:00:00+00:00'
    future['available_at_utc']='2030-01-01T00:00:00+00:00'
    future['track_temperature']=999
    pd.concat([weather,future],ignore_index=True).to_csv(weather_path,index=False)
    update_record(data,'weather.csv')
    lap_handoff.historical(lm.validate(data),lm.INPUT_COLUMNS)


def test_future_lineage_and_bad_hash_are_rejected(make_data):
    data, _ = make_data()
    directory = Path(data.attrs['m2_handoff_path']).parent
    path = directory/'lineage.csv'
    table=pd.read_csv(path)
    table.loc[0,'available_at_utc']='2030-01-01T00:00:00+00:00'
    table.to_csv(path,index=False); update_record(data,'lineage.csv')
    with pytest.raises(ValueError, match='future information'):
        lap_handoff.historical(lm.validate(data),lm.INPUT_COLUMNS)
    path.write_text(path.read_text()+'\n')
    with pytest.raises(ValueError, match='hash mismatch'):
        lap_handoff.historical(lm.validate(data),lm.INPUT_COLUMNS)


def test_scaling_excludes_test_races(make_data, tmp_path, monkeypatch):
    data, labels = make_data(test_shift=1000)
    monkeypatch.setattr(lm, 'ARTIFACTS', tmp_path/'models')
    report=lm.train_lap_model(data,labels)
    model=joblib.load(lm.ARTIFACTS/'linear_regression.joblib')
    history=data[data.race_id.isin(report['partitions']['train']['race_ids']+report['partitions']['validation']['race_ids'])]
    np.testing.assert_allclose(model.named_steps['preprocess'].named_transformers_['numeric'].mean_,history[lm.NUMERIC].mean())
    assert set(model.feature_names_in_) == set(lm.FEATURES)


def test_unseen_test_circuit_reports_coverage_and_abstains(make_data,tmp_path,monkeypatch):
    data, labels = make_data(unseen_test_circuit=True)
    monkeypatch.setattr(lm, 'ARTIFACTS', tmp_path/'models')
    report=lm.train_lap_model(data,labels)
    assert report['test']['predicted_rows']==0
    assert len(report['test']['unsupported_rows'])==24
    assert all(v is None for v in report['test']['metrics'].values())
    subset=data.iloc[-1:].copy(); subset.attrs=dict(data.attrs)
    with pytest.raises(ValueError, match='Unsupported lap prediction'):
        lm.predict_lap_time(subset)


def test_metric_definitions():
    result=lm.metrics([10,20],[12,17])
    assert result['mae']==2.5
    assert result['rmse']==pytest.approx(np.sqrt(6.5))
    assert result['median_absolute_error']==2.5
    assert result['signed_bias']==-.5
    assert result['r2']==pytest.approx(.74)
    assert lm.metrics([],[])['mae'] is None
    assert lm.metrics([10],[10])['r2'] is None


def test_training_dates_group_all_laps_and_reject_ties(base_model):
    _,data,_,_=base_model
    package=lap_handoff.load_package(data.attrs['m2_handoff_path'])
    groups=lm.chronological_split(data,package['races'])
    assert sum(len(v) for v in groups.values())==10
    races={k:dict(v) for k,v in package['races'].items()}
    for r in races.values():r['race_start_utc']='2024-01-03T14:00:00+00:00'
    with pytest.raises(ValueError,match='strictly chronological'):
        lm.chronological_split(data,races)
    with pytest.raises(ValueError,match='five approved'):
        lm.chronological_split(data.iloc[:12],package['races'])
