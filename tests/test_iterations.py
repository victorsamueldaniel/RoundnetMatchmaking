# Test script to verify that iterations are being tracked correctly
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
import numpy as np
from core.main import Player, GamesRound, SessionOfRounds

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

print("\n")
print("=" * 80)
print("ALL TESTS COMPLETED!")
print("=" * 80)
