# Test script to verify that iterations are being tracked correctly
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
import numpy as np
from core.main import (
    Player,
    GamesRound,
    SessionOfRounds,
    run_session_generation_with_seed_optimization,
)

# Create test dataframe with minimal example
df_test = pd.DataFrame(
    {
        "Name": ["Alice", "Bob", "Charlie", "David", "Eve", "Frank", "Grace", "Hugo"],
        "Surname": [
            "Smith",
            "Johnson",
            "Williams",
            "Jones",
            "Brown",
            "Davis",
            "Miller",
            "Wilson",
        ],
        "Level": [1, 2, 3, 2, 1, 3, 2, 1],
        "Noisy level": [0] * 8,
        "Gender": [
            "Female",
            "Male",
            "Male",
            "Female",
            "Female",
            "Male",
            "Female",
            "Male",
        ],
        "Games played": [0] * 8,
        "Happiness": [0] * 8,
    }
)

df_test.set_index("Name", inplace=True)

# Test 1: Check iterations for balanced games
print("=" * 80)
print("TEST 1: Checking iterations attribute for 'balanced' type preference")
print("=" * 80)

list_of_players_balanced = [Player(df_test.iloc[i]) for i in range(8)]
round_balanced = GamesRound(
    list_of_players_balanced,
    type_preference="balanced",
    gender_preference=None,
    num_iter=10,
    level_gap_tol=2,
    seed=42,
)

print(f"Number of games created: {len(round_balanced.games)}")
print(f"Number of iterations explored: {len(round_balanced.iterations)}")
print(f"Iterations attribute exists: {hasattr(round_balanced, 'iterations')}")

if round_balanced.iterations:
    print(f"\nFirst 3 iterations:")
    for idx, iteration in enumerate(round_balanced.iterations[:3]):
        print(f"  Iteration {idx + 1}:")
        print(f"    Score: {iteration['score']:.4f}")
        print(f"    Number of games: {len(iteration['games'])}")

print("\n")

# Test 2: Check iterations for level-based games
print("=" * 80)
print("TEST 2: Checking iterations attribute for 'level' type preference")
print("=" * 80)

list_of_players_level = [Player(df_test.iloc[i]) for i in range(8)]
round_level = GamesRound(
    list_of_players_level,
    type_preference="level",
    gender_preference=None,
    num_iter=10,
    level_gap_tol=2,
    seed=42,
)

print(f"Number of games created: {len(round_level.games)}")
print(f"Number of iterations explored: {len(round_level.iterations)}")
print(f"Iterations attribute exists: {hasattr(round_level, 'iterations')}")

if round_level.iterations:
    print(f"\nFirst 3 iterations:")
    for idx, iteration in enumerate(round_level.iterations[:3]):
        print(f"  Iteration {idx + 1}:")
        print(f"    Game number: {iteration['game_num']}")
        print(f"    Level difference: {iteration['level_diff']:.4f}")
        print(
            f"    Teams: {iteration['teams'][0].players_name} vs {iteration['teams'][1].players_name}"
        )

print("\n")

# Test 3: Check iterations in SessionOfRounds
print("=" * 80)
print("TEST 3: Checking iterations attribute in SessionOfRounds")
print("=" * 80)

list_of_players_session = [Player(df_test.iloc[i]) for i in range(8)]
session = SessionOfRounds(
    list_of_players_session,
    amount_of_rounds=2,
    type_preferences=["balanced", "level"],
    level_gap_tol=2,
    num_iter=10,
    seed=42,
)

for round_idx, round_obj in enumerate(session.rounds):
    print(f"\nRound {round_idx + 1}:")
    print(f"  Type preference: {round_obj.type_preference}")
    print(f"  Number of games: {len(round_obj.games)}")
    print(f"  Number of iterations: {len(round_obj.iterations)}")
    print(f"  Iterations attribute exists: {hasattr(round_obj, 'iterations')}")

# Test 4: Sit-out fairness tie-break (happier overplayed players benched first)
print("\n" + "=" * 80)
print("TEST 4: Sit-out fairness tie-break")
print("=" * 80)

df_fair = pd.DataFrame(
    {
        "Name": ["P1", "P2", "P3", "P4", "P5", "P6"],
        "Surname": ["S"] * 6,
        "Level": [2.0, 2.2, 2.4, 2.6, 2.8, 3.0],
        "Noisy level": [0] * 6,
        "Gender": ["Male", "Female", "Male", "Female", "Male", "Female"],
        "Games played": [1] * 6,
        "Happiness": [0, 1, 2, 3, 4, 5],
    }
)
df_fair.set_index("Name", inplace=True)

fair_players = [Player(df_fair.iloc[i]) for i in range(6)]
fair_round = GamesRound(
    fair_players,
    amount_of_games=1,
    type_preference="level",
    gender_preference=None,
    level_gap_tol=3,
    seed=123,
)

bench_count = len(df_fair.index) - (1 * 4)
expected_benched = set(
    df_fair.sort_values("Happiness", ascending=False).head(bench_count).index
)
actual_benched = {player.name for player in fair_round.not_playing}

print(f"Expected benched: {sorted(expected_benched)}")
print(f"Actual benched:   {sorted(actual_benched)}")
assert (
    actual_benched == expected_benched
), f"Fairness tie-break mismatch: expected {expected_benched}, got {actual_benched}"


# Test 5: Iterations telemetry includes pass metadata and selected candidate
print("\n" + "=" * 80)
print("TEST 5: Iterations telemetry metadata")
print("=" * 80)

df_gender_fail = pd.DataFrame(
    {
        "Name": ["A", "B", "C", "D"],
        "Surname": ["X"] * 4,
        "Level": [2.0, 2.1, 2.2, 2.3],
        "Noisy level": [0] * 4,
        "Gender": ["Male", "Male", "Male", "Male"],
        "Games played": [0] * 4,
        "Happiness": [0] * 4,
    }
)
df_gender_fail.set_index("Name", inplace=True)

gender_players = [Player(df_gender_fail.iloc[i]) for i in range(4)]
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
assert all(
    "pass_num" in it and "gender_enforced" in it and "selected" in it
    for it in mixed_round.iterations
), "Missing telemetry keys in balanced iterations"
assert any(
    it["pass_num"] == 1 for it in mixed_round.iterations
), "Expected pass-1 iterations when mixed gender is impossible"

selected_rows = [it for it in mixed_round.iterations if it.get("selected")]
print(f"Selected iteration rows: {len(selected_rows)}")
assert len(selected_rows) == 1, "Expected exactly one selected iteration row"
assert (
    selected_rows[0]["pass_num"] == 1
), "Expected selected iteration from pass 1 in this scenario"
assert selected_rows[0]["score"] is not None, "Selected iteration should have a score"


# Test 6: Seed ranking uses provided objective function
print("\n" + "=" * 80)
print("TEST 6: Seed ranking objective alignment")
print("=" * 80)


class _View:
    def __init__(self, participants):
        self.participants = participants


def custom_seed_objective(view):
    values = [player.happiness for player in view.participants]
    return float(min(values) * 1000 + np.mean(values))


common_kwargs = dict(
    df=df_test,
    amount_of_rounds=3,
    type_preferences=["balanced", "balanced", "level"],
    gender_preferences=["open", "open", "open"],
    level_gap_tol=2.0,
    num_iter=20,
    lambda_weight=0.1,
    spectrum=False,
    games_per_round_each_round=2,
    objective_function=custom_seed_objective,
    print_progress=False,
)

manual_scores = {}
for seed in range(3):
    single_session, _ = run_session_generation_with_seed_optimization(
        first_seed=seed,
        last_seed=seed,
        **common_kwargs,
    )
    manual_scores[seed] = custom_seed_objective(_View(single_session.players))

expected_seed = max(manual_scores, key=manual_scores.get)
_, chosen_seed = run_session_generation_with_seed_optimization(
    first_seed=0,
    last_seed=2,
    **common_kwargs,
)

print(f"Manual scores: {manual_scores}")
print(f"Expected seed: {expected_seed}, chosen seed: {chosen_seed}")
assert (
    chosen_seed == expected_seed
), f"Seed objective mismatch: expected {expected_seed}, got {chosen_seed}"


# Test 7: Balanced iteration count is bounded by num_iter (C7)
print("\n" + "=" * 80)
print("TEST 7: Balanced iteration budget bound")
print("=" * 80)

budget_players = [Player(df_test.iloc[i]) for i in range(8)]
budget_round = GamesRound(
    budget_players,
    type_preference="balanced",
    gender_preference=None,
    num_iter=5,
    level_gap_tol=2,
    seed=42,
)

print(
    f"Iterations explored: {len(budget_round.iterations)} (num_iter={budget_round.num_iter})"
)
assert (
    len(budget_round.iterations) <= budget_round.num_iter
), "Balanced iteration count should not exceed num_iter"

print("\nAll new assertions passed.")
print("=" * 80)
print("ALL TESTS COMPLETED!")
print("=" * 80)
