"""algorithm.py - run_session_generation_with_seed_optimization."""

import numpy as np

from core.models import (
    Player,
    SessionOfRounds,
    mean_min_max_happiness_objective,
)


class _ParticipantsView:
    """Adapter exposing a participants attribute for objective functions."""

    def __init__(self, participants):
        self.participants = participants


def _score_players_with_objective(players, objective_function, lambda_weight):
    """Return objective score for players, with robust fallback.

    The fallback keeps backward compatibility for custom objective functions that
    don't accept the participants-view adapter.
    """
    if objective_function is not None:
        try:
            score = float(objective_function(_ParticipantsView(players)))
            if np.isfinite(score):
                return score, False
        except Exception:
            pass

    happinesses = [p.happiness for p in players]
    return np.mean(happinesses) - lambda_weight * np.std(happinesses), True


def run_session_generation_with_seed_optimization(
    df,
    amount_of_rounds=4,
    type_preferences=None,
    gender_preferences=None,
    rounds_reordering=None,
    level_gap_tol=1.1,
    num_iter=435,
    lambda_weight=2.4,
    weight_same_teammate=5,
    never_met_bonus_per_player=2,
    never_met_bonus_cap=4,
    first_seed=0,
    last_seed=9,
    spectrum=True,
    games_per_round_each_round=None,
    objective_function=None,
    extra_parameters=None,
    print_progress=True,
    print_all_happiness=False,
    progress_callback=None,
):
    """
    Run multiple session simulations with different seeds to find the best matchmaking configuration.

    Parameters:
    -----------
    df : pandas.DataFrame
        DataFrame containing player information
    amount_of_rounds : int
        Number of rounds to play (default: 4)
    type_preferences : list
        List of preferences for each round (e.g., ["level", "balanced"])
    gender_preferences : list
        List of gender preferences for each round (e.g., ["open", "mixed"])
    level_gap_tol : float
        Tolerance for level gaps between players (default: 1)
    num_iter : int
        Number of iterations for optimization (default: 100)
    lambda_weight : float
        Weight for standard deviation in objective function (default: 3)
    weight_same_teammate : float
        Weight penalty for repeating teammates (default: 3)
    never_met_bonus_per_player : float
        Bonus per previously unseen player encountered in a game (default: 0.35)
    never_met_bonus_cap : float
        Maximum never-met bonus a player can receive per game (default: 1.0)
    first_seed : int
        Starting seed for iteration (default: 3)
    last_seed : int
        Ending seed for iteration (default: 10)
    spectrum : bool
        Whether to use spectrum mode (default: True)
    games_per_round_each_round : int or None
        Number of games per round (default: None)
    objective_function : callable or None
        Custom objective function (default: uses mean_min_max_happiness_objective)
    print_progress : bool
        Whether to print progress information (default: True)
    print_all_happiness : bool
        Whether to print all players' happiness with color coding (default: False)

    Returns:
    --------
    tuple: (session_of_rounds, chosen_seed)
        Best session configuration and the seed that produced it
    """

    # Set default objective function if not provided.
    # The default objective inherits lambda_weight so stage-A (round scoring)
    # and stage-B (seed scoring) use consistent lambda semantics.
    if objective_function is None:
        objective_function = lambda x: mean_min_max_happiness_objective(
            x, lambda_weight=lambda_weight
        )

    # Set default type preferences if not provided
    if type_preferences is None:
        type_preferences = ["balanced", "balanced", "level", "level"]

    # Set default gender preferences if not provided
    if gender_preferences is None:
        gender_preferences = ["open", "mixed", "mixed", "open"]

    session_of_rounds = None
    chosen_seed = None
    best_score = None

    # Fallback in case no fully valid session is found in the seed range
    fallback_session = None
    fallback_seed = None
    fallback_score = None
    objective_fallback_warned = False

    for seed in range(first_seed, last_seed + 1):
        if progress_callback is not None:
            progress_callback(seed)

        if print_progress:
            print(
                "################################################################################"
            )
            print(
                "################################################################################"
            )
            print(
                f"#################################### SEED: {seed} ###################################"
            )

        list_of_players = [Player(df.loc[name]) for name in df.index]

        # Build kwargs for SessionOfRounds
        session_kwargs = {
            "list_of_players": list_of_players,
            "amount_of_rounds": amount_of_rounds,
            "type_preferences": type_preferences,
            "level_gap_tol": level_gap_tol,
            "num_iter": num_iter,
            "objective_function": objective_function,
            "weight_same_teammate": weight_same_teammate,
            "never_met_bonus_per_player": never_met_bonus_per_player,
            "never_met_bonus_cap": never_met_bonus_cap,
            "seed": seed,
            "spectrum": spectrum,
            "rounds_reordering": rounds_reordering,
            "gender_preferences": gender_preferences,
            "extra_parameters": extra_parameters,
        }

        if games_per_round_each_round is not None:
            session_kwargs["games_per_round_each_round"] = games_per_round_each_round

        temp_session_of_rounds = SessionOfRounds(**session_kwargs)

        if print_progress:
            print(
                "##################################### STATS ####################################"
            )
            print("current mean happiness:", temp_session_of_rounds.mean_happiness)
            print("current standard deviation:", temp_session_of_rounds.std_happiness)

        current_score, used_fallback_score = _score_players_with_objective(
            temp_session_of_rounds.players,
            objective_function,
            lambda_weight,
        )
        if print_progress:
            print("current score:", current_score)
            if used_fallback_score and not objective_fallback_warned:
                print(
                    "Warning: objective_function could not be evaluated at session "
                    "seed-selection stage; falling back to mean - lambda * std."
                )
                objective_fallback_warned = True

        if print_progress:
            player_pairs, pair_rounds = temp_session_of_rounds.count_all_pairs()
            output, team_repetition = (
                temp_session_of_rounds.add_team_repetition_to_output(
                    [], player_pairs, pair_rounds
                )
            )
            print("\n".join(output))

        # Print all happiness if requested
        if print_all_happiness:
            temp_session_of_rounds.print_happiness_with_colors()

        # Keep best overall session as fallback
        if fallback_score is None or current_score > fallback_score:
            fallback_score = current_score
            fallback_seed = seed
            fallback_session = temp_session_of_rounds

        # Keep only sessions with all rounds successfully created
        has_all_rounds = all(
            len(getattr(round_obj, "games", [])) > 0
            for round_obj in temp_session_of_rounds.rounds
        )

        if not has_all_rounds:
            if print_progress:
                print("Seed skipped: at least one round has no generated games.")
            continue

        # Check if this is the best valid session so far
        if best_score is None or current_score > best_score:
            best_score = current_score
            chosen_seed = seed
            session_of_rounds = temp_session_of_rounds

    # If no fully valid session exists, fall back to best available session
    if session_of_rounds is None and fallback_session is not None:
        session_of_rounds = fallback_session
        chosen_seed = fallback_seed
        best_score = fallback_score
        if print_progress:
            print(
                "Warning: no seed produced a fully valid session; using best available session."
            )

    if print_progress:
        print(
            "################################################################################"
        )
        print(
            "#################################### RESULTS ###################################"
        )
        print(f"\033[94mChosen seed: {chosen_seed}\033[0m")
        print("\033[92mDONE\033[0m")

    return session_of_rounds, chosen_seed


# ---------------------------------------------------------------------------
# Post-processing: force preferred pairs to be teammates
# ---------------------------------------------------------------------------


def _session_score(session, lambda_weight):
    """Score = mean(happiness) - lambda * std(happiness) across all players."""
    happinesses = [p.happiness for p in session.players]
    return np.mean(happinesses) - lambda_weight * np.std(happinesses)


def _are_teammates(pos1, pos2):
    """Return True iff both positions are in the same game on the same team."""
    if pos1 is None or pos2 is None:
        return False
    return (
        pos1[0] == "game"
        and pos2[0] == "game"
        and pos1[1] == pos2[1]
        and pos1[2] == pos2[2]
    )


def _get_teammate_pos(pos):
    """Return the position of the other player slot on the same team.

    pos must be ("game", game_idx, team_id, player_idx) where player_idx is 0 or 1.
    """
    _, game_idx, team_id, player_idx = pos
    return ("game", game_idx, team_id, 1 - player_idx)


def _count_games_per_player(session):
    """Return {player_name: rounds_played_count} for all players."""
    counts = {p.name: 0 for p in session.players}
    for round_obj in session.rounds:
        for game in round_obj.games:
            for participant in game.participants:
                counts[participant.name] = counts.get(participant.name, 0) + 1
    return counts


def _balance_ok(session):
    """Games-played counts are balanced: max - min <= 1."""
    counts = _count_games_per_player(session)
    if not counts:
        return True
    return max(counts.values()) - min(counts.values()) <= 1


def _affected_game_idxs(pos_a, pos_b):
    """Return the set of game indices affected by swapping pos_a and pos_b."""
    game_idxs = set()
    for pos in (pos_a, pos_b):
        if pos[0] == "game":
            game_idxs.add(pos[1])
    return game_idxs


def _evaluate_swap_score(round_obj, round_idx, pos_a, pos_b, session, lambda_weight):
    """Evaluate a candidate swap and return the resulting session score, or None if invalid.

    All constraint checks (level gap, balance, gender preference) are performed and
    the swap is always fully undone before returning.
    """
    round_obj.swap_player_positions(pos_a, pos_b)

    # --- Level gap check ---
    for game_idx in _affected_game_idxs(pos_a, pos_b):
        game = round_obj.games[game_idx]
        if (
            abs(game.team_A.mean_level - game.team_B.mean_level)
            > round_obj.level_gap_tol
        ):
            round_obj.swap_player_positions(pos_a, pos_b)
            return None

    # --- Games balance check ---
    if not _balance_ok(session):
        round_obj.swap_player_positions(pos_a, pos_b)
        return None

    # --- Recalculate happiness (rebuilds team objects, updates all histories) ---
    round_obj.recalculate_happiness(round_idx)

    # --- Gender preference check ---
    if not all(g.is_gender_preference_satisfied for g in round_obj.games):
        round_obj.swap_player_positions(pos_a, pos_b)
        round_obj.recalculate_happiness(round_idx)
        return None

    # --- Compute score ---
    score = _session_score(session, lambda_weight)

    # --- Always undo ---
    round_obj.swap_player_positions(pos_a, pos_b)
    round_obj.recalculate_happiness(round_idx)
    return score


def force_preferred_pairs_in_session(
    session,
    preferred_pairs,
    forced_games=1,
    lambda_weight=2.4,
    score_tolerance=0.10,
):
    """Post-process a generated session to force preferred pairs together.

    ``preferred_pairs`` accepts two formats:
      - ``[(frozenset({name1, name2}), forced_games), ...]``
      - ``[frozenset({name1, name2}), ...]`` (uses ``forced_games`` arg)

    For each pair the function attempts to arrange swaps so the two players are
    teammates in at least the requested number of rounds.

    Constraints respected:
      - No player plays 2+ fewer games than any other (balance).
      - Level gap between teams stays within round.level_gap_tol.
      - Gender preference per game is not violated.
      - Session score does not drop more than *score_tolerance* (10 %).

    All candidate swaps across all pending pairs and all rounds compete at each
    step; the single best valid swap is applied (global-greedy).
    After all pairs have been processed the session-level cached stats are
    refreshed.
    """
    if not preferred_pairs:
        return

    normalized_pairs = []
    for pair_entry in preferred_pairs:
        pair_fs = None
        pair_forced_games = forced_games

        # Full tuple/list form: (pair, forced_games)
        if (
            isinstance(pair_entry, (tuple, list))
            and len(pair_entry) == 2
            and isinstance(pair_entry[1], (int, float))
        ):
            pair_fs = frozenset(pair_entry[0])
            pair_forced_games = int(pair_entry[1])
        else:
            pair_fs = frozenset(pair_entry)

        if len(pair_fs) != 2:
            continue

        normalized_pairs.append((pair_fs, max(0, pair_forced_games)))

    if not normalized_pairs:
        return

    base_score = _session_score(session, lambda_weight)
    score_threshold = base_score * (1.0 - score_tolerance)

    # Resolve player objects and compute how many rounds each pair still needs
    players_per_pair = []
    needed = []
    for pair_fs, pair_forced_games in normalized_pairs:
        names = sorted(pair_fs)
        player1 = next((p for p in session.players if p.name == names[0]), None)
        player2 = next((p for p in session.players if p.name == names[1]), None)
        players_per_pair.append((player1, player2))
        if player1 is None or player2 is None:
            needed.append(0)
            continue
        already = sum(
            1
            for r in session.rounds
            if _are_teammates(
                r.find_player_position(player1), r.find_player_position(player2)
            )
        )
        needed.append(max(0, pair_forced_games - already))

    # Global-greedy: at each step apply the single best valid swap across all
    # pending pairs × all rounds, then repeat until all pairs are satisfied or
    # no valid swap remains.
    while any(n > 0 for n in needed):
        best_score = None
        best_candidate = None  # (pair_idx, round_idx, round_obj, pos_a, pos_b)

        for pair_idx, (pair_fs, _) in enumerate(normalized_pairs):
            if needed[pair_idx] <= 0:
                continue
            player1, player2 = players_per_pair[pair_idx]
            if player1 is None or player2 is None:
                continue

            for round_idx, round_obj in enumerate(session.rounds):
                pos1 = round_obj.find_player_position(player1)
                pos2 = round_obj.find_player_position(player2)

                # Already teammates in this round — skip
                if _are_teammates(pos1, pos2):
                    continue

                if pos1 is None or pos2 is None:
                    continue

                # Both sitting out — nothing to do in this round
                if pos1[0] == "not_playing" and pos2[0] == "not_playing":
                    continue

                # Build up to two candidate (pos_a, pos_b) swaps for this round
                if pos1[0] == "game" and pos2[0] == "game":
                    candidates_this_round = [
                        (_get_teammate_pos(pos1), pos2),
                        (_get_teammate_pos(pos2), pos1),
                    ]
                elif pos1[0] == "not_playing":
                    # player1 sitting out; swap player2's teammate for player1
                    candidates_this_round = [(pos1, _get_teammate_pos(pos2))]
                else:
                    # player2 sitting out; swap player1's teammate for player2
                    candidates_this_round = [(pos2, _get_teammate_pos(pos1))]

                for pos_a, pos_b in candidates_this_round:
                    score = _evaluate_swap_score(
                        round_obj, round_idx, pos_a, pos_b, session, lambda_weight
                    )
                    if score is not None and score >= score_threshold:
                        if best_score is None or score > best_score:
                            best_score = score
                            best_candidate = (
                                pair_idx,
                                round_idx,
                                round_obj,
                                pos_a,
                                pos_b,
                            )

        if best_candidate is None:
            break  # No valid swap exists for any pending pair

        pair_idx, round_idx, round_obj, pos_a, pos_b = best_candidate
        round_obj.swap_player_positions(pos_a, pos_b)
        round_obj.recalculate_happiness(round_idx)
        needed[pair_idx] -= 1

    # Refresh session-level cached statistics
    happinesses = [p.happiness for p in session.players]
    session.mean_happiness = np.mean(happinesses)
    session.std_happiness = np.std(happinesses)
    session.max_and_min_happiness = (max(happinesses), min(happinesses))
    session.max_happiness_difference = (
        session.max_and_min_happiness[0] - session.max_and_min_happiness[1]
    )
    for player in session.players:
        player.relative_happiness = player.happiness - session.mean_happiness


def apply_preferred_pairs_happiness(session, preferred_pairs):
    """Award happiness bonuses to preferred-pair members for rounds spent together.

    For each pair requesting ``n`` forced games together the bonus schedule is:
        ``[max(8, 2*(n-k+2)) for k in range(n)]``
    giving e.g. [8] for n=1, [8,8] for n=2, [10,8,8] for n=3, [12,10,8,8] for n=4.

    Additionally, the never-met bonus (+2 per player) is removed for the first
    round each pair shared a game, since they were deliberately paired together.

    Session-level cached statistics are refreshed at the end.
    """
    if not preferred_pairs:
        return

    # Normalise pairs to (frozenset_of_names, n) — same logic as force_preferred_pairs_in_session
    normalized_pairs = []
    for pair_entry in preferred_pairs:
        if (
            isinstance(pair_entry, (tuple, list))
            and len(pair_entry) == 2
            and isinstance(pair_entry[1], (int, float))
        ):
            pair_fs = frozenset(pair_entry[0])
            n = max(1, int(pair_entry[1]))
        else:
            pair_fs = frozenset(pair_entry)
            n = 1
        if len(pair_fs) != 2:
            continue
        normalized_pairs.append((pair_fs, n))

    if not normalized_pairs:
        return

    # never_met_bonus_per_player — read from the first round if available, fallback 2
    never_met_per_player = 2
    if session.rounds:
        never_met_per_player = getattr(
            session.rounds[0], "never_met_bonus_per_player", 2
        )

    # Build name → player lookup
    player_by_name = {p.name: p for p in session.players}

    # Per-round award tracking so the Games Editor can reverse and re-apply bonuses
    # after manual swaps. Shape: {player_name: [bonus_r0, bonus_r1, ...]}.
    num_rounds = len(session.rounds)
    per_round_awards = {p.name: [0] * num_rounds for p in session.players}

    for pair_fs, n in normalized_pairs:
        names = sorted(pair_fs)
        p1 = player_by_name.get(names[0])
        p2 = player_by_name.get(names[1])
        if p1 is None or p2 is None:
            continue

        bonus_list = [max(8, 2 * (n - k + 2)) for k in range(n)]
        pair_player_frozenset = frozenset({p1, p2})

        rounds_together = 0  # how many rounds they have been teammates so far

        for r_idx, round_obj in enumerate(session.rounds):
            # Check if they are teammates this round
            are_teammates = any(
                pair_player_frozenset == team.players_frozenset
                for game in round_obj.games
                for team in game.teams
            )

            if are_teammates:
                k = min(rounds_together, len(bonus_list) - 1)
                bonus = bonus_list[k]
                # On the first round together, offset the never-met bonus they
                # received during generation (they were never "strangers").
                if rounds_together == 0:
                    bonus -= never_met_per_player
                p1.happiness += bonus
                p2.happiness += bonus
                per_round_awards[p1.name][r_idx] += bonus
                per_round_awards[p2.name][r_idx] += bonus
                rounds_together += 1

    # Store per-round awards on the session for Games Editor use
    session._pair_happiness_per_round = per_round_awards

    # Refresh session-level cached statistics
    happinesses = [p.happiness for p in session.players]
    session.mean_happiness = np.mean(happinesses)
    session.std_happiness = np.std(happinesses)
    session.max_and_min_happiness = (max(happinesses), min(happinesses))
    session.max_happiness_difference = (
        session.max_and_min_happiness[0] - session.max_and_min_happiness[1]
    )
    for player in session.players:
        player.relative_happiness = player.happiness - session.mean_happiness


# %%
