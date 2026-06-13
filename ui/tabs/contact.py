"""Contact tab mixin for the main UI.

Provides `ContactTabMixin.show_contact_tab()` which adds a "Contact" tab
to `self.main_notebook`. The mixin uses `self.colors` and `self.fonts` when
available and falls back to sensible defaults.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser
from functools import partial


class ContactTabMixin:
    """Mixin that adds a Contact tab to the application's notebook.

    Host object (`self`) is expected to provide:
    - `self.main_notebook`: a `ttk.Notebook` instance
    - `self.colors`: optional dict of colors
    - `self.fonts`: optional dict of font tuples
    """

    def show_contact_tab(self):
        """Create (or recreate) a Contact tab and return the frame.

        The method is safe to call multiple times (it will remove any
        existing "Contact" tab before adding a new one).
        """
        # Remove existing Contact tab if present (by frame first, then by text).
        old_tab_frame = getattr(self, "_contact_tab_frame", None)
        if old_tab_frame is not None:
            try:
                if str(old_tab_frame) in self.main_notebook.tabs():
                    self.main_notebook.forget(old_tab_frame)
            except Exception:
                pass

        for tab_id in list(self.main_notebook.tabs()):
            try:
                tab_text = self.main_notebook.tab(tab_id, "text").strip().lower()
                if tab_text.endswith("contact"):
                    self.main_notebook.forget(tab_id)
                    break
            except Exception:
                # defensive: ignore widgets we can't inspect
                pass

        colors = getattr(self, "colors", {}) or {}
        fonts = getattr(self, "fonts", {}) or {}

        bg = colors.get("bg_light", "#FFFFFF")
        header_fg = colors.get("accent_yellow", "#FED403")
        card_bg = colors.get("bg_light", "#F6F6F6")
        text_fg = colors.get("text_dark", "#000000")

        heading_font = fonts.get("huge", ("Arial", 18, "bold"))
        label_font = fonts.get("normal_bold", ("Arial", 12, "bold"))
        value_font = fonts.get("small", ("Arial", 11))

        parent = self.main_notebook

        tab_frame = tk.Frame(parent, bg=bg)
        parent.add(tab_frame, text="Contact")
        self._contact_tab_frame = tab_frame

        # Header
        header_container = tk.Frame(tab_frame, bg=bg)
        header_container.pack(side=tk.TOP, pady=(14, 6))
        tk.Label(
            header_container,
            text="CONTACT",
            font=heading_font,
            fg=header_fg,
            bg=bg,
        ).pack()
        tk.Label(
            header_container,
            text="This is a small open source project.\nWanna Contribute? Reach out!",
            font=value_font,
            fg=text_fg,
            bg=bg,
        ).pack()

        # Centered card
        card_outer = tk.Frame(tab_frame, bg=bg)
        card_outer.pack(fill=tk.BOTH, expand=True)

        card = tk.Frame(
            card_outer,
            bg=card_bg,
            bd=1,
            relief=tk.SOLID,
            padx=18,
            pady=12,
        )
        card.place(relx=0.5, rely=0.15, anchor=tk.N)

        # Default / placeholder contact info — user can edit these values
        contact = {
            "Name": "Victor DANIEL",
            "Role": "Developer / Maintainer",
            "Email": "daniel.victor.samuel@gmail.com",
            "GitHub": "https://github.com/victorsamueldaniel/RoundnetMatchmaking",
        }

        # Helper actions
        def _copy_to_clipboard(text, label):
            try:
                # Use main_notebook as clipboard owner; it's a widget
                parent.clipboard_clear()
                parent.clipboard_append(text)
            except Exception as exc:  # pragma: no cover - UI feedback
                messagebox.showerror("Copy failed", f"Failed to copy {label}:\n{exc}")

        def _open_mailto(address):
            try:
                webbrowser.open(f"mailto:{address}", new=2)
            except Exception as exc:  # pragma: no cover - UI feedback
                messagebox.showerror(
                    "Open failed", f"Failed to open mail client:\n{exc}"
                )

        def _open_url(url):
            try:
                webbrowser.open(url, new=2)
            except Exception as exc:  # pragma: no cover - UI feedback
                messagebox.showerror("Open failed", f"Failed to open URL:\n{exc}")

        # Build rows inside the card
        for r_idx, (key, val) in enumerate(contact.items()):
            lbl = tk.Label(
                card, text=f"{key}:", bg=card_bg, fg=text_fg, font=label_font
            )
            lbl.grid(row=r_idx, column=0, sticky=tk.W, padx=(0, 12), pady=6)

            val_lbl = tk.Label(card, text=val, bg=card_bg, fg=text_fg, font=value_font)
            val_lbl.grid(row=r_idx, column=1, sticky=tk.W, pady=6)

            actions = tk.Frame(card, bg=card_bg)
            actions.grid(row=r_idx, column=2, sticky=tk.E, padx=(12, 0))

            copy_btn = ttk.Button(
                actions,
                text="Copy",
                width=7,
                command=partial(_copy_to_clipboard, val, key),
            )
            copy_btn.pack(side=tk.LEFT, padx=(0, 6))

            if key == "Email":
                mail_btn = ttk.Button(
                    actions, text="Email", width=7, command=partial(_open_mailto, val)
                )
                mail_btn.pack(side=tk.LEFT)
            elif key in ("Website", "GitHub"):
                open_btn = ttk.Button(
                    actions, text="Open", width=7, command=partial(_open_url, val)
                )
                open_btn.pack(side=tk.LEFT)
            elif key == "Phone":
                call_btn = ttk.Button(
                    actions,
                    text="Call",
                    width=7,
                    command=partial(_open_url, f"tel:{val}"),
                )
                call_btn.pack(side=tk.LEFT)

        # Layout tuning
        for c in range(3):
            card.grid_columnconfigure(c, weight=1)

        # ── Bug report section ─────────────────────────────────────────
        bug_section = tk.Frame(card_outer, bg=bg)
        bug_section.place(relx=0.5, rely=0.72, anchor=tk.CENTER)

        tk.Frame(
            bug_section, bg=colors.get("accent_yellow", "#FED403"), height=1, width=340
        ).pack(fill=tk.X, pady=(0, 10))
        tk.Label(
            bug_section,
            text="Found a bug?",
            font=label_font,
            fg=colors.get("text_dark", "#000000"),
            bg=bg,
        ).pack()
        tk.Label(
            bug_section,
            text=(
                "Click below to package the app log, session files, and settings\n"
                "into a BUG/ folder. Attach that folder when opening a GitHub issue."
            ),
            font=value_font,
            fg=colors.get("text_dark", "#000000"),
            bg=bg,
            justify=tk.CENTER,
        ).pack(pady=(4, 10))

        def _on_create_bug_report():
            try:
                from ui.functions.bug_reporter import (
                    collect_bug_report,
                )  # noqa: PLC0415

                pkg_dir = collect_bug_report(self)
                messagebox.showinfo(
                    "Bug Report Created",
                    f"Bug report saved to:\n{pkg_dir}\n\n"
                    "Please attach this folder when opening a GitHub issue.",
                )
            except Exception as exc:
                messagebox.showerror("Bug Report Failed", str(exc))

        ttk.Button(
            bug_section,
            text="Create Bug Report",
            command=_on_create_bug_report,
        ).pack()

        # Keep Contact as the last tab and paint its tab area in black.
        self._configure_contact_tab_behavior()
        self._ensure_contact_tab_last()

        return tab_frame

    def _configure_contact_tab_behavior(self):
        """Configure styling and event bindings for contact-tab behavior."""
        if getattr(self, "_contact_tab_behavior_bound", False):
            self._render_contact_tab_overlay()
            return

        def _on_notebook_event(_event=None):
            self._ensure_contact_tab_last()

        self.main_notebook.bind("<<NotebookTabChanged>>", _on_notebook_event, add="+")
        self.main_notebook.bind("<Configure>", _on_notebook_event, add="+")
        self._contact_tab_behavior_bound = True
        self._render_contact_tab_overlay()

    def _render_contact_tab_overlay(self):
        """Render a black overlay exactly on top of the Contact notebook tab."""
        tab_frame = getattr(self, "_contact_tab_frame", None)
        if tab_frame is None:
            return

        try:
            if (
                not hasattr(self, "_contact_tab_overlay")
                or self._contact_tab_overlay is None
            ):
                self._contact_tab_overlay = tk.Label(
                    self.main_notebook,
                    text="Contact",
                    bg="#000000",
                    fg="#FFFFFF",
                    bd=0,
                    cursor="hand2",
                    padx=8,
                    pady=2,
                )
                self._contact_tab_overlay.bind(
                    "<Button-1>",
                    lambda _e: self.main_notebook.select(self._contact_tab_frame),
                )

            bbox = self.main_notebook.bbox(tab_frame)
            if bbox and len(bbox) == 4:
                x, y, w, h = bbox
                self._contact_tab_overlay.place(
                    in_=self.main_notebook, x=x, y=y, width=w, height=h
                )
                self._contact_tab_overlay.lift()
            else:
                self._contact_tab_overlay.place_forget()
        except Exception:
            pass

    def _ensure_contact_tab_last(self):
        """Move Contact tab to the end so it remains last as tabs are added."""
        tab_frame = getattr(self, "_contact_tab_frame", None)
        if tab_frame is None:
            return

        try:
            tabs = list(self.main_notebook.tabs())
            tab_id = str(tab_frame)
            if tab_id not in tabs:
                return
            if tabs[-1] != tab_id:
                self.main_notebook.insert("end", tab_frame)
            self._render_contact_tab_overlay()
        except Exception:
            pass
