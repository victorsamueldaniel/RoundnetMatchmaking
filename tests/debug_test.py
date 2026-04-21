# Debug test to understand why iterations aren't being recorded
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
import numpy as np
from core.main import Player, GamesRound

# Create test dataframe with minimal example
df_test = pd.DataFrame(
    {
        "Name": ["Alice", "Bob", "Charlie", "David"],
        "Surname": ["Smith", "Johnson", "Williams", "Jones"],
        "Level": [1, 2, 3, 2],
        "Noisy level": [0] * 4,
        "Gender": ["Female", "Male", "Male", "Female"],
        "Games played": [0] * 4,
        "Happiness": [0] * 4,
    }
)

df_test.set_index("Name", inplace=True)

print("=" * 80)
print("DEBUG TEST: Checking why iterations aren't being recorded")
print("=" * 80)

list_of_players = [Player(df_test.iloc[i]) for i in range(4)]

# Create a round with balanced preference
print("\nCreating round with 'balanced' preference...")
round_obj = GamesRound(
    list_of_players,
    type_preference="balanced",
    gender_preference=None,
    num_iter=5,
    level_gap_tol=5,  # Very high tolerance
    seed=42,
)

print(f"\nRound attributes:")
print(f"  Number of games: {len(round_obj.games)}")
print(f"  Amount of games: {round_obj.amount_of_games}")
print(f"  People playing: {[p.name for p in round_obj.people_playing]}")
print(f"  Iterations attribute exists: {hasattr(round_obj, 'iterations')}")
print(f"  Number of iterations: {len(round_obj.iterations)}")

# Try to manually call generate_all_game_combinations
print("\n\nManually testing generate_all_game_combinations...")
all_combos = round_obj.generate_all_game_combinations(round_obj.people_playing)
print(f"Number of combinations generated: {len(all_combos)}")

if all_combos:
    print(f"First combination has {len(all_combos[0])} games")
    for idx, game in enumerate(all_combos[0]):
        print(f"  Game {idx + 1}: {[p.name for p in game.participants]}")
