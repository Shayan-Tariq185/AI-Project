# M2 verification package

Start with [CHECKLIST.md](CHECKLIST.md). It explains the review steps and groups
the evidence and editable worksheet fields by Grand Prix.

- [issues.csv](issues.csv): primary review register; 57 issues, all initially
  unresolved. Edit this file in a spreadsheet. Set `review_status` to `verified`,
  `corrected`, or `unresolved`, and complete reviewer, review UTC timestamp,
  correction details, evidence and notes. Cutoff issues also have a
  `confirmed_cutoff_utc` field.
- [qualifying_lap_events.csv](qualifying_lap_events.csv): all 12 detected
  qualifying deletion messages, driver identification, lap numbers, UTC message
  timestamps, raw message text, and cached JSON row references. No reinstatement
  message was detected in these cached logs. Optional event review fields are
  provided; keep the corresponding decision in issues.csv authoritative.
- [source_manifest.json](source_manifest.json): 82 source paths and SHA-256
  hashes identify the exact contract/data snapshot used by this package.
- `build_package.py`: stdlib-only, offline package generator. It refuses to
  overwrite existing review files so teammate decisions are preserved.
- `test_verification.py`: read-only tests for completeness, driver matching,
  evidence links/hashes, initial unresolved status and unchanged source evidence.

Source paths in CSV/JSON are relative to `modelling/`. Markdown links resolve
from this directory. A JSON row reference is the 1-based position in the JSON
array, not a text-file line number. Driver/lap values parsed from message prose
are labeled as such; their structured OpenF1 fields are often null. Message UTC
timestamps and clock times embedded in prose must not be conflated.

No race is approved by this package. Marking an issue `corrected` records a
proposed/verified correction for handoff; it does not edit ML features. All
feature tables, labels, caches and original quality flags remain untouched. No
network requests or model training are involved. Where existing evidence cannot
establish final-grid timing or forecast availability, leave the issue unresolved.

Run the package tests from `modelling/` without creating bytecode or pytest
temporary files outside this directory:

```powershell
.venv\Scripts\python.exe -B -m unittest discover -s verification -p test_verification.py -v
```

The snapshot-equality test checks the initial handoff package. After M2 begins
editing review fields, differences from this generated initial state are expected;
do not regenerate over their decisions to make that test pass.
