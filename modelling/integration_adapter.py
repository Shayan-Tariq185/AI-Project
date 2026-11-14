"""Explicit dashboard translations; public M3 inference remains authoritative.

Import with modelling/ on sys.path (the existing M3 module layout).
No inference fallback, training, evidence creation or artifact writes occur here.
"""
from dataclasses import dataclass
import json
from pathlib import Path
from math import isfinite
from numbers import Integral, Real

import pandas as pd

from f1_dashboard.contracts import RaceInputs, validate_inputs
from f1_dashboard.predictions import LapEstimate
import m3
import lap_model
import lap_handoff
import podium_handoff


@dataclass(frozen=True)
class PodiumContext:
    handoff_path: str
    # Exact columns: dashboard_driver_id, driver_id, driver_number,
    # qualifying_position. driver_id is the reviewed canonical M2 ID.
    drivers: pd.DataFrame
    qualifying_air_temp_c: float | None
    qualifying_gap_definition: str
    practice_gap_definition: str
    reviewer: str
    reviewed_at_utc: str
    grid_verified: bool = False


@dataclass(frozen=True)
class PodiumResult:
    picks: list[str]
    model_version: str
    evidence: dict


@dataclass(frozen=True)
class LapContext:
    # All ten non-scalar M3 columns, including explicit nullable fields.
    row: dict
    mode: str
    evidence_path: str
    scenario_provenance: dict | None
    circuit_display_name: str
    tyre_age_convention: str


@dataclass(frozen=True)
class LapResult:
    estimate: LapEstimate
    is_hypothetical: bool
    support_status: str
    evidence: dict
    artifact_metadata: dict


def _review(context):
    if not isinstance(context.reviewer, str) or not context.reviewer.strip():
        raise ValueError('Supplementary translation context requires a reviewer')
    podium_handoff.utc(context.reviewed_at_utc, 'Translation review time')
    if context.qualifying_gap_definition != 'best_valid_all_segments_minus_session_best_seconds':
        raise ValueError('Reviewed qualifying delta meaning is required')
    if context.practice_gap_definition != 'best_valid_selected_common_practice_minus_session_best_seconds':
        raise ValueError('Reviewed practice delta meaning is required')


def _podium_frame(inputs, include_grid, context):
    if not isinstance(inputs, RaceInputs) or type(include_grid) is not bool or not isinstance(context, PodiumContext):
        raise ValueError('RaceInputs, boolean include_grid and PodiumContext are required')
    try:
        validate_inputs(inputs, include_grid)
    except (TypeError, AttributeError) as exc:
        raise ValueError('Invalid dashboard request field types') from exc
    numeric = [inputs.qualifying_track_temp_c, context.qualifying_air_temp_c]
    for driver in inputs.drivers:
        numeric.extend([driver.qualifying_delta_s, driver.practice_delta_s])
    if any(pd.api.types.is_bool(value) for value in numeric):
        raise ValueError('Dashboard pace and temperature fields cannot be booleans')
    _review(context)
    columns = ['dashboard_driver_id', 'driver_id', 'driver_number', 'qualifying_position']
    identities = context.drivers
    if not isinstance(identities, pd.DataFrame) or list(identities.columns) != columns:
        raise ValueError(f'Supplementary drivers require exactly {columns}')
    for column in columns[:3]:
        if identities[column].isna().any() or identities[column].duplicated().any():
            raise ValueError(f'Missing or ambiguous identity mapping: {column}')
    for column in columns[:2]:
        if not identities[column].map(lambda x: isinstance(x, str) and bool(x.strip())).all():
            raise ValueError(f'Invalid identity mapping: {column}')
    for column in ('driver_number', 'qualifying_position'):
        if identities[column].map(pd.api.types.is_bool).any():
            raise ValueError(f'{column} cannot contain booleans')
    if not identities.driver_number.map(lambda v: isinstance(v, Integral) and v > 0).all():
        raise ValueError('Supplementary driver_number must be a positive integer')
    if set(identities.dashboard_driver_id) != {d.driver_id for d in inputs.drivers}:
        raise ValueError('Supplementary identities must cover exactly the dashboard field')
    stage = 'post_grid' if include_grid else 'post_qualifying'
    mapping = identities.set_index('dashboard_driver_id')
    rows = []
    for driver in inputs.drivers:
        identity = mapping.loc[driver.driver_id]
        rows.append(dict(race_id=inputs.race.race_id, driver_number=identity.driver_number,
                         driver_name=driver.name, qualifying_position=identity.qualifying_position,
                         qualifying_gap_seconds=driver.qualifying_delta_s,
                         practice_gap_seconds=driver.practice_delta_s,
                         qualifying_air_temp_c=context.qualifying_air_temp_c,
                         qualifying_track_temp_c=inputs.qualifying_track_temp_c,
                         qualifying_rainfall=int(inputs.qualifying_rainfall),
                         **({'grid_position': driver.grid_position} if include_grid else {})))
    data = pd.DataFrame(rows, columns=['race_id', 'driver_number', 'driver_name'] + m3.features(stage))
    data.attrs['m2_handoff_path'] = context.handoff_path
    data.attrs['grid_verified'] = context.grid_verified
    m3.validate(data, stage)
    evidence = podium_handoff.verify(data, stage, m3.features(stage))
    # The feature verifier checks driver numbers; also bind dashboard IDs to the
    # actual canonical identities in the hashed crosswalk, never row order.
    path = Path(context.handoff_path).resolve()
    manifest = json.loads(path.read_text(encoding='utf-8-sig'))
    race = next(r for r in manifest['races'] if r['race_id'] == inputs.race.race_id)
    if (podium_handoff.utc(race['race_start_utc'], 'Reviewed race start') != podium_handoff.utc(inputs.race.start_utc, 'Dashboard race start')
            or podium_handoff.utc(race['prediction_cutoffs_utc'][stage], 'Reviewed cutoff') != podium_handoff.utc(inputs.cutoff_utc, 'Dashboard cutoff')):
        raise ValueError('Dashboard race start/cutoff must match reviewed M2 context')
    def read_crosswalk(relative):
        source = path.parent / relative
        if source.suffix.lower() == '.json':
            value = json.loads(source.read_text(encoding='utf-8-sig'))
            return pd.DataFrame(value if isinstance(value, list) else [value])
        return pd.read_csv(source)
    tables = [read_crosswalk(p) for p in manifest['crosswalk_paths']]
    crosswalk = pd.concat([t for t in tables if {'race_id', 'driver_number', 'driver_id'}.issubset(t)], ignore_index=True)
    approved = crosswalk[crosswalk.race_id == inputs.race.race_id].set_index('driver_number').driver_id.to_dict()
    if any(approved.get(r.driver_number) != r.driver_id for r in identities.itertuples()):
        raise ValueError('Supplementary driver identities disagree with reviewed M2 crosswalk')
    return data, stage, evidence


def predict_podium(inputs: RaceInputs, include_grid: bool = False, *, context: PodiumContext) -> PodiumResult:
    """Return three dashboard IDs plus metadata required for truthful snapshots."""
    data, stage, evidence = _podium_frame(inputs, include_grid, context)
    output = m3.predict_podium(data, stage)
    columns = ['race_id', 'driver_number', 'driver_name', 'podium_probability',
               'predicted_rank', 'is_podium_pick', 'stage', 'model_name']
    if not isinstance(output, pd.DataFrame) or list(output.columns) != columns or len(output) != len(data):
        raise ValueError('Incomplete or invalid M3 podium result schema')
    if (output.driver_number.duplicated().any() or set(output.driver_number) != set(data.driver_number)
            or not output.driver_number.map(lambda v: isinstance(v, Integral) and not isinstance(v, bool)).all()
            or not output.race_id.eq(inputs.race.race_id).all() or not output.stage.eq(stage).all()
            or not output.model_name.eq('random_forest').all()
            or not output.is_podium_pick.map(lambda v: type(v) is bool).all()
            or not output.predicted_rank.map(lambda v: isinstance(v, Integral) and not isinstance(v, bool)).all()
            or sorted(output.predicted_rank) != list(range(1, len(data) + 1))
            or not output.is_podium_pick.eq(output.predicted_rank <= 3).all()
            or not output.podium_probability.map(lambda v: isinstance(v, Real)
                and not pd.api.types.is_bool(v) and isfinite(v) and 0 <= v <= 1).all()):
        raise ValueError('Invalid or ambiguous M3 podium result rows')
    expected = data.set_index('driver_number').driver_name.to_dict()
    if any(expected[r.driver_number] != r.driver_name for r in output.itertuples()):
        raise ValueError('M3 result driver names disagree with request')
    ordered = output.sort_values(['podium_probability', 'driver_number'], ascending=[False, True])
    if ordered.predicted_rank.tolist() != list(range(1, len(data) + 1)):
        raise ValueError('M3 ranks disagree with probability ordering and tie policy')
    lookup = context.drivers.set_index('driver_number').dashboard_driver_id.to_dict()
    picks = [lookup[n] for n in output.loc[output.is_podium_pick, 'driver_number']]
    if len(picks) != 3 or len(set(picks)) != 3:
        raise ValueError('M3 must return exactly three unique podium picks')
    names = {d.driver_id: d.name for d in inputs.drivers}
    metadata = m3._metadata(m3.ARTIFACTS / f'{stage}.joblib', stage)
    return PodiumResult(sorted(picks, key=lambda p: (names[p], p)), metadata['model_version'], evidence)


def estimate_lap(circuit: str, compound: str, tire_age_laps: int, track_temp_c: float,
                 *, context: LapContext) -> LapResult:
    """Four scalar values are insufficient without explicit reviewed lap context."""
    if not isinstance(context, LapContext):
        raise ValueError('Explicit LapContext is required')
    if context.mode == 'historical' and context.scenario_provenance is not None:
        raise ValueError('Historical requests must not carry scenario provenance')
    if circuit != context.circuit_display_name or not isinstance(circuit, str) or not circuit.strip():
        raise ValueError('Circuit display name must match explicit circuit context')
    if context.tyre_age_convention != 'completed_laps_before_target':
        raise ValueError('Explicit completed-laps tire-age convention is required')
    scalar_columns = {'compound', 'tyre_age_laps', 'track_temperature_c'}
    required = set(lap_model.INPUT_COLUMNS) - scalar_columns
    if not isinstance(context.row, dict) or set(context.row) != required:
        raise ValueError(f'Lap context row requires exactly {sorted(required)}')
    row = dict(context.row, compound=compound, tyre_age_laps=tire_age_laps, track_temperature_c=track_temp_c)
    data = pd.DataFrame([row], columns=lap_model.INPUT_COLUMNS)
    data.attrs['mode'] = context.mode
    key = 'm2_handoff_path' if context.mode == 'historical' else 'm2_context_path'
    data.attrs[key] = context.evidence_path
    data.attrs['scenario_provenance'] = context.scenario_provenance
    data = lap_model.validate(data)
    package = (lap_handoff.historical(data, lap_model.INPUT_COLUMNS) if context.mode == 'historical'
               else lap_handoff.scenario(data))
    output = lap_model.predict_lap_time(data)
    if not isinstance(output, pd.DataFrame) or list(output.columns) != lap_model.OUTPUT_COLUMNS or len(output) != 1:
        raise ValueError('Incomplete or invalid M3 lap result schema')
    result = output.iloc[0]
    for column in ('example_id', 'race_id', 'driver_id', 'driver_number', 'driver_name', 'lap_number', 'prediction_time_utc'):
        expected = data.iloc[0][column]
        actual = result[column]
        if not ((pd.isna(expected) and pd.isna(actual)) or actual == expected):
            raise ValueError(f'M3 lap result context mismatch: {column}')
    if (result['mode'] != context.mode or result.model_name != 'linear_regression'
            or not pd.api.types.is_bool(result.is_hypothetical)
            or result.is_hypothetical != (context.mode == 'scenario')
            or result.support_status not in ('numeric_extrapolation', 'within_training_numeric_ranges')
            or not isinstance(result.predicted_lap_time_seconds, Real)
            or pd.api.types.is_bool(result.predicted_lap_time_seconds)
            or not isfinite(result.predicted_lap_time_seconds) or result.predicted_lap_time_seconds <= 0):
        raise ValueError('Invalid M3 lap result status or prediction')
    metadata = lap_model._metadata(lap_model.ARTIFACTS / 'linear_regression.joblib')
    if result.model_version != metadata['model_version']:
        raise ValueError('Lap result and artifact versions disagree')
    # No unscoped metric is guessed from a partially supported held-out set.
    return LapResult(LapEstimate(float(result.predicted_lap_time_seconds), None, result.model_version),
                     bool(result.is_hypothetical), result.support_status,
                     {'handoff_id': package['handoff_id'], 'handoff_sha256': package['handoff_sha256'],
                      'source_hashes': package['hashes']}, metadata)
