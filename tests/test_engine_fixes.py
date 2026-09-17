"""Regression tests for the balanced search, level noise and bench histories."""

import numpy as np
import pandas as pd

from core.algorithm import force_preferred_pairs_in_session
from core.models import GamesRound, Player, SessionOfRounds


def _make_players(n=20, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        rows.append(
            {
                "Name": f"P{i}",
                "Surname": "X",
                "Level": float(np.round(rng.uniform(1, 4), 1)),
                "Gender": "Male" if i % 3 else "Female",
                "Happiness": 0,
                "Games played": 0,
                **{
                    k: int(rng.integers(0, 11))
                    for k in [
                        "Prey",
                        "Equilibrist",
                        "Challenger",
                        "Chill",
                        "Hunter",
                        "Classist",
                    ]
                },
            }
        )
    df = pd.DataFrame(rows, index=[f"P{i}" for i in range(n)])
    return [Player(df.loc[name]) for name in df.index]


def test_balanced_search_varies_every_game():
    players = _make_players(20)
    round_ = GamesRound(
        players,
        type_preference="balanced",
        gender_preference="open",
        num_iter=200,
        level_gap_tol=3,
        seed=1,
    )
    combos = [it["games"] for it in round_.iterations if it["pass_num"] == 0]
    first_games = {frozenset(c[0].participants) for c in combos}
    assert len(combos) == 200
    assert len(first_games) > 50


def test_balanced_search_is_deterministic_for_a_seed():
    def signature(seed):
        round_ = GamesRound(
            _make_players(16),
            type_preference="balanced",
            num_iter=50,
            level_gap_tol=3,
            seed=seed,
        )
        return sorted(sorted(p.name for p in g.participants) for g in round_.games)

    assert signature(4) == signature(4)


def test_level_noise_differs_between_players():
    players = _make_players(12)
    round_ = GamesRound(
        players, type_preference="level", num_iter=10, level_gap_tol=3, seed=7
    )
    offsets = {
        round(round_._level_sorter(p, seed=7)[0] - round(p.level), 9) for p in players
    }
    assert len(offsets) > 1


def test_histories_have_one_entry_per_round_for_benched_players():
    players = _make_players(18)
    session = SessionOfRounds(players, amount_of_rounds=4, num_iter=30, seed=2)
    for p in session.players:
        assert len(p.teammate_history) == 4
        assert len(p.other_players_in_same_game_history) == 4
        assert len(p.happiness_gained_history) == 4


def test_swap_and_swap_back_restores_happiness_without_reordering():
    players = _make_players(18)
    session = SessionOfRounds(players, amount_of_rounds=4, num_iter=30, seed=3)
    round_ = session.rounds[1]
    before = {p.name: p.happiness for p in session.players}
    pos_a, pos_b = ("game", 0, "A", 0), ("not_playing", 0)
    for _ in range(2):
        round_.swap_player_positions(pos_a, pos_b)
        round_.recalculate_happiness(1)
    after = {p.name: p.happiness for p in session.players}
    assert after == before


def test_force_pairs_threshold_with_negative_score():
    players = _make_players(16)
    session = SessionOfRounds(players, amount_of_rounds=3, num_iter=30, seed=5)
    names = [p.name for p in session.players]
    # A huge lambda makes the base score negative; the call must still be able to pair players.
    force_preferred_pairs_in_session(
        session, [(frozenset(names[:2]), 1)], lambda_weight=50, score_tolerance=0.5
    )
    together = sum(
        1
        for r in session.rounds
        for g in r.games
        for t in g.teams
        if {p.name for p in t.players} == set(names[:2])
    )
    assert together >= 1


def test_round_without_games_benches_everyone_and_stays_consistent():
    from core.session_codec import decode_session, encode_session

    players = _make_players(16)
    session = SessionOfRounds(
        players,
        amount_of_rounds=3,
        type_preferences=["level", "balanced", "level"],
        level_gap_tol=0.0,
        num_iter=5,
        seed=1,
    )
    empty = [r for r in session.rounds if not r.games]
    assert empty, "a zero tolerance should leave at least one round without games"
    assert any(r.games for r in session.rounds)
    for r in empty:
        assert len(r.not_playing) == len(players)
    documents = [
        {
            "id": p.name,
            "Name": p.name,
            "Surname": "",
            "Level": p.level,
            "Gender": p.gender,
            **{k: getattr(p, k.lower()) for k in ["Prey", "Equilibrist", "Challenger", "Chill", "Hunter", "Classist"]},
        }
        for p in players
    ]
    reloaded = decode_session(encode_session(session, documents, {"level_gap_tol": 0.0}, []))
    assert {p.name: p.happiness for p in reloaded.players} == {p.name: p.happiness for p in session.players}
