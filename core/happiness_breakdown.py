"""happiness_breakdown.py - explain the happiness gained by each player in a round.

Mirrors Player.update_happiness term by term. tests/test_happiness_breakdown.py
checks that the terms add up to the gain stored in happiness_gained_history.
"""

"""happiness_breakdown.py - explain the happiness gained by each player in a round.

Mirrors Player.update_happiness term by term. tests/test_happiness_breakdown.py
checks that the terms add up to the gain stored in happiness_gained_history.
"""

import numpy as np

from core.gameplay_config import SPEC_KEY_TO_ATTR, compute_spectrum_game
from core.models import repeated_same_people_count, same_teammate_penalty_applies


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
                    team_level = np.mean(teammates_levels + [player.level])
                    opp_mean = np.mean(opponents_levels)
                    triggers = compute_spectrum_game(
                        team_level=team_level,
                        opponents_mean_level=opp_mean,
                        teammates_mean_level=np.mean(teammates_levels),
                        roster_spread_R=getattr(round_obj, "roster_spread_R", None),
                        level_gap_tol=gap_tol,
                        players_chill=sum(q.chill for q in team.players),
                        tuning={
                            "prey_opponents_mean_level_multiplier": p["spectrum_prey_opponents_mean_level_multiplier"],
                            "challenger_opponents_mean_level_multiplier": p["spectrum_challenger_opponents_mean_level_multiplier"],
                            "equilibrist_roster_spread_ratio": 0.1,
                            "challenger_roster_spread_ratio": 0.2,
                            "equilibrist_fallback_gap_multiplier": p["spectrum_equilibrist_level_gap_tol_multiplier"],
                            "challenger_fallback_gap_multiplier": p["spectrum_challenger_level_gap_tol_multiplier"],
                            "classist_level_gap_tol_multiplier": p["spectrum_classist_level_gap_tol_multiplier"],
                            "chill_players_threshold": p["spectrum_chill_players_chill_threshold"],
                        },
                    )

                    chosen = player.spec_chosen_history[round_idx]
                    gain = (
                        getattr(player, SPEC_KEY_TO_ATTR[chosen]) * triggers[chosen]
                        if chosen
                        else 0
                    )
                    spectrum = {
                        "values": {
                            spec: float(getattr(player, attr))
                            for spec, attr in SPEC_KEY_TO_ATTR.items()
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
    return out
