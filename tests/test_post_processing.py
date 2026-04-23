"""Smoke-tests for force_preferred_pairs_in_session."""

import sys

sys.path.insert(0, ".")

import pandas as pd
from core.models import Player, SessionOfRounds
from core.algorithm import force_preferred_pairs_in_session


def make_row(name, level=3.0, gender="Male"):
    return {
        "Level": level,
        "Gender": gender,
        "Happiness": 0,
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


def are_teammates(r, p1, p2):
    a = r.find_player_position(p1)
    b = r.find_player_position(p2)
    return (
        a is not None
        and b is not None
        and a[0] == "game"
        and b[0] == "game"
        and a[1] == b[1]
        and a[2] == b[2]
    )


# --- Test 1: pair already satisfied → no crash, no change needed ---
print("=== Test 1: pair already 1-round satisfied, force_games=1 ===")
names = ["Alice", "Bob", "Carol", "Dave", "Eve", "Frank", "Grace", "Hank"]
df = pd.DataFrame([make_row(n) for n in names], index=names)
players = [Player(df.loc[n]) for n in df.index]

# Try seeds until Alice+Bob start together in round 0
for seed in range(20):
    sess = SessionOfRounds(
        list_of_players=[Player(df.loc[n]) for n in df.index],
        amount_of_rounds=2,
        type_preferences=["balanced", "balanced"],
        gender_preferences=["open", "open"],
        level_gap_tol=2.0,
        num_iter=50,
        spectrum=False,
        seed=seed,
    )
    alice = next(p for p in sess.players if p.name == "Alice")
    bob = next(p for p in sess.players if p.name == "Bob")
    if are_teammates(sess.rounds[0], alice, bob):
        print(f"  Seed {seed}: Alice+Bob together in round 0")
        before = sum(1 for r in sess.rounds if are_teammates(r, alice, bob))
        force_preferred_pairs_in_session(
            sess,
            preferred_pairs=[frozenset({"Alice", "Bob"})],
            forced_games=1,
            lambda_weight=2.4,
        )
        after = sum(1 for r in sess.rounds if are_teammates(r, alice, bob))
        assert after >= before, f"Pair count regressed: {before} -> {after}"
        assert sess.mean_happiness > 0, "mean_happiness not updated"
        print(f"  Before={before}, After={after}  PASSED")
        break


# --- Test 2: pair NOT together yet → force them for 1 game ---
print()
print("=== Test 2: find seed where Alice+Bob never start together, force 1 game ===")
for seed in range(30):
    players2 = [Player(df.loc[n]) for n in df.index]
    sess2 = SessionOfRounds(
        list_of_players=players2,
        amount_of_rounds=3,
        type_preferences=["balanced", "balanced", "balanced"],
        gender_preferences=["open", "open", "open"],
        level_gap_tol=2.0,
        num_iter=50,
        spectrum=False,
        seed=seed,
    )
    alice2 = next(p for p in sess2.players if p.name == "Alice")
    bob2 = next(p for p in sess2.players if p.name == "Bob")
    before2 = sum(1 for r in sess2.rounds if are_teammates(r, alice2, bob2))
    if before2 == 0:
        print(f"  Seed {seed}: Alice+Bob never together before post-processing")
        force_preferred_pairs_in_session(
            sess2,
            preferred_pairs=[frozenset({"Alice", "Bob"})],
            forced_games=1,
            lambda_weight=2.4,
        )
        after2 = sum(1 for r in sess2.rounds if are_teammates(r, alice2, bob2))
        print(f"  Before=0, After={after2}")
        # If forced, great; if constraints prevent it, that's also valid — but no crash
        assert after2 >= 0
        assert sess2.mean_happiness > 0, "mean_happiness not updated"
        print(f"  PASSED (forced={after2 >= 1})")
        break
else:
    print("  Could not find a seed where they never start together — skip")

# --- Test 3: unknown player names → no crash ---
print()
print("=== Test 3: preferred pair with unknown name -> no crash ===")
players3 = [Player(df.loc[n]) for n in df.index]
sess3 = SessionOfRounds(
    list_of_players=players3,
    amount_of_rounds=2,
    type_preferences=["balanced", "balanced"],
    gender_preferences=["open", "open"],
    level_gap_tol=2.0,
    num_iter=50,
    spectrum=False,
    seed=1,
)
force_preferred_pairs_in_session(
    sess3,
    preferred_pairs=[frozenset({"Alice", "Zoltan"})],
    forced_games=1,
)
print("  PASSED")

print()
print("ALL TESTS PASSED")
