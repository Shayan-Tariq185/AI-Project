"""Read-only package checks; stdlib unittest avoids external caches/temp files."""
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import unittest
from build_package import HERE, MODELLING, REVIEW_FIELDS, build_contents, extract_events

class VerificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contents = build_contents()
        cls.issues = list(csv.DictReader(io.StringIO(cls.contents['issues.csv'])))
        cls.events = list(csv.DictReader(io.StringIO(cls.contents['qualifying_lap_events.csv'])))
        cls.manifest = json.loads(cls.contents['source_manifest.json'])

    def test_all_five_races_and_initial_review_fields(self):
        self.assertEqual(len({r['race_id'] for r in self.issues}), 5)
        self.assertEqual(len(self.issues), 57)
        self.assertEqual(len({r['issue_id'] for r in self.issues}), len(self.issues))
        for row in self.issues + self.events:
            self.assertEqual(row['review_status'], 'unresolved')
            for field in REVIEW_FIELDS[1:]:
                self.assertEqual(row[field], '')
        self.assertFalse(self.manifest['automatic_approval'])

    def test_every_raw_event_retained_with_identifiable_driver(self):
        self.assertEqual(len(self.events), 12)
        self.assertEqual(self.manifest['deleted_events'], 12)
        self.assertEqual(self.manifest['reinstated_events'], 0)
        self.assertEqual([sum(e['race_id'] == race for e in self.events) for race in
                          ('2024_bahrain_gp', '2024_saudi_arabia_gp', '2024_australia_gp', '2024_japan_gp', '2024_china_gp')], [2, 4, 2, 1, 3])
        issue_ids = {r['issue_id'] for r in self.issues}
        for event in self.events:
            raw = json.loads((MODELLING / event['source_path']).read_text())
            self.assertEqual(raw[int(event['source_row_1_based'])-1]['message'], event['message'])
            self.assertTrue(event['driver_name'])
            self.assertTrue(event['driver_number'])
            self.assertIn(event['issue_id'], issue_ids)
            self.assertEqual(event['identity_conflict'], 'False')

    def test_parser_retains_reinstatement_and_unknown_identity(self):
        events = extract_events([
            {'message': 'CAR 44 TIME 1:22.000 REINSTATED LAP 7'},
            {'message': 'LAP TIME DELETED'},
            {'message': 'CAR 44 LAP 8 DELETED', 'driver_number': 11},
        ], [{'driver_number': 44, 'full_name': 'Known Driver'}], 'demo', 'source.json')
        self.assertEqual(events[0]['action'], 'reinstated')
        self.assertEqual(events[0]['driver_name'], 'Known Driver')
        self.assertEqual(events[0]['lap_number'], 7)
        self.assertIsNone(events[1]['driver_number'])
        self.assertEqual(events[1]['identity_basis'], 'unidentified')
        self.assertTrue(events[2]['identity_conflict'])

    def test_critical_review_flags(self):
        by_id = {r['issue_id']: r for r in self.issues}
        self.assertIn('UNUSUAL COUNT: 19', by_id['2024_australia_gp-ENTRANTS']['observation'])
        self.assertIn('ZHOU Guanyu', by_id['2024_saudi_arabia_gp-QUALIFYING']['observation'])
        self.assertIn('Practice 1', by_id['2024_china_gp-PRACTICE']['observation'])
        for race in {r['race_id'] for r in self.issues}:
            self.assertIn('unknown', by_id[race+'-CUTOFF-G']['observation'])
            self.assertIn('not established', by_id[race+'-CUTOFF-Q']['observation'])
            self.assertIn('no M2 attestation', by_id[race+'-GRID']['observation'])

    def test_source_paths_hashes_and_markdown_links(self):
        self.assertEqual(len(self.manifest['sources']), 82)
        for source in self.manifest['sources']:
            path = (MODELLING / source['path']).resolve()
            self.assertTrue(path.is_relative_to(MODELLING))
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), source['sha256'])
        links = re.findall(r'\]\((\.\./[^)]+)\)', self.contents['CHECKLIST.md'])
        self.assertGreater(len(links), 50)
        for link in links:
            self.assertTrue((HERE / link).is_file(), link)

    def test_package_build_does_not_modify_evidence(self):
        before = {r['path']: r['sha256'] for r in self.manifest['sources']}
        after = json.loads(build_contents()['source_manifest.json'])
        self.assertEqual(before, {r['path']: r['sha256'] for r in after['sources']})
        for source in self.manifest['sources']:
            if source['path'].endswith('quality_report.json'):
                report = json.loads((MODELLING / source['path']).read_text())
                if 'M2_approved' in report:
                    self.assertFalse(report['M2_approved'])
                if 'grid_verified' in report:
                    self.assertFalse(report['grid_verified'])

    def test_generated_files_match_review_snapshot(self):
        for name, expected in self.contents.items():
            # newline='' preserves intentional CSV CRLF in the in-memory snapshot.
            with (HERE / name).open(encoding='utf-8', newline='') as stream:
                self.assertEqual(stream.read(), expected, name)

if __name__ == '__main__':
    unittest.main()
