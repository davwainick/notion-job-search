"""
gui.py — Tkinter GUI for notion-job-search.

Provides a three-screen workflow:

  Screen 1 — Returning-user mode (shown when saved workspaces exist):
    Lists previously created workspaces with Open / Create New / Delete buttons.

  Screen 2 — Setup / first-run mode:
    Token, parent page ID, workspace name inputs plus optional seed data checkbox.
    Runs the workspace build in a background thread with live progress updates.

  Screen 3 — Gap Analysis input:
    Dynamic form for the user to enter their strengths and
    gap/objection/rebuttal rows before opening Notion.

Entry point is :func:`main`, which is also used as the PyInstaller target.
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
import webbrowser
from datetime import datetime
from tkinter import messagebox, ttk
from typing import Any

# ---------------------------------------------------------------------------
# Colour / font constants
# ---------------------------------------------------------------------------
BG = "#1e1e2e"
BG_CARD = "#2a2a3e"
FG = "#cdd6f4"
FG_DIM = "#6c7086"
ACCENT = "#89b4fa"
ACCENT2 = "#a6e3a1"
ERROR = "#f38ba8"
FONT_BODY = ("Segoe UI", 11)
FONT_SMALL = ("Segoe UI", 9)
FONT_HEADING = ("Segoe UI", 14, "bold")
FONT_TITLE = ("Segoe UI", 18, "bold")
PAD = 12


def _link_label(parent: tk.Widget, text: str, url: str) -> tk.Label:
    """
    Create a clickable hyperlink label.

    Args:
        parent: Parent widget.
        text:   Displayed link text.
        url:    URL to open on click.

    Returns:
        Configured :class:`tk.Label` widget.
    """
    lbl = tk.Label(
        parent,
        text=text,
        font=FONT_SMALL,
        fg=ACCENT,
        bg=BG_CARD,
        cursor="hand2",
        underline=True,
    )
    lbl.bind("<Button-1>", lambda _e: webbrowser.open(url))
    return lbl


def _entry(parent: tk.Widget, show: str = "") -> tk.Entry:
    """
    Create a styled text entry widget.

    Args:
        parent: Parent widget.
        show:   Character to display instead of actual input (e.g. ``"*"``).

    Returns:
        Configured :class:`tk.Entry` widget.
    """
    return tk.Entry(
        parent,
        font=FONT_BODY,
        bg=BG_CARD,
        fg=FG,
        insertbackground=FG,
        relief=tk.FLAT,
        show=show,
        highlightthickness=1,
        highlightbackground=FG_DIM,
        highlightcolor=ACCENT,
    )


def _button(
    parent: tk.Widget,
    text: str,
    command: Any,
    accent: bool = False,
) -> tk.Button:
    """
    Create a styled button widget.

    Args:
        parent:  Parent widget.
        text:    Button label.
        command: Callback function.
        accent:  If *True*, use the accent colour for the background.

    Returns:
        Configured :class:`tk.Button` widget.
    """
    bg_col = ACCENT if accent else BG_CARD
    fg_col = BG if accent else FG
    return tk.Button(
        parent,
        text=text,
        command=command,
        font=FONT_BODY,
        bg=bg_col,
        fg=fg_col,
        activebackground=ACCENT2,
        activeforeground=BG,
        relief=tk.FLAT,
        padx=PAD,
        pady=6,
        cursor="hand2",
    )


def _label(
    parent: tk.Widget,
    text: str,
    font: tuple = FONT_BODY,
    fg: str = FG,
    wraplength: int = 0,
) -> tk.Label:
    """
    Create a styled label widget.

    Args:
        parent:     Parent widget.
        text:       Label text.
        font:       Font tuple.
        fg:         Foreground colour.
        wraplength: Pixel width at which text wraps (0 = no wrap).

    Returns:
        Configured :class:`tk.Label` widget.
    """
    kwargs: dict[str, Any] = dict(
        text=text, font=font, bg=BG, fg=fg
    )
    if wraplength:
        kwargs["wraplength"] = wraplength
        kwargs["justify"] = tk.LEFT
    return tk.Label(parent, **kwargs)


# ---------------------------------------------------------------------------
# Main application class
# ---------------------------------------------------------------------------

class NotionJobSearchApp:
    """
    Main Tkinter application.

    Manages three screens as frames that are destroyed and rebuilt on each
    transition rather than using a notebook or stacked frames, keeping the
    widget tree simple.
    """

    def __init__(self, root: tk.Tk) -> None:
        """
        Initialise the application.

        Args:
            root: The root :class:`tk.Tk` window.
        """
        self.root = root
        self.root.configure(bg=BG)
        self.root.resizable(True, True)
        self.root.minsize(560, 400)

        # Shared state set during the build flow
        self._build_result: dict[str, str] = {}
        self._token: str = ""
        self._parent_page_id: str = ""
        self._workspace_name: str = ""
        self._seed_data: bool = False

        # Current frame (destroyed on each screen transition)
        self._frame: tk.Frame | None = None

        # Decide which screen to show on launch
        from .state import has_workspaces
        if has_workspaces():
            self._show_workspace_list()
        else:
            self._show_setup()

    # -----------------------------------------------------------------------
    # Screen management helper
    # -----------------------------------------------------------------------

    def _clear(self) -> tk.Frame:
        """Destroy the current frame and return a fresh one."""
        if self._frame is not None:
            self._frame.destroy()
        self._frame = tk.Frame(self.root, bg=BG, padx=PAD * 2, pady=PAD * 2)
        self._frame.pack(fill=tk.BOTH, expand=True)
        return self._frame

    # -----------------------------------------------------------------------
    # Screen 1 — Workspace list (returning-user mode)
    # -----------------------------------------------------------------------

    def _show_workspace_list(self) -> None:
        """Render the returning-user workspace list screen."""
        self.root.title("Notion Job Search")
        frame = self._clear()

        _label(frame, "Notion Job Search", font=FONT_TITLE).pack(anchor=tk.W)
        _label(
            frame,
            "Your saved workspaces:",
            font=FONT_BODY,
            fg=FG_DIM,
        ).pack(anchor=tk.W, pady=(4, PAD))

        # Listbox with scrollbar
        list_frame = tk.Frame(frame, bg=BG)
        list_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._listbox = tk.Listbox(
            list_frame,
            font=FONT_BODY,
            bg=BG_CARD,
            fg=FG,
            selectbackground=ACCENT,
            selectforeground=BG,
            relief=tk.FLAT,
            activestyle="none",
            yscrollcommand=scrollbar.set,
            height=8,
        )
        self._listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self._listbox.yview)

        self._refresh_listbox()

        # Buttons
        btn_frame = tk.Frame(frame, bg=BG)
        btn_frame.pack(fill=tk.X, pady=(PAD, 0))

        _button(btn_frame, "Open in Notion", self._open_selected, accent=True).pack(
            side=tk.LEFT, padx=(0, 8)
        )
        _button(btn_frame, "Create New Workspace", self._show_setup).pack(
            side=tk.LEFT, padx=(0, 8)
        )
        _button(btn_frame, "Delete", self._delete_selected).pack(side=tk.LEFT)

    def _refresh_listbox(self) -> None:
        """Reload workspace entries into the listbox."""
        from .state import load_workspaces

        self._workspaces = load_workspaces()
        self._listbox.delete(0, tk.END)
        for ws in self._workspaces:
            created = ws.get("created_at", "")[:10]
            self._listbox.insert(tk.END, f"  {ws.get('name', 'Untitled')}   —   {created}")
        if self._workspaces:
            self._listbox.selection_set(0)

    def _open_selected(self) -> None:
        """Open the selected workspace in the browser."""
        sel = self._listbox.curselection()
        if not sel:
            messagebox.showwarning("No selection", "Please select a workspace first.")
            return
        ws = self._workspaces[sel[0]]
        url = ws.get("notion_url", "")
        if url:
            webbrowser.open(url)
        else:
            messagebox.showerror("No URL", "This workspace has no stored URL.")

    def _delete_selected(self) -> None:
        """Remove the selected workspace from the state file."""
        sel = self._listbox.curselection()
        if not sel:
            messagebox.showwarning("No selection", "Please select a workspace to delete.")
            return
        idx = sel[0]
        name = self._workspaces[idx].get("name", "this workspace")
        if not messagebox.askyesno(
            "Confirm delete",
            f"Remove '{name}' from the list?\n\n"
            "This does NOT delete the workspace in Notion.",
        ):
            return
        from .state import delete_workspace
        delete_workspace(idx)
        self._refresh_listbox()

    # -----------------------------------------------------------------------
    # Screen 2 — Setup / first-run
    # -----------------------------------------------------------------------

    def _show_setup(self, show_back: bool | None = None) -> None:
        """Render the setup screen."""
        from .state import has_workspaces

        self.root.title("Notion Job Search — Setup")
        frame = self._clear()

        if show_back is None:
            show_back = has_workspaces()

        if show_back:
            _button(frame, "← Back", self._show_workspace_list).pack(
                anchor=tk.W, pady=(0, PAD)
            )

        _label(frame, "Create a New Workspace", font=FONT_TITLE).pack(anchor=tk.W)
        _label(
            frame,
            "Connect your Notion account and name your job-search workspace.",
            fg=FG_DIM,
            wraplength=520,
        ).pack(anchor=tk.W, pady=(4, PAD))

        # ---- Token field ----
        tk.Frame(frame, bg=BG, height=1).pack(fill=tk.X)
        _label(frame, "Notion Integration Token").pack(anchor=tk.W)
        _link_label(
            frame,
            "How do I get this?  →  notion.so/my-integrations",
            "https://www.notion.so/my-integrations",
        ).pack(anchor=tk.W, pady=(0, 4))
        self._token_var = tk.StringVar()
        token_entry = _entry(frame, show="•")
        token_entry.config(textvariable=self._token_var)
        token_entry.pack(fill=tk.X, pady=(0, PAD))

        # ---- Parent page ID ----
        _label(frame, "Parent Page ID").pack(anchor=tk.W)
        _label(
            frame,
            "Found in your Notion page URL:  notion.so/workspace/ THIS-PART",
            font=FONT_SMALL,
            fg=FG_DIM,
        ).pack(anchor=tk.W, pady=(0, 4))
        self._parent_var = tk.StringVar()
        parent_entry = _entry(frame)
        parent_entry.config(textvariable=self._parent_var)
        parent_entry.pack(fill=tk.X, pady=(0, PAD))

        # ---- Workspace name ----
        _label(frame, "Workspace Name").pack(anchor=tk.W)
        self._name_var = tk.StringVar(value="Job Search HQ")
        name_entry = _entry(frame)
        name_entry.config(textvariable=self._name_var)
        name_entry.pack(fill=tk.X, pady=(0, PAD))

        # ---- Seed data checkbox ----
        self._seed_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            frame,
            text="Add 3 sample company rows (Acme Corp, Example Inc, Sample Co)",
            variable=self._seed_var,
            font=FONT_BODY,
            bg=BG,
            fg=FG,
            selectcolor=BG_CARD,
            activebackground=BG,
            activeforeground=FG,
        ).pack(anchor=tk.W, pady=(0, PAD))

        # ---- Create button ----
        self._create_btn = _button(
            frame, "Create Workspace", self._start_build, accent=True
        )
        self._create_btn.pack(anchor=tk.W, pady=(0, 8))

        # ---- Progress / error labels ----
        self._progress_var = tk.StringVar(value="")
        tk.Label(
            frame,
            textvariable=self._progress_var,
            font=FONT_SMALL,
            bg=BG,
            fg=ACCENT2,
            wraplength=520,
            justify=tk.LEFT,
        ).pack(anchor=tk.W)

        self._error_var = tk.StringVar(value="")
        tk.Label(
            frame,
            textvariable=self._error_var,
            font=FONT_SMALL,
            bg=BG,
            fg=ERROR,
            wraplength=520,
            justify=tk.LEFT,
        ).pack(anchor=tk.W)

    def _start_build(self) -> None:
        """Validate inputs and kick off the workspace build in a background thread."""
        import re

        token = self._token_var.get().strip()
        name = self._name_var.get().strip() or "Job Search HQ"
        seed = self._seed_var.get()

        # Clean the parent page ID thoroughly:
        # strip whitespace, surrounding quotes, and handle full Notion URLs
        raw_parent = self._parent_var.get().strip().strip('"').strip("'")

        # If the user pasted a full Notion URL, extract just the ID portion
        # e.g. https://notion.so/myworkspace/PageTitle-1a2b3c4d5e6f7a8b9c0d...
        if "notion.so" in raw_parent:
            last_segment = raw_parent.rstrip("/").split("/")[-1].split("?")[0]
            hex_match = re.search(r"([0-9a-fA-F]{32})$", last_segment.replace("-", ""))
            if hex_match:
                raw_parent = hex_match.group(1)
            else:
                raw_parent = last_segment

        # Remove hyphens — Notion accepts both hyphenated and bare UUID formats
        parent_id = raw_parent.replace("-", "").strip()

        if not token:
            self._error_var.set("❌ Please enter your Notion integration token.")
            return
        if not parent_id:
            self._error_var.set("❌ Please enter the parent page ID.")
            return
        if len(parent_id) != 32:
            self._error_var.set(
                f"❌ Page ID looks wrong — got {len(parent_id)} characters "
                f"after cleaning (expected 32).\n"
                f"Cleaned value: '{parent_id}'\n"
                "Tip: copy only the ID from your Notion URL, not the full URL."
            )
            return

        self._token = token
        self._parent_page_id = parent_id
        self._workspace_name = name
        self._seed_data = seed

        self._create_btn.config(state=tk.DISABLED)
        self._error_var.set("")
        self._progress_var.set("⏳ Starting …")

        q: queue.Queue[tuple[str, Any]] = queue.Queue()

        def worker() -> None:
            try:
                from .builder import build_workspace
                from .client import get_client

                client = get_client(token)
                result = build_workspace(
                    client,
                    parent_id,
                    name,
                    dry_run=False,
                    seed_data=seed,
                    progress_callback=lambda msg: q.put(("progress", msg)),
                )
                q.put(("done", result))
            except Exception as exc:  # noqa: BLE001
                q.put(("error", str(exc)))

        threading.Thread(target=worker, daemon=True).start()
        self._poll_queue(q)

    def _poll_queue(self, q: queue.Queue) -> None:
        """
        Poll the build thread's queue and update the UI.

        Args:
            q: Queue receiving ``("progress", msg)``, ``("done", result)``,
               or ``("error", msg)`` tuples from the worker thread.
        """
        try:
            while True:
                kind, payload = q.get_nowait()
                if kind == "progress":
                    self._progress_var.set(payload.strip())
                elif kind == "done":
                    self._build_result = payload
                    self._progress_var.set("✅ Workspace created!")
                    self._show_gap_analysis_input()
                    return
                elif kind == "error":
                    self._error_var.set(f"❌ {payload}")
                    self._create_btn.config(state=tk.NORMAL)
                    self._progress_var.set("")
                    return
        except queue.Empty:
            pass
        self.root.after(100, lambda: self._poll_queue(q))

    # -----------------------------------------------------------------------
    # Screen 3 — Gap Analysis input
    # -----------------------------------------------------------------------

    def _show_gap_analysis_input(self) -> None:
        """Render the Gap Analysis data-entry screen."""
        self.root.title("Notion Job Search — Gap Analysis")
        self.root.minsize(620, 520)
        frame = self._clear()

        _label(frame, "Set Up Your Gap Analysis", font=FONT_TITLE).pack(anchor=tk.W)
        _label(
            frame,
            "Your workspace was created! Fill in your strengths and any objections "
            "you want to prepare for now, or skip and edit the page directly in Notion later.",
            fg=FG_DIM,
            wraplength=580,
        ).pack(anchor=tk.W, pady=(4, PAD))

        # Scrollable canvas for the dynamic rows
        canvas = tk.Canvas(frame, bg=BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(frame, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        inner = tk.Frame(canvas, bg=BG)
        canvas_window = canvas.create_window((0, 0), window=inner, anchor=tk.NW)

        def _on_configure(event: tk.Event) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(canvas_window, width=event.width)

        inner.bind("<Configure>", _on_configure)
        canvas.bind("<Configure>", _on_configure)

        # ---- Strengths section ----
        _label(inner, "💪 Strengths to Lead With", font=FONT_HEADING).pack(
            anchor=tk.W, pady=(0, 4)
        )
        _label(
            inner,
            "List the skills, experience, and credentials you will lead with.",
            fg=FG_DIM,
            wraplength=560,
        ).pack(anchor=tk.W, pady=(0, 8))

        self._strength_rows: list[dict[str, tk.StringVar]] = []
        strength_container = tk.Frame(inner, bg=BG)
        strength_container.pack(fill=tk.X, pady=(0, 8))

        def add_strength_row(
            strength: str = "", talking_point: str = ""
        ) -> None:
            row_frame = tk.Frame(strength_container, bg=BG_CARD, pady=6, padx=8)
            row_frame.pack(fill=tk.X, pady=3)

            sv = tk.StringVar(value=strength)
            tp = tk.StringVar(value=talking_point)
            self._strength_rows.append({"strength": sv, "talking_point": tp})

            tk.Label(row_frame, text="Strength:", font=FONT_SMALL, bg=BG_CARD, fg=FG_DIM).grid(
                row=0, column=0, sticky=tk.W, padx=(0, 6)
            )
            e1 = _entry(row_frame)
            e1.config(textvariable=sv)
            e1.grid(row=0, column=1, sticky=tk.EW, padx=(0, 6))

            tk.Label(row_frame, text="Talking point:", font=FONT_SMALL, bg=BG_CARD, fg=FG_DIM).grid(
                row=1, column=0, sticky=tk.W, padx=(0, 6), pady=(4, 0)
            )
            e2 = _entry(row_frame)
            e2.config(textvariable=tp)
            e2.grid(row=1, column=1, sticky=tk.EW, padx=(0, 6), pady=(4, 0))

            row_frame.columnconfigure(1, weight=1)

            def remove_row(rf=row_frame, entry={"strength": sv, "talking_point": tp}) -> None:
                rf.destroy()
                if entry in self._strength_rows:
                    self._strength_rows.remove(entry)

            tk.Button(
                row_frame, text="−", command=remove_row,
                font=FONT_BODY, bg=ERROR, fg=BG,
                relief=tk.FLAT, cursor="hand2", padx=6,
            ).grid(row=0, column=2, rowspan=2, padx=(4, 0))

        _button(inner, "+ Add Strength", add_strength_row).pack(
            anchor=tk.W, pady=(0, PAD)
        )

        # ---- Gaps section ----
        tk.Frame(inner, bg=FG_DIM, height=1).pack(fill=tk.X, pady=(4, PAD))
        _label(inner, "⚠️ Gaps & Objections to Prepare For", font=FONT_HEADING).pack(
            anchor=tk.W, pady=(0, 4)
        )
        _label(
            inner,
            "List objections a hiring manager might raise and your prepared rebuttal for each.",
            fg=FG_DIM,
            wraplength=560,
        ).pack(anchor=tk.W, pady=(0, 8))

        self._gap_rows: list[dict[str, tk.StringVar]] = []
        gap_container = tk.Frame(inner, bg=BG)
        gap_container.pack(fill=tk.X, pady=(0, 8))

        def add_gap_row(
            objection: str = "", rebuttal: str = "", mitigation: str = ""
        ) -> None:
            row_frame = tk.Frame(gap_container, bg=BG_CARD, pady=6, padx=8)
            row_frame.pack(fill=tk.X, pady=3)

            ov = tk.StringVar(value=objection)
            rv = tk.StringVar(value=rebuttal)
            mv = tk.StringVar(value=mitigation)
            entry_dict = {"objection": ov, "rebuttal": rv, "mitigation": mv}
            self._gap_rows.append(entry_dict)

            labels_vars = [
                ("Objection:", ov),
                ("Rebuttal:", rv),
                ("Mitigation:", mv),
            ]
            for i, (lbl_text, var) in enumerate(labels_vars):
                tk.Label(
                    row_frame, text=lbl_text, font=FONT_SMALL, bg=BG_CARD, fg=FG_DIM
                ).grid(row=i, column=0, sticky=tk.W, padx=(0, 6), pady=(0 if i == 0 else 4, 0))
                e = _entry(row_frame)
                e.config(textvariable=var)
                e.grid(row=i, column=1, sticky=tk.EW, padx=(0, 6), pady=(0 if i == 0 else 4, 0))

            row_frame.columnconfigure(1, weight=1)

            def remove_gap(rf=row_frame, ed=entry_dict) -> None:
                rf.destroy()
                if ed in self._gap_rows:
                    self._gap_rows.remove(ed)

            tk.Button(
                row_frame, text="−", command=remove_gap,
                font=FONT_BODY, bg=ERROR, fg=BG,
                relief=tk.FLAT, cursor="hand2", padx=6,
            ).grid(row=0, column=2, rowspan=3, padx=(4, 0))

        _button(inner, "+ Add Gap", add_gap_row).pack(
            anchor=tk.W, pady=(0, PAD * 2)
        )

        # ---- Action buttons ----
        btn_frame = tk.Frame(frame, bg=BG)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(PAD, 0))

        _button(
            btn_frame,
            "Save & Open Notion",
            self._save_and_open,
            accent=True,
        ).pack(side=tk.LEFT, padx=(0, 8))
        _button(
            btn_frame,
            "Skip — I'll fill this in later",
            self._skip_gap_analysis,
        ).pack(side=tk.LEFT)

    def _collect_gap_data(self) -> tuple[list[dict], list[dict]]:
        """
        Read the current values from all strength and gap row widgets.

        Returns:
            A tuple of (strengths, gaps) where each is a list of dicts.
        """
        strengths = [
            {
                "strength": row["strength"].get().strip(),
                "talking_point": row["talking_point"].get().strip(),
            }
            for row in self._strength_rows
            if row["strength"].get().strip()
        ]
        gaps = [
            {
                "objection": row["objection"].get().strip(),
                "rebuttal": row["rebuttal"].get().strip(),
                "mitigation": row["mitigation"].get().strip(),
            }
            for row in self._gap_rows
            if row["objection"].get().strip()
        ]
        return strengths, gaps

    def _save_workspace_to_state(self) -> None:
        """Persist the current build result to the local state file."""
        from .state import save_workspace

        result = self._build_result
        save_workspace({
            "name": self._workspace_name,
            "parent_page_id": self._parent_page_id,
            "notion_url": result.get("notion_url", ""),
            "gap_page_id": result.get("gap_analysis_id", ""),
            "database_ids": {
                k: result[k]
                for k in ("companies", "job_postings", "contacts", "outreach_log")
                if k in result
            },
            "token": self._token,
        })

    def _save_and_open(self) -> None:
        """Save Gap Analysis content, persist state, then open Notion."""
        strengths, gaps = self._collect_gap_data()
        result = self._build_result
        gap_page_id = result.get("gap_analysis_id", "")

        if gap_page_id and (strengths or gaps):
            try:
                from .builder import update_gap_analysis
                from .client import get_client

                client = get_client(self._token)
                update_gap_analysis(client, gap_page_id, strengths, gaps)
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror(
                    "Gap Analysis Error",
                    f"Could not save Gap Analysis content:\n{exc}\n\n"
                    "Your workspace was created. You can edit the Gap Analysis "
                    "page directly in Notion.",
                )

        self._save_workspace_to_state()
        url = result.get("notion_url", "")
        if url:
            webbrowser.open(url)
        self._show_workspace_list()

    def _skip_gap_analysis(self) -> None:
        """Skip Gap Analysis input, persist state, and open Notion."""
        self._save_workspace_to_state()
        url = self._build_result.get("notion_url", "")
        if url:
            webbrowser.open(url)
        self._show_workspace_list()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """
    Launch the Notion Job Search GUI application.

    This is the entry point used by PyInstaller and by ``python -m
    notion_job_search.gui``.
    """
    root = tk.Tk()
    root.title("Notion Job Search")
    app = NotionJobSearchApp(root)  # noqa: F841
    root.mainloop()


if __name__ == "__main__":
    main()