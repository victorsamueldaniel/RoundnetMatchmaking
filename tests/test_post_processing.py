"""Tests for force_preferred_pairs_in_session and apply_preferred_pairs_happiness."""

from __future__ import annotations

import pandas as pd
import pytest

from core.models import Player, SessionOfRounds
from core.algorithm import (
    force_preferred_pairs_in_session,
    apply_preferred_pairs_happiness,
)
from core.happiness_breakdown import round_breakdown
from core.session_codec import decode_session

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


def _make_10_player_df():
    names = [
        "Alice",
        "Bob",
        "Carol",
        "Dave",
        "Eve",
        "Frank",
        "Grace",
        "Hank",
        "Ivy",
        "Jack",
    ]
    levels = [1.8, 2.0, 2.2, 2.4, 2.6, 2.8, 3.0, 3.2, 3.4, 3.6]
    genders = ["Female", "Male"] * 5
    df = pd.DataFrame(
        [
            _make_row(name, level=level, gender=gender)
            for name, level, gender in zip(names, levels, genders)
        ],
        index=names,
    )
    return df


def _games_played_from_structure(session):
    counts = {p.name: 0 for p in session.players}
    for round_obj in session.rounds:
        for game in round_obj.games:
            for participant in game.team_A.players + game.team_B.players:
                counts[participant.name] += 1
    return counts


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


def _two_round_repeat_document(preferred_pairs):
    players = [
        _make_row("Alice", gender="Female"),
        _make_row("Bob"),
        _make_row("Carol", gender="Female"),
        _make_row("Dave"),
    ]
    return {
        "version": 1,
        "players": [{"id": row["Name"], **row} for row in players],
        "params": {"spectrum": False, "weight_same_teammate": 5},
        "preferred_pairs": preferred_pairs,
        "rounds": [
            {
                "type_preference": "balanced",
                "gender_preference": "open",
                "games": [{"team_a": ["Alice", "Bob"], "team_b": ["Carol", "Dave"]}],
                "bench": [],
            },
            {
                "type_preference": "balanced",
                "gender_preference": "open",
                "games": [{"team_a": ["Alice", "Bob"], "team_b": ["Carol", "Dave"]}],
                "bench": [],
            },
        ],
    }


def _four_round_future_repeat_document(preferred_pairs):
    players = [
        _make_row("Alice", gender="Female"),
        _make_row("Bob"),
        _make_row("Carol", gender="Female"),
        _make_row("Dave"),
    ]
    return {
        "version": 1,
        "players": [{"id": row["Name"], **row} for row in players],
        "params": {"spectrum": False, "weight_same_teammate": 5},
        "preferred_pairs": preferred_pairs,
        "rounds": [
            {
                "type_preference": "balanced",
                "gender_preference": "open",
                "games": [{"team_a": ["Alice", "Bob"], "team_b": ["Carol", "Dave"]}],
                "bench": [],
            },
            {
                "type_preference": "balanced",
                "gender_preference": "open",
                "games": [{"team_a": ["Alice", "Carol"], "team_b": ["Bob", "Dave"]}],
                "bench": [],
            },
            {
                "type_preference": "balanced",
                "gender_preference": "open",
                "games": [{"team_a": ["Alice", "Dave"], "team_b": ["Bob", "Carol"]}],
                "bench": [],
            },
            {
                "type_preference": "balanced",
                "gender_preference": "open",
                "games": [{"team_a": ["Alice", "Bob"], "team_b": ["Carol", "Dave"]}],
                "bench": [],
            },
        ],
    }


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


def test_force_pair_with_bench_swap_keeps_games_played_in_sync():
    """Preferred-pair post-processing must keep live games_played aligned with round structure."""
    df = _make_10_player_df()

    for seed in range(40):
        baseline = SessionOfRounds(
            list_of_players=[Player(df.loc[n]) for n in df.index],
            amount_of_rounds=1,
            type_preferences=["balanced"],
            gender_preferences=["open"],
            level_gap_tol=10.0,
            num_iter=60,
            spectrum=False,
            seed=seed,
        )
        round_obj = baseline.rounds[0]
        benched_names = [p.name for p in round_obj.not_playing]
        active_names = [
            p.name
            for game in round_obj.games
            for p in game.team_A.players + game.team_B.players
        ]

        if not benched_names or not active_names:
            continue

        for benched_name in benched_names:
            for active_name in active_names:
                sess = SessionOfRounds(
                    list_of_players=[Player(df.loc[n]) for n in df.index],
                    amount_of_rounds=1,
                    type_preferences=["balanced"],
                    gender_preferences=["open"],
                    level_gap_tol=10.0,
                    num_iter=60,
                    spectrum=False,
                    seed=seed,
                )
                pair = frozenset({benched_name, active_name})
                force_preferred_pairs_in_session(
                    sess,
                    preferred_pairs=[pair],
                    forced_games=1,
                    lambda_weight=0.0,
                    score_tolerance=1.0,
                )

                p1 = next(p for p in sess.players if p.name == benched_name)
                p2 = next(p for p in sess.players if p.name == active_name)
                if not _are_teammates(sess.rounds[0], p1, p2):
                    continue

                structural_counts = _games_played_from_structure(sess)
                live_counts = {p.name: p.games_played for p in sess.players}
                assert structural_counts == live_counts
                assert (
                    max(structural_counts.values()) - min(structural_counts.values())
                    <= 1
                )
                return

    pytest.skip("Could not find a bench-swap preferred-pair case across tested seeds")


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


def test_preferred_pair_repeat_penalty_waits_until_requested_count_is_exceeded():
    preferred = decode_session(
        _two_round_repeat_document([{"players": ["Alice", "Bob"], "games": 2}])
    )
    unpreferred = decode_session(_two_round_repeat_document([]))

    preferred_breakdown = round_breakdown(preferred.rounds[1], 1)
    unpreferred_breakdown = round_breakdown(unpreferred.rounds[1], 1)

    assert preferred_breakdown["Alice"]["terms"]["same_teammate"] == pytest.approx(0)
    assert unpreferred_breakdown["Alice"]["terms"]["same_teammate"] == pytest.approx(-5)
    assert preferred_breakdown["Bob"]["terms"]["same_teammate"] == pytest.approx(0)
    assert unpreferred_breakdown["Bob"]["terms"]["same_teammate"] == pytest.approx(-5)
    assert preferred_breakdown["Alice"]["terms"]["same_people"] == pytest.approx(-5)
    assert unpreferred_breakdown["Alice"]["terms"]["same_people"] == pytest.approx(-7.5)


def test_preferred_pair_repeat_penalty_applies_after_requested_count():
    session = decode_session(
        _two_round_repeat_document([{"players": ["Alice", "Bob"], "games": 1}])
    )
    breakdown = round_breakdown(session.rounds[1], 1)

    assert breakdown["Alice"]["terms"]["same_teammate"] == pytest.approx(-5)
    assert breakdown["Bob"]["terms"]["same_teammate"] == pytest.approx(-5)


def test_apply_changes_to_rounds_updates_later_preferred_pair_penalties():
    session = decode_session(
        _four_round_future_repeat_document([{"players": ["Alice", "Bob"], "games": 2}])
    )

    before = round_breakdown(session.rounds[3], 3)
    assert before["Alice"]["terms"]["same_teammate"] == pytest.approx(0)

    round_two = session.rounds[1]
    alice = next(p for p in session.players if p.name == "Alice")
    bob = next(p for p in session.players if p.name == "Bob")
    carol = next(p for p in session.players if p.name == "Carol")
    pos_bob = round_two.find_player_position(bob)
    pos_carol = round_two.find_player_position(carol)
    round_two.swap_player_positions(pos_bob, pos_carol)

    session.apply_changes_to_rounds([1])

    after = round_breakdown(session.rounds[3], 3)
    assert after["Alice"]["terms"]["same_teammate"] == pytest.approx(-5)
    assert after["Alice"]["total"] < before["Alice"]["total"]
    assert after["Bob"]["terms"]["same_teammate"] == pytest.approx(-5)
