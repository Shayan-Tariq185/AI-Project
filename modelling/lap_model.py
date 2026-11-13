"""Contract-v2 Linear Regression for clean practice flying laps only."""
from pathlib import Path
import json
import platform
import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, median_absolute_error, r2_score
from podium_handoff import sha256, utc
import lap_handoff

ROOT = Path(__file__).resolve().parent
ARTIFACTS = ROOT / 'artifacts/v2/lap_time'
CONTRACT_VERSION = '2.0'
MODEL_NAME = 'linear_regression'
SCOPE = 'clean_normal_practice_flying_laps'
INPUT_COLUMNS = ['example_id', 'race_id', 'session_key', 'driver_number', 'driver_name',
                 'driver_id', 'circuit_id', 'lap_number', 'prediction_time_utc',
                 'compound', 'tyre_age_laps', 'track_temperature_c', 'weather_observed_at_utc']
FEATURES = ['compound', 'tyre_age_laps', 'track_temperature_c', 'circuit_id', 'driver_id']
CATEGORICAL = ['compound', 'circuit_id', 'driver_id']
NUMERIC = ['tyre_age_laps', 'track_temperature_c']
OUTPUT_COLUMNS = ['example_id', 'race_id', 'driver_id', 'driver_number', 'driver_name',
                  'lap_number', 'mode', 'prediction_time_utc', 'predicted_lap_time_seconds',
                  'model_name', 'model_version', 'is_hypothetical', 'support_status']
LABEL_COLUMNS = ['example_id', 'lap_time_actual_seconds']
COMPOUNDS = {'SOFT', 'MEDIUM', 'HARD', 'INTERMEDIATE', 'WET'}


class LapArtifactCompatibilityError(ValueError):
    """A saved object is not a supported v2 lap-time Linear Regression pipeline."""


def validate(lap_data):
    if not isinstance(lap_data, pd.DataFrame) or lap_data.empty:
        raise ValueError('Lap input must be a nonempty DataFrame')
    if list(lap_data.columns) != INPUT_COLUMNS:
        raise ValueError(f'Lap input requires exactly the ordered contract columns; labels/extra fields are forbidden: {INPUT_COLUMNS}')
    mode = lap_data.attrs.get('mode')
    if mode not in ('historical', 'scenario'):
        raise ValueError('Set DataFrame.attrs[mode] explicitly to historical or scenario')
    data = lap_data.copy()
    for column in ('example_id', 'race_id', 'driver_name', 'driver_id', 'circuit_id', 'compound'):
        bad = ~data[column].map(lambda v: isinstance(v, str) and bool(v.strip()))
        if bad.any():
            raise ValueError(f'{column} must contain nonempty strings; rows {list(data.index[bad])}')
    if data.example_id.duplicated().any():
        raise ValueError('Duplicate example_id in lap input')
    if not data.compound.isin(COMPOUNDS).all():
        raise ValueError('Unknown tire compound in lap input')
    for column in ('session_key', 'driver_number', 'lap_number', 'tyre_age_laps', 'track_temperature_c'):
        if data[column].map(lambda v: isinstance(v, (bool, np.bool_))).any():
            raise ValueError(f'{column} cannot contain booleans')
        try:
            values = pd.to_numeric(data[column], errors='raise').astype(float)
        except (ValueError, TypeError) as exc:
            raise ValueError(f'{column} must be numeric') from exc
        nullable = mode == 'scenario' and column in ('session_key', 'lap_number')
        if np.isinf(values).any() or (not nullable and values.isna().any()):
            raise ValueError(f'{column} must be finite and present')
        if column != 'track_temperature_c':
            if (values.dropna() % 1 != 0).any() or (values.dropna() < (0 if column == 'tyre_age_laps' else 1)).any():
                raise ValueError(f'{column} has invalid integer/range values')
            data[column] = values.astype('Int64')
        else:
            data[column] = values
    data['prediction_time_utc'] = data.prediction_time_utc.map(lambda v: utc(v, 'prediction_time_utc'))
    weather = []
    for row in data.to_dict('records'):
        value = row['weather_observed_at_utc']
        if pd.isna(value):
            if mode == 'historical':
                raise ValueError(f"Historical weather timestamp missing: {row['example_id']}")
            weather.append(pd.NaT)
        else:
            observed = utc(value, 'weather_observed_at_utc')
            if observed > row['prediction_time_utc']:
                raise ValueError(f"Future weather is forbidden: {row['example_id']}")
            weather.append(observed)
    data['weather_observed_at_utc'] = pd.to_datetime(weather, utc=True)
    observed = data[data.session_key.notna() & data.lap_number.notna()]
    if observed.duplicated(['race_id', 'session_key', 'driver_id', 'lap_number']).any() and mode == 'historical':
        raise ValueError('Duplicate physical historical lap under different example IDs')
    for (_, _), group in data.groupby(['race_id', 'driver_id']):
        if group.driver_number.nunique() != 1 or group.driver_name.nunique() != 1:
            raise ValueError('Conflicting driver context within a race')
    if any(g.driver_id.nunique() != 1 for _, g in data.groupby(['race_id', 'driver_number'])):
        raise ValueError('Duplicate driver-number assignment within a race')
    if any(g.circuit_id.nunique() != 1 for _, g in data.groupby('race_id')):
        raise ValueError('Conflicting circuit context within one race')
    data.attrs = dict(lap_data.attrs)
    return data


def validate_labels(labels, example_ids):
    if not isinstance(labels, pd.DataFrame) or list(labels.columns) != LABEL_COLUMNS or labels.example_id.duplicated().any():
        raise ValueError('Lap targets require a separate exact-schema unique label table')
    if set(labels.example_id) != set(example_ids):
        raise ValueError('Every historical example needs exactly one target; scenario labels are forbidden')
    result = labels.copy()
    try:
        result['lap_time_actual_seconds'] = pd.to_numeric(result.lap_time_actual_seconds, errors='raise').astype(float)
    except (ValueError, TypeError) as exc:
        raise ValueError('Lap targets must be numeric') from exc
    if not np.isfinite(result.lap_time_actual_seconds).all() or (result.lap_time_actual_seconds <= 0).any():
        raise ValueError('Missing/nonpositive lap targets cannot be imputed')
    return result


def pipeline():
    return Pipeline([
        ('preprocess', ColumnTransformer([
            ('categorical', OneHotEncoder(drop='first', handle_unknown='error', sparse_output=False), CATEGORICAL),
            ('numeric', StandardScaler(), NUMERIC)], remainder='drop')),
        ('model', LinearRegression())])


def _domains(model):
    encoder = model.named_steps['preprocess'].named_transformers_['categorical']
    return {c: list(values) for c, values in zip(CATEGORICAL, encoder.categories_)}


def _unsupported(data, domains):
    reasons = {}
    for row in data.to_dict('records'):
        bad = [c for c in CATEGORICAL if row[c] not in domains[c]]
        if bad:
            reasons[row['example_id']] = 'unsupported categories: ' + ', '.join(bad)
    return reasons


def _score(data, model, metadata):
    unsupported = _unsupported(data, metadata['supported_domains'])
    if unsupported:
        raise ValueError(f'Unsupported lap prediction rows: {unsupported}')
    predictions = np.asarray(model.predict(data[FEATURES]), dtype=float)
    if not np.isfinite(predictions).all() or (predictions <= 0).any():
        bad = data.loc[~np.isfinite(predictions) | (predictions <= 0), 'example_id'].tolist()
        raise ValueError(f'Nonpositive/nonfinite lap predictions are unsupported, not clipped: {bad}')
    output = data[['example_id', 'race_id', 'driver_id', 'driver_number', 'driver_name',
                   'lap_number']].copy().reset_index(drop=True)
    output['mode'] = data.attrs['mode']
    output['prediction_time_utc'] = data.prediction_time_utc.to_numpy()
    output['predicted_lap_time_seconds'] = predictions
    output['model_name'] = MODEL_NAME
    output['model_version'] = metadata['model_version']
    output['is_hypothetical'] = data.attrs['mode'] == 'scenario'
    outside = np.zeros(len(data), dtype=bool)
    for c in NUMERIC:
        bounds = metadata['numeric_training_ranges'][c]
        outside |= ((data[c] < bounds['min']) | (data[c] > bounds['max'])).to_numpy(dtype=bool)
    output['support_status'] = np.where(outside, 'numeric_extrapolation', 'within_training_numeric_ranges')
    return output[OUTPUT_COLUMNS]


def versions():
    return {'python': platform.python_version(), 'sklearn': sklearn.__version__,
            'pandas': pd.__version__, 'numpy': np.__version__, 'joblib': joblib.__version__}


def _metadata(path):
    try:
        meta = json.loads(path.with_suffix('.json').read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise LapArtifactCompatibilityError('Missing/malformed lap artifact metadata; no pickle loaded') from exc
    expected = {'contract_version': CONTRACT_VERSION, 'task': 'lap_time', 'model_name': MODEL_NAME,
                'scope': SCOPE, 'features': FEATURES, 'input_columns': INPUT_COLUMNS, 'output_columns': OUTPUT_COLUMNS}
    required = {'model_version', 'versions', 'training_handoff_ids', 'source_hashes', 'training_race_cutoff',
                'partitions', 'preprocessing', 'supported_domains', 'category_training_counts',
                'numeric_training_ranges', 'assumption_decisions', 'evaluation', 'artifact_sha256'}
    if not isinstance(meta, dict) or any(meta.get(k) != v for k, v in expected.items()) or required - set(meta):
        raise LapArtifactCompatibilityError('Incompatible artifact: contract 2.0 lap_time LinearRegression with exact schema required')
    current = versions()
    if (not isinstance(meta['versions'], dict) or any(meta['versions'].get(k) != v for k, v in current.items() if k != 'python')
            or str(meta['versions'].get('python', '')).split('.')[:2] != current['python'].split('.')[:2]):
        raise LapArtifactCompatibilityError('Incompatible lap artifact library/Python versions')
    try:
        lap_handoff.decisions(meta['assumption_decisions'])
        if not isinstance(meta['model_version'], str) or not meta['model_version']:
            raise ValueError('Missing model_version')
        for c in CATEGORICAL:
            if not isinstance(meta['supported_domains'][c], list) or not meta['supported_domains'][c]:
                raise ValueError('Missing supported categorical domain')
        for c in NUMERIC:
            b = meta['numeric_training_ranges'][c]
            if not np.isfinite([b['min'], b['max']]).all() or b['min'] > b['max']:
                raise ValueError('Invalid numeric training range')
    except (ValueError, TypeError, KeyError) as exc:
        raise LapArtifactCompatibilityError('Incompatible lap artifact support/policy metadata') from exc
    if sha256(path) != meta['artifact_sha256']:
        raise LapArtifactCompatibilityError('Lap artifact pipeline hash mismatch')
    return meta


def _load(path, metadata):
    try:
        model = joblib.load(path)
    except Exception as exc:
        raise LapArtifactCompatibilityError('Cannot deserialize lap artifact pipeline') from exc
    if (not isinstance(model, Pipeline) or not isinstance(model.named_steps.get('model'), LinearRegression)
            or not isinstance(model.named_steps.get('preprocess'), ColumnTransformer)
            or list(getattr(model, 'feature_names_in_', [])) != FEATURES):
        raise LapArtifactCompatibilityError('Expected a fitted LinearRegression lap pipeline')
    try:
        preprocess = model.named_steps['preprocess']
        encoder = preprocess.named_transformers_['categorical']
        scaler = preprocess.named_transformers_['numeric']
        if (not isinstance(encoder, OneHotEncoder) or encoder.drop != 'first' or encoder.handle_unknown != 'error'
                or not isinstance(scaler, StandardScaler) or _domains(model) != metadata['supported_domains']
                or list(preprocess.transformers[0][2]) != CATEGORICAL or list(preprocess.transformers[1][2]) != NUMERIC
                or not np.isfinite(model.named_steps['model'].coef_).all()):
            raise ValueError('Incompatible preprocessing')
    except (KeyError, AttributeError, ValueError, IndexError) as exc:
        raise LapArtifactCompatibilityError('Incompatible/unfitted lap preprocessing or support domains') from exc
    return model


def predict_lap_time(lap_data: pd.DataFrame) -> pd.DataFrame:
    """Mode is explicit in attrs; exact contract columns are never extended."""
    data = validate(lap_data)
    path = ARTIFACTS / 'linear_regression.joblib'
    if not path.is_file():
        raise FileNotFoundError(f'No trained lap-time artifact: {path}; M2-approved training is required')
    metadata = _metadata(path)
    package = (lap_handoff.historical(data, INPUT_COLUMNS) if data.attrs['mode'] == 'historical'
               else lap_handoff.scenario(data))
    if package['policy'] != metadata['assumption_decisions']:
        raise ValueError('Lap handoff/context assumption policy differs from model artifact')
    return _score(data, _load(path, metadata), metadata)


def chronological_split(data, races):
    starts = {rid: utc(info['race_start_utc'], 'Race start') for rid, info in races.items() if rid in set(data.race_id)}
    order = pd.Series(starts).sort_values(kind='stable')
    if len(order) < 5:
        raise ValueError('At least five approved race-weekend groups are required for the 60/20/20 lap split')
    a, b = int(len(order)*.6), int(len(order)*.8)
    groups = {'train': order.iloc[:a], 'validation': order.iloc[a:b], 'test': order.iloc[b:]}
    if any(g.empty for g in groups.values()) or not groups['train'].max() < groups['validation'].min() or not groups['validation'].max() < groups['test'].min():
        raise ValueError('Lap partition boundaries must be strictly chronological')
    # Entire sessions/laps in a race stay with that race. Also require every
    # training target to have completed before the next partition predictions.
    return {name: list(group.index) for name, group in groups.items()}


def metrics(actual, predicted):
    if len(actual) == 0:
        return {'mae': None, 'rmse': None, 'median_absolute_error': None, 'signed_bias': None, 'r2': None}
    actual, predicted = np.asarray(actual, dtype=float), np.asarray(predicted, dtype=float)
    return {'mae': float(mean_absolute_error(actual, predicted)),
            'rmse': float(np.sqrt(mean_squared_error(actual, predicted))),
            'median_absolute_error': float(median_absolute_error(actual, predicted)),
            'signed_bias': float(np.mean(predicted-actual)),
            'r2': float(r2_score(actual, predicted)) if len(actual) >= 2 and np.var(actual) > 0 else None}


def evaluate(data, labels, model, baseline_history, baseline_labels, examples):
    """Fixed fitted model; baseline uses only prior training targets, never test targets."""
    actual = labels.set_index('example_id').lap_time_actual_seconds
    unsupported = _unsupported(data, _domains(model))
    eligible = data[~data.example_id.isin(unsupported)].copy()
    predictions = {}
    if len(eligible):
        p = model.predict(eligible[FEATURES])
        for eid, value in zip(eligible.example_id, p):
            if not np.isfinite(value) or value <= 0:
                unsupported[eid] = 'nonpositive/nonfinite prediction'
            else:
                predictions[eid] = float(value)
    ids = list(predictions)
    report = {'rows': len(data), 'predicted_rows': len(ids), 'unsupported_rows': unsupported,
              'metrics': metrics([actual[eid] for eid in ids], [predictions[eid] for eid in ids])}
    prior = baseline_history[['example_id', 'driver_id', 'circuit_id']].merge(baseline_labels, on='example_id', validate='one_to_one')
    prior['available'] = prior.example_id.map(lambda eid: utc(examples.loc[eid, 'target_available_at_utc'], 'Prior target availability'))
    baselines, strategies = {}, {}
    for row in data.to_dict('records'):
        known = prior[(prior.available <= row['prediction_time_utc']) & (prior.circuit_id == row['circuit_id'])]
        driver = known[known.driver_id == row['driver_id']]
        if not driver.empty:
            baselines[row['example_id']] = float(driver.sort_values('available').iloc[-1].lap_time_actual_seconds)
            strategies[row['example_id']] = 'last_prior_training_driver_circuit_lap'
        elif not known.empty:
            baselines[row['example_id']] = float(known.lap_time_actual_seconds.median())
            strategies[row['example_id']] = 'prior_training_circuit_median'
    common = [eid for eid in ids if eid in baselines]
    report['baseline'] = {'rows': len(baselines), 'unavailable_rows': [eid for eid in data.example_id if eid not in baselines],
                          'strategy_counts': pd.Series(list(strategies.values()), dtype=object).value_counts().to_dict(),
                          'metrics': metrics([actual[eid] for eid in baselines], list(baselines.values())),
                          'common_comparison_rows': len(common),
                          'common_metrics': metrics([actual[eid] for eid in common], [baselines[eid] for eid in common]),
                          'model_common_metrics': metrics([actual[eid] for eid in common], [predictions[eid] for eid in common])}
    by_race = {}
    for race, group in data.groupby('race_id'):
        eids = [eid for eid in group.example_id if eid in predictions]
        by_race[race] = {'rows': len(group), 'predicted_rows': len(eids),
                         'metrics': metrics([actual[eid] for eid in eids], [predictions[eid] for eid in eids])}
    report['by_race'] = by_race
    report['race_macro_metrics'] = {key: float(np.mean(values)) if values else None for key in metrics([], []) for values in [[r['metrics'][key] for r in by_race.values() if r['metrics'][key] is not None]]}
    report['breakdowns'] = {}
    for field in ('circuit_id', 'driver_id', 'compound', 'session_key', 'tyre_age_laps'):
        report['breakdowns'][field] = {}
        for value, group in data.groupby(field):
            eids = [eid for eid in group.example_id if eid in predictions]
            report['breakdowns'][field][str(value)] = {'rows': len(group), 'predicted_rows': len(eids),
                'metrics': metrics([actual[eid] for eid in eids], [predictions[eid] for eid in eids])}
    return report


def train_lap_model(lap_data, lap_labels):
    """No production data is usable without approved, hash-matched M2 evidence."""
    data = validate(lap_data)
    if data.attrs['mode'] != 'historical':
        raise ValueError('Hypothetical scenarios cannot train a lap model')
    labels = validate_labels(lap_labels, data.example_id)
    package = lap_handoff.historical(data, INPUT_COLUMNS, labels=labels, require_all=True)
    groups = chronological_split(data, package['races'])
    parts = {name: data[data.race_id.isin(ids)].copy() for name, ids in groups.items()}
    targets = labels.set_index('example_id').lap_time_actual_seconds
    examples = package['examples']
    for earlier, later in (('train', 'validation'), ('validation', 'test')):
        available = [utc(examples.loc[eid, 'target_available_at_utc'], 'Target availability') for eid in parts[earlier].example_id]
        if max(available) >= parts[later].prediction_time_utc.min():
            raise ValueError('Training/validation targets were not available before the next partition cutoff')
    initial = pipeline().fit(parts['train'][FEATURES], targets.loc[parts['train'].example_id].to_numpy())
    train_labels = labels[labels.example_id.isin(parts['train'].example_id)]
    validation = evaluate(parts['validation'], labels, initial, parts['train'], train_labels, examples)
    history = pd.concat([parts['train'], parts['validation']], ignore_index=True)
    history_labels = labels[labels.example_id.isin(history.example_id)]
    model = pipeline().fit(history[FEATURES], targets.loc[history.example_id].to_numpy())
    test = evaluate(parts['test'], labels, model, history, history_labels, examples)
    partitions = {name: {'race_ids': ids, 'races': len(ids), 'rows': len(parts[name]),
                         'sessions': int(parts[name].session_key.nunique()),
                         'start': min(package['races'][rid]['race_start_utc'] for rid in ids),
                         'end': max(package['races'][rid]['race_start_utc'] for rid in ids)} for name, ids in groups.items()}
    report = {'contract_version': CONTRACT_VERSION, 'task': 'lap_time', 'model_name': MODEL_NAME,
              'partitions': partitions, 'validation': validation, 'test': test,
              'evaluation_scope': 'M2-approved clean practice flying laps; not all laps or hypothetical scenarios'}
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    path = ARTIFACTS / 'linear_regression.joblib'
    joblib.dump(model, path)
    domains = _domains(model)
    metadata = {'contract_version': CONTRACT_VERSION, 'task': 'lap_time', 'model_name': MODEL_NAME,
                'scope': SCOPE, 'features': FEATURES, 'input_columns': INPUT_COLUMNS, 'output_columns': OUTPUT_COLUMNS,
                'model_version': 'lap-time-v2-' + sha256(path)[:16], 'versions': versions(),
                'training_handoff_ids': [package['handoff_id']], 'handoff_sha256': package['handoff_sha256'],
                'source_hashes': package['hashes'], 'partitions': partitions,
                'training_race_cutoff': partitions['validation']['end'],
                'preprocessing': {'categorical': 'one-hot, drop first sorted training category; unknowns rejected',
                                  'numeric': 'training-only StandardScaler; no missing-value imputation'},
                'supported_domains': domains,
                'category_training_counts': {c: {str(k): int(v) for k,v in history[c].value_counts().items()} for c in CATEGORICAL},
                'numeric_training_ranges': {c: {'min': float(history[c].min()), 'max': float(history[c].max())} for c in NUMERIC},
                'assumption_decisions': package['policy'], 'evaluation': report, 'random_seed': None,
                'artifact_sha256': sha256(path)}
    path.with_suffix('.json').write_text(json.dumps(metadata, indent=2, allow_nan=False), encoding='utf-8')
    (ARTIFACTS / 'evaluation.json').write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    # Historical public-API parity on supported test examples, with targets separate.
    supported = parts['test'][~parts['test'].example_id.isin(test['unsupported_rows'])].copy()
    if len(supported):
        supported.attrs = dict(data.attrs)
        pd.testing.assert_frame_equal(_score(supported, model, metadata), predict_lap_time(supported))
    return report
