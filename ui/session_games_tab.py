"""Session Games tab controller."""

import os

import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk

main_module = None


class SessionGamesTabMixin:
    def show_session_games_tab(self, png_path: str, round_images=None):
        """Display the Session Games overview as n click-able round tiles.

        Parameters
        ----------
        png_path : str
            Path to the combined session-games PNG (used as fallback and for
            regeneration after Apply Changes).
        round_images : list[PIL.Image] | None
            One PIL Image per round.  When *None* the combined PNG is shown as
            before (single-image fallback).
        """
        # Remove any existing "Session Games" tab
        for tab_id in list(self.main_notebook.tabs()):
            if self.main_notebook.tab(tab_id, "text") == "Session Games":
                self.main_notebook.forget(tab_id)
                break

        # Create the tab frame
        tab_frame = tk.Frame(self.main_notebook, bg=self.colors["bg_light"])
        self.main_notebook.add(tab_frame, text="Session Games")

        # Move to position 2 (after Session Generation at 0 and Games Editor at 1)
        num_tabs = len(self.main_notebook.tabs())
        if num_tabs > 1:
            self.main_notebook.insert(2, tab_frame)

        # Do NOT select this tab — Games Editor stays focused after generation

        self.session_games_png_path = png_path

        # ------------------------------------------------------------------
        # When individual round images are provided, use the interactive mode;
        # otherwise fall back to the plain single-image display.
        # ------------------------------------------------------------------
        if not round_images:
            # ---- plain single-image fallback --------------------------------
            canvas = tk.Canvas(tab_frame, bg=self.colors["bg_light"])
            h_scrollbar = tk.Scrollbar(
                tab_frame, orient=tk.HORIZONTAL, command=canvas.xview
            )
            v_scrollbar = tk.Scrollbar(
                tab_frame, orient=tk.VERTICAL, command=canvas.yview
            )
            canvas.configure(
                xscrollcommand=h_scrollbar.set, yscrollcommand=v_scrollbar.set
            )
            h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
            v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
            canvas.zoom_level = 1.0
            canvas.auto_fit_height = True
            try:
                img = Image.open(png_path)
                canvas.original_image = img

                def _make_fns(cnv):
                    def _fit():
                        ch = cnv.winfo_height()
                        if ch <= 1:
                            return
                        _, oh = cnv.original_image.size
                        cnv.zoom_level = max((ch - 20) / oh, 0.1)

                    def _upd():
                        cw, ch = cnv.winfo_width(), cnv.winfo_height()
                        if cw <= 1 or ch <= 1:
                            return
                        ow, oh = cnv.original_image.size
                        nw, nh = int(ow * cnv.zoom_level), int(oh * cnv.zoom_level)
                        resized = cnv.original_image.resize(
                            (nw, nh), Image.Resampling.LANCZOS
                        )
                        photo = ImageTk.PhotoImage(resized)
                        cnv.delete("all")
                        xp, yp = max(0, (cw - nw) // 2), max(0, (ch - nh) // 2)
                        cnv.create_image(xp, yp, anchor=tk.NW, image=photo)
                        cnv.image = photo
                        cnv.configure(
                            scrollregion=(
                                min(0, xp),
                                min(0, yp),
                                max(cw, xp + nw),
                                max(ch, yp + nh),
                            )
                        )

                    def _resize(event):
                        if getattr(cnv, "auto_fit_height", False):
                            _fit()
                        _upd()

                    def _zi():
                        cnv.auto_fit_height = False
                        cnv.zoom_level = min(cnv.zoom_level * 1.2, 5.0)
                        _upd()

                    def _zo():
                        cnv.auto_fit_height = False
                        cnv.zoom_level = max(cnv.zoom_level / 1.2, 0.1)
                        _upd()

                    return _upd, _resize, _zi, _zo

                _upd, _resize, _zi, _zo = _make_fns(canvas)
                canvas.bind("<Configure>", _resize)

                def _do_fit(cnv, u):
                    def _f():
                        cnv.update_idletasks()
                        if cnv.winfo_height() <= 1:
                            cnv.after(50, _f)
                            return
                        _, oh = cnv.original_image.size
                        cnv.zoom_level = max((cnv.winfo_height() - 20) / oh, 0.1)
                        u()

                    return _f

                canvas.after(2, _do_fit(canvas, _upd))

                def _wheel(event):
                    if event.state & 0x0004:
                        _zi() if event.delta > 0 else _zo()
                        return "break"
                    canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

                def _shift_wheel(event):
                    if event.state & 0x0001:
                        canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")
                        return "break"

                canvas.bind("<MouseWheel>", _wheel)
                canvas.bind("<Shift-MouseWheel>", _shift_wheel)
            except Exception as e:
                tk.Label(
                    tab_frame,
                    text=f"Error loading Session Games image:\n{e}",
                    font=self.fonts["normal"],
                    fg="red",
                    bg=self.colors["bg_light"],
                ).pack(expand=True)
            return

        # ------------------------------------------------------------------
        # Interactive round-swap mode
        # ------------------------------------------------------------------
        n_rounds = len(round_images)

        # Initialise or reset swap state on self so Apply Changes can access it
        self._sg_round_images_base = list(round_images)  # original PIL images
        self._sg_round_order = list(range(n_rounds))  # display_pos -> orig_idx
        self._sg_selected_round = None  # currently highlighted pos
        self._sg_has_pending_swaps = False
        self._sg_round_y_ranges: list = []  # (y_top, y_bot) per display pos
        self._sg_photo_refs: list = []  # keep PhotoImage refs alive

        # ---- outer layout: canvas area (left) + right control panel ----
        outer = tk.Frame(tab_frame, bg=self.colors["bg_light"])
        outer.pack(fill=tk.BOTH, expand=True)

        # Right panel (fixed width)
        right_panel = tk.Frame(
            outer,
            bg="#EEEEEE",
            width=150,
            relief=tk.RIDGE,
            bd=1,
        )
        right_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(4, 8), pady=8)
        right_panel.pack_propagate(False)

        tk.Label(
            right_panel,
            text="Round Order",
            font=self.fonts["small_bold"],
            bg="#EEEEEE",
            fg=self.colors["accent_red"],
        ).pack(pady=(14, 4))

        tk.Label(
            right_panel,
            text="Click a round to\nselect it, then click\nanother to swap.",
            font=("Arial", 9),
            bg="#EEEEEE",
            fg="#555555",
            justify=tk.LEFT,
            wraplength=130,
        ).pack(padx=8, pady=(0, 12))

        status_lbl = tk.Label(
            right_panel,
            text="No pending swaps",
            font=("Arial", 9),
            bg="#EEEEEE",
            fg="#555555",
            justify=tk.CENTER,
            wraplength=130,
        )
        status_lbl.pack(padx=8, pady=(0, 10))

        apply_btn = tk.Button(
            right_panel,
            text="Apply\nChanges",
            font=self.fonts["small_bold"],
            bg=self.colors["accent_yellow"],
            fg=self.colors["text_dark"],
            relief=tk.RAISED,
            cursor="hand2",
            padx=10,
            pady=8,
            state=tk.DISABLED,
        )
        apply_btn.pack(padx=8, pady=(0, 8))

        reset_btn = tk.Button(
            right_panel,
            text="Reset Order",
            font=("Arial", 9),
            bg="#CCCCCC",
            fg=self.colors["text_dark"],
            relief=tk.RAISED,
            cursor="hand2",
            padx=6,
            pady=4,
            state=tk.DISABLED,
        )
        reset_btn.pack(padx=8)

        # Canvas area (left side)
        canvas_frame = tk.Frame(outer, bg=self.colors["bg_light"])
        canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(canvas_frame, bg=self.colors["bg_light"])
        h_scrollbar = tk.Scrollbar(
            canvas_frame, orient=tk.HORIZONTAL, command=canvas.xview
        )
        v_scrollbar = tk.Scrollbar(
            canvas_frame, orient=tk.VERTICAL, command=canvas.yview
        )
        canvas.configure(xscrollcommand=h_scrollbar.set, yscrollcommand=v_scrollbar.set)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        canvas.zoom_level = 1.0
        canvas.auto_fit_height = True

        GAP = 8  # pixels between stacked round images

        def _render():
            canvas.delete("all")
            self._sg_round_y_ranges = []
            self._sg_photo_refs = []

            cw = canvas.winfo_width()
            if cw <= 1:
                cw = 600

            y_cursor = 0
            total_width = 0

            for disp_pos in range(n_rounds):
                orig_idx = self._sg_round_order[disp_pos]
                pil_img = self._sg_round_images_base[orig_idx]
                ow, oh = pil_img.size
                nw = int(ow * canvas.zoom_level)
                nh = int(oh * canvas.zoom_level)
                scaled = pil_img.resize((nw, nh), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(scaled)
                self._sg_photo_refs.append(photo)

                xp = max(0, (cw - nw) // 2)
                canvas.create_image(xp, y_cursor, anchor=tk.NW, image=photo)
                self._sg_round_y_ranges.append((y_cursor, y_cursor + nh))
                total_width = max(total_width, nw)

                # Selection highlight — yellow border
                if disp_pos == self._sg_selected_round:
                    canvas.create_rectangle(
                        xp - 4,
                        y_cursor - 4,
                        xp + nw + 4,
                        y_cursor + nh + 4,
                        outline="#FED403",
                        width=5,
                    )

                y_cursor += nh + GAP

            canvas.configure(scrollregion=(0, 0, max(cw, total_width), y_cursor))

        def _fit_to_height():
            try:
                ch = canvas.winfo_height()
                if ch <= 1 or not self._sg_round_images_base:
                    return
                total_orig_h = sum(
                    img.size[1] for img in self._sg_round_images_base
                ) + GAP * max(0, n_rounds - 1)
                canvas.zoom_level = max((ch - 20) / total_orig_h, 0.1)
            except Exception:
                pass

        def _resize_event(event):
            if getattr(canvas, "auto_fit_height", False):
                _fit_to_height()
            _render()

        def _zoom_in():
            canvas.auto_fit_height = False
            canvas.zoom_level = min(canvas.zoom_level * 1.2, 5.0)
            _render()

        def _zoom_out():
            canvas.auto_fit_height = False
            canvas.zoom_level = max(canvas.zoom_level / 1.2, 0.1)
            _render()

        canvas.bind("<Configure>", _resize_event)

        def _initial_fit():
            canvas.update_idletasks()
            if canvas.winfo_height() <= 1:
                canvas.after(50, _initial_fit)
                return
            _fit_to_height()
            _render()

        canvas.after(2, _initial_fit)

        # ---- click-to-select / swap logic --------------------------------
        def _on_click(event):
            cy = canvas.canvasy(event.y)
            clicked = None
            for disp_pos, (y_top, y_bot) in enumerate(self._sg_round_y_ranges):
                if y_top <= cy < y_bot:
                    clicked = disp_pos
                    break

            if clicked is None:
                # Clicked outside any round — deselect
                self._sg_selected_round = None
                _render()
                return

            if self._sg_selected_round is None:
                # Select this round
                self._sg_selected_round = clicked
                _render()
            elif self._sg_selected_round == clicked:
                # Deselect
                self._sg_selected_round = None
                _render()
            else:
                # Swap the two rounds in display order
                a, b = self._sg_selected_round, clicked
                self._sg_round_order[a], self._sg_round_order[b] = (
                    self._sg_round_order[b],
                    self._sg_round_order[a],
                )
                self._sg_selected_round = None
                self._sg_has_pending_swaps = self._sg_round_order != list(
                    range(n_rounds)
                )
                _render()
                # Update button states and status label
                if self._sg_has_pending_swaps:
                    n_swapped = sum(
                        1 for i, v in enumerate(self._sg_round_order) if i != v
                    )
                    apply_btn.config(state=tk.NORMAL)
                    reset_btn.config(state=tk.NORMAL)
                    status_lbl.config(
                        text=f"{n_swapped} round(s)\nout of place",
                        fg=self.colors["accent_red"],
                    )
                else:
                    apply_btn.config(state=tk.DISABLED)
                    reset_btn.config(state=tk.DISABLED)
                    status_lbl.config(text="No pending swaps", fg="#555555")

        canvas.bind("<Button-1>", _on_click)

        # ---- reset button ------------------------------------------------
        def _reset_order():
            self._sg_round_order = list(range(n_rounds))
            self._sg_selected_round = None
            self._sg_has_pending_swaps = False
            apply_btn.config(state=tk.DISABLED)
            reset_btn.config(state=tk.DISABLED)
            status_lbl.config(text="No pending swaps", fg="#555555")
            _render()

        reset_btn.config(command=_reset_order)

        # ---- apply changes button ----------------------------------------
        def _apply_round_swaps():
            if not self._sg_has_pending_swaps:
                return

            apply_btn.config(state=tk.DISABLED)
            reset_btn.config(state=tk.DISABLED)

            # Warn if the Games Editor has pending player swaps
            has_editor_changes = bool(getattr(self, "pending_changes", []))
            if has_editor_changes:
                from tkinter import messagebox as _mb  # noqa: PLC0415

                if not _mb.askyesno(
                    "Pending Games Editor changes",
                    "The Games Editor has unapplied player swaps.\n"
                    "Applying the round swap will discard them.\n\n"
                    "Continue?",
                ):
                    apply_btn.config(state=tk.NORMAL)
                    reset_btn.config(state=tk.NORMAL)
                    return

            # Log the operation
            print("\n" + "=" * 80)
            print("APPLYING ROUND ORDER SWAP")
            orig_labels = " → ".join(f"R{orig + 1}" for orig in self._sg_round_order)
            print(f"New display order: {orig_labels}")
            print("=" * 80)

            # Reorder the rounds list on the live session object
            old_rounds = list(self.session_of_rounds.rounds)
            self.session_of_rounds.rounds = [
                old_rounds[orig_idx] for orig_idx in self._sg_round_order
            ]

            # Reset swap state (will be re-initialised by show_session_games_tab)
            self._sg_has_pending_swaps = False
            status_lbl.config(text="Applied!", fg="#1A6B2A")

            # Regenerate the session-games PNG and per-round images
            try:
                from core.charts import (  # noqa: PLC0415
                    create_session_games_png,
                    create_session_games_round_images,
                )

                create_session_games_png(
                    self.session_of_rounds,
                    png_path,
                    show_levels=self.png_show_levels_var.get(),
                )
                new_round_images = create_session_games_round_images(
                    self.session_of_rounds,
                    show_levels=self.png_show_levels_var.get(),
                )
                self.show_session_games_tab(png_path, round_images=new_round_images)
            except Exception as e:
                print(f"Warning: could not regenerate Session Games PNG: {e}")

            # Regenerate Games Editor (clears any stale pending player swaps)
            try:
                self.show_games_editor()
            except Exception as e:
                print(f"Warning: could not regenerate Games Editor: {e}")

            # Regenerate plots
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
                        main_module.create_all_session_charts(
                            self.session_of_rounds,
                            save_png=True,
                            png_dir=plots_dir,
                        )
                        self.show_plots_window(plots_dir)
                        print("Plots regenerated successfully.")
            except Exception as e:
                print(f"Warning: could not regenerate plots: {e}")

            print("=" * 80)
            print("ROUND ORDER APPLIED SUCCESSFULLY")
            print("=" * 80)

        apply_btn.config(command=_apply_round_swaps)

        # ---- mousewheel --------------------------------------------------
        def _wheel(event):
            if event.state & 0x0004:
                _zoom_in() if event.delta > 0 else _zoom_out()
                return "break"
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _shift_wheel(event):
            if event.state & 0x0001:
                canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")
                return "break"

        canvas.bind("<MouseWheel>", _wheel)
        canvas.bind("<Shift-MouseWheel>", _shift_wheel)
