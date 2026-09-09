"""User preference persistence for the Roundnet Matchmaking UI.

Two pairs of JSON files live under ui/user_preferences/:

  ui_accessible.json    — long-term preferences (auto-saved or confirmed)
  ui_accessible_temp.json      — current runtime state; deleted on exit
  extra_parameters.json — non-UI generation knobs (developer-configurable)
  extra_parameters_temp.json   — runtime copy; deleted on exit

Path resolution mirrors setup_wizard.py: frozen executables use a sibling
directory next to the .exe; dev runs use <project_root>/ui/user_preferences/.

Policy classes
--------------
UI_DEFAULT_SAVED_KEYS   — written to stable automatically on every change.
UI_DEFAULT_NOT_SAVED_KEYS — written to stable only when the user confirms at
                            close time; absent from both files otherwise.
"""

import json
import os
import sys

# ---------------------------------------------------------------------------
# Path resolution  (mirrors setup_wizard.py)
# ---------------------------------------------------------------------------
if getattr(sys, "frozen", False):
    _prefs_dir = os.path.join(os.path.dirname(sys.executable), "user_preferences")
else:
    _project_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    _prefs_dir = os.path.join(_project_root, "ui", "user_preferences")

_UI_STABLE = os.path.join(_prefs_dir, "ui_accessible.json")
_UI_TEMP = os.path.join(_prefs_dir, "ui_accessible_temp.json")
_EXTRA_STABLE = os.path.join(_prefs_dir, "extra_parameters.json")
_EXTRA_TEMP = os.path.join(_prefs_dir, "extra_parameters_temp.json")

# ---------------------------------------------------------------------------
# Developer defaults
# ---------------------------------------------------------------------------
_SCHEMA_VERSION = 1

_UI_DEFAULTS: dict = {
    "schema_version": _SCHEMA_VERSION,
    "num_rounds": 4,
    "games_per_round": "auto",
    "level_gap_tol": 1.1,
    "lambda_weight": 2.0,
    "percentile": 33,
    "spectrum_enabled": True,
    "round_type_preferences": ["balanced", "balanced", "level", "level"],
    "round_gender_preferences": ["open", "mixed", "mixed", "open"],
}

_EXTRA_DEFAULTS: dict = {
    "schema_version": _SCHEMA_VERSION,
    "first_seed": 0,
    "last_seed": 9,
    "num_iter": 435,
    "weight_same_teammate": 5,
    "never_met_bonus_per_player": 2,
    "never_met_bonus_cap": 4,
    "objective": {
        "name": "mean_min_max_happiness_objective",
        "hyperparameters": {
            "lambda": 2.4,
            "percentile": 33,
        },
    },
    "game_optimization": {
        "games_by_level": {
            "_level_sorter": {
                "max_noise_factor": 0.1,
                "round_factor": 1,
            }
        },
        "generate_all_game_combinations": {
            "max_combos": {
                "depth_0": 20,
                "depth_n": 10,
            },
            "max_team_combos": 3,
        },
        "spectrum": {
            "Prey": {
                "opponents_mean_level_multiplier": 0.7,
            },
            "Challenger": {
                "opponents_mean_level_multiplier": 0.9,
                "level_gap_tol_multiplier": 0.5,
            },
            "Equilibrist": {
                "level_gap_tol_multiplier": 0.5,
            },
            "Classist": {
                "level_gap_tol_multiplier": 0.5,
            },
            "Chill": {
                "players_chill_threshold": 10,
            },
        },
        "non_spectrum": {
            "high_level_threshold": {
                "self_level_multiplier": 0.85,
            }
        },
    },
    "happiness": {
        "penalties": {
            "same_people_in_game_history": {
                "weight_same_teammate_divisor": 2,
            },
            "gender_preference_not_satisfied": {
                "spectrum": 5,
                "non_spectrum": 2,
            },
        },
        "bonuses": {
            "minority_gender": {
                "mixed": 1,
            },
            "above_median_level": {
                "type_level": 1,
            },
        },
    },
    "post_processing": {
        "force_preferred_pairs_in_session": {
            "forced_games_default": 1,
            "score_tolerance": 0.10,
        }
    },
    "print_progress": True,
}

# ---------------------------------------------------------------------------
# Policy sets
# ---------------------------------------------------------------------------

# Written to stable silently on every UI change.
UI_DEFAULT_SAVED_KEYS: frozenset = frozenset(
    {
        "num_rounds",
        "games_per_round",
        "level_gap_tol",
        "lambda_weight",
        "percentile",
        "spectrum_enabled",
        "round_type_preferences",
        "round_gender_preferences",
    }
)

# Written to stable only after explicit user confirmation at close.
UI_DEFAULT_NOT_SAVED_KEYS: frozenset = frozenset(
    {
        "selected_players",
        "female_boost",
        "preferred_pairs",
    }
)

# Human-readable labels for the UI close dialog — kept next to the keys so that
# adding a new "default not saved" param only requires editing this file.
UI_DEFAULT_NOT_SAVED_LABELS: dict = {
    "selected_players": "Selected players",
    "female_boost": "Female level shift",
    "preferred_pairs": "Preferred pairs",
}

# ---------------------------------------------------------------------------
# Internal I/O helpers
# ---------------------------------------------------------------------------


def _ensure_dir() -> None:
    os.makedirs(_prefs_dir, exist_ok=True)


def _deep_merge(defaults: dict, overrides: dict) -> dict:
    """Recursively merge overrides into defaults and return merged dict."""
    merged = dict(defaults)
    for key, value in overrides.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _read_json(path: str, defaults: dict) -> dict:
    """Read *path*; return developer defaults merged with file content on success."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            return dict(defaults)
        # Start from defaults so missing keys are always filled in, including
        # nested expert config trees.
        return _deep_merge(defaults, data)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return dict(defaults)


def _write_json(path: str, data: dict) -> None:
    _ensure_dir()
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Serialization helpers for non-primitive types
# ---------------------------------------------------------------------------


def serialize_preferred_pairs(pairs: list) -> list:
    """Convert preferred_pairs ``[(frozenset, int), ...]`` to a JSON-safe list."""
    result = []
    for entry in pairs:
        try:
            pair_fs, forced_games = entry
            result.append(
                {
                    "players": sorted(pair_fs),
                    "forced_games": int(forced_games),
                }
            )
        except (TypeError, ValueError):
            pass
    return result


def deserialize_preferred_pairs(data: list) -> list:
    """Restore preferred_pairs from a JSON list of ``{"players": [...], "forced_games": n}``."""
    result = []
    for item in data:
        try:
            result.append((frozenset(item["players"]), int(item["forced_games"])))
        except (KeyError, TypeError, ValueError):
            pass
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def ensure_preferences_exist() -> None:
    """Create all four JSON files from developer defaults when they are missing."""
    _ensure_dir()
    for path, defaults in (
        (_UI_STABLE, _UI_DEFAULTS),
        (_UI_TEMP, _UI_DEFAULTS),
        (_EXTRA_STABLE, _EXTRA_DEFAULTS),
    ):
        if not os.path.exists(path):
            _write_json(path, dict(defaults))
    if not os.path.exists(_EXTRA_TEMP):
        _write_json(_EXTRA_TEMP, _read_json(_EXTRA_STABLE, _EXTRA_DEFAULTS))


def load_ui_preferences() -> dict:
    """Return stable UI preference dict, merged with developer defaults for missing keys."""
    return _read_json(_UI_STABLE, _UI_DEFAULTS)


def load_extra_preferences() -> dict:
    """Return stable extra-parameters dict, merged with developer defaults."""
    return _read_json(_EXTRA_STABLE, _EXTRA_DEFAULTS)


def load_extra_preferences_temp() -> dict:
    """Return the runtime-editable temp extra-parameters dict.

    Use this at session-generation time so that in-session edits to
    extra_parameters_temp.json are picked up without restarting the app.
    Falls back to developer defaults if the file is missing or corrupt.
    """
    return _read_json(_EXTRA_TEMP, _EXTRA_DEFAULTS)


def extra_temp_differs_from_stable() -> bool:
    """Return True if extra_parameters_temp.json content differs from extra_parameters.json."""
    stable = _read_json(_EXTRA_STABLE, _EXTRA_DEFAULTS)
    temp = _read_json(_EXTRA_TEMP, _EXTRA_DEFAULTS)
    return stable != temp


def save_extra_temp_as_dated(date_str: str) -> str:
    """Archive extra_parameters_temp.json as extra_parameters_temp_{date_str}.json.

    The file is written next to the other prefs files in _prefs_dir.
    Returns the absolute path of the saved file.
    """
    temp = _read_json(_EXTRA_TEMP, _EXTRA_DEFAULTS)
    dated_path = os.path.join(_prefs_dir, f"extra_parameters_temp_{date_str}.json")
    _write_json(dated_path, temp)
    return dated_path


def save_ui_default_saved(prefs_subset: dict) -> None:
    """Silently persist default-saved keys to both stable and temp UI files."""
    for path in (_UI_STABLE, _UI_TEMP):
        current = _read_json(path, _UI_DEFAULTS)
        for k in UI_DEFAULT_SAVED_KEYS:
            if k in prefs_subset:
                current[k] = prefs_subset[k]
        _write_json(path, current)


def update_ui_temp(full_prefs: dict) -> None:
    """Write the full current UI state (saved + not-saved keys) to the temp file."""
    current = _read_json(_UI_TEMP, _UI_DEFAULTS)
    current.update(full_prefs)
    _write_json(_UI_TEMP, current)


def save_ui_not_saved(prefs_subset: dict) -> None:
    """Persist default-not-saved keys to stable after the user confirms at close."""
    current = _read_json(_UI_STABLE, _UI_DEFAULTS)
    for k in UI_DEFAULT_NOT_SAVED_KEYS:
        if k in prefs_subset:
            current[k] = prefs_subset[k]
    _write_json(_UI_STABLE, current)


def get_not_saved_diff(full_current_prefs: dict) -> dict:
    """Return mapping of not-saved keys whose current values differ from stable."""
    stable = _read_json(_UI_STABLE, _UI_DEFAULTS)
    diff = {}
    for k in UI_DEFAULT_NOT_SAVED_KEYS:
        current_val = full_current_prefs.get(k)
        stable_val = stable.get(k)
        if current_val != stable_val:
            diff[k] = current_val
    return diff


def get_not_saved_diff_from_temp() -> dict:
    """Return mapping of not-saved keys where ui_accessible_temp.json differs from stable.

    Mirrors extra_temp_differs_from_stable(): compares the temp file directly against the
    stable file so that the close-time check is independent of live widget state.
    """
    stable = _read_json(_UI_STABLE, _UI_DEFAULTS)
    temp = _read_json(_UI_TEMP, _UI_DEFAULTS)
    diff = {}
    for k in UI_DEFAULT_NOT_SAVED_KEYS:
        temp_val = temp.get(k)
        stable_val = stable.get(k)
        if temp_val != stable_val:
            diff[k] = temp_val
    return diff


def cleanup_temp_files() -> None:
    """Delete both temp JSON files.  Called on app exit."""
    for path in (_UI_TEMP, _EXTRA_TEMP):
        try:
            os.remove(path)
        except (FileNotFoundError, OSError):
            pass
