# Comprehensive test to show what information is stored in iterations
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
from core.main import Player, GamesRound, SessionOfRounds

# Create test dataframe
df_test = pd.DataFrame(
    {
        "Name": ["Alice", "Bob", "Charlie", "David", "Eve", "Frank"],
        "Surname": ["Smith", "Johnson", "Williams", "Jones", "Brown", "Davis"],
        "Level": [1, 2, 3, 2, 1, 3],
        "Noisy level": [0] * 6,
        "Gender": ["Female", "Male", "Male", "Female", "Female", "Male"],
        "Games played": [0] * 6,
        "Happiness": [0] * 6,
    }
)

df_test.set_index("Name", inplace=True)

print("=" * 80)
print("COMPREHENSIVE ITERATIONS TEST")
print("=" * 80)

# Test with balanced games
print("\n1. BALANCED GAMES - Detailed Iteration Information")
print("-" * 80)
list_of_players = [Player(df_test.iloc[i]) for i in range(6)]
round_balanced = GamesRound(
    list_of_players,
    type_preference="balanced",
    gender_preference=None,
    num_iter=5,
    level_gap_tol=2,
    seed=42,
)

print(f"Total iterations explored: {len(round_balanced.iterations)}")
print(f"\nShowing first 5 iterations with full details:\n")

for idx, iteration in enumerate(round_balanced.iterations[:5]):
    print(f"Iteration {idx + 1}:")
    print(f"  Score: {iteration['score'] if iteration['score'] is not None else 'N/A'}")
    print(f"  Meets tolerance: {iteration['meets_tolerance']}")
    print(f"  Number of games: {len(iteration['games'])}")

    for game_idx, game in enumerate(iteration["games"]):
        print(f"  Game {game_idx + 1}:")
        teams = list(game.teams)
        print(
            f"    Team A: {teams[0].players_name} (avg level: {teams[0].mean_level:.2f})"
        )
        print(
            f"    Team B: {teams[1].players_name} (avg level: {teams[1].mean_level:.2f})"
        )
        print(f"    Level difference: {game.level_difference:.2f}")
    print()

# Find the best iteration
best_iteration = max(
    [it for it in round_balanced.iterations if it["score"] is not None],
    key=lambda x: x["score"],
)
best_idx = round_balanced.iterations.index(best_iteration)
print(f"Best iteration was #{ best_idx + 1} with score: {best_iteration['score']:.4f}")

# Test with level games
print("\n\n2. LEVEL GAMES - Detailed Iteration Information")
print("-" * 80)
list_of_players_level = [Player(df_test.iloc[i]) for i in range(6)]
round_level = GamesRound(
    list_of_players_level,
    type_preference="level",
    gender_preference=None,
    level_gap_tol=2,
    seed=42,
)

print(f"Total iterations explored: {len(round_level.iterations)}")
print(f"\nShowing first 5 iterations:\n")

for idx, iteration in enumerate(round_level.iterations[:5]):
    print(f"Iteration {idx + 1}:")
    print(f"  Game number: {iteration['game_num']}")
    print(f"  Level difference: {iteration['level_diff']:.2f}")
    teams = iteration["teams"]
    print(f"  Team A: {teams[0].players_name} (avg level: {teams[0].mean_level:.2f})")
    print(f"  Team B: {teams[1].players_name} (avg level: {teams[1].mean_level:.2f})")
    print()

# Test in a session
print("\n\n3. SESSION ANALYSIS - Iterations Across Multiple Rounds")
print("-" * 80)
list_of_players_session = [Player(df_test.iloc[i]) for i in range(6)]
session = SessionOfRounds(
    list_of_players_session,
    amount_of_rounds=3,
    type_preferences=["balanced", "level", "balanced"],
    level_gap_tol=2,
    num_iter=5,
    seed=42,
)

print(f"Session has {len(session.rounds)} rounds\n")

for round_idx, round_obj in enumerate(session.rounds):
    print(f"Round {round_idx + 1}:")
    print(f"  Type: {round_obj.type_preference}")
    print(f"  Games created: {len(round_obj.games)}")
    print(f"  Iterations explored: {len(round_obj.iterations)}")

    if round_obj.iterations:
        if round_obj.type_preference == "balanced":
            valid_scores = [
                it["score"] for it in round_obj.iterations if it["score"] is not None
            ]
            if valid_scores:
                print(f"  Best score: {max(valid_scores):.4f}")
                print(f"  Worst score: {min(valid_scores):.4f}")
                print(f"  Average score: {sum(valid_scores)/len(valid_scores):.4f}")
        elif round_obj.type_preference == "level":
            level_diffs = [it["level_diff"] for it in round_obj.iterations]
            print(f"  Best level diff: {min(level_diffs):.4f}")
            print(f"  Worst level diff: {max(level_diffs):.4f}")
    print()

print("=" * 80)
print("TEST COMPLETED - Iterations attribute successfully tracks all explored options!")
print("=" * 80)
