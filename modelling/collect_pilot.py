"""Fixed five-race 2024 OpenF1 pilot. Draft data only; never trains models."""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import pandas as pd
from openf1_prototype import ROOT, Client, build, stage_tables, IDENTITY
from m3 import BASE, validate

COUNTRIES = ('Bahrain', 'Saudi Arabia', 'Australia', 'Japan', 'China')
KEYS = ['race_id', 'driver_number']
LABEL_COLUMNS = KEYS + ['is_podium_actual']

def classification_labels(data, results):
    """Join labels by race/driver key only; ambiguous or absent results stay null."""
    indexed = {}
    for row in results:
        indexed.setdefault(row['driver_number'], []).append(row)
    labels, issues = [], []
    for number in data.driver_number:
        rows = indexed.get(number, [])
        target = None
        if len(rows) != 1:
            issues.append({'driver_number': int(number), 'reason': 'missing or duplicate race classification'})
        else:
            row = rows[0]
            flags = [row.get(k) for k in ('dnf', 'dns', 'dsq')]
            position = row.get('position')
            if not all(isinstance(v, bool) for v in flags):
                issues.append({'driver_number': int(number), 'reason': 'ambiguous result status'})
            elif any(flags):
                target = 0
            elif isinstance(position, int) and not isinstance(position, bool) and position > 0:
                target = int(position <= 3)
            else:
                issues.append({'driver_number': int(number), 'reason': 'ambiguous finishing classification'})
        labels.append({'race_id': data.race_id.iloc[0], 'driver_number': int(number), 'is_podium_actual': target})
    table = pd.DataFrame(labels, columns=LABEL_COLUMNS)
    table['is_podium_actual'] = table.is_podium_actual.astype('Int64')
    return table, issues

def lap_quality(laps, control):
    rejected = {'pit_out_or_unknown': 0, 'invalid_or_missing_duration': 0, 'incomplete_sectors': 0}
    accepted = set()
    for lap in laps:
        duration = lap.get('lap_duration')
        if lap.get('is_pit_out_lap') is not False:
            rejected['pit_out_or_unknown'] += 1
        elif not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration <= 0:
            rejected['invalid_or_missing_duration'] += 1
        elif not all(isinstance(lap.get(f'duration_sector_{i}'), (int, float)) and math.isfinite(lap[f'duration_sector_{i}']) and lap[f'duration_sector_{i}'] > 0 for i in (1, 2, 3)):
            rejected['incomplete_sectors'] += 1
        else:
            accepted.add(lap['driver_number'])
    messages = [r for r in control if 'DELETED' in str(r.get('message', '')).upper() or 'REINSTATED' in str(r.get('message', '')).upper()]
    return {'raw_laps': len(laps), 'provisional_valid_driver_numbers': sorted(accepted),
            'rejected_laps': rejected, 'lap_deletion_or_reinstatement_messages': messages,
            'fully_verified': False,
            'review_required': 'Pit-in/deleted/reinstated lap validity must be reviewed by M2; provisional filter is not official validity.'}

def cached(client, endpoint, session):
    if session is None:
        return []
    path = client.directory / f'{endpoint}_session_key-{session["session_key"]}.json'
    return json.loads(path.read_text()) if path.exists() else []

def race_quality(client, data, report):
    q, race, practice = report['qualifying_session'], report['race_session'], report['practice_session']
    results = cached(client, 'session_result', race)
    labels, label_issues = classification_labels(data, results)
    tables = stage_tables(data)
    numbers = set(data.driver_number)
    sources = {'qualifying_classification': cached(client, 'session_result', q),
               'qualifying_laps': cached(client, 'laps', q),
               'practice_laps': cached(client, 'laps', practice),
               'starting_grid': cached(client, 'starting_grid', q), 'race_classification': results}
    identities = []
    if practice:
        practice_drivers = client.get('drivers', session_key=practice['session_key'])
        by_number = {}
        for row in practice_drivers:
            by_number.setdefault(row['driver_number'], []).append(row)
        for row in data.to_dict('records'):
            matches = by_number.get(row['driver_number'], [])
            if len(matches) != 1:
                identities.append({'driver_number': row['driver_number'], 'reason': 'absent or duplicate practice roster identity'})
            elif str(matches[0].get('full_name', '')).strip().casefold() != str(row['driver_name']).strip().casefold():
                identities.append({'driver_number': row['driver_number'], 'reason': 'practice/qualifying name mismatch'})
        practice_control = client.get('race_control', session_key=practice['session_key'])
    else:
        practice_control = []
    coverage = {}
    for source, rows in sources.items():
        ids = [r['driver_number'] for r in rows]
        unique = set(ids)
        coverage[source] = {'rows': len(rows), 'unique_drivers': len(unique),
                            'missing_entrant_drivers': sorted(numbers - unique),
                            'source_only_drivers': sorted(unique - numbers)}
        if source in ('qualifying_classification', 'starting_grid', 'race_classification'):
            coverage[source]['duplicate_drivers'] = sorted({n for n in ids if ids.count(n) > 1})
    checks = {}
    for stage, table in tables.items():
        try:
            # Contract shape/value smoke only, not an M2 approval.
            table.attrs['grid_verified'] = True
            validate(table, stage)
            checks[stage] = 'passed_with_smoke_only_grid_attestation' if stage == 'post_grid' else 'passed'
        except ValueError as exc:
            checks[stage] = str(exc)
    report.update({'requires_M2_verification': True, 'M2_approved': False,
                   'missing_by_feature': {c: int(data[c].isna().sum()) for c in BASE + ['grid_position']},
                   'duplicate_feature_driver_rows': int(data.duplicated(KEYS).sum()),
                   'source_coverage': coverage, 'identity_review': identities,
                   'race_completed': datetime.fromisoformat(race['date_end']) < datetime.now(timezone.utc),
                   'label_issues': label_issues, 'labels_missing': int(labels.is_podium_actual.isna().sum()),
                   'podium_label_count': int(labels.is_podium_actual.sum()),
                   'contract_smoke_checks': checks,
                   'lap_quality': {'qualifying': lap_quality(sources['qualifying_laps'], cached(client, 'race_control', q)),
                                   'practice': lap_quality(sources['practice_laps'], practice_control)},
                   'forecast_cutoffs': {'post_qualifying': q['date_end'], 'post_grid': None},
                   'cutoff_review': 'Post-qualifying uses intended session-end cutoff; historical publication timing is unverified. Post-grid publication cutoff unknown; M2 must supply it.'})
    classification = coverage['race_classification']
    report['classification_coverage_complete'] = not (classification['missing_entrant_drivers'] or classification['source_only_drivers'] or classification['duplicate_drivers'] or label_issues)
    report['collection_complete'] = bool(len(data) >= 3 and report['race_completed'] and
        report['classification_coverage_complete'] and report['podium_label_count'] == 3 and
        report['grid_integrity']['populated'] == len(data) and
        checks['post_qualifying'] == 'passed' and checks['post_grid'] == 'passed_with_smoke_only_grid_attestation' and
        not identities and
        not report['duplicate_feature_driver_rows'] and not any('error' in c for c in client.calls))
    report['collection_status'] = 'collected_draft_requires_M2' if report['collection_complete'] else 'incomplete_requires_M2'
    report['requests'] = client.calls
    return tables, labels

def collect_pilot(root=ROOT, offline=False):
    """Fixed reviewed-scope pilot; no season/country expansion flag."""
    root = Path(root)
    combined = root / 'data/pilot_2024'
    combined.mkdir(parents=True, exist_ok=True)
    frames = {stage: [] for stage in ('post_qualifying', 'post_grid')}
    label_frames, reports, manifest = [], [], []
    for country in COUNTRIES:
        output = root / 'data' / ('2024_' + country.lower().replace(' ', '_'))
        client = Client(output / 'raw', offline=offline)
        try:
            data, report = build(client, 2024, country)
            if data is None:
                raise ValueError('; '.join(report['blocking']))
            tables, labels = race_quality(client, data, report)
            data.to_csv(output / 'draft_entrants.csv', index=False)
            for stage, table in tables.items():
                table.to_csv(output / f'{stage}_entrants.csv', index=False)
                frames[stage].append(table)
            labels.to_csv(output / 'podium_labels.csv', index=False)
            label_frames.append(labels)
            manifest.append({'race_id': report['race_id'], 'country': country, 'year': 2024,
                             'race_date': report['race_session']['date_start'],
                             'meeting_key': report['race_session']['meeting_key'],
                             'qualifying_session_key': report['qualifying_session']['session_key'],
                             'race_session_key': report['race_session']['session_key'],
                             'practice_session_key': report['practice_session']['session_key'] if report['practice_session'] else None,
                             'requires_M2_verification': True})
        except (ValueError, KeyError, TypeError) as exc:
            report = {'country': country, 'collection_complete': False, 'requires_M2_verification': True,
                      'collection_status': 'failed_requires_M2', 'error': str(exc), 'requests': client.calls}
        report_file = 'offline_quality_report.json' if offline else 'quality_report.json'
        (output / report_file).write_text(json.dumps(report, indent=2, allow_nan=False))
        reports.append(report)
    summary = {'scope': 'five completed 2024 Grands Prix only', 'offline': offline,
               'races_requested': len(COUNTRIES), 'races_with_feature_tables': len(manifest),
               'races_collected_successfully': sum(r.get('collection_complete', False) for r in reports),
               'all_require_M2_verification': True, 'races': reports}
    for stage, parts in frames.items():
        columns = IDENTITY + BASE + (['grid_position'] if stage == 'post_grid' else [])
        table = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=columns)
        if table.duplicated(KEYS).any():
            raise ValueError('duplicate race/driver key in combined features')
        table.to_csv(combined / f'{stage}_features.csv', index=False)
        summary[stage] = {'driver_rows': len(table), 'missing_by_feature': {c: int(table[c].isna().sum()) for c in columns if c not in IDENTITY}}
    labels = pd.concat(label_frames, ignore_index=True) if label_frames else pd.DataFrame(columns=LABEL_COLUMNS)
    labels.to_csv(combined / 'podium_labels.csv', index=False)
    pd.DataFrame(manifest).to_csv(combined / 'race_manifest.csv', index=False)
    name = 'offline_quality_report.json' if offline else 'quality_report.json'
    (combined / name).write_text(json.dumps(summary, indent=2, allow_nan=False))
    return summary

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()
    report = collect_pilot(offline=args.offline)
    print(json.dumps({k: v for k, v in report.items() if k != 'races'}, indent=2))
    print(json.dumps([{'race': r.get('race_id', r.get('country')), 'status': r['collection_status'],
                       'api_errors': [c for c in r['requests'] if 'error' in c]} for r in report['races']], indent=2))
    return 0 if report['races_collected_successfully'] == len(COUNTRIES) else 1

if __name__ == '__main__':
    raise SystemExit(main())
