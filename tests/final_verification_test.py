# Final verification test with real data
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.main import Player, GamesRound, SessionOfRounds, main_df

print("=" * 80)
print("FINAL VERIFICATION TEST WITH REAL DATA")
print("=" * 80)

# Use actual players from main_df
good_numbers = [1, 3, 4, 5, 7, 9]
list_of_players = [
    Player(main_df.loc[name]) for name in main_df.iloc[good_numbers].index
]

print(f"\nCreating session with {len(list_of_players)} real players...")
print(f"Players: {[p.name for p in list_of_players]}\n")

session = SessionOfRounds(
    list_of_players,
    amount_of_rounds=3,
    type_preferences=["balanced", "level", "balanced"],
    level_gap_tol=1.5,
    num_iter=20,
    seed=42,
)

print("Session created successfully!\n")
print("Iterations Summary:")
print("-" * 80)

total_iterations = 0
for round_idx, round_obj in enumerate(session.rounds):
    iterations_count = len(round_obj.iterations)
    total_iterations += iterations_count
    print(
        f"Round {round_idx + 1} ({round_obj.type_preference}): {iterations_count} iterations"
    )

    if round_obj.type_preference == "balanced" and round_obj.iterations:
        valid_scores = [
            it["score"] for it in round_obj.iterations if it["score"] is not None
        ]
        if valid_scores:
            print(f"  Valid iterations: {len(valid_scores)}")
            print(f"  Best score: {max(valid_scores):.4f}")
            print(f"  Selected {len(round_obj.games)} games")

print(f"\nTotal iterations across all rounds: {total_iterations}")
print("\n" + "=" * 80)
print("✓ SUCCESS: Iterations attribute is working with real data!")
print("=" * 80)
