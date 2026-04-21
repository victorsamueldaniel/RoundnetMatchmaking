# main.py - thin compatibility bridge
# All logic lives in the dedicated sub-modules below.
# Existing code that does `import main` or `load_module('main', 'main.py')`
# keeps working without changes.

import sys
import pandas as pd

from core.data_loader import main_df  # noqa: F401  (re-exported for UI)
from core.models import (  # noqa: F401
    Player,
    TeamOfTwo,
    GameOfFour,
    GamesRound,
    SessionOfRounds,
    mean_happiness_objective,
    std_happiness_objective,
    mean_std_happiness_objective,
    min_happiness_objective,
    mean_min_max_happiness_objective,
)
from core.charts import (  # noqa: F401
    plot_happiness_charts,
    plot_team_analysis,
    plot_spectrum_analysis,
    create_all_session_charts,
)
from core.algorithm import run_session_generation_with_seed_optimization  # noqa: F401
from core.algorithm import force_preferred_pairs_in_session  # noqa: F401

# Ensure legacy references to module name "main" remain importable. This is
# required for pickle compatibility with objects that encode class paths as
# main.SessionOfRounds.
sys.modules.setdefault("main", sys.modules[__name__])


def _build_df_minimal_example() -> pd.DataFrame:
    """Return a stable minimal DataFrame used by legacy tests.

    Prefer the first rows from loaded data when available; otherwise provide a
    synthetic fallback with enough players for session creation tests.
    """
    if isinstance(main_df, pd.DataFrame) and len(main_df) >= 12:
        return main_df.iloc[:12].copy()

    names = [
        "Alice",
        "Bob",
        "Charlie",
        "David",
        "Eve",
        "Frank",
        "Grace",
        "Hugo",
        "Iris",
        "Jack",
        "Kara",
        "Liam",
    ]
    levels = [2.0, 2.5, 3.0, 3.5, 2.2, 3.2, 2.8, 3.8, 1.9, 2.9, 3.1, 2.6]
    genders = [
        "Female",
        "Male",
        "Male",
        "Male",
        "Female",
        "Male",
        "Female",
        "Male",
        "Female",
        "Male",
        "Female",
        "Male",
    ]

    rows = []
    for name, level, gender in zip(names, levels, genders):
        rows.append(
            {
                "Name": name,
                "Surname": "Test",
                "Level": level,
                "Gender": gender,
                "Happiness": 0,
                "Games played": 0,
                "Noisy level": level,
                "Category": level,
                "Prey": 5,
                "Equilibrist": 5,
                "Challenger": 5,
                "Chill": 5,
                "Hunter": 5,
                "Classist": 5,
            }
        )

    df = pd.DataFrame(rows, index=names)
    df.index.name = "NameSurname"
    return df


# Compatibility fixture used by older script-style tests.
df_minimal_example = _build_df_minimal_example()


def plot_session_charts(session_of_rounds, *args, **kwargs):
    """Backward-compatible alias for legacy scripts/tests.

    Historically, callers used ``main.plot_session_charts(session_of_rounds)``.
    The maintained implementation lives in ``create_all_session_charts``.
    """
    return create_all_session_charts(session_of_rounds, *args, **kwargs)
