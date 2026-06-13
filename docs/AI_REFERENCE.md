# AI Quick Reference — RoundnetMatchmaking

Fast lookup for data model attributes, function locations, and common task recipes.
Generated 2026-06-13. Line numbers are accurate at creation and remain useful search hints as code evolves.

---

## 1 — Data Model Cheat Sheet

### `Player` — `core/models.py:291`

From a `pd.Series` row. Key attributes set in `__init__`:

| Attribute | Type | Notes |
|---|---|---|
| `name` | str | `series.name` (DataFrame index) |
| `level` | float | from series `"Level"` |
| `noisy_level` | float | = `level` at init; may be perturbed |
| `rounded_noisy_level` | float | rounded version of noisy_level |
| `happiness` | float | cumulative across rounds |
| `previous_happiness` | float | happiness before current round |
| `relative_happiness` | float | `happiness - session.mean_happiness`, set at end of session |
| `gender` | str | `"Male"` / `"Female"` / other |
| `prey` | float | spectrum score (0 = not set) |
| `equilibrist` | float | spectrum score |
| `challenger` | float | spectrum score |
| `chill` | float | spectrum score |
| `hunter` | float | spectrum score |
| `classist` | float | spectrum score |
| `last_spec_chosen` | str or None | spectrum category chosen last round |
| `spec_chosen_history` | list | one entry per round |
| `last_happiness_gained` | float | delta from latest round |
| `happiness_gained_history` | list | one delta per round |
| `games_played` | int | from series `"Games played"` |
| `teammate_history` | list | players paired with |
| `other_players_in_same_game_history` | list | opponents seen |

> **Pickle safety**: all `Player` attributes are plain Python types — no lambda, no unpicklable object.

---

### `TeamOfTwo` — `core/models.py:521`

| Attribute | Type | Notes |
|---|---|---|
| `player_A`, `player_B` | Player | the two players |
| `players` | list[Player] | `[player_A, player_B]` |
| `players_set` | set | membership tests |
| `players_frozenset` | frozenset | use for history dedup |
| `players_name` | set[str] | name strings |
| `level_difference` | float | `abs(A.level - B.level)` |
| `mean_level` | float | average level |
| `mixed` | bool | different genders |
| `male`, `female`, `non_binary` | bool | majority gender flags |

---

### `GameOfFour` — `core/models.py:580`

| Attribute | Type | Notes |
|---|---|---|
| `team_A`, `team_B` | TeamOfTwo | |
| `teams` | set[TeamOfTwo] | `{team_A, team_B}` |
| `participants` | frozenset[Player] | all 4 players |
| `team_A_mean_level`, `team_B_mean_level` | float | |
| `overall_mean_level` | float | |
| `level_difference` | float | `abs(A.mean - B.mean)`, rounded |
| `is_gender_preference_satisfied` | bool | |
| `weight_same_teammate` | float | from session config |

---

### `GamesRound` — `core/models.py:756` — **PICKLED**

| Attribute | Type | Notes |
|---|---|---|
| `games` | list[GameOfFour] | populated after `create_games()` |
| `not_playing` | list[Player] | bench players this round |
| `teams` | set[TeamOfTwo] | union of all game teams |
| `participants` | list[Player] | all players available for round |
| `participants_names` | list[str] | |
| `amount_of_games` | int | |
| `type_preference` | str | `"balanced"` / `"level"` / `None` |
| `gender_preference` | str | `"open"` / `"mixed"` / `None` |
| `minority_gender` | str or None | |
| `num_iter` | int | iteration budget |
| `level_gap_tol` | float | |
| `spectrum` | bool | |
| `weight_same_teammate` | float | |
| `iterations` | list[dict] | telemetry — keys vary by type_preference |
| `objective_function` | callable | **not pickled directly** — restored from metadata |
| `_objective_function_name` | str | pickle metadata |
| `_objective_lambda_weight` | float or None | pickle metadata |
| `_objective_percentile` | int or None | pickle metadata |

> **Pickle safety**: `objective_function` is stripped in `__getstate__` and reconstructed in `__setstate__` from the three `_objective_*` fields. Adding a new attribute: always guard with `getattr(obj, 'attr', default)`.

---

### `SessionOfRounds` — `core/models.py:1963` — **PICKLED** (`__module__ = "main"`)

| Attribute | Type | Notes |
|---|---|---|
| `players` | list[Player] | all session players (with updated happiness) |
| `players_name` | list[str] | |
| `rounds` | list[GamesRound] | one per round, in play order |
| `amount_of_rounds` | int | |
| `type_preferences` | list[str] | per-round, length == amount_of_rounds |
| `gender_preferences` | list[str] | per-round |
| `games_per_round_each_round` | list[int] | per-round game counts |
| `players_per_team_each_round` | list[int] | per-round team sizes |
| `mean_happiness` | float | computed after `create_rounds()` |
| `std_happiness` | float | computed after `create_rounds()` |
| `level_gap_tol` | float | |
| `num_iter` | int | |
| `spectrum` | bool | |
| `weight_same_teammate` | float | |
| `never_met_bonus_per_player` | float | |
| `never_met_bonus_cap` | float | |
| `extra_parameters` | dict | raw expert config dict |
| `game_optimization` | dict | `extra_parameters["game_optimization"]` |
| `happiness_config` | dict | `extra_parameters["happiness"]` |
| `_objective_function_name` | str | pickle metadata |
| `_objective_lambda_weight` | float or None | pickle metadata |
| `_objective_percentile` | int or None | pickle metadata |
| `objective_function` | callable | restored from metadata on load |
| `prioritize_level_rounds` | bool | |
| `rounds_reordering` | list or None | |

> **Pickle safety**: same `__getstate__`/`__setstate__` pattern as `GamesRound`. All pickled session files encode the class path as `main.SessionOfRounds` (see `__module__ = "main"`). Do not change `__module__`.

---

## 2 — Function Index

### Generate a session

```python
# Primary entry point — iterate seeds, return best session
session, seed = run_session_generation_with_seed_optimization(
    df, amount_of_rounds, type_preferences, gender_preferences,
    level_gap_tol, num_iter, objective_function, lambda_weight,
    first_seed, last_seed, ...
)
# core/algorithm.py:37
```

UI bridge called from the Run Session button:
```python
self.run_generation_with_progress(...)
# ui/tabs/session_generation_tab.py:3156
```

---

### Post-process (preferred pairs)

```python
force_preferred_pairs_in_session(session, preferred_pairs, ...)
# core/algorithm.py:351

apply_preferred_pairs_happiness(session, preferred_pairs)
# core/algorithm.py:505
```

---

### Save / load sessions

```python
save_session(session_of_rounds, folder="session", filename=None)
# core/pickle_helper.py:13

load_session(file_path)
# core/pickle_helper.py:48

find_latest_session(folder="session")
# core/pickle_helper.py:75
```

---

### Charts

```python
create_all_session_charts(session, ...)   # convenience wrapper
# core/charts.py:873

plot_happiness_charts(session, ...)
# core/charts.py:13

plot_team_analysis(session_of_rounds, save_path=None, save_png=True, png_dir=None)
# core/charts.py:266

plot_spectrum_analysis(session, ...)
# core/charts.py:639
```

---

### Preferences

```python
load_ui_preferences() -> dict          # ui/functions/preferences_manager.py:265
load_extra_preferences() -> dict       # ui/functions/preferences_manager.py:270
load_extra_preferences_temp() -> dict  # ui/functions/preferences_manager.py:275
save_ui_default_saved(prefs_subset)    # ui/functions/preferences_manager.py:304
update_ui_temp(full_prefs)             # ui/functions/preferences_manager.py:314
save_ui_not_saved(prefs_subset)        # ui/functions/preferences_manager.py:321
get_not_saved_diff(full_current_prefs) # ui/functions/preferences_manager.py:330
get_not_saved_diff_from_temp()         # ui/functions/preferences_manager.py:342
cleanup_temp_files()                   # ui/functions/preferences_manager.py:359
serialize_preferred_pairs(pairs)       # ui/functions/preferences_manager.py:218
deserialize_preferred_pairs(data)      # ui/functions/preferences_manager.py:235
```

---

### Module loading (mandatory for any core import from UI)

```python
# NEVER do: import core.something from UI code
# ALWAYS do:
module = load_module(module_name, file_name, force_reload=False)
# ui/functions/ui_helpers.py:75
```

---

### UI infrastructure helpers

```python
set_window_icon_from_logo(root)    # ui/functions/ui_helpers.py:102
ConsoleRedirector                  # ui/functions/ui_helpers.py:120  (io.StringIO subclass)
ProgressDialog                     # ui/functions/ui_helpers.py:145
```

---

### Tab helpers (`ui/functions/tab_functions.py`)

```python
session_generation_round_type_priority(type_pref)  # :17 — sort key for round ordering
games_editor_delta_to_bg(delta)                    # :36 — happiness delta → bg colour
session_games_out_of_place_count(round_order)      # :66 — count misplaced rounds
plots_find_png_files(plots_dir)                    # :76 — discover plot PNGs
_show_loading_window(root)                         # :88 — splash window
_ensure_windows_tcl_env()                          # :131 — set TCL_LIBRARY/TK_LIBRARY
```

---

## 3 — Common Task Recipes

### Add a parameter slider (auto-saved preference)

1. **`ui/functions/preferences_manager.py`**
   - Add key to `UI_DEFAULT_SAVED_KEYS` (frozenset, ~line 148)
   - Add default value to `_UI_DEFAULTS` dict (~line 52)

2. **Tab Mixin `__init__`** (`ui/tabs/session_generation_tab.py`)
   - Call the builder helper:
     ```python
     self._make_param_slider(
         parent, grid_row, grid_col,
         label_text="My Label",
         tooltip_text="...",
         var_attr="my_var",       # creates self.my_var (tk.DoubleVar)
         scale_attr="my_scale",   # creates self.my_scale (tk.Scale)
         from_=0.0, to_=5.0, resolution=0.1,
         initial_value=default_value,
     )
     # session_generation_tab.py:971
     ```

3. **`_load_and_apply_preferences()`** (same Mixin)
   ```python
   self.my_var.trace_add("write", self._on_auto_save_change)
   ```

4. **`_collect_ui_default_saved()`**
   ```python
   prefs["my_key"] = self.my_var.get()
   ```

5. **`_apply_ui_preferences(prefs)`**
   ```python
   self.my_var.set(prefs.get("my_key", default_value))
   ```

---

### Add a parameter toggle group (auto-saved)

Same 5-step preference chain as the slider. Replace step 2's `_make_param_slider` call with:

```python
frame, btn_dict = self._make_toggle_group(
    parent, bg_color="#dddddd",
    label_text="My Toggle",
    options=["option_a", "option_b"],
    var=self.my_str_var,          # tk.StringVar, create before calling
)
# session_generation_tab.py:1026
```

---

### Add an action button to the header row

Locate the action button row frame in `SessionGenerationTabMixin.__init__` (search for `btn_frame` near the "Select All" and "Clear Selection" buttons). Add:

```python
tk.Button(
    btn_frame,
    text="My Action",
    font=self.fonts["normal_bold"],
    bg=self.colors["accent_yellow"],
    fg=self.colors["text_dark"],
    relief=tk.FLAT,
    padx=12, pady=4,
    cursor="hand2",
    command=self.my_action_method,
).pack(side=tk.LEFT, padx=4)
```

---

### Add a new tab

1. Create `ui/tabs/my_tab.py` containing `class MyTabMixin`.
2. Import and add to `PlayerSelectionUI` bases in `ui/main/roundnet_matchmaking_ui.py`:
   ```python
   class PlayerSelectionUI(
       ...,
       MyTabMixin,
   ):
   ```
3. Add to `FILES_TO_COPY` in `ui/main/build_exe.py`.
4. Update `docs/UI_STRUCTURE.md`.

---

### Add a new attribute to a pickled class (safe)

Always add in `__init__`; read everywhere with `getattr`:

```python
# In __init__:
self.new_attr = default_value

# When reading a loaded object (old .pkl files won't have it):
value = getattr(session, "new_attr", default_value)
```

Do **not** rename or remove attributes without a `__setstate__` migration. See Step 5 of `DEV_PROCESS.md` for the stamp-on-load pattern.

---

### Wire a UI slider → algorithm parameter (full chain)

```
self.my_var (tk.DoubleVar, session_generation_tab.py)
    ↓ _collect_ui_default_saved()
prefs["my_key"]
    ↓ run_generation_with_progress() — session_generation_tab.py:3156
kwargs["my_param"] = prefs["my_key"]
    ↓ run_session_generation_with_seed_optimization(...) — core/algorithm.py:37
session_kwargs["my_param"] = my_param
    ↓ SessionOfRounds(**session_kwargs) — core/models.py:1963
self.my_param = my_param
```

---

### Add an opt-in preference (user confirms at close)

Four-step chain — all in `ui/functions/preferences_manager.py` and the tab Mixin:

1. Add key to `UI_DEFAULT_NOT_SAVED_KEYS` (~line 163)
2. Add human-readable label to `UI_DEFAULT_NOT_SAVED_LABELS` (~line 173)
3. Add default to `_UI_DEFAULTS` (~line 52)
4. Read in `_collect_ui_all_tracked()`, restore in `_apply_ui_preferences()`
