# main.py - thin compatibility bridge
# All logic lives in the dedicated sub-modules below.
# Existing code that does `import main` or `load_module('main', 'main.py')`
# keeps working without changes.

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
