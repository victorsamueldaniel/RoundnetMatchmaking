"""A session saved as JSON must reload with exactly the same happiness."""

import json

import numpy as np
import pytest

from core.algorithm import (
    apply_preferred_pairs_happiness,
    force_preferred_pairs_in_session,
    run_session_generation_with_seed_optimization,
)
from core.models import mean_min_max_happiness_objective
from core.session_codec import decode_session, encode_session, players_dataframe


def _players(n=21):
    rng = np.random.default_rng(1)
    return [
        {
            "id": f"P{i}",
            "Name": f"P{i}",
            "Surname": "",
            "Level": float(np.round(rng.uniform(1, 4), 1)),
            "Gender": "Male" if i % 3 else "Female",
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
        for i in range(n)
    ]


@pytest.mark.parametrize("with_pairs", [False, True])
def test_round_trip_keeps_happiness(with_pairs):
    players = _players()
    pairs = [(frozenset(["P1", "P2"]), 2)] if with_pairs else []
    session, seed = run_session_generation_with_seed_optimization(
        players_dataframe(players),
        amount_of_rounds=4,
        type_preferences=["balanced", "level", "balanced", "level"],
        gender_preferences=["open", "mixed", "mixed", "open"],
        rounds_reordering=[3, 1, 4, 2],
        num_iter=60,
        first_seed=0,
        last_seed=1,
        preferred_pairs=pairs,
        print_progress=False,
        objective_function=lambda x: mean_min_max_happiness_objective(
            x, lambda_weight=2.4, percentile=10
        ),
    )
    if pairs:
        force_preferred_pairs_in_session(session, pairs, lambda_weight=2.4)
        apply_preferred_pairs_happiness(session, pairs)
    session._games_per_round_preference = "auto"

    doc = json.loads(
        json.dumps(
            encode_session(
                session,
                players,
                {"num_iter": 60, "games_per_round": "auto"},
                pairs,
                seed=seed,
            )
        )
    )
    reloaded = decode_session(doc)

    expected = {p.name: p.happiness for p in session.players}
    assert {p.name: p.happiness for p in reloaded.players} == pytest.approx(expected)
    assert doc["params"]["games_per_round"] == "auto"
    assert reloaded._games_per_round_preference == "auto"
    assert [len(r.games) for r in reloaded.rounds] == [
        len(r.games) for r in session.rounds
    ]
