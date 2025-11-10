"""Tkinter user interface for the Scratch Arcade Kiosk."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List

import tkinter as tk
from tkinter import ttk


class UIDisplayError(RuntimeError):
    """Raised when the Tkinter UI cannot be initialised due to display issues."""

    pass

from .config import Config
from .player import PlayerLaunchError, PlayerManager

logger = logging.getLogger(__name__)


@dataclass
class DirectoryEntry:
    path: Path
    is_dir: bool


class FilePickerApp:
    def __init__(
        self,
        config: Config,
        player: PlayerManager,
        on_exit_pressed: Callable[[], None] | None = None,
    ) -> None:
        self.config = config
        self.player = player
        self.on_exit_pressed = on_exit_pressed or (lambda: None)

        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            raise UIDisplayError(
                "Unable to open the kiosk interface because no display server is available. "
                "Ensure the application is launched within a graphical session with $DISPLAY set."
            ) from exc
        self.root.title("Scratch Arcade Kiosk")
        self.root.configure(bg="#111")
        self.root.attributes("-fullscreen", True)
        self.root.config(cursor="none")

        self.base_dir = config.base_dir
        self.current_dir = self.base_dir
        self._game_running = False
        self._last_interaction = time.time()
        self._idle_job: str | None = None

        self._init_styles()
        self._build_layout()

        if not self.base_dir.exists():
            self.show_error(
                f"Configured base directory not found:\n{self.base_dir}\n\nCreate the folder or update config/config."
            )
        else:
            self.refresh()

        self._schedule_idle_check()

    # ------------------------------------------------------------------ UI setup
    def _init_styles(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TButton", font=("Helvetica", 20), padding=20)
        style.configure("Header.TButton", font=("Helvetica", 20, "bold"), padding=20)
        style.configure("Dir.TButton", font=("Helvetica", 24), padding=30)
        style.configure("Play.TButton", font=("Helvetica", 24, "bold"), padding=30)
        style.configure("TLabel", font=("Helvetica", 22), foreground="#eee", background="#222")
        style.configure("Error.TLabel", font=("Helvetica", 26, "bold"), foreground="#ff6666", background="#111")

    def _build_layout(self) -> None:
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=1)

        header = ttk.Frame(self.root, padding=10, style="TFrame")
        header.grid(row=0, column=0, sticky="nsew")
        header.grid_columnconfigure(1, weight=1)

        self.back_button = ttk.Button(header, text="⬅ Back", style="Header.TButton", command=self.go_back)
        self.back_button.grid(row=0, column=0, padx=10, pady=10)

        self.path_label = ttk.Label(header, text="", anchor="center", style="TLabel")
        self.path_label.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        self.refresh_button = ttk.Button(header, text="🔄 Refresh", style="Header.TButton", command=self.refresh)
        self.refresh_button.grid(row=0, column=2, padx=10, pady=10)

        if self.config.ui.show_search:
            self.search_var = tk.StringVar()
            self.search_var.trace_add("write", lambda *_: self.refresh())
            search_entry = ttk.Entry(header, textvariable=self.search_var, font=("Helvetica", 20))
            search_entry.grid(row=1, column=0, columnspan=3, sticky="ew", padx=10, pady=(0, 10))
            search_entry.insert(0, "")
            search_entry.bind("<FocusIn>", lambda e: self._record_interaction())
            search_entry.bind("<Key>", lambda e: self._record_interaction())
        else:
            self.search_var = tk.StringVar(value="")

        body = ttk.Frame(self.root, padding=10)
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(body, bg="#222", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(body, orient="vertical", command=self.canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.entries_frame = ttk.Frame(self.canvas, padding=10)
        self.entries_frame.bind("<Configure>", lambda e: self._on_frame_configure())
        self.canvas_window = self.canvas.create_window((0, 0), window=self.entries_frame, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self._on_canvas_configure(e.width))

        self.status_var = tk.StringVar(value="")
        self.status_label = ttk.Label(self.root, textvariable=self.status_var, style="TLabel")
        self.status_label.grid(row=2, column=0, sticky="ew", padx=20, pady=10)

        self.root.bind_all("<Button>", lambda e: self._record_interaction())
        self.root.bind_all("<Key>", lambda e: self._record_interaction())

    # ------------------------------------------------------------------ Navigation
    def go_back(self) -> None:
        if self.current_dir == self.base_dir:
            return
        parent = self.current_dir.parent
        if self._within_base(parent):
            self.navigate(parent)

    def navigate(self, directory: Path) -> None:
        if not self._within_base(directory):
            logger.warning("Attempted to escape base directory: %s", directory)
            return
        if not directory.exists():
            self.show_error(f"Folder not found: {directory}")
            return
        if not directory.is_dir():
            self.show_error(f"Not a folder: {directory}")
            return
        self.current_dir = directory
        self.refresh()

    def refresh(self) -> None:
        self.status_var.set("")
        for child in self.entries_frame.winfo_children():
            child.destroy()

        self.path_label.config(text=self._relative_path(self.current_dir))

        entries = self._list_directory(self.current_dir)
        query = self.search_var.get().strip().lower()
        if query:
            entries = [entry for entry in entries if query in entry.path.name.lower()]

        if not entries:
            label = ttk.Label(
                self.entries_frame,
                text="No games or folders found here.",
                style="TLabel",
            )
            label.pack(fill="x", pady=20)
            return

        for entry in entries:
            if entry.is_dir:
                self._add_directory_entry(entry.path)
            else:
                self._add_file_entry(entry.path)

    def _list_directory(self, directory: Path) -> List[DirectoryEntry]:
        entries: List[DirectoryEntry] = []
        try:
            for item in sorted(directory.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
                if item.is_dir():
                    entries.append(DirectoryEntry(item, True))
                elif item.is_file() and item.suffix.lower() in self.config.normalized_extensions:
                    entries.append(DirectoryEntry(item, False))
        except PermissionError:
            self.show_error(f"Cannot read folder: {directory}")
        return entries

    def _add_directory_entry(self, directory: Path) -> None:
        frame = ttk.Frame(self.entries_frame, padding=10)
        frame.pack(fill="x", pady=6)
        btn = ttk.Button(
            frame,
            text=f"📁 {directory.name}",
            style="Dir.TButton",
            command=lambda d=directory: self.navigate(d),
        )
        btn.pack(fill="x")

    def _add_file_entry(self, file_path: Path) -> None:
        frame = ttk.Frame(self.entries_frame, padding=10)
        frame.pack(fill="x", pady=6)
        label = ttk.Label(frame, text=file_path.name, style="TLabel")
        label.pack(side="left", fill="x", expand=True, padx=(0, 20))
        play_btn = ttk.Button(
            frame,
            text="▶ Play",
            style="Play.TButton",
            command=lambda f=file_path: self.launch_game(f),
        )
        play_btn.pack(side="right")

    def _relative_path(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.base_dir)) or "/"
        except ValueError:
            return str(path)

    def _within_base(self, path: Path) -> bool:
        try:
            path.resolve().relative_to(self.base_dir)
            return True
        except ValueError:
            return path.resolve() == self.base_dir

    def _on_frame_configure(self) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, width: int) -> None:
        self.canvas.itemconfigure(self.canvas_window, width=width)

    # ------------------------------------------------------------------ Game lifecycle
    def launch_game(self, file_path: Path) -> None:
        if self._game_running:
            return
        try:
            self.player.launch(file_path)
        except PlayerLaunchError as exc:
            self.show_error(str(exc))
            return
        self._game_running = True
        self.status_var.set(f"Running: {file_path.name}")
        self.root.withdraw()
        self.root.after(500, self._poll_player)

    def _poll_player(self) -> None:
        if not self._game_running:
            return
        if not self.player.is_running:
            self._game_running = False
            self.root.deiconify()
            self.root.attributes("-fullscreen", True)
            self.root.config(cursor="none")
            self.root.focus_force()
            self.refresh()
            self.status_var.set("Select a game to play.")
        else:
            self.root.after(1000, self._poll_player)

    def handle_exit_button(self) -> None:
        if self._game_running:
            self.player.terminate()
            self._game_running = False
            self.root.deiconify()
            self.root.attributes("-fullscreen", True)
            self.root.config(cursor="none")
            self.root.focus_force()
            self.refresh()
            self.status_var.set("Returned to launcher.")
        else:
            logger.info("Exit button pressed with no active game.")
        self.on_exit_pressed()

    # ------------------------------------------------------------------ Idle handling
    def _schedule_idle_check(self) -> None:
        if self._idle_job:
            self.root.after_cancel(self._idle_job)
        self._idle_job = self.root.after(1000, self._check_idle)

    def _check_idle(self) -> None:
        timeout = self.config.idle.idle_return_seconds
        if timeout and not self._game_running:
            elapsed = time.time() - self._last_interaction
            if elapsed > timeout:
                logger.info("Idle timeout reached; returning to base directory")
                self.current_dir = self.base_dir
                self.refresh()
        self._schedule_idle_check()

    def _record_interaction(self) -> None:
        self._last_interaction = time.time()

    # ------------------------------------------------------------------ Error handling
    def show_error(self, message: str) -> None:
        self.status_var.set("")
        for child in self.entries_frame.winfo_children():
            child.destroy()
        label = ttk.Label(self.entries_frame, text=message, style="Error.TLabel", anchor="center", justify="center")
        label.pack(expand=True, fill="both", padx=40, pady=40)

    # ------------------------------------------------------------------ Main loop
    def run(self) -> None:
        self.status_var.set("Select a game to play.")
        self.root.mainloop()


__all__ = ["FilePickerApp"]
