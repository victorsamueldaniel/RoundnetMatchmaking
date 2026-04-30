"""Session Generation tab controller and shared UI mechanics."""

import sys
import os

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import ctypes
from ctypes import wintypes
from PIL import Image, ImageTk
import tkinter.font as tkfont

from ui.ui_helpers import (
    current_dir,
    set_window_icon_from_logo,
    ConsoleRedirector,
    ProgressDialog,
)
from ui.tab_functions import session_generation_round_type_priority

main_module = None


class SessionGenerationTabMixin:
    def __init__(self, root):
        self.root = root
        self.root.title("Roundnet Matchmaking - Player Selection")
        self._app_icon_photo = set_window_icon_from_logo(self.root)

        # Make window full screen by default (maximized)
        self.root.state("zoomed")

        # Color palette
        self.colors = {
            "bg_dark": "#2E2E2E",  # Dark grey background
            "bg_light": "#FFFFFF",  # White
            "accent_red": "#7F0301",  # Burgundy
            "accent_yellow": "#FED403",  # Yellow
            "text_dark": "#000000",  # Black
            "text_light": "#FFFFFF",  # White
        }

        # Screen size and scale factor (use 1080p as baseline)
        self.screen_w, self.screen_h = self._get_current_monitor_size()
        self.scale = max(0.6, self.screen_h / 1080.0)
        self._base_scale = self.scale
        self._last_monitor_signature = (
            self.screen_w,
            self.screen_h,
            round(self.scale, 3),
        )
        self._layout_refresh_after_id = None
        self._player_button_fit_after_id = None
        self._widget_base_fonts = {}

        self._base_font_sizes = {
            "small": 13,
            "small_bold": 13,
            "normal": 16,
            "normal_bold": 16,
            "big": 20,
            "huge": 32,
        }
        self._rebuild_fonts_from_scale()

        # Configure root background
        self.root.configure(bg=self.colors["bg_dark"])

        # Load main dataframe
        self.main_df = main_module.main_df.copy()
        self.selected_players = []
        self.player_overrides = {}
        self.preferred_pairs = []  # list of (frozenset({name1, name2}), forced_games)
        self._tooltip_window = None
        self._tooltip_after_id = None
        self._tooltip_delay_ms = 500

        # Create main frame with dark background
        main_frame = tk.Frame(root, bg=self.colors["bg_dark"])
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Create main notebook (tabbed interface) for all content
        # Configure style for tabs
        self.style = ttk.Style()
        self.style.theme_use("default")
        self.style.configure(
            "TNotebook.Tab",
            background=self.colors["accent_red"],
            foreground=self.colors["text_light"],
            padding=[20, 10],
            font=self.fonts["normal_bold"],
        )
        self.style.map(
            "TNotebook.Tab",
            background=[("selected", self.colors["accent_yellow"])],
            foreground=[("selected", self.colors["text_dark"])],
        )

        self.main_notebook = ttk.Notebook(main_frame)
        self.main_notebook.pack(fill=tk.BOTH, expand=True)

        # Create "Session Generation" tab
        session_tab = tk.Frame(self.main_notebook, bg=self.colors["bg_dark"])
        self.main_notebook.add(session_tab, text="Session Generation")
        self.session_tab = session_tab

        # Header frame with logo and title (inside session tab)
        header_frame = tk.Frame(session_tab, bg=self.colors["bg_dark"])
        header_frame.pack(side=tk.TOP, pady=(10, 10))

        # Container to center logo and title together
        title_container = tk.Frame(header_frame, bg=self.colors["bg_dark"])
        title_container.pack()

        # Load and display logo
        try:
            logo_path = os.path.join(current_dir, "ui", "logo.png")
            logo_image = Image.open(logo_path)
            # Resize logo relative to screen scale
            logo_size = max(40, int(80 * getattr(self, "scale", 1.0)))
            logo_image = logo_image.resize(
                (logo_size, logo_size), Image.Resampling.LANCZOS
            )
            self.logo_photo = ImageTk.PhotoImage(logo_image)
            logo_label = tk.Label(
                title_container, image=self.logo_photo, bg=self.colors["bg_dark"]
            )
            logo_label.pack(side=tk.LEFT, padx=(0, 15))
        except Exception as e:
            print(f"Could not load logo: {e}")

        # Title with yellow accent
        title_label = tk.Label(
            title_container,
            text="ROUNDNET MATCHMAKING",
            font=self.fonts["huge"],
            fg=self.colors["accent_yellow"],
            bg=self.colors["bg_dark"],
        )
        title_label.pack(side=tk.LEFT)

        # Player count label with white text
        self.count_label = tk.Label(
            session_tab,
            text="Selected: 0 players",
            font=self.fonts["normal_bold"],
            fg=self.colors["text_light"],
            bg=self.colors["bg_dark"],
        )
        self.count_label.pack(
            side=tk.TOP, fill=tk.X, pady=(0, 10), padx=20, anchor=tk.W
        )

        # Buttons frame (part of session tab) - placed before the main paned area
        button_frame = tk.Frame(session_tab, bg=self.colors["bg_dark"])
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=15, padx=20)
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(5, weight=1)

        # Custom button style
        btn_config = {
            "font": self.fonts["normal_bold"],
            "relief": tk.FLAT,
            "cursor": "hand2",
            "padx": 20,
            "pady": 10,
        }

        # Preferred Pairs button — leftmost
        self.pairs_btn = tk.Button(
            button_frame,
            text="\U0001f465 Preferred Pairs",
            command=self.show_preferred_pairs_dialog,
            bg=self.colors["accent_red"],
            fg=self.colors["text_light"],
            font=self.fonts["normal_bold"],
            relief=tk.FLAT,
            cursor="hand2",
            padx=20,
            pady=10,
        )
        self.pairs_btn.grid(row=0, column=1, padx=5)

        # Select All button
        self.select_all_btn = tk.Button(
            button_frame,
            text="Select All",
            command=self.select_all,
            bg=self.colors["bg_light"],
            fg=self.colors["text_dark"],
            **btn_config,
        )
        self.select_all_btn.grid(row=0, column=2, padx=5)

        # Clear Selection button
        self.clear_btn = tk.Button(
            button_frame,
            text="Clear Selection",
            command=self.clear_selection,
            bg=self.colors["bg_light"],
            fg=self.colors["text_dark"],
            **btn_config,
        )
        self.clear_btn.grid(row=0, column=3, padx=5)

        # Run Session button - highlighted with yellow
        self.run_btn = tk.Button(
            button_frame,
            text="⚡ RUN SESSION GENERATION ⚡",
            command=self.run_session,
            bg=self.colors["accent_yellow"],
            fg=self.colors["text_dark"],
            font=self.fonts["big"],
            relief=tk.FLAT,
            cursor="hand2",
            padx=25,
            pady=12,
        )
        self.run_btn.grid(row=0, column=4, padx=10)

        # Create vertical PanedWindow to separate main content from preferences
        vertical_paned = tk.PanedWindow(
            session_tab,
            orient=tk.VERTICAL,
            sashwidth=8,
            sashrelief=tk.RAISED,
            bg=self.colors["bg_dark"],
            bd=0,
        )
        vertical_paned.pack(
            side=tk.TOP, fill=tk.BOTH, expand=True, padx=20, pady=(0, 20)
        )

        # Store reference for dynamic resizing
        self.vertical_paned = vertical_paned

        # Create horizontal PanedWindow for resizable panels (top section)
        paned_window = tk.PanedWindow(
            vertical_paned,
            orient=tk.HORIZONTAL,
            sashwidth=8,
            sashrelief=tk.RAISED,
            bg=self.colors["bg_dark"],
            bd=0,
        )
        # Set default height relative to screen height
        top_pane_height = int(self.screen_h * 0.53)
        paned_window.config(height=top_pane_height)
        vertical_paned.add(paned_window, stretch="always")

        # Store reference for configuration
        self.paned_window = paned_window

        # Create frame for player buttons with burgundy border
        list_frame = self._make_label_frame(paned_window, "Available Players")
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)
        paned_window.add(list_frame, stretch="always")

        # Store reference for configuration
        self.list_frame = list_frame

        # Create canvas and scrollbar for player buttons
        canvas = tk.Canvas(list_frame, bg=self.colors["bg_light"], highlightthickness=0)
        scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=self.colors["bg_light"])

        # Keep references for later use
        self.player_canvas = canvas
        self.player_scrollable_frame = scrollable_frame

        # Initialize current mousewheel target (used by Games Editor)
        self._mousewheel_target_canvas = None

        # Update scrollregion when the internal frame changes
        scrollable_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        # Create the window with a tag so we can reliably update its width
        canvas.create_window(
            (0, 0), window=scrollable_frame, anchor="nw", tags=("player_window",)
        )
        canvas.configure(yscrollcommand=scrollbar.set)

        # Bind canvas resize to update scrollable_frame width using the tag
        def on_canvas_configure(event):
            try:
                canvas.itemconfig("player_window", width=event.width)
            except Exception:
                pass
            self._schedule_player_button_font_fit()

        canvas.bind("<Configure>", on_canvas_configure)

        # Mouse wheel handled globally to allow multiple scrollable areas

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Store player buttons
        self.player_buttons = {}
        self.player_button_states = {}  # Track selected state

        # Create player buttons in 6 columns, sorted alphabetically horizontally
        sorted_players = sorted(self.main_df.index)
        num_columns = 6

        for idx, player_name in enumerate(sorted_players):
            row = idx // num_columns
            col = idx % num_columns

            btn = tk.Button(
                scrollable_frame,
                text=self.format_player_button_text(player_name),
                font=self.player_button_font,
                bg=self.colors["bg_light"],
                fg=self.colors["text_dark"],
                relief=tk.RAISED,
                bd=2,
                cursor="hand2",
                padx=self.player_button_padx,
                pady=self.player_button_pady,
                anchor="center",
                command=lambda name=player_name: self.toggle_player(name),
            )
            btn.grid(row=row, column=col, padx=2, pady=2, sticky=(tk.W, tk.E))
            btn.bind(
                "<Button-3>",
                lambda event, name=player_name: self.show_edit_player_dialog(name),
            )
            self.bind_tooltip(btn, "right click to change specs")

            self.player_buttons[player_name] = btn
            self.player_button_states[player_name] = False

        # Add "+ Add Player" button at the end of the list
        total_players = len(sorted_players)
        add_row = total_players // num_columns
        add_col = total_players % num_columns

        add_player_btn = tk.Button(
            scrollable_frame,
            text="+ Add Player",
            font=self.player_button_font,
            bg=self.colors["accent_red"],
            fg=self.colors["text_light"],
            relief=tk.RAISED,
            bd=2,
            cursor="hand2",
            padx=self.player_button_padx,
            pady=self.player_button_pady,
            anchor="center",
            command=self.show_add_player_dialog,
        )
        add_player_btn.grid(
            row=add_row, column=add_col, padx=2, pady=2, sticky=(tk.W, tk.E)
        )
        self.add_player_btn = add_player_btn

        # Configure column weights for equal distribution
        for col in range(num_columns):
            scrollable_frame.columnconfigure(col, weight=1)

        # Let tkinter process pending events so the splash bar keeps animating
        self.root.update_idletasks()

        # Create frame for selected players info
        info_frame = self._make_label_frame(paned_window, "Selected Players Info")
        info_frame.rowconfigure(0, weight=1)
        info_frame.columnconfigure(0, weight=1)
        paned_window.add(info_frame, stretch="always")

        # Store reference for configuration
        self.info_frame = info_frame

        self.info_text = scrolledtext.ScrolledText(
            info_frame,
            width=40,
            font=self.fonts["small"],
            bg=self.colors["bg_light"],
            fg=self.colors["text_dark"],
            highlightthickness=0,
            wrap=tk.WORD,
        )
        self.info_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create console output frame on the right
        console_frame = self._make_label_frame(paned_window, "Console Output")
        console_frame.rowconfigure(0, weight=1)
        console_frame.columnconfigure(0, weight=1)
        paned_window.add(console_frame, stretch="always")

        # Store reference for configuration
        self.console_frame = console_frame

        self.console_text = scrolledtext.ScrolledText(
            console_frame,
            width=50,
            font=("Consolas", 9),
            bg="#1E1E1E",
            fg="#D4D4D4",
            highlightthickness=0,
            wrap=tk.WORD,
        )
        self.console_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.console_text.insert("1.0", "Console output will appear here...\n")
        self.console_text.config(state=tk.DISABLED)

        # Redirect stdout to console immediately and permanently
        self.original_stdout = sys.stdout
        sys.stdout = ConsoleRedirector(self.console_text)

        # Create frame for round preferences (bottom section of vertical paned window)
        prefs_frame = self._make_label_frame(vertical_paned, "Round Preferences")
        vertical_paned.add(prefs_frame, stretch="never")
        prefs_frame.rowconfigure(0, weight=1)
        prefs_frame.columnconfigure(0, weight=3)
        prefs_frame.columnconfigure(1, weight=2)

        # Store reference for dynamic resizing
        self.prefs_frame = prefs_frame
        self.prefs_default_height = int(
            self.screen_h * 0.27
        )  # Store default height (scaled)

        # Create left panel for round preferences list
        rounds_panel = tk.Frame(prefs_frame, bg=self.colors["bg_light"])
        rounds_panel.grid(
            row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(10, 6), pady=10
        )
        rounds_panel.rowconfigure(0, weight=1)
        rounds_panel.columnconfigure(0, weight=1)

        # Create right panel for parameters
        parameters_panel = tk.LabelFrame(
            prefs_frame,
            text="parameters",
            font=self.fonts["normal_bold"],
            bg=self.colors["bg_light"],
            fg=self.colors["accent_red"],
            bd=2,
            relief=tk.RIDGE,
            padx=10,
            pady=10,
        )
        parameters_panel.grid(
            row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(6, 10), pady=10
        )
        parameters_panel.rowconfigure(0, weight=1)
        parameters_panel.columnconfigure(0, weight=1)

        # Make parameters area scrollable vertically
        params_canvas = tk.Canvas(
            parameters_panel, bg=self.colors["bg_light"], highlightthickness=0
        )
        params_scrollbar = tk.Scrollbar(
            parameters_panel, orient="vertical", command=params_canvas.yview
        )
        params_scrollable_frame = tk.Frame(params_canvas, bg=self.colors["bg_light"])

        params_scrollable_frame.bind(
            "<Configure>",
            lambda e: params_canvas.configure(scrollregion=params_canvas.bbox("all")),
        )

        params_canvas.create_window(
            (0, 0),
            window=params_scrollable_frame,
            anchor="nw",
            width=params_canvas.winfo_width(),
            tags=("params_window",),
        )
        params_canvas.configure(yscrollcommand=params_scrollbar.set)

        def on_params_canvas_configure(event):
            try:
                params_canvas.itemconfig("params_window", width=event.width)
            except Exception:
                pass

        params_canvas.bind("<Configure>", on_params_canvas_configure)

        # Store references for global mousewheel dispatcher
        self.params_canvas = params_canvas
        self.params_scrollable_frame = params_scrollable_frame

        params_canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        params_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        params_grid = tk.Frame(params_scrollable_frame, bg=self.colors["bg_light"])
        params_grid.pack(fill=tk.BOTH, expand=True)
        params_grid.columnconfigure(0, weight=1)
        params_grid.columnconfigure(1, weight=1)

        # Create canvas and scrollbar for round preferences
        rounds_canvas = tk.Canvas(
            rounds_panel, bg=self.colors["bg_light"], highlightthickness=0
        )
        rounds_scrollbar = tk.Scrollbar(
            rounds_panel, orient="vertical", command=rounds_canvas.yview
        )
        rounds_scrollable_frame = tk.Frame(rounds_canvas, bg=self.colors["bg_light"])

        rounds_scrollable_frame.bind(
            "<Configure>",
            lambda e: rounds_canvas.configure(scrollregion=rounds_canvas.bbox("all")),
        )

        rounds_canvas.create_window(
            (0, 0),
            window=rounds_scrollable_frame,
            anchor="nw",
            width=rounds_canvas.winfo_width(),
        )
        rounds_canvas.configure(yscrollcommand=rounds_scrollbar.set)

        # Bind canvas resize to update scrollable_frame width
        def on_rounds_canvas_configure(event):
            rounds_canvas.itemconfig(
                rounds_canvas.find_withtag("all")[0], width=event.width
            )

        rounds_canvas.bind("<Configure>", on_rounds_canvas_configure)

        # Store references for global mousewheel dispatcher
        self.rounds_canvas = rounds_canvas
        self.rounds_scrollable_frame = rounds_scrollable_frame

        rounds_canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        rounds_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        # Container for round preferences (will be dynamically populated)
        self.rounds_container = tk.Frame(
            rounds_scrollable_frame, bg=self.colors["bg_light"]
        )
        self.rounds_container.grid(
            row=0, column=0, columnspan=5, sticky=(tk.W, tk.E), padx=10, pady=10
        )

        # Create initial round preferences
        self.type_prefs = []
        self.gender_prefs = []
        self.round_frames = []
        self.type_buttons_list = []  # Store type button references
        self.gender_buttons_list = []  # Store gender button references

        self.num_rounds_var = tk.IntVar(value=4)

        self.create_round_preferences()
        self.root.update_idletasks()

        # Number of rounds control
        rounds_control_frame = tk.Frame(
            rounds_scrollable_frame, bg=self.colors["bg_light"]
        )
        rounds_control_frame.grid(
            row=1, column=0, columnspan=5, pady=(10, 10), sticky=tk.W, padx=10
        )

        tk.Label(
            rounds_control_frame,
            text="Number of Rounds:",
            font=self.fonts["normal_bold"],
            bg=self.colors["bg_light"],
            fg=self.colors["text_dark"],
        ).pack(side=tk.LEFT, padx=5)

        # Custom styled buttons for rounds
        minus_btn = tk.Button(
            rounds_control_frame,
            text="-",
            width=3,
            command=self.decrease_rounds,
            bg=self.colors["accent_red"],
            fg=self.colors["text_light"],
            font=self.fonts["normal_bold"],
            relief=tk.FLAT,
            cursor="hand2",
        )
        minus_btn.pack(side=tk.LEFT, padx=2)

        self.rounds_label = tk.Label(
            rounds_control_frame,
            text="4",
            font=self.fonts["big"],
            width=3,
            bg=self.colors["accent_yellow"],
            fg=self.colors["text_dark"],
        )
        self.rounds_label.pack(side=tk.LEFT, padx=5)

        plus_btn = tk.Button(
            rounds_control_frame,
            text="+",
            width=3,
            command=self.increase_rounds,
            bg=self.colors["accent_red"],
            fg=self.colors["text_light"],
            font=self.fonts["normal_bold"],
            relief=tk.FLAT,
            cursor="hand2",
        )
        plus_btn.pack(side=tk.LEFT, padx=2)

        # Games per round control
        games_control_frame = tk.Frame(
            rounds_scrollable_frame, bg=self.colors["bg_light"]
        )
        games_control_frame.grid(
            row=2, column=0, columnspan=5, pady=(10, 10), sticky=tk.W, padx=10
        )

        tk.Label(
            games_control_frame,
            text="Games per Round:",
            font=self.fonts["normal_bold"],
            bg=self.colors["bg_light"],
            fg=self.colors["text_dark"],
        ).pack(side=tk.LEFT, padx=5)

        # Create radio buttons for games per round
        self.games_per_round_var = tk.StringVar(value="auto")

        games_options_frame = tk.Frame(games_control_frame, bg=self.colors["bg_light"])
        games_options_frame.pack(side=tk.LEFT, padx=5)

        # Auto option (default: players/4)
        tk.Radiobutton(
            games_options_frame,
            text="Auto",
            variable=self.games_per_round_var,
            value="auto",
            bg=self.colors["bg_light"],
            fg=self.colors["text_dark"],
            selectcolor=self.colors["accent_yellow"],
            font=self.fonts["normal"],
            cursor="hand2",
        ).pack(side=tk.LEFT, padx=5)

        # Specific number options (1-5 games)
        for num_games in range(1, 9):
            tk.Radiobutton(
                games_options_frame,
                text=str(num_games),
                variable=self.games_per_round_var,
                value=str(num_games),
                bg=self.colors["bg_light"],
                fg=self.colors["text_dark"],
                selectcolor=self.colors["accent_yellow"],
                font=self.fonts["normal"],
                cursor="hand2",
            ).pack(side=tk.LEFT, padx=3)

        # Parameter sliders
        self._make_param_slider(
            params_grid,
            0,
            1,
            "Shift female levels",
            "Temporary shifter applied to female players' level before matchmaking.",
            "female_boost_var",
            "female_boost_scale",
            -2.0,
            2.0,
            0.1,
            0.0,
        )
        self._make_param_slider(
            params_grid,
            2,
            0,
            "maximal level gap in game",
            "Maximum allowed level difference considered acceptable inside a game.",
            "level_gap_tol_var",
            "level_gap_tol_scale",
            0.5,
            3.0,
            0.1,
            1.1,
        )
        self._make_param_slider(
            params_grid,
            0,
            0,
            "extra factor for bottom 33%",
            "Higher values prioritize increasing the happiness of the bottom x% of players.",
            "lambda_weight_var",
            "lambda_weight_scale",
            0.0,
            10,
            0.1,
            2,
            label_attr="lambda_weight_label",
        )
        self._make_param_slider(
            params_grid,
            1,
            0,
            "bottom x% size",
            "Percentile threshold x used to define the bottom x% of players by happiness.",
            "percentile_var",
            "percentile_scale",
            0,
            50,
            1,
            33,
        )

        # Keep "factor for bottom x%" label in sync with the percentile slider
        def _update_lambda_label(*_):
            try:
                x = int(self.percentile_var.get())
                self.lambda_weight_label.config(text=f"factor for bottom {x}%")
            except Exception:
                pass

        self.percentile_var.trace_add("write", _update_lambda_label)

        # Spectrum toggle parameter
        spectrum_control_frame = tk.Frame(
            params_grid, bg="#dddddd", bd=2, relief=tk.RIDGE
        )
        spectrum_control_frame.grid(
            row=1, column=1, rowspan=3, sticky=(tk.W, tk.E, tk.N), padx=4, pady=4
        )

        spectrum_row = tk.Frame(spectrum_control_frame, bg="#dddddd")
        spectrum_row.pack(fill=tk.X, padx=5, pady=4)

        spectrum_label = tk.Label(
            spectrum_row,
            text="Spectrum",
            font=self.fonts["small_bold"],
            bg="#dddddd",
            fg=self.colors["text_dark"],
        )
        spectrum_label.pack(side=tk.LEFT)
        self.bind_tooltip(
            spectrum_label,
            "Enable or disable spectrum preferences during matchup generation.",
        )

        self.spectrum_var = tk.BooleanVar(value=True)
        spectrum_buttons_frame = tk.Frame(spectrum_row, bg="#dddddd")
        spectrum_buttons_frame.pack(side=tk.RIGHT)

        spectrum_on_btn = tk.Button(
            spectrum_buttons_frame,
            text="ON",
            font=self.fonts["small"],
            width=6,
            cursor="hand2",
            padx=5,
            pady=0,
            command=lambda: self.set_spectrum_state(True),
        )
        spectrum_on_btn.pack(side=tk.LEFT, padx=2)

        spectrum_off_btn = tk.Button(
            spectrum_buttons_frame,
            text="OFF",
            font=self.fonts["small"],
            width=6,
            cursor="hand2",
            padx=5,
            pady=0,
            command=lambda: self.set_spectrum_state(False),
        )
        spectrum_off_btn.pack(side=tk.LEFT, padx=2)

        self.spectrum_buttons = {"on": spectrum_on_btn, "off": spectrum_off_btn}
        self.update_spectrum_switch_display()

        # PNG levels toggle
        levels_row = tk.Frame(spectrum_control_frame, bg="#dddddd")
        levels_row.pack(fill=tk.X, padx=5, pady=(0, 4))
        levels_label = tk.Label(
            levels_row,
            text="Show levels in session PNG",
            font=self.fonts["small_bold"],
            bg="#dddddd",
            fg=self.colors["text_dark"],
        )
        levels_label.pack(side=tk.LEFT)
        self.bind_tooltip(
            levels_label,
            "Show each player's level next to their name in the Session Games PNG.",
        )
        self.png_show_levels_var = tk.BooleanVar(value=False)
        levels_btn_frame = tk.Frame(levels_row, bg="#dddddd")
        levels_btn_frame.pack(side=tk.RIGHT)
        levels_on_btn = tk.Button(
            levels_btn_frame,
            text="ON",
            font=self.fonts["small"],
            width=6,
            cursor="hand2",
            padx=5,
            pady=0,
            command=lambda: self._set_png_levels_state(True),
        )
        levels_on_btn.pack(side=tk.LEFT, padx=2)
        levels_off_btn = tk.Button(
            levels_btn_frame,
            text="OFF",
            font=self.fonts["small"],
            width=6,
            cursor="hand2",
            padx=5,
            pady=0,
            command=lambda: self._set_png_levels_state(False),
        )
        levels_off_btn.pack(side=tk.LEFT, padx=2)
        self._png_levels_buttons = {"on": levels_on_btn, "off": levels_off_btn}
        self._set_png_levels_state(False)  # initialise display

        # Configure grid weights
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.columnconfigure(2, weight=1)
        main_frame.rowconfigure(1, weight=1)

        # Configure grid weights
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.columnconfigure(2, weight=1)
        main_frame.rowconfigure(1, weight=1)

        # Configure default pane sizes relative to screen
        list_w = int(self.screen_w * 0.5)
        info_w = int(self.screen_w * 0.22)
        console_w = int(self.screen_w * 0.28)

        self.paned_window.paneconfigure(self.list_frame, width=list_w)
        self.paned_window.paneconfigure(self.info_frame, width=info_w)
        self.paned_window.paneconfigure(self.console_frame, width=console_w)

        # Vertical panes: use top_pane_height computed earlier and scaled prefs height
        prefs_height = int(self.screen_h * 0.27)
        self.vertical_paned.paneconfigure(self.paned_window, height=top_pane_height)
        self.vertical_paned.paneconfigure(self.prefs_frame, height=prefs_height)

        # Global mousewheel handler to dispatch scroll events to the widget under cursor
        def _can_scroll(cnv):
            try:
                bbox = cnv.bbox("all")
                if not bbox:
                    return False
                content_h = bbox[3] - bbox[1]
                visible_h = cnv.winfo_height()
                return content_h > visible_h
            except Exception:
                return True

        def _wheel_units(event):
            delta = getattr(event, "delta", 0)
            if delta == 0:
                return 0
            if abs(delta) < 120:
                return -1 if delta > 0 else 1
            return int(-1 * (delta / 120))

        def _on_global_mousewheel(event):
            try:
                # If a target canvas is explicitly set by hover, prefer it
                target = getattr(self, "_mousewheel_target_canvas", None)
                if target is not None:
                    try:
                        units = _wheel_units(event)
                        if _can_scroll(target):
                            target.yview_scroll(units, "units")
                        return "break"
                    except Exception:
                        return

                # Fallback: find widget under pointer and dispatch
                x_root = self.root.winfo_pointerx()
                y_root = self.root.winfo_pointery()
                widget = self.root.winfo_containing(x_root, y_root)

                # Helper to check ancestry
                def is_descendant(w, ancestor):
                    while w is not None:
                        if w == ancestor:
                            return True
                        w = getattr(w, "master", None)
                    return False

                # Dispatch to player canvas if pointer is inside its scrollable frame
                if (
                    hasattr(self, "player_scrollable_frame")
                    and widget is not None
                    and is_descendant(widget, self.player_scrollable_frame)
                ):
                    try:
                        units = _wheel_units(event)
                        if _can_scroll(self.player_canvas):
                            self.player_canvas.yview_scroll(units, "units")
                        return "break"
                    except Exception:
                        pass

                # Dispatch to rounds canvas if pointer is inside its scrollable frame
                if (
                    hasattr(self, "rounds_scrollable_frame")
                    and widget is not None
                    and is_descendant(widget, self.rounds_scrollable_frame)
                ):
                    try:
                        units = _wheel_units(event)
                        if _can_scroll(self.rounds_canvas):
                            self.rounds_canvas.yview_scroll(units, "units")
                        return "break"
                    except Exception:
                        pass

                # Dispatch to parameters canvas if pointer is inside its scrollable frame
                if (
                    hasattr(self, "params_scrollable_frame")
                    and widget is not None
                    and is_descendant(widget, self.params_scrollable_frame)
                ):
                    try:
                        units = _wheel_units(event)
                        if _can_scroll(self.params_canvas):
                            self.params_canvas.yview_scroll(units, "units")
                        return "break"
                    except Exception:
                        pass
            except Exception:
                pass

        # Bind the global mousewheel dispatcher
        try:
            self.root.bind_all("<MouseWheel>", _on_global_mousewheel)
        except Exception:
            pass

        # Monitor-aware responsive refresh (handles moving window between screens)
        self.root.bind("<Configure>", self._on_root_configure)
        self.root.after(150, lambda: self.refresh_layout_for_current_screen(force=True))
        # Second pass after the window manager has fully settled the maximized layout
        self.root.after(800, self._schedule_player_button_font_fit)

    def _make_label_frame(self, parent, title, bd=3):
        """Return a styled LabelFrame with the app's standard look."""
        return tk.LabelFrame(
            parent,
            text=title,
            font=self.fonts["normal_bold"],
            bg=self.colors["bg_light"],
            fg=self.colors["accent_red"],
            bd=bd,
            relief=tk.RIDGE,
        )

    def _make_param_slider(
        self,
        parent,
        grid_row,
        grid_col,
        label_text,
        tooltip_text,
        var_attr,
        scale_attr,
        from_,
        to_,
        resolution,
        initial_value,
        label_attr=None,
    ):
        """Create a ridged labeled Scale, assigning self.{var_attr} and self.{scale_attr}."""
        ctrl_frame = tk.Frame(parent, bg="#dddddd", bd=2, relief=tk.RIDGE)
        ctrl_frame.grid(
            row=grid_row, column=grid_col, sticky=(tk.W, tk.E), padx=4, pady=4
        )
        row_frame = tk.Frame(ctrl_frame, bg="#dddddd")
        row_frame.pack(fill=tk.X, padx=5, pady=4)
        label = tk.Label(
            row_frame,
            text=label_text,
            font=self.fonts["small_bold"],
            bg="#dddddd",
            fg=self.colors["text_dark"],
        )
        label.pack(side=tk.LEFT)
        if label_attr is not None:
            setattr(self, label_attr, label)
        self.bind_tooltip(label, tooltip_text)
        var = tk.DoubleVar(value=initial_value)
        setattr(self, var_attr, var)
        scale = tk.Scale(
            row_frame,
            from_=from_,
            to=to_,
            resolution=resolution,
            orient=tk.HORIZONTAL,
            variable=var,
            showvalue=True,
            length=max(100, int(120 * self.scale)),
            font=self.fonts["normal"],
            bg="#dddddd",
            fg=self.colors["text_dark"],
            highlightthickness=0,
            troughcolor=self.colors["bg_light"],
            activebackground=self.colors["accent_yellow"],
            cursor="hand2",
        )
        scale.pack(side=tk.RIGHT)
        setattr(self, scale_attr, scale)

    def _make_toggle_group(self, parent, bg_color, label_text, options, var):
        """Create a ridged section with toggle buttons for a StringVar.

        Returns (section_frame, buttons_dict).
        """
        section = tk.Frame(parent, bg=bg_color, relief=tk.RIDGE, bd=2)
        tk.Label(
            section,
            text=label_text,
            font=self.fonts["small_bold"],
            bg=bg_color,
            fg=self.colors["text_dark"],
        ).pack(side=tk.LEFT, padx=(5, 5))
        btn_frame = tk.Frame(section, bg=bg_color)
        btn_frame.pack(side=tk.LEFT, padx=(0, 5), pady=1)

        buttons = {}
        for option in options:
            btn = tk.Button(
                btn_frame,
                text=option.capitalize(),
                font=self.fonts["small"],
                width=8,
                cursor="hand2",
                padx=5,
                pady=0,
            )
            btn.pack(side=tk.LEFT, padx=2)
            buttons[option] = btn

        def make_toggle(opt, btns_ref):
            def toggle():
                var.set(opt)
                for o, b in btns_ref.items():
                    if o == opt:
                        b.config(
                            bg=self.colors["accent_yellow"],
                            fg=self.colors["text_dark"],
                            relief=tk.SUNKEN,
                        )
                    else:
                        b.config(
                            bg=self.colors["bg_light"],
                            fg=self.colors["text_dark"],
                            relief=tk.RAISED,
                        )

            return toggle

        for option, btn in buttons.items():
            btn.config(command=make_toggle(option, buttons))

        for option, btn in buttons.items():
            if option == var.get():
                btn.config(
                    bg=self.colors["accent_yellow"],
                    fg=self.colors["text_dark"],
                    relief=tk.SUNKEN,
                )
            else:
                btn.config(
                    bg=self.colors["bg_light"],
                    fg=self.colors["text_dark"],
                    relief=tk.RAISED,
                )

        return section, buttons

    def _scaled_font_tuple(self, font_tuple, factor: float):
        """Create a scaled font tuple from an existing font tuple."""
        name = font_tuple[0]
        size = font_tuple[1] if len(font_tuple) > 1 else 12
        extras = font_tuple[2:] if len(font_tuple) > 2 else ()
        return (name, max(8, int(size * factor)), *extras)

    def _rebuild_fonts_from_scale(self):
        """Rebuild standard UI fonts from current scale."""

        def s(sz):
            return max(8, int(sz * self.scale))

        self.fonts = {
            "small": ("Arial", s(self._base_font_sizes["small"])),
            "small_bold": ("Arial", s(self._base_font_sizes["small_bold"]), "bold"),
            "normal": ("Arial", s(self._base_font_sizes["normal"])),
            "normal_bold": (
                "Arial",
                s(self._base_font_sizes["normal_bold"]),
                "bold",
            ),
            "big": ("Arial", s(self._base_font_sizes["big"]), "bold"),
            "huge": ("Arial", s(self._base_font_sizes["huge"]), "bold"),
        }

        # Slightly larger player selection button font and padding (~108%)
        self.player_button_font = self._scaled_font_tuple(
            self.fonts["normal_bold"], 1.08
        )
        self.player_button_padx = max(2, int(5 * 1.08 * self.scale))
        self.player_button_pady = max(2, int(5 * 1.08 * self.scale))

    def _get_current_monitor_size(self):
        """Return width/height of monitor containing the root window (with fallback)."""
        try:
            user32 = ctypes.windll.user32

            class MONITORINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.DWORD),
                    ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT),
                    ("dwFlags", wintypes.DWORD),
                ]

            MONITOR_DEFAULTTONEAREST = 2
            hwnd = self.root.winfo_id()
            monitor = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
            if monitor:
                monitor_info = MONITORINFO()
                monitor_info.cbSize = ctypes.sizeof(MONITORINFO)
                if user32.GetMonitorInfoW(monitor, ctypes.byref(monitor_info)):
                    rect = monitor_info.rcMonitor
                    width = max(1, rect.right - rect.left)
                    height = max(1, rect.bottom - rect.top)
                    return width, height
        except Exception:
            pass

        return self.root.winfo_screenwidth(), self.root.winfo_screenheight()

    def _on_root_configure(self, event=None):
        """Throttle resize/monitor-change refreshes."""
        if self._layout_refresh_after_id is not None:
            try:
                self.root.after_cancel(self._layout_refresh_after_id)
            except Exception:
                pass

        self._layout_refresh_after_id = self.root.after(
            120, self.refresh_layout_for_current_screen
        )
        # Always re-fit button fonts on any window geometry change (e.g. maximize/restore)
        self._schedule_player_button_font_fit()

    def _apply_scaled_fonts_to_widget_tree(self):
        """Apply scaled fonts to current widget tree while preserving font family/style."""
        scale_ratio = self.scale / self._base_scale if self._base_scale else 1.0

        # Nothing to rescale if ratio is 1 — skip the expensive tree walk
        if abs(scale_ratio - 1.0) < 0.001:
            return

        def walk(widget):
            try:
                for child in widget.winfo_children():
                    walk(child)
            except Exception:
                return

            widget_id = str(widget)
            try:
                current_font = widget.cget("font")
            except Exception:
                return

            if not current_font:
                return

            if widget_id not in self._widget_base_fonts:
                try:
                    f = tkfont.Font(font=current_font)
                    actual = f.actual()
                    self._widget_base_fonts[widget_id] = {
                        "family": actual.get("family", "Arial"),
                        "size": max(1, abs(int(actual.get("size", 10)))),
                        "weight": actual.get("weight", "normal"),
                        "slant": actual.get("slant", "roman"),
                        "underline": int(actual.get("underline", 0)),
                        "overstrike": int(actual.get("overstrike", 0)),
                    }
                except Exception:
                    return

            base = self._widget_base_fonts.get(widget_id)
            if not base:
                return

            new_size = max(8, int(base["size"] * scale_ratio))
            try:
                style_tokens = []
                if base["weight"] == "bold":
                    style_tokens.append("bold")
                if base["slant"] == "italic":
                    style_tokens.append("italic")
                if base["underline"]:
                    style_tokens.append("underline")
                if base["overstrike"]:
                    style_tokens.append("overstrike")

                style_suffix = " ".join(style_tokens)
                if style_suffix:
                    widget.configure(font=(base["family"], new_size, style_suffix))
                else:
                    widget.configure(font=(base["family"], new_size))
            except Exception:
                pass

        walk(self.root)

    def _schedule_player_button_font_fit(self):
        """Throttle auto-fit of player button text to button width."""
        if self._player_button_fit_after_id is not None:
            try:
                self.root.after_cancel(self._player_button_fit_after_id)
            except Exception:
                pass

        self._player_button_fit_after_id = self.root.after(
            50, self._fit_player_button_fonts
        )

    def _fit_player_button_fonts(self):
        """Set one shared font size for all player buttons based on longest label."""
        self._player_button_fit_after_id = None

        if not hasattr(self, "player_buttons"):
            return

        try:
            base_family = self.player_button_font[0]
            base_size = int(self.player_button_font[1])
            base_style = (
                self.player_button_font[2:] if len(self.player_button_font) > 2 else ()
            )
        except Exception:
            base_family = "Arial"
            base_size = 12
            base_style = ("bold",)

        min_size = 7

        all_buttons = []
        all_labels = []

        for player_name, button in self.player_buttons.items():
            all_buttons.append(button)
            all_labels.append(self.format_player_button_text(player_name))

        if hasattr(self, "add_player_btn") and self.add_player_btn is not None:
            all_buttons.append(self.add_player_btn)
            all_labels.append("+ Add Player")

        if not all_buttons:
            return

        longest_label = max(all_labels, key=lambda x: len(str(x)))

        available_widths = []
        for button in all_buttons:
            try:
                width_px = int(button.winfo_width())
                pad_x = int(button.cget("padx"))
                if width_px > 1:
                    available_widths.append(max(20, width_px - (2 * pad_x) - 10))
            except Exception:
                continue

        if not available_widths:
            # Geometry not ready yet — flush pending layout and retry once.
            self.root.update_idletasks()
            for button in all_buttons:
                try:
                    width_px = int(button.winfo_width())
                    pad_x = int(button.cget("padx"))
                    if width_px > 1:
                        available_widths.append(max(20, width_px - (2 * pad_x) - 10))
                except Exception:
                    continue

        if not available_widths:
            # Still not ready — schedule another attempt in 300 ms.
            self._player_button_fit_after_id = self.root.after(
                300, self._fit_player_button_fonts
            )
            return

        target_available_px = min(available_widths)
        target_size = base_size

        while target_size > min_size:
            candidate_font = (base_family, target_size, *base_style)
            try:
                text_px = tkfont.Font(font=candidate_font).measure(longest_label)
            except Exception:
                break
            if text_px <= target_available_px:
                break
            target_size -= 1

        shared_font = (base_family, target_size, *base_style)
        for button in all_buttons:
            try:
                button.config(font=shared_font)
            except Exception:
                pass

    def refresh_layout_for_current_screen(self, force=False):
        """Refresh dimensions/fonts when monitor changes or a resize requires re-scaling."""
        self._layout_refresh_after_id = None
        screen_w, screen_h = self._get_current_monitor_size()
        next_scale = max(0.6, screen_h / 1080.0)
        signature = (screen_w, screen_h, round(next_scale, 3))

        if not force and signature == self._last_monitor_signature:
            return

        self.screen_w = screen_w
        self.screen_h = screen_h
        self.scale = next_scale
        self._last_monitor_signature = signature

        self._rebuild_fonts_from_scale()

        # Notebook tab typography and spacing
        try:
            self.style.configure(
                "TNotebook.Tab",
                font=self.fonts["normal_bold"],
                padding=[max(12, int(20 * self.scale)), max(6, int(10 * self.scale))],
            )
        except Exception:
            pass

        # Refresh pane sizes
        try:
            list_w = int(self.screen_w * 0.5)
            info_w = int(self.screen_w * 0.22)
            console_w = int(self.screen_w * 0.28)
            self.paned_window.paneconfigure(self.list_frame, width=list_w)
            self.paned_window.paneconfigure(self.info_frame, width=info_w)
            self.paned_window.paneconfigure(self.console_frame, width=console_w)
        except Exception:
            pass

        try:
            top_pane_height = int(self.screen_h * 0.53)
            prefs_height = int(self.screen_h * 0.27)
            self.vertical_paned.paneconfigure(self.paned_window, height=top_pane_height)
            self.vertical_paned.paneconfigure(self.prefs_frame, height=prefs_height)
            self.prefs_default_height = prefs_height
        except Exception:
            pass

        # Scale parameter controls lengths
        control_length = max(100, int(120 * self.scale))
        for control_name in (
            "female_boost_scale",
            "level_gap_tol_scale",
            "lambda_weight_scale",
        ):
            try:
                getattr(self, control_name).config(length=control_length)
            except Exception:
                pass

        # Scale player list button typography/padding
        for button in self.player_buttons.values():
            try:
                button.config(
                    font=self.player_button_font,
                    padx=self.player_button_padx,
                    pady=self.player_button_pady,
                )
            except Exception:
                pass

        try:
            self.add_player_btn.config(
                font=self.player_button_font,
                padx=self.player_button_padx,
                pady=self.player_button_pady,
            )
        except Exception:
            pass

        self._schedule_player_button_font_fit()

        # Apply scaled fonts across existing widgets
        self._apply_scaled_fonts_to_widget_tree()

    def write_to_console(self, text):
        """Write text to the console output widget"""
        self.console_text.config(state=tk.NORMAL)
        self.console_text.insert(tk.END, text)
        self.console_text.see(tk.END)
        self.console_text.config(state=tk.DISABLED)
        self.root.update()

    def bind_tooltip(self, widget, text):
        """Bind a simple hover tooltip to a widget."""
        widget.bind(
            "<Enter>",
            lambda event, tooltip_text=text: self.schedule_tooltip(event, tooltip_text),
        )
        widget.bind("<Leave>", self.hide_tooltip)

    def schedule_tooltip(self, event, text):
        """Schedule tooltip display after a short delay."""
        self.hide_tooltip()

        widget = event.widget
        x = widget.winfo_rootx() + 14
        y = widget.winfo_rooty() + widget.winfo_height() + 8

        self._tooltip_after_id = self.root.after(
            self._tooltip_delay_ms,
            lambda: self.show_tooltip_at(x, y, text),
        )

    def show_tooltip(self, event, text):
        """Show a tooltip near the hovered widget."""
        self.hide_tooltip()

        x = event.widget.winfo_rootx() + 14
        y = event.widget.winfo_rooty() + event.widget.winfo_height() + 8
        self.show_tooltip_at(x, y, text)

    def show_tooltip_at(self, x, y, text):
        """Show a tooltip at screen coordinates."""
        self.hide_tooltip()

        tooltip = tk.Toplevel(self.root)
        tooltip.wm_overrideredirect(True)
        try:
            tooltip.wm_attributes("-topmost", True)
        except Exception:
            pass

        tooltip_label = tk.Label(
            tooltip,
            text=text,
            justify=tk.LEFT,
            bg="#FFF8DC",
            fg=self.colors["text_dark"],
            relief=tk.SOLID,
            bd=1,
            padx=6,
            pady=4,
            wraplength=max(220, int(280 * self.scale)),
            font=self.fonts["small"],
        )
        tooltip_label.pack()
        tooltip.wm_geometry(f"+{x}+{y}")

        self._tooltip_window = tooltip

    def hide_tooltip(self, event=None):
        """Hide current tooltip if displayed."""
        if self._tooltip_after_id is not None:
            try:
                self.root.after_cancel(self._tooltip_after_id)
            except Exception:
                pass
            self._tooltip_after_id = None

        if self._tooltip_window is not None:
            try:
                self._tooltip_window.destroy()
            except Exception:
                pass
            self._tooltip_window = None

    def clear_console(self):
        """Clear the console output"""
        self.console_text.config(state=tk.NORMAL)
        self.console_text.delete("1.0", tk.END)
        self.console_text.config(state=tk.DISABLED)

    def create_round_preferences(self):
        """Create or recreate the round preference controls based on num_rounds_var"""
        # Clear existing round frames
        for frame in self.round_frames:
            frame.destroy()
        self.round_frames.clear()
        self.type_prefs.clear()
        self.gender_prefs.clear()
        self.type_buttons_list.clear()
        self.gender_buttons_list.clear()

        num_rounds = self.num_rounds_var.get()

        # Default preferences (cycle through these for any number of rounds)
        type_defaults = ["balanced", "balanced", "level", "level"]
        gender_defaults = ["open", "mixed", "mixed", "open"]

        for i in range(num_rounds):
            round_frame = tk.Frame(self.rounds_container, bg=self.colors["bg_light"])
            round_frame.grid(row=i, column=0, columnspan=5, sticky=(tk.W, tk.E), pady=2)
            self.round_frames.append(round_frame)

            # Round label with burgundy background
            round_label = tk.Label(
                round_frame,
                text=f"Round {i+1}:",
                font=self.fonts["normal_bold"],
                width=10,
                bg=self.colors["accent_red"],
                fg=self.colors["text_light"],
                padx=5,
                pady=3,
            )
            round_label.grid(row=0, column=0, padx=5, sticky=tk.W)

            # Type preference
            type_var = tk.StringVar(value=type_defaults[i % len(type_defaults)])
            self.type_prefs.append(type_var)
            type_section, type_buttons = self._make_toggle_group(
                round_frame, "#E8F4F8", "Type:", ["level", "balanced"], type_var
            )
            type_section.grid(row=0, column=1, padx=10, sticky=tk.W)
            self.type_buttons_list.append(type_buttons)

            # Gender preference
            gender_var = tk.StringVar(value=gender_defaults[i % len(gender_defaults)])
            self.gender_prefs.append(gender_var)
            gender_section, gender_buttons = self._make_toggle_group(
                round_frame, "#F8E8F4", "Gender:", ["open", "mixed"], gender_var
            )
            gender_section.grid(row=0, column=2, padx=10, sticky=tk.W)
            self.gender_buttons_list.append(gender_buttons)

    def toggle_spectrum_switch(self):
        """Toggle Spectrum parameter ON/OFF"""
        self.set_spectrum_state(not bool(self.spectrum_var.get()))

    def set_spectrum_state(self, enabled):
        """Set Spectrum parameter state"""
        self.spectrum_var.set(bool(enabled))
        self.update_spectrum_switch_display()

    def _set_png_levels_state(self, enabled):
        """Set the 'show levels in PNG' toggle state and refresh button display."""
        self.png_show_levels_var.set(bool(enabled))
        if not hasattr(self, "_png_levels_buttons"):
            return
        selected = "on" if enabled else "off"
        for key, btn in self._png_levels_buttons.items():
            if key == selected:
                btn.config(
                    bg=self.colors["accent_yellow"],
                    fg=self.colors["text_dark"],
                    relief=tk.SUNKEN,
                )
            else:
                btn.config(
                    bg=self.colors["bg_light"],
                    fg=self.colors["text_dark"],
                    relief=tk.RAISED,
                )

    def update_spectrum_switch_display(self):
        """Refresh Spectrum ON/OFF button appearances from current state"""
        if not hasattr(self, "spectrum_buttons"):
            return

        selected_key = "on" if bool(self.spectrum_var.get()) else "off"
        for key, btn in self.spectrum_buttons.items():
            if key == selected_key:
                btn.config(
                    bg=self.colors["accent_yellow"],
                    fg=self.colors["text_dark"],
                    relief=tk.SUNKEN,
                )
            else:
                btn.config(
                    bg=self.colors["bg_light"],
                    fg=self.colors["text_dark"],
                    relief=tk.RAISED,
                )

    def increase_rounds(self):
        """Increase the number of rounds"""
        current = self.num_rounds_var.get()
        if current < 10:  # Max 10 rounds
            self.num_rounds_var.set(current + 1)
            self.rounds_label.config(text=str(current + 1))
            self.create_round_preferences()
            # Expand the pane by approximately 30 pixels per round to keep buttons in place
            current_height = self.prefs_frame.winfo_height()
            if current_height > 1:  # Only adjust if widget has been rendered
                self.prefs_frame.config(height=current_height + 30)

    def decrease_rounds(self):
        """Decrease the number of rounds"""
        current = self.num_rounds_var.get()
        if current > 1:  # Min 1 round
            self.num_rounds_var.set(current - 1)
            self.rounds_label.config(text=str(current - 1))
            self.create_round_preferences()
            # Shrink the pane by approximately 30 pixels per round to keep buttons in place
            current_height = self.prefs_frame.winfo_height()
            if current_height > 430:  # Don't shrink below minimum
                self.prefs_frame.config(height=current_height - 30)

    def toggle_player(self, player_name):
        """Toggle player selection when button is clicked"""
        if self.player_button_states[player_name]:
            # Deselect
            self.player_button_states[player_name] = False
            self.player_buttons[player_name].config(
                bg=self.colors["bg_light"],
                fg=self.colors["text_dark"],
                relief=tk.RAISED,
            )
            self.selected_players.remove(player_name)
        else:
            # Select
            self.player_button_states[player_name] = True
            self.player_buttons[player_name].config(
                bg=self.colors["accent_yellow"],
                fg=self.colors["text_dark"],
                relief=tk.SUNKEN,
            )
            self.selected_players.append(player_name)

        # Update count label and info display
        self._update_count_label()
        self.update_info_display()

    def _update_count_label(self):
        """Update the count label with total, male and female counts."""
        n = len(self.selected_players)
        if n > 0 and "Gender" in self.main_df.columns:
            genders = [
                self.player_overrides.get(p, {}).get(
                    "Gender", self.main_df.at[p, "Gender"]
                )
                for p in self.selected_players
                if p in self.main_df.index
            ]
            n_male = sum(1 for g in genders if g == "Male")
            n_female = sum(1 for g in genders if g == "Female")
            self.count_label.config(
                text=f"Selected: {n} players  (M: {n_male}  F: {n_female})"
            )
        else:
            self.count_label.config(text=f"Selected: {n} players")

    def format_player_button_text(self, player_name):
        """Return button text with marker when player has temporary edits."""
        if player_name in self.player_overrides:
            return f"{player_name} ✎"
        return player_name

    def refresh_player_button_markers(self):
        """Refresh all player button labels to reflect edit markers."""
        for player_name, btn in self.player_buttons.items():
            btn.config(text=self.format_player_button_text(player_name))
        self._schedule_player_button_font_fit()

    def update_info_display(self):
        """Update the info display with selected players details"""
        self.info_text.delete("1.0", tk.END)

        if not self.selected_players:
            self.info_text.insert("1.0", "No players selected")
            return

        # Create dataframe of selected players
        selected_df = self.main_df.loc[self.selected_players].copy()
        for player_name in self.selected_players:
            overrides = self.player_overrides.get(player_name, {})
            for column_name, value in overrides.items():
                selected_df.at[player_name, column_name] = value

        # Display summary
        self.info_text.insert(tk.END, f"Total Players: {len(self.selected_players)}\n")
        n_male = (
            (selected_df["Gender"] == "Male").sum()
            if "Gender" in selected_df.columns
            else "?"
        )
        n_female = (
            (selected_df["Gender"] == "Female").sum()
            if "Gender" in selected_df.columns
            else "?"
        )
        self.info_text.insert(tk.END, f"Male: {n_male}  Female: {n_female}\n")
        self.info_text.insert(tk.END, "=" * 40 + "\n")

        # Display level distribution FIRST (above players list)
        self.info_text.insert(tk.END, "Level Distribution:\n")

        # Categorize levels into ranges
        levels = selected_df["Level"]
        range_1_2 = len(levels[(levels >= 1) & (levels < 2)])
        range_2_3 = len(levels[(levels >= 2) & (levels < 3)])
        range_3_4 = len(levels[(levels >= 3) & (levels <= 4)])

        self.info_text.insert(tk.END, f"  Level 1-2: {range_1_2} player(s)\n")
        self.info_text.insert(tk.END, f"  Level 2-3: {range_2_3} player(s)\n")
        self.info_text.insert(tk.END, f"  Level 3-4: {range_3_4} player(s)\n")

        self.info_text.insert(tk.END, f"Avg Level: {selected_df['Level'].mean():.2f}\n")
        self.info_text.insert(tk.END, "=" * 40 + "\n\n")

        # Display each player AFTER level distribution
        for name in self.selected_players:
            player = selected_df.loc[name]
            self.info_text.insert(tk.END, f"{name}\n")
            self.info_text.insert(tk.END, f"  Level: {player['Level']}\n")
            if "Gender" in player.index:
                self.info_text.insert(tk.END, f"  Gender: {player['Gender']}\n")
            self.info_text.insert(tk.END, "\n")

    def select_all(self):
        """Select all players"""
        # Select all player buttons
        for player_name in self.player_buttons:
            if not self.player_button_states[player_name]:
                self.player_button_states[player_name] = True
                button = self.player_buttons[player_name]
                button.config(bg="#FED403", relief=tk.SUNKEN)
                if player_name not in self.selected_players:
                    self.selected_players.append(player_name)

        # Update count and info display
        self._update_count_label()
        self.update_info_display()

    def clear_selection(self):
        """Clear all selections"""
        # Deselect all player buttons
        for player_name in self.player_buttons:
            if self.player_button_states[player_name]:
                self.player_button_states[player_name] = False
                button = self.player_buttons[player_name]
                button.config(bg="white", relief=tk.RAISED)

        # Clear selected players list
        self.selected_players = []
        self._update_count_label()
        self.info_text.delete("1.0", tk.END)
        self.info_text.insert("1.0", "No players selected")

    def show_add_player_dialog(self):
        """Show dialog to add a new player."""
        self._show_player_dialog()

    def show_edit_player_dialog(self, player_name):
        """Show dialog to edit an existing player's specs."""
        self._show_player_dialog(player_name)

    def _update_pairs_count_label(self):
        """Refresh the Preferred Pairs button text to show the current pair count."""
        n = len(self.preferred_pairs)
        if n == 0:
            self.pairs_btn.config(text="\U0001f465 Preferred Pairs")
        elif n == 1:
            self.pairs_btn.config(text="\U0001f465 Preferred Pairs  \u00b7  1 pair")
        else:
            self.pairs_btn.config(text=f"\U0001f465 Preferred Pairs  \u00b7  {n} pairs")

    def show_preferred_pairs_dialog(self):
        """Modal dialog for managing preferred pairs."""
        BG = self.colors["bg_dark"]
        BG_SECT = "#3A3A3A"
        BURG = self.colors["accent_red"]
        YELLOW = self.colors["accent_yellow"]
        WHITE = self.colors["text_light"]
        GRAY = "#BBBBBB"
        GREEN = "#4CAF50"

        win = tk.Toplevel(self.root)
        win.title("Preferred Pairs")
        win.configure(bg=BG)
        win.resizable(True, True)
        win.grab_set()

        W, H = 820, 660
        win.update_idletasks()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry(f"{W}x{H}+{(sw - W) // 2}+{(sh - H) // 2}")

        # Working copies so cancelling has no effect
        # Each entry is (frozenset({name1, name2}), forced_games)
        pairs_working = list(self.preferred_pairs)
        pending = []  # 0, 1, or 2 player names waiting to form a pair

        # ── header ──────────────────────────────────────────────────────────
        hdr = tk.Frame(win, bg=BURG)
        hdr.pack(fill=tk.X)
        tk.Label(
            hdr,
            text="\U0001f465  Preferred Pairs",
            font=("Arial", 14, "bold"),
            fg=YELLOW,
            bg=BURG,
            padx=14,
            pady=8,
        ).pack(side=tk.LEFT)
        tk.Label(
            hdr,
            text="Click two players, then choose how many games to force them together.",
            font=("Arial", 10),
            fg=WHITE,
            bg=BURG,
            padx=6,
        ).pack(side=tk.LEFT)

        # ── current pairs display ────────────────────────────────────────────
        pairs_section = tk.LabelFrame(
            win,
            text="Current pairs",
            font=("Arial", 10, "bold"),
            bg=BG,
            fg=YELLOW,
            bd=1,
            relief=tk.RIDGE,
            padx=8,
            pady=4,
        )
        pairs_section.pack(fill=tk.X, padx=14, pady=(10, 4))

        pairs_text_var = tk.StringVar()
        pairs_display = tk.Label(
            pairs_section,
            textvariable=pairs_text_var,
            font=("Arial", 10),
            fg=WHITE,
            bg=BG,
            justify=tk.LEFT,
            wraplength=780,
            anchor=tk.W,
        )
        pairs_display.pack(anchor=tk.W)

        def refresh_pairs_display():
            if pairs_working:
                lines = []
                for i, (fs, fg) in enumerate(pairs_working, 1):
                    names = sorted(fs)
                    games_label = f"{fg} game" + ("s" if fg > 1 else "")
                    lines.append(f"  {i}. {names[0]}  /  {names[1]}   [{games_label}]")
                pairs_text_var.set("\n".join(lines))
            else:
                pairs_text_var.set("  (none)")
            _check_buttons()

        # ── player grid ─────────────────────────────────────────────────────
        grid_outer = tk.LabelFrame(
            win,
            text="Select two players",
            font=("Arial", 10, "bold"),
            bg=BG,
            fg=YELLOW,
            bd=1,
            relief=tk.RIDGE,
        )
        grid_outer.pack(fill=tk.BOTH, expand=True, padx=14, pady=4)

        grid_canvas = tk.Canvas(grid_outer, bg="#F5F5F5", highlightthickness=0)
        grid_scroll = tk.Scrollbar(
            grid_outer, orient="vertical", command=grid_canvas.yview
        )
        grid_frame = tk.Frame(grid_canvas, bg="#F5F5F5")

        grid_frame.bind(
            "<Configure>",
            lambda e: grid_canvas.configure(scrollregion=grid_canvas.bbox("all")),
        )
        grid_canvas.create_window((0, 0), window=grid_frame, anchor="nw", tags=("gw",))
        grid_canvas.configure(yscrollcommand=grid_scroll.set)
        grid_canvas.bind(
            "<Configure>",
            lambda e: grid_canvas.itemconfig("gw", width=e.width),
        )

        def _on_mousewheel(event):
            grid_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        grid_canvas.bind("<MouseWheel>", _on_mousewheel)
        grid_frame.bind("<MouseWheel>", _on_mousewheel)

        grid_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6, pady=6)
        grid_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        sorted_players = sorted(self.main_df.index)
        num_cols = 6
        btn_refs = {}

        def _btn_bg(name):
            """Return background colour for a player button given current state."""
            if name in pending:
                return YELLOW
            # Check if player is in any existing pair
            for fs, _fg in pairs_working:
                if name in fs:
                    return "#8B3030"  # dark red tint — already paired
            return "#FFFFFF"

        def _btn_fg(name):
            if name in pending:
                return self.colors["text_dark"]
            for fs, _fg in pairs_working:
                if name in fs:
                    return WHITE
            return self.colors["text_dark"]

        def _refresh_grid():
            for name, btn in btn_refs.items():
                btn.config(bg=_btn_bg(name), fg=_btn_fg(name))

        def _on_player_click(name):
            if name in pending:
                pending.remove(name)
            else:
                if len(pending) >= 2:
                    pending.pop(0)
                pending.append(name)
            _refresh_grid()
            _check_buttons()

        for idx, name in enumerate(sorted_players):
            row = idx // num_cols
            col = idx % num_cols
            btn = tk.Button(
                grid_frame,
                text=name,
                font=("Arial", 9),
                bg=_btn_bg(name),
                fg=_btn_fg(name),
                relief=tk.RAISED,
                bd=1,
                cursor="hand2",
                padx=4,
                pady=4,
                anchor="center",
                command=lambda n=name: _on_player_click(n),
            )
            btn.grid(row=row, column=col, padx=2, pady=2, sticky=(tk.W, tk.E))
            btn.bind("<MouseWheel>", _on_mousewheel)
            btn_refs[name] = btn

        for c in range(num_cols):
            grid_frame.columnconfigure(c, weight=1)

        # ── footer buttons ───────────────────────────────────────────────────
        footer = tk.Frame(win, bg=BG)
        footer.pack(fill=tk.X, padx=14, pady=10)

        add_1_btn = tk.Button(
            footer,
            text="Add pair  ·  1 game 🔒",
            font=("Arial", 11, "bold"),
            bg=GREEN,
            fg=WHITE,
            relief=tk.RAISED,
            cursor="hand2",
            padx=16,
            pady=6,
            state=tk.DISABLED,
        )
        add_2_btn = tk.Button(
            footer,
            text="Add pair  ·  2 games 🔒",
            font=("Arial", 11, "bold"),
            bg="#2E7D32",
            fg=WHITE,
            relief=tk.RAISED,
            cursor="hand2",
            padx=16,
            pady=6,
            state=tk.DISABLED,
        )
        remove_btn = tk.Button(
            footer,
            text="Remove last pair",
            font=("Arial", 11, "bold"),
            bg="#CC4444",
            fg=WHITE,
            relief=tk.RAISED,
            cursor="hand2",
            padx=16,
            pady=6,
            state=tk.DISABLED,
        )
        close_btn = tk.Button(
            footer,
            text="Close",
            font=("Arial", 11),
            bg="#555555",
            fg=WHITE,
            relief=tk.RAISED,
            cursor="hand2",
            padx=16,
            pady=6,
        )

        def _check_buttons():
            # Add pair: need exactly 2 distinct pending players not already paired together
            can_add = False
            if len(pending) == 2 and pending[0] != pending[1]:
                candidate = frozenset(pending)
                if not any(fs == candidate for (fs, _fg) in pairs_working):
                    can_add = True
            add_1_btn.config(state=tk.NORMAL if can_add else tk.DISABLED)
            add_2_btn.config(state=tk.NORMAL if can_add else tk.DISABLED)
            remove_btn.config(state=tk.NORMAL if pairs_working else tk.DISABLED)

        def _on_add(forced_games):
            if len(pending) != 2 or pending[0] == pending[1]:
                return
            candidate = frozenset(pending)
            if any(fs == candidate for (fs, _fg) in pairs_working):
                return
            pairs_working.append((candidate, forced_games))
            pending.clear()
            _refresh_grid()
            refresh_pairs_display()

        def _on_remove():
            if pairs_working:
                pairs_working.pop()
                _refresh_grid()
                refresh_pairs_display()

        def _on_close():
            # Commit working copy back to the app state
            self.preferred_pairs = list(pairs_working)
            self._update_pairs_count_label()
            win.destroy()

        add_1_btn.config(command=lambda: _on_add(1))
        add_2_btn.config(command=lambda: _on_add(2))
        remove_btn.config(command=_on_remove)
        close_btn.config(command=_on_close)

        add_1_btn.pack(side=tk.LEFT, padx=(0, 6))
        add_2_btn.pack(side=tk.LEFT, padx=(0, 8))
        remove_btn.pack(side=tk.LEFT, padx=(0, 8))
        close_btn.pack(side=tk.RIGHT)

        win.protocol("WM_DELETE_WINDOW", _on_close)

        # Initial render
        refresh_pairs_display()
        _check_buttons()

    def _show_player_dialog(self, player_name=None):
        """Unified add/edit player dialog.  player_name=None → add mode."""
        edit_mode = player_name is not None

        if edit_mode and player_name not in self.main_df.index:
            messagebox.showerror("Error", f"Player '{player_name}' not found.")
            return

        # Load existing data in edit mode
        player_data = None
        if edit_mode:
            player_data = self.main_df.loc[player_name].copy()
            for col, val in self.player_overrides.get(player_name, {}).items():
                player_data[col] = val

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Edit Player - {player_name}" if edit_mode else "Add New Player")
        dialog.geometry("450x550")
        dialog.resizable(False, False)
        dialog.configure(bg=self.colors["bg_light"])
        dialog.transient(self.root)
        dialog.grab_set()

        dialog.update_idletasks()
        x = (
            self.root.winfo_x()
            + (self.root.winfo_width() // 2)
            - (dialog.winfo_width() // 2)
        )
        y = (
            self.root.winfo_y()
            + (self.root.winfo_height() // 2)
            - (dialog.winfo_height() // 2)
        )
        dialog.geometry(f"+{x}+{y}")

        tk.Label(
            dialog,
            text=f"Edit {player_name}" if edit_mode else "Add New Player",
            font=self.fonts["big"],
            fg=self.colors["accent_red"],
            bg=self.colors["bg_light"],
        ).pack(pady=(20, 10))

        form_frame = tk.Frame(dialog, bg=self.colors["bg_light"])
        form_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)

        # Name row
        tk.Label(
            form_frame,
            text="Name:",
            font=self.fonts["normal"],
            bg=self.colors["bg_light"],
        ).grid(row=0, column=0, sticky=tk.W, pady=5)
        name_entry = None
        if edit_mode:
            tk.Label(
                form_frame,
                text=player_name,
                font=self.fonts["normal_bold"],
                bg=self.colors["bg_light"],
                fg=self.colors["text_dark"],
            ).grid(row=0, column=1, sticky=tk.W, pady=5, padx=10)
        else:
            name_entry = tk.Entry(form_frame, font=self.fonts["normal"], width=25)
            name_entry.grid(row=0, column=1, pady=5, padx=10)
            name_entry.focus_set()

        # Gender row
        tk.Label(
            form_frame,
            text="Gender:",
            font=self.fonts["normal"],
            bg=self.colors["bg_light"],
        ).grid(row=1, column=0, sticky=tk.W, pady=5)
        if edit_mode:
            init_gender = str(player_data.get("Gender", "Male"))
            if init_gender not in ["Male", "Female"]:
                init_gender = "Male"
        else:
            init_gender = "Male"
        gender_var = tk.StringVar(value=init_gender)
        gender_frame = tk.Frame(form_frame, bg=self.colors["bg_light"])
        gender_frame.grid(row=1, column=1, pady=5, padx=10, sticky=tk.W)
        for g in ["Male", "Female"]:
            tk.Radiobutton(
                gender_frame,
                text=g,
                variable=gender_var,
                value=g,
                font=self.fonts["normal"],
                bg=self.colors["bg_light"],
            ).pack(side=tk.LEFT, padx=5)

        # Level row
        tk.Label(
            form_frame,
            text="Level:",
            font=self.fonts["normal"],
            bg=self.colors["bg_light"],
        ).grid(row=2, column=0, sticky=tk.W, pady=5)
        if edit_mode:
            try:
                init_level = float(player_data.get("Level", 1.5))
            except (TypeError, ValueError):
                init_level = 1.5
        else:
            init_level = 1.5
        level_var = tk.DoubleVar(value=init_level)
        tk.Spinbox(
            form_frame,
            from_=0,
            to=4,
            increment=0.1,
            textvariable=level_var,
            font=self.fonts["normal"],
            width=23,
        ).grid(row=2, column=1, pady=5, padx=10)

        # Separator
        tk.Frame(form_frame, height=2, bg=self.colors["accent_red"]).grid(
            row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10
        )

        # Spectrum section header
        tk.Label(
            form_frame,
            text="Spectrum Attributes:",
            font=self.fonts["normal_bold"],
            bg=self.colors["bg_light"],
            fg=self.colors["accent_red"],
        ).grid(row=4, column=0, columnspan=2, pady=(5, 10))

        # Happiness row
        tk.Label(
            form_frame,
            text="Happiness:",
            font=self.fonts["small"],
            bg=self.colors["bg_light"],
        ).grid(row=5, column=0, sticky=tk.W, pady=3)
        if edit_mode:
            try:
                init_happiness = int(player_data.get("Happiness", 0))
            except (TypeError, ValueError):
                init_happiness = 0
        else:
            init_happiness = 0
        happiness_var = tk.IntVar(value=init_happiness)
        tk.Entry(
            form_frame, textvariable=happiness_var, font=self.fonts["small"], width=25
        ).grid(row=5, column=1, pady=3, padx=10)

        # Spectrum spinboxes
        spectrum_names = [
            "Prey",
            "Equilibrist",
            "Challenger",
            "Chill",
            "Hunter",
            "Classist",
        ]
        spectrum_frame = tk.Frame(form_frame, bg=self.colors["bg_light"])
        spectrum_frame.grid(row=6, column=0, columnspan=2, pady=5)
        spectrum_vars = {}
        for idx, spec_name in enumerate(spectrum_names):
            row_idx = idx // 2
            col_idx = idx % 2
            spec_frame = tk.Frame(spectrum_frame, bg=self.colors["bg_light"])
            spec_frame.grid(row=row_idx, column=col_idx, padx=5, pady=3, sticky=tk.W)
            tk.Label(
                spec_frame,
                text=f"{spec_name}:",
                font=self.fonts["small"],
                bg=self.colors["bg_light"],
                width=10,
                anchor=tk.W,
            ).pack(side=tk.LEFT)
            if edit_mode:
                try:
                    init_spec = int(player_data.get(spec_name, 5))
                except (TypeError, ValueError):
                    init_spec = 5
            else:
                init_spec = 5
            var = tk.IntVar(value=init_spec)
            spectrum_vars[spec_name] = var
            tk.Spinbox(
                spec_frame,
                from_=0,
                to=10,
                textvariable=var,
                font=self.fonts["small"],
                width=5,
            ).pack(side=tk.LEFT, padx=5)

        # Buttons
        buttons_frame = tk.Frame(dialog, bg=self.colors["bg_light"])
        buttons_frame.pack(pady=20)
        btn_cfg = dict(
            font=self.fonts["normal_bold"],
            relief=tk.RAISED,
            bd=3,
            cursor="hand2",
            padx=20,
            pady=8,
        )

        if edit_mode:

            def on_save():
                try:
                    new_level = float(level_var.get())
                    new_happiness = int(happiness_var.get())
                except (TypeError, ValueError):
                    messagebox.showerror(
                        "Invalid Input", "Level and Happiness must be numeric values."
                    )
                    return
                self.player_overrides[player_name] = {
                    "Gender": str(gender_var.get()),
                    "Level": new_level,
                    "Category": new_level,
                    "Happiness": new_happiness,
                    **{s: int(spectrum_vars[s].get()) for s in spectrum_names},
                }
                self.refresh_player_button_markers()
                self.update_info_display()
                dialog.destroy()

            def on_reset():
                if player_name in self.player_overrides:
                    del self.player_overrides[player_name]
                base = self.main_df.loc[player_name]
                base_gender = str(base.get("Gender", "Male"))
                if base_gender not in ["Male", "Female"]:
                    base_gender = "Male"
                gender_var.set(base_gender)
                try:
                    level_var.set(float(base.get("Level", 1.5)))
                except (TypeError, ValueError):
                    level_var.set(1.5)
                try:
                    happiness_var.set(int(base.get("Happiness", 0)))
                except (TypeError, ValueError):
                    happiness_var.set(0)
                for s in spectrum_names:
                    try:
                        spectrum_vars[s].set(int(base.get(s, 5)))
                    except (TypeError, ValueError):
                        spectrum_vars[s].set(5)
                self.refresh_player_button_markers()
                self.update_info_display()

            dialog.bind("<Return>", lambda e: on_save())
            tk.Button(
                buttons_frame,
                text="Reset",
                command=on_reset,
                bg=self.colors["accent_red"],
                fg=self.colors["text_light"],
                **btn_cfg,
            ).pack(side=tk.LEFT, padx=5)
            tk.Button(
                buttons_frame,
                text="Save",
                command=on_save,
                bg=self.colors["accent_yellow"],
                fg=self.colors["text_dark"],
                **btn_cfg,
            ).pack(side=tk.LEFT, padx=5)
            tk.Button(
                buttons_frame,
                text="Cancel",
                command=dialog.destroy,
                bg=self.colors["bg_light"],
                fg=self.colors["text_dark"],
                **btn_cfg,
            ).pack(side=tk.LEFT, padx=5)
        else:

            def on_add():
                name = name_entry.get().strip()
                if not name:
                    messagebox.showerror("Error", "Please enter a player name.")
                    return
                if name in self.main_df.index:
                    messagebox.showerror("Error", f"Player '{name}' already exists.")
                    return
                self.add_new_player(
                    name=name,
                    gender=gender_var.get(),
                    level=level_var.get(),
                    happiness=happiness_var.get(),
                    prey=spectrum_vars["Prey"].get(),
                    equilibrist=spectrum_vars["Equilibrist"].get(),
                    challenger=spectrum_vars["Challenger"].get(),
                    chill=spectrum_vars["Chill"].get(),
                    hunter=spectrum_vars["Hunter"].get(),
                    classist=spectrum_vars["Classist"].get(),
                )
                dialog.destroy()

            dialog.bind("<Return>", lambda e: on_add())
            tk.Button(
                buttons_frame,
                text="Add Player",
                command=on_add,
                bg=self.colors["accent_yellow"],
                fg=self.colors["text_dark"],
                **btn_cfg,
            ).pack(side=tk.LEFT, padx=5)
            tk.Button(
                buttons_frame,
                text="Cancel",
                command=dialog.destroy,
                bg=self.colors["bg_light"],
                fg=self.colors["text_dark"],
                **btn_cfg,
            ).pack(side=tk.LEFT, padx=5)

    def add_new_player(
        self,
        name,
        gender,
        level,
        happiness,
        prey,
        equilibrist,
        challenger,
        chill,
        hunter,
        classist,
    ):
        """Add a new player to the main dataframe and update UI"""
        # Create a new player series
        new_player_data = {
            "Name": name,
            "Surname": "",
            "Level": float(level),
            "Gender": str(gender),
            "Happiness": int(happiness),
            "Games played": 0,
            "Noisy level": 0,
            "Category": float(level),
            "Prey": int(prey),
            "Equilibrist": int(equilibrist),
            "Challenger": int(challenger),
            "Chill": int(chill),
            "Hunter": int(hunter),
            "Classist": int(classist),
        }

        # Add to main_df - drop any existing player with same name first to avoid duplicates
        import pandas as pd  # noqa: PLC0415

        if name in self.main_df.index:
            self.main_df = self.main_df.drop(name)
        new_row_df = pd.DataFrame([new_player_data], index=[name])
        self.main_df = pd.concat([self.main_df, new_row_df])

        # Get the scrollable frame (parent of player buttons)
        scrollable_frame = getattr(self, "player_scrollable_frame", None)

        if scrollable_frame is None:
            messagebox.showerror("Error", "Could not find player button container.")
            return

        # Destroy all existing buttons and recreate them
        for widget in scrollable_frame.winfo_children():
            widget.destroy()

        # Save current selection state before recreating buttons
        previously_selected = set(self.selected_players)

        # Recreate all player buttons
        self.player_buttons = {}
        self.player_button_states = {}
        sorted_players = sorted(self.main_df.index)
        num_columns = 6

        for idx, player_name in enumerate(sorted_players):
            row = idx // num_columns
            col = idx % num_columns

            # Check if this player was previously selected OR is the newly added player
            is_selected = player_name in previously_selected or player_name == name

            btn = tk.Button(
                scrollable_frame,
                text=self.format_player_button_text(player_name),
                font=(
                    self.font_button_font
                    if hasattr(self, "font_button_font")
                    else self.player_button_font
                ),
                bg=(
                    self.colors["accent_yellow"]
                    if is_selected
                    else self.colors["bg_light"]
                ),
                fg=self.colors["text_dark"],
                relief=tk.SUNKEN if is_selected else tk.RAISED,
                bd=2,
                cursor="hand2",
                padx=self.player_button_padx,
                pady=self.player_button_pady,
                anchor="center",
                command=lambda pname=player_name: self.toggle_player(pname),
            )
            btn.grid(row=row, column=col, padx=2, pady=2, sticky=(tk.W, tk.E))
            btn.bind(
                "<Button-3>",
                lambda event, pname=player_name: self.show_edit_player_dialog(pname),
            )
            self.bind_tooltip(btn, "right click to change specs")

            self.player_buttons[player_name] = btn
            self.player_button_states[player_name] = is_selected

        # Rebuild selected_players list from the saved state plus the new player
        self.selected_players = [
            p for p in sorted_players if p in previously_selected or p == name
        ]

        # Add "+ Add Player" button at the end of the list
        total_players = len(sorted_players)
        add_row = total_players // num_columns
        add_col = total_players % num_columns

        add_player_btn = tk.Button(
            scrollable_frame,
            text="+ Add Player",
            font=self.fonts["normal_bold"],
            bg=self.colors["accent_red"],
            fg=self.colors["text_light"],
            relief=tk.RAISED,
            bd=2,
            cursor="hand2",
            padx=5,
            pady=5,
            anchor="center",
            command=self.show_add_player_dialog,
        )
        add_player_btn.grid(
            row=add_row, column=add_col, padx=2, pady=2, sticky=(tk.W, tk.E)
        )
        self.add_player_btn = add_player_btn

        # Configure column weights for equal distribution
        for col in range(num_columns):
            scrollable_frame.columnconfigure(col, weight=1)

        self._schedule_player_button_font_fit()

        # Update count label and info display
        self._update_count_label()
        self.update_info_display()

    def run_session(self):
        """Run session generation with selected players"""
        if len(self.selected_players) < 4:
            messagebox.showwarning(
                "Too Few Players", "Please select at least 4 players to run a session."
            )
            return

        # Disable the run button to prevent multiple clicks
        self.run_btn.config(state=tk.DISABLED)

        # Create sub dataframe - remove duplicates if any exist
        # Use unique() to ensure selected_players list has no duplicates
        import pandas as pd  # noqa: PLC0415

        unique_selected_players = list(dict.fromkeys(self.selected_players))
        sub_df = self.main_df.loc[unique_selected_players].copy()

        # Additional safety check: ensure sub_df has no duplicate indices
        if sub_df.index.duplicated().any():
            duplicates = sub_df.index[sub_df.index.duplicated()].tolist()
            messagebox.showerror(
                "Data Error",
                f"Duplicate players found in database: {', '.join(duplicates)}\n\n"
                "Please restart the application to fix this issue.",
            )
            self.run_btn.config(state=tk.NORMAL)
            return

        # Apply temporary UI overrides without mutating self.main_df
        for player_name in unique_selected_players:
            overrides = self.player_overrides.get(player_name, {})
            for column_name, value in overrides.items():
                sub_df.at[player_name, column_name] = value

        # Optional temporary female level/category shift (UI-only)
        try:
            female_shift = float(self.female_boost_var.get())
        except (TypeError, ValueError):
            female_shift = 0.0

        if female_shift != 0.0:
            female_mask = (
                sub_df["Gender"]
                .astype(str)
                .str.strip()
                .str.lower()
                .isin(["female", "f"])
            )
            if female_mask.any():
                boosted_levels = pd.to_numeric(
                    sub_df.loc[female_mask, "Level"], errors="coerce"
                ).fillna(0)
                sub_df.loc[female_mask, "Level"] = (
                    boosted_levels + female_shift
                ).round(1)

                if "Category" in sub_df.columns:
                    boosted_categories = pd.to_numeric(
                        sub_df.loc[female_mask, "Category"], errors="coerce"
                    ).fillna(0)
                    sub_df.loc[female_mask, "Category"] = (
                        boosted_categories + female_shift
                    ).round(1)

        sub_df["Happiness"] = 0
        sub_df["Games played"] = 0

        # Get selected preferences from UI
        type_preferences = [var.get() for var in self.type_prefs]
        gender_preferences = [var.get() for var in self.gender_prefs]
        amount_of_rounds = self.num_rounds_var.get()

        # Get games per round setting
        games_per_round_setting = self.games_per_round_var.get()
        if games_per_round_setting == "auto":
            games_per_round = len(self.selected_players) // 4
        else:
            games_per_round = int(games_per_round_setting)

        # Parameters for seed optimization
        first_seed = 0
        last_seed = 9

        # Parameters from UI
        try:
            level_gap_tol = float(self.level_gap_tol_var.get())
        except (TypeError, ValueError):
            level_gap_tol = 1.1

        try:
            lambda_weight = float(self.lambda_weight_var.get())
        except (TypeError, ValueError):
            lambda_weight = 2.4

        try:
            percentile = int(self.percentile_var.get())
        except (TypeError, ValueError):
            percentile = 10

        spectrum_enabled = bool(self.spectrum_var.get())

        # Create progress dialog
        progress_dialog = ProgressDialog(self.root, first_seed, last_seed, self.colors)

        # Run generation with progress tracking
        self.run_generation_with_progress(
            sub_df,
            amount_of_rounds,
            type_preferences,
            gender_preferences,
            first_seed,
            last_seed,
            progress_dialog,
            games_per_round,
            level_gap_tol,
            lambda_weight,
            percentile,
            spectrum_enabled,
            self.preferred_pairs,
        )

    def run_generation_with_progress(
        self,
        sub_df,
        amount_of_rounds,
        type_preferences,
        gender_preferences,
        first_seed,
        last_seed,
        progress_dialog,
        games_per_round,
        level_gap_tol,
        lambda_weight,
        percentile,
        spectrum_enabled,
        preferred_pairs=None,
    ):
        """Run session generation with progress updates."""
        try:
            # Clear console at start
            self.clear_console()
            print("Starting session generation...")
            print(f"Testing seeds {first_seed} to {last_seed}\n")

            # Compute rounds_reordering once: internally generate level rounds first for
            # better optimization, then reorder back to the user-intended display order.
            generated_order_indices = sorted(
                range(amount_of_rounds),
                key=lambda idx: (
                    session_generation_round_type_priority(type_preferences[idx]),
                    idx,
                ),
            )
            generated_pos_by_original_idx = {
                original_idx: generated_pos + 1
                for generated_pos, original_idx in enumerate(generated_order_indices)
            }
            rounds_reordering = [
                generated_pos_by_original_idx[i] for i in range(amount_of_rounds)
            ]

            session_of_rounds, chosen_seed = (
                main_module.run_session_generation_with_seed_optimization(
                    df=sub_df,
                    amount_of_rounds=amount_of_rounds,
                    type_preferences=type_preferences,
                    gender_preferences=gender_preferences,
                    rounds_reordering=rounds_reordering,
                    level_gap_tol=level_gap_tol,
                    num_iter=435,
                    lambda_weight=lambda_weight,
                    objective_function=lambda x: main_module.mean_min_max_happiness_objective(
                        x, lambda_weight=lambda_weight, percentile=percentile
                    ),
                    weight_same_teammate=5,
                    first_seed=first_seed,
                    last_seed=last_seed,
                    spectrum=spectrum_enabled,
                    games_per_round_each_round=games_per_round,
                    print_progress=True,
                    progress_callback=progress_dialog.update_progress,
                )
            )

            # Apply preferred-pairs post-processing
            if preferred_pairs:
                main_module.force_preferred_pairs_in_session(
                    session_of_rounds,
                    preferred_pairs,
                    lambda_weight=lambda_weight,
                )

            # Close progress dialog
            progress_dialog.close()

            # Show results in console/terminal
            print("\n" + "=" * 80)
            print("SESSION RESULTS")
            print("=" * 80)
            session_of_rounds.print_all_results(
                print_levels=True,
            )

            # Store session for further use
            self.session_of_rounds = session_of_rounds
            self.chosen_seed = chosen_seed

            # Stamp objective metadata on the live session object so the Games Editor
            # score history uses the correct lambda weight (these attributes are
            # normally only set during __setstate__ / unpickling).
            session_of_rounds._objective_lambda_weight = lambda_weight
            session_of_rounds._objective_function_name = (
                "mean_min_max_happiness_objective"
            )
            session_of_rounds._objective_percentile = percentile

            # Save the session using save_session_of_rounds with default parameters
            try:
                session_of_rounds.save_session_of_rounds()
                print("\n" + "=" * 80)
                print("Session saved successfully!")
                print("=" * 80)

                # Find the most recently created session folder with plots
                sessions_dir = "sessions"
                if os.path.exists(sessions_dir):
                    # Get all subdirectories in sessions folder
                    session_folders = [
                        os.path.join(sessions_dir, d)
                        for d in os.listdir(sessions_dir)
                        if os.path.isdir(os.path.join(sessions_dir, d))
                    ]

                    # Find folders with a plots subdirectory
                    folders_with_plots = [
                        f
                        for f in session_folders
                        if os.path.exists(os.path.join(f, "plots"))
                    ]

                    # Get the most recently modified one
                    if folders_with_plots:
                        most_recent = max(folders_with_plots, key=os.path.getmtime)
                        plots_dir = os.path.join(most_recent, "plots")

                        # Generate and show the Session Games overview PNG
                        from core.charts import (  # noqa: PLC0415
                            create_session_games_png,
                            create_session_games_round_images,
                        )

                        session_games_png = os.path.join(
                            most_recent, "session_games.png"
                        )
                        print("Creating session games overview...")
                        create_session_games_png(
                            session_of_rounds,
                            session_games_png,
                            show_levels=self.png_show_levels_var.get(),
                        )
                        _round_imgs = create_session_games_round_images(
                            session_of_rounds,
                            show_levels=self.png_show_levels_var.get(),
                        )

                        # Show interactive games editor then session games tab
                        self.show_games_editor()
                        self.show_session_games_tab(
                            session_games_png, round_images=_round_imgs
                        )

                        # Then show happiness/team/spectrum charts in tabbed window
                        self.show_plots_window(plots_dir)

            except Exception as save_error:
                import traceback

                print(f"Warning: Could not save session: {save_error}")
                print("Full traceback:")
                traceback.print_exc()

                # Still try to show the UI even if save failed
                try:
                    sessions_dir = "sessions"
                    if os.path.exists(sessions_dir):
                        session_folders = [
                            os.path.join(sessions_dir, d)
                            for d in os.listdir(sessions_dir)
                            if os.path.isdir(os.path.join(sessions_dir, d))
                        ]
                        if session_folders:
                            most_recent = max(session_folders, key=os.path.getmtime)
                            plots_dir = os.path.join(most_recent, "plots")
                            if os.path.exists(plots_dir):
                                self.show_games_editor()
                                self.show_plots_window(plots_dir)
                            # Session Games tab even without plots folder
                            from core.charts import (  # noqa: PLC0415
                                create_session_games_png,
                                create_session_games_round_images,
                            )

                            session_games_png = os.path.join(
                                most_recent, "session_games.png"
                            )
                            create_session_games_png(
                                session_of_rounds,
                                session_games_png,
                                show_levels=self.png_show_levels_var.get(),
                            )
                            _round_imgs_fb = create_session_games_round_images(
                                session_of_rounds,
                                show_levels=self.png_show_levels_var.get(),
                            )
                            self.show_session_games_tab(
                                session_games_png, round_images=_round_imgs_fb
                            )
                except:
                    pass

        except Exception as e:
            # Close progress dialog if still open
            try:
                progress_dialog.close()
            except:
                pass

            # Print error details
            print(f"Error: {e}")
            import traceback

            traceback.print_exc()

            messagebox.showerror("Error", f"An error occurred:\n\n{str(e)}")
        finally:
            # Re-enable the run button
            self.run_btn.config(state=tk.NORMAL)
