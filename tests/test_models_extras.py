"""Tests for model helpers not covered elsewhere:
compute_session_score, reorder_rounds, GameOfFour, TeamOfTwo.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.models import (
    GameOfFour,
    GamesRound,
    Player,
    SessionOfRounds,
    TeamOfTwo,
    compute_session_score,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _player(
    name: str, happiness: float, level: float = 2.0, gender: str = "Male"
) -> Player:
    series = pd.Series(
        {
            "Level": level,
            "Gender": gender,
            "Happiness": happiness,
            "Games played": 0,
            "Noisy level": level,
            "Prey": 0,
            "Equilibrist": 0,
            "Challenger": 0,
            "Chill": 0,
            "Hunter": 5,
            "Classist": 0,
            "Surname": "",
        },
        name=name,
    )
    return Player(series)


def _team(p1, p2):
    return TeamOfTwo(p1, p2)


def _game(p1, p2, p3, p4, gender_preference=None):
    t1 = TeamOfTwo(p1, p2, gender_preference=gender_preference)
    t2 = TeamOfTwo(p3, p4, gender_preference=gender_preference)
    return GameOfFour(t1, t2, gender_preference=gender_preference)


# ---------------------------------------------------------------------------
# compute_session_score
# ---------------------------------------------------------------------------


class _TestComputeSessionScore:
    def test_mean_happiness(self):
        players = [_player(f"p{i}", float(i)) for i in range(5)]
        score = compute_session_score(players, "mean_happiness_objective")
        assert score == pytest.approx(np.mean([0, 1, 2, 3, 4]))

    def test_mean_min_max_happiness(self):
        players = [_player(f"p{i}", float(i)) for i in range(5)]
        lw, pct = 2.4, 10
        all_h = [0.0, 1.0, 2.0, 3.0, 4.0]
        bottom_threshold = np.percentile(all_h, pct)
        bottom_vals = [h for h in all_h if h <= bottom_threshold]
        expected = np.mean(all_h) + lw * np.mean(bottom_vals)
        score = compute_session_score(
            players,
            "mean_min_max_happiness_objective",
            lambda_weight=lw,
            percentile=pct,
        )
        assert score == pytest.approx(float(expected), abs=1e-9)

    def test_std_happiness(self):
        players = [_player(f"p{i}", float(i)) for i in range(5)]
        score = compute_session_score(players, "std_happiness_objective")
        assert score == pytest.approx(float(np.std([0, 1, 2, 3, 4])))

    def test_mean_std_happiness(self):
        players = [_player(f"p{i}", float(i)) for i in range(5)]
        lw = 2.0
        all_h = [0.0, 1.0, 2.0, 3.0, 4.0]
        expected = np.mean(all_h) - lw * np.std(all_h)
        score = compute_session_score(
            players, "mean_std_happiness_objective", lambda_weight=lw
        )
        assert score == pytest.approx(float(expected), abs=1e-9)

    def test_empty_players_returns_zero(self):
        assert compute_session_score([], "mean_happiness_objective") == 0.0

    def test_none_objective_uses_default(self):
        """None objective name falls back to mean_min_max_happiness_objective."""
        players = [_player(f"p{i}", float(i)) for i in range(4)]
        score_explicit = compute_session_score(
            players,
            "mean_min_max_happiness_objective",
            lambda_weight=2.4,
            percentile=10,
        )
        score_none = compute_session_score(
            players, None, lambda_weight=2.4, percentile=10
        )
        assert score_explicit == pytest.approx(score_none, abs=1e-9)


# Instantiate as functions so pytest discovers them
def test_compute_session_score_mean_happiness():
    _TestComputeSessionScore().test_mean_happiness()


def test_compute_session_score_mean_min_max():
    _TestComputeSessionScore().test_mean_min_max_happiness()


def test_compute_session_score_std():
    _TestComputeSessionScore().test_std_happiness()


def test_compute_session_score_mean_std():
    _TestComputeSessionScore().test_mean_std_happiness()


def test_compute_session_score_empty():
    _TestComputeSessionScore().test_empty_players_returns_zero()


def test_compute_session_score_none_name():
    _TestComputeSessionScore().test_none_objective_uses_default()


# ---------------------------------------------------------------------------
# TeamOfTwo
# ---------------------------------------------------------------------------


def test_teamoftwo_mixed_flag_true():
    pa = _player("A", 0.0, gender="Male")
    pb = _player("B", 0.0, gender="Female")
    team = _team(pa, pb)
    assert team.mixed is True
    assert team.male is False
    assert team.female is False


def test_teamoftwo_mixed_flag_false_male():
    pa = _player("A", 0.0, gender="Male")
    pb = _player("B", 0.0, gender="Male")
    team = _team(pa, pb)
    assert team.mixed is False
    assert team.male is True


def test_teamoftwo_mean_level():
    pa = _player("A", 0.0, level=2.0)
    pb = _player("B", 0.0, level=4.0)
    team = _team(pa, pb)
    assert team.mean_level == pytest.approx(3.0)


def test_teamoftwo_same_players():
    pa = _player("A", 0.0)
    pb = _player("B", 0.0)
    pc = _player("C", 0.0)
    t1 = TeamOfTwo(pa, pb)
    t2 = TeamOfTwo(pb, pa)
    t3 = TeamOfTwo(pa, pc)
    assert t1.same_players(t2) is True
    assert t1.same_players(t3) is False


# ---------------------------------------------------------------------------
# GameOfFour — compute_gender_preference_score
# ---------------------------------------------------------------------------


def test_gender_preference_mixed_satisfied():
    # 2M + 2F split evenly into mixed teams
    m1 = _player("M1", 0.0, gender="Male")
    m2 = _player("M2", 0.0, gender="Male")
    f1 = _player("F1", 0.0, gender="Female")
    f2 = _player("F2", 0.0, gender="Female")
    game = _game(m1, f1, m2, f2, gender_preference="mixed")
    assert game.compute_gender_preference_score() == 1
    assert game.is_gender_preference_satisfied is True


def test_gender_preference_mixed_not_satisfied():
    # 3M + 1F: teams cannot both be mixed
    m1 = _player("M1", 0.0, gender="Male")
    m2 = _player("M2", 0.0, gender="Male")
    m3 = _player("M3", 0.0, gender="Male")
    f1 = _player("F1", 0.0, gender="Female")
    game = _game(m1, m2, m3, f1, gender_preference="mixed")
    assert game.compute_gender_preference_score() == 0
    assert game.is_gender_preference_satisfied is False


def test_gender_preference_open_always_satisfied():
    m1 = _player("M1", 0.0, gender="Male")
    m2 = _player("M2", 0.0, gender="Male")
    m3 = _player("M3", 0.0, gender="Male")
    m4 = _player("M4", 0.0, gender="Male")
    game = _game(m1, m2, m3, m4, gender_preference="open")
    assert game.compute_gender_preference_score() == 1


def test_gender_preference_none_always_satisfied():
    m1 = _player("M1", 0.0, gender="Male")
    m2 = _player("M2", 0.0, gender="Male")
    f1 = _player("F1", 0.0, gender="Female")
    f2 = _player("F2", 0.0, gender="Female")
    game = _game(m1, m2, f1, f2, gender_preference=None)
    assert game.compute_gender_preference_score() == 1


# ---------------------------------------------------------------------------
# SessionOfRounds.reorder_rounds
# ---------------------------------------------------------------------------


def _build_session_3r(players):
    return SessionOfRounds(
        list_of_players=players,
        amount_of_rounds=3,
        type_preferences=["balanced", "level", "balanced"],
        gender_preferences=["open", "open", "open"],
        level_gap_tol=2.0,
        num_iter=10,
        spectrum=False,
        seed=0,
        prioritize_level_rounds=False,  # keep the original order for this test
    )


def test_reorder_rounds_changes_round_order(players_8):
    sess = _build_session_3r(players_8)
    # Record round objects before reorder
    rounds_before = list(sess.rounds)
    # Apply reorder: [2, 3, 1] means new order is old[1], old[2], old[0]
    sess.reorder_rounds([2, 3, 1])
    assert sess.rounds[0] is rounds_before[1]
    assert sess.rounds[1] is rounds_before[2]
    assert sess.rounds[2] is rounds_before[0]


def test_reorder_rounds_preserves_player_history_length(players_8):
    sess = _build_session_3r(players_8)
    hist_len_before = {p.name: len(p.spec_chosen_history) for p in sess.players}
    sess.reorder_rounds([3, 1, 2])
    for p in sess.players:
        assert (
            len(p.spec_chosen_history) == hist_len_before[p.name]
        ), f"Player {p.name} spec_chosen_history length changed after reorder"
