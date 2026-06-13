"""Tests for SessionOfRounds pickle round-trip and objective-function serialisation."""

from __future__ import annotations

import pickle
from types import SimpleNamespace

import pytest

import core.main as main
from core.main import (
    GamesRound,
    SessionOfRounds,
    mean_min_max_happiness_objective,
    mean_std_happiness_objective,
)

# ---------------------------------------------------------------------------
# Helper: build a small session
# ---------------------------------------------------------------------------


def _make_session():
    players = [main.Player(main.df_minimal_example.iloc[i]) for i in range(12)]
    return main.SessionOfRounds(
        players,
        amount_of_rounds=2,
        type_preferences=["balanced", "level"],
        gender_preferences=["open", "open"],
        level_gap_tol=2,
        num_iter=20,
        spectrum=False,
        seed=42,
    )


# ---------------------------------------------------------------------------
# Test 1 â€” round-trip: core data survives save/load
# ---------------------------------------------------------------------------


def test_pickle_session_round_trip(tmp_path):
    session = _make_session()
    pkl_file = tmp_path / "session.pkl"

    with open(pkl_file, "wb") as fh:
        pickle.dump(session, fh, protocol=pickle.HIGHEST_PROTOCOL)

    with open(pkl_file, "rb") as fh:
        loaded = pickle.load(fh)

    assert len(loaded.players) == len(
        session.players
    ), "Player count must survive round-trip"
    assert len(loaded.rounds) == len(
        session.rounds
    ), "Round count must survive round-trip"
    assert (
        loaded.type_preferences == session.type_preferences
    ), "type_preferences must survive"

    # Objective metadata must be stamped on both session and rounds
    assert (
        getattr(loaded, "_objective_function_name", None)
        == "mean_min_max_happiness_objective"
    )
    first_round = loaded.rounds[0]
    assert (
        getattr(first_round, "_objective_function_name", None)
        == "mean_min_max_happiness_objective"
    )


# ---------------------------------------------------------------------------
# Test 2 â€” objective function is re-callable after load
# ---------------------------------------------------------------------------


def test_pickle_objective_params_survive(tmp_path):
    session = _make_session()
    pkl_file = tmp_path / "session.pkl"

    with open(pkl_file, "wb") as fh:
        pickle.dump(session, fh, protocol=pickle.HIGHEST_PROTOCOL)
    with open(pkl_file, "rb") as fh:
        loaded = pickle.load(fh)

    first_round = loaded.rounds[0]
    lambda_w = getattr(first_round, "_objective_lambda_weight", None)
    percentile = getattr(first_round, "_objective_percentile", 10) or 10

    restored_score = first_round.objective_function(first_round)
    expected_score = mean_min_max_happiness_objective(
        first_round,
        lambda_weight=lambda_w if lambda_w is not None else 2,
        percentile=percentile,
    )
    assert (
        abs(restored_score - expected_score) < 1e-9
    ), f"Restored objective score {restored_score} != expected {expected_score}"


# ---------------------------------------------------------------------------
# Test 3 â€” legacy SessionOfRounds __setstate__ (std-marker with no lambda)
# ---------------------------------------------------------------------------


def test_pickle_legacy_session_setstate():
    legacy = SessionOfRounds.__new__(SessionOfRounds)
    legacy.__setstate__({"_objective_function_name": "mean_std_happiness_objective"})

    assert (
        getattr(legacy, "_objective_function_name", None)
        == "mean_std_happiness_objective"
    )
    # Legacy restore must fill in the default lambda_weight of 2
    assert getattr(legacy, "_objective_lambda_weight", None) == 2


# ---------------------------------------------------------------------------
# Test 4 -- legacy GamesRound __setstate__ evaluates correctly
# ---------------------------------------------------------------------------


def test_pickle_legacy_round_setstate():
    legacy_round = GamesRound.__new__(GamesRound)
    legacy_round.__setstate__(
        {"_objective_function_name": "mean_std_happiness_objective"}
    )
    # Attach minimal participants so the objective can be evaluated
    legacy_round.participants = [SimpleNamespace(happiness=h) for h in (1.0, 3.0, 5.0)]

    restored_score = legacy_round.objective_function(legacy_round)
    expected_score = mean_std_happiness_objective(legacy_round, lambda_weight=2)
    assert (
        abs(restored_score - expected_score) < 1e-9
    ), f"Legacy round score {restored_score} != expected {expected_score}"
    # Legacy restore must fill in the default lambda_weight of 2
    assert getattr(legacy, "_objective_lambda_weight", None) == 2


# ---------------------------------------------------------------------------
# Test 4 â€” legacy GamesRound __setstate__ evaluates correctly
# ---------------------------------------------------------------------------


def test_pickle_legacy_round_setstate():
    legacy_round = GamesRound.__new__(GamesRound)
    legacy_round.__setstate__(
        {"_objective_function_name": "mean_std_happiness_objective"}
    )
    # Attach minimal participants so the objective can be evaluated
    legacy_round.participants = [SimpleNamespace(happiness=h) for h in (1.0, 3.0, 5.0)]

    restored_score = legacy_round.objective_function(legacy_round)
    expected_score = mean_std_happiness_objective(legacy_round, lambda_weight=2)
    assert (
        abs(restored_score - expected_score) < 1e-9
    ), f"Legacy round score {restored_score} != expected {expected_score}"


import core.main as main
import pickle
import os
from datetime import datetime
from types import SimpleNamespace
