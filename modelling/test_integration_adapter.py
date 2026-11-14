"""Synthetic evidence and stub inference only; never production artifacts."""
from dataclasses import replace
import json
import pandas as pd
import pytest
from f1_dashboard.contracts import Race, RaceInputs, DriverInput
import integration_adapter as adapter
from lap_synthetic import create_dataset, scenario_input


@pytest.fixture
def podium(reviewed_history):
    race = reviewed_history[reviewed_history.race_id == 'race_9']
    inputs = RaceInputs(Race('race_9', 'Synthetic GP', 'Synthetic', '2024-10-01',
                            '2024-10-01T14:00:00Z'), '2024-10-01T12:00:00Z',
                        '2024-10-01T11:00:00Z', '2024-10-01T10:00:00Z',
                        '2024-10-01T11:00:00Z', '2024-10-01T11:30:00Z', 35., False,
                        tuple(DriverInput(f'D{r.driver_number}', r.driver_name, r.qualifying_gap_seconds,
                                          None if pd.isna(r.practice_gap_seconds) else r.practice_gap_seconds,
                                          int(r.grid_position)) for r in race.itertuples()))
    drivers = pd.DataFrame([dict(dashboard_driver_id=f'D{r.driver_number}',
                                driver_id=f'synthetic_driver_{r.driver_number}', driver_number=r.driver_number,
                                qualifying_position=r.qualifying_position) for r in race.itertuples()])
    context = adapter.PodiumContext(reviewed_history.attrs['m2_handoffs']['post_qualifying'], drivers, 24.,
                'best_valid_all_segments_minus_session_best_seconds',
                'best_valid_selected_common_practice_minus_session_best_seconds',
                'SYNTHETIC reviewer', '2025-01-01T00:00:00Z')
    return inputs, context, reviewed_history


def stub_podium(monkeypatch, mutate=lambda out: out):
    calls = []
    def predict(data, stage):
        calls.append((data.copy(), stage))
        # Actual picks deliberately differ from the first three input drivers.
        out = data.iloc[::-1][['race_id', 'driver_number', 'driver_name']].reset_index(drop=True)
        out['podium_probability'] = [.9, .8, .7, .3, .2, .1]
        out['predicted_rank'] = range(1, 7)
        out['is_podium_pick'] = out.predicted_rank <= 3
        out['stage'] = stage
        out['model_name'] = 'random_forest'
        return mutate(out)
    monkeypatch.setattr(adapter.m3, 'predict_podium', predict)
    monkeypatch.setattr(adapter.m3, '_metadata', lambda *a: {'model_version': 'SYNTHETIC-v2'})
    return calls


@pytest.mark.parametrize('grid', [False, True])
def test_podium_translation(podium, monkeypatch, grid):
    inputs, context, history = podium
    stage = 'post_grid' if grid else 'post_qualifying'
    context = replace(context, handoff_path=history.attrs['m2_handoffs'][stage], grid_verified=grid)
    calls = stub_podium(monkeypatch)
    result = adapter.predict_podium(inputs, grid, context=context)
    assert result.picks == ['D4', 'D5', 'D6']
    assert result.model_version == 'SYNTHETIC-v2'
    assert result.evidence['handoff_id'].startswith('SYNTHETIC')
    frame, received = calls[0]
    assert received == stage
    assert ('grid_position' in frame) == grid
    assert frame.qualifying_rainfall.eq(0).all()
    assert frame.attrs['grid_verified'] is grid
    assert frame.practice_gap_seconds.isna().sum() == 1
    assert inputs.drivers[0].driver_id == 'D1'


@pytest.mark.parametrize('change,match', [
    (dict(qualifying_gap_definition='unknown'), 'qualifying delta'),
    (dict(practice_gap_definition='unknown'), 'practice delta'),
    (dict(reviewer=''), 'reviewer'),
    (dict(reviewed_at_utc='2025-01-01'), 'timezone-aware'),
    (dict(qualifying_air_temp_c=99), 'match'),
    (dict(handoff_path='missing.json'), 'Cannot read'),
])
def test_missing_review_context(podium, monkeypatch, change, match):
    inputs, context, _ = podium
    calls = stub_podium(monkeypatch)
    with pytest.raises(ValueError, match=match):
        adapter.predict_podium(inputs, False, context=replace(context, **change))
    assert not calls


@pytest.mark.parametrize('column', ['dashboard_driver_id', 'driver_id', 'driver_number'])
def test_ambiguous_mapping(podium, column):
    inputs, context, _ = podium
    drivers = context.drivers.copy()
    drivers.loc[1, column] = drivers.loc[0, column]
    with pytest.raises(ValueError, match='ambiguous'):
        adapter.predict_podium(inputs, False, context=replace(context, drivers=drivers))


def test_wrong_canonical_mapping(podium):
    inputs, context, _ = podium
    drivers = context.drivers.copy()
    drivers['driver_id'] = list(reversed(drivers.driver_id))
    with pytest.raises(ValueError, match='crosswalk'):
        adapter.predict_podium(inputs, False, context=replace(context, drivers=drivers))


@pytest.mark.parametrize('mutation', [
    lambda out: out.iloc[:3],
    lambda out: out.assign(is_podium_pick=False),
    lambda out: out.assign(driver_number=1),
    lambda out: out.assign(podium_probability=float('nan')),
    lambda out: out.assign(podium_probability=True),
    lambda out: out.assign(driver_name='wrong'),
    lambda out: out.assign(stage='wrong'),
    lambda out: out.drop(columns='model_name'),
    lambda out: out.assign(predicted_rank=1),
    lambda out: out.assign(is_podium_pick=1),
])
def test_invalid_results(podium, monkeypatch, mutation):
    inputs, context, _ = podium
    stub_podium(monkeypatch, mutation)
    with pytest.raises(ValueError):
        adapter.predict_podium(inputs, False, context=context)


def test_picks_ignore_output_row_order(podium, monkeypatch):
    inputs, context, _ = podium
    stub_podium(monkeypatch, lambda out: out.iloc[::-1])
    assert adapter.predict_podium(inputs, False, context=context).picks == ['D4', 'D5', 'D6']


def test_probability_ties_use_driver_number(podium, monkeypatch):
    inputs, context, _ = podium
    def tied(out):
        out = out.sort_values('driver_number').reset_index(drop=True)
        out['podium_probability'] = .5
        out['predicted_rank'] = range(1, 7)
        out['is_podium_pick'] = out.predicted_rank <= 3
        return out.iloc[::-1]
    stub_podium(monkeypatch, tied)
    assert adapter.predict_podium(inputs, False, context=context).picks == ['D1', 'D2', 'D3']


def test_incorrect_tie_ranks_rejected(podium, monkeypatch):
    inputs, context, _ = podium
    stub_podium(monkeypatch, lambda out: out.assign(podium_probability=.5))
    with pytest.raises(ValueError, match='tie policy'):
        adapter.predict_podium(inputs, False, context=context)


def test_unapproved_evidence(podium, monkeypatch):
    inputs, context, _ = podium
    from pathlib import Path
    path = Path(context.handoff_path)
    manifest = json.loads(path.read_text())
    manifest['approved_for_modeling'] = False
    path.write_text(json.dumps(manifest))
    calls = stub_podium(monkeypatch)
    with pytest.raises(ValueError, match='not explicitly approved'):
        adapter.predict_podium(inputs, False, context=context)
    assert not calls


def test_tampered_evidence(podium, monkeypatch):
    inputs, context, _ = podium
    from pathlib import Path
    feature_path = Path(context.handoff_path).parent / 'features.csv'
    feature_path.write_text(feature_path.read_text() + '\n')
    calls = stub_podium(monkeypatch)
    with pytest.raises(ValueError, match='hash mismatch'):
        adapter.predict_podium(inputs, False, context=context)
    assert not calls


def test_real_public_podium_missing_artifact(podium, monkeypatch, tmp_path):
    inputs, context, _ = podium
    monkeypatch.setattr(adapter.m3, 'ARTIFACTS', tmp_path / 'absent')
    with pytest.raises(FileNotFoundError):
        adapter.predict_podium(inputs, False, context=context)


def test_grid_attestation_required(podium):
    inputs, context, history = podium
    context = replace(context, handoff_path=history.attrs['m2_handoffs']['post_grid'])
    with pytest.raises(ValueError, match='grid_verified'):
        adapter.predict_podium(inputs, True, context=context)


def test_cutoff_disagreement(podium):
    inputs, context, _ = podium
    with pytest.raises(ValueError, match='cutoff'):
        adapter.predict_podium(replace(inputs, cutoff_utc='2024-10-01T12:01:00Z'), False, context=context)


def test_missing_supplementary_column(podium):
    inputs, context, _ = podium
    with pytest.raises(ValueError, match='Supplementary drivers'):
        adapter.predict_podium(inputs, False, context=replace(context, drivers=context.drivers.drop(columns='qualifying_position')))


def test_public_podium_artifact_error_propagates(podium, monkeypatch):
    inputs, context, _ = podium
    def reject(*args):
        raise adapter.m3.ArtifactCompatibilityError('SYNTHETIC incompatible artifact')
    monkeypatch.setattr(adapter.m3, 'predict_podium', reject)
    with pytest.raises(adapter.m3.ArtifactCompatibilityError, match='incompatible artifact'):
        adapter.predict_podium(inputs, False, context=context)


@pytest.fixture
def lap(tmp_path):
    create_dataset(tmp_path / 'evidence')
    frame = scenario_input(tmp_path / 'evidence')
    row = frame.iloc[0].to_dict()
    for key in ('compound', 'tyre_age_laps', 'track_temperature_c'):
        row.pop(key)
    return adapter.LapContext(row, 'scenario', frame.attrs['m2_context_path'],
               frame.attrs['scenario_provenance'], 'Synthetic Circuit', 'completed_laps_before_target')


def stub_lap(monkeypatch, status='numeric_extrapolation'):
    calls = []
    def predict(data):
        calls.append(data.copy())
        out = data[['example_id', 'race_id', 'driver_id', 'driver_number', 'driver_name', 'lap_number']].copy()
        out['mode'] = data.attrs['mode']
        out['prediction_time_utc'] = data.prediction_time_utc
        out['predicted_lap_time_seconds'] = 85.5
        out['model_name'] = 'linear_regression'
        out['model_version'] = 'SYNTHETIC-lap'
        out['is_hypothetical'] = data.attrs['mode'] == 'scenario'
        out['support_status'] = status
        return out[adapter.lap_model.OUTPUT_COLUMNS]
    monkeypatch.setattr(adapter.lap_model, 'predict_lap_time', predict)
    monkeypatch.setattr(adapter.lap_model, '_metadata', lambda *a: {'model_version': 'SYNTHETIC-lap'})
    return calls


def test_lap_conversion(lap, monkeypatch):
    calls = stub_lap(monkeypatch)
    result = adapter.estimate_lap('Synthetic Circuit', 'SOFT', 5, 30., context=lap)
    assert result.estimate.seconds == 85.5
    assert result.estimate.test_mae_seconds is None
    assert result.is_hypothetical
    assert result.support_status == 'numeric_extrapolation'
    assert result.evidence['handoff_sha256']
    assert list(calls[0].columns) == adapter.lap_model.INPUT_COLUMNS
    assert calls[0].attrs['scenario_provenance'] == lap.scenario_provenance


@pytest.mark.parametrize('change', [dict(row={}), dict(mode='wrong'), dict(scenario_provenance=None),
    dict(evidence_path='absent.json'), dict(tyre_age_convention='unknown')])
def test_lap_missing_context(lap, monkeypatch, change):
    calls = stub_lap(monkeypatch)
    with pytest.raises(ValueError):
        adapter.estimate_lap('Synthetic Circuit', 'SOFT', 5, 30., context=replace(lap, **change))
    assert not calls


@pytest.mark.parametrize('args', [('wrong circuit', 'SOFT', 5, 30.),
    ('Synthetic Circuit', 'UNKNOWN', 5, 30.), ('Synthetic Circuit', 'SOFT', True, 30.),
    ('Synthetic Circuit', 'SOFT', -1, 30.), ('Synthetic Circuit', 'SOFT', 5, float('inf'))])
def test_lap_invalid_inputs(lap, monkeypatch, args):
    calls = stub_lap(monkeypatch)
    with pytest.raises(ValueError):
        adapter.estimate_lap(*args, context=lap)
    assert not calls


def test_real_public_lap_missing_artifact(lap, monkeypatch, tmp_path):
    monkeypatch.setattr(adapter.lap_model, 'ARTIFACTS', tmp_path / 'absent')
    with pytest.raises(FileNotFoundError):
        adapter.estimate_lap('Synthetic Circuit', 'SOFT', 5, 30., context=lap)


def test_historical_lap_translation(tmp_path, monkeypatch):
    data, _ = create_dataset(tmp_path / 'historical')
    row = data.iloc[0].to_dict()
    compound, age, temperature = (row.pop(k) for k in ('compound', 'tyre_age_laps', 'track_temperature_c'))
    context = adapter.LapContext(row, 'historical', data.attrs['m2_handoff_path'], None,
                                'Synthetic Circuit', 'completed_laps_before_target')
    calls = stub_lap(monkeypatch, 'within_training_numeric_ranges')
    result = adapter.estimate_lap('Synthetic Circuit', compound, age, temperature, context=context)
    assert not result.is_hypothetical
    assert calls[0].attrs['m2_handoff_path'] == context.evidence_path


def test_lap_invalid_output(lap, monkeypatch):
    stub_lap(monkeypatch, 'invented-status')
    with pytest.raises(ValueError, match='status'):
        adapter.estimate_lap('Synthetic Circuit', 'SOFT', 5, 30., context=lap)


def test_lap_public_rejection_propagates(lap, monkeypatch):
    def reject(*args):
        raise ValueError('Unsupported lap prediction rows: synthetic unseen category')
    monkeypatch.setattr(adapter.lap_model, 'predict_lap_time', reject)
    with pytest.raises(ValueError, match='Unsupported lap prediction'):
        adapter.estimate_lap('Synthetic Circuit', 'SOFT', 5, 30., context=lap)


def test_lap_artifact_compatibility_error_propagates(lap, monkeypatch):
    def reject(*args):
        raise adapter.lap_model.LapArtifactCompatibilityError('SYNTHETIC incompatible artifact')
    monkeypatch.setattr(adapter.lap_model, 'predict_lap_time', reject)
    with pytest.raises(adapter.lap_model.LapArtifactCompatibilityError, match='incompatible artifact'):
        adapter.estimate_lap('Synthetic Circuit', 'SOFT', 5, 30., context=lap)


def test_tampered_lap_evidence(lap, monkeypatch):
    from pathlib import Path
    path = Path(lap.evidence_path)
    manifest = json.loads(path.read_text())
    evidence = path.parent / manifest['files'][0]['relative_path']
    evidence.write_bytes(evidence.read_bytes() + b'\n')
    calls = stub_lap(monkeypatch)
    with pytest.raises(ValueError, match='hash mismatch'):
        adapter.estimate_lap('Synthetic Circuit', 'SOFT', 5, 30., context=lap)
    assert not calls


def test_unapproved_lap_context(lap, monkeypatch):
    from pathlib import Path
    path = Path(lap.evidence_path)
    manifest = json.loads(path.read_text())
    manifest['approved_for_modeling'] = False
    path.write_text(json.dumps(manifest))
    calls = stub_lap(monkeypatch)
    with pytest.raises(ValueError, match='not explicitly approved'):
        adapter.estimate_lap('Synthetic Circuit', 'SOFT', 5, 30., context=lap)
    assert not calls


@pytest.mark.parametrize('field,value', [('example_id', 'wrong-example'),
    ('model_version', 'wrong-version'), ('predicted_lap_time_seconds', -1),
    ('is_hypothetical', False)])
def test_lap_result_integrity(lap, monkeypatch, field, value):
    stub_lap(monkeypatch)
    original = adapter.lap_model.predict_lap_time
    def changed(data):
        return original(data).assign(**{field: value})
    monkeypatch.setattr(adapter.lap_model, 'predict_lap_time', changed)
    with pytest.raises(ValueError):
        adapter.estimate_lap('Synthetic Circuit', 'SOFT', 5, 30., context=lap)
