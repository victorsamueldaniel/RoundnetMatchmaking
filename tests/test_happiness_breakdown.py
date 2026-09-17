"""The breakdown terms must add up to the gain the engine stored for each player."""

import numpy as np
import pytest

from core.happiness_breakdown import round_breakdown
from core.session_codec import decode_session


def _document(spectrum, seed):
    rng = np.random.default_rng(seed)
    players = [
        {
            "id": f"P{i}",
            "Name": f"P{i}",
            "Surname": "",
            "Level": float(np.round(rng.uniform(1, 4), 1)),
            "Gender": "Male" if rng.random() < 0.6 else "Female",
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
        for i in range(18)
    ]
    order = [p["id"] for p in players]
    rng.shuffle(order)
    rounds = []
    for r, (t, g) in enumerate(
        [
            ("balanced", "open"),
            ("level", "mixed"),
            ("balanced", "mixed"),
            ("level", "open"),
        ]
    ):
        names = list(np.roll(order, r * 5))
        games = [
            {"team_a": names[i : i + 2], "team_b": names[i + 2 : i + 4]}
            for i in range(0, 16, 4)
        ]
        rounds.append(
            {
                "type_preference": t,
                "gender_preference": g,
                "games": games,
                "bench": names[16:],
            }
        )
    return {
        "version": 1,
        "players": players,
        "params": {"spectrum": spectrum},
        "preferred_pairs": [],
        "rounds": rounds,
    }


@pytest.mark.parametrize("spectrum", [True, False])
@pytest.mark.parametrize("seed", [0, 1, 2])
def test_breakdown_matches_engine_gain(spectrum, seed):
    session = decode_session(_document(spectrum, seed))
    for r_idx, round_obj in enumerate(session.rounds):
        breakdown = round_breakdown(round_obj, r_idx)
        for player in session.players:
            gain = player.happiness_gained_history[r_idx]
            if gain is None:
                assert player.name not in breakdown
            else:
                assert breakdown[player.name]["total"] == pytest.approx(gain)
