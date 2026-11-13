"""Static calendar and synthetic inputs. Replace with M2's adapter."""
from datetime import datetime, timedelta, timezone
from .contracts import DriverInput, Race, RaceInputs, utc

CALENDAR_CHECKED = "2026-11-13"
CALENDAR_SOURCE = "https://www.formula1.com/en/racing/2026"
RACES = (
    Race("2026-las-vegas", "Las Vegas Grand Prix", "Las Vegas", "2026-11-21", "2026-11-22T04:00:00Z"),
    Race("2026-qatar", "Qatar Grand Prix", "Lusail", "2026-11-29", "2026-11-29T16:00:00Z"),
    Race("2026-abu-dhabi", "Abu Dhabi Grand Prix", "Yas Marina", "2026-12-06", "2026-12-06T13:00:00Z"),
)
SCENARIOS = ("Before qualifying", "Qualifying ready", "Official grid ready", "Qualifying weather missing")
DRIVERS = (
    ("NOR", "Lando Norris", 0.00, 0.12, 5),
    ("VER", "Max Verstappen", 0.11, 0.00, 1),
    ("LEC", "Charles Leclerc", 0.18, 0.24, 4),
    ("PIA", "Oscar Piastri", 0.21, 0.17, 2),
    ("RUS", "George Russell", 0.35, 0.28, 3),
    ("HAM", "Lewis Hamilton", 0.42, 0.38, 6),
)


def upcoming_races(now: datetime | None = None) -> list[Race]:
    now = now or datetime.now(timezone.utc)
    return [race for race in RACES if utc(race.start_utc) > now]


def load_demo_inputs(race: Race, scenario: str, practice: bool,
                     now: datetime | None = None) -> RaceInputs:
    if scenario not in SCENARIOS:
        raise ValueError("Unknown demo scenario.")
    now = now or datetime.now(timezone.utc)
    def stamp(hours):
        return (now - timedelta(hours=hours)).isoformat()
    qualified = scenario != "Before qualifying"
    grid = scenario == "Official grid ready"
    weather = qualified and scenario != "Qualifying weather missing"
    return RaceInputs(
        race, now.isoformat(), stamp(2) if qualified else None,
        stamp(4) if practice else None, stamp(2) if weather else None,
        stamp(1) if grid else None, 32.0 if weather else None,
        False if weather else None,
        tuple(DriverInput(code, name, quali, pace if practice else None, position if grid else None)
              for code, name, quali, pace, position in DRIVERS) if qualified else (),
    )


SAMPLE_FORECAST = {
    "schema_version": 1, "forecast_id": "demo-sample-001", "demo": True,
    "race": {"race_id": "fictional-sample-gp", "name": "Sample Grand Prix (fictional)",
             "circuit": "Sample Circuit", "local_date": "2026-01-11", "start_utc": "2026-01-11T14:00:00Z"},
    "created_at_utc": "2026-01-10T18:05:00Z", "cutoff_utc": "2026-01-10T18:00:00Z",
    "model_version": "demo-podium-v1", "mode": "qualifying", "picks": ["LEC", "NOR", "VER"],
    "driver_names": {"LEC": "Charles Leclerc", "NOR": "Lando Norris", "VER": "Max Verstappen"},
    "input_snapshot": {"note": "Illustrative seed record only; not a real model inference."},
}
DEMO_RESULTS = {"fictional-sample-gp": {
    "podium": ["VER", "NOR", "PIA"], "available_at_utc": "2026-01-11T17:00:00Z",
    "source": "Fictional demo result (not official)",
}}
