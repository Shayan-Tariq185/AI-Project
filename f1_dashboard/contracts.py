"""Proposed integration contracts; availability timestamps are UTC."""
from dataclasses import dataclass
from datetime import datetime
from math import isfinite


def utc(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None or result.utcoffset().total_seconds() != 0:
        raise ValueError("Timestamp must include UTC offset (+00:00 or Z).")
    return result


@dataclass(frozen=True)
class Race:
    race_id: str
    name: str
    circuit: str
    local_date: str
    start_utc: str


@dataclass(frozen=True)
class DriverInput:
    driver_id: str
    name: str
    qualifying_delta_s: float
    practice_delta_s: float | None
    grid_position: int | None


@dataclass(frozen=True)
class RaceInputs:
    race: Race
    cutoff_utc: str
    qualifying_available_utc: str | None
    practice_available_utc: str | None
    weather_available_utc: str | None
    grid_available_utc: str | None
    qualifying_track_temp_c: float | None
    qualifying_rainfall: bool | None
    drivers: tuple[DriverInput, ...]


def readiness(inputs: RaceInputs) -> str:
    if utc(inputs.cutoff_utc) >= utc(inputs.race.start_utc):
        return "Forecast window closed"
    if not inputs.qualifying_available_utc:
        return "Awaiting qualifying data."
    if not inputs.weather_available_utc:
        return "Awaiting qualifying-session weather."
    if inputs.grid_available_utc:
        return "Ready for grid-updated forecast"
    return "Ready for qualifying forecast"


def validate_inputs(inputs: RaceInputs, include_grid: bool) -> None:
    cutoff = utc(inputs.cutoff_utc)
    if cutoff >= utc(inputs.race.start_utc):
        raise ValueError("The pre-race forecast window is closed.")
    if not inputs.qualifying_available_utc or not inputs.weather_available_utc:
        raise ValueError("Qualifying and qualifying-session weather are required.")
    for timestamp in (inputs.qualifying_available_utc, inputs.practice_available_utc,
                      inputs.weather_available_utc, inputs.grid_available_utc):
        if timestamp and utc(timestamp) > cutoff:
            raise ValueError("An input became available after the forecast cutoff.")
    if (inputs.qualifying_track_temp_c is None
            or not isfinite(inputs.qualifying_track_temp_c)
            or not isinstance(inputs.qualifying_rainfall, bool)):
        raise ValueError("Qualifying-session weather is incomplete.")
    ids = [driver.driver_id for driver in inputs.drivers]
    if len(ids) < 3 or len(set(ids)) != len(ids):
        raise ValueError("At least three distinct drivers are required.")
    if include_grid and not inputs.grid_available_utc:
        raise ValueError("An official starting grid is required for the update.")
    positions = []
    for driver in inputs.drivers:
        if not isfinite(driver.qualifying_delta_s) or driver.qualifying_delta_s < 0:
            raise ValueError("Qualifying deltas must be finite and non-negative.")
        if driver.practice_delta_s is not None:
            if (not inputs.practice_available_utc or not isfinite(driver.practice_delta_s)
                    or driver.practice_delta_s < 0):
                raise ValueError("Practice needs a valid delta and availability timestamp.")
        if include_grid:
            if type(driver.grid_position) is not int or not 1 <= driver.grid_position <= len(ids):
                raise ValueError("Every driver needs a valid grid position.")
            positions.append(driver.grid_position)
    if len(positions) != len(set(positions)):
        raise ValueError("Starting grid positions must be unique.")


def matched_picks(picks: list[str], actual: list[str]) -> int:
    if len(picks) != 3 or len(set(picks)) != 3 or len(actual) != 3 or len(set(actual)) != 3:
        raise ValueError("Forecast and actual podium need three unique drivers each.")
    return len(set(picks) & set(actual))
