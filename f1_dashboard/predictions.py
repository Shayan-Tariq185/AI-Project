"""DEMO heuristics only. M3 replaces these functions with trained inference."""
from dataclasses import dataclass
from math import isfinite
from .contracts import RaceInputs, validate_inputs

PODIUM_MODEL_VERSION = "demo-podium-v1"
LAP_MODEL_VERSION = "demo-lap-v1"
CIRCUIT_BASE_SECONDS = {"Las Vegas": 95.0, "Lusail": 85.0, "Yas Marina": 88.0}
COMPOUND_PENALTY = {"SOFT": 0.0, "MEDIUM": 0.7, "HARD": 1.4}


def predict_podium(inputs: RaceInputs, include_grid: bool = False) -> list[str]:
    validate_inputs(inputs, include_grid)
    def score(driver):
        # Illustrative weather-sensitive weights, not learned coefficients.
        weight = 0.2 if inputs.qualifying_rainfall else 0.3
        if inputs.qualifying_track_temp_c > 40:
            weight += 0.05
        pace = driver.qualifying_delta_s
        if driver.practice_delta_s is not None:
            pace = (1 - weight) * pace + weight * driver.practice_delta_s
        return pace + (0.08 * (driver.grid_position - 1) if include_grid else 0)
    selected = sorted(inputs.drivers, key=lambda d: (score(d), d.driver_id))[:3]
    return [driver.driver_id for driver in sorted(selected, key=lambda d: d.name)]


@dataclass(frozen=True)
class LapEstimate:
    seconds: float
    test_mae_seconds: float | None
    model_version: str


def estimate_lap(circuit: str, compound: str, tire_age_laps: int,
                 track_temp_c: float) -> LapEstimate:
    if circuit not in CIRCUIT_BASE_SECONDS or compound not in COMPOUND_PENALTY:
        raise ValueError("Select a supported circuit and tire compound.")
    if type(tire_age_laps) is not int or not 0 <= tire_age_laps <= 60:
        raise ValueError("Tire age must be an integer from 0 to 60 laps.")
    if not isfinite(track_temp_c) or not 10 <= track_temp_c <= 65:
        raise ValueError("Track temperature must be between 10 and 65 °C.")
    seconds = (CIRCUIT_BASE_SECONDS[circuit] + COMPOUND_PENALTY[compound]
               + 0.045 * tire_age_laps + 0.006 * (track_temp_c - 35) ** 2)
    return LapEstimate(round(seconds, 3), None, LAP_MODEL_VERSION)
