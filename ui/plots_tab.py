"""Plots tab controller."""

import os

import tkinter as tk
from PIL import Image, ImageTk

from ui.tab_functions import plots_find_png_files


class PlotsTabMixin:
    def show_plots_window(self, plots_dir):
        """Add plot tabs to the main notebook"""
        # Remove existing plot tabs (keep Session Generation at index 0, Session Games
        # at index 1 if it exists, and Games Editor if it exists)
        games_editor_exists = False
        session_games_exists = False
        for i, tab_id in enumerate(self.main_notebook.tabs()):
            tab_text = self.main_notebook.tab(tab_id, "text")
            if tab_text == "Games Editor":
                games_editor_exists = True
            if tab_text == "Session Games":
                session_games_exists = True

        # Keep: Session Generation (always), Session Games (if present), Games Editor (if present)
        num_tabs_to_keep = 1 + int(session_games_exists) + int(games_editor_exists)
        while len(self.main_notebook.tabs()) > num_tabs_to_keep:
            self.main_notebook.forget(num_tabs_to_keep)

        # Find all PNG files in the plots directory
        png_files = plots_find_png_files(plots_dir)

        if not png_files:
            print("No plot files found to display.")
            return

        # Create a tab for each PNG file
        for png_file in sorted(png_files):
            # Get filename without path and extension for tab label
            filename = os.path.basename(png_file)
            tab_name = os.path.splitext(filename)[0].replace("_", " ").title()

            # Create frame for this tab
            tab_frame = tk.Frame(self.main_notebook, bg=self.colors["bg_light"])
            self.main_notebook.add(tab_frame, text=tab_name)

            # Add centered title at the top
            title_label = tk.Label(
                tab_frame,
                text=tab_name,
                font=self.fonts["big"],
                fg=self.colors["accent_red"],
                bg=self.colors["bg_light"],
            )
            title_label.pack(side=tk.TOP, pady=(20, 10))

            # Create canvas with scrollbars for the image
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

            # Pack scrollbars and canvas
            h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
            v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

            # Initialize zoom level
            canvas.zoom_level = 1.0
            canvas.auto_fit_width = True

            # Load and display image
            try:
                img = Image.open(png_file)

                # Store original image for resizing
                canvas.original_image = img
                canvas.png_file = png_file

                # Create functions with proper closure (wrapping in a factory function)
                def make_image_functions(cnv):
                    def fit_to_width():
                        try:
                            canvas_width = cnv.winfo_width()
                            if canvas_width <= 1:
                                return

                            original_width, _ = cnv.original_image.size
                            # Small margin so image does not touch edges
                            cnv.zoom_level = max(
                                (canvas_width - 20) / original_width, 0.1
                            )
                        except Exception:
                            pass

                    # Function to update image with current zoom level
                    def update_image():
                        try:
                            # Get canvas dimensions
                            canvas_width = cnv.winfo_width()
                            canvas_height = cnv.winfo_height()

                            if canvas_width <= 1 or canvas_height <= 1:
                                return

                            # Calculate new dimensions maintaining aspect ratio
                            original_width, original_height = cnv.original_image.size

                            # Apply zoom
                            new_width = int(original_width * cnv.zoom_level)
                            new_height = int(original_height * cnv.zoom_level)

                            # Resize image
                            resized_img = cnv.original_image.resize(
                                (new_width, new_height), Image.Resampling.LANCZOS
                            )
                            photo = ImageTk.PhotoImage(resized_img)

                            # Update canvas - center the image
                            cnv.delete("all")

                            # Calculate position to center the image
                            x_pos = max(0, (canvas_width - new_width) // 2)
                            y_pos = max(0, (canvas_height - new_height) // 2)

                            cnv.create_image(x_pos, y_pos, anchor=tk.NW, image=photo)
                            cnv.image = photo  # Keep a reference

                            # Configure scroll region to allow scrolling if image is larger than canvas
                            scroll_x0 = min(0, x_pos)
                            scroll_y0 = min(0, y_pos)
                            scroll_x1 = max(canvas_width, x_pos + new_width)
                            scroll_y1 = max(canvas_height, y_pos + new_height)
                            cnv.configure(
                                scrollregion=(
                                    scroll_x0,
                                    scroll_y0,
                                    scroll_x1,
                                    scroll_y1,
                                )
                            )
                        except Exception as e:
                            print(f"Error updating image: {e}")

                    # Function to resize and display image to fit canvas height
                    def resize_image(event):
                        if getattr(cnv, "auto_fit_width", False):
                            fit_to_width()
                        update_image()

                    # Zoom in function
                    def zoom_in():
                        cnv.auto_fit_width = False
                        cnv.zoom_level = min(cnv.zoom_level * 1.2, 5.0)  # Max 500%
                        update_image()

                    # Zoom out function
                    def zoom_out():
                        cnv.auto_fit_width = False
                        cnv.zoom_level = max(cnv.zoom_level / 1.2, 0.1)  # Min 10%
                        update_image()

                    return update_image, resize_image, zoom_in, zoom_out

                # Create the functions for this specific canvas
                update_image, resize_image, zoom_in, zoom_out = make_image_functions(
                    canvas
                )

                # Bind canvas resize event
                canvas.bind("<Configure>", resize_image)

                # Fit to width initially - with better timing and proper closure
                def make_fit_function(cnv, update_func):
                    def fit_to_width_on_load():
                        # Wait for the canvas to be fully rendered
                        cnv.update_idletasks()
                        canvas_width = cnv.winfo_width()

                        # If canvas isn't rendered yet, try again
                        if canvas_width <= 1:
                            cnv.after(50, fit_to_width_on_load)
                            return

                        original_width, _ = cnv.original_image.size
                        # Subtract a small margin to ensure it fills the available horizontal area
                        cnv.zoom_level = max((canvas_width - 20) / original_width, 0.1)
                        update_func()

                    return fit_to_width_on_load

                fit_to_width_on_load = make_fit_function(canvas, update_image)

                # Schedule fit to width after window is drawn with multiple attempts
                canvas.after(2, fit_to_width_on_load)

                # Bind mouse wheel for zooming (with Ctrl key) - with proper closure
                def make_mousewheel_functions(cnv, zoom_in_func, zoom_out_func):
                    def on_mousewheel_zoom(event):
                        if event.state & 0x0004:  # Ctrl key is pressed
                            if event.delta > 0:
                                zoom_in_func()
                            else:
                                zoom_out_func()
                            return "break"
                        else:
                            # Regular scroll (vertical)
                            cnv.yview_scroll(int(-1 * (event.delta / 120)), "units")

                    def on_shift_mousewheel(event):
                        if event.state & 0x0001:  # Shift key is pressed
                            cnv.xview_scroll(int(-1 * (event.delta / 120)), "units")
                            return "break"

                    return on_mousewheel_zoom, on_shift_mousewheel

                on_mousewheel_zoom, on_shift_mousewheel = make_mousewheel_functions(
                    canvas, zoom_in, zoom_out
                )

                canvas.bind("<MouseWheel>", on_mousewheel_zoom)
                canvas.bind("<Shift-MouseWheel>", on_shift_mousewheel)

            except Exception as e:
                # If image loading fails, show error message
                error_label = tk.Label(
                    tab_frame,
                    text=f"Error loading image:\n{str(e)}",
                    font=self.fonts["normal"],
                    fg="red",
                    bg=self.colors["bg_light"],
                )
                error_label.pack(expand=True)

        print(f"Added {len(png_files)} plot tabs to main window.")
