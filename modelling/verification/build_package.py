"""Create M2 review documents from existing local OpenF1 evidence only."""
import csv
import hashlib
import io
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
MODELLING = HERE.parent
FILES = ('CHECKLIST.md', 'issues.csv', 'qualifying_lap_events.csv', 'source_manifest.json')
REVIEW_FIELDS = ['review_status', 'reviewer', 'reviewed_at_utc', 'confirmed_cutoff_utc',
                 'correction_details', 'evidence_and_notes']

def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def csv_text(rows, columns):
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()

def extract_events(rows, drivers, race_id, source):
    names = {r['driver_number']: r.get('full_name', '') for r in drivers}
    events = []
    for index, row in enumerate(rows, 1):
        message = str(row.get('message', ''))
        action = re.search(r'\b(DELETED|REINSTATED)\b', message, re.I)
        if not action:
            continue
        car = re.search(r'\bCAR\s+(\d+)\b', message, re.I)
        number = row.get('driver_number')
        method = 'structured driver_number'
        if number is None:
            number = int(car.group(1)) if car else None
            method = 'CAR number parsed from message' if car else 'unidentified'
        conflict = car is not None and number != int(car.group(1))
        lap = re.search(r'\bLAP\s+(\d+)\b', message, re.I)
        duration = re.search(r'\bTIME\s+(\d+:\d+(?:\.\d+)?)', message, re.I)
        events.append({'issue_id': f'{race_id}-LAP-{len(events)+1:02d}', 'race_id': race_id,
                       'session_key': row.get('session_key'), 'action': action.group(1).lower(),
                       'message_utc': row.get('date'), 'driver_number': number,
                       'driver_name': names.get(number, ''), 'identity_basis': method,
                       'identity_conflict': conflict,
                       'lap_number': row.get('lap_number') if row.get('lap_number') is not None else (int(lap.group(1)) if lap else None),
                       'reported_lap_time': duration.group(1) if duration else '',
                       'message': message, 'source_path': source, 'source_row_1_based': index,
                       **{f: 'unresolved' if f == 'review_status' else '' for f in REVIEW_FIELDS}})
    return events

def build_contents():
    report_path = MODELLING / 'data/pilot_2024/quality_report.json'
    pilot = read_json(report_path)
    issues, all_events, race_sections = [], [], []
    sources = {MODELLING / 'CONTRACT.md', report_path}

    def issue(race_id, code, title, observation, task, paths, session_keys):
        row = {'issue_id': f'{race_id}-{code}', 'race_id': race_id, 'category': code,
               'title': title, 'observation': observation, 'M2_action': task,
               'session_keys': session_keys, 'source_paths': '; '.join(paths),
               **{f: 'unresolved' if f == 'review_status' else '' for f in REVIEW_FIELDS}}
        issues.append(row)
        return row

    for race in pilot['races']:
        race_id = race['race_id']
        directory = MODELLING / 'data' / race_id.removesuffix('_gp')
        q = race['qualifying_session']['session_key']
        r = race['race_session']['session_key']
        p = race['practice_session']['session_key']
        meeting = race['race_session']['meeting_key']
        keys = f'meeting={meeting}; qualifying={q}; race={r}; practice={p}'
        raw = directory / 'raw'
        evidence = {
            'sessions': raw / f'sessions_year-2024_country_name-{race["race_session"]["country_name"]}.json',
            'qualifying_drivers': raw / f'drivers_session_key-{q}.json',
            'practice_drivers': raw / f'drivers_session_key-{p}.json',
            'qualifying_laps': raw / f'laps_session_key-{q}.json',
            'practice_laps': raw / f'laps_session_key-{p}.json',
            'qualifying_classification': raw / f'session_result_session_key-{q}.json',
            'grid': raw / f'starting_grid_session_key-{q}.json',
            'qualifying_control': raw / f'race_control_session_key-{q}.json',
            'practice_control': raw / f'race_control_session_key-{p}.json',
            'weather': raw / f'weather_session_key-{q}.json',
            'race_classification': raw / f'session_result_session_key-{r}.json',
            'draft': directory / 'draft_entrants.csv',
            'post_qualifying': directory / 'post_qualifying_entrants.csv',
            'post_grid': directory / 'post_grid_entrants.csv',
            'labels': directory / 'podium_labels.csv',
            'quality': directory / 'quality_report.json',
        }
        sources.update(evidence.values())
        paths = {k: str(v.relative_to(MODELLING)).replace('\\', '/') for k, v in evidence.items()}
        with evidence['post_grid'].open(encoding='utf-8-sig', newline='') as stream:
            features = list(csv.DictReader(stream))
        missing_rows = [{k: row[k] for k in ('driver_number', 'driver_name', 'qualifying_position', 'qualifying_gap_seconds')}
                        for row in features if not row['qualifying_position'] or not row['qualifying_gap_seconds']]
        events = extract_events(read_json(evidence['qualifying_control']), read_json(evidence['qualifying_drivers']), race_id, paths['qualifying_control'])
        reported = race['lap_quality']['qualifying']['lap_deletion_or_reinstatement_messages']
        if [e['message'] for e in events] != [e['message'] for e in reported]:
            raise ValueError(f'Raw qualifying messages and pilot report differ: {race_id}')
        all_events.extend(events)
        local = []
        def add(code, title, observation, task, refs):
            local.append(issue(race_id, code, title, observation, task, [paths[x] for x in refs], keys))
        add('ENTRANTS', 'Eligible entrants and normal GP sessions',
            f"{race['entrants']} entrants; duplicate feature rows={race['duplicate_feature_driver_rows']}. " +
            ('UNUSUAL COUNT: 19 rather than a usual 20; classification, grid and roster coverage agree, but eligibility still needs review.' if race['entrants'] != 20 else 'Count is 20; this is a coverage check, not eligibility approval.'),
            'Confirm the eligible entrant list at each forecast stage. Explain withdrawals/substitutions and any count difference. Confirm normal Qualifying and Race in this meeting, excluding sprint sessions.',
            ['sessions', 'qualifying_drivers', 'qualifying_classification', 'grid', 'quality'])
        add('QUALIFYING', 'Missing qualifying data and classification',
            'Missing feature counts: ' + json.dumps(race['missing_by_feature']) + '. Affected qualifying rows: ' + json.dumps(missing_rows, ensure_ascii=False) + '.',
            'Verify official normal-GP qualifying positions. Preserve nulls when no valid classification/lap exists. For Zhou in Saudi Arabia, review the all-null Q1/Q2/Q3 times and confirm position/gap should remain null; do not substitute grid position.',
            ['qualifying_classification', 'qualifying_laps', 'post_qualifying'])
        # Remove the Saudi-specific instruction from other races.
        if not missing_rows:
            local[-1]['M2_action'] = 'Verify normal-GP qualifying classification and confirm no missing qualifying values were overlooked. Never substitute grid positions for qualifying classification.'
        add('LAP-VALIDITY', 'Qualifying valid-lap reconstruction',
            f'{len(events)} deleted/reinstated messages found. Provisional filtering does not fully resolve pit-in, deleted or reinstated laps. Raw messages are listed individually below.',
            'Review every event below and the full chronological qualifying race-control log. Match by driver and lap, resolve reinstatements, and check best valid lap across all Q1/Q2/Q3. Recheck the session-fastest reference: changing one driver\'s fastest valid lap can change every qualifying gap. Record proposed corrections without editing feature CSVs in this package.',
            ['qualifying_control', 'qualifying_laps', 'qualifying_classification', 'post_qualifying'])
        practice_quality = race['lap_quality']['practice']
        add('PRACTICE', 'Practice selection, lap validity and driver identity',
            f"Selected {race['practice_session']['session_name']} ({p}). Rejected-lap counts: {json.dumps(practice_quality['rejected_laps'])}. Identity review flags: {json.dumps(race['identity_review'])}.",
            'Confirm one common latest comparable practice before normal qualifying (FP3 when present; China uses FP1). Exclude sprint sessions, pit-out/incomplete/pit-in laps and invalid/deleted laps. Confirm driver-number identity, including substitutes; review track-evolution limitations.',
            ['sessions', 'practice_drivers', 'qualifying_drivers', 'practice_laps', 'practice_control', 'draft'])
        add('WEATHER', 'Qualifying weather',
            'Shared qualifying weather comes from one cached /weather response; missing counts are included above.',
            'Confirm qualifying-session air/track-temperature medians and any-rainfall aggregation, shared by all drivers and available by the chosen forecast cutoff.',
            ['weather', 'post_qualifying'])
        add('GRID', 'Final grid and penalties',
            f"Grid integrity: {json.dumps(race['grid_integrity'])}. Stored grid_verified={race['grid_verified']}; no M2 attestation has been supplied.",
            f'Confirm final grid, including penalties and pit-lane arrangements, for every eligible starter. OpenF1 starting_grid is keyed by qualifying session {q}, not race {r}. Structural uniqueness/completeness alone is not final-grid verification. Record source timing and any correction.',
            ['grid', 'qualifying_drivers', 'post_grid', 'quality'])
        cutoffs = race['forecast_cutoffs']
        add('CUTOFF-Q', 'Post-qualifying forecast cutoff remains unverified',
            f"Intended session-end cutoff: {cutoffs['post_qualifying']}. Historical availability of classification/weather/lap validity at this instant is not established.",
            'Enter the verified UTC forecast cutoff in confirmed_cutoff_utc; document when every qualifying-stage input was available and whether late corrections were known then. Later retrieval timestamps do not prove earlier availability.',
            ['sessions', 'qualifying_control', 'qualifying_classification', 'weather', 'draft', 'quality'])
        add('CUTOFF-G', 'Post-grid forecast cutoff is unresolved',
            f"Recorded post-grid cutoff: {cutoffs['post_grid']} (unknown).",
            'Enter a verified pre-race UTC forecast cutoff in confirmed_cutoff_utc. Establish when the final penalized grid was published and available, and confirm it precedes race start. Keep unresolved if existing evidence is insufficient; do not infer it from race outcomes or scheduled race time.',
            ['sessions', 'grid', 'quality'])
        add('LABELS', 'Race classification and separate podium labels',
            f"Classification coverage complete={race['classification_coverage_complete']}; missing labels={race['labels_missing']}; positive podium labels={race['podium_label_count']}; issues={json.dumps(race['label_issues'])}.",
            'Audit only the separate labels against the normal Grand Prix race classification. Confirm top three and DNF/DNS/DSQ interpretation; leave ambiguous targets unresolved. Never use this evidence to construct prediction features or filter entrants retrospectively.',
            ['race_classification', 'labels', 'quality'])
        for event in events:
            local.append(issue(race_id, event['issue_id'].split(race_id+'-', 1)[1],
                f"{event['action'].capitalize()} qualifying lap — #{event['driver_number']} {event['driver_name'] or '(unidentified)'}",
                f"UTC message {event['message_utc']}; lap {event['lap_number']}; reported time {event['reported_lap_time'] or 'not given'}; identity basis: {event['identity_basis']}. Exact message: {event['message']}",
                'Resolve this event against the full log and matching lap. Check later reinstatement/deletion and whether it changes best valid pace or the session-wide reference. Record evidence and proposed correction; no automatic feature change.',
                [event['source_path'], paths['qualifying_laps'], paths['qualifying_classification']], keys))
        title = race['race_session']['country_name'] + ' 2024'
        section = [f'## {title}', '', f'Race ID: `{race_id}`. Meeting **{meeting}**; normal qualifying **{q}**; GP race **{r}**; practice **{p}**.', '',
                   f"**{race['entrants']} entrants; all issues initially unresolved; M2 approval remains pending.**", '',
                   'Evidence files (links open existing local caches/tables):', '']
        section += [f'- {name.replace("_", " ")}: [{Path(path).name}](../{path})' for name, path in paths.items()]
        section += ['', 'Review checklist:', '']
        for entry in local:
            section += [f"### {entry['issue_id']} — {entry['title']}", '', entry['observation'], '',
                        '**M2 check:** ' + entry['M2_action'], '',
                        '- Review status: **unresolved** (choose verified / corrected / unresolved)',
                        '- Reviewer / reviewed at UTC: ____________________',
                        '- Confirmed cutoff UTC, if applicable: ____________________',
                        '- Correction details: ____________________',
                        '- Evidence and notes: ____________________', '']
        if events:
            section += ['Deleted/reinstated messages are reproduced verbatim above. UTC is the message record timestamp; trailing clock times inside messages are preserved as supplied and are not assumed to be UTC. Driver/lap values parsed from prose remain interpretations for review.', '']
        race_sections.append('\n'.join(section))
    for source in sources:
        if not source.is_file():
            raise FileNotFoundError(f'Missing cached evidence: {source}')
    manifest = {'contract_version': '1.0', 'source': 'existing collected OpenF1 data only; no network',
                'races': len(pilot['races']), 'issues': len(issues), 'qualifying_lap_events': len(all_events),
                'deleted_events': sum(e['action'] == 'deleted' for e in all_events),
                'reinstated_events': sum(e['action'] == 'reinstated' for e in all_events),
                'automatic_approval': False,
                'sources': [{'path': str(p.relative_to(MODELLING)).replace('\\', '/'), 'bytes': p.stat().st_size,
                             'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(sources)]}
    intro = ['# M2 verification checklist — five-race 2024 pilot', '',
             'This package is a review worksheet, not an approval or a corrected dataset. Start here if you are new to the project. M2 verifies forecast-time inputs; M3 will use reviewed data later. No model training is part of this review.', '',
             '## How to use this package', '',
             '1. Review one race at a time using the evidence links below. Paths in CSV/JSON files are relative to `modelling/`; links in this document are relative to `verification/`.',
             '2. Record decisions in **issues.csv** (the primary editable review register). Use **verified** when the supplied value/evidence is confirmed, **corrected** when a specific correction is documented for handoff, or **unresolved** when evidence is insufficient. Corrected does not mean the ML feature file has been changed.',
             '3. Fill reviewer, UTC review time, correction details, and evidence/notes. For cutoff issues also fill confirmed_cutoff_utc. The Markdown fields are an optional printable worksheet; copy any decisions back to issues.csv so it remains the single decision register.',
             '4. qualifying_lap_events.csv is a searchable event inventory with its own optional review fields. Reference its issue_id in issues.csv. Retain every event, including any reinstatement; do not assume a deletion is final.',
             '5. Do not mark a race ready merely because collection or contract smoke checks passed. Close or explicitly escalate every unresolved item, then hand decisions to M3. This package contains no automatic race approval mechanism.', '',
             f"Scope: **5 races, 99 driver rows, {len(all_events)} detected qualifying lap events, {len(issues)} review items**. No additional races were fetched. Source version: [CONTRACT.md](../CONTRACT.md); data checks: [pilot quality report](../data/pilot_2024/quality_report.json).", '',
             '## Immediate attention', '',
             '- **All five races:** final-grid verification and both forecast cutoffs remain pending; the post-grid cutoff is unknown. Deleted/pit-in/reinstated-lap validity still requires review.',
             '- **Saudi Arabia:** Zhou Guanyu (#24) has null qualifying_position and qualifying_gap_seconds; no valid segment time is recorded. Preserve nulls unless M2 establishes a correction.',
             '- **Australia:** 19 entrants rather than the usual 20. Existing roster, grid and classification agree, but explain the eligible-entry count without inventing a twentieth driver.',
             '- **China:** Practice 1 is the fallback practice source. Verify normal GP sessions, excluding sprint qualifying and the sprint race.',
             f"- Detected actions: **{manifest['deleted_events']} deleted, {manifest['reinstated_events']} reinstated**. No reinstatement was detected in these cached qualifying logs; this is not proof of final validity.", '',
             'The source manifest records SHA-256 hashes to identify the exact reviewed snapshot. No source CSV, label, cache, quality flag, or model artifact is modified by this package.', '']
    event_columns = list(all_events[0]) if all_events else ['issue_id', 'race_id'] + REVIEW_FIELDS
    return {'CHECKLIST.md': '\n'.join(intro + race_sections),
            'issues.csv': csv_text(issues, list(issues[0])),
            'qualifying_lap_events.csv': csv_text(all_events, event_columns),
            'source_manifest.json': json.dumps(manifest, indent=2)}

def main():
    contents = build_contents()
    if any((HERE / name).exists() for name in contents):
        raise FileExistsError('Review files already exist; refusing to overwrite teammate decisions. build_contents() can produce an in-memory comparison.')
    for name, content in contents.items():
        (HERE / name).write_text(content, encoding='utf-8', newline='')
    print(json.dumps({'files': list(contents), 'summary': {k: v for k, v in json.loads(contents['source_manifest.json']).items() if k != 'sources'}}, indent=2))

if __name__ == '__main__':
    main()
