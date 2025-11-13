"""Entry point wiring for the Scratch Arcade Kiosk."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from .config import ConfigError, load_config
from .gpio import ExitButton, ExitButtonConfig, KeyButtonManager
from .player import PlayerManager
from .ui import FilePickerApp, UIDisplayError

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def main(config_path: Path | None = None) -> int:
    configure_logging()
    try:
        config = load_config(config_path)
    except ConfigError as exc:
        logger.error("%s", exc)
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    player = PlayerManager(config.player)
    try:
        ui = FilePickerApp(config=config, player=player)
    except UIDisplayError as exc:
        logger.error("%s", exc)
        print(f"Display error: {exc}", file=sys.stderr)
        return 1

    exit_button = ExitButton(
        ExitButtonConfig(pin=config.gpio.exit_pin, debounce_ms=config.gpio.debounce_ms),
        on_press=ui.handle_exit_button,
    )
    key_button_manager = KeyButtonManager(
        press_command_template=config.gpio.keypad.press_command,
        release_command_template=config.gpio.keypad.release_command,
        buttons=config.gpio.keypad.buttons,
        default_debounce_ms=config.gpio.debounce_ms,
    )

    try:
        ui.run()
    finally:
        exit_button.close()
        key_button_manager.close()
        player.ensure_stopped()

    return 0


if __name__ == "__main__":
    sys.exit(main())
