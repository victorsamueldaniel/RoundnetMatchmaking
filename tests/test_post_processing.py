"""Tests for force_preferred_pairs_in_session and apply_preferred_pairs_happiness."""

from __future__ import annotations

import pandas as pd
import pytest

from core.models import Player, SessionOfRounds
from core.algorithm import (
    force_preferred_pairs_in_session,
    apply_preferred_pairs_happiness,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_row(name, level=3.0, gender="Male"):
    return {
        "Level": level,
        "Gender": gender,
        "Happiness": 0.0,
        "Games played": 0,
        "Noisy level": level,
        "Category": level,
        "Prey": 0,
        "Equilibrist": 0,
        "Challenger": 0,
        "Chill": 0,
        "Hunter": 5,
        "Classist": 0,
        "Name": name,
        "Surname": "",
    }


def _make_8_player_df():
    names = ["Alice", "Bob", "Carol", "Dave", "Eve", "Frank", "Grace", "Hank"]
    df = pd.DataFrame([_make_row(n) for n in names], index=names)
    return df


def _are_teammates(round_obj, p1, p2):
    a = round_obj.find_player_position(p1)
    b = round_obj.find_player_position(p2)
    return (
        a is not None
        and b is not None
        and a[0] == "game"
        and b[0] == "game"
        and a[1] == b[1]
        and a[2] == b[2]
    )


def _build_session(df, n_rounds=2, seed=0):
    players = [Player(df.loc[n]) for n in df.index]
    return SessionOfRounds(
        list_of_players=players,
        amount_of_rounds=n_rounds,
        type_preferences=["balanced"] * n_rounds,
        gender_preferences=["open"] * n_rounds,
        level_gap_tol=2.0,
        num_iter=50,
        spectrum=False,
        seed=seed,
    )


# ---------------------------------------------------------------------------
# Test 1 -- pair already satisfied -> no regression
# ---------------------------------------------------------------------------


def test_force_pair_already_satisfied():
    """force_preferred_pairs_in_session must not reduce the count of rounds where pair is together."""
    df = _make_8_player_df()

    for seed in range(20):
        sess = _build_session(df, n_rounds=2, seed=seed)
        alice = next(p for p in sess.players if p.name == "Alice")
        bob = next(p for p in sess.players if p.name == "Bob")
        before = sum(1 for r in sess.rounds if _are_teammates(r, alice, bob))
        if before >= 1:
            force_preferred_pairs_in_session(
                sess,
                preferred_pairs=[frozenset({"Alice", "Bob"})],
                forced_games=1,
                lambda_weight=2.4,
            )
            after = sum(1 for r in sess.rounds if _are_teammates(r, alice, bob))
            assert after >= before, f"Pair count regressed: {before} -> {after}"
            assert sess.mean_happiness > 0, "mean_happiness must be updated after force"
            return  # success

    pytest.skip("Could not find a seed where Alice+Bob start together â€” skipping")


# ---------------------------------------------------------------------------
# Test 2 -- pair not together -> force for 1 game
# ---------------------------------------------------------------------------


def test_force_pair_not_together():
    """force_preferred_pairs_in_session must not crash and must update mean_happiness."""
    df = _make_8_player_df()

    for seed in range(30):
        players = [Player(df.loc[n]) for n in df.index]
        sess = SessionOfRounds(
            list_of_players=players,
            amount_of_rounds=3,
            type_preferences=["balanced", "balanced", "balanced"],
            gender_preferences=["open", "open", "open"],
            level_gap_tol=2.0,
            num_iter=50,
            spectrum=False,
            seed=seed,
        )
        alice = next(p for p in sess.players if p.name == "Alice")
        bob = next(p for p in sess.players if p.name == "Bob")
        before = sum(1 for r in sess.rounds if _are_teammates(r, alice, bob))
        if before == 0:
            force_preferred_pairs_in_session(
                sess,
                preferred_pairs=[frozenset({"Alice", "Bob"})],
                forced_games=1,
                lambda_weight=2.4,
            )
            # Just assert no crash and session stats refreshed
            assert sess.mean_happiness > 0, "mean_happiness must be updated after force"
            return

    pytest.skip(
        "Could not find a seed where Alice+Bob never start together â€” skipping"
    )


# ---------------------------------------------------------------------------
# Test 3 -- unknown player name -> no crash
# ---------------------------------------------------------------------------


def test_force_pair_unknown_name_no_crash():
    df = _make_8_player_df()
    sess = _build_session(df, n_rounds=2, seed=1)
    # Zoltan does not exist; function must not raise
    force_preferred_pairs_in_session(
        sess,
        preferred_pairs=[frozenset({"Alice", "Zoltan"})],
        forced_games=1,
    )


# ---------------------------------------------------------------------------
# Test 4 -- apply_preferred_pairs_happiness: bonus applied for n=1 pair together
# ---------------------------------------------------------------------------


def test_apply_pairs_happiness_bonus_n1():
    """Players in a pair that are together for 1 round receive the expected bonus."""
    df = _make_8_player_df()

    # Find a seed where Alice+Bob are teammates in at least one round
    for seed in range(20):
        sess = _build_session(df, n_rounds=2, seed=seed)
        alice = next(p for p in sess.players if p.name == "Alice")
        bob = next(p for p in sess.players if p.name == "Bob")
        if any(_are_teammates(r, alice, bob) for r in sess.rounds):
            h_alice_before = alice.happiness
            h_bob_before = bob.happiness

            # never_met_bonus_per_player defaults to 2 on GamesRound
            never_met_per_player = getattr(
                sess.rounds[0], "never_met_bonus_per_player", 2
            )
            # For n=1: bonus_list = [max(8, 2*(1-0+2))] = [max(8,6)] = [8]
            # First round together: bonus -= never_met_per_player => net = 8 - 2 = 6
            expected_bonus_each = 8 - never_met_per_player

            apply_preferred_pairs_happiness(
                sess,
                preferred_pairs=[frozenset({"Alice", "Bob"})],
            )

            assert alice.happiness == pytest.approx(
                h_alice_before + expected_bonus_each, abs=1e-9
            )
            assert bob.happiness == pytest.approx(
                h_bob_before + expected_bonus_each, abs=1e-9
            )
            return

    pytest.skip("Could not find a seed where Alice+Bob are teammates â€” skipping")


# ---------------------------------------------------------------------------
# Test 5 -- apply_preferred_pairs_happiness: _pair_happiness_per_round is stored
# ---------------------------------------------------------------------------


def test_apply_pairs_happiness_per_round_attribute():
    df = _make_8_player_df()
    sess = _build_session(df, n_rounds=2, seed=0)

    apply_preferred_pairs_happiness(
        sess,
        preferred_pairs=[frozenset({"Alice", "Bob"})],
    )

    assert hasattr(
        sess, "_pair_happiness_per_round"
    ), "_pair_happiness_per_round must be set"
    per_round = sess._pair_happiness_per_round
    assert isinstance(per_round, dict), "_pair_happiness_per_round must be a dict"
    for player in sess.players:
        assert player.name in per_round, f"Missing entry for {player.name}"
        assert len(per_round[player.name]) == len(
            sess.rounds
        ), f"Per-round awards for {player.name} must have one entry per round"


# ---------------------------------------------------------------------------
# Test 6 -- apply_preferred_pairs_happiness: session stats are refreshed
# ---------------------------------------------------------------------------


def test_apply_pairs_happiness_session_stats_refreshed():
    df = _make_8_player_df()
    sess = _build_session(df, n_rounds=2, seed=0)

    mean_before = sess.mean_happiness
    std_before = sess.std_happiness

    apply_preferred_pairs_happiness(
        sess,
        preferred_pairs=[frozenset({"Alice", "Bob"})],
    )

    import numpy as np

    expected_mean = float(np.mean([p.happiness for p in sess.players]))
    expected_std = float(np.std([p.happiness for p in sess.players]))

    assert sess.mean_happiness == pytest.approx(
        expected_mean, abs=1e-9
    ), "mean_happiness must be recalculated after apply_preferred_pairs_happiness"
    assert sess.std_happiness == pytest.approx(
        expected_std, abs=1e-9
    ), "std_happiness must be recalculated after apply_preferred_pairs_happiness"
