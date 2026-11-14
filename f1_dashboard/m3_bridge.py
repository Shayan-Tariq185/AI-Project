"""Optional M3 boundary. Never substitutes demo output for a failed model call."""
import json
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import subprocess
import sys
from dataclasses import asdict
from .contracts import RaceInputs

ROOT = Path(__file__).resolve().parents[1]
DEPENDENCIES = {"pandas": "2.3.3", "numpy": "2.3.5", "scikit-learn": "1.8.0", "joblib": "1.5.3"}


class ModelUnavailable(RuntimeError):
    """The optional model environment, artifact or handoff is unavailable."""


def dependency_status() -> list[dict]:
    rows = []
    for package, required in DEPENDENCIES.items():
        try:
            installed = version(package)
        except PackageNotFoundError:
            installed = "Not installed"
        rows.append({"Package": package, "Required": required, "Installed": installed,
                     "Status": "Matches" if installed == required else "Setup needed"})
    return rows


def artifact_status(root: Path = ROOT) -> list[dict]:
    rows = []
    for task, model, metadata in (
        ("Qualifying podium", "podium/post_qualifying.joblib", "podium/post_qualifying.json"),
        ("Grid-updated podium", "podium/post_grid.joblib", "podium/post_grid.json"),
        ("Lap time", "lap_time/linear_regression.joblib", "lap_time/linear_regression.json"),
    ):
        base = root / "modelling/artifacts/v2"
        present = [name for name in (model, metadata) if (base / name).is_file()]
        rows.append({"Task": task, "Model file": model, "Metadata file": metadata,
                     "Status": "Files present; validation pending" if len(present) == 2
                     else "Missing: " + ", ".join(name for name in (model, metadata) if name not in present)})
    return rows


def _predict(payload: dict) -> dict:
    mismatches = [row["Package"] for row in dependency_status() if row["Status"] != "Matches"]
    if mismatches:
        raise ModelUnavailable("Set up requirements-models.txt first. Missing/incompatible: " + ", ".join(mismatches))
    try:
        # M3 uses directory-local imports. A separate interpreter keeps those imports
        # out of Streamlit's module namespace and avoids changing its working directory.
        result = subprocess.run(
            [sys.executable, "-X", "utf8", str(ROOT / "f1_dashboard/model_worker.py")],
            input=json.dumps(payload, allow_nan=False), capture_output=True, text=True,
            encoding="utf-8", cwd=ROOT / "modelling", timeout=60, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ModelUnavailable(f"M3 inference could not complete: {error}") from error
    try:
        response = json.loads(result.stdout)
        if not response.get("ok"):
            raise ModelUnavailable(response.get("error", "M3 inference failed."))
        if result.returncode:
            raise ModelUnavailable("M3 inference process failed.")
        return response["prediction"]
    except (json.JSONDecodeError, KeyError, AttributeError, TypeError) as error:
        raise ModelUnavailable("M3 returned an invalid response; no prediction is available.") from error


def predict_podium(inputs: RaceInputs, include_grid: bool = False, *, context: dict) -> dict:
    """Call M3's integration_adapter using RaceInputs and explicit PodiumContext fields.

    context['drivers'] is a list of mapping records; other fields match M3's
    PodiumContext exactly. Returns its complete result as a dictionary.
    """
    if not isinstance(inputs, RaceInputs) or type(include_grid) is not bool or not isinstance(context, dict):
        raise ValueError("RaceInputs, boolean include_grid and explicit context are required.")
    if include_grid and context.get("grid_verified") is not True:
        raise ValueError("M2's explicit grid verification is required.")
    context = dict(context)
    if "handoff_path" not in context:
        raise ValueError("Explicit M2 handoff_path is required.")
    context["handoff_path"] = str(Path(context["handoff_path"]).resolve())
    return _predict({"task": "podium", "inputs": asdict(inputs),
                     "include_grid": include_grid, "context": context})


def estimate_lap(circuit: str, compound: str, tire_age_laps: int,
                 track_temp_c: float, *, context: dict) -> dict:
    """Call M3's adapter with four scalars plus explicit LapContext fields.

    Preserve hypothetical/extrapolation disclosures, evidence and metadata.
    Typical error stays None until M3/M1 agree a representative evaluated metric.
    """
    if not isinstance(context, dict) or "evidence_path" not in context:
        raise ValueError("Explicit lap context and evidence_path are required.")
    if context.get("mode") not in ("historical", "scenario"):
        raise ValueError("Mode must be historical or scenario.")
    if context["mode"] == "scenario" and not context.get("scenario_provenance"):
        raise ValueError("Scenario input provenance is required.")
    context = dict(context)
    context["evidence_path"] = str(Path(context["evidence_path"]).resolve())
    return _predict({"task": "lap_time", "circuit": circuit, "compound": compound,
                     "tire_age_laps": tire_age_laps, "track_temp_c": track_temp_c,
                     "context": context})
