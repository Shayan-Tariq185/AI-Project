# Validation results — 2026-11-13

Command run from modelling/:

```powershell
.venv\Scripts\python.exe -B m2_lap_handoff/validate_examples.py
```

Completed successfully (exit code 0):

- Three clearly labeled SYNTHETIC historical-format rows passed the existing
  lap_model.validate input checks.
- The separate target table passed lap_model.validate_labels, including exact
  ordered schema, unique keys, matching example IDs and finite positive targets.
- The draft manifest remains unresolved and approved_for_modeling=false.
- Local Markdown links resolved.
- SHA-256 comparison confirmed all 30 captured existing top-level source,
  contract, documentation/configuration and verification-package files unchanged.
  The baseline is in protected_files_before.json (local absolute paths).

Only read-only validation functions were invoked. No training test suite or smoke
demo was run because those fit models. No data was fetched, no predictions made,
and no model artifacts or approval records created. These checks do not establish
real historical validity, source availability, statistical sufficiency or M2 approval.
