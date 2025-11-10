"""GPIO helpers for the physical exit button."""
from __future__ import annotations

import logging
import select
import sys
import threading
from dataclasses import dataclass
from typing import Callable, Optional

logger = logging.getLogger(__name__)

try:  # pragma: no cover - gpiozero is not available in test environments
    from gpiozero import Button  # type: ignore
except ImportError:  # pragma: no cover - executed on non-RPi hosts
    Button = None  # type: ignore


@dataclass
class ExitButtonConfig:
    pin: int
    debounce_ms: int = 150


class ExitButton:
    """Wraps the GPIO button with an optional software fallback."""

    def __init__(self, config: ExitButtonConfig, on_press: Callable[[], None]):
        self._config = config
        self._on_press = on_press
        self._button: Optional[Button] = None
        self._fallback_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        if Button is not None:
            bounce = config.debounce_ms / 1000 if config.debounce_ms else None
            try:
                self._button = Button(config.pin, pull_up=True, bounce_time=bounce)
                self._button.when_pressed = self._handle_press
                logger.info("GPIO exit button initialised on pin %s", config.pin)
            except Exception as exc:  # pragma: no cover - hardware-specific
                logger.warning("Failed to initialise GPIO button: %s", exc)
                self._start_fallback()
        else:
            self._start_fallback()

    def _start_fallback(self) -> None:
        logger.info("Using development fallback for exit button (Ctrl+C to exit game).")
        self._fallback_thread = threading.Thread(target=self._fallback_loop, daemon=True)
        self._fallback_thread.start()

    def _fallback_loop(self) -> None:
        """Listen for keyboard input to simulate button presses during development."""
        logger.info("Type 'exit' and press Enter in this terminal to simulate the exit button.")
        while not self._stop_event.is_set():
            try:
                ready, _, _ = select.select([sys.stdin], [], [], 1.0)
            except (ValueError, OSError):  # pragma: no cover - select errors
                break
            if self._stop_event.is_set():
                break
            if sys.stdin in ready:
                line = sys.stdin.readline()
                if line.strip().lower() in {"exit", "quit", "q"}:
                    logger.info("Simulated exit button press from keyboard")
                    self._handle_press()

    def _handle_press(self) -> None:
        try:
            self._on_press()
        except Exception:  # pragma: no cover - defensive
            logger.exception("Error while handling exit button press")

    def close(self) -> None:
        self._stop_event.set()
        if self._button is not None:
            try:
                self._button.close()
            except Exception:  # pragma: no cover - hardware-specific
                logger.debug("Error while closing GPIO button", exc_info=True)
        if self._fallback_thread and self._fallback_thread.is_alive():
            self._fallback_thread.join(timeout=1)


__all__ = ["ExitButton", "ExitButtonConfig"]
