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
from types import SimpleNamespace

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
    print(f"[OK] Successfully saved to: {pickle_file}")
except Exception as e:
    print(f"[ERR] Error saving: {e}")
    raise

# %%
# Test unpickling
print("\n" + "=" * 50)
print("Testing pickle load...")

try:
    with open(pickle_file, "rb") as f:
        loaded_session = pickle.load(f)
    print(f"[OK] Successfully loaded from: {pickle_file}")
    print(f"  - Players: {len(loaded_session.players)}")
    print(f"  - Rounds: {len(loaded_session.rounds)}")
    print(f"  - Type preferences: {loaded_session.type_preferences}")
    print(
        f"  - Has objective_function: {hasattr(loaded_session, 'objective_function')}"
    )

    # Verify objective metadata survives round-trip for new pickles
    session_obj_name = getattr(loaded_session, "_objective_function_name", None)
    print(f"  - Restored objective marker: {session_obj_name}")
    assert (
        session_obj_name == "mean_min_max_happiness_objective"
    ), f"Unexpected session objective marker: {session_obj_name}"

    first_round = loaded_session.rounds[0]
    round_obj_name = getattr(first_round, "_objective_function_name", None)
    print(f"  - Round 1 objective marker: {round_obj_name}")
    assert (
        round_obj_name == "mean_min_max_happiness_objective"
    ), f"Unexpected round objective marker: {round_obj_name}"

    round_lambda = getattr(first_round, "_objective_lambda_weight", None)
    round_percentile = getattr(first_round, "_objective_percentile", 10) or 10
    restored_round_score = first_round.objective_function(first_round)
    expected_round_score = main.mean_min_max_happiness_objective(
        first_round,
        lambda_weight=round_lambda if round_lambda is not None else 2,
        percentile=round_percentile,
    )
    assert abs(restored_round_score - expected_round_score) < 1e-9

    # Verify the loaded session is usable
    print("\n" + "=" * 50)
    print("Testing loaded session functionality...")
    print(f"  - First player: {loaded_session.players[0].name}")
    print(f"  - First round games: {len(loaded_session.rounds[0].games)}")

    # Verify legacy objective marker compatibility path
    print("\n" + "=" * 50)
    print("Testing legacy objective marker compatibility...")

    legacy_session = main.SessionOfRounds.__new__(main.SessionOfRounds)
    legacy_session.__setstate__({"_objective_function_name": "mean_std_happiness_objective"})
    assert (
        getattr(legacy_session, "_objective_function_name", None)
        == "mean_std_happiness_objective"
    )
    assert getattr(legacy_session, "_objective_lambda_weight", None) == 2

    legacy_round = main.GamesRound.__new__(main.GamesRound)
    legacy_round.__setstate__({"_objective_function_name": "mean_std_happiness_objective"})
    legacy_round.participants = [
        SimpleNamespace(happiness=happiness) for happiness in (1.0, 3.0, 5.0)
    ]
    legacy_round_score = legacy_round.objective_function(legacy_round)
    expected_legacy_round_score = main.mean_std_happiness_objective(
        legacy_round, lambda_weight=2
    )
    assert abs(legacy_round_score - expected_legacy_round_score) < 1e-9

    print("\n[OK] ALL TESTS PASSED! Pickle is working correctly.")

except Exception as e:
    print(f"[ERR] Error loading: {e}")
    import traceback

    traceback.print_exc()
    raise

# %%
# Clean up
import shutil

if os.path.exists(test_folder):
    shutil.rmtree(test_folder)
    print(f"\nCleaned up test folder: {test_folder}")
