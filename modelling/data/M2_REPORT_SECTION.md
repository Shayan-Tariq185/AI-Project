# M2 Report Section

## Data sources

M2 used the cached OpenF1 `/sessions`, `/drivers`, `/laps`, `/weather`,
`/session_result`, `/starting_grid`, and `/race_control` responses. A Jolpica
adapter was not implemented in this repository snapshot.

## Feature preparation

The pilot creates separate post-qualifying and post-grid feature tables. Qualifying
pace uses the valid fastest lap in normal qualifying, practice pace uses the latest
comparable practice lap set, and weather uses qualifying-session median values.
Race classifications are converted to a separate binary podium label table.

## Lap handling

The practice lap handoff requires clean normal-practice laps, exact stint interval
matching, tire-age derivation, and backward weather matching. Cached stint responses
are absent, so the lap table is deliberately empty rather than populated with
guessed compounds or tire ages.

## Missing and unusual values

Missing values remain null. They are not median-imputed or replaced with guessing
in exported M2 data. DNF/DNS/DSQ labels follow the contract where classification
is unambiguous. Deleted laps and unknown official validity remain unresolved.

## Limitations

The five-race pilot is a data implementation and smoke test. It is not enough for
production training. Final grids, forecast publication cutoffs, lap validity,
Jolpica corroboration, and a reviewed M2 handoff remain unresolved.
