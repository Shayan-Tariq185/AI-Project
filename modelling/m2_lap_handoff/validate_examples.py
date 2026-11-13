"""Read-only schema checks; no fetching, fitting, prediction or approval."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import pandas as pd
import lap_model


def main():
    package = Path(__file__).resolve().parent
    features = pd.read_csv(package / 'synthetic_features.csv')
    labels = pd.read_csv(package / 'synthetic_labels.csv')
    features.attrs['mode'] = 'historical'
    validated = lap_model.validate(features)
    lap_model.validate_labels(labels, validated.example_id)
    for column in ('example_id', 'race_id', 'driver_name', 'driver_id', 'circuit_id'):
        assert features[column].str.startswith('SYNTHETIC').all(), column
    assert len(features) == 3
    draft = json.loads((package / 'handoff.template.json').read_text())
    assert draft['approved_for_modeling'] is False
    assert draft['review_status'] == 'unresolved'
    assert all(draft['assumption_decisions'][key]['status'] == 'unresolved'
               for key in ('A1', 'A2', 'A3'))
    # Verify protected files captured before package creation remain unchanged.
    before = json.loads((package / 'protected_files_before.json').read_text(encoding='utf-8-sig'))
    for record in before:
        path = Path(record['path'])
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        assert actual == record['sha256'].lower(), f'Protected file changed: {path}'
    # Check relative Markdown links resolve without contacting external services.
    import re
    for document in package.glob('*.md'):
        for target in re.findall(r'\]\(([^)]+)\)', document.read_text(encoding='utf-8')):
            assert (document.parent / target).is_file(), f'Broken link: {target}'
    print(f'PASS: {len(features)} SYNTHETIC rows; exact input/target schemas and key matching.')
    print('PASS: unresolved template remains unapproved; local documentation links resolve.')
    print(f'PASS: {len(before)} protected source/contract/documentation/verification files unchanged.')
    print('No data fetched, models trained, predictions made or M2 approval granted.')


if __name__ == '__main__':
    main()
