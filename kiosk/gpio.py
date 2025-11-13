"""GPIO helpers for the physical controls."""
from __future__ import annotations

import logging
import select
import sys
import threading
import subprocess
from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence

from .config import KeyButtonConfig

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


class KeyButtonManager:
    """Handle GPIO buttons that emit keyboard events."""

    def __init__(
        self,
        press_command_template: Sequence[str],
        release_command_template: Sequence[str] | None,
        buttons: Sequence[KeyButtonConfig],
        default_debounce_ms: int | None = None,
    ) -> None:
        self._press_command_template = list(press_command_template)
        self._release_command_template = (
            list(release_command_template) if release_command_template is not None else []
        )
        self._buttons: List[Button] = []  # type: ignore[var-annotated]
        self._button_configs = list(buttons)
        self._default_debounce_ms = default_debounce_ms

        if not self._button_configs:
            logger.info("No GPIO key buttons configured.")
            return

        if Button is None:
            logger.info(
                "gpiozero not available; GPIO key buttons are disabled. "
                "Use a keyboard to simulate presses during development."
            )
            return

        for config in self._button_configs:
            bounce_ms = (
                config.debounce_ms
                if config.debounce_ms is not None
                else self._default_debounce_ms
            )
            bounce = bounce_ms / 1000 if bounce_ms else None
            try:
                button = Button(config.pin, pull_up=True, bounce_time=bounce)  # type: ignore[misc]
            except Exception as exc:  # pragma: no cover - hardware-specific
                logger.warning(
                    "Failed to initialise GPIO key button on pin %s: %s", config.pin, exc
                )
                continue
            button.when_pressed = self._make_press_handler(config.key)
            if self._release_command_template:
                button.when_released = self._make_release_handler(config.key)
            self._buttons.append(button)
            logger.info("GPIO key button initialised on pin %s for key '%s'", config.pin, config.key)

    def _make_press_handler(self, key: str) -> Callable[[], None]:
        def _handler() -> None:
            self._handle_press(key)

        return _handler

    def _make_release_handler(self, key: str) -> Callable[[], None]:
        def _handler() -> None:
            self._handle_release(key)

        return _handler

    def _build_command(self, template: Sequence[str], key: str, action: str) -> List[str]:
        command: List[str] = []
        for part in template:
            try:
                formatted = part.format(key=key, action=action)
            except KeyError as exc:
                logger.error("Unknown placeholder %s in GPIO key command", exc)
                return []
            if formatted.strip():
                command.append(formatted)
        return command

    def _handle_press(self, key: str) -> None:
        command = self._build_command(self._press_command_template, key, "press")
        if not command:
            logger.warning("Skipping GPIO key press for '%s'; command is empty.", key)
            return
        logger.debug("GPIO key button triggering command: %s", command)
        try:
            subprocess.run(command, check=True)
        except FileNotFoundError:
            logger.error(
                "Command '%s' not found while handling GPIO key '%s'. Update gpio.keypad.press_command.",
                command[0],
                key,
            )
        except subprocess.CalledProcessError as exc:
            logger.error(
                "GPIO key command failed for '%s' with exit code %s", key, exc.returncode
            )
        except Exception:  # pragma: no cover - defensive
            logger.exception("Unexpected error while handling GPIO key '%s'", key)

    def _handle_release(self, key: str) -> None:
        if not self._release_command_template:
            return
        command = self._build_command(self._release_command_template, key, "release")
        if not command:
            return
        logger.debug("GPIO key release triggering command: %s", command)
        try:
            subprocess.run(command, check=True)
        except FileNotFoundError:
            logger.error(
                "Command '%s' not found while handling GPIO key release '%s'. Update gpio.keypad.release_command.",
                command[0],
                key,
            )
        except subprocess.CalledProcessError as exc:
            logger.error(
                "GPIO key release command failed for '%s' with exit code %s",
                key,
                exc.returncode,
            )
        except Exception:  # pragma: no cover - defensive
            logger.exception("Unexpected error while handling GPIO key release '%s'", key)

    def close(self) -> None:
        for button in self._buttons:
            try:
                button.close()
            except Exception:  # pragma: no cover - hardware-specific
                logger.debug("Error while closing GPIO key button", exc_info=True)
        self._buttons.clear()


__all__ = ["ExitButton", "ExitButtonConfig", "KeyButtonManager"]
