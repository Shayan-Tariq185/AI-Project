"""Clearly synthetic fixtures for tests and smoke demos; never real M2 approval."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import lap_model
from lap_handoff import LINEAGE
from podium_handoff import sha256

ROOT = Path(__file__).resolve().parent


def create_dataset(directory, test_shift=0, unseen_test_circuit=False):
    directory = Path(directory).resolve()
    if not directory.is_relative_to(ROOT / '.test-work'):
        raise ValueError('Synthetic lap fixtures must stay under modelling/.test-work/')
    directory.mkdir(parents=True, exist_ok=False)
    rng = np.random.default_rng(42)
    rows, targets, examples, weather, drivers, circuits, races, lineage = [], [], [], [], [], [], [], []
    for i in range(10):
        rid, session = f'synthetic_lap_gp_{i}', 5000+i
        circuit = 'synthetic_circuit_A' if i % 2 == 0 else 'synthetic_circuit_B'
        if unseen_test_circuit and i >= 8:
            circuit = 'synthetic_unseen_circuit'
        race_start = f'2024-{i+1:02d}-03T14:00:00+00:00'
        base = pd.Timestamp(f'2024-{i+1:02d}-01T12:00:00+00:00')
        circuits.append(dict(race_id=rid, circuit_id=circuit, review_status='verified'))
        for driver in (1, 2):
            drivers.append(dict(race_id=rid, driver_id=f'synthetic_driver_{driver}',
                                driver_number=driver, driver_name=f'Synthetic Driver {driver}', review_status='verified'))
            for j, (compound, age) in enumerate((('SOFT', 2), ('SOFT', 8), ('MEDIUM', 2), ('MEDIUM', 8), ('HARD', 2), ('HARD', 8)), 1):
                eid = f'{rid}-D{driver}-L{j}'
                cutoff = base + pd.Timedelta(seconds=((driver-1)*6+j)*150)
                temperature = float(rng.uniform(28, 36)) + (test_shift if i >= 8 else 0)
                duration = 85 + {'SOFT': 0, 'MEDIUM': 1, 'HARD': 2}[compound] + .1*age + .05*(temperature-30) + (3 if i % 2 else 0) + (driver-1)
                observed = cutoff-pd.Timedelta(seconds=30)
                rows.append(dict(example_id=eid, race_id=rid, session_key=session,
                    driver_number=driver, driver_name=f'Synthetic Driver {driver}', driver_id=f'synthetic_driver_{driver}',
                    circuit_id=circuit, lap_number=j, prediction_time_utc=cutoff.isoformat(), compound=compound,
                    tyre_age_laps=age, track_temperature_c=temperature, weather_observed_at_utc=observed.isoformat()))
                targets.append(dict(example_id=eid, lap_time_actual_seconds=duration))
                end = cutoff+pd.Timedelta(seconds=duration)
                examples.append(dict(example_id=eid, session_name='Practice 3', clean_flying_lap_verified=True,
                    stint_lap_start=j, stint_lap_end=j, tyre_age_at_start=age,
                    lap_start_utc=cutoff.isoformat(), lap_end_utc=end.isoformat(),
                    target_available_at_utc=(end+pd.Timedelta(seconds=3)).isoformat(),
                    stint_available_at_utc=(cutoff-pd.Timedelta(seconds=1)).isoformat(), compound=compound))
                weather.append(dict(session_key=session, date=observed.isoformat(),
                                    available_at_utc=observed.isoformat(), track_temperature=temperature))
                for column in lap_model.INPUT_COLUMNS:
                    lineage.append(dict(task='lap_time', row_key=json.dumps({'example_id': eid}),
                        field_name=column, selected_source='derived', source_record_refs='PENDING',
                        derived_from='[]', observed_at_utc=observed.isoformat(), available_at_utc=observed.isoformat(),
                        retrieved_at_utc='2025-01-01T00:00:00+00:00', review_status='verified',
                        reviewer='SYNTHETIC TEST ONLY', reviewed_at_utc='2025-01-01T00:00:00+00:00',
                        resolution_notes='Synthetic fixture, not verification of a real lap'))
        races.append(dict(race_id=rid, race_start_utc=race_start,
                          source_session_keys={'practice': [session], 'race': 6000+i},
                          eligible_driver_ids=['synthetic_driver_1', 'synthetic_driver_2'],
                          prediction_cutoffs_utc={'historical_start': base.isoformat(),
                                                  'historical_end': (base+pd.Timedelta(hours=1)).isoformat()}))
    data = pd.DataFrame(rows, columns=lap_model.INPUT_COLUMNS)
    labels = pd.DataFrame(targets, columns=lap_model.LABEL_COLUMNS)
    data.to_csv(directory / 'features.csv', index=False)
    labels.to_csv(directory / 'labels.csv', index=False)
    pd.DataFrame(examples).to_csv(directory / 'examples.csv', index=False)
    pd.DataFrame(weather).to_csv(directory / 'weather.csv', index=False)
    pd.DataFrame(drivers).to_csv(directory / 'drivers.csv', index=False)
    pd.DataFrame(circuits).to_csv(directory / 'circuits.csv', index=False)
    (directory / 'quality.json').write_text(json.dumps({'unresolved_issues': [], 'scope_note': 'SYNTHETIC TEST ONLY - NOT A REAL M2 APPROVAL'}))
    refs = json.dumps([dict(source='derived', relative_path='features.csv', record_key='synthetic_fixture_only', sha256=sha256(directory / 'features.csv'))])
    for row in lineage:
        row['source_record_refs'] = refs
    pd.DataFrame(lineage, columns=LINEAGE).to_csv(directory / 'lineage.csv', index=False)
    records = []
    for name, role in [('features.csv', 'features'), ('labels.csv', 'labels'), ('examples.csv', 'metadata'),
                       ('weather.csv', 'metadata'), ('drivers.csv', 'crosswalk'), ('circuits.csv', 'crosswalk'),
                       ('quality.json', 'metadata'), ('lineage.csv', 'lineage')]:
        p = directory / name
        table = pd.DataFrame([json.loads(p.read_text())]) if p.suffix == '.json' else pd.read_csv(p)
        records.append(dict(role=role, relative_path=name, sha256=sha256(p), row_count=len(table), ordered_columns=list(table.columns)))
    policy = {'A1': {'status': 'verified', 'convention': 'completed_laps_before_target'},
              'A2': {'status': 'verified', 'max_age_seconds': 120, 'matching': 'latest_available_at_or_before_cutoff'},
              'A3': {'status': 'verified', 'scope': 'clean_normal_practice_flying_laps', 'supported_compounds': ['SOFT', 'MEDIUM', 'HARD']}}
    handoff = dict(handoff_id='SYNTHETIC-LAP-ONLY-'+directory.name, contract_version='2.0',
        task='lap_time', stage_or_mode='historical', files=records, races=races,
        lineage_path='lineage.csv', crosswalk_paths=['drivers.csv', 'circuits.csv'],
        quality_report_path='quality.json', assumption_decisions=policy,
        review_status='verified', reviewer='SYNTHETIC TEST ONLY', reviewed_at_utc='2025-01-01T00:00:00+00:00',
        approved_for_modeling=True)
    (directory / 'handoff.json').write_text(json.dumps(handoff, indent=2))
    context = {k:v for k,v in handoff.items() if k not in ('handoff_id', 'stage_or_mode', 'lineage_path')}
    context['context_id'] = 'SYNTHETIC-SCENARIO-ONLY-'+directory.name
    context['files'] = [r for r in records if r['relative_path'] in ('weather.csv', 'drivers.csv', 'circuits.csv', 'quality.json')]
    (directory / 'context.json').write_text(json.dumps(context, indent=2))
    data.attrs.update(mode='historical', m2_handoff_path=str(directory / 'handoff.json'))
    return data, labels


def scenario_input(directory, example_id='synthetic_scenario_1'):
    row = dict(example_id=example_id, race_id='synthetic_lap_gp_8', session_key=None,
        driver_number=1, driver_name='Synthetic Driver 1', driver_id='synthetic_driver_1',
        circuit_id='synthetic_circuit_A', lap_number=None, prediction_time_utc='2024-09-01T10:00:00+00:00',
        compound='SOFT', tyre_age_laps=5, track_temperature_c=30.0, weather_observed_at_utc=None)
    data = pd.DataFrame([row], columns=lap_model.INPUT_COLUMNS)
    data.attrs.update(mode='scenario', m2_context_path=str(Path(directory) / 'context.json'),
        scenario_provenance={example_id: {'compound': 'user_scenario', 'tyre_age_laps': 'user_scenario', 'track_temperature_c': 'user_scenario'}})
    return data
