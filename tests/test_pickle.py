# %%
"""
Test script to verify pickle functionality for SessionOfRounds
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import core.main as main
import pickle
import os
from datetime import datetime

# %%
# Create a small session for testing
print("Creating a test session...")
list_of_players = [main.Player(main.df_minimal_example.iloc[i]) for i in range(12)]

session_of_rounds = main.SessionOfRounds(
    list_of_players,
    amount_of_rounds=2,
    type_preferences=["balanced", "level"],
    gender_preferences=None,
    level_gap_tol=2,
    num_iter=20,
    spectrum=False,
    seed=42,
)

print(f"Session created with {len(session_of_rounds.players)} players")
print(f"Number of rounds: {len(session_of_rounds.rounds)}")

# %%
# Test pickling
print("\n" + "=" * 50)
print("Testing pickle save...")
test_folder = "test_pickle_session"
os.makedirs(test_folder, exist_ok=True)

pickle_file = os.path.join(test_folder, "test_session.pkl")

try:
    with open(pickle_file, "wb") as f:
        pickle.dump(session_of_rounds, f, protocol=pickle.HIGHEST_PROTOCOL)
    print(f"✓ Successfully saved to: {pickle_file}")
except Exception as e:
    print(f"✗ Error saving: {e}")
    raise

# %%
# Test unpickling
print("\n" + "=" * 50)
print("Testing pickle load...")

try:
    with open(pickle_file, "rb") as f:
        loaded_session = pickle.load(f)
    print(f"✓ Successfully loaded from: {pickle_file}")
    print(f"  - Players: {len(loaded_session.players)}")
    print(f"  - Rounds: {len(loaded_session.rounds)}")
    print(f"  - Type preferences: {loaded_session.type_preferences}")
    print(
        f"  - Has objective_function: {hasattr(loaded_session, 'objective_function')}"
    )

    # Verify the loaded session is usable
    print("\n" + "=" * 50)
    print("Testing loaded session functionality...")
    print(f"  - First player: {loaded_session.players[0].name}")
    print(f"  - First round games: {len(loaded_session.rounds[0].games)}")

    print("\n✓ ALL TESTS PASSED! Pickle is working correctly.")

except Exception as e:
    print(f"✗ Error loading: {e}")
    import traceback

    traceback.print_exc()
    raise

# %%
# Clean up
import shutil

if os.path.exists(test_folder):
    shutil.rmtree(test_folder)
    print(f"\nCleaned up test folder: {test_folder}")
