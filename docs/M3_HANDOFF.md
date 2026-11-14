# M1 connection to M3's integration adapter

## Current state

The merged `modelling/integration_adapter.py` is the single implementation of dashboard-to-model translation, evidence checking and output validation. M3 also supplies Random Forest podium and separate Linear Regression lap pipelines, evidence templates and synthetic software tests. **Production artifacts and approved real input packages are still pending.** The five-race historical pilot is explicitly unreviewed.

The dashboard therefore keeps the existing forecast/lap screens in labeled demo mode. Its **Integration status** page reports model/metadata file presence and optional dependency versions, plus outstanding handoffs. File presence is not approval or proof that inference works. This page does not fetch data, train a model or deserialize artifacts.

## Callable M1 bridge

`f1_dashboard/m3_bridge.py` sends requests to `model_worker.py` in an isolated interpreter using the same project environment. The worker configures the repository root and `modelling/` import paths, imports `integration_adapter` once under its canonical name, constructs its explicit contexts and calls its public functions. M3's files, Streamlit's working directory and parent module namespace remain untouched.

The bridge returns dictionaries corresponding to **complete** M3 result dataclasses. It preserves version/evidence and lap hypothetical/extrapolation disclosures. It does not select drivers, translate features independently, create approvals, infer tire-age conventions, train/fetch, or substitute demo predictions after a failure. Errors raise `ModelUnavailable`. Invalid top-level arguments raise `ValueError`.

```python
from f1_dashboard import m3_bridge

# inputs: the existing RaceInputs, supplied by the real reviewed M2 provider.
# context: all fields documented in modelling/INTEGRATION_ADAPTER.md.
# context['drivers']: mapping records in exactly this column order:
# dashboard_driver_id, driver_id, driver_number, qualifying_position.
forecast = m3_bridge.predict_podium(inputs, include_grid=False, context=podium_context)
# forecast = {'picks': [...], 'model_version': '...', 'evidence': {...}}

# Use a separately approved post-grid context and explicit grid_verified=True
# within that context for a grid-updated prediction.
updated = m3_bridge.predict_podium(grid_inputs, include_grid=True, context=grid_context)

# The four scalars still require M3's explicit LapContext fields.
result = m3_bridge.estimate_lap(circuit, compound, age, temperature, context=lap_context)
# result preserves estimate, is_hypothetical, support_status, evidence,
# and artifact_metadata. estimate contains seconds, test_mae_seconds and version.
```

Contexts are dictionaries with exactly M3's documented context fields, except `PodiumContext.drivers` is serialized as mapping records rather than a DataFrame. Use JSON-compatible values: UTC ISO strings, ordinary numbers/booleans and `None` for reviewed missing values. Handoff/evidence paths are resolved before the child starts. No context values are filled from demo data.

See **[M3's adapter contract](../modelling/INTEGRATION_ADAPTER.md)** for every required field, reviewed pace definitions, supplementary qualifying position/air temperature, driver crosswalks, cutoff equality, explicit grid attestation and lap identity/timing context. Its complete result wrapper is authoritative. A selection rank never means a predicted finishing position.

**Typical lap test error remains `None`**, matching M3's adapter. Choosing a representative held-out metric and disclosing its supported population remains a team decision. The bridge retains full evaluation metadata but never extracts an unscoped MAE or treats it as a prediction interval. Synthetic test errors are not historical performance evidence.

## Optional model environment

The demo and status page require only `requirements.txt`. For the M3 boundary/tests, use the shared project environment from the repository root:

```powershell
& ".\.venv\Scripts\python.exe" -m pip install -r requirements-models.txt
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -v
Push-Location modelling
try {
    & "..\.venv\Scripts\python.exe" -B -m pytest -q
} finally {
    Pop-Location
}
```

The optional requirements combine Streamlit with M3's existing lock file, including its pinned pandas/numpy versions. Artifact loading also checks Python minor/library compatibility and hashes. Install the versions accompanying real artifacts before using them. Only trusted local artifacts/evidence are supported; no joblib upload or automatic artifact download is implemented.

M3 tests generate synthetic evidence/models under ignored `modelling/.test-work/`. They do not approve real data or create production artifacts. Dashboard tests cover the unchanged demo flows, status page, bridge transport, preserved result wrappers and explicit failure behavior.

## Remaining handoffs

| Owner | Needed next |
| --- | --- |
| M2 | Reviewed live/historical feature packages; supplementary qualifying position/air temperature; canonical driver/circuit mappings; availability/cutoff lineage; final-grid evidence; reviewed adapter contexts |
| M3 | Trusted trained artifacts for both podium stages and lap regression; matching metadata/evaluation; supported categories/ranges; real-data inference examples |
| M1 + M3 | Reconcile the requested four-input lap form with M3's driver/weekend conditioning; agree metric selection and disclosures |
| M1 | Connect the reviewed provider and bridge to the UI; add model-backed forecast persistence, result joins, disclosure display, deployment storage and combined tests |

Do not silently choose a driver or drop driver_id from a fitted lap model. Preserve the four-input demo until the team agrees a model/context policy. M3 estimates conditional clean **normal practice flying-lap** duration, not race or qualifying pace.

The current archive is explicitly demo-only. Before real saves, introduce a model-backed schema that retains canonical driver identities, input/translation context, model version, cutoff and evidence hashes. Qualifying/grid updates must remain separate snapshots. Display hypothetical and numeric-extrapolation flags on model-backed lap outputs, and populate UI categories/ranges from model metadata.

This change prepares a callable integration boundary and status reporting. **It does not enable real model inference from the Streamlit prediction screens.**

## Local validation — 14 November 2026

- Dashboard/bridge: **33 passed**, including Streamlit flows and a real isolated adapter call rejecting missing reviewed evidence.
- M3 suite: **153 passed, 1 failed**. The failure is `verification/test_verification.py::VerificationTests::test_generated_files_match_review_snapshot` on this Windows checkout.
- `pip check`: no broken requirements. Streamlit started and returned HTTP 200 from its health endpoint; the temporary verification server was stopped. Browser visual inspection was not performed.

The snapshot failure is unrelated to M1 inference code: checked-out `CHECKLIST.md` uses CRLF while its generated text uses LF. The only source-manifest difference is `CONTRACT.md`'s byte count/hash. Normalizing that file's CRLF to LF **in memory** reproduces both the stored byte count and SHA-256. The CSV snapshots match exactly; no data/content correction is indicated. No M3 source, reviewed evidence or stored manifest was edited to obtain these results.

The team should resolve the repository's line-ending policy for byte-hashed evidence and generated snapshots. Do not regenerate or overwrite review decisions to hide this portability failure. Keep the failed check visible until the policy and appropriate fix are agreed.
