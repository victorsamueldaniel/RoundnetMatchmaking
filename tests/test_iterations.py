"""Tests for iteration tracking and seed optimisation in GamesRound / SessionOfRounds."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.main import (
    GamesRound,
    Player,
    SessionOfRounds,
    run_session_generation_with_seed_optimization,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _ParticipantsView:
    def __init__(self, participants):
        self.participants = participants


# ---------------------------------------------------------------------------
# Test 1 â€” balanced round: .iterations is populated with expected keys
# ---------------------------------------------------------------------------


def test_balanced_round_iterations_exist(players_8):
    round_obj = GamesRound(
        players_8,
        type_preference="balanced",
        gender_preference=None,
        num_iter=10,
        level_gap_tol=2,
        seed=42,
    )
    assert hasattr(round_obj, "iterations"), "GamesRound must have .iterations"
    assert len(round_obj.iterations) > 0, "Expected at least one iteration entry"
    assert len(round_obj.games) > 0, "Expected at least one game to be created"

    for entry in round_obj.iterations:
        assert "meets_tolerance" in entry, "Missing key: meets_tolerance"
        assert "selected" in entry, "Missing key: selected"
        if entry["meets_tolerance"]:
            assert entry["score"] is not None, "Scored iteration must have a score"
            assert isinstance(entry["score"], float), "Score must be a float"

    selected = [e for e in round_obj.iterations if e.get("selected")]
    assert len(selected) == 1, "Exactly one iteration must be marked selected"


# ---------------------------------------------------------------------------
# Test 2 â€” level round: .iterations populated with expected keys
# ---------------------------------------------------------------------------


def test_level_round_iterations_exist(players_8):
    round_obj = GamesRound(
        players_8,
        type_preference="level",
        gender_preference=None,
        num_iter=10,
        level_gap_tol=2,
        seed=42,
    )
    assert hasattr(round_obj, "iterations"), "GamesRound must have .iterations"
    assert len(round_obj.iterations) > 0, "Expected at least one iteration entry"
    assert len(round_obj.games) > 0, "Expected at least one game to be created"

    for entry in round_obj.iterations:
        assert "game_num" in entry, "Missing key: game_num"
        assert "level_diff" in entry, "Missing key: level_diff"
        assert "teams" in entry, "Missing key: teams"
        assert "selected" in entry, "Missing key: selected"
        assert isinstance(entry["level_diff"], float), "level_diff must be a float"

    selected = [e for e in round_obj.iterations if e.get("selected")]
    assert len(selected) >= 1, "At least one iteration must be marked selected"


# ---------------------------------------------------------------------------
# Test 3 â€” session: every round has .iterations
# ---------------------------------------------------------------------------


def test_session_round_iterations_exist(players_8):
    session = SessionOfRounds(
        players_8,
        amount_of_rounds=2,
        type_preferences=["balanced", "level"],
        gender_preferences=["open", "open"],
        level_gap_tol=2,
        num_iter=10,
        seed=42,
    )
    assert len(session.rounds) == 2, "Expected 2 rounds"
    for i, round_obj in enumerate(session.rounds):
        assert hasattr(round_obj, "iterations"), f"Round {i} missing .iterations"
        assert isinstance(
            round_obj.iterations, list
        ), f"Round {i} .iterations must be a list"


# ---------------------------------------------------------------------------
# Test 4 â€” sit-out fairness tie-break
# ---------------------------------------------------------------------------


def test_sitout_fairness_tiebreak():
    """In a 6-player/1-game round the happiest player(s) are benched first."""
    df_fair = pd.DataFrame(
        {
            "Name": ["P1", "P2", "P3", "P4", "P5", "P6"],
            "Surname": ["S"] * 6,
            "Level": [2.0, 2.2, 2.4, 2.6, 2.8, 3.0],
            "Noisy level": [0.0] * 6,
            "Gender": ["Male", "Female", "Male", "Female", "Male", "Female"],
            "Games played": [1] * 6,
            "Happiness": [0.0, 1.0, 2.0, 3.0, 4.0, 5.0],
        }
    )
    df_fair.set_index("Name", inplace=True)

    fair_players = [Player(df_fair.iloc[i]) for i in range(6)]
    bench_count = len(df_fair) - 4  # 1 game x 4 players
    expected_benched = set(
        df_fair.sort_values("Happiness", ascending=False).head(bench_count).index
    )

    fair_round = GamesRound(
        fair_players,
        amount_of_games=1,
        type_preference="level",
        gender_preference=None,
        level_gap_tol=3,
        seed=123,
    )
    actual_benched = {p.name for p in fair_round.not_playing}

    assert (
        actual_benched == expected_benched
    ), f"Fairness tie-break mismatch: expected {expected_benched}, got {actual_benched}"


# ---------------------------------------------------------------------------
# Test 5 â€” iterations telemetry: pass metadata and selected candidate
# ---------------------------------------------------------------------------


def test_iterations_telemetry_keys():
    """When mixed gender is impossible, pass_num=1 is used and exactly one row is selected."""
    df_all_male = pd.DataFrame(
        {
            "Name": ["A", "B", "C", "D"],
            "Surname": ["X"] * 4,
            "Level": [2.0, 2.1, 2.2, 2.3],
            "Noisy level": [0.0] * 4,
            "Gender": ["Male", "Male", "Male", "Male"],
            "Games played": [0] * 4,
            "Happiness": [0.0] * 4,
        }
    )
    df_all_male.set_index("Name", inplace=True)

    gender_players = [Player(df_all_male.iloc[i]) for i in range(4)]
    mixed_round = GamesRound(
        gender_players,
        amount_of_games=1,
        type_preference="balanced",
        gender_preference="mixed",
        num_iter=20,
        level_gap_tol=3,
        seed=7,
    )

    assert mixed_round.iterations, "Expected non-empty iterations telemetry"
    for entry in mixed_round.iterations:
        assert "pass_num" in entry, "Missing key: pass_num"
        assert "gender_enforced" in entry, "Missing key: gender_enforced"
        assert "selected" in entry, "Missing key: selected"

    assert any(
        e["pass_num"] == 1 for e in mixed_round.iterations
    ), "Expected pass-1 iterations when mixed gender is impossible"

    selected = [e for e in mixed_round.iterations if e.get("selected")]
    assert len(selected) == 1, "Exactly one iteration row must be marked selected"
    assert selected[0]["pass_num"] == 1, "Selected iteration must come from pass 1"
    assert selected[0]["score"] is not None, "Selected iteration must have a score"


# ---------------------------------------------------------------------------
# Test 6 â€” seed ranking uses the provided objective function
# ---------------------------------------------------------------------------


def test_seed_ranking_uses_custom_objective(df_8):
    """run_session_generation_with_seed_optimization picks the seed that scores highest
    under the caller-supplied objective function."""

    def custom_objective(view):
        values = [p.happiness for p in view.participants]
        return float(min(values) * 1000 + np.mean(values))

    kwargs = dict(
        df=df_8,
        amount_of_rounds=3,
        type_preferences=["balanced", "balanced", "level"],
        gender_preferences=["open", "open", "open"],
        level_gap_tol=2.0,
        num_iter=20,
        lambda_weight=0.1,
        spectrum=False,
        games_per_round_each_round=2,
        objective_function=custom_objective,
        print_progress=False,
    )

    manual_scores: dict[int, float] = {}
    for seed in range(3):
        single, _ = run_session_generation_with_seed_optimization(
            first_seed=seed, last_seed=seed, **kwargs
        )
        manual_scores[seed] = custom_objective(_ParticipantsView(single.players))

    expected_seed = max(manual_scores, key=manual_scores.get)

    _, chosen_seed = run_session_generation_with_seed_optimization(
        first_seed=0, last_seed=2, **kwargs
    )

    assert chosen_seed == expected_seed, (
        f"Seed mismatch: manual scores={manual_scores}, "
        f"expected seed {expected_seed}, got {chosen_seed}"
    )


# ---------------------------------------------------------------------------
# Test 7 -- balanced iteration count is bounded by num_iter
# ---------------------------------------------------------------------------


def test_iteration_budget_bound(players_8):
    """Number of balanced iterations must not exceed num_iter."""
    num_iter = 5
    round_obj = GamesRound(
        players_8,
        type_preference="balanced",
        gender_preference=None,
        num_iter=num_iter,
        level_gap_tol=2,
        seed=42,
    )
    assert (
        len(round_obj.iterations) <= num_iter
    ), f"Iteration count {len(round_obj.iterations)} exceeds budget {num_iter}"


# ---------------------------------------------------------------------------
# Test 7 â€” balanced iteration count is bounded by num_iter
# ---------------------------------------------------------------------------


def test_iteration_budget_bound(players_8):
    """Number of balanced iterations must not exceed num_iter."""
    num_iter = 5
    round_obj = GamesRound(
        players_8,
        type_preference="balanced",
        gender_preference=None,
        num_iter=num_iter,
        level_gap_tol=2,
        seed=42,
    )
    assert (
        len(round_obj.iterations) <= num_iter
    ), f"Iteration count {len(round_obj.iterations)} exceeds budget {num_iter}"
