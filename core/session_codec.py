"""session_codec.py - JSON-safe session documents.

A session document only stores inputs (players, parameters, preferred pairs)
and the structure of each round (teams and bench, by player name). Happiness
and every derived statistic are recomputed from that structure, so a document
can be loaded without unpickling anything.
"""

import numpy as np
import pandas as pd

from core.algorithm import apply_preferred_pairs_happiness
from core.models import (
    GameOfFour,
    GamesRound,
    Player,
    SessionOfRounds,
    TeamOfTwo,
    mean_min_max_happiness_objective,
)

DOCUMENT_VERSION = 1

PLAYER_FIELDS = [
    "Name",
    "Surname",
    "Level",
    "Gender",
    "Prey",
    "Equilibrist",
    "Challenger",
    "Chill",
    "Hunter",
    "Classist",
]

DEFAULT_PARAMS = {
    "level_gap_tol": 1.1,
    "games_per_round": "auto",
    "num_iter": 435,
    "lambda_weight": 2.0,
    "percentile": 33,
    "weight_same_teammate": 5,
    "never_met_bonus_per_player": 2,
    "never_met_bonus_cap": 4,
    "spectrum": True,
    "extra_parameters": {},
}


def players_dataframe(players):
    """Build the DataFrame the engine expects from a list of player dicts keyed by id."""
    rows = []
    for p in players:
        row = {field: p.get(field) for field in PLAYER_FIELDS}
        for spec in PLAYER_FIELDS[4:]:
            row[spec] = 5 if row[spec] is None else row[spec]
        row["Level"] = float(row["Level"])
        row["Category"] = row["Level"]
        row["Happiness"] = 0
        row["Games played"] = 0
        row["Noisy level"] = 0
        rows.append(row)
    df = pd.DataFrame(rows, index=[p["id"] for p in players])
    df.index.name = "NameSurname"
    return df


def encode_session(session, players, params, preferred_pairs, seed=None):
    """Return the JSON document for a generated or edited session."""
    params = dict(params or {})
    games_per_round_pref = getattr(session, "_games_per_round_preference", None)
    if games_per_round_pref is not None:
        params.setdefault("games_per_round", games_per_round_pref)

    rounds = []
    for r in session.rounds:
        rounds.append(
            {
                "type_preference": r.type_preference,
                "gender_preference": r.gender_preference,
                "games": [
                    {
                        "team_a": [p.name for p in g.team_A.players],
                        "team_b": [p.name for p in g.team_B.players],
                    }
                    for g in r.games
                ],
                "bench": [p.name for p in r.not_playing],
            }
        )
    return {
        "version": DOCUMENT_VERSION,
        "seed": seed,
        "players": players,
        "params": params,
        "preferred_pairs": [
            {"players": sorted(pair), "games": int(n)} for pair, n in preferred_pairs
        ],
        "rounds": rounds,
    }


def _pairs_from_document(doc):
    return [
        (frozenset(entry["players"]), int(entry.get("games", 1)))
        for entry in doc.get("preferred_pairs", [])
    ]


def decode_session(doc):
    """Rebuild a SessionOfRounds from a document and recompute all happiness."""
    params = {**DEFAULT_PARAMS, **(doc.get("params") or {})}
    extra = params.get("extra_parameters") or {}
    df = players_dataframe(doc["players"])
    players = [Player(df.loc[pid]) for pid in df.index]
    by_name = {p.name: p for p in players}
    lambda_weight = float(params["lambda_weight"])
    percentile = float(params["percentile"])

    def objective(x):
        return mean_min_max_happiness_objective(
            x, lambda_weight=lambda_weight, percentile=percentile
        )

    session = SessionOfRounds.__new__(SessionOfRounds)
    session.players = players
    session.players_name = [p.name for p in players]
    session.amount_of_rounds = len(doc["rounds"])
    session.level_gap_tol = float(params["level_gap_tol"])
    session.num_iter = int(params["num_iter"])
    session.spectrum = bool(params["spectrum"])
    session.objective_function = objective
    session.weight_same_teammate = params["weight_same_teammate"]
    session.never_met_bonus_per_player = params["never_met_bonus_per_player"]
    session.never_met_bonus_cap = params["never_met_bonus_cap"]
    session.extra_parameters = extra
    session.game_optimization = extra.get("game_optimization", {})
    session.happiness_config = extra.get("happiness", {})
    session.prioritize_level_rounds = True
    session.rounds_reordering = params.get("rounds_reordering")
    session._games_per_round_preference = params.get("games_per_round", "auto")
    session.type_preferences = [r["type_preference"] for r in doc["rounds"]]
    session.gender_preferences = [r["gender_preference"] for r in doc["rounds"]]
    session.games_per_round_each_round = [len(r["games"]) for r in doc["rounds"]]
    session.players_per_team_each_round = [2] * len(doc["rounds"])
    session._calculate_gender_distribution()
    median_level = np.median([p.level for p in players])

    session.rounds = []
    for r in doc["rounds"]:
        round_ = GamesRound.__new__(GamesRound)
        round_.type_preference = r["type_preference"]
        round_.gender_preference = r["gender_preference"]
        round_.minority_gender = session.minority_gender
        round_.gender_level_medians = session.gender_level_medians
        round_.participants = players
        round_.participants_names = session.players_name
        round_.previous_games = []
        round_.previous_teams = set()
        round_.previous_team_frozensets = set()
        round_.teams_per_game = 2
        round_.players_per_team = 2
        round_.num_iter = session.num_iter
        round_.level_gap_tol = session.level_gap_tol
        round_.spectrum = session.spectrum
        round_.objective_function = objective
        round_.never_met_bonus_per_player = session.never_met_bonus_per_player
        round_.never_met_bonus_cap = session.never_met_bonus_cap
        round_.game_optimization = session.game_optimization
        round_.happiness_config = session.happiness_config
        round_._params = round_._resolve_params()
        round_.session_median_level = median_level
        round_.weight_same_teammate = session.weight_same_teammate
        round_.iterations = []
        round_.amount_of_games = len(r["games"])
        round_.games = []
        for g in r["games"]:
            team_a = TeamOfTwo(*[by_name[n] for n in g["team_a"]])
            team_b = TeamOfTwo(*[by_name[n] for n in g["team_b"]])
            round_.games.append(
                GameOfFour(
                    team_a,
                    team_b,
                    type_preference=round_.type_preference,
                    gender_preference=round_.gender_preference,
                    weight_same_teammate=session.weight_same_teammate,
                )
            )
        round_.not_playing = [by_name[n] for n in r["bench"]]
        round_.people_playing = [p for g in round_.games for p in g.participants]
        round_.teams = set()
        for g in round_.games:
            round_.teams |= g.teams
        session.rounds.append(round_)

    recompute_session(session, _pairs_from_document(doc))
    return session


def recompute_session(session, preferred_pairs):
    """Recompute happiness, histories, games played and stats from the round structure."""
    num_rounds = len(session.rounds)
    for player in session.players:
        player.happiness = 0
        player.games_played = 0
        player.happiness_gained_history = [None] * num_rounds
        player.teammate_history = [frozenset()] * num_rounds
        player.other_players_in_same_game_history = [frozenset()] * num_rounds
        player.spec_chosen_history = [None] * num_rounds
    for r_idx, round_ in enumerate(session.rounds):
        round_.recalculate_happiness(r_idx)
        for game in round_.games:
            for player in game.participants:
                player.games_played += 1
    session._pair_happiness_per_round = {
        p.name: [0] * num_rounds for p in session.players
    }
    if preferred_pairs:
        apply_preferred_pairs_happiness(session, preferred_pairs)
    session.recalculate_session_statistics()
    return session
