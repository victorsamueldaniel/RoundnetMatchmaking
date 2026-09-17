"""Chart data and session summaries for the web client.

Every block mirrors one subplot of core/charts.py, but returns data instead of
a matplotlib figure so the browser can draw interactive charts.
"""

import math
from collections import defaultdict

import networkx as nx
import numpy as np

from core.models import compute_session_score

SPECTRUM_ATTRS = ["prey", "equilibrist", "challenger", "chill", "hunter", "classist"]
SPECTRUM_NAMES = ["Prey", "Equilibrist", "Challenger", "Chill", "Hunter", "Classist"]


def _f(value):
    return None if value is None else float(value)


def happiness_overview(session):
    players = session.players
    happiness = [float(p.happiness) for p in players]
    evolution = []
    for p in sorted(players, key=lambda p: p.name):
        cumulative = [0.0]
        for gain in p.happiness_gained_history:
            cumulative.append(cumulative[-1] + (gain or 0))
        evolution.append({"name": p.name, "values": cumulative})
    by_gender = defaultdict(list)
    for p in players:
        gender = p.gender if isinstance(p.gender, str) else "Unknown"
        by_gender[gender].append(float(p.happiness))
    return {
        "stats": {
            "mean": float(np.mean(happiness)),
            "std": float(np.std(happiness)),
            "min": float(np.min(happiness)),
            "max": float(np.max(happiness)),
        },
        "players": [
            {
                "name": p.name,
                "level": float(p.level),
                "happiness": float(p.happiness),
                "games_played": int(p.games_played),
            }
            for p in players
        ],
        "by_gender": [
            {"gender": g, "values": by_gender[g]} for g in sorted(by_gender.keys())
        ],
        "evolution": evolution,
    }


def team_analysis(session):
    players = session.players
    partner_counts = defaultdict(int)
    max_partner = {}
    max_opponent = {}
    for round_ in session.rounds:
        for game in round_.games:
            for team, other in (
                (game.team_A, game.team_B),
                (game.team_B, game.team_A),
            ):
                a, b = team.players
                partner_counts[tuple(sorted((a.name, b.name)))] += 1
                for p, mate in ((a, b), (b, a)):
                    max_partner[p.name] = max(
                        max_partner.get(p.name, -math.inf), mate.level
                    )
                    for opp in other.players:
                        max_opponent[p.name] = max(
                            max_opponent.get(p.name, -math.inf), opp.level
                        )

    graph = nx.Graph()
    for p in players:
        graph.add_node(p.name)
    for (a, b), n in partner_counts.items():
        graph.add_edge(a, b, weight=n)
    try:
        pos = nx.kamada_kawai_layout(graph, scale=2)
    except Exception:
        pos = nx.spring_layout(
            graph, k=1.5 / math.sqrt(max(len(players), 1)), iterations=50, seed=42
        )

    opponent_pairs, _ = session.count_all_opponent_pairs()
    levels_by_gender = {}
    for p in players:
        gender = p.gender if isinstance(p.gender, str) else "Unknown"
        levels_by_gender.setdefault(gender, []).append(float(p.level))

    scatter = []
    overlap = defaultdict(int)
    names = [p.name for p in players if p.name in max_partner]
    ys = [max_opponent[n] for n in names]
    y_span = (max(ys) - min(ys)) if len(ys) > 1 else 1.0
    step = max(0.03, 0.04 * y_span)
    level_by_name = {p.name: float(p.level) for p in players}
    for name in names:
        key = (max_partner[name], max_opponent[name])
        idx = overlap[key]
        overlap[key] += 1
        scatter.append(
            {
                "name": name,
                "x": float(key[0]),
                "y": float(key[1] + idx * step),
                "level": level_by_name[name],
            }
        )

    return {
        "nodes": [
            {
                "name": p.name,
                "level": float(p.level),
                "happiness": float(p.happiness),
                "x": float(pos[p.name][0]),
                "y": float(pos[p.name][1]),
            }
            for p in players
        ],
        "partner_edges": [
            {"a": a, "b": b, "count": n} for (a, b), n in partner_counts.items()
        ],
        "opponent_edges": [
            {"a": sorted(pair)[0], "b": sorted(pair)[1], "count": n}
            for pair, n in opponent_pairs.items()
            if n >= 2
        ],
        "levels_by_gender": [
            {"gender": g, "values": v} for g, v in levels_by_gender.items()
        ],
        "max_partner_vs_opponent": scatter,
    }


def spectrum_analysis(session):
    players = session.players
    matrix = [[float(getattr(p, a, 0) or 0) for a in SPECTRUM_ATTRS] for p in players]
    if not any(v > 0 for row in matrix for v in row):
        return None
    dominant = {}
    for p, row in zip(players, matrix):
        best = max(row)
        name = SPECTRUM_NAMES[row.index(best)] if best > 0 else "None"
        dominant.setdefault(name, []).append(float(p.happiness))
    chosen = {}
    for p in players:
        for spec in p.spec_chosen_history:
            if spec is not None:
                chosen[spec] = chosen.get(spec, 0) + 1
    return {
        "attributes": SPECTRUM_NAMES,
        "average": [float(np.mean([row[i] for row in matrix])) for i in range(6)],
        "happiness_by_dominant": [
            {"spectrum": k, "values": v} for k, v in dominant.items()
        ],
        "chosen_counts": [{"spectrum": k, "count": v} for k, v in chosen.items()],
        "heatmap": {"players": [p.name for p in players], "values": matrix},
    }


def repetitions(session):
    teammate_pairs, teammate_rounds = session.count_all_pairs()
    opponent_pairs, opponent_rounds = session.count_all_opponent_pairs()

    def rows(counts, rounds, minimum):
        out = [
            {"players": sorted(pair), "count": n, "rounds": rounds[pair]}
            for pair, n in counts.items()
            if n >= minimum
        ]
        return sorted(out, key=lambda r: (-r["count"], r["players"]))

    return {
        "teammates": rows(teammate_pairs, teammate_rounds, 2),
        "opponents": rows(opponent_pairs, opponent_rounds, 2),
        "never_met": session.get_never_met_sentences(),
    }


def rounds_view(session):
    """Round structure plus per-player gains, for the editor and the games view."""
    out = []
    for r_idx, round_ in enumerate(session.rounds):

        def player(p):
            history = p.happiness_gained_history
            gain = history[r_idx] if r_idx < len(history) else None
            specs = p.spec_chosen_history
            return {
                "name": p.name,
                "level": float(p.level),
                "gender": p.gender if isinstance(p.gender, str) else None,
                "gain": _f(gain),
                "spec": specs[r_idx] if r_idx < len(specs) else None,
            }

        out.append(
            {
                "type_preference": round_.type_preference,
                "gender_preference": round_.gender_preference,
                "games": [
                    {
                        "team_a": [player(p) for p in g.team_A.players],
                        "team_b": [player(p) for p in g.team_B.players],
                        "level_difference": float(g.level_difference),
                        "gender_ok": bool(g.is_gender_preference_satisfied),
                    }
                    for g in round_.games
                ],
                "bench": [player(p) for p in round_.not_playing],
            }
        )
    return out


def session_summary(session, lambda_weight, percentile):
    happiness = [float(p.happiness) for p in session.players]
    ordered = sorted(session.players, key=lambda p: p.happiness)
    return {
        "score": compute_session_score(
            session.players,
            "mean_min_max_happiness_objective",
            lambda_weight=lambda_weight,
            percentile=percentile,
        ),
        "mean": float(np.mean(happiness)),
        "std": float(np.std(happiness)),
        "min": float(np.min(happiness)),
        "max": float(np.max(happiness)),
        "players": [
            {
                "name": p.name,
                "level": float(p.level),
                "gender": p.gender if isinstance(p.gender, str) else None,
                "happiness": float(p.happiness),
                "games_played": int(p.games_played),
            }
            for p in session.players
        ],
        "least_happy": [p.name for p in ordered[:3]],
        "happiest": [p.name for p in ordered[::-1][:3]],
    }
