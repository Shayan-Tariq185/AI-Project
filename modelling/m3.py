"""Contract-v2 Random Forest podium API. Load only trusted local artifacts."""
from pathlib import Path
import json
import platform
import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import precision_score, recall_score, average_precision_score, brier_score_loss
from podium_handoff import verify as verify_handoff, sha256, utc

ROOT = Path(__file__).resolve().parent
LEGACY_ARTIFACTS = ROOT / 'artifacts'
ARTIFACTS = LEGACY_ARTIFACTS / 'v2' / 'podium'
CONTRACT_VERSION = '2.0'
MODEL_NAME = 'random_forest'
BASE = ['qualifying_position', 'qualifying_gap_seconds', 'practice_gap_seconds',
        'qualifying_air_temp_c', 'qualifying_track_temp_c', 'qualifying_rainfall']
STAGES = ('post_qualifying', 'post_grid')
TARGET = 'is_podium_actual'
FOREST_PARAMETERS = dict(n_estimators=200, max_depth=4, min_samples_leaf=3, random_state=42, n_jobs=1)


class ArtifactCompatibilityError(ValueError):
    """The artifact is not a compatible contract-v2 podium Random Forest."""


def features(stage):
    if stage not in STAGES:
        raise ValueError(f'invalid stage: {stage!r}')
    return BASE + (['grid_position'] if stage == 'post_grid' else [])


def validate(data, stage):
    cols = features(stage)
    missing = set(['race_id', 'driver_number', 'driver_name'] + cols) - set(data.columns)
    if missing:
        raise ValueError(f'missing required columns: {sorted(missing)}')
    if len(data) < 3 or data.race_id.nunique(dropna=False) != 1:
        raise ValueError('expected one race with at least three entrants')
    d = data.copy()
    for c in ('race_id', 'driver_name'):
        if not d[c].map(lambda v: isinstance(v, str) and bool(v.strip())).all():
            raise ValueError(f'{c} must contain nonempty strings')
    for c in cols + ['driver_number']:
        try:
            n = pd.to_numeric(d[c], errors='raise').astype(float)
        except (ValueError, TypeError) as exc:
            raise ValueError(f'{c} must be numeric') from exc
        if np.isinf(n).any():
            raise ValueError(f'{c} must be finite or null')
        if c in ('driver_number', 'qualifying_position', 'grid_position', 'qualifying_rainfall'):
            if ((n.dropna() % 1) != 0).any():
                raise ValueError(f'{c} must be integer')
        if c in ('driver_number', 'qualifying_position', 'grid_position') and (n.dropna() < 1).any():
            raise ValueError(f'{c} must be positive')
        if c.endswith('gap_seconds') and (n.dropna() < 0).any():
            raise ValueError(f'{c} must be nonnegative')
        if c == 'qualifying_rainfall' and not n.dropna().isin([0, 1]).all():
            raise ValueError('qualifying_rainfall must be 0, 1 or null')
        d[c] = n
    if d.driver_number.isna().any() or d.driver_number.duplicated().any():
        raise ValueError('driver_number must be present and unique')
    if stage == 'post_grid':
        if d.grid_position.isna().any():
            raise ValueError('post_grid requires verified grid positions for every starter')
        if d.grid_position.duplicated().any():
            raise ValueError('post_grid requires unique grid positions')
        if data.attrs.get('grid_verified') is not True:
            raise ValueError('post_grid requires DataFrame.attrs[grid_verified] = True from M2')
    for c in ('qualifying_air_temp_c', 'qualifying_track_temp_c', 'qualifying_rainfall'):
        if d[c].nunique(dropna=False) > 1:
            raise ValueError(f'{c} must be shared across the race')
    return d


def pipeline(stage, name=MODEL_NAME):
    if name != MODEL_NAME:
        raise ValueError('Only random_forest is supported for podium prediction in contract 2.0')
    numeric = Pipeline([('impute', SimpleImputer(strategy='median', keep_empty_features=True))])
    return Pipeline([
        ('preprocess', ColumnTransformer([('numeric', numeric, features(stage))], remainder='drop')),
        ('model', RandomForestClassifier(**FOREST_PARAMETERS))])


def score(data, stage, model, name=MODEL_NAME):
    if name != MODEL_NAME:
        raise ValueError('Only random_forest may label podium output')
    d = validate(data, stage)
    p = model.predict_proba(d[features(stage)])[:, list(model.classes_).index(1)]
    if not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
        raise ValueError('Invalid podium probabilities from model')
    out = d[['race_id', 'driver_number', 'driver_name']].copy()
    out['driver_number'] = out.driver_number.astype(int)
    out['podium_probability'] = p
    out = out.sort_values(['podium_probability', 'driver_number'], ascending=[False, True]).reset_index(drop=True)
    out['predicted_rank'] = np.arange(1, len(out) + 1)
    out['is_podium_pick'] = out.predicted_rank <= 3
    out['stage'] = stage
    out['model_name'] = MODEL_NAME
    return out


def versions():
    return {'python': platform.python_version(), 'sklearn': sklearn.__version__,
            'pandas': pd.__version__, 'numpy': np.__version__, 'joblib': joblib.__version__}


def _metadata(path, stage):
    try:
        meta = json.loads(path.with_suffix('.json').read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise ArtifactCompatibilityError('Incompatible artifact: missing or malformed v2 metadata; no model was loaded') from exc
    expected = {'contract_version': CONTRACT_VERSION, 'task': 'podium', 'model_name': MODEL_NAME,
                'stage': stage, 'stage_or_scope': stage, 'features': features(stage)}
    required = {'model_version', 'training_race_cutoff', 'versions', 'training_handoff_ids',
                'source_hashes', 'partitions', 'preprocessing', 'numeric_training_ranges',
                'assumption_decisions', 'evaluation', 'random_seed', 'artifact_sha256'}
    if not isinstance(meta, dict) or any(meta.get(k) != v for k, v in expected.items()) or required - set(meta):
        raise ArtifactCompatibilityError('Incompatible artifact: expected contract 2.0, task podium, random_forest and matching stage/features')
    current = versions()
    if (not isinstance(meta['versions'], dict) or
            any(meta['versions'].get(k) != v for k, v in current.items() if k != 'python') or
            str(meta['versions'].get('python', '')).split('.')[:2] != current['python'].split('.')[:2]):
        raise ArtifactCompatibilityError('Incompatible artifact library/Python versions; retraining in the pinned environment is required')
    if not isinstance(meta['model_version'], str) or not meta['model_version']:
        raise ArtifactCompatibilityError('Incompatible artifact: model_version is missing')
    if sha256(path) != meta['artifact_sha256']:
        raise ArtifactCompatibilityError('Incompatible artifact: saved pipeline hash mismatch')
    return meta


def _load_model(path, stage):
    try:
        model = joblib.load(path)
    except Exception as exc:
        raise ArtifactCompatibilityError('Incompatible artifact: pipeline cannot be deserialized') from exc
    if (not isinstance(model, Pipeline) or
            not isinstance(model.named_steps.get('model'), RandomForestClassifier) or
            not isinstance(model.named_steps.get('preprocess'), ColumnTransformer) or
            list(getattr(model, 'classes_', [])) != [0, 1] or
            list(getattr(model, 'feature_names_in_', [])) != features(stage)):
        raise ArtifactCompatibilityError('Incompatible artifact: expected fitted RandomForestClassifier pipeline and matching input schema')
    preprocess = model.named_steps['preprocess']
    transformers = preprocess.transformers
    numeric = preprocess.named_transformers_.get('numeric')
    if (len(transformers) != 1 or list(transformers[0][2]) != features(stage)
            or not isinstance(numeric, Pipeline) or list(numeric.named_steps) != ['impute']
            or not isinstance(numeric.named_steps['impute'], SimpleImputer)
            or numeric.named_steps['impute'].strategy != 'median'):
        raise ArtifactCompatibilityError('Incompatible artifact preprocessing feature schema')
    return model


def predict_podium(race_data: pd.DataFrame, stage: str) -> pd.DataFrame:
    forbidden = {TARGET, 'finishing_position', 'race_result', 'race_position', 'points', 'lap_time_actual_seconds'} & set(race_data.columns)
    if forbidden:
        raise ValueError(f'post-race fields are forbidden at inference: {sorted(forbidden)}')
    validate(race_data, stage)
    path = ARTIFACTS / f'{stage}.joblib'
    if not path.exists():
        if (LEGACY_ARTIFACTS / f'{stage}.joblib').exists():
            raise ArtifactCompatibilityError('Incompatible legacy artifact found: v1 models are not loaded or converted; a reviewed v2 Random Forest artifact is required')
        raise FileNotFoundError(f'No trained artifact: {path}. Train on reviewed historical races first.')
    _metadata(path, stage)  # Reject legacy metadata before deserializing a pickle.
    verify_handoff(race_data, stage, features(stage))
    return score(race_data, stage, _load_model(path, stage))


def _race(data, race):
    race = race.copy()
    race.attrs = dict(data.attrs)
    return race


def evaluate(data, stage, model, name=MODEL_NAME):
    hits, baseline, misses, actuals, predictions, probabilities = [], [], [], [], [], []
    missing_baselines = []
    for race_id, group in data.groupby('race_id', sort=False):
        race = _race(data, group)
        out = score(race.drop(columns=[TARGET]), stage, model, name)
        truth = set(race.loc[race[TARGET] == 1, 'driver_number'])
        picks = set(out.head(3).driver_number)
        field = 'grid_position' if stage == 'post_grid' else 'qualifying_position'
        known = race.dropna(subset=[field]).sort_values([field, 'driver_number'])
        if len(known) >= 3:
            base = set(known.head(3).driver_number)
            baseline.append(len(base & truth))
        else:
            missing_baselines.append(race_id)
        hits.append(len(picks & truth))
        if picks != truth:
            misses.append({'race_id': race_id, 'picked': sorted(picks), 'actual': sorted(truth)})
        actuals.extend(race[TARGET])
        predictions.extend(race.driver_number.isin(picks).astype(int))
        probabilities.extend(out.set_index('driver_number').loc[race.driver_number, 'podium_probability'])
    if not hits:
        raise ValueError('evaluation requires at least one complete race')
    threshold_picks = np.asarray(probabilities) >= 0.5
    return {'mean_correct_picks': float(np.mean(hits)), 'exact_set_rate': float(np.mean(np.array(hits) == 3)),
            'baseline_mean_correct_picks': float(np.mean(baseline)) if baseline else None,
            'baseline_exact_set_rate': float(np.mean(np.array(baseline) == 3)) if baseline else None,
            'baseline_races': len(baseline), 'baseline_unavailable_races': missing_baselines,
            'precision': precision_score(actuals, predictions, zero_division=0),
            'recall': recall_score(actuals, predictions, zero_division=0),
            'classification_threshold': 0.5,
            'threshold_precision': precision_score(actuals, threshold_picks, zero_division=0),
            'threshold_recall': recall_score(actuals, threshold_picks, zero_division=0),
            'average_precision': average_precision_score(actuals, probabilities),
            'brier_score': brier_score_loss(actuals, probabilities),
            'first_miss': misses[0] if misses else None}


def _fit(data, stage):
    empty = [c for c in features(stage) if data[c].isna().all()]
    if empty:
        raise ValueError(f'all-null training features require an explicit modeling decision: {empty}')
    return pipeline(stage).fit(data[features(stage)], data[TARGET])


def train(data, grid_verified=False):
    """Train two fixed Random Forests on approved handoffs; never tune on test."""
    if not {'race_id', 'race_date', TARGET}.issubset(data.columns):
        raise ValueError('training requires race_id, race_date and is_podium_actual')
    if not data[TARGET].isin([0, 1]).all():
        raise ValueError('ambiguous target: send to M2 review')
    for _, race in data.groupby('race_id'):
        if race.race_date.nunique() != 1 or race[TARGET].sum() != 3:
            raise ValueError('each complete race requires one date and exactly three actual podium drivers')
    dates = data.race_date.map(lambda value: utc(value, 'race_date'))
    order = data.assign(_date=dates).groupby('race_id')._date.first().sort_values()
    if len(order) < 10:
        raise ValueError('at least ten reviewed races required; one race is smoke-only')
    a, b = int(len(order)*.6), int(len(order)*.8)
    groups = [order.iloc[:a], order.iloc[a:b], order.iloc[b:]]
    if not groups[0].max() < groups[1].min() or not groups[1].max() < groups[2].min():
        raise ValueError('partition boundaries must be strictly chronological')
    reviewed = data.copy()
    reviewed.attrs['grid_verified'] = grid_verified
    handoffs = {}
    # Complete review/schema checks for both stages before fitting/writing anything.
    for stage in STAGES:
        for _, group in reviewed.groupby('race_id'):
            validate(_race(reviewed, group), stage)
        handoffs[stage] = verify_handoff(reviewed, stage, features(stage), training=True)
        initial = reviewed[reviewed.race_id.isin(groups[0].index)]
        empty = [c for c in features(stage) if initial[c].isna().all()]
        if empty:
            raise ValueError(f'all-null training features require an explicit modeling decision: {empty}')
    report = {'contract_version': CONTRACT_VERSION, 'task': 'podium', 'model_name': MODEL_NAME,
              'partitions': {k: {'races': len(g), 'race_ids': list(g.index),
                                 'start': str(g.min()), 'end': str(g.max())}
                             for k, g in zip(['train', 'validation', 'test'], groups)}}
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    for stage in STAGES:
        parts = [_race(reviewed, reviewed[reviewed.race_id.isin(g.index)]) for g in groups]
        initial = _fit(parts[0], stage)
        validation_metrics = evaluate(parts[1], stage, initial)
        history = _race(reviewed, pd.concat(parts[:2]))
        model = _fit(history, stage)
        test_metrics = evaluate(parts[2], stage, model)
        evaluation = {'model_name': MODEL_NAME, 'validation': validation_metrics, 'test': test_metrics}
        path = ARTIFACTS / f'{stage}.joblib'
        joblib.dump(model, path)
        handoff = handoffs[stage]
        model_version = f'podium-{stage}-v2-{sha256(path)[:16]}'
        meta = {'contract_version': CONTRACT_VERSION, 'task': 'podium', 'stage': stage,
                'stage_or_scope': stage, 'model_name': MODEL_NAME, 'model_version': model_version,
                'features': features(stage), 'training_race_cutoff': str(groups[1].max()),
                'versions': versions(), 'partitions': report['partitions'],
                'training_handoff_ids': [handoff['handoff_id']],
                'source_hashes': handoff['source_hashes'], 'handoff_sha256': handoff['handoff_sha256'],
                'assumption_decisions': handoff['assumption_decisions'],
                'preprocessing': {'numeric': 'training-only median imputation', 'scaling': None,
                                  'categorical_features': []},
                'supported_domains': {'circuit': None, 'driver': None, 'compound': None},
                'numeric_training_ranges': {c: {'min': float(history[c].min()), 'max': float(history[c].max())} for c in features(stage)},
                'forest_parameters': FOREST_PARAMETERS, 'random_seed': 42,
                'evaluation': evaluation, 'artifact_sha256': sha256(path)}
        path.with_suffix('.json').write_text(json.dumps(meta, indent=2, allow_nan=False), encoding='utf-8')
        report[stage] = evaluation
        for _, group in parts[2].groupby('race_id'):
            race = _race(reviewed, group).drop(columns=[TARGET])
            pd.testing.assert_frame_equal(score(race, stage, model), predict_podium(race, stage))
    (ARTIFACTS / 'evaluation.json').write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    return report


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Train contract-v2 podium Random Forests from M2-approved history')
    parser.add_argument('csv', help='Training-workflow table including race_date and separate-label join')
    parser.add_argument('--grid-verified', action='store_true', help='Explicit M2 grid attestation; approved hashed handoffs are also required')
    parser.add_argument('--post-qualifying-handoff', required=True)
    parser.add_argument('--post-grid-handoff', required=True)
    args = parser.parse_args()
    data = pd.read_csv(args.csv)
    data.attrs['m2_handoffs'] = {'post_qualifying': args.post_qualifying_handoff, 'post_grid': args.post_grid_handoff}
    print(json.dumps(train(data, args.grid_verified), indent=2))
