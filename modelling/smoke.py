"""Offline contract smoke check on cached real entrants, without fitting a model."""
import json
import pandas as pd
import m3

def main():
    directory = m3.ROOT / 'data/2024_bahrain'
    raw_grid = json.loads((directory / 'raw/starting_grid_session_key-9468.json').read_text())
    assert len(raw_grid) == 20
    assert all(r['session_key'] == 9468 and r['meeting_key'] == 1229 for r in raw_grid)
    assert len({r['driver_number'] for r in raw_grid}) == 20
    assert {r['position'] for r in raw_grid} == set(range(1, 21))
    source_grid = {r['driver_number']: r['position'] for r in raw_grid}
    results = {'entrants': 20, 'grid_populated': 20,
               'grid_verification_scope': 'OpenF1 source/mapping integrity checked; explicit smoke-only attestation, M2 sign-off still required'}
    for stage in m3.STAGES:
        data = pd.read_csv(directory / f'{stage}_entrants.csv')
        assert len(data) == 20 and data.driver_number.is_unique
        if stage == 'post_grid':
            assert data.grid_position.notna().all()
            assert set(data.grid_position) == set(range(1, 21))
            assert dict(zip(data.driver_number, data.grid_position)) == source_grid
            # Explicit local attestation exercises the unchanged API requirement;
            # neither the CSV nor collector report is marked M2-approved.
            data.attrs['grid_verified'] = True
        m3.validate(data, stage)
        results[stage + '_contract'] = 'passed'
        field = 'grid_position' if stage == 'post_grid' else 'qualifying_position'
        results[stage + '_baseline_top_three'] = data.sort_values([field, 'driver_number']).head(3)[['driver_number', 'driver_name', field]].to_dict('records')
        try:
            m3.predict_podium(data, stage)
        except FileNotFoundError as exc:
            results[stage + '_prediction'] = {'expected_rejection': str(exc)}
        else:
            raise AssertionError('Unexpected production predictions from unreviewed single-race data')
    (m3.ROOT / 'data/2024_bahrain/smoke.json').write_text(json.dumps(results, indent=2))
    print(json.dumps(results, indent=2))

if __name__ == '__main__':
    main()
