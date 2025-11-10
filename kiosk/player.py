"""Manage launching and monitoring the Scratch player process."""
from __future__ import annotations

import logging
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import List, Optional

from .config import PlayerConfig

logger = logging.getLogger(__name__)


class PlayerLaunchError(RuntimeError):
    """Raised when the player cannot be started."""


class PlayerManager:
    def __init__(self, config: PlayerConfig):
        self._config = config
        self._process: Optional[subprocess.Popen[bytes]] = None

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def _build_command(self, project: Path) -> List[str]:
        substitutions = {
            "file": str(project),
            "autoplay": "1" if self._config.autoplay else "0",
            "turbo": "1" if self._config.turbo else "0",
            "fps": str(self._config.fps or ""),
        }
        command: List[str] = []
        for part in self._config.command:
            try:
                command.append(part.format(**substitutions))
            except KeyError as exc:
                raise PlayerLaunchError(f"Unknown placeholder {exc} in player command") from exc
        return command

    def launch(self, project: Path) -> None:
        if self.is_running:
            raise PlayerLaunchError("A project is already running")
        if not project.exists():
            raise PlayerLaunchError(f"Project file not found: {project}")
        command = self._build_command(project)
        logger.info("Launching player: %s", command)
        try:
            self._process = subprocess.Popen(command)
        except FileNotFoundError as exc:
            raise PlayerLaunchError(
                f"Player executable not found: {command[0]}. Update the [player] command in the config."
            ) from exc
        except OSError as exc:
            raise PlayerLaunchError(f"Unable to start player: {exc}") from exc

    def terminate(self, timeout: float = 5.0) -> None:
        if not self.is_running:
            return
        assert self._process is not None
        logger.info("Terminating player process (pid=%s)", self._process.pid)
        self._process.terminate()
        try:
            self._process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            logger.warning("Player did not exit in time; sending SIGKILL")
            self._process.kill()
            try:
                self._process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                logger.error("Failed to kill player process")
        finally:
            self._process = None

    def ensure_stopped(self) -> None:
        if self.is_running:
            self.terminate()


__all__ = ["PlayerManager", "PlayerLaunchError"]
