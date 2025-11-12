# Scratch Arcade Kiosk

Scratch Arcade Kiosk is a borderless, touchscreen-friendly launcher for Raspberry Pi
installations that host Scratch (`.sb3`) arcade games. It boots into a full-screen file
picker, launches projects with a configurable player, and listens for a physical GPIO
button to return from games instantly.

## Features

- **Touch-first UI** – large buttons, high contrast layout, and optional search field.
- **Sandboxed file browser** – users can only browse within the configured `base_dir`.
- **Configurable player** – run any Scratch-compatible player command; defaults to
  Chromium in kiosk mode targeting the TurboWarp web player.
- **Physical exit button** – GPIO-driven with software debouncing and development
  keyboard fallback.
- **Idle reset** – optionally return to the root picker after inactivity.
- **Autostart** – optional systemd service installer for kiosk boot.

## Requirements

- Raspberry Pi OS (Bullseye or later) with Python 3.11+
- Tkinter (usually preinstalled on Raspberry Pi OS)
- `gpiozero` (install with `sudo apt install python3-gpiozero`)
- Chromium (`sudo apt install chromium`) for the bundled TurboWarp web player command

## Configuration

Copy the example configuration and edit it to suit your setup:

```bash
cp config/example.config config/config
nano config/config
```

The file is in TOML syntax. Key options:

| Key | Description |
| --- | --- |
| `base_dir` | Root directory containing games. The UI cannot escape this path. |
| `allowed_extensions` | List of playable file extensions (default `.sb3`). |
| `[display] width/height` | Target display size (default 800×480). |
| `[idle] idle_return_seconds` | Auto-reset back to the picker after N seconds of inactivity. |
| `[gpio] exit_pin` | BCM pin for the physical exit button. |
| `[gpio] debounce_ms` | Software debounce window for the button. |
| `[player] command` | Command array to launch the player. `{file}` is the raw path, `{file_url}` is a URI version for browsers, and `{fps_query}` expands to an optional `&fps=…` fragment. |
| `[player] autoplay/turbo/fps` | Additional placeholders (`{autoplay}`, `{turbo}`, `{fps}`) for player command templates. |
| `[ui] show_search` | Toggle the search box in the picker. |

> **Tip:** Install Chromium with `sudo apt install chromium` to use the default
> TurboWarp player command. You can swap in another browser or player by editing the
> `[player]` section of the config.

The bundled TurboWarp URL streams assets from the public `turbowarp.org` site. If you
need the kiosk to operate completely offline, download a self-hosted copy of the player
and update `[player].command` to point Chromium at your local HTML entry point instead.

## Running the kiosk

From the repository root:

```bash
python3 -m kiosk.app
```

Press the physical exit button (or type `exit` + Enter in the terminal when running on a
non-Raspberry Pi host) to close the currently running project and return to the picker.

## Autostart on boot

When `kiosk.autostart` is `true`, install the provided systemd service:

```bash
sudo ./scripts/install_autostart.sh
```

This writes `/etc/systemd/system/scratch-arcade-kiosk.service` pointing at the project
folder. The service restarts automatically if the player crashes. Disable with:

```bash
sudo systemctl disable --now scratch-arcade-kiosk
```

## Development notes

- The fallback exit button helper allows testing without GPIO hardware by typing `exit`
  in the terminal where the kiosk is running.
- The UI hides the mouse cursor and forces full-screen mode. Pressing `Ctrl+C` in the
  terminal stops the kiosk entirely (development only).
- Directory traversal is restricted via `Path.resolve()` checks; attempts to leave the
  sandbox are ignored and logged.

## License

This project is provided as-is for kiosk deployments. See the repository history for
contributors.
