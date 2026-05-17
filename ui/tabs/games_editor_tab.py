"""Games Editor tab controller."""

import os

import tkinter as tk
from tkinter import messagebox

from ui.functions.tab_functions import games_editor_delta_to_bg

main_module = None

# Abbreviated spectrum names for player button middle lines.
_SPEC_ABBREV = {
    "Prey": "Prey",
    "Hunter": "Hntr",
    "Challenger": "Clgr",
    "Classist": "Clst",
    "Equilibrist": "Equl",
    "Chill": "Chll",
}

# Maps spec key → player attribute name (mirrors core.models._SPEC_KEY_TO_ATTR).
_SPEC_KEY_TO_ATTR = {
    "Prey": "prey",
    "Equilibrist": "equilibrist",
    "Challenger": "challenger",
    "Chill": "chill",
    "Hunter": "hunter",
    "Classist": "classist",
}


class GamesEditorTabMixin:
    def _ensure_games_editor_button_config(self):
        """Ensure token-based text/style maps exist for button presentation."""
        middle_text_map = getattr(self, "_games_editor_middle_text_map", None)
        if not isinstance(middle_text_map, dict):
            middle_text_map = {}
        middle_text_map.setdefault("default", "")
        middle_text_map.setdefault("over_benched_not_playing", "SAD!")
        self._games_editor_middle_text_map = middle_text_map

        style_map = getattr(self, "_games_editor_button_style_map", None)
        if not isinstance(style_map, dict):
            style_map = {}
        style_map.setdefault(
            "default",
            {
                "bg": self.colors["bg_light"],
                "fg": self.colors["text_dark"],
            },
        )
        style_map.setdefault(
            "over_benched_not_playing",
            {
                "bg": "#000000",
                "fg": "#FFFFFF",
            },
        )
        self._games_editor_button_style_map = style_map

    def _resolve_middle_text(self, middle_token="default", middle_override=None):
        """Return middle-line text from token map, with optional direct override."""
        if middle_override is not None:
            return middle_override
        self._ensure_games_editor_button_config()
        return self._games_editor_middle_text_map.get(
            middle_token,
            self._games_editor_middle_text_map.get("default", ""),
        )

    def _format_player_button_text(
        self,
        player,
        middle_token="default",
        middle_override=None,
    ):
        """Build the player button label with a tokenized, configurable middle line."""
        middle_text = self._resolve_middle_text(
            middle_token=middle_token,
            middle_override=middle_override,
        )
        if middle_text:
            return f"{player.name}\n{middle_text}\nLvl {player.level}"
        return f"{player.name}\n\nLvl {player.level}"

    def _resolve_button_colors(
        self,
        style_token="default",
        bg_override=None,
        fg_override=None,
    ):
        """Resolve button colours from style token map and optional overrides."""
        self._ensure_games_editor_button_config()
        token_style = self._games_editor_button_style_map.get(
            style_token,
            self._games_editor_button_style_map["default"],
        )
        bg = bg_override if bg_override is not None else token_style.get("bg")
        fg = fg_override if fg_override is not None else token_style.get("fg")
        return bg, fg

    def _compute_games_played_counts_from_editor_session(self):
        """Compute games-played counts from the current editable in-memory session."""
        if not hasattr(self, "session_of_rounds") or self.session_of_rounds is None:
            return {}

        counts = {p.name: 0 for p in self.session_of_rounds.players}
        for round_obj in self.session_of_rounds.rounds:
            for game in round_obj.games:
                # Use live team slots instead of cached game.participants so
                # pending swaps in the editor are reflected immediately.
                for participant in game.team_A.players + game.team_B.players:
                    counts[participant.name] = counts.get(participant.name, 0) + 1
        return counts

    def _over_benched_not_playing_names(self):
        """Return player names whose games-played count is 2+ below current max."""
        counts = self._compute_games_played_counts_from_editor_session()
        if not counts:
            return set()

        max_played = max(counts.values())
        return {name for name, played in counts.items() if (max_played - played) >= 2}

    def _middle_style_token_for_player(
        self,
        player,
        team_id,
        over_benched_names=None,
    ):
        """Return presentation token for this player button context."""
        if team_id == "not_playing":
            if over_benched_names is None:
                over_benched_names = self._over_benched_not_playing_names()
            if player.name in over_benched_names:
                return "over_benched_not_playing"
        return "default"

    # ------------------------------------------------------------------
    # Spectrum helpers
    # ------------------------------------------------------------------

    def _abbrev_spec(self, spec_name):
        """Return the abbreviated spectrum name, or empty string if None."""
        if not spec_name:
            return ""
        return _SPEC_ABBREV.get(spec_name, spec_name)

    def _round_uses_spectrum(self, round_idx):
        """Return True if the given round was run with spectrum=True."""
        try:
            return getattr(self.session_of_rounds.rounds[round_idx], "spectrum", False)
        except Exception:
            return False

    def _baseline_spec_middle(self, player, round_idx, team_id):
        """Return the committed spec abbreviation to use as the button middle line.

        Returns None when spectrum is off for that round, or when the index is
        missing (e.g. not_playing slot).
        """
        if team_id == "not_playing":
            return None
        if not self._round_uses_spectrum(round_idx):
            return None
        try:
            spec = player.spec_chosen_history[round_idx]
        except (IndexError, AttributeError):
            return None
        return self._abbrev_spec(spec) or None

    def _player_from_button_key(self, key):
        """Resolve current player object backing a stored games-editor button key."""
        round_idx, game_idx, team_id, row, col = key
        game_round = self.session_of_rounds.rounds[round_idx]

        if team_id == "not_playing":
            return game_round.not_playing[row * 4 + col]

        game = game_round.games[game_idx]
        if team_id == "A":
            return game.team_A.players[col]
        if team_id == "B":
            return game.team_B.players[col]
        return None

    def _apply_player_button_presentation(
        self,
        btn,
        player,
        team_id,
        *,
        middle_token="default",
        middle_override=None,
        bg_override=None,
        fg_override=None,
        relief=tk.RAISED,
    ):
        """Apply centralized text + style presentation to a games editor button."""
        text = self._format_player_button_text(
            player,
            middle_token=middle_token,
            middle_override=middle_override,
        )
        bg, fg = self._resolve_button_colors(
            style_token=middle_token,
            bg_override=bg_override,
            fg_override=fg_override,
        )
        btn.config(text=text, bg=bg, fg=fg, relief=relief)

    def _refresh_not_playing_button_styles(self):
        """Apply tokenized not-playing styles globally across all rounds."""
        if not hasattr(self, "game_player_buttons"):
            return

        over_benched_names = self._over_benched_not_playing_names()
        for key, btn in list(self.game_player_buttons.items()):
            _, _, team_id, _, _ = key
            if team_id != "not_playing":
                continue

            try:
                player = self._player_from_button_key(key)
            except Exception:
                continue

            if player is None:
                continue

            token = self._middle_style_token_for_player(
                player,
                team_id,
                over_benched_names=over_benched_names,
            )
            try:
                self._apply_player_button_presentation(
                    btn,
                    player,
                    team_id,
                    middle_token=token,
                )
            except Exception:
                pass

    def show_games_editor(self):
        """Create interactive games editor tab where users can swap players"""
        if not hasattr(self, "session_of_rounds") or self.session_of_rounds is None:
            print("No session available to edit.")
            return

        self._ensure_games_editor_button_config()

        # Compact sizing for this tab so 4 rounds can fit horizontally.
        self.games_editor_button_font = self._scaled_font_tuple(
            self.fonts["small"], 0.85
        )
        self.games_editor_player_button_font = self._scaled_font_tuple(
            self.fonts["small"], 0.8
        )
        self.games_editor_vs_font = self._scaled_font_tuple(
            self.fonts["small_bold"], 0.78
        )

        # Check if Games Editor tab already exists
        for tab_id in self.main_notebook.tabs():
            if self.main_notebook.tab(tab_id, "text") == "Games Editor":
                # Tab exists, remove it first so we can recreate it with fresh data
                self.main_notebook.forget(tab_id)
                break

        # Create "Games Editor" tab
        editor_tab = tk.Frame(self.main_notebook, bg=self.colors["bg_dark"])

        # Add the tab (it will be added after existing tabs)
        # Then we can select it to make it visible
        self.main_notebook.add(editor_tab, text="Games Editor")

        # Move it to position 1 (right after Session Generation at position 0)
        num_tabs = len(self.main_notebook.tabs())
        if num_tabs > 1:
            # Move the last tab (just added) to position 1
            last_tab_index = num_tabs - 1
            if last_tab_index > 1:
                # There are other tabs, need to reorder
                tab_id = self.main_notebook.tabs()[last_tab_index]
                # Remove and reinsert at position 1
                self.main_notebook.forget(last_tab_index)
                self.main_notebook.insert(1, editor_tab, text="Games Editor")

        # Header frame for title (centered, matching Session Generation tab)
        header_frame = tk.Frame(editor_tab, bg=self.colors["bg_dark"])
        header_frame.pack(side=tk.TOP, pady=(10, 10))

        # Title container to center the title
        title_container = tk.Frame(header_frame, bg=self.colors["bg_dark"])
        title_container.pack()

        # Add title
        title_label = tk.Label(
            title_container,
            text="INTERACTIVE GAMES EDITOR",
            font=self.fonts["huge"],
            fg=self.colors["accent_yellow"],
            bg=self.colors["bg_dark"],
        )
        title_label.pack()

        # Instructions and status in a separate frame
        info_frame = tk.Frame(editor_tab, bg=self.colors["bg_dark"])
        info_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 10), padx=20)

        # Instructions
        instructions = tk.Label(
            info_frame,
            text="Click on two players to swap their positions. Selected players are highlighted in yellow.",
            font=self.fonts["normal"],
            fg=self.colors["text_light"],
            bg=self.colors["bg_dark"],
        )
        instructions.pack(side=tk.TOP, pady=(0, 5))

        # Changes display frame (scrollable list of swaps)
        changes_container = tk.Frame(info_frame, bg=self.colors["bg_dark"])
        changes_container.pack(side=tk.TOP, fill=tk.X, pady=(10, 5))

        changes_label = tk.Label(
            changes_container,
            text="Pending Changes:",
            font=self.fonts["small_bold"],
            fg=self.colors["text_light"],
            bg=self.colors["bg_dark"],
        )
        changes_label.pack(side=tk.TOP, anchor=tk.W)

        # Frame to hold the list of changes
        self.changes_list_frame = tk.Frame(
            changes_container, bg=self.colors["bg_light"], relief=tk.RIDGE, bd=1
        )
        self.changes_list_frame.pack(side=tk.TOP, fill=tk.X, pady=(5, 0))

        # Initially show "No changes" message
        self.no_changes_label = tk.Label(
            self.changes_list_frame,
            text="No changes yet",
            font=self.fonts["small"],
            fg="#888888",
            bg=self.colors["bg_light"],
        )
        self.no_changes_label.pack(pady=5)

        # Status label
        self.status_label = tk.Label(
            info_frame,
            text="No changes pending",
            font=self.fonts["normal"],
            fg=self.colors["text_light"],
            bg=self.colors["bg_dark"],
        )
        self.status_label.pack(side=tk.TOP, pady=(5, 0))

        # Track pending changes
        self.pending_changes = []
        self.swap_history = []  # Track swaps for undo functionality

        # Baseline happiness gains per round per player — used by preview coloring.
        # Keyed as {round_idx: {player_name: gain_value_or_None}}
        self._editor_baseline_gains = {}
        for _r_idx, _game_round in enumerate(self.session_of_rounds.rounds):
            _round_baseline = {}
            for _p in self.session_of_rounds.players:
                if _r_idx < len(_p.happiness_gained_history):
                    _round_baseline[_p.name] = _p.happiness_gained_history[_r_idx]
                else:
                    _round_baseline[_p.name] = None
            self._editor_baseline_gains[_r_idx] = _round_baseline

        # --- Score history (initial + after each Apply) ---
        # Read objective metadata stored on the session to keep score semantics
        # in sync with what the optimizer actually used.
        from core.models import (
            compute_session_score as _compute_session_score,
        )  # noqa: PLC0415

        _sess_obj_name = getattr(
            self.session_of_rounds, "_objective_function_name", None
        )
        _sess_lw_raw = getattr(self.session_of_rounds, "_objective_lambda_weight", None)
        _sess_lw = _sess_lw_raw if _sess_lw_raw is not None else 2.4
        _sess_pct = getattr(self.session_of_rounds, "_objective_percentile", None) or 10
        _initial_score = _compute_session_score(
            self.session_of_rounds.players, _sess_obj_name, _sess_lw, _sess_pct
        )
        # Find the baseline pkl path so score chips can link back to the saved file
        _initial_pkl = getattr(self, "_loaded_pkl_path", None)
        if hasattr(self, "_loaded_pkl_path"):
            del self._loaded_pkl_path
        if _initial_pkl is None:
            _sf_init = getattr(self, "_active_session_folder", None)
            if _sf_init and os.path.exists(_sf_init):
                import re as _re_init  # noqa: PLC0415

                _base_pkls = sorted(
                    f
                    for f in os.listdir(_sf_init)
                    if f.endswith(".pkl")
                    and not _re_init.search(r"_v\d+\.pkl$", f)
                    and "_modified" not in f
                )
                if _base_pkls:
                    _initial_pkl = os.path.join(_sf_init, _base_pkls[0])
        self.score_history = [(_initial_score, _initial_pkl)]
        # Restore previous history if a version-restore operation is in progress
        if hasattr(self, "_pending_restore_history"):
            self.score_history = self._pending_restore_history
            del self._pending_restore_history
        # Store objective metadata for post-apply reuse; do NOT use live slider values
        # so the score stays tied to the generated session regardless of UI changes.
        self._score_obj_name = _sess_obj_name
        self._score_lw = _sess_lw
        self._score_pct = _sess_pct

        # Buttons frame (part of editor tab) - matching Session Generation layout
        # Pack this BEFORE canvas so it stays at the bottom
        button_frame = tk.Frame(editor_tab, bg=self.colors["bg_dark"])
        button_frame.pack(side=tk.BOTTOM, pady=15, padx=20)

        # Build a human-readable label for the active objective formula
        _obj_label_name = _sess_obj_name or "mean_min_max_happiness_objective"
        if _obj_label_name == "mean_min_max_happiness_objective":
            _score_label_text = (
                f"Score history  (mean + {_sess_lw:.1f}·bottom{int(_sess_pct)}%):"
            )
        elif _obj_label_name == "mean_std_happiness_objective":
            _score_label_text = f"Score history  (mean − {_sess_lw:.1f}·std):"
        elif _obj_label_name == "mean_happiness_objective":
            _score_label_text = "Score history  (mean happiness):"
        else:
            _score_label_text = "Score history:"

        # Score history strip — just above buttons
        score_history_outer = tk.Frame(editor_tab, bg=self.colors["bg_dark"])
        score_history_outer.pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=(0, 4))
        tk.Label(
            score_history_outer,
            text=_score_label_text,
            font=self.fonts["small_bold"],
            fg=self.colors["text_light"],
            bg=self.colors["bg_dark"],
        ).pack(side=tk.LEFT, padx=(0, 8))
        self.score_history_container = tk.Frame(
            score_history_outer, bg=self.colors["bg_dark"]
        )
        self.score_history_container.pack(side=tk.LEFT, fill=tk.X)
        self._render_score_history()

        # Custom button style
        btn_config = {
            "font": self.games_editor_button_font,
            "relief": tk.FLAT,
            "cursor": "hand2",
            "padx": 12,
            "pady": 6,
        }

        # Undo button
        self.undo_button = tk.Button(
            button_frame,
            text="Undo Last Swap",
            command=self.undo_last_swap,
            bg=self.colors["bg_light"],
            fg=self.colors["text_dark"],
            state=tk.DISABLED,
            **btn_config,
        )
        self.undo_button.grid(row=0, column=0, padx=5)

        # Apply button - highlighted with yellow (matching Run Session button)
        self.apply_button = tk.Button(
            button_frame,
            text="⚡ APPLY CHANGES & RECALCULATE ⚡",
            command=self.apply_changes,
            bg=self.colors["accent_yellow"],
            fg=self.colors["text_dark"],
            font=self.games_editor_button_font,
            relief=tk.FLAT,
            cursor="hand2",
            padx=14,
            pady=6,
        )
        self.apply_button.grid(row=0, column=1, padx=10)

        # Create scrollable area (pack AFTER button_frame so it fills remaining space)
        canvas = tk.Canvas(editor_tab, bg=self.colors["bg_dark"])
        v_scrollbar = tk.Scrollbar(editor_tab, orient=tk.VERTICAL, command=canvas.yview)
        h_scrollbar = tk.Scrollbar(
            editor_tab, orient=tk.HORIZONTAL, command=canvas.xview
        )
        scrollable_frame = tk.Frame(canvas, bg=self.colors["bg_dark"])

        scrollable_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Track selected players for swapping
        self.selected_for_swap = []

        # Mapping for player buttons in the games editor UI
        # Keyed by (round_idx, game_idx, team_id, row, col) -> button
        self.game_player_buttons = {}

        # Mapping for level-diff labels above VS: (round_idx, game_idx) -> Label
        self.game_level_diff_labels = {}

        # Mapping for team frames: (round_idx, game_idx, team_id) -> (outer_frame, inner_frame)
        self.game_team_frames = {}

        # Create rounds container with columns
        num_rounds = len(self.session_of_rounds.rounds)
        rounds_container = tk.Frame(scrollable_frame, bg=self.colors["bg_dark"])
        rounds_container.pack(expand=True, fill=tk.BOTH, padx=4, pady=6)

        # Configure columns to have equal weight
        for col_idx in range(num_rounds):
            rounds_container.columnconfigure(col_idx, weight=1, uniform="round")

        # Display each round in a column
        for round_idx, game_round in enumerate(self.session_of_rounds.rounds):
            # Round column
            round_column = tk.Frame(
                rounds_container, bg=self.colors["bg_light"], relief=tk.RIDGE, bd=2
            )
            round_column.grid(
                row=0, column=round_idx, sticky=(tk.N, tk.S, tk.E, tk.W), padx=2
            )

            # Round header
            round_header = tk.Frame(round_column, bg=self.colors["accent_red"], pady=6)
            round_header.pack(fill=tk.X, pady=(0, 10))

            round_label = tk.Label(
                round_header,
                text=f"ROUND {round_idx + 1}",
                font=self.fonts["big"],
                fg=self.colors["text_light"],
                bg=self.colors["accent_red"],
            )
            round_label.pack()

            # Games section
            games_frame = tk.Frame(round_column, bg=self.colors["bg_light"])
            games_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

            for game_idx, game in enumerate(game_round.games):
                # Game frame
                game_frame = tk.Frame(games_frame, bg="#F0F0F0", relief=tk.RAISED, bd=2)
                game_frame.pack(fill=tk.X, pady=3, padx=3)

                # Game type subtitle (type_preference + gender_preference)
                type_str = (game.type_preference or "open").capitalize()
                gender_str = (game.gender_preference or "open").capitalize()
                game_type_label = tk.Label(
                    game_frame,
                    text=f"{type_str}  |  {gender_str}",
                    font=(
                        self.games_editor_button_font[0],
                        max(7, self.games_editor_button_font[1] - 1),
                        "italic",
                    ),
                    fg="#555555",
                    bg="#F0F0F0",
                    anchor="center",
                    justify="center",
                )
                game_type_label.pack(pady=(0, 4), fill=tk.X)

                # Teams container
                teams_container = tk.Frame(game_frame, bg="#F0F0F0")
                teams_container.pack(pady=(0, 6))

                # Team A
                team_a_bg = self._team_pair_bg(round_idx, game_idx, "A")
                team_a_frame = tk.Frame(
                    teams_container, bg=team_a_bg, relief=tk.GROOVE, bd=2
                )
                team_a_frame.grid(row=0, column=0, padx=4, pady=3, sticky=tk.NSEW)

                # Create horizontal layout for Team A players
                team_a_players_frame = tk.Frame(team_a_frame, bg=team_a_bg)
                team_a_players_frame.pack(padx=3, pady=3)
                self.game_team_frames[(round_idx, game_idx, "A")] = (
                    team_a_frame,
                    team_a_players_frame,
                )

                for col_idx, player in enumerate(game.team_A.players):
                    self.create_player_button_grid(
                        team_a_players_frame,
                        player,
                        round_idx,
                        game_idx,
                        "A",
                        0,
                        col_idx,
                    )

                # VS label with level diff above it
                vs_container = tk.Frame(teams_container, bg="#F0F0F0")
                vs_container.grid(row=0, column=1, padx=2)

                level_diff = game.team_A.mean_level - game.team_B.mean_level
                diff_text = (
                    f"+{level_diff:.1f}" if level_diff > 0 else f"{level_diff:.1f}"
                )
                diff_color = "#2255AA" if level_diff >= 0 else "#AA2222"
                diff_label = tk.Label(
                    vs_container,
                    text=diff_text,
                    font=(
                        self.games_editor_vs_font[0],
                        max(7, self.games_editor_vs_font[1] - 4),
                    ),
                    fg=diff_color,
                    bg="#F0F0F0",
                )
                diff_label.pack()
                self.game_level_diff_labels[(round_idx, game_idx)] = diff_label
                vs_label = tk.Label(
                    vs_container,
                    text="VS",
                    font=self.games_editor_vs_font,
                    fg=self.colors["accent_red"],
                    bg="#F0F0F0",
                )
                vs_label.pack()

                # Team B
                team_b_bg = self._team_pair_bg(round_idx, game_idx, "B")
                team_b_frame = tk.Frame(
                    teams_container, bg=team_b_bg, relief=tk.GROOVE, bd=2
                )
                team_b_frame.grid(row=0, column=2, padx=4, pady=3, sticky=tk.NSEW)

                # Create horizontal layout for Team B players
                team_b_players_frame = tk.Frame(team_b_frame, bg=team_b_bg)
                team_b_players_frame.pack(padx=3, pady=3)
                self.game_team_frames[(round_idx, game_idx, "B")] = (
                    team_b_frame,
                    team_b_players_frame,
                )

                for col_idx, player in enumerate(game.team_B.players):
                    self.create_player_button_grid(
                        team_b_players_frame,
                        player,
                        round_idx,
                        game_idx,
                        "B",
                        0,
                        col_idx,
                    )

            # Not playing section
            if game_round.not_playing:
                not_playing_frame = tk.Frame(
                    round_column, bg="#FFF8DC", relief=tk.RIDGE, bd=2
                )
                not_playing_frame.pack(fill=tk.X, pady=(0, 6))

                not_playing_label = tk.Label(
                    not_playing_frame,
                    text="Not Playing:",
                    font=self.games_editor_button_font,
                    fg=self.colors["text_dark"],
                    bg="#FFF8DC",
                )
                not_playing_label.pack(pady=(3, 0))

                # Create a grid container for 2 columns
                not_playing_grid = tk.Frame(not_playing_frame, bg="#FFF8DC")
                not_playing_grid.pack(pady=(0, 3))

                # Place players in 4 columns
                for idx, player in enumerate(game_round.not_playing):
                    row = idx // 4
                    col = idx % 4
                    player_btn = self.create_player_button_grid(
                        not_playing_grid,
                        player,
                        round_idx,
                        None,
                        "not_playing",
                        row,
                        col,
                    )

        # Bind mouse wheel for scrolling
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def on_shift_mousewheel(event):
            canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")

        # Use enter/leave on the scrollable frame to set the mousewheel target for the games editor
        def _on_editor_enter(event):
            self._mousewheel_target_canvas = canvas

        def _on_editor_leave(event):
            if getattr(self, "_mousewheel_target_canvas", None) == canvas:
                self._mousewheel_target_canvas = None

        scrollable_frame.bind("<Enter>", _on_editor_enter)
        scrollable_frame.bind("<Leave>", _on_editor_leave)

        # Switch to the Games Editor tab
        self.main_notebook.select(editor_tab)

    def create_player_button(self, parent, player, round_idx, game_idx, team_id):
        """Create a clickable player button for swapping"""
        player_info = {
            "player": player,
            "round_idx": round_idx,
            "game_idx": game_idx,
            "team_id": team_id,
        }

        btn = tk.Button(
            parent,
            text=self._format_player_button_text(player),
            font=getattr(self, "games_editor_player_button_font", self.fonts["small"]),
            bg=self._resolve_button_colors(style_token="default")[0],
            fg=self._resolve_button_colors(style_token="default")[1],
            relief=tk.RAISED,
            padx=6,
            pady=3,
            cursor="hand2",
            command=lambda: self.toggle_player_selection(btn, player_info),
        )
        btn.pack(padx=3, pady=2)
        # Attach the mutable player_info dict to the button so it can be
        # updated when swaps/undo happen and refresh routines can keep
        # closures in sync with the underlying data model.
        try:
            btn._player_info = player_info
        except Exception:
            pass

    def create_player_button_grid(
        self, parent, player, round_idx, game_idx, team_id, row, col
    ):
        """Create a clickable player button for swapping in a grid layout"""
        player_info = {
            "player": player,
            "round_idx": round_idx,
            "game_idx": game_idx,
            "team_id": team_id,
        }

        over_benched_names = self._over_benched_not_playing_names()
        token = self._middle_style_token_for_player(
            player,
            team_id,
            over_benched_names=over_benched_names,
        )
        spec_middle = self._baseline_spec_middle(player, round_idx, team_id)
        bg, fg = self._resolve_button_colors(style_token=token)
        btn = tk.Button(
            parent,
            text=self._format_player_button_text(
                player,
                middle_token=token,
                middle_override=spec_middle,
            ),
            font=getattr(self, "games_editor_player_button_font", self.fonts["small"]),
            bg=bg,
            fg=fg,
            relief=tk.RAISED,
            padx=6,
            pady=3,
            cursor="hand2",
            command=lambda: self.toggle_player_selection(btn, player_info),
        )
        btn.grid(row=row, column=col, padx=2, pady=2, sticky=tk.EW)

        # Store button reference so we can refresh labels when swaps/undo happen
        try:
            key = (round_idx, game_idx, team_id, row, col)
            self.game_player_buttons[key] = btn
        except Exception:
            # If mapping isn't available (called outside games editor), ignore
            pass
        # Also attach the player_info to the button for later refresh
        try:
            btn._player_info = player_info
        except Exception:
            pass
        # Bind 1-second hover tooltip
        try:
            self._bind_player_hover_tooltip(btn, round_idx, game_idx, team_id)
        except Exception:
            pass
        return btn

    def refresh_round_ui(self, round_idx):
        """Refresh the visible buttons for a specific round based on data model."""
        if not hasattr(self, "session_of_rounds") or self.session_of_rounds is None:
            return

        try:
            game_round = self.session_of_rounds.rounds[round_idx]
        except Exception:
            return

        over_benched_names = self._over_benched_not_playing_names()

        # Update games
        for game_idx, game in enumerate(game_round.games):
            # Team A
            for col_idx, player in enumerate(game.team_A.players):
                key = (round_idx, game_idx, "A", 0, col_idx)
                btn = self.game_player_buttons.get(key)
                if btn:
                    self._apply_player_button_presentation(
                        btn,
                        player,
                        "A",
                    )

            # Team B
            for col_idx, player in enumerate(game.team_B.players):
                key = (round_idx, game_idx, "B", 0, col_idx)
                btn = self.game_player_buttons.get(key)
                if btn:
                    self._apply_player_button_presentation(
                        btn,
                        player,
                        "B",
                    )

            # Refresh team frame colours
            self._refresh_team_frame_colors(round_idx, game_idx)

        # Update not playing
        if game_round.not_playing:
            for idx, player in enumerate(game_round.not_playing):
                row = idx // 4
                col = idx % 4
                key = (round_idx, None, "not_playing", row, col)
                btn = self.game_player_buttons.get(key)
                if btn:
                    token = self._middle_style_token_for_player(
                        player,
                        "not_playing",
                        over_benched_names=over_benched_names,
                    )
                    self._apply_player_button_presentation(
                        btn,
                        player,
                        "not_playing",
                        middle_token=token,
                    )

    def refresh_all_rounds(self):
        """Refresh all stored game buttons from the session data.

        This is more robust than refreshing a single round because keys may
        not map perfectly in some edge cases; iterating stored buttons ensures
        visible labels match the underlying data model.
        """
        if not hasattr(self, "session_of_rounds") or self.session_of_rounds is None:
            return

        over_benched_names = self._over_benched_not_playing_names()

        for key, btn in list(self.game_player_buttons.items()):
            try:
                round_idx, game_idx, team_id, row, col = key
                player = self._player_from_button_key(key)
                if player is None:
                    continue

                token = self._middle_style_token_for_player(
                    player,
                    team_id,
                    over_benched_names=over_benched_names,
                )
                spec_middle = self._baseline_spec_middle(player, round_idx, team_id)
                self._apply_player_button_presentation(
                    btn,
                    player,
                    team_id,
                    middle_token=token,
                    middle_override=spec_middle,
                )
                # use the correct player object
                try:
                    if hasattr(btn, "_player_info") and isinstance(
                        btn._player_info, dict
                    ):
                        btn._player_info["player"] = player
                except Exception:
                    pass
            except Exception:
                # If any mapping/indexing fails, skip updating that button
                continue

        # Refresh all team frame colours
        seen_games = set()
        for round_idx, game_idx, team_id, _row, _col in list(
            self.game_player_buttons.keys()
        ):
            if team_id != "not_playing" and game_idx is not None:
                key = (round_idx, game_idx)
                if key not in seen_games:
                    seen_games.add(key)
                    self._refresh_team_frame_colors(round_idx, game_idx)

    def _team_pair_bg(self, round_idx, game_idx, team_id):
        """Return gold if this team contains a preferred pair, else the normal team color."""
        GOLD = "#FFD700"
        normal = "#D0E8FF" if team_id == "A" else "#FFE0E0"
        if (
            not self.preferred_pairs
            or game_idx is None
            or not hasattr(self, "session_of_rounds")
            or self.session_of_rounds is None
        ):
            return normal
        try:
            game = self.session_of_rounds.rounds[round_idx].games[game_idx]
            team_names = (
                {p.name for p in game.team_A.players}
                if team_id == "A"
                else {p.name for p in game.team_B.players}
            )
            for pair_fs, _ in self.preferred_pairs:
                if pair_fs.issubset(team_names):
                    return GOLD
        except Exception:
            pass
        return normal

    def _refresh_team_frame_colors(self, round_idx, game_idx):
        """Update the background colour of both team frames for a given game."""
        for team_id in ("A", "B"):
            frames = self.game_team_frames.get((round_idx, game_idx, team_id))
            if frames is None:
                continue
            outer, inner = frames
            bg = self._team_pair_bg(round_idx, game_idx, team_id)
            try:
                outer.config(bg=bg)
                inner.config(bg=bg)
            except Exception:
                pass

    def _delta_to_bg(self, delta):
        """Return (bg_hex, text_suffix) for a happiness delta.

        White if unchanged, green tint if happier, red tint if less happy.
        Saturation is interpolated linearly up to ±5 units, then capped.
        Negative deltas also return a text suffix like '[−2.0]'.
        """
        return games_editor_delta_to_bg(delta)

    def _preview_happiness_delta(self, round_idx):
        """Simulate recalculate_happiness for round_idx without permanently changing state.

        Returns a dict {player_name: delta} where delta is the change in
        happiness_gained for that round compared to the stored baseline.
        """
        if not hasattr(self, "session_of_rounds") or self.session_of_rounds is None:
            return {}
        if not hasattr(self, "_editor_baseline_gains"):
            return {}

        game_round = self.session_of_rounds.rounds[round_idx]
        all_players = self.session_of_rounds.players

        # ---- 1. Snapshot player state ----
        player_snapshots = {}
        for p in all_players:
            player_snapshots[p.name] = {
                "happiness": p.happiness,
                "happiness_gained_history": list(p.happiness_gained_history),
                "last_happiness_gained": getattr(p, "last_happiness_gained", 0),
                "teammate_history": [frozenset(fs) for fs in p.teammate_history],
                "other_players_in_same_game_history": [
                    frozenset(fs) for fs in p.other_players_in_same_game_history
                ],
                "spec_chosen_history": list(
                    p.spec_chosen_history if hasattr(p, "spec_chosen_history") else []
                ),
                "last_spec_chosen": getattr(p, "last_spec_chosen", None),
            }

        # ---- 2. Snapshot game/round state ----
        game_snapshots = []
        for game in game_round.games:
            game_snapshots.append(
                {
                    "team_A": game.team_A,
                    "team_B": game.team_B,
                    "teams": set(game.teams),
                    "participants": frozenset(game.participants),
                    "team_A_mean_level": game.team_A_mean_level,
                    "team_B_mean_level": game.team_B_mean_level,
                    "overall_mean_level": game.overall_mean_level,
                    "level_difference": game.level_difference,
                    "is_gender_preference_satisfied": game.is_gender_preference_satisfied,
                }
            )
        round_teams_snapshot = set(game_round.teams)

        # ---- 3. Run simulation ----
        try:
            game_round.recalculate_happiness(round_idx=round_idx)
        except Exception:
            pass

        # ---- 4. Read new gains ----
        new_gains = {}
        for p in all_players:
            if round_idx < len(p.happiness_gained_history):
                new_gains[p.name] = p.happiness_gained_history[round_idx]
            else:
                new_gains[p.name] = None

        # ---- 4b. Capture simulated spec chosen per player ----
        preview_specs = {
            p.name: getattr(p, "last_spec_chosen", None) for p in all_players
        }

        # ---- 4.5. Compute pair bonus deltas for this round ----
        # happiness_gained_history only tracks game-mechanics gains; the pair bonus
        # lives separately in player.happiness.  We compute its expected change here
        # so the preview colour correctly reflects pair-related happiness shifts.
        pair_bonus_deltas = {}
        if getattr(self, "preferred_pairs", None) and hasattr(
            self.session_of_rounds, "_pair_happiness_per_round"
        ):
            per_round = self.session_of_rounds._pair_happiness_per_round
            never_met_per_player = 2
            if self.session_of_rounds.rounds:
                never_met_per_player = getattr(
                    self.session_of_rounds.rounds[0], "never_met_bonus_per_player", 2
                )
            player_by_name = {p.name: p for p in all_players}
            for pair_entry in self.preferred_pairs:
                if (
                    isinstance(pair_entry, (tuple, list))
                    and len(pair_entry) == 2
                    and isinstance(pair_entry[1], (int, float))
                ):
                    _pair_fs = frozenset(pair_entry[0])
                    _n = max(1, int(pair_entry[1]))
                else:
                    _pair_fs = frozenset(pair_entry)
                    _n = 1
                if len(_pair_fs) != 2:
                    continue
                _names = sorted(_pair_fs)
                _pp1 = player_by_name.get(_names[0])
                _pp2 = player_by_name.get(_names[1])
                if _pp1 is None or _pp2 is None:
                    continue
                _bonus_list = [max(8, 2 * (_n - k + 2)) for k in range(_n)]
                _pair_pfs = frozenset({_pp1, _pp2})

                # Old bonus this pair received for this specific round
                _p1_awards = per_round.get(_pp1.name, [])
                _old_bonus = _p1_awards[round_idx] if round_idx < len(_p1_awards) else 0

                # How many rounds before round_idx were they teammates (current session state)?
                _rounds_before = sum(
                    1
                    for _ri in range(round_idx)
                    for _g in self.session_of_rounds.rounds[_ri].games
                    for _t in _g.teams
                    if _pair_pfs == _t.players_frozenset
                )

                # Are they teammates in the simulated (swapped) state for this round?
                _teammates_now = any(
                    _pair_pfs == _t.players_frozenset
                    for _g in game_round.games
                    for _t in _g.teams
                )

                if _teammates_now:
                    _k = min(_rounds_before, len(_bonus_list) - 1)
                    _new_bonus = _bonus_list[_k]
                    if _rounds_before == 0:
                        _new_bonus -= never_met_per_player
                else:
                    _new_bonus = 0

                _delta = _new_bonus - _old_bonus
                if _delta != 0:
                    pair_bonus_deltas[_pp1.name] = (
                        pair_bonus_deltas.get(_pp1.name, 0) + _delta
                    )
                    pair_bonus_deltas[_pp2.name] = (
                        pair_bonus_deltas.get(_pp2.name, 0) + _delta
                    )

        # ---- 5. Restore player state ----
        for p in all_players:
            snap = player_snapshots.get(p.name)
            if snap is None:
                continue
            p.happiness = snap["happiness"]
            p.happiness_gained_history = snap["happiness_gained_history"]
            p.last_happiness_gained = snap["last_happiness_gained"]
            p.teammate_history = snap["teammate_history"]
            p.other_players_in_same_game_history = snap[
                "other_players_in_same_game_history"
            ]
            if hasattr(p, "spec_chosen_history"):
                p.spec_chosen_history = snap["spec_chosen_history"]
            p.last_spec_chosen = snap["last_spec_chosen"]

        # ---- 6. Restore game/round state ----
        for game, snap in zip(game_round.games, game_snapshots):
            game.team_A = snap["team_A"]
            game.team_B = snap["team_B"]
            game.teams = snap["teams"]
            game.participants = snap["participants"]
            game.team_A_mean_level = snap["team_A_mean_level"]
            game.team_B_mean_level = snap["team_B_mean_level"]
            game.overall_mean_level = snap["overall_mean_level"]
            game.level_difference = snap["level_difference"]
            game.is_gender_preference_satisfied = snap["is_gender_preference_satisfied"]
        game_round.teams = round_teams_snapshot

        # ---- 7. Compute deltas vs baseline ----
        baseline = self._editor_baseline_gains.get(round_idx, {})
        deltas = {}
        for name, new_gain in new_gains.items():
            base_gain = baseline.get(name)
            new_val = new_gain if new_gain is not None else 0.0
            base_val = base_gain if base_gain is not None else 0.0
            deltas[name] = (new_val - base_val) + pair_bonus_deltas.get(name, 0)

        return deltas, preview_specs

    def _apply_happiness_preview_colors(self, round_idx):
        """Color all player buttons in round_idx based on simulated happiness delta."""
        if not hasattr(self, "game_player_buttons"):
            return

        deltas, preview_specs = self._preview_happiness_delta(round_idx)
        if not deltas:
            return

        game_round = self.session_of_rounds.rounds[round_idx]
        is_spectrum = getattr(game_round, "spectrum", False)

        over_benched_names = self._over_benched_not_playing_names()

        for key, btn in list(self.game_player_buttons.items()):
            btn_round, game_idx, team_id, row, col = key
            if btn_round != round_idx:
                continue

            # Resolve current player from data model
            try:
                if team_id == "not_playing":
                    index = row * 4 + col
                    player = game_round.not_playing[index]
                else:
                    game = game_round.games[game_idx]
                    player = (
                        game.team_A.players[col]
                        if team_id == "A"
                        else game.team_B.players[col]
                    )
            except Exception:
                continue

            try:
                if team_id == "not_playing":
                    token = self._middle_style_token_for_player(
                        player,
                        team_id,
                        over_benched_names=over_benched_names,
                    )
                    self._apply_player_button_presentation(
                        btn,
                        player,
                        team_id,
                        middle_token=token,
                    )
                else:
                    delta = deltas.get(player.name, 0.0)
                    bg, suffix = self._delta_to_bg(delta)
                    if is_spectrum:
                        sim_spec = preview_specs.get(player.name)
                        abbrev = self._abbrev_spec(sim_spec)
                        if suffix:
                            middle = f"{abbrev} {suffix}".strip() if abbrev else suffix
                        else:
                            middle = abbrev or None
                    else:
                        middle = suffix
                    self._apply_player_button_presentation(
                        btn,
                        player,
                        team_id,
                        middle_override=middle,
                        bg_override=bg,
                    )
            except Exception:
                pass

        # Enforce global not-playing styles for matching names across all rounds.
        self._refresh_not_playing_button_styles()

    # ------------------------------------------------------------------
    # Hover tooltip infrastructure (steps 10-13)
    # ------------------------------------------------------------------

    def _bind_player_hover_tooltip(self, btn, round_idx, game_idx, team_id):
        """Bind enter/leave events on a player button to show a 1-second hover tooltip."""
        btn.bind(
            "<Enter>",
            lambda e: self._schedule_ge_tooltip(e, btn, round_idx, game_idx, team_id),
        )
        btn.bind("<Leave>", self.hide_tooltip)

    def _schedule_ge_tooltip(self, event, btn, round_idx, game_idx, team_id):
        """Cancel any pending tooltip and schedule a fresh one after 1 second."""
        self.hide_tooltip()
        delay = getattr(self, "_ge_tooltip_delay_ms", 500)
        self._tooltip_after_id = self.root.after(
            delay,
            lambda: self._show_ge_tooltip(btn, round_idx, game_idx, team_id),
        )

    def _compute_tooltip_breakdown(self, player, round_idx, game_idx, team_id):
        """Compute all happiness breakdown components from the live game state.

        Returns a dict with keys:
          is_spectrum, spec_breakdown, chosen_spec,
          high_lvl_tmmt, high_lvl_opp,
          same_tmmt_penalty, same_people_penalty, never_met_bonus,
          gender_penalty, minority_bonus, above_median_bonus,
          pair_bonus, total_gain
        Or {'sitting_out': True} for not_playing players.
        """
        if team_id == "not_playing":
            return {"sitting_out": True}

        try:
            game_round = self.session_of_rounds.rounds[round_idx]
        except Exception:
            return {"error": True}

        # -- Resolve live game object by searching for the player (handles cross-game swaps) --
        game = None
        my_team = None
        opp_team = None
        for g in game_round.games:
            if player in g.team_A.players_set:
                game = g
                my_team = g.team_A
                opp_team = g.team_B
                break
            if player in g.team_B.players_set:
                game = g
                my_team = g.team_B
                opp_team = g.team_A
                break
        if game is None:
            return {"error": True}

        is_spectrum = getattr(game_round, "spectrum", False)

        teammates = [p for p in my_team.players if p is not player]
        opponents = list(opp_team.players)
        teammates_levels = [p.level for p in teammates]
        opponents_levels = [p.level for p in opponents]
        all_others = frozenset(p for p in game.participants if p is not player)

        # -- Read params (with fallbacks matching update_happiness defaults) --
        p = getattr(game_round, "_params", {})
        weight = getattr(game_round, "weight_same_teammate", 5)
        nmb_per_player = getattr(game_round, "never_met_bonus_per_player", 2)
        nmb_cap = getattr(game_round, "never_met_bonus_cap", 4)
        same_div = (
            float(
                p.get(
                    "happiness_penalty_same_people_in_game_history_weight_same_teammate_divisor",
                    2,
                )
            )
            or 2.0
        )
        level_gap_tol = getattr(game_round, "level_gap_tol", 0.5)
        hl_mult = float(
            p.get("non_spectrum_high_level_threshold_self_level_multiplier", 0.85)
        )
        gender_pen_spectrum = float(
            p.get("happiness_penalty_gender_preference_not_satisfied_spectrum", 5)
        )
        gender_pen_non_spectrum = float(
            p.get("happiness_penalty_gender_preference_not_satisfied_non_spectrum", 2)
        )
        minority_bonus_val = float(p.get("happiness_bonus_minority_gender_mixed", 1))
        above_median_bonus_val = float(
            p.get("happiness_bonus_above_median_level_type_level", 1)
        )

        # -- Is this round's happiness pending (swap not yet applied)? --
        round_has_pending = any(
            c["round_idx"] == round_idx for c in getattr(self, "pending_changes", [])
        )

        # -- Spectrum breakdown --
        spec_breakdown = {}
        chosen_spec = None
        if is_spectrum:
            import numpy as np  # noqa: PLC0415

            teammates_mean = (
                float(np.mean(teammates_levels)) if teammates_levels else player.level
            )
            team_mean = float(np.mean(teammates_levels + [player.level]))
            opponents_mean = (
                float(np.mean(opponents_levels)) if opponents_levels else player.level
            )
            prey_mult = float(
                p.get("spectrum_prey_opponents_mean_level_multiplier", 0.7)
            )
            eq_mult = float(p.get("spectrum_equilibrist_level_gap_tol_multiplier", 0.5))
            chal_opp_mult = float(
                p.get("spectrum_challenger_opponents_mean_level_multiplier", 0.9)
            )
            chal_gap_mult = float(
                p.get("spectrum_challenger_level_gap_tol_multiplier", 0.5)
            )
            chill_thresh = float(p.get("spectrum_chill_players_chill_threshold", 10))
            clst_gap_mult = float(
                p.get("spectrum_classist_level_gap_tol_multiplier", 0.5)
            )
            # count chill players in game (level <= chill_thresh)
            players_chill = sum(
                1 for pp in game.participants if pp.level <= chill_thresh
            )
            spectrum_triggered = {
                "Prey": 1 if prey_mult * opponents_mean >= player.level else 0,
                "Equilibrist": (
                    1
                    if abs(team_mean - opponents_mean) <= eq_mult * level_gap_tol
                    else 0
                ),
                "Challenger": (
                    1
                    if abs(chal_opp_mult * opponents_mean - team_mean)
                    <= chal_gap_mult * level_gap_tol
                    else 0
                ),
                "Chill": 1 if players_chill >= chill_thresh else 0,
                "Hunter": 1 if opponents_mean <= team_mean else 0,
                "Classist": (
                    1
                    if abs(player.level - teammates_mean)
                    <= clst_gap_mult * level_gap_tol
                    else 0
                ),
            }
            for spec_name, triggered in spectrum_triggered.items():
                score = getattr(player, _SPEC_KEY_TO_ATTR[spec_name], 0) or 0
                spec_breakdown[spec_name] = {
                    "score": score,
                    "triggered": bool(triggered),
                    "gain": score * triggered,
                }

            # Determine chosen spec:
            # - For committed rounds: read spec_chosen_history
            # - For pending rounds: run simulation to get current spec
            if not round_has_pending:
                try:
                    chosen_spec = player.spec_chosen_history[round_idx]
                except (IndexError, AttributeError):
                    chosen_spec = None
            else:
                # Quick simulation to get preview spec for this player
                try:
                    _, preview_specs = self._preview_happiness_delta(round_idx)
                    chosen_spec = preview_specs.get(player.name)
                except Exception:
                    chosen_spec = None

        # -- Non-spectrum breakdown --
        high_lvl_tmmt = 0
        high_lvl_opp = 0
        if not is_spectrum:
            threshold = player.level * hl_mult
            high_lvl_tmmt = sum(1 for lvl in teammates_levels if lvl >= threshold)
            high_lvl_opp = sum(1 for lvl in opponents_levels if lvl >= threshold)

        # -- History-based components (always use history up to round_idx) --
        prior_teammate_sets = (
            player.teammate_history[:round_idx]
            if hasattr(player, "teammate_history")
            else []
        )
        prior_game_sets = (
            player.other_players_in_same_game_history[:round_idx]
            if hasattr(player, "other_players_in_same_game_history")
            else []
        )
        prior_teammates_flat = frozenset(pp for fs in prior_teammate_sets for pp in fs)
        prior_game_flat = frozenset(pp for fs in prior_game_sets for pp in fs)
        prior_all = prior_teammates_flat | prior_game_flat

        # current teammate frozenset (live, for pending rounds)
        current_tmmt_fs = frozenset(my_team.players_set)

        has_same_teammate = current_tmmt_fs in prior_teammate_sets

        same_people_count = sum(1 for pp in all_others if pp in prior_game_flat)
        never_met_count = sum(1 for pp in all_others if pp not in prior_all)

        same_tmmt_penalty = -weight if has_same_teammate else 0.0
        same_people_penalty = -(weight / same_div) * same_people_count
        never_met_bonus = min(never_met_count * nmb_per_player, nmb_cap)

        # -- Gender / level bonuses --
        is_gender_sat = getattr(game, "is_gender_preference_satisfied", True)
        gender_preference = getattr(game, "gender_preference", None)
        type_preference = getattr(game, "type_preference", None)
        minority_gender = getattr(game_round, "minority_gender", None)
        gender_level_medians = getattr(game_round, "gender_level_medians", {})
        session_median = getattr(game_round, "session_median_level", None)

        gender_penalty = 0.0
        if not is_gender_sat:
            gender_penalty = (
                -gender_pen_spectrum if is_spectrum else -gender_pen_non_spectrum
            )

        minority_bonus = 0.0
        if gender_preference == "mixed" and minority_gender is not None:
            if player.gender == minority_gender:
                minority_bonus = minority_bonus_val

        above_median_bonus = 0.0
        if type_preference == "level":
            if gender_preference == "mixed" and gender_level_medians:
                gender_median = gender_level_medians.get(player.gender)
                if gender_median is not None and player.level > gender_median:
                    above_median_bonus = above_median_bonus_val
            elif session_median is not None:
                if player.level > session_median:
                    above_median_bonus = above_median_bonus_val

        # -- Pair bonus (from committed _pair_happiness_per_round) --
        pair_bonus = 0.0
        try:
            per_round = self.session_of_rounds._pair_happiness_per_round
            awards = per_round.get(player.name, [])
            if round_idx < len(awards):
                pair_bonus = float(awards[round_idx])
        except Exception:
            pair_bonus = 0.0

        # -- Total gain --
        if is_spectrum:
            spec_gain = (
                spec_breakdown.get(chosen_spec, {}).get("gain", 0) if chosen_spec else 0
            )
            total = (
                spec_gain
                + same_tmmt_penalty
                + same_people_penalty
                + never_met_bonus
                + gender_penalty
                + minority_bonus
                + above_median_bonus
                + pair_bonus
            )
        else:
            total = (
                high_lvl_tmmt
                + high_lvl_opp
                + same_tmmt_penalty
                + same_people_penalty
                + never_met_bonus
                + gender_penalty
                + minority_bonus
                + above_median_bonus
                + pair_bonus
            )

        return {
            "is_spectrum": is_spectrum,
            "spec_breakdown": spec_breakdown,
            "chosen_spec": chosen_spec,
            "high_lvl_tmmt": high_lvl_tmmt,
            "high_lvl_opp": high_lvl_opp,
            "same_tmmt_penalty": same_tmmt_penalty,
            "same_people_penalty": same_people_penalty,
            "never_met_bonus": never_met_bonus,
            "never_met_count": never_met_count,
            "gender_penalty": gender_penalty,
            "minority_bonus": minority_bonus,
            "above_median_bonus": above_median_bonus,
            "pair_bonus": pair_bonus,
            "total_gain": total,
            "round_has_pending": round_has_pending,
        }

    def _build_ge_tooltip_text(self, player, round_idx, game_idx, team_id):
        """Format the breakdown dict from _compute_tooltip_breakdown into display text."""
        bd = self._compute_tooltip_breakdown(player, round_idx, game_idx, team_id)
        lines = [f"── {player.name}  [Round {round_idx + 1}] ──"]

        if bd.get("sitting_out"):
            lines.append("Sitting out this round")
            return "\n".join(lines)

        if bd.get("error"):
            lines.append("(Could not compute breakdown)")
            return "\n".join(lines)

        is_spectrum = bd["is_spectrum"]

        if is_spectrum:
            spec_bd = bd["spec_breakdown"]
            chosen = bd["chosen_spec"]
            # Row 1: Prey / Hntr / Clgr — Row 2: Clst / Equl / Chll
            order = ["Prey", "Hunter", "Challenger", "Classist", "Equilibrist", "Chill"]
            row_parts = [[], []]
            for i, spec_name in enumerate(order):
                abbrev = _SPEC_ABBREV.get(spec_name, spec_name)
                info = spec_bd.get(spec_name, {})
                score = info.get("score", 0)
                triggered = info.get("triggered", False)
                marker = "✓" if triggered else " "
                row_parts[i // 3].append(f"{abbrev}:{score}{marker}")
            lines.append("  " + "  ".join(row_parts[0]))
            lines.append("  " + "  ".join(row_parts[1]))
            chosen_gain = spec_bd.get(chosen, {}).get("gain", 0) if chosen else 0
            chosen_abbrev = _SPEC_ABBREV.get(chosen, chosen or "?")
            lines.append(f"  → Chosen: {chosen_abbrev}  {chosen_gain:+.0f}")
        else:
            if bd["high_lvl_tmmt"]:
                lines.append(f"High-lvl tmmt:  +{bd['high_lvl_tmmt']}")
            if bd["high_lvl_opp"]:
                lines.append(f"High-lvl opp:   +{bd['high_lvl_opp']}")

        if bd["never_met_bonus"]:
            lines.append(
                f"Never met:      {bd['never_met_bonus']:+.0f}  ({bd['never_met_count']} new)"
            )
        if bd["same_tmmt_penalty"]:
            lines.append(f"Same tmmt:      {bd['same_tmmt_penalty']:+.0f}")
        if bd["same_people_penalty"]:
            lines.append(f"Same people:    {bd['same_people_penalty']:+.0f}")
        if bd["gender_penalty"]:
            lines.append(
                f"Gender pref:    {bd['gender_penalty']:+.0f}  (not satisfied)"
            )
        if bd["minority_bonus"]:
            lines.append(f"Minority:       {bd['minority_bonus']:+.0f}")
        if bd["above_median_bonus"]:
            lines.append(f"Level bonus:    {bd['above_median_bonus']:+.0f}")
        if bd["pair_bonus"]:
            lines.append(f"Pref pair:      {bd['pair_bonus']:+.0f}")

        lines.append("─" * 20)
        pending_tag = "  [pending]" if bd.get("round_has_pending") else ""
        lines.append(f"Total:          {bd['total_gain']:+.0f}{pending_tag}")
        return "\n".join(lines)

    def _show_ge_tooltip(self, btn, round_idx, game_idx, team_id):
        """Compute and show the tooltip for the given player button."""
        try:
            # Resolve player from live data model (not stale player_info cache)
            key = None
            for k, b in self.game_player_buttons.items():
                if b is btn:
                    key = k
                    break
            if key is None:
                return
            player = self._player_from_button_key(key)
            if player is None:
                return

            text = self._build_ge_tooltip_text(player, round_idx, game_idx, team_id)
            x = btn.winfo_rootx() + btn.winfo_width() + 4
            y = btn.winfo_rooty()
            self.show_tooltip_at(x, y, text)
        except Exception:
            pass

    def toggle_player_selection(self, button, player_info):
        """Toggle player selection for swapping"""
        # Check if this player is already selected
        for idx, (btn, info) in enumerate(self.selected_for_swap):
            if info["player"].name == player_info["player"].name:
                # Deselect
                token = self._middle_style_token_for_player(
                    info["player"],
                    info.get("team_id"),
                )
                self._apply_player_button_presentation(
                    btn,
                    info["player"],
                    info.get("team_id"),
                    middle_token=token,
                )
                self.selected_for_swap.pop(idx)
                return

        # Select this player
        button.config(bg=self.colors["accent_yellow"], relief=tk.SUNKEN)
        self.selected_for_swap.append((button, player_info))

        # If two players are selected, perform swap
        if len(self.selected_for_swap) == 2:
            self.swap_players()

    def swap_players(self):
        """Swap two selected players"""
        if len(self.selected_for_swap) != 2:
            return

        btn1, info1 = self.selected_for_swap[0]
        btn2, info2 = self.selected_for_swap[1]

        player1 = info1["player"]
        player2 = info2["player"]

        # Check if they're in the same round
        if info1["round_idx"] != info2["round_idx"]:
            messagebox.showwarning(
                "Invalid Swap", "Can only swap players within the same round!"
            )
            # Deselect both
            token1 = self._middle_style_token_for_player(
                info1["player"], info1.get("team_id")
            )
            token2 = self._middle_style_token_for_player(
                info2["player"], info2.get("team_id")
            )
            self._apply_player_button_presentation(
                btn1,
                info1["player"],
                info1.get("team_id"),
                middle_token=token1,
            )
            self._apply_player_button_presentation(
                btn2,
                info2["player"],
                info2.get("team_id"),
                middle_token=token2,
            )
            self.selected_for_swap.clear()
            return

        round_idx = info1["round_idx"]
        game_round = self.session_of_rounds.rounds[round_idx]

        # Find positions of both players
        pos1 = game_round.find_player_position(player1)
        pos2 = game_round.find_player_position(player2)

        if pos1 is None or pos2 is None:
            messagebox.showerror("Error", "Could not find player positions!")
            self.selected_for_swap.clear()
            return

        # Perform the swap in the data structure
        game_round.swap_player_positions(pos1, pos2)

        # Track this change in pending changes
        self.pending_changes.append(
            {"round_idx": round_idx, "player1": player1.name, "player2": player2.name}
        )

        # Track in swap history for undo
        self.swap_history.append(
            {"round_idx": round_idx, "player1": player1, "player2": player2}
        )

        # Enable undo button
        self.undo_button.config(state=tk.NORMAL)

        # Update button labels
        btn1.config(
            relief=tk.RAISED,
        )
        btn2.config(
            relief=tk.RAISED,
        )

        # Update the player info references
        info1["player"] = player2
        info2["player"] = player1

        token1 = self._middle_style_token_for_player(player2, info1.get("team_id"))
        token2 = self._middle_style_token_for_player(player1, info2.get("team_id"))
        self._apply_player_button_presentation(
            btn1,
            player2,
            info1.get("team_id"),
            middle_token=token1,
        )
        self._apply_player_button_presentation(
            btn2,
            player1,
            info2.get("team_id"),
            middle_token=token2,
        )

        # Clear selection
        self.selected_for_swap.clear()

        # Refresh level diff labels and team frame colours for the affected games
        self._refresh_level_diff_labels(round_idx)
        self._refresh_team_frame_colors(round_idx, info1["game_idx"])
        if info2["game_idx"] != info1["game_idx"]:
            self._refresh_team_frame_colors(round_idx, info2["game_idx"])

        # Update changes display
        self.update_changes_display()

        # Update status
        self.status_label.config(
            text=f"{len(self.pending_changes)} change(s) pending - Click Apply to recalculate happiness",
            fg=self.colors["accent_yellow"],
        )

        # Apply happiness-delta preview colors to all buttons in the affected round
        self._apply_happiness_preview_colors(round_idx)

        print(
            f"Swapped {player1.name} and {player2.name} in Round {round_idx + 1} (pending)"
        )

    def _refresh_level_diff_labels(self, round_idx):
        """Update the level-diff labels above VS for every game in the given round."""
        if (
            not hasattr(self, "game_level_diff_labels")
            or self.session_of_rounds is None
        ):
            return
        game_round = self.session_of_rounds.rounds[round_idx]
        for game_idx, game in enumerate(game_round.games):
            diff_label = self.game_level_diff_labels.get((round_idx, game_idx))
            if diff_label is None:
                continue
            level_diff = game.team_A.mean_level - game.team_B.mean_level
            diff_text = f"+{level_diff:.1f}" if level_diff > 0 else f"{level_diff:.1f}"
            diff_color = "#2255AA" if level_diff >= 0 else "#AA2222"
            diff_label.config(text=diff_text, fg=diff_color)

    def _render_score_history(self):
        """Redraw the score history strip; each chip (except current) is clickable to restore that version."""
        if not hasattr(self, "score_history_container"):
            return
        for w in self.score_history_container.winfo_children():
            w.destroy()

        GREEN = "#4CAF50"
        RED = "#E53935"
        GRAY = "#BBBBBB"

        last_idx = len(self.score_history) - 1
        for i, entry in enumerate(self.score_history):
            score, pkl_path = entry if isinstance(entry, tuple) else (entry, None)

            # Determine colour relative to previous entry
            if i == 0:
                label_text = "Initial"
                box_color = GRAY
                arrow = ""
            else:
                prev_entry = self.score_history[i - 1]
                prev = prev_entry[0] if isinstance(prev_entry, tuple) else prev_entry
                delta = score - prev
                if delta > 0.009:
                    box_color = GREEN
                    arrow = f"  ▲ +{delta:.2f}"
                elif delta < -0.009:
                    box_color = RED
                    arrow = f"  ▼ {delta:.2f}"
                else:
                    box_color = GRAY
                    arrow = "  ≈ 0"
                label_text = f"Swap {i}"

            is_current = i == last_idx
            cell = tk.Frame(
                self.score_history_container,
                bg=box_color,
                relief=tk.SUNKEN if is_current else tk.RIDGE,
                bd=3 if is_current else 1,
            )
            cell.pack(side=tk.LEFT, padx=3, pady=2)

            display_label = f"► {label_text}" if is_current else label_text
            lbl_top = tk.Label(
                cell,
                text=display_label,
                font=(
                    self.fonts["small"][0],
                    max(7, self.fonts["small"][1] - 1),
                    "bold",
                ),
                fg=self.colors["text_dark"],
                bg=box_color,
                padx=6,
                pady=1,
            )
            lbl_top.pack()
            lbl_score = tk.Label(
                cell,
                text=f"{score:.3f}",
                font=(self.fonts["small"][0], self.fonts["small"][1], "bold"),
                fg=self.colors["text_dark"],
                bg=box_color,
                padx=6,
                pady=1,
            )
            lbl_score.pack()

            lbl_arrow = None
            if arrow:
                lbl_arrow = tk.Label(
                    cell,
                    text=arrow,
                    font=(self.fonts["small"][0], max(7, self.fonts["small"][1] - 1)),
                    fg=self.colors["text_dark"],
                    bg=box_color,
                    padx=4,
                    pady=1,
                )
                lbl_arrow.pack()

            # Make non-current chips clickable to restore that session version
            if not is_current and pkl_path:
                _handler = lambda e, p=pkl_path: self._restore_session_version(p)
                targets = (cell, lbl_top, lbl_score) + (
                    (lbl_arrow,) if lbl_arrow else ()
                )
                for widget in targets:
                    widget.config(cursor="hand2")
                    widget.bind("<Button-1>", _handler)

    def _restore_session_version(self, pkl_path):
        """Restore the editor to a previously saved session version."""
        if not pkl_path or not os.path.exists(pkl_path):
            messagebox.showerror(
                "Restore failed", f"Snapshot file not found:\n{pkl_path}"
            )
            return

        from core.pickle_helper import load_session  # noqa: PLC0415

        try:
            session = load_session(pkl_path)

            # Stamp objective metadata if absent (legacy pkls)
            if not getattr(session, "_objective_function_name", None):
                session._objective_function_name = "mean_min_max_happiness_objective"
            if getattr(session, "_objective_lambda_weight", None) is None:
                session._objective_lambda_weight = 2.4
            if getattr(session, "_objective_percentile", None) is None:
                session._objective_percentile = 10

            self.session_of_rounds = session

            # Truncate history to this restore point and preserve it across editor rebuild
            for idx, entry in enumerate(self.score_history):
                _, path = entry if isinstance(entry, tuple) else (entry, None)
                if path == pkl_path:
                    self._pending_restore_history = self.score_history[: idx + 1]
                    break

            # Rebuild editor with restored session state
            self.show_games_editor()
            print(f"\nSession restored from: {os.path.basename(pkl_path)}")

        except Exception as e:
            import traceback  # noqa: PLC0415

            print(f"Error restoring session version: {e}")
            traceback.print_exc()
            messagebox.showerror(
                "Restore failed", f"Could not restore session:\n\n{str(e)}"
            )

    def update_changes_display(self):
        """Update the visual display of pending changes"""
        # Clear existing changes display
        for widget in self.changes_list_frame.winfo_children():
            widget.destroy()

        if not self.pending_changes:
            # Show "no changes" message
            self.no_changes_label = tk.Label(
                self.changes_list_frame,
                text="No changes yet",
                font=self.fonts["small"],
                fg="#888888",
                bg=self.colors["bg_light"],
            )
            self.no_changes_label.pack(pady=5)
        else:
            # Show list of changes
            for idx, change in enumerate(self.pending_changes, 1):
                change_text = f"{idx}. Round {change['round_idx'] + 1}: {change['player1']} ↔ {change['player2']}"
                change_label = tk.Label(
                    self.changes_list_frame,
                    text=change_text,
                    font=self.fonts["small"],
                    fg=self.colors["text_dark"],
                    bg=self.colors["bg_light"],
                    anchor=tk.W,
                )
                change_label.pack(anchor=tk.W, padx=10, pady=2)

    def undo_last_swap(self):
        """Undo the last swap operation"""
        if not self.swap_history:
            messagebox.showinfo("Nothing to Undo", "No swaps to undo.")
            return

        # Get the last swap
        last_swap = self.swap_history.pop()
        round_idx = last_swap["round_idx"]
        player1 = last_swap["player1"]
        player2 = last_swap["player2"]

        # Find and remove from pending changes
        for i, change in enumerate(self.pending_changes):
            if (
                change["round_idx"] == round_idx
                and change["player1"] == player1.name
                and change["player2"] == player2.name
            ):
                self.pending_changes.pop(i)
                break

        # Swap the players back
        game_round = self.session_of_rounds.rounds[round_idx]
        pos1 = game_round.find_player_position(player1)
        pos2 = game_round.find_player_position(player2)

        if pos1 and pos2:
            game_round.swap_player_positions(pos1, pos2)

        # Refresh visible UI for this round so button labels reflect the data model
        try:
            # Refresh visible UI. Use the comprehensive refresh to cover all stored buttons.
            self.refresh_all_rounds()
        except Exception:
            # Fallback: still update changes display even if refresh fails
            pass

        # Update changes display
        self.update_changes_display()

        # Update status
        if self.pending_changes:
            self.status_label.config(
                text=f"{len(self.pending_changes)} change(s) pending - Click Apply to recalculate happiness",
                fg=self.colors["accent_yellow"],
            )
        else:
            self.status_label.config(
                text="No pending changes", fg=self.colors["text_dark"]
            )

        # Disable undo button if no more swaps
        if not self.swap_history:
            self.undo_button.config(state=tk.DISABLED)

        # Re-apply happiness-delta preview colors for any rounds still pending.
        # The undo'd round was just reset to white by refresh_all_rounds(); only
        # rounds that still have pending swaps need their colours recalculated.
        still_pending_rounds = set(c["round_idx"] for c in self.pending_changes)
        for _r in still_pending_rounds:
            self._apply_happiness_preview_colors(_r)

        print(f"Undid swap: {player1.name} and {player2.name} in Round {round_idx + 1}")

    def apply_changes(self):
        """Apply all pending changes and recalculate happiness for affected rounds"""
        if not self.pending_changes:
            messagebox.showinfo("No Changes", "No pending changes to apply.")
            return

        # Disable the apply button to prevent multiple clicks
        self.apply_button.config(state=tk.DISABLED)

        print("\n" + "=" * 80)
        print(f"APPLYING {len(self.pending_changes)} CHANGES")
        print("=" * 80)

        # Get unique rounds that were modified
        modified_rounds = sorted(
            set(change["round_idx"] for change in self.pending_changes)
        )

        # Apply changes using the SessionOfRounds methods
        print(f"\nRecalculating happiness for {len(modified_rounds)} round(s)...")

        # Check if the method exists (for older session objects)
        if hasattr(self.session_of_rounds, "apply_changes_to_rounds"):
            self.session_of_rounds.apply_changes_to_rounds(modified_rounds)
        else:
            # Fallback: manually recalculate for older session objects
            print("Using fallback recalculation method...")
            for round_idx in modified_rounds:
                print(f"Recalculating happiness for Round {round_idx + 1}...")
                game_round = self.session_of_rounds.rounds[round_idx]

                # Manually call recalculate_happiness if it exists
                if hasattr(game_round, "recalculate_happiness"):
                    game_round.recalculate_happiness(round_idx=round_idx)
                else:
                    messagebox.showerror(
                        "Error",
                        "Your session object is outdated. Please restart the Python kernel and regenerate the session.",
                    )
                    return

            # Recalculate session statistics
            if hasattr(self.session_of_rounds, "recalculate_session_statistics"):
                self.session_of_rounds.recalculate_session_statistics()
            else:
                # Fallback for older sessions
                import numpy as np  # noqa: PLC0415

                self.session_of_rounds.mean_happiness = np.mean(
                    [player.happiness for player in self.session_of_rounds.players]
                )
                self.session_of_rounds.std_happiness = np.std(
                    [player.happiness for player in self.session_of_rounds.players]
                )

        # Re-apply preferred pair bonuses with updated team assignments.
        # recalculate_happiness only redoes game-mechanics gains; the pair bonus
        # (added directly to player.happiness) must be reversed and re-computed
        # based on the new pairing so it stays accurate after swaps.
        if (
            getattr(self, "preferred_pairs", None)
            and hasattr(self.session_of_rounds, "_pair_happiness_per_round")
            and main_module is not None
        ):
            per_round_awards = self.session_of_rounds._pair_happiness_per_round
            for _player in self.session_of_rounds.players:
                _old_total = sum(per_round_awards.get(_player.name, []))
                _player.happiness -= _old_total
            main_module.apply_preferred_pairs_happiness(
                self.session_of_rounds, self.preferred_pairs
            )

        # Clear pending changes and swap history
        num_changes = len(self.pending_changes)
        self.pending_changes.clear()
        self.swap_history.clear()

        # Update baseline gains and reset all button colors to white now that
        # happiness has been officially recalculated.
        self._editor_baseline_gains = {}
        for _r_idx, _game_round in enumerate(self.session_of_rounds.rounds):
            _round_baseline = {}
            for _p in self.session_of_rounds.players:
                if _r_idx < len(_p.happiness_gained_history):
                    _round_baseline[_p.name] = _p.happiness_gained_history[_r_idx]
                else:
                    _round_baseline[_p.name] = None
            self._editor_baseline_gains[_r_idx] = _round_baseline

        for _key, _btn in list(self.game_player_buttons.items()):
            try:
                _r_idx, _g_idx, _team_id, _row, _col = _key
                _game_round = self.session_of_rounds.rounds[_r_idx]
                if _team_id == "not_playing":
                    _player = _game_round.not_playing[_row * 4 + _col]
                elif _team_id == "A":
                    _player = _game_round.games[_g_idx].team_A.players[_col]
                else:
                    _player = _game_round.games[_g_idx].team_B.players[_col]
                _token = self._middle_style_token_for_player(_player, _team_id)
                _spec_middle = self._baseline_spec_middle(_player, _r_idx, _team_id)
                self._apply_player_button_presentation(
                    _btn,
                    _player,
                    _team_id,
                    middle_token=_token,
                    middle_override=_spec_middle,
                )
            except Exception:
                pass

        # Disable undo button
        self.undo_button.config(state=tk.DISABLED)

        # Update changes display
        self.update_changes_display()

        # Update status - show "Processing..." while regenerating plots
        self.status_label.config(
            text="Processing changes...", fg=self.colors["accent_yellow"]
        )

        print("\n" + "=" * 80)
        print("CHANGES APPLIED - RECALCULATION COMPLETE")
        print(f"New Mean Happiness: {self.session_of_rounds.mean_happiness:.2f}")
        print(f"New Std Happiness: {self.session_of_rounds.std_happiness:.2f}")
        print("=" * 80)

        # Pre-compute the versioned pkl path for this apply operation so score history
        # can link each chip to the snapshot written during the same apply.
        _versioned_pkl_for_hist = None
        _sf_for_hist = getattr(self, "_active_session_folder", None)
        if _sf_for_hist and os.path.exists(_sf_for_hist):
            import re as _re_hist  # noqa: PLC0415

            _fn_for_hist = os.path.basename(_sf_for_hist)
            _dp_for_hist = "_".join(_fn_for_hist.split("_")[:3])
            _existing_v_for_hist = [
                f
                for f in os.listdir(_sf_for_hist)
                if f.endswith(".pkl") and _re_hist.search(r"_v\d+\.pkl$", f)
            ]
            _nv_for_hist = len(_existing_v_for_hist) + 1
            _versioned_pkl_for_hist = os.path.join(
                _sf_for_hist,
                f"session_of_rounds_{_dp_for_hist}_v{_nv_for_hist}.pkl",
            )

        # Append new score to history and refresh the strip
        try:
            from core.models import (
                compute_session_score as _compute_session_score,
            )  # noqa: PLC0415

            _new_score = _compute_session_score(
                self.session_of_rounds.players,
                getattr(self, "_score_obj_name", None),
                getattr(self, "_score_lw", 2.4),
                getattr(self, "_score_pct", 10),
            )
            if hasattr(self, "score_history"):
                self.score_history.append((_new_score, _versioned_pkl_for_hist))
            self._render_score_history()
        except Exception:
            pass

        # Regenerate plots, update XLS and PKL files if they exist
        try:
            session_folder = getattr(self, "_active_session_folder", None)
            if session_folder and os.path.exists(session_folder):
                plots_dir = os.path.join(session_folder, "plots")
                os.makedirs(plots_dir, exist_ok=True)

                print("\nRegenerating plots with updated data...")
                # Add a clear blank line before heavy chart work
                print()
                main_module.create_all_session_charts(
                    self.session_of_rounds, save_png=True, png_dir=plots_dir
                )

                # Small pause in console output for readability
                print()
                # Refresh plot tabs
                self.show_plots_window(plots_dir)
                print("\nPlots regenerated successfully!\n")

                # Regenerate and refresh the Session Games PNG
                try:
                    from core.charts import (  # noqa: PLC0415
                        create_session_games_png,
                        create_session_games_round_images,
                    )

                    session_games_png = os.path.join(
                        session_folder, "session_games.png"
                    )
                    create_session_games_png(
                        self.session_of_rounds,
                        session_games_png,
                        show_levels=self.png_show_levels_var.get(),
                    )
                    _round_imgs = create_session_games_round_images(
                        self.session_of_rounds,
                        show_levels=self.png_show_levels_var.get(),
                    )
                    self.show_session_games_tab(
                        session_games_png, round_images=_round_imgs
                    )
                    print("Session Games PNG updated successfully!\n")
                except Exception as png_error:
                    print(f"Warning: Could not update Session Games PNG: {png_error}")

                # Update Excel file with new game data
                print("\nUpdating Excel file with new data...\n")
                try:
                    # Find the existing xlsx file in the session folder
                    xlsx_files = [
                        f
                        for f in os.listdir(session_folder)
                        if f.endswith(".xlsx") and not f.endswith("_read_only.xlsx")
                    ]
                    if xlsx_files:
                        xlsx_filename = xlsx_files[0]  # Use the first found
                    else:
                        # Fallback: use default naming if none found
                        folder_name = os.path.basename(session_folder)
                        date_str = "_".join(folder_name.split("_")[:3])
                        xlsx_filename = f"session_{date_str}.xlsx"

                    self.session_of_rounds.export_to_excel(
                        directory=session_folder, filename=xlsx_filename
                    )
                    print(f"Excel file updated successfully as {xlsx_filename}!")
                except Exception as excel_error:
                    print(f"Warning: Could not update Excel file: {excel_error}")

                # Save versioned pickle snapshot
                print("\nSaving versioned pickle snapshot...\n")
                try:
                    import re as _re_pkl  # noqa: PLC0415
                    from core.pickle_helper import save_session  # noqa: PLC0415

                    folder_name = os.path.basename(session_folder)
                    date_str = "_".join(folder_name.split("_")[:3])
                    existing_versions = [
                        f
                        for f in os.listdir(session_folder)
                        if f.endswith(".pkl") and _re_pkl.search(r"_v\d+\.pkl$", f)
                    ]
                    next_version = len(existing_versions) + 1
                    versioned_filename = (
                        f"session_of_rounds_{date_str}_v{next_version}.pkl"
                    )
                    save_session(
                        self.session_of_rounds,
                        folder=session_folder,
                        filename=versioned_filename,
                    )
                    print(f"Versioned pickle saved as: {versioned_filename}")
                except Exception as pickle_error:
                    print(f"Warning: Could not save versioned pickle: {pickle_error}")
        except Exception as e:
            print(f"Warning: Could not regenerate plots: {e}")

        # Update status label after everything is done
        self.status_label.config(
            text="Changes applied successfully!", fg=self.colors["accent_yellow"]
        )

        print("\n" + "=" * 80)
        print("ALL OPERATIONS COMPLETED SUCCESSFULLY")
        print("=" * 80)

        messagebox.showinfo(
            "Success",
            f"Applied {num_changes} change(s) successfully!\n\n"
            f"New Mean Happiness: {self.session_of_rounds.mean_happiness:.2f}\n"
            f"New Std Happiness: {self.session_of_rounds.std_happiness:.2f}\n\n"
            "Session files updated:\n"
            "• Plots regenerated\n"
            "• Excel file updated\n"
            "• Versioned pickle snapshot saved",
        )

        # Re-enable the apply button
        self.apply_button.config(state=tk.NORMAL)
