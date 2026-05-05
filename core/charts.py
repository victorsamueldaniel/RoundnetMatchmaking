"""charts.py - matplotlib visualisation helpers for a SessionOfRounds."""

import datetime
import os
from collections import defaultdict
import re

import matplotlib

matplotlib.use("Agg")


def plot_happiness_charts(
    session_of_rounds, save_path=None, save_png=True, png_dir=None
):
    """
    Create happiness-focused visualizations for a roundnet session.

    Parameters:
    - session_of_rounds: SessionOfRounds object
    - save_path: Optional path to save plots (deprecated, use save_png and png_dir instead)
    - save_png: Whether to save the plot as PNG (default: True)
    - png_dir: Directory to save PNG files (default: sessions/{date})
    """
    import matplotlib.pyplot as plt  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415
    import seaborn as sns  # noqa: PLC0415

    # Close any existing figures to prevent memory issues
    plt.close("all")

    # Handle default png_dir
    if png_dir is None:
        date_str = datetime.datetime.now().strftime("%d_%m_%Y")
        png_dir = os.path.join("sessions", date_str, "plots")

    # Create directory if it doesn't exist and we're saving
    if save_png and not os.path.exists(png_dir):
        os.makedirs(png_dir, exist_ok=True)

    # Set style
    plt.style.use("seaborn-v0_8")
    sns.set_palette("husl")

    # Create figure with 2x2 subplots
    fig, axes = plt.subplots(2, 2, figsize=(24, 13))

    # Prepare data
    happiness_values = [player.happiness for player in session_of_rounds.players]
    player_names = [player.name for player in session_of_rounds.players]
    levels = [player.level for player in session_of_rounds.players]
    games_played = [player.games_played for player in session_of_rounds.players]

    # 1. Happiness Distribution (top-left)
    ax1 = axes[0, 0]
    ax1.hist(
        happiness_values,
        bins=max(1, len(set(happiness_values))),
        alpha=0.7,
        color="skyblue",
        edgecolor="black",
    )
    ax1.set_title("Happiness Distribution", fontsize=14, fontweight="bold")
    ax1.set_xlabel("Happiness Score")
    ax1.set_ylabel("Number of Players")
    ax1.grid(axis="y", alpha=0.3)

    # Add statistics text
    stats_text = f"Mean: {np.mean(happiness_values):.2f}\n"
    stats_text += f"Std: {np.std(happiness_values):.2f}\n"
    stats_text += f"Min: {min(happiness_values):.2f}\n"
    stats_text += f"Max: {max(happiness_values):.2f}"
    ax1.text(
        0.02,
        0.98,
        stats_text,
        transform=ax1.transAxes,
        verticalalignment="top",
        bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.8),
    )

    # 2. Level vs Happiness Scatter (top-right)
    ax2 = axes[0, 1]
    scatter = ax2.scatter(
        levels,
        happiness_values,
        s=[p.games_played * 50 for p in session_of_rounds.players],
        alpha=0.7,
        c=happiness_values,
        cmap="RdYlGn",
    )
    ax2.set_title(
        "Level vs Happiness\n(Size = Games Played)", fontsize=14, fontweight="bold"
    )

    ax2.set_xlabel("Player Level")
    ax2.set_ylabel("Happiness Score")
    ax2.grid(alpha=0.3)

    # Add player name annotations with white boxes
    for i, (level, happiness, name) in enumerate(
        zip(levels, happiness_values, player_names)
    ):
        ax2.annotate(
            name,
            (level, happiness),
            xytext=(3, 3),
            textcoords="offset points",
            fontsize=8,
            alpha=0.9,
            ha="left",
            va="bottom",
            bbox=dict(
                boxstyle="round,pad=0.3", facecolor="white", edgecolor="gray", alpha=0.8
            ),
        )

    # 3. Happiness by Gender (bottom-left)
    ax3 = axes[1, 0]

    # Group happiness by gender
    genders = [
        getattr(player, "gender", "Unknown") for player in session_of_rounds.players
    ]
    happiness_by_gender = defaultdict(list)
    for player in session_of_rounds.players:
        gender = getattr(player, "gender", "Unknown")
        happiness_by_gender[gender].append(player.happiness)

    # Prepare data for boxplot
    box_data = []
    box_labels = []
    box_colors = {"Homme": "lightblue", "Femme": "lightpink", "Unknown": "lightgray"}
    colors_list = []

    for gender in sorted(happiness_by_gender.keys()):
        box_data.append(happiness_by_gender[gender])
        box_labels.append(f"{gender}\n(n={len(happiness_by_gender[gender])})")
        colors_list.append(box_colors.get(gender, "lightgray"))

    # Create boxplot
    bp = ax3.boxplot(
        box_data, labels=box_labels, patch_artist=True, showmeans=True, meanline=True
    )

    # Color the boxes
    for patch, color in zip(bp["boxes"], colors_list):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)

    ax3.set_title("Happiness Distribution by Gender", fontsize=14, fontweight="bold")
    ax3.set_ylabel("Happiness Score")
    ax3.grid(axis="y", alpha=0.3)

    # Add mean values as text
    for i, (gender, happiness_list) in enumerate(sorted(happiness_by_gender.items())):
        mean_val = np.mean(happiness_list)
        ax3.text(
            i + 1,
            mean_val,
            f"{mean_val:.2f}",
            ha="center",
            va="bottom",
            fontweight="bold",
            fontsize=9,
        )

    # 4. Round-by-Round Happiness Evolution (bottom-right)
    ax4 = axes[1, 1]

    # 6 base colors; 6 style groups: solid, dotted, dash-dot, dashed, dashed+x, dotted+x
    _evo_base_colors = [
        "#1f77b4",
        "#ff7f0e",
        "#2ca02c",
        "#d62728",
        "#9467bd",
        "#8c564b",
    ]
    _evo_styles = [
        {"linestyle": "-", "marker": None},  # solid
        {"linestyle": ":", "marker": None},  # dotted
        {"linestyle": "-.", "marker": None},  # dash-dot
        {"linestyle": "--", "marker": None},  # dashed
        {"linestyle": "--", "marker": "x"},  # dashed + x
        {"linestyle": ":", "marker": "x"},  # dotted + x
    ]
    _N_C = len(_evo_base_colors)  # 6
    _N_S = len(_evo_styles)  # 6

    # Extra colors for overflow (>36 players): one new unique color per overflow player
    _tab20_hex = [matplotlib.colors.to_hex(c) for c in matplotlib.cm.tab20.colors]
    _evo_overflow_colors = [c for c in _tab20_hex if c not in _evo_base_colors]

    # Sort players alphabetically for legend ordering
    sorted_players_evo = sorted(session_of_rounds.players, key=lambda p: p.name)

    legend_lines_evo = []
    for i, player in enumerate(sorted_players_evo):
        happiness_progression = [0]
        cumulative_happiness = 0

        for round_idx in range(len(session_of_rounds.rounds)):
            # Get happiness gained in this round from history
            if hasattr(player, "happiness_gained_history") and round_idx < len(
                player.happiness_gained_history
            ):
                happiness_gain = player.happiness_gained_history[round_idx]
                if happiness_gain is not None:
                    cumulative_happiness += happiness_gain
            happiness_progression.append(cumulative_happiness)

        if i < _N_C * _N_S:
            # Normal: color cycles through 6; style advances every 6 players
            color = _evo_base_colors[i % _N_C]
            style = _evo_styles[i // _N_C]
        else:
            # Overflow: one new color per player, styles wrap around
            overflow_i = i - _N_C * _N_S
            color = _evo_overflow_colors[min(overflow_i, len(_evo_overflow_colors) - 1)]
            style = _evo_styles[(i // _N_C) % _N_S]

        (line,) = ax4.plot(
            range(len(happiness_progression)),
            happiness_progression,
            linestyle=style["linestyle"],
            marker=style["marker"],
            label=player.name,
            color=color,
            alpha=0.8,
            linewidth=1.8,
            markersize=6 if style["marker"] else 0,
        )
        legend_lines_evo.append(line)

    ax4.set_title("Happiness Evolution by Round", fontsize=14, fontweight="bold")
    ax4.set_xlabel("Round Number")
    ax4.set_ylabel("Cumulative Happiness")
    # Legend in alphabetical order (players already sorted)
    ax4.legend(
        handles=legend_lines_evo,
        bbox_to_anchor=(1.05, 1),
        loc="upper left",
        fontsize=8,
    )
    ax4.grid(alpha=0.3)

    plt.tight_layout()

    # Handle saving with new parameters or legacy save_path
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"Happiness charts saved to {save_path}")
    elif save_png:
        save_file = os.path.join(png_dir, "happiness_overview.png")
        plt.savefig(save_file, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"Happiness charts saved to {save_file}")
    else:
        plt.show()

    return fig


def plot_team_analysis(session_of_rounds, save_path=None, save_png=True, png_dir=None):
    """
    Create visualizations focused on team compositions and partnerships.

    Parameters:
    - session_of_rounds: SessionOfRounds object
    - save_path: Optional path to save plots (deprecated, use save_png and png_dir instead)
    - save_png: Whether to save the plot as PNG (default: True)
    - png_dir: Directory to save PNG files (default: sessions/{date})
    """
    import matplotlib.pyplot as plt  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415
    import networkx as nx  # noqa: PLC0415

    # Close any existing figures to prevent memory issues
    plt.close("all")

    # Handle default png_dir
    if png_dir is None:
        date_str = datetime.datetime.now().strftime("%d_%m_%Y")
        png_dir = os.path.join("sessions", date_str, "plots")

    # Compute opponent pair data for the Opponent Network graph.
    opponent_pairs, _ = session_of_rounds.count_all_opponent_pairs()

    # Create directory if it doesn't exist and we're saving
    if save_png and not os.path.exists(png_dir):
        os.makedirs(png_dir, exist_ok=True)

    fig = plt.figure(figsize=(16, 12))
    grid = fig.add_gridspec(2, 2)
    ax1 = fig.add_subplot(grid[0, 0])
    ax2 = fig.add_subplot(grid[0, 1])
    ax3 = fig.add_subplot(grid[1, 0])
    ax0 = fig.add_subplot(grid[1, 1])

    # 1. Partnership Network Graph
    G = nx.Graph()

    # Add all players as nodes
    for player in session_of_rounds.players:
        G.add_node(player.name, level=player.level, happiness=player.happiness)

    # Add edges for partnerships
    partnership_counts = defaultdict(int)
    for round_obj in session_of_rounds.rounds:
        for game in round_obj.games:
            for team in game.teams:
                players_list = list(team.players)
                if len(players_list) == 2:
                    p1, p2 = players_list[0].name, players_list[1].name
                    partnership_counts[(p1, p2)] += 1
                    G.add_edge(p1, p2, weight=partnership_counts[(p1, p2)])

    # Create layout with optimized parameters to minimize edge overlap
    # Use Kamada-Kawai layout which minimizes edge crossing better than spring layout
    try:
        pos = nx.kamada_kawai_layout(G, scale=2)
    except:
        # Fallback to improved spring layout if kamada_kawai fails
        pos = nx.spring_layout(
            G, k=1.5 / np.sqrt(len(G.nodes())), iterations=50, seed=42
        )

    # Draw nodes with size based on happiness
    node_sizes = [max(50, G.nodes[node]["happiness"] * 20) for node in G.nodes()]
    node_colors = [G.nodes[node]["level"] for node in G.nodes()]

    nx.draw_networkx_nodes(
        G,
        pos,
        node_size=node_sizes,
        node_color=node_colors,
        cmap="viridis",
        alpha=0.8,
        ax=ax1,
    )

    # Draw edges with thickness based on partnership frequency
    edges = G.edges()
    weights = [G[u][v]["weight"] for u, v in edges]
    nx.draw_networkx_edges(G, pos, width=[w * 2 for w in weights], alpha=0.6, ax=ax1)

    # Add labels with white background boxes positioned to the side of nodes
    x_values = [coords[0] for coords in pos.values()]
    x_min, x_max = min(x_values), max(x_values)
    x_span = max(1e-9, x_max - x_min)
    right_label_threshold = x_max - 0.12 * x_span
    x_offset = max(0.05, 0.04 * x_span)

    for node, (x, y) in pos.items():
        # Move labels to left for rightmost nodes to avoid overlap with colorbar
        if x >= right_label_threshold:
            lx = x - x_offset
            ha = "right"
        else:
            lx = x + x_offset
            ha = "left"

        ax1.text(
            lx,
            y + 0.05,  # Slight offset upward
            node,
            fontsize=8,
            ha=ha,
            va="center",
            bbox=dict(
                boxstyle="round,pad=0.3", facecolor="white", edgecolor="gray", alpha=0.9
            ),
        )

    ax1.set_title(
        "Partnership Network\n(Node size = Happiness, Color = Level,\nEdge thickness = Partnerships)",
        fontsize=12,
        fontweight="bold",
    )
    ax1.axis("off")

    # 2. Opponent Network Graph
    # Build a graph where an edge exists if two players faced each other at least twice
    H = nx.Graph()

    # Add all players as nodes with same attributes as partnership graph
    for player in session_of_rounds.players:
        H.add_node(player.name, level=player.level, happiness=player.happiness)

    # Add edges for pairs with >= 2 meetings (opponent_pairs computed at function top)
    for pair, count in opponent_pairs.items():
        if count >= 2:
            p1, p2 = list(pair)
            H.add_edge(p1, p2, weight=count)

    # Use same layout as partnership chart to keep consistent node positions
    # 'pos' was created for the partnership graph above; fallback to spring layout
    try:
        _ = pos  # prefer the existing layout
    except NameError:
        try:
            pos = nx.kamada_kawai_layout(H, scale=2)
        except Exception:
            pos = nx.spring_layout(
                H, k=1.5 / (len(H.nodes()) ** 0.5), iterations=50, seed=42
            )

    # Draw nodes with size based on happiness and color based on level
    node_sizes_h = [max(50, H.nodes[node]["happiness"] * 20) for node in H.nodes()]
    node_colors_h = [H.nodes[node]["level"] for node in H.nodes()]

    nx.draw_networkx_nodes(
        H,
        pos,
        node_size=node_sizes_h,
        node_color=node_colors_h,
        cmap="viridis",
        alpha=0.8,
        ax=ax2,
    )

    # Add vertical colorbar legend for node colors (player level) on opponent network
    try:
        levels_h = [H.nodes[node]["level"] for node in H.nodes()]
        if levels_h:
            vmin_h, vmax_h = min(levels_h), max(levels_h)
            sm_h = matplotlib.cm.ScalarMappable(
                norm=matplotlib.colors.Normalize(vmin=vmin_h, vmax=vmax_h),
                cmap="viridis",
            )
            sm_h.set_array([])
            fig.colorbar(
                sm_h,
                ax=ax2,
                fraction=0.046,
                pad=0.02,
                orientation="vertical",
                label="Level",
            )
    except Exception:
        pass

    # Draw edges with thickness based on how many times players faced each other
    edges_h = H.edges()
    weights_h = [H[u][v]["weight"] for u, v in edges_h]
    if weights_h:
        nx.draw_networkx_edges(
            H, pos, width=[w * 2 for w in weights_h], alpha=0.6, ax=ax2
        )

    # Add labels with white background boxes positioned to the side of nodes
    for node, (x, y) in pos.items():
        if x >= right_label_threshold:
            lx = x - x_offset
            ha = "right"
        else:
            lx = x + x_offset
            ha = "left"

        ax2.text(
            lx,
            y + 0.05,
            node,
            fontsize=8,
            ha=ha,
            va="center",
            bbox=dict(
                boxstyle="round,pad=0.3", facecolor="white", edgecolor="gray", alpha=0.9
            ),
        )

    ax2.set_title(
        "Opponent Network\n(Node size = Happiness, Color = Level,\nEdge = faced >=2 times, Edge thickness = Times faced)",
        fontsize=12,
        fontweight="bold",
    )
    ax2.axis("off")

    # 3. Partner/Opponent Level Exposure Scatter
    player_level = {
        player.name: float(player.level) for player in session_of_rounds.players
    }
    max_partner_level = {player.name: -np.inf for player in session_of_rounds.players}
    max_opponent_level = {player.name: -np.inf for player in session_of_rounds.players}

    for round_obj in session_of_rounds.rounds:
        for game in round_obj.games:
            teams_in_game = list(game.teams)
            if len(teams_in_game) != 2:
                continue

            team_a_names = [p.name for p in teams_in_game[0].players]
            team_b_names = [p.name for p in teams_in_game[1].players]

            for pname in team_a_names:
                partner_names = [n for n in team_a_names if n != pname]
                if partner_names:
                    max_partner_level[pname] = max(
                        max_partner_level[pname],
                        max(player_level.get(n, -np.inf) for n in partner_names),
                    )
                if team_b_names:
                    max_opponent_level[pname] = max(
                        max_opponent_level[pname],
                        max(player_level.get(n, -np.inf) for n in team_b_names),
                    )

            for pname in team_b_names:
                partner_names = [n for n in team_b_names if n != pname]
                if partner_names:
                    max_partner_level[pname] = max(
                        max_partner_level[pname],
                        max(player_level.get(n, -np.inf) for n in partner_names),
                    )
                if team_a_names:
                    max_opponent_level[pname] = max(
                        max_opponent_level[pname],
                        max(player_level.get(n, -np.inf) for n in team_a_names),
                    )

    scatter_names = []
    scatter_x = []
    scatter_y = []
    scatter_colors = []
    for player in session_of_rounds.players:
        name = player.name
        x_val = max_partner_level.get(name, -np.inf)
        y_val = max_opponent_level.get(name, -np.inf)
        if np.isfinite(x_val) and np.isfinite(y_val):
            scatter_names.append(name)
            scatter_x.append(x_val)
            scatter_y.append(y_val)
            scatter_colors.append(player_level[name])

    if scatter_x and scatter_y:
        # Stack overlapping points vertically (same x,y) to avoid complete overlap
        stacked_x = []
        stacked_y = []
        y_span = max(scatter_y) - min(scatter_y) if len(scatter_y) > 1 else 1.0
        stack_step = max(0.03, 0.04 * y_span)
        overlap_counts = defaultdict(int)

        for x_val, y_val in zip(scatter_x, scatter_y):
            key = (x_val, y_val)
            idx = overlap_counts[key]
            overlap_counts[key] += 1
            stacked_x.append(x_val)
            stacked_y.append(y_val + idx * stack_step)

        scatter_plot = ax0.scatter(
            stacked_x,
            stacked_y,
            c=scatter_colors,
            cmap="viridis",
            s=85,
            alpha=0.9,
            edgecolors="black",
            linewidths=0.5,
        )

        for name, x_val, y_val in zip(scatter_names, stacked_x, stacked_y):
            ax0.text(x_val + 0.02, y_val + 0.02, name, fontsize=7, alpha=0.85)
    else:
        ax0.text(
            0.5,
            0.5,
            "No valid partner/opponent level data",
            ha="center",
            va="center",
            fontsize=11,
            transform=ax0.transAxes,
            bbox=dict(boxstyle="round,pad=0.5", facecolor="white", alpha=0.9),
        )

    ax0.set_title(
        "Max Partner vs Max Opponent Level\n(Color = player level)",
        fontsize=12,
        fontweight="bold",
    )
    ax0.set_xlabel("Max partner level")
    ax0.set_ylabel("Max opponent level")
    ax0.grid(alpha=0.25)

    # 4. Gender and Level Distribution (bottom-left, wider)

    # Get gender and level data
    genders = [
        getattr(player, "gender", "Unknown") for player in session_of_rounds.players
    ]
    levels_by_gender = defaultdict(list)
    for player in session_of_rounds.players:
        gender = getattr(player, "gender", "Unknown")
        levels_by_gender[gender].append(player.level)

    # Create violin plot
    positions = []
    data_to_plot = []
    labels = []
    for i, (gender, levels_list) in enumerate(levels_by_gender.items()):
        positions.append(i)
        data_to_plot.append(levels_list)
        labels.append(f"{gender}\n(n={len(levels_list)})")

    parts = ax3.violinplot(
        data_to_plot, positions=positions, showmeans=True, showmedians=True
    )

    # Color the violin plots
    for i, pc in enumerate(parts["bodies"]):
        pc.set_facecolor(plt.cm.Set2(i))
        pc.set_alpha(0.7)

    ax3.set_title("Level Distribution by Gender", fontsize=12, fontweight="bold")
    ax3.set_ylabel("Player Level")
    ax3.set_xticks(positions)
    ax3.set_xticklabels(labels)
    ax3.grid(axis="y", alpha=0.3)

    plt.tight_layout()

    # Handle saving with new parameters or legacy save_path
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"Team analysis charts saved to {save_path}")
    elif save_png:
        save_file = os.path.join(png_dir, "team_analysis.png")
        plt.savefig(save_file, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"Team analysis charts saved to {save_file}")
    else:
        plt.show()

    return fig


def plot_spectrum_analysis(
    session_of_rounds, save_path=None, save_png=True, png_dir=None
):
    """
    Create visualizations for spectrum (personality types) analysis if spectrum data is available.

    Parameters:
    - session_of_rounds: SessionOfRounds object
    - save_path: Optional path to save plots (deprecated, use save_png and png_dir instead)
    - save_png: Whether to save the plot as PNG (default: True)
    - png_dir: Directory to save PNG files (default: sessions/{date})
    """
    import matplotlib.pyplot as plt  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415

    # Close any existing figures to prevent memory issues
    plt.close("all")

    # Handle default png_dir
    if png_dir is None:
        date_str = datetime.datetime.now().strftime("%d_%m_%Y")
        png_dir = os.path.join("sessions", date_str, "plots")

    # Create directory if it doesn't exist and we're saving
    if save_png and not os.path.exists(png_dir):
        os.makedirs(png_dir, exist_ok=True)

    # Check if spectrum data is available
    spectrum_attrs = [
        "prey",
        "equilibrist",
        "challenger",
        "chill",
        "hunter",
        "classist",
    ]
    has_spectrum = any(
        hasattr(player, attr) and getattr(player, attr, 0) > 0
        for player in session_of_rounds.players
        for attr in spectrum_attrs
    )

    if not has_spectrum:
        print("No spectrum data available for analysis.")
        return None

    fig, axes = plt.subplots(2, 2, figsize=(16, 12))

    # 1. Spectrum Profile Radar Chart
    # Remove the default rectangular axes at (0,0) before creating the polar one.
    fig.delaxes(axes[0, 0])

    # Create radar chart for average spectrum values
    spectrum_names = [
        "Prey",
        "Equilibrist",
        "Challenger",
        "Chill",
        "Hunter",
        "Classist",
    ]
    spectrum_values = []

    for attr in spectrum_attrs:
        values = [getattr(player, attr, 0) for player in session_of_rounds.players]
        spectrum_values.append(np.mean(values))

    # Number of variables
    N = len(spectrum_names)

    # Compute angle for each axis
    angles = [n / float(N) * 2 * np.pi for n in range(N)]
    angles += angles[:1]  # Complete the circle

    # Add the first value at the end to close the polygon
    spectrum_values += spectrum_values[:1]

    # Plot
    ax1 = fig.add_subplot(2, 2, 1, projection="polar")
    ax1.plot(angles, spectrum_values, "o-", linewidth=2, color="blue", alpha=0.7)
    ax1.fill(angles, spectrum_values, alpha=0.25, color="blue")
    ax1.set_xticks(angles[:-1])
    ax1.set_xticklabels(spectrum_names)
    ax1.set_title("Average Spectrum Profile", fontsize=12, fontweight="bold", pad=20)

    # 2. Spectrum vs Happiness
    ax2 = axes[0, 1]

    # Calculate dominant spectrum for each player
    player_dominant_spectrums = []
    player_happiness = []

    for player in session_of_rounds.players:
        spectrum_scores = {
            name: getattr(player, attr, 0)
            for name, attr in zip(spectrum_names, spectrum_attrs)
        }
        dominant = (
            max(spectrum_scores, key=spectrum_scores.get)
            if max(spectrum_scores.values()) > 0
            else "None"
        )
        player_dominant_spectrums.append(dominant)
        player_happiness.append(player.happiness)

    # Group happiness by dominant spectrum
    spectrum_happiness = defaultdict(list)
    for spectrum, happiness in zip(player_dominant_spectrums, player_happiness):
        spectrum_happiness[spectrum].append(happiness)

    # Create box plot
    box_data = []
    box_labels = []
    for spectrum, happiness_list in spectrum_happiness.items():
        if happiness_list:  # Only include if there's data
            box_data.append(happiness_list)
            box_labels.append(f"{spectrum}\n(n={len(happiness_list)})")

    bp = ax2.boxplot(box_data, labels=box_labels, patch_artist=True)

    # Color boxes
    colors = plt.cm.Set3(np.linspace(0, 1, len(bp["boxes"])))
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)

    ax2.set_title("Happiness by Dominant Spectrum", fontsize=12, fontweight="bold")
    ax2.set_ylabel("Happiness Score")
    ax2.tick_params(axis="x", rotation=45)
    ax2.grid(axis="y", alpha=0.3)

    # 3. Spectrum Chosen History (if available)
    ax3 = axes[1, 0]

    # Analyze spec_chosen_history
    all_specs_chosen = []
    for player in session_of_rounds.players:
        if hasattr(player, "spec_chosen_history"):
            all_specs_chosen.extend(
                [spec for spec in player.spec_chosen_history if spec is not None]
            )

    if all_specs_chosen:
        spec_counts = {}
        for spec in all_specs_chosen:
            spec_counts[spec] = spec_counts.get(spec, 0) + 1

        # Create pie chart
        wedges, texts, autotexts = ax3.pie(
            spec_counts.values(),
            labels=spec_counts.keys(),
            autopct="%1.1f%%",
            startangle=90,
        )
        ax3.set_title(
            "Spectrum Types Chosen During Games", fontsize=12, fontweight="bold"
        )
    else:
        ax3.text(
            0.5,
            0.5,
            "No spectrum choices recorded",
            ha="center",
            va="center",
            transform=ax3.transAxes,
            fontsize=14,
        )
        ax3.set_title(
            "Spectrum Types Chosen During Games", fontsize=12, fontweight="bold"
        )

    # 4. Player Spectrum Heatmap
    ax4 = axes[1, 1]

    # Create matrix of player spectrum values
    spectrum_matrix = []
    player_names = [player.name for player in session_of_rounds.players]

    for player in session_of_rounds.players:
        player_spectrum = [getattr(player, attr, 0) for attr in spectrum_attrs]
        spectrum_matrix.append(player_spectrum)

    spectrum_matrix = np.array(spectrum_matrix)

    # Create heatmap
    im = ax4.imshow(spectrum_matrix, cmap="YlOrRd", aspect="auto")
    ax4.set_title("Player Spectrum Profiles", fontsize=12, fontweight="bold")
    ax4.set_xlabel("Spectrum Types")
    ax4.set_ylabel("Players")
    ax4.set_xticks(range(len(spectrum_names)))
    ax4.set_xticklabels(spectrum_names, rotation=45)
    ax4.set_yticks(range(len(player_names)))
    ax4.set_yticklabels(player_names, fontsize=8)

    # Add colorbar
    plt.colorbar(im, ax=ax4, shrink=0.8)

    # Add text annotations with dynamic color based on background darkness
    for i in range(len(player_names)):
        for j in range(len(spectrum_names)):
            # Get the background color intensity (0-10 scale for YlOrRd colormap)
            value = spectrum_matrix[i, j]
            # Use white text if value > 5 (darker colors), black otherwise
            text_color = "white" if value > 5 else "black"
            text = ax4.text(
                j,
                i,
                f"{int(spectrum_matrix[i, j])}",
                ha="center",
                va="center",
                color=text_color,
                fontsize=12,
                fontweight="bold",
            )

    plt.tight_layout()

    # Handle saving with new parameters or legacy save_path
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"Spectrum analysis charts saved to {save_path}")
    elif save_png:
        save_file = os.path.join(png_dir, "spectrum_analysis.png")
        plt.savefig(save_file, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"Spectrum analysis charts saved to {save_file}")
    else:
        plt.show()

    return fig


# Example usage function
def create_all_session_charts(
    session_of_rounds, base_filename=None, save_png=True, png_dir=None
):
    """
    Create all available charts for a session.

    Parameters:
    - session_of_rounds: SessionOfRounds object
    - base_filename: Base filename for saving (deprecated, use save_png and png_dir instead)
    - save_png: Whether to save the plots as PNG (default: True)
    - png_dir: Directory to save PNG files (default: sessions/{date}/plots)
    """
    print("Creating happiness charts...")
    fig1 = plot_happiness_charts(
        session_of_rounds,
        save_path=(
            f"{base_filename}_happiness.png" if base_filename is not None else None
        ),
        save_png=save_png,
        png_dir=png_dir,
    )

    print("Creating team analysis charts...")
    fig2 = plot_team_analysis(
        session_of_rounds,
        save_path=f"{base_filename}_teams.png" if base_filename is not None else None,
        save_png=save_png,
        png_dir=png_dir,
    )

    print("Creating spectrum analysis charts...")
    fig3 = plot_spectrum_analysis(
        session_of_rounds,
        save_path=(
            f"{base_filename}_spectrum.png" if base_filename is not None else None
        ),
        save_png=save_png,
        png_dir=png_dir,
    )

    print("All charts created successfully!")

    # Close all figures to free memory
    import matplotlib.pyplot as plt  # noqa: PLC0415

    plt.close("all")

    return fig1, fig2, fig3


def _playershort(player):
    player_name_surname_split = re.split(r"(?=[A-Z])", player)
    player_first_name = player_name_surname_split[1]

    if len(player_name_surname_split) == 3:
        player_surname = player_name_surname_split[2]
        length_surname = len(player_surname)
        return (
            player_first_name[: min(8 - length_surname, len(player_first_name))]
            + player_surname
        )
    else:
        return player[: min(8, len(player))]


def create_session_games_png(
    session_of_rounds, save_path: str, show_levels: bool = False
) -> None:
    """Render the session games as a PNG table matching the Excel Games sheet layout.

    Rounds are stacked vertically. Each round has a dark-blue title row, a header
    row, one row per game (with Team-A / VS / Team-B / Δ Level / Info columns), and
    an optional 'Not Playing' row — identical to the exported xlsx.

    Parameters
    ----------
    session_of_rounds : SessionOfRounds
    save_path : str
        Full path where the PNG will be written.
    """
    import matplotlib.pyplot as plt  # noqa: PLC0415
    import matplotlib.patches as mpatches  # noqa: PLC0415

    plt.close("all")

    rounds = session_of_rounds.rounds
    if not rounds:
        return

    # ------------------------------------------------------------------
    # Column definitions  [label, raw_weight]
    # Matches Excel widths: [8, 18, 18, 6, 18, 18, 12, 20]
    # ------------------------------------------------------------------
    COL_DEFS = [
        ("#", 3),
        ("T1  P1", 11),
        ("T1  P2", 11),
        ("VS", 4),
        ("T2  P1", 11),
        ("T2  P2", 11),
        ("Δ", 6),
        ("Info", 9),
    ]
    total_w = sum(c[1] for c in COL_DEFS)
    col_ws = [c[1] / total_w for c in COL_DEFS]
    col_xs = []
    cx = 0.0
    for w in col_ws:
        col_xs.append(cx)
        cx += w
    col_labels = [c[0] for c in COL_DEFS]

    # ------------------------------------------------------------------
    # Row-height units  (1 unit = ROW_INCH inches)
    # ------------------------------------------------------------------
    TITLE_H = 1.0  # round title row
    HEADER_H = 0.75  # column-header row
    ROW_H = 0.75  # one game row
    SIT_H = 0.75  # "Not Playing" row
    SPACER_H = 0.45  # gap between rounds
    ROW_INCH = 0.38  # inches per unit

    # ------------------------------------------------------------------
    # Compute per-round layout specs and total figure height
    # ------------------------------------------------------------------
    specs = []
    total_h = 0.0
    for r_idx, rnd in enumerate(rounds):
        n_g = len(rnd.games)
        has_sit = bool(rnd.not_playing)
        h = TITLE_H + HEADER_H + n_g * ROW_H + (SIT_H if has_sit else 0) + SPACER_H
        specs.append(
            {
                "rnd": rnd,
                "r_idx": r_idx,
                "n_g": n_g,
                "has_sit": has_sit,
                "y_top": total_h,
                "h": h,
            }
        )
        total_h += h

    # Portrait smartphone ratio (~9:19.5 → height/width ≈ 2.16)
    _TARGET_ASPECT = 2.16
    fig_h = max(3.0, total_h * ROW_INCH + 0.6)
    fig_w = max(3.0, fig_h / _TARGET_ASPECT)

    fig, ax = plt.subplots(figsize=(fig_w, fig_h), facecolor="white")
    # y = 0 at top, increases downward
    ax.set_xlim(0, 1)
    ax.set_ylim(total_h, 0)
    ax.axis("off")

    # ------------------------------------------------------------------
    # Colors — identical to the xlsx export
    # ------------------------------------------------------------------
    C_ROUND = "#305496"  # dark blue  — round title
    C_HEADER = "#366092"  # medium blue — column headers
    C_TEAM_A = "#B4C7E7"  # light blue  — Team A cells
    C_TEAM_B = "#F4B084"  # orange      — Team B cells
    C_VS = "#E7E6E6"  # light gray  — VS cell
    C_LEVEL = "#FFF2CC"  # pale yellow — Δ Level cell
    C_SIT = "#FCE4D6"  # light peach — Not Playing row
    C_WHITE = "#FFFFFF"
    C_ROW2 = "#F2F7FF"  # subtle tint for alternating rows
    C_BORDER = "#B8B8B8"

    def _diff_fg(d: float) -> str:
        if d <= 0.3:
            return "#1A6B2A"  # dark green
        if d <= 0.8:
            return "#9B4400"  # dark orange
        return "#8B0000"  # dark red

    def _cell(
        x, y, w, h, txt, bg, fg="#111111", bold=False, fs=7.5, ha="center", va="center"
    ):
        """Draw one filled rectangle with centred/left-aligned text."""
        rect = mpatches.FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="square,pad=0",
            linewidth=0.45,
            edgecolor=C_BORDER,
            facecolor=bg,
            transform=ax.transData,
            zorder=2,
            clip_on=False,
        )
        ax.add_patch(rect)
        tx = (x + w / 2) if ha == "center" else (x + w * 0.025)
        ax.text(
            tx,
            y + h / 2,
            txt,
            ha=ha,
            va=va,
            fontsize=fs,
            color=fg,
            fontweight="bold" if bold else "normal",
            transform=ax.transData,
            zorder=3,
            clip_on=True,
        )

    # ------------------------------------------------------------------
    # Draw rounds
    # ------------------------------------------------------------------
    for spec in specs:
        rnd = spec["rnd"]
        r_idx = spec["r_idx"]
        y = spec["y_top"]

        # ---- Round title ------------------------------------------------
        _ABBREV = {
            "balanced": "bal",
            "level": "lvl",
            "mixed": "mix",
            "open": "opn",
        }
        rtype = (rnd.type_preference or "").strip()
        gpref = (rnd.gender_preference or "").strip()
        rtype_abbr = _ABBREV.get(rtype.lower(), rtype)
        gpref_abbr = _ABBREV.get(gpref.lower(), gpref)
        parts = [
            p
            for p in [rtype_abbr, gpref_abbr]
            if p and p.lower() not in ("none", "any", "")
        ]
        suffix = f"   [{' / '.join(parts)}]" if parts else ""
        _cell(
            0,
            y,
            1.0,
            TITLE_H,
            f"ROUND {r_idx + 1}{suffix}",
            C_ROUND,
            fg="#FFFFFF",
            bold=True,
            fs=8.0,
        )
        y += TITLE_H

        # ---- Column headers ---------------------------------------------
        for lbl, x0, w in zip(col_labels, col_xs, col_ws):
            _cell(x0, y, w, HEADER_H, lbl, C_HEADER, fg="#FFFFFF", bold=True, fs=6.5)
        y += HEADER_H

        # ---- Game rows --------------------------------------------------
        for g_idx, game in enumerate(rnd.games):
            row_bg = C_WHITE if g_idx % 2 == 0 else C_ROW2
            pA1 = game.team_A.player_A
            pA2 = game.team_A.player_B
            pB1 = game.team_B.player_A
            pB2 = game.team_B.player_B
            diff = game.level_difference
            type_str = (game.type_preference or "").strip()
            gender_str = (game.gender_preference or "").strip()
            _ABBREV_GAME = {
                "balanced": "bal",
                "level": "lvl",
                "mixed": "mix",
                "female": "F",
                "male": "M",
                "open": "opn",
            }
            info = _ABBREV_GAME.get(type_str.lower(), type_str)
            gender_abbr = _ABBREV_GAME.get(gender_str.lower(), gender_str)
            if gender_abbr and gender_abbr.lower() not in ("none", ""):
                info += (" / " if info else "") + gender_abbr

            row = [
                (str(g_idx + 1), row_bg, "#333333", False),
                (
                    (
                        f"{_playershort(pA1.name)}\n({pA1.level:.1f})"
                        if show_levels
                        else _playershort(pA1.name)
                    ),
                    C_TEAM_A,
                    "#1A3A6C",
                    False,
                ),
                (
                    (
                        f"{_playershort(pA2.name)}\n({pA2.level:.1f})"
                        if show_levels
                        else _playershort(pA2.name)
                    ),
                    C_TEAM_A,
                    "#1A3A6C",
                    False,
                ),
                ("VS", C_VS, "#333333", True),
                (
                    (
                        f"{_playershort(pB1.name)}\n({pB1.level:.1f})"
                        if show_levels
                        else _playershort(pB1.name)
                    ),
                    C_TEAM_B,
                    "#5C1A00",
                    False,
                ),
                (
                    (
                        f"{_playershort(pB2.name)}\n({pB2.level:.1f})"
                        if show_levels
                        else _playershort(pB2.name)
                    ),
                    C_TEAM_B,
                    "#5C1A00",
                    False,
                ),
                (f"{diff:.2f}", C_LEVEL, _diff_fg(diff), True),
                (info, row_bg, "#555555", False),
            ]
            # Player-name columns: indices 1,2,4,5 get +20% font size
            _NAME_COLS = {1, 2, 4, 5}
            for col_i, ((txt, bg, fg, bold), x0, w) in enumerate(
                zip(row, col_xs, col_ws)
            ):
                if _NAME_COLS:
                    if show_levels:
                        fs = 8.0
                    else:
                        fs = 9.5
                else:
                    fs = 7.0
                _cell(x0, y, w, ROW_H, txt, bg, fg=fg, bold=bold, fs=fs)
            y += ROW_H

        # ---- Not-playing row --------------------------------------------
        if rnd.not_playing:
            names = ", ".join(p.name for p in rnd.not_playing)
            _cell(
                0,
                y,
                1.0,
                SIT_H,
                f"Not Playing:  {names}",
                C_SIT,
                fg="#333333",
                fs=7.0,
                ha="left",
            )
            y += SIT_H

    # ------------------------------------------------------------------
    # Title and save
    # ------------------------------------------------------------------
    fig.suptitle(
        "Session Games",
        fontsize=11,
        fontweight="bold",
        y=0.999,
        color="#111111",
    )

    plt.tight_layout(pad=0.3)
    os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
    fig.savefig(save_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def create_session_games_round_images(
    session_of_rounds, show_levels: bool = False
) -> list:
    """Return a list of PIL Images, one per round, with consistent widths.

    Each image renders a single round using the same visual style as
    ``create_session_games_png`` but split into individual images so the
    Session Games tab can display them as separate, click-able tiles.

    Parameters
    ----------
    session_of_rounds : SessionOfRounds
    show_levels : bool
        Whether to append ``(level)`` to player names.

    Returns
    -------
    list[PIL.Image.Image]
        One image per round, in the same order as ``session_of_rounds.rounds``.
    """
    import io  # noqa: PLC0415

    import matplotlib.patches as mpatches  # noqa: PLC0415
    import matplotlib.pyplot as plt  # noqa: PLC0415
    from PIL import Image  # noqa: PLC0415

    plt.close("all")

    rounds = session_of_rounds.rounds
    if not rounds:
        return []

    # ------------------------------------------------------------------ constants
    TITLE_H = 1.0
    HEADER_H = 0.75
    ROW_H = 0.75
    SIT_H = 0.75
    SPACER_H = 0.45
    ROW_INCH = 0.38
    _TARGET_ASPECT = 2.16

    COL_DEFS = [
        ("#", 3),
        ("T1  P1", 11),
        ("T1  P2", 11),
        ("VS", 4),
        ("T2  P1", 11),
        ("T2  P2", 11),
        ("Δ", 6),
        ("Info", 9),
    ]
    total_col_w = sum(c[1] for c in COL_DEFS)
    col_ws = [c[1] / total_col_w for c in COL_DEFS]
    col_xs: list = []
    cx = 0.0
    for w in col_ws:
        col_xs.append(cx)
        cx += w
    col_labels = [c[0] for c in COL_DEFS]

    # Derive a *consistent* figure width from the combined-session layout so that
    # individual round images are the same width as the combined PNG.
    total_h = sum(
        TITLE_H
        + HEADER_H
        + len(rnd.games) * ROW_H
        + (SIT_H if rnd.not_playing else 0)
        + SPACER_H
        for rnd in rounds
    )
    fig_h_total = max(3.0, total_h * ROW_INCH + 0.6)
    fig_w = max(3.0, fig_h_total / _TARGET_ASPECT)

    # ------------------------------------------------------------------ colors
    C_ROUND = "#305496"
    C_HEADER = "#366092"
    C_TEAM_A = "#B4C7E7"
    C_TEAM_B = "#F4B084"
    C_VS = "#E7E6E6"
    C_LEVEL = "#FFF2CC"
    C_SIT = "#FCE4D6"
    C_WHITE = "#FFFFFF"
    C_ROW2 = "#F2F7FF"
    C_BORDER = "#B8B8B8"

    def _diff_fg(d: float) -> str:
        if d <= 0.3:
            return "#1A6B2A"
        if d <= 0.8:
            return "#9B4400"
        return "#8B0000"

    # ------------------------------------------------------------------ per-round render
    images = []
    _ABBREV = {"balanced": "bal", "level": "lvl", "mixed": "mix", "open": "opn"}
    _ABBREV_GAME = {
        "balanced": "bal",
        "level": "lvl",
        "mixed": "mix",
        "female": "F",
        "male": "M",
        "open": "opn",
    }
    _NAME_COLS = {1, 2, 4, 5}

    for disp_idx, rnd in enumerate(rounds):
        n_g = len(rnd.games)
        has_sit = bool(rnd.not_playing)
        rnd_h = TITLE_H + HEADER_H + n_g * ROW_H + (SIT_H if has_sit else 0) + SPACER_H
        fig_h = max(1.0, rnd_h * ROW_INCH + 0.1)

        fig, ax = plt.subplots(figsize=(fig_w, fig_h), facecolor="white")
        ax.set_xlim(0, 1)
        ax.set_ylim(rnd_h, 0)
        ax.axis("off")

        # Local _cell bound to this iteration's ax via default argument
        def _cell(
            x,
            y,
            w,
            h,
            txt,
            bg,
            fg="#111111",
            bold=False,
            fs=7.5,
            ha="center",
            va="center",
            _ax=ax,
            _border=C_BORDER,
        ):
            rect = mpatches.FancyBboxPatch(
                (x, y),
                w,
                h,
                boxstyle="square,pad=0",
                linewidth=0.45,
                edgecolor=_border,
                facecolor=bg,
                transform=_ax.transData,
                zorder=2,
                clip_on=False,
            )
            _ax.add_patch(rect)
            tx = (x + w / 2) if ha == "center" else (x + w * 0.025)
            _ax.text(
                tx,
                y + h / 2,
                txt,
                ha=ha,
                va="center",
                fontsize=fs,
                color=fg,
                fontweight="bold" if bold else "normal",
                transform=_ax.transData,
                zorder=3,
                clip_on=True,
            )

        y = 0.0

        # Round title
        rtype = (rnd.type_preference or "").strip()
        gpref = (rnd.gender_preference or "").strip()
        rtype_abbr = _ABBREV.get(rtype.lower(), rtype)
        gpref_abbr = _ABBREV.get(gpref.lower(), gpref)
        parts = [
            p
            for p in [rtype_abbr, gpref_abbr]
            if p and p.lower() not in ("none", "any", "")
        ]
        suffix = f"   [{' / '.join(parts)}]" if parts else ""
        _cell(
            0,
            y,
            1.0,
            TITLE_H,
            f"ROUND {disp_idx + 1}{suffix}",
            C_ROUND,
            fg="#FFFFFF",
            bold=True,
            fs=8.0,
        )
        y += TITLE_H

        # Column headers
        for lbl, x0, w in zip(col_labels, col_xs, col_ws):
            _cell(x0, y, w, HEADER_H, lbl, C_HEADER, fg="#FFFFFF", bold=True, fs=6.5)
        y += HEADER_H

        # Game rows
        for g_idx, game in enumerate(rnd.games):
            row_bg = C_WHITE if g_idx % 2 == 0 else C_ROW2

            pA1 = game.team_A.player_A
            pA2 = game.team_A.player_B
            pB1 = game.team_B.player_A
            pB2 = game.team_B.player_B
            diff = game.level_difference
            type_str = (game.type_preference or "").strip()
            gender_str = (game.gender_preference or "").strip()
            info = _ABBREV_GAME.get(type_str.lower(), type_str)
            gender_abbr = _ABBREV_GAME.get(gender_str.lower(), gender_str)
            if gender_abbr and gender_abbr.lower() not in ("none", ""):
                info += (" / " if info else "") + gender_abbr

            row_data = [
                (str(g_idx + 1), row_bg, "#333333", False),
                (
                    (
                        f"{_playershort(pA1.name)}\n({pA1.level:.1f})"
                        if show_levels
                        else _playershort(pA1.name)
                    ),
                    C_TEAM_A,
                    "#1A3A6C",
                    False,
                ),
                (
                    (
                        f"{_playershort(pA2.name)}\n({pA2.level:.1f})"
                        if show_levels
                        else _playershort(pA2.name)
                    ),
                    C_TEAM_A,
                    "#1A3A6C",
                    False,
                ),
                ("VS", C_VS, "#333333", True),
                (
                    (
                        f"{_playershort(pB1.name)}\n({pB1.level:.1f})"
                        if show_levels
                        else _playershort(pB1.name)
                    ),
                    C_TEAM_B,
                    "#5C1A00",
                    False,
                ),
                (
                    (
                        f"{_playershort(pB2.name)}\n({pB2.level:.1f})"
                        if show_levels
                        else _playershort(pB2.name)
                    ),
                    C_TEAM_B,
                    "#5C1A00",
                    False,
                ),
                (f"{diff:.2f}", C_LEVEL, _diff_fg(diff), True),
                (info, row_bg, "#555555", False),
            ]
            for col_i, ((txt, bg, fg, bold), x0, w) in enumerate(
                zip(row_data, col_xs, col_ws)
            ):
                if _NAME_COLS:
                    if show_levels:
                        fs = 8.0
                    else:
                        fs = 9.5
                else:
                    fs = 7.0
                _cell(x0, y, w, ROW_H, txt, bg, fg=fg, bold=bold, fs=fs)
            y += ROW_H

        # Not-playing row
        if rnd.not_playing:
            names = ", ".join(p.name for p in rnd.not_playing)
            _cell(
                0,
                y,
                1.0,
                SIT_H,
                f"Not Playing:  {names}",
                C_SIT,
                fg="#333333",
                fs=7.0,
                ha="left",
            )

        plt.tight_layout(pad=0.1)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="white")
        buf.seek(0)
        img = Image.open(buf).copy()
        images.append(img)
        buf.close()
        plt.close(fig)

    return images


if __name__ == "__main__":
    # Example usage
    good_numbers = [1, 3, 4, 5, 7, 9]
    list_of_players = [
        Player(main_df.loc[name]) for name in main_df.iloc[good_numbers].index
    ]
    session_of_rounds = SessionOfRounds(
        list_of_players,
        amount_of_rounds=6,
        type_preferences=["balanced"] * 3 + ["level"] * 3,
        level_gap_tol=1.5,
        num_iter=50,
        seed=3,
    )


# %%
