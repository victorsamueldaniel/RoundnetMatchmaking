# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

## [1.2.0] - 2026-04-25
### Added
- Interactive round reordering in the Session Games tab: rounds are displayed as clickable tiles; click two rounds to swap their order, then apply the change.
- `create_session_games_round_images()` in `core/charts.py` generates one PIL Image per round with consistent portrait sizing (2.16:1 aspect ratio) for use as UI tiles.
- Percentile slider ("bottom x% size", range 0–50, default 33) in the generation panel to control which bottom-x% of players are prioritised by the objective function.
- `compute_session_score()` utility in `core/models.py` — computes a scalar session score from `Player` objects and objective metadata without coupling to UI slider state.
- Objective metadata stamped on generated session objects (`_objective_function_name`, `_objective_lambda_weight`, `_objective_percentile`) so the Games Editor score history always reflects actual generation parameters.
- Happiness delta preview in the Games Editor: player buttons are colour-coded green/red to show the happiness impact of each pending swap before it is applied.

### Changed
- Session games PNG now uses a dynamic figure width derived from a 2.16:1 portrait aspect ratio instead of a fixed 7.5-inch width.
- Lambda-weight slider label updates dynamically when the percentile slider value changes.
- `SessionOfRounds.reorder_rounds()` now fully resets and rebuilds all player happiness histories from the new display order, making round reordering idempotent.
- Not-playing (benched) players have their teammate and opponent histories cleared for each round they sit out, preventing stale data from affecting subsequent recalculations.
- Player buttons in the Games Editor use a cleaner two-line format (`Name\n\nLvl X`) with no parentheses.

### Tests
- Disabled `tests/tests_fine_tuning.py` in `tests/run_script_tests.py`.

## [1.1.0] - 2026-04-21
### Added
- Initial repository hygiene baseline for GitHub distribution.
- Root documentation and contribution guidance.
