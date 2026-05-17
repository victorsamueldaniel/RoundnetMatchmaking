# Preferences Persistence

Describes how user-configurable parameters are saved and restored across sessions.

---

## Overview

Four JSON files under `ui/user_preferences/` form two pairs — one for UI-accessible
parameters and one for non-UI generation knobs:

| File | Purpose | Lifetime |
|---|---|---|
| `ui_accessible.json` | Long-term UI preferences | Persists across sessions |
| `ui_accessible_temp.json` | Full runtime snapshot | Created on launch, deleted on exit |
| `extra_parameters.json` | Generation algorithm knobs | Persists (developer-edited) |
| `extra_parameters_temp.json` | Runtime editable copy; read at each session generation | Created on launch, deleted on exit; optionally archived at close |

---

## Parameter Categories

All logic lives in `ui/functions/preferences_manager.py`.

### `UI_DEFAULT_SAVED_KEYS` — auto-saved

Written to `ui_accessible.json` silently on every UI change (via tkinter traces).
No user prompt, no opt-in.

| Key | Type | Default | UI control |
|---|---|---|---|
| `num_rounds` | int | `4` | Rounds +/− buttons |
| `games_per_round` | str or int | `"auto"` | Games/round dropdown |
| `level_gap_tol` | float | `1.1` | Level gap tolerance slider |
| `lambda_weight` | float | `2.0` | Lambda weight slider |
| `percentile` | int | `33` | Percentile slider |
| `spectrum_enabled` | bool | `true` | Spectrum toggle |
| `round_type_preferences` | list[str] | `["balanced","balanced","level","level"]` | Per-round type toggles |
| `round_gender_preferences` | list[str] | `["open","mixed","mixed","open"]` | Per-round gender toggles |

### `UI_DEFAULT_NOT_SAVED_KEYS` — opt-in at close

Only written to `ui_accessible.json` if the user explicitly chooses "Save" in the
close dialog. Keys that are discarded are never written to the persistent file.

Both the keys and their human-readable labels are declared in `preferences_manager.py`
(`UI_DEFAULT_NOT_SAVED_KEYS` and `UI_DEFAULT_NOT_SAVED_LABELS`), so adding a new
opt-in parameter requires editing only that file.

| Key | Label in dialog | Default |
|---|---|---|
| `selected_players` | Selected players | _(none)_ |
| `female_boost` | Female level shift | `0.0` |
| `preferred_pairs` | Preferred pairs | `[]` |

### `extra_parameters.json` — developer-only knobs

Not exposed in the UI. Edit `extra_parameters_temp.json` directly during a session
to try different knobs — changes are picked up on the **next Run Session click**
without restarting the app. `extra_parameters.json` is the stable baseline read
once at startup.

| Key | Default | Description |
|---|---|---|
| `first_seed` | `0` | First random seed to test |
| `last_seed` | `9` | Last random seed to test |
| `num_iter` | `435` | Iterations per seed |
| `weight_same_teammate` | `5` | Penalty for repeated teammates |
| `never_met_bonus_per_player` | `2` | Bonus per player for novel matchups |
| `never_met_bonus_cap` | `4` | Cap on the novel-matchup bonus |
| `objective.name` | `"mean_min_max_happiness_objective"` | Objective function name |
| `objective.hyperparameters` | `{"lambda": 2.4, "percentile": 33}` | Objective hyperparameters |

Advanced expert knobs are nested and use script terminology to mirror call sites:

- `game_optimization.games_by_level._level_sorter.sd_of_randomizer` (default `0.1`)
- `game_optimization.games_by_level._level_sorter.round_factor` (default `1`)
- `game_optimization.generate_all_game_combinations.max_combos.depth_0` (default `20`)
- `game_optimization.generate_all_game_combinations.max_combos.depth_n` (default `10`)
- `game_optimization.generate_all_game_combinations.max_team_combos` (default `3`)
- `game_optimization.spectrum.Prey.opponents_mean_level_multiplier` (default `0.7`)
- `game_optimization.spectrum.Challenger.opponents_mean_level_multiplier` (default `0.9`)
- `game_optimization.spectrum.Challenger.level_gap_tol_multiplier` (default `0.5`)
- `game_optimization.spectrum.Equilibrist.level_gap_tol_multiplier` (default `0.5`)
- `game_optimization.spectrum.Classist.level_gap_tol_multiplier` (default `0.5`)
- `game_optimization.spectrum.Chill.players_chill_threshold` (default `10`)
- `game_optimization.non_spectrum.high_level_threshold.self_level_multiplier` (default `0.85`)
- `happiness.penalties.same_people_in_game_history.weight_same_teammate_divisor` (default `2`)
- `happiness.penalties.gender_preference_not_satisfied.spectrum` (default `5`)
- `happiness.penalties.gender_preference_not_satisfied.non_spectrum` (default `2`)
- `happiness.bonuses.minority_gender.mixed` (default `1`)
- `happiness.bonuses.above_median_level.type_level` (default `1`)
- `post_processing.force_preferred_pairs_in_session.forced_games_default` (default `1`)
- `post_processing.force_preferred_pairs_in_session.score_tolerance` (default `0.10`)

---

## Lifecycle

```
App launch
  └── ensure_preferences_exist()   create missing JSON files from developer defaults
  └── load_ui_preferences()        read ui_accessible.json → merged with defaults
  └── load_extra_preferences()     read extra_parameters.json → stored as _extra_prefs (startup snapshot)
  └── _apply_ui_preferences()      push values into all UI controls
  └── _initial_not_saved snapshot  record the not-saved keys at startup for change detection
  └── trace wiring                 tkinter write-traces → _on_auto_save_change
  └── update_ui_temp()             write initial full state to ui_accessible_temp.json

Runtime (every UI change to a default-saved key)
  └── _on_auto_save_change()
        save_ui_default_saved()    → ui_accessible.json  (only saved keys)
        update_ui_temp()           → ui_accessible_temp.json  (all tracked keys)

Session generation (Run Session / other generation triggers)
  └── load_extra_preferences_temp()  read extra_parameters_temp.json fresh each time
        picks up any edits made to extra_parameters_temp.json mid-session
        without restarting the app

App close (X button / WM_DELETE_WINDOW)
  └── _collect_ui_all_tracked()    snapshot current full state
  └── diff vs _initial_not_saved   find not-saved keys changed this session
  └── if any changed → _UnsavedPrefsDialog
        per-param Save / Discard toggle (defaults to Discard)
        Confirm → save_ui_not_saved() for chosen keys → ui_accessible.json
  └── extra_temp_differs_from_stable()  compare extra_parameters_temp.json vs extra_parameters.json
  └── if different → _ask_save_extra_params dialog
        Save   → save_extra_temp_as_dated(DD_MM_YYYY) → extra_parameters_temp_DD_MM_YYYY.json
        Discard → no file written
  └── cleanup_temp_files()         delete both _temp files
  └── root.destroy()
```

---

## Adding a New Parameter

### Auto-saved (user changes it, it persists silently)

1. Add the key to `UI_DEFAULT_SAVED_KEYS` in `preferences_manager.py`.
2. Add its developer default to `_UI_DEFAULTS`.
3. In `SessionGenerationTabMixin._collect_ui_default_saved()`, read the widget value and include it in the returned dict.
4. In `_apply_ui_preferences()`, set the widget from `prefs.get("your_key", default)`.
5. Add a `trace_add("write", self._on_auto_save_change)` call for the widget's tkinter variable in `_load_and_apply_preferences()`.

### Opt-in at close

1. Add the key to `UI_DEFAULT_NOT_SAVED_KEYS` in `preferences_manager.py`.
2. Add its human-readable label to `UI_DEFAULT_NOT_SAVED_LABELS` in the same file.
3. Add its developer default to `_UI_DEFAULTS` (or handle absence gracefully).
4. In `_collect_ui_all_tracked()`, read the widget value and include it.
5. In `_apply_ui_preferences()`, restore from `prefs` when the key is present.

---

## Path Resolution

| Context | `user_preferences/` location |
|---|---|
| Development (`python -m ui...`) | `<project_root>/ui/user_preferences/` |
| Frozen executable (PyInstaller) | Sibling of the `.exe` file |
