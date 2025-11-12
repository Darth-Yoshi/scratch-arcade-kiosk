"""Configuration loading for the Scratch Arcade Kiosk."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Sequence
import tomllib


CONFIG_PATH = Path("config/config")
EXAMPLE_CONFIG_PATH = Path("config/example.config")


@dataclass
class DisplayConfig:
    width: int = 800
    height: int = 480


@dataclass
class IdleConfig:
    idle_return_seconds: int | None = None


@dataclass
class KioskConfig:
    autostart: bool = False


@dataclass
class GPIOConfig:
    exit_pin: int = 17
    debounce_ms: int = 150


@dataclass
class PlayerConfig:
    command: List[str] = field(
        default_factory=lambda: [
            "chromium-browser",
            "--kiosk",
            "--start-fullscreen",
            "--incognito",
            "--autoplay-policy=no-user-gesture-required",
            "--noerrdialogs",
            "--disable-session-crashed-bubble",
            "https://turbowarp.org/player.html?project_url={file_url}&autoplay={autoplay}&turbo={turbo}{fps_query}",
        ]
    )
    autoplay: bool = True
    turbo: bool = False
    fps: int | None = 60


@dataclass
class UIConfig:
    show_search: bool = True
    max_visible_entries: int = 6


@dataclass
class Config:
    base_dir: Path
    allowed_extensions: List[str]
    display: DisplayConfig = field(default_factory=DisplayConfig)
    idle: IdleConfig = field(default_factory=IdleConfig)
    kiosk: KioskConfig = field(default_factory=KioskConfig)
    gpio: GPIOConfig = field(default_factory=GPIOConfig)
    player: PlayerConfig = field(default_factory=PlayerConfig)
    ui: UIConfig = field(default_factory=UIConfig)

    @property
    def normalized_extensions(self) -> List[str]:
        """Return extensions lowercased and guaranteed to start with a dot."""
        normalized: List[str] = []
        for ext in self.allowed_extensions:
            ext = ext.strip()
            if not ext:
                continue
            if not ext.startswith("."):
                ext = "." + ext
            normalized.append(ext.lower())
        return normalized or [".sb3"]


class ConfigError(RuntimeError):
    """Raised when the configuration file cannot be loaded."""


DEFAULTS: Dict[str, Any] = {
    "base_dir": str(Path.home()),
    "allowed_extensions": [".sb3"],
    "display": {"width": 800, "height": 480},
    "idle": {"idle_return_seconds": None},
    "kiosk": {"autostart": False},
    "gpio": {"exit_pin": 17, "debounce_ms": 150},
    "player": {
        "command": [
            "chromium-browser",
            "--kiosk",
            "--start-fullscreen",
            "--incognito",
            "--autoplay-policy=no-user-gesture-required",
            "--noerrdialogs",
            "--disable-session-crashed-bubble",
            "https://turbowarp.org/player.html?project_url={file_url}&autoplay={autoplay}&turbo={turbo}{fps_query}",
        ],
        "autoplay": True,
        "turbo": False,
        "fps": 60,
    },
    "ui": {"show_search": True, "max_visible_entries": 6},
}


def deep_merge(defaults: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged: Dict[str, Any] = {}
    for key, value in defaults.items():
        if isinstance(value, dict):
            merged[key] = value.copy()
        else:
            merged[key] = value
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(path: Path | None = None) -> Config:
    """Load the kiosk configuration file."""
    config_path = path or CONFIG_PATH
    if not config_path.exists():
        example_hint = ""
        if EXAMPLE_CONFIG_PATH.exists():
            example_hint = f" Copy {EXAMPLE_CONFIG_PATH} to {config_path} to get started."
        raise ConfigError(f"Configuration file not found at {config_path}.{example_hint}")

    try:
        with config_path.open("rb") as fh:
            data = tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Invalid configuration file: {exc}") from exc
    except OSError as exc:  # pragma: no cover - filesystem errors
        raise ConfigError(f"Unable to read configuration file: {exc}") from exc

    merged = deep_merge(DEFAULTS, data)
    base_dir = Path(merged["base_dir"]).expanduser().resolve()
    allowed = merged.get("allowed_extensions") or [".sb3"]

    return Config(
        base_dir=base_dir,
        allowed_extensions=list(allowed),
        display=DisplayConfig(**merged["display"]),
        idle=IdleConfig(**merged["idle"]),
        kiosk=KioskConfig(**merged["kiosk"]),
        gpio=GPIOConfig(**merged["gpio"]),
        player=PlayerConfig(**merged["player"]),
        ui=UIConfig(**merged["ui"]),
    )


__all__ = [
    "Config",
    "ConfigError",
    "DisplayConfig",
    "GPIOConfig",
    "IdleConfig",
    "KioskConfig",
    "PlayerConfig",
    "UIConfig",
    "load_config",
    "CONFIG_PATH",
]
