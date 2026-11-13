"""One immutable JSON file per snapshot; independent of Streamlit state."""
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from .contracts import RaceInputs, matched_picks, utc, validate_inputs
from .predictions import PODIUM_MODEL_VERSION

DEFAULT_ARCHIVE = Path(__file__).resolve().parents[1] / "data" / "saved_forecasts"


def make_snapshot(inputs: RaceInputs, picks: list[str], include_grid: bool,
                  now: datetime | None = None) -> dict:
    validate_inputs(inputs, include_grid)
    matched_picks(picks, picks)
    drivers = {driver.driver_id: driver.name for driver in inputs.drivers}
    if not set(picks) <= drivers.keys():
        raise ValueError("Picks must belong to the input driver field.")
    now = now or datetime.now(timezone.utc)
    if not utc(inputs.cutoff_utc) <= now < utc(inputs.race.start_utc):
        raise ValueError("Snapshots must be created after their cutoff and before race start.")
    return {"schema_version": 1, "forecast_id": str(uuid4()), "demo": True,
            "race": asdict(inputs.race), "created_at_utc": now.isoformat(),
            "cutoff_utc": inputs.cutoff_utc, "model_version": PODIUM_MODEL_VERSION,
            "mode": "grid-updated" if include_grid else "qualifying", "picks": list(picks),
            "driver_names": drivers, "input_snapshot": asdict(inputs)}


def save_snapshot(snapshot: dict, directory: Path = DEFAULT_ARCHIVE) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{uuid4()}.json"
    with path.open("x", encoding="utf-8") as file:
        json.dump(snapshot, file, indent=2, allow_nan=False)
    return path


def load_snapshots(directory: Path = DEFAULT_ARCHIVE) -> tuple[list[dict], list[str]]:
    records, errors = [], []
    for path in sorted(directory.glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            if record["schema_version"] != 1 or record["demo"] is not True:
                raise ValueError("Unsupported prototype archive schema.")
            if not isinstance(record["race"]["name"], str) or not record["race"]["race_id"]:
                raise ValueError("Invalid race identity.")
            if not utc(record["cutoff_utc"]) <= utc(record["created_at_utc"]) < utc(record["race"]["start_utc"]):
                raise ValueError("Invalid pre-race timestamps.")
            matched_picks(record["picks"], record["picks"])
            for code in record["picks"]:
                if not isinstance(record["driver_names"][code], str):
                    raise ValueError("Invalid driver name.")
            if record["mode"] not in ("qualifying", "grid-updated") or not record["model_version"]:
                raise ValueError("Invalid forecast metadata.")
            records.append(record)
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
            errors.append(f"Skipped {path.name}: {error}")
    return records, errors
