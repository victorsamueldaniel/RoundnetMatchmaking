"""Games Editor tab controller."""

import os

import tkinter as tk
from tkinter import messagebox

from ui.functions.tab_functions import games_editor_delta_to_bg

main_module = None


class GamesEditorTabMixin:
    def show_games_editor(self):
        """Create interactive games editor tab where users can swap players"""
        if not hasattr(self, "session_of_rounds") or self.session_of_rounds is None:
            print("No session available to edit.")
            return

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
        self.score_history = [_initial_score]
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
            text=f"{player.name}\n\nLvl {player.level}",
            font=getattr(self, "games_editor_player_button_font", self.fonts["small"]),
            bg=self.colors["bg_light"],
            fg=self.colors["text_dark"],
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

        btn = tk.Button(
            parent,
            text=f"{player.name}\n\nLvl {player.level}",
            font=getattr(self, "games_editor_player_button_font", self.fonts["small"]),
            bg=self.colors["bg_light"],
            fg=self.colors["text_dark"],
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
        return btn

    def refresh_round_ui(self, round_idx):
        """Refresh the visible buttons for a specific round based on data model."""
        if not hasattr(self, "session_of_rounds") or self.session_of_rounds is None:
            return

        try:
            game_round = self.session_of_rounds.rounds[round_idx]
        except Exception:
            return

        # Update games
        for game_idx, game in enumerate(game_round.games):
            # Team A
            for col_idx, player in enumerate(game.team_A.players):
                key = (round_idx, game_idx, "A", 0, col_idx)
                btn = self.game_player_buttons.get(key)
                if btn:
                    btn.config(
                        text=f"{player.name}\n\nLvl {player.level}",
                        bg=self.colors["bg_light"],
                        relief=tk.RAISED,
                    )

            # Team B
            for col_idx, player in enumerate(game.team_B.players):
                key = (round_idx, game_idx, "B", 0, col_idx)
                btn = self.game_player_buttons.get(key)
                if btn:
                    btn.config(
                        text=f"{player.name}\n\nLvl {player.level}",
                        bg=self.colors["bg_light"],
                        relief=tk.RAISED,
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
                    btn.config(
                        text=f"{player.name}\n\nLvl {player.level}",
                        bg=self.colors["bg_light"],
                        relief=tk.RAISED,
                    )

    def refresh_all_rounds(self):
        """Refresh all stored game buttons from the session data.

        This is more robust than refreshing a single round because keys may
        not map perfectly in some edge cases; iterating stored buttons ensures
        visible labels match the underlying data model.
        """
        if not hasattr(self, "session_of_rounds") or self.session_of_rounds is None:
            return

        for key, btn in list(self.game_player_buttons.items()):
            try:
                round_idx, game_idx, team_id, row, col = key
                game_round = self.session_of_rounds.rounds[round_idx]

                if team_id == "not_playing":
                    index = row * 4 + col
                    player = game_round.not_playing[index]
                else:
                    # game_idx should be int
                    game = game_round.games[game_idx]
                    if team_id == "A":
                        player = game.team_A.players[col]
                    elif team_id == "B":
                        player = game.team_B.players[col]
                    else:
                        continue

                btn.config(
                    text=f"{player.name}\n\nLvl {player.level} ",
                    bg=self.colors["bg_light"],
                    relief=tk.RAISED,
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
            deltas[name] = new_val - base_val

        return deltas

    def _apply_happiness_preview_colors(self, round_idx):
        """Color all player buttons in round_idx based on simulated happiness delta."""
        if not hasattr(self, "game_player_buttons"):
            return

        deltas = self._preview_happiness_delta(round_idx)
        if not deltas:
            return

        game_round = self.session_of_rounds.rounds[round_idx]

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

            delta = deltas.get(player.name, 0.0)
            bg, suffix = self._delta_to_bg(delta)
            base_text = f"{player.name}\n\nLvl {player.level}"
            new_text = (
                f"{player.name}\n{suffix}\nLvl {player.level}"
                if suffix is not None
                else f"{base_text}"
            )
            try:
                btn.config(bg=bg, text=new_text)
            except Exception:
                pass

    def toggle_player_selection(self, button, player_info):
        """Toggle player selection for swapping"""
        # Check if this player is already selected
        for idx, (btn, info) in enumerate(self.selected_for_swap):
            if info["player"].name == player_info["player"].name:
                # Deselect
                btn.config(bg=self.colors["bg_light"], relief=tk.RAISED)
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
            btn1.config(bg=self.colors["bg_light"], relief=tk.RAISED)
            btn2.config(bg=self.colors["bg_light"], relief=tk.RAISED)
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
            text=f"{player2.name}\n\nLvl {player2.level}",
            bg=self.colors["bg_light"],
            relief=tk.RAISED,
        )
        btn2.config(
            text=f"{player1.name}\n\nLvl {player1.level}",
            bg=self.colors["bg_light"],
            relief=tk.RAISED,
        )

        # Update the player info references
        info1["player"] = player2
        info2["player"] = player1

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
        """Redraw the score history strip inside score_history_container."""
        if not hasattr(self, "score_history_container"):
            return
        for w in self.score_history_container.winfo_children():
            w.destroy()

        YELLOW = self.colors["accent_yellow"]
        GREEN = "#4CAF50"
        RED = "#E53935"
        GRAY = "#BBBBBB"
        BG = self.colors["bg_dark"]

        for i, score in enumerate(self.score_history):
            # Determine colour relative to previous entry
            if i == 0:
                label_text = "Initial"
                box_color = GRAY
                arrow = ""
            else:
                prev = self.score_history[i - 1]
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

            cell = tk.Frame(
                self.score_history_container, bg=box_color, relief=tk.RIDGE, bd=1
            )
            cell.pack(side=tk.LEFT, padx=3, pady=2)

            tk.Label(
                cell,
                text=label_text,
                font=(
                    self.fonts["small"][0],
                    max(7, self.fonts["small"][1] - 1),
                    "bold",
                ),
                fg=self.colors["text_dark"],
                bg=box_color,
                padx=6,
                pady=1,
            ).pack()
            tk.Label(
                cell,
                text=f"{score:.3f}",
                font=(self.fonts["small"][0], self.fonts["small"][1], "bold"),
                fg=self.colors["text_dark"],
                bg=box_color,
                padx=6,
                pady=1,
            ).pack()

            if arrow:
                tk.Label(
                    cell,
                    text=arrow,
                    font=(self.fonts["small"][0], max(7, self.fonts["small"][1] - 1)),
                    fg=self.colors["text_dark"],
                    bg=box_color,
                    padx=4,
                    pady=1,
                ).pack()

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
                _btn.config(
                    bg=self.colors["bg_light"],
                    text=f"{_player.name}\n\nLvl {_player.level}",
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
                self.score_history.append(_new_score)
            self._render_score_history()
        except Exception:
            pass

        # Regenerate plots, update XLS and PKL files if they exist
        try:
            sessions_dir = "sessions"
            if os.path.exists(sessions_dir):
                session_folders = [
                    os.path.join(sessions_dir, d)
                    for d in os.listdir(sessions_dir)
                    if os.path.isdir(os.path.join(sessions_dir, d))
                ]
                folders_with_plots = [
                    f
                    for f in session_folders
                    if os.path.exists(os.path.join(f, "plots"))
                ]
                if folders_with_plots:
                    most_recent = max(folders_with_plots, key=os.path.getmtime)
                    plots_dir = os.path.join(most_recent, "plots")
                    session_folder = most_recent

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
                            most_recent, "session_games.png"
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
                        print(
                            f"Warning: Could not update Session Games PNG: {png_error}"
                        )

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
                            date_str = folder_name.split("_")[0:3]
                            date_str = "_".join(date_str)
                            xlsx_filename = f"session_{date_str}.xlsx"

                        self.session_of_rounds.export_to_excel(
                            directory=session_folder, filename=xlsx_filename
                        )
                        print(f"Excel file updated successfully as {xlsx_filename}!")
                    except Exception as excel_error:
                        print(f"Warning: Could not update Excel file: {excel_error}")

                    # Update pickle file with new session data
                    print("\nUpdating pickle file with new data...\n")
                    try:
                        from core.pickle_helper import save_session

                        # Extract only the date part (e.g., 18_11_2025) from folder name
                        folder_name = os.path.basename(session_folder)
                        date_str = folder_name.split("_")[0:3]
                        date_str = "_".join(date_str)  # Only day_month_year

                        save_session(
                            self.session_of_rounds,
                            folder=session_folder,
                            filename=f"session_of_rounds_{date_str}_modified.pkl",
                        )
                        print("Pickle file updated successfully!")
                    except Exception as pickle_error:
                        print(f"Warning: Could not update pickle file: {pickle_error}")
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
            "• Pickle file updated",
        )

        # Re-enable the apply button
        self.apply_button.config(state=tk.NORMAL)
