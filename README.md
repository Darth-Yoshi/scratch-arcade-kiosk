# Scratch Arcade Kiosk

Scratch Arcade Kiosk is a borderless, touchscreen-friendly launcher for Raspberry Pi
installations that host Scratch (`.sb3`) arcade games. It boots into a full-screen file
picker, launches projects with a configurable player, and listens for a physical GPIO
button to return from games instantly.

## Features

- **Touch-first UI** – large buttons, high contrast layout, and optional search field.
- **Sandboxed file browser** – users can only browse within the configured `base_dir`.
- **Configurable player** – run any Scratch-compatible player command; defaults to
  TurboWarp Desktop in full-screen player mode.
- **Physical exit button** – GPIO-driven with software debouncing and development
  keyboard fallback.
- **Configurable control panel buttons** – map up to eight additional GPIO inputs to
  keyboard events (arrow keys, space, and number keys by default).
- **Idle reset** – optionally return to the root picker after inactivity.
- **Autostart** – optional systemd service installer for kiosk boot.

## Requirements

- Raspberry Pi OS (Bullseye or later) with Python 3.11+
- Tkinter (usually preinstalled on Raspberry Pi OS)
- `gpiozero` (install with `sudo apt install python3-gpiozero`)
- TurboWarp Desktop (download from https://desktop.turbowarp.org and install the AppImage)
- `xdotool` (install with `sudo apt install xdotool`) for translating GPIO buttons into key presses

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
| `[gpio.keypad] press_command` / `release_command` | Commands executed when GPIO key buttons are pressed and released. `{key}` expands to the configured symbol; `{action}` resolves to `press` or `release`. |
| `[[gpio.keypad.buttons]]` | Define each key button with a `pin` and `key` (e.g. `Up`, `space`, `1`). |
| `[player] command` | Command array to launch the player. `{file}` is the raw path; `{file_url}` is a URI version for browsers. Additional placeholders (`{autoplay_flag}`, `{turbo_flag}`, `{fps_flag}`) expand to TurboWarp Desktop CLI switches, while `{hash_fragment}`/`{fps_query}` remain for browser-based templates. Empty substitutions are removed automatically. |
| `[player] autoplay/turbo/fps` | Control which optional flags expand; by default they map to TurboWarp Desktop's `--unpause`, `--turbo`, and `--fps=<n>` switches. |
| `[ui] show_search` | Toggle the search box in the picker. |

> **Tip:** Install TurboWarp Desktop by downloading the AppImage from
> https://desktop.turbowarp.org, making it executable, and placing it somewhere on your
> `$PATH` (e.g. `/usr/local/bin/turbowarp-desktop`). The default command launches the
> desktop player in full-screen mode and forwards autoplay/turbo/fps toggles using its
> documented CLI options. You can swap in Chromium or any other player by editing the
> `[player]` section and using the provided placeholders.

If you prefer a browser-based player or need an entirely offline setup, replace the
command with your own Chromium/Firefox invocation or point TurboWarp Desktop at a local
AppImage. The placeholder variables let you control which options are passed to the
player.

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
  in the terminal where the kiosk is running. GPIO key buttons rely on `gpiozero`/GPIO
  hardware; during development you can press the corresponding keys on your keyboard or
  run the configured command manually (default: `xdotool keydown <key>` / `xdotool keyup <key>`).
- The UI hides the mouse cursor and forces full-screen mode. Pressing `Ctrl+C` in the
  terminal stops the kiosk entirely (development only).
- Directory traversal is restricted via `Path.resolve()` checks; attempts to leave the
  sandbox are ignored and logged.

## License

This project is provided as-is for kiosk deployments. See the repository history for
contributors.
