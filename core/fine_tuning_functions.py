# %%
################################################################################
################################################################################
################################################################################
################################################################################
################################################################################
################################################################################
################################################################################
###################                                         ####################
###################  ###### ####### ####### #     # ####### ####################
################### #       #          #    #     # #     # ####################
###################  ####   #######    #    #     # ####### ####################
###################       # #          #    #     # #       ####################
################### ######  #######    #    ####### #       ####################
###################                                         ####################
################################################################################
################################################################################
################################################################################
################################################################################
################################################################################
################################################################################
################################################################################
import sys as _sys

if "main" not in _sys.modules:
    import core.main as _core_main

    _sys.modules["main"] = _core_main
import main
import random
import pandas as pd
import numpy as np
import re
from itertools import combinations
import datetime
from math import comb

# from str_to_ascii import *
import pickle
import os
from datetime import datetime

# %%
###############################################################################################
#                                                                                             #
# ######  #     # ##    #        ###### #######  ######  ######       ####### ####### ##    # #
# #     # #     # # #   #       #       #       #       #             #       #       # #   # #
# ######  #     # #  #  #        ####   #######  ####    ####         #  #### ####### #  #  # #
# #   ##  #     # #   # #             # #             #       #       #     # #       #   # # #
# #    ## ####### #    ## ##### ######  ####### ######  ######  ##### ####### ####### #    ## #
#                                                                                             #
###############################################################################################
# NOTE: run_session_generation_with_seed_optimization has been moved to main.py
# Import it from main: from main import run_session_generation_with_seed_optimization
run_session_generation_with_seed_optimization = (
    main.run_session_generation_with_seed_optimization
)


def _show_or_close_plot(plt_module):
    """Show plots only on interactive backends; close silently on headless ones."""
    backend = ""
    try:
        backend = (plt_module.get_backend() or "").lower()
    except Exception:
        backend = ""

    if "agg" in backend:
        plt_module.close()
        return

    plt_module.show()


# %%
###############################################################################################################
#                                                                                                             #
# ####### #       ####### #######        ###### #     # ####### ####### #######       ######  #######  ###### #
# #     # #       #     #    #          #       #     # #       #       #     #       #     # #       #       #
# ####### #       #     #    #           ####   #  #  # ####### ####### #######       ######  #######  ####   #
# #       #       #     #    #                # ##   ## #       #       #             #   ##  #             # #
# #        ###### #######    #    ##### ######  #     # ####### ####### #       ##### #    ## ####### ######  #
#                                                                                                             #
###############################################################################################################
# %%
def plot_parameter_sweep_results(
    parameter_to_metric_data,
    parameter_name,
    metric_name="happiness",
    plot_title=None,
    xlabel=None,
    ylabel=None,
):
    """
    Create a box and whisker plot for parameter sweep results.

    Args:
        parameter_to_metric_data: Dict mapping parameter values to metric data
        parameter_name: Name of the parameter being varied
        metric_name: Name of the metric being measured
        plot_title: Title for the box plot (optional)
        xlabel: X-axis label (optional, defaults to parameter_name)
        ylabel: Y-axis label (optional, defaults to metric_name)
    """
    import matplotlib.pyplot as plt

    # Prepare data for box plots
    param_values_sorted = sorted(parameter_to_metric_data.keys())
    metrics_by_param = []

    for param_value in param_values_sorted:
        data = parameter_to_metric_data[param_value]
        metric_values = [value for name, value in data[f"all_{metric_name}"]]
        metrics_by_param.append(metric_values)

    # Create box and whisker plot
    plt.figure(figsize=(14, 8))
    box_plot = plt.boxplot(
        metrics_by_param,
        positions=range(len(param_values_sorted)),
        widths=0.6,
        patch_artist=True,
        showmeans=True,
        meanprops=dict(marker="D", markerfacecolor="red", markersize=8),
    )

    # Color the boxes
    for patch in box_plot["boxes"]:
        patch.set_facecolor("lightblue")
        patch.set_alpha(0.7)

    # Set x-axis labels
    plt.xticks(
        range(len(param_values_sorted)),
        [str(np.round(pv, 2)) for pv in param_values_sorted],
        rotation=45,
    )
    plt.xlabel(
        xlabel if xlabel else parameter_name.replace("_", " ").title(), fontsize=12
    )
    plt.ylabel(ylabel if ylabel else metric_name.replace("_", " ").title(), fontsize=12)
    plt.title(
        (
            plot_title
            if plot_title
            else f"Distribution of Player {metric_name.title()} by {parameter_name.replace('_', ' ').title()}"
        ),
        fontsize=14,
        fontweight="bold",
    )
    plt.grid(True, alpha=0.3, axis="y")
    plt.tight_layout()
    _show_or_close_plot(plt)


# %%
#######################################################################################
#                                                                                     #
# ######  #     # ##    #       #######  #####  ######         ###### #     # ####### #
# #     # #     # # #   #       #     # #     # #     #       #       #     # #     # #
# ######  #     # #  #  #       ####### ####### ######         ####   #  #  # ####### #
# #   ##  #     # #   # #       #       #     # #   ##              # ##   ## #       #
# #    ## ####### #    ## ##### #       #     # #    ## ##### ######  #     # #       #
#                                                                                     #
#######################################################################################
def run_parameter_sweep(
    df,
    parameter_name,
    parameter_values,
    metric_name="happiness",
    metric_extractor=lambda player: player.happiness,
    objective_function_factory=None,
    parameter_updater=None,
    session_kwargs=None,
    plot_title=None,
    xlabel=None,
    ylabel=None,
    print_metrics=False,
    show_plot=True,
):
    """
    Run a parameter sweep to analyze the effect of a parameter on a metric.

    Args:
        df: DataFrame with player data
        parameter_name: Name of the parameter being varied (e.g., "lambda_weight", "num_iter")
        parameter_values: List/array of parameter values to test
        metric_name: Name of the metric being measured (default: "happiness")
        metric_extractor: Function to extract metric from a player object (default: lambda player: player.happiness)
        objective_function_factory: Function that takes a parameter value and returns an objective function (optional)
        parameter_updater: Function that takes (session_kwargs, param_value) and updates session_kwargs in-place.
                          If None, the parameter_name is used as a key in session_kwargs.
        session_kwargs: Dict of keyword arguments to pass to run_session_generation_with_seed_optimization
        plot_title: Title for the box plot (optional)
        xlabel: X-axis label (optional, defaults to parameter_name)
        ylabel: Y-axis label (optional, defaults to metric_name)
        show_plot: Whether to display the box plot (default: True)

    Returns:
        dict: Mapping from parameter values to metric data
        last session_of_rounds object

    Example usage:
        # Sweep over num_iter
        run_parameter_sweep(df, "num_iter", [50, 100, 150, 200])

        # Sweep over lambda_weight with custom objective function
        run_parameter_sweep(
            df,
            "lambda_weight",
            [0, 1, 2, 3],
            objective_function_factory=lambda lw: lambda x: main.mean_min_max_happiness_objective(x, lambda_weight=lw)
        )

        # Sweep over weight_same_teammate
        run_parameter_sweep(df, "weight_same_teammate", [1, 3, 5, 7])
    """
    # Default session kwargs
    if session_kwargs is None:
        session_kwargs = {
            "amount_of_rounds": 4,
            "type_preferences": ["level", "level", "balanced", "balanced"],
            "gender_preferences": ["open", "mixed", "mixed", "open"],
            "level_gap_tol": 0.8,
            "num_iter": 100,
            "weight_same_teammate": 5,
            "first_seed": 0,
            "last_seed": 10,
            "spectrum": True,
            "games_per_round_each_round": None,
            "rounds_reordering": [3, 4, 2, 1],
            "print_progress": False,
        }

    parameter_to_metric_data = {}
    last_session = None

    for param_value in parameter_values:
        print(
            "################################################################################"
        )
        print(
            "################################################################################"
        )
        print(
            f"############################### {parameter_name.upper()}: {param_value} ###############################"
        )

        # Update session kwargs with current parameter value
        current_kwargs = session_kwargs.copy()

        # Use custom parameter updater if provided
        if parameter_updater is not None:
            parameter_updater(current_kwargs, param_value)
        else:
            # Default behavior: directly set the parameter in session_kwargs
            current_kwargs[parameter_name] = param_value

        # Apply objective function factory if provided
        if objective_function_factory is not None:
            current_kwargs["objective_function"] = objective_function_factory(
                param_value
            )

        # Run session generation
        session_of_rounds, chosen_seed = (
            main.run_session_generation_with_seed_optimization(df, **current_kwargs)
        )
        last_session = session_of_rounds

        # Collect all players' metric values
        all_metrics = [
            (player.name, np.round(metric_extractor(player), 2))
            for player in session_of_rounds.players
        ]

        if print_metrics:
            print(f"\n\033[94mMetrics for parameter value {param_value}:\033[0m")
            for player_name, metric_value in sorted(all_metrics, key=lambda x: x[1]):
                print(f"{player_name}: {metric_value}")

        parameter_to_metric_data[param_value] = {f"all_{metric_name}": all_metrics}
        df["Happiness"] = 0
        df["Games played"] = 0

    print("\033[92mDONE\033[0m")

    # Create visualization if requested
    if show_plot:
        plot_parameter_sweep_results(
            parameter_to_metric_data=parameter_to_metric_data,
            parameter_name=parameter_name,
            metric_name=metric_name,
            plot_title=plot_title,
            xlabel=xlabel,
            ylabel=ylabel,
        )

    return parameter_to_metric_data, last_session


# %%
# %%
################################################################################
################################################################################
################################################################################
################################################################################
################################################################################
################################################################################
################################################################################
########                                                               #########
######## ######  #     # ######        ######  #     # ######  ####### #########
######## #     # #     # #     #       #     # ##    # #     # #       #########
######## ######  #     # #     #       ######  # #   # #     # ####### #########
######## #   ##  #     # #     #       #   ##  #  #  # #     #       # #########
######## #    ## ####### #     # ##### #    ## #   # # ######  ####### #########
########                                                               #########
################################################################################
################################################################################
################################################################################
################################################################################
################################################################################
################################################################################
################################################################################
# %%


def run_with_random_sample(
    df,
    amount_of_samples,
    amount_of_players,
    metric_name="happiness",
    metric_extractor=lambda player: player.happiness,
    objective_function=None,
    session_kwargs=None,
    plot_title=None,
    xlabel=None,
    ylabel=None,
    show_plot=True,
):
    """
    Generate random samples of players and analyze their metrics across different samples.

    Args:
        df: DataFrame with player data
        amount_of_samples: Number of random samples to generate
        amount_of_players: Number of players to include in each sample
        metric_name: Name of the metric being measured (default: "happiness")
        metric_extractor: Function to extract metric from a player object (default: lambda player: player.happiness)
        objective_function: Objective function to use (optional)
        session_kwargs: Dict of keyword arguments to pass to run_session_generation_with_seed_optimization
        plot_title: Title for the box plot (optional)
        xlabel: X-axis label (optional)
        ylabel: Y-axis label (optional, defaults to metric_name)
        show_plot: Whether to display the box plot (default: True)

    Returns:
        dict: Mapping from sample index to metric data
        list: List of all session_of_rounds objects
    """
    import matplotlib.pyplot as plt

    # Default session kwargs
    if session_kwargs is None:
        session_kwargs = {
            "amount_of_rounds": 4,
            "type_preferences": ["level", "level", "balanced", "balanced"],
            "gender_preferences": ["open", "mixed", "mixed", "open"],
            "level_gap_tol": 1,
            "num_iter": 100,
            "lambda_weight": 0.5,
            "weight_same_teammate": 5,
            "first_seed": 0,
            "last_seed": 9,
            "spectrum": True,
            "games_per_round_each_round": None,
            "rounds_reordering": [3, 4, 2, 1],
            "print_progress": False,
        }

    # Default objective function
    if objective_function is None:
        lambda_weight = session_kwargs.get("lambda_weight", 0.5)
        objective_function = lambda x: main.mean_min_max_happiness_objective(
            x, lambda_weight=lambda_weight
        )

    sample_to_metric_data = {}
    all_sessions = []

    for sample_idx in range(amount_of_samples):
        sample_number = sample_idx + 1
        print(
            "################################################################################"
        )
        print(
            "################################################################################"
        )
        print(
            f"########################### SAMPLE {sample_number}/{amount_of_samples} #############################"
        )

        # Generate random sample of players
        sampled_players = df.sample(n=amount_of_players, replace=False)
        sampled_df = sampled_players.copy()
        sampled_df["Happiness"] = 0
        sampled_df["Games played"] = 0

        print(f"Selected players: {', '.join(sampled_df.index.tolist())}")

        # Update session kwargs with objective function
        current_kwargs = session_kwargs.copy()
        current_kwargs["objective_function"] = objective_function

        # Run session generation
        session_of_rounds, chosen_seed = (
            main.run_session_generation_with_seed_optimization(
                sampled_df, **current_kwargs
            )
        )
        all_sessions.append(session_of_rounds)

        # Collect all players' metric values
        all_metrics = [
            (player.name, np.round(metric_extractor(player), 2))
            for player in session_of_rounds.players
        ]

        print(f"All players' {metric_name}:")
        for player_name, metric_value in sorted(all_metrics, key=lambda x: x[1]):
            print(f"{player_name}: {metric_value}")

        sample_to_metric_data[sample_number] = {f"all_{metric_name}": all_metrics}

    print("\033[92mDONE\033[0m")

    # Create visualization if requested
    if show_plot:
        # Prepare data for box plots
        metrics_by_sample = []
        for sample_number in range(1, amount_of_samples + 1):
            data = sample_to_metric_data[sample_number]
            metric_values = [value for name, value in data[f"all_{metric_name}"]]
            metrics_by_sample.append(metric_values)

        # Create box and whisker plot
        plt.figure(figsize=(14, 8))
        box_plot = plt.boxplot(
            metrics_by_sample,
            positions=range(amount_of_samples),
            widths=0.6,
            patch_artist=True,
            showmeans=True,
            meanprops=dict(marker="D", markerfacecolor="red", markersize=8),
        )

        # Color the boxes
        for patch in box_plot["boxes"]:
            patch.set_facecolor("lightblue")
            patch.set_alpha(0.7)

        # Set x-axis labels
        plt.xticks(
            range(amount_of_samples),
            [f"Sample {i+1}" for i in range(amount_of_samples)],
            rotation=45,
        )
        plt.xlabel(
            xlabel if xlabel else f"Random Samples ({amount_of_players} players each)",
            fontsize=12,
        )
        plt.ylabel(
            ylabel if ylabel else metric_name.replace("_", " ").title(), fontsize=12
        )
        plt.title(
            (
                plot_title
                if plot_title
                else f"Distribution of Player {metric_name.title()} Across Random Samples"
            ),
            fontsize=14,
            fontweight="bold",
        )
        plt.grid(True, alpha=0.3, axis="y")
        plt.tight_layout()
        _show_or_close_plot(plt)

    return sample_to_metric_data, all_sessions


# %%
