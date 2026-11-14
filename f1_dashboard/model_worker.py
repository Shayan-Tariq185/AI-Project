"""Internal JSON worker for M3's integration_adapter; never trains or fetches."""
from dataclasses import asdict
import json
from pathlib import Path
import sys


def run(request):
    if request.get("task") not in ("podium", "lap_time"):
        raise ValueError("Unknown inference task.")
    root = Path(__file__).resolve().parents[1]
    for directory in (root, root / "modelling"):
        if str(directory) not in sys.path:
            sys.path.insert(0, str(directory))
    # One canonical import, as required by M3's sibling-module layout.
    import integration_adapter as adapter
    if request["task"] == "podium":
        import pandas as pd
        from f1_dashboard.contracts import Race, RaceInputs, DriverInput
        raw = dict(request["inputs"])
        race = Race(**raw.pop("race"))
        drivers = tuple(DriverInput(**row) for row in raw.pop("drivers"))
        inputs = RaceInputs(race=race, drivers=drivers, **raw)
        context = dict(request["context"])
        context["drivers"] = pd.DataFrame.from_records(context["drivers"])
        result = adapter.predict_podium(inputs, request["include_grid"],
                                        context=adapter.PodiumContext(**context))
    else:
        result = adapter.estimate_lap(
            request["circuit"], request["compound"], request["tire_age_laps"],
            request["track_temp_c"], context=adapter.LapContext(**request["context"]),
        )
    # Preserve complete M3 result wrappers, including all evidence/disclosures.
    # Selection, identity translation, validation and metric decisions stay in M3.
    return asdict(result)


if __name__ == "__main__":
    try:
        response = {"ok": True, "prediction": run(json.load(sys.stdin))}
    except Exception as error:
        response = {"ok": False, "error": f"{type(error).__name__}: {error}"}
    print(json.dumps(response, allow_nan=False))
    sys.exit(0 if response["ok"] else 1)
