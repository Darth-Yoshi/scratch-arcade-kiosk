"""Entry point wiring for the Scratch Arcade Kiosk."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from .config import ConfigError, load_config
from .gpio import ExitButton, ExitButtonConfig
from .player import PlayerManager
from .ui import FilePickerApp

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
    ui = FilePickerApp(config=config, player=player)

    exit_button = ExitButton(
        ExitButtonConfig(pin=config.gpio.exit_pin, debounce_ms=config.gpio.debounce_ms),
        on_press=ui.handle_exit_button,
    )

    try:
        ui.run()
    finally:
        exit_button.close()
        player.ensure_stopped()

    return 0


if __name__ == "__main__":
    sys.exit(main())
