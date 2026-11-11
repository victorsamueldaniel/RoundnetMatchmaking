"""Central configuration for gameplay spectrum names, defaults, and tuning.

This file is the single source of truth for the values used across the engine,
UI, and analysis layers. Adjust the constants here when you want to change how
spectrum types are defined or weighted without touching multiple files.
"""

import numpy as np

SPECTRUM_NAMES = [
    "Prey",
    "Equilibrist",
    "Challenger",
    "Chill",
    "Hunter",
    "Classist",
]

SPECTRUM_ATTRS = [
    "prey",
    "equilibrist",
    "challenger",
    "chill",
    "hunter",
    "classist",
]

SPEC_KEY_TO_ATTR = dict(zip(SPECTRUM_NAMES, SPECTRUM_ATTRS))

SPECTRUM_DEFAULT_VALUES = {name: 5 for name in SPECTRUM_NAMES}

SPECTRUM_TUNING = {
    "prey_opponents_mean_level_multiplier": 0.7,
    "challenger_opponents_mean_level_multiplier": 0.9,
    "equilibrist_roster_spread_ratio": 0.1,
    "challenger_roster_spread_ratio": 0.2,
    "equilibrist_fallback_gap_multiplier": 0.5,
    "challenger_fallback_gap_multiplier": 0.5,
    "classist_level_gap_tol_multiplier": 0.5,
    "chill_players_threshold": 10,
}


def compute_spectrum_game(
    *,
    team_level,
    opponents_mean_level,
    teammates_mean_level,
    roster_spread_R=None,
    level_gap_tol=1.0,
    players_chill=0,
    tuning=None,
):
    """Return the current spectrum classification for a game outcome.

    The logic is intentionally centralized here so renaming or adjusting the
    meaning of a spectrum type updates all consumers in one place.
    """
    config = dict(SPECTRUM_TUNING)
    if tuning:
        config.update(tuning)

    d = team_level - opponents_mean_level
    d_challenger = (
        team_level
        - config["challenger_opponents_mean_level_multiplier"] * opponents_mean_level
    )

    R = None
    try:
        if roster_spread_R is not None:
            R = float(roster_spread_R)
            if not np.isfinite(R) or R <= 0:
                R = None
    except Exception:
        R = None

    if R is not None:
        t_eq = config["equilibrist_roster_spread_ratio"] * R
        t_chlgr = config["challenger_roster_spread_ratio"] * R
    else:
        t_eq = config["equilibrist_fallback_gap_multiplier"] * level_gap_tol
        t_chlgr = config["challenger_fallback_gap_multiplier"] * level_gap_tol

    is_equilibrist = abs(d) < t_eq
    is_prey = d <= -t_chlgr if t_chlgr is not None else False
    is_hunter = d >= t_eq if t_eq is not None else False
    is_challenger = ((-d) > t_eq and (-d) < t_chlgr) if t_chlgr is not None else False

    return {
        "Prey": 1 if is_prey else 0,
        "Equilibrist": 1 if is_equilibrist else 0,
        "Challenger": 1 if is_challenger else 0,
        "Chill": (1 if players_chill >= config["chill_players_threshold"] else 0),
        "Hunter": 1 if is_hunter else 0,
        "Classist": (
            1
            if abs(team_level - teammates_mean_level)
            <= config["classist_level_gap_tol_multiplier"] * level_gap_tol
            else 0
        ),
    }


def choose_best_spectrum(player, spectrum_game):
    """Pick the strongest matching spectrum for a player from a game result."""
    best_gain = float("-inf")
    specs_with_best_gain = []

    for spec in sorted(spectrum_game.keys()):
        spec_gain = getattr(player, SPEC_KEY_TO_ATTR[spec]) * spectrum_game[spec]
        if spec_gain > best_gain:
            specs_with_best_gain = [spec]
            best_gain = spec_gain
        elif spec_gain == best_gain:
            specs_with_best_gain.append(spec)

    if best_gain <= 0:
        return None

    return specs_with_best_gain[0]
