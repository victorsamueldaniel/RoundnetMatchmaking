"""happiness_breakdown.py - explain the happiness gained by each player in a round.

Mirrors Player.update_happiness term by term. tests/test_happiness_breakdown.py
checks that the terms add up to the gain stored in happiness_gained_history.
"""

import numpy as np

from core.models import (
    _SPEC_KEY_TO_ATTR,
    repeated_same_people_count,
    same_teammate_penalty_applies,
    spectrum_trigger_profile,
)


def _divisor(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return 2.0
    return 1.0 if value == 0 else value


def round_breakdown(round_obj, round_idx):
    """Return {player_name: breakdown dict} for every playing player of a round."""
    p = round_obj._params
    gap_tol = round_obj.level_gap_tol
    out = {}
    for game in round_obj.games:
        for team, other in ((game.team_A, game.team_B), (game.team_B, game.team_A)):
            for player in team.players:
                teammates = [q for q in team.players if q is not player]
                teammates_levels = [q.level for q in teammates]
                opponents_levels = [q.level for q in other.players]
                teammate_history = player.teammate_history[:round_idx]
                same_game_history = player.other_players_in_same_game_history[
                    :round_idx
                ]
                terms = []

                spectrum = None
                if round_obj.spectrum:
                    triggers, _spectrum_diagnostics = spectrum_trigger_profile(
                        player,
                        teammates_levels,
                        opponents_levels,
                        sum(q.chill for q in team.players),
                        getattr(round_obj, "session_level_spread", 0.0),
                        round_obj.session_median_level,
                        {
                            "spectrum_equilibrist_relative_gap_threshold": p[
                                "spectrum_equilibrist_level_gap_tol_multiplier"
                            ],
                            "spectrum_challenger_relative_gap_threshold": p[
                                "spectrum_challenger_level_gap_tol_multiplier"
                            ],
                            "spectrum_classist_relative_teammate_gap_threshold": p[
                                "spectrum_classist_level_gap_tol_multiplier"
                            ],
                            "spectrum_chill_players_chill_threshold": p[
                                "spectrum_chill_players_chill_threshold"
                            ],
                            "spectrum_classist_requires_above_median_level": p.get(
                                "spectrum_classist_requires_above_median_level", True
                            ),
                        },
                    )
                    chosen = player.spec_chosen_history[round_idx]
                    gain = (
                        getattr(player, _SPEC_KEY_TO_ATTR[chosen]) * triggers[chosen]
                        if chosen
                        else 0
                    )
                    spectrum = {
                        "values": {
                            spec: float(getattr(player, attr))
                            for spec, attr in _SPEC_KEY_TO_ATTR.items()
                        },
                        "triggered": {k: bool(v) for k, v in triggers.items()},
                        "chosen": chosen,
                    }
                    terms.append(("spectrum", float(gain)))
                else:
                    threshold = (
                        player.level
                        * p["non_spectrum_high_level_threshold_self_level_multiplier"]
                    )
                    terms.append(
                        (
                            "high_level_teammates",
                            float(sum(1 for lv in teammates_levels if lv >= threshold)),
                        )
                    )
                    terms.append(
                        (
                            "high_level_opponents",
                            float(sum(1 for lv in opponents_levels if lv >= threshold)),
                        )
                    )

                weight = game.weight_same_teammate
                same_teammate_penalty = same_teammate_penalty_applies(
                    player,
                    [mate for mate in team.players if mate is not player],
                    teammate_history,
                    getattr(game, "preferred_pair_allowances", None),
                )
                terms.append(("same_teammate", -float(weight * same_teammate_penalty)))

                repeated = repeated_same_people_count(
                    player,
                    game.participants,
                    same_game_history,
                    [mate for mate in team.players if mate is not player],
                    getattr(game, "preferred_pair_allowances", None),
                )
                divisor = _divisor(
                    p[
                        "happiness_penalty_same_people_in_game_history_weight_same_teammate_divisor"
                    ]
                )
                terms.append(("same_people", -float(weight / divisor * repeated)))

                met = set()
                for players_set in same_game_history:
                    met.update(players_set)
                new_people = sum(
                    1 for q in game.participants if q is not player and q not in met
                )
                terms.append(
                    (
                        "never_met",
                        float(
                            min(
                                new_people * round_obj.never_met_bonus_per_player,
                                round_obj.never_met_bonus_cap,
                            )
                        ),
                    )
                )

                if not game.is_gender_preference_satisfied:
                    penalty = (
                        p["happiness_penalty_gender_preference_not_satisfied_spectrum"]
                        if round_obj.spectrum
                        else p[
                            "happiness_penalty_gender_preference_not_satisfied_non_spectrum"
                        ]
                    )
                    terms.append(("gender_preference", -float(penalty)))

                if (
                    round_obj.gender_preference == "mixed"
                    and round_obj.minority_gender is not None
                    and player.gender == round_obj.minority_gender
                ):
                    terms.append(
                        ("minority", float(p["happiness_bonus_minority_gender_mixed"]))
                    )

                if round_obj.type_preference == "level":
                    medians = round_obj.gender_level_medians or {}
                    if round_obj.gender_preference == "mixed" and medians:
                        reference = medians.get(player.gender)
                    else:
                        reference = round_obj.session_median_level
                    if reference is not None and player.level > reference:
                        terms.append(
                            (
                                "level_bonus",
                                float(
                                    p["happiness_bonus_above_median_level_type_level"]
                                ),
                            )
                        )

                out[player.name] = {
                    "terms": {k: v for k, v in terms},
                    "new_people": new_people,
                    "spectrum": spectrum,
                    "total": float(sum(v for _, v in terms)),
                }
    return out
