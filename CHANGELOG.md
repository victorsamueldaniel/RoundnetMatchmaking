# Changelog
All notable changes to this project are documented in this file.
## [1.5.0]
### Changed
#### new sorter in level games
In games by level, there is now a helper function `_level_sorter` that sorts players by rounded level first and unhappiness second, with optional Gaussian noise to add variety across rounds. This helps players near a level boundary sometimes move into a different group.
Example:
Example players: A (lvl 3.9, happiness 10), B (lvl 3.4, happiness 9).
If the noise gives B a level of 3.6, then both players round to 4, so the keys become:
`_level_sorter(A) = (4, -10)`
`_level_sorter(B) = (4, -9)`

So B is placed ahead of A in that case. If B instead stays below 3.5, then A sorts ahead because its rounded level is higher.

#### User preferences
The application now remembers user-configured parameters across sessions using a small set of JSON files stored under `ui/user_preferences/`. On launch, saved values are restored into all UI controls automatically, with no user action required.

Parameters are split into two categories. **Auto-saved** parameters (number of rounds, games per round, level gap tolerance, lambda weight, percentile, spectrum toggle, and per-round type/gender preferences) are written to disk silently on every change via tkinter variable traces. **Opt-in** parameters (selected players, female level shift, and preferred pairs) are only persisted if the user explicitly chooses to save them at close time. When the app is closed and any of these opt-in parameters were modified during the session, a styled dialog appears listing each changed parameter individually with a Save / Discard toggle (defaulting to Discard), so the user can decide per-parameter.

A separate file (`extra_parameters.json`) holds generation algorithm knobs that are not exposed in the UI (seed range, iteration count, teammate-repeat penalty, never-met bonus). These are read once at startup and can be tuned by editing the file directly. See `docs/PREFERENCES_PERSISTENCE.md` for the full parameter reference and instructions for adding new parameters.

### Bug fixes
- Fixed round type/gender preferences resetting to defaults when clicking `+` or `−` on the number of rounds. The controls now preserve current selections for existing rounds and, for newly added rounds, fall back to the last values stored in the runtime temp file instead of hardcoded defaults.

## [1.4.0] - 2026-05-08
### Added
- Added a contact page tab.
- The Games Editor now detects over-benched players live during pending swaps and marks every matching Not Playing button across rounds with a black background, white text, and a middle SAD! label.
This behavior is implemented through a centralized, token-based button text/style system so the middle-line UI text can be changed later without rewriting swap or refresh logic.
- possibility to have 3 and 4 in prefered pair selection window.
### Changed
- Names of tabs scripts
- Changed placement of show level on PNG button. It is now in session games tab and allow dynamic changes
- major change to prefered pair: now it checks for best swap amongst all possible rounds and pairs swapped, instead of greedy searching for each round and each pair. There is a happiness computed (default [...14,12,10,8,8], and cutting starting at the end,depending on amount of games wanted: e.g. 3 games wanted, happiness is [10,8,8])
### Removed
### Bug fixes
- Changed quantile problem (it is now <=33%, >33%-<=66%, >66%)

## [1.3.0] - 2026-05-05
### Added
- Mac OS Intel and ARM executable, Unix executable
### Changed
- separated `player_selection_ui.py` in several .py files. One main called `roundnet_matchmaking_ui`, one for each tab (`games_editor_tab.py`, `plots_tab.py`, `session_games_tab.py`, `session_generation_tab.py`, `setup_wizard.py`),two for functions (`tab_functions.py` and `ui_helpers.py`)
### Removed
All `pyperclip` dependencies.
#### bug fix
- Changed alphabetical ordering, so accented letters come before the next one (Like "Aliénor" would come before "Alissa") in players frame
- Spinbox of player level in player edit dialog used to be caped at 4, it is now caped at 10'000
- removed display bug on session png when level is selected
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
