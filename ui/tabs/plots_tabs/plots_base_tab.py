"""Shared image-tab rendering logic for plot tabs."""

import tkinter as tk
from PIL import Image, ImageTk


class PlotsBaseTabMixin:
    def _add_plot_image_tab(self, png_file, tab_name):
        """Add one image-based plot tab with zoom and scroll support."""
        tab_frame = tk.Frame(self.main_notebook, bg=self.colors["bg_light"])
        self.main_notebook.add(tab_frame, text=tab_name)

        title_label = tk.Label(
            tab_frame,
            text=tab_name,
            font=self.fonts["big"],
            fg=self.colors["accent_red"],
            bg=self.colors["bg_light"],
        )
        title_label.pack(side=tk.TOP, pady=(20, 10))

        canvas = tk.Canvas(tab_frame, bg=self.colors["bg_light"])
        h_scrollbar = tk.Scrollbar(
            tab_frame, orient=tk.HORIZONTAL, command=canvas.xview
        )
        v_scrollbar = tk.Scrollbar(tab_frame, orient=tk.VERTICAL, command=canvas.yview)

        canvas.configure(xscrollcommand=h_scrollbar.set, yscrollcommand=v_scrollbar.set)

        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        canvas.zoom_level = 1.0
        canvas.auto_fit_width = True

        try:
            img = Image.open(png_file)

            canvas.original_image = img
            canvas.png_file = png_file

            def make_image_functions(cnv):
                def fit_to_width():
                    try:
                        canvas_width = cnv.winfo_width()
                        if canvas_width <= 1:
                            return

                        original_width, _ = cnv.original_image.size
                        cnv.zoom_level = max((canvas_width - 20) / original_width, 0.1)
                    except Exception:
                        pass

                def update_image():
                    try:
                        canvas_width = cnv.winfo_width()
                        canvas_height = cnv.winfo_height()

                        if canvas_width <= 1 or canvas_height <= 1:
                            return

                        original_width, original_height = cnv.original_image.size
                        new_width = int(original_width * cnv.zoom_level)
                        new_height = int(original_height * cnv.zoom_level)

                        resized_img = cnv.original_image.resize(
                            (new_width, new_height), Image.Resampling.LANCZOS
                        )
                        photo = ImageTk.PhotoImage(resized_img)

                        cnv.delete("all")

                        x_pos = max(0, (canvas_width - new_width) // 2)
                        y_pos = max(0, (canvas_height - new_height) // 2)

                        cnv.create_image(x_pos, y_pos, anchor=tk.NW, image=photo)
                        cnv.image = photo

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

                def resize_image(event):
                    if getattr(cnv, "auto_fit_width", False):
                        fit_to_width()
                    update_image()

                def zoom_in():
                    cnv.auto_fit_width = False
                    cnv.zoom_level = min(cnv.zoom_level * 1.2, 5.0)
                    update_image()

                def zoom_out():
                    cnv.auto_fit_width = False
                    cnv.zoom_level = max(cnv.zoom_level / 1.2, 0.1)
                    update_image()

                return update_image, resize_image, zoom_in, zoom_out

            update_image, resize_image, zoom_in, zoom_out = make_image_functions(canvas)

            canvas.bind("<Configure>", resize_image)

            def make_fit_function(cnv, update_func):
                def fit_to_width_on_load():
                    cnv.update_idletasks()
                    canvas_width = cnv.winfo_width()

                    if canvas_width <= 1:
                        cnv.after(50, fit_to_width_on_load)
                        return

                    original_width, _ = cnv.original_image.size
                    cnv.zoom_level = max((canvas_width - 20) / original_width, 0.1)
                    update_func()

                return fit_to_width_on_load

            fit_to_width_on_load = make_fit_function(canvas, update_image)
            canvas.after(2, fit_to_width_on_load)

            def make_mousewheel_functions(cnv, zoom_in_func, zoom_out_func):
                def on_mousewheel_zoom(event):
                    if event.state & 0x0004:
                        if event.delta > 0:
                            zoom_in_func()
                        else:
                            zoom_out_func()
                        return "break"
                    cnv.yview_scroll(int(-1 * (event.delta / 120)), "units")

                def on_shift_mousewheel(event):
                    if event.state & 0x0001:
                        cnv.xview_scroll(int(-1 * (event.delta / 120)), "units")
                        return "break"

                return on_mousewheel_zoom, on_shift_mousewheel

            on_mousewheel_zoom, on_shift_mousewheel = make_mousewheel_functions(
                canvas, zoom_in, zoom_out
            )

            canvas.bind("<MouseWheel>", on_mousewheel_zoom)
            canvas.bind("<Shift-MouseWheel>", on_shift_mousewheel)

        except Exception as e:
            error_label = tk.Label(
                tab_frame,
                text=f"Error loading image:\n{str(e)}",
                font=self.fonts["normal"],
                fg="red",
                bg=self.colors["bg_light"],
            )
            error_label.pack(expand=True)
