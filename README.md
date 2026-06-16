# CMS 2021 Scrap Automation

## Overview

This project provides Python scripts for automating the Car Mechanic Simulator 2021 scrap/salvage minigame using screen recognition and normal keyboard input.

The automation detects the blue/cyan target area and the orange/yellow pointer, then sends `SPACE` when the pointer is aligned with the target. It can also restart the next scrap attempt automatically.

This tool does not modify game files, edit memory, inject DLLs, inject into processes, or interact with the game internally. It only captures the visible screen and sends normal keyboard input.

## Features

- Calibrates the screen region used for detection.
- Saves calibration to `cms2021_scrap_config.json`.
- Captures only the configured minigame region.
- Detects the blue/cyan target area.
- Detects the orange/yellow pointer.
- Sends `SPACE` using `pydirectinput`.
- Supports automatic next-attempt restart.
- Provides global hotkeys for start/stop, manual test, and exit.

## Requirements

- Python 3.11 or newer
- `pyautogui`
- `mss`
- `opencv-python`
- `keyboard`
- `numpy`
- `pydirectinput`

## Installation

Install the required Python packages:

```powershell
pip install pyautogui mss opencv-python keyboard numpy pydirectinput
```

## Calibration

Use `cms2021_scrap_calibrate.py` to define the screen region containing the scrap minigame UI.

```powershell
python cms2021_scrap_calibrate.py
```

Calibration controls:

- `F6` saves the current mouse position as the top-left corner.
- `F7` saves the current mouse position as the bottom-right corner.
- `ESC` exits calibration.

After pressing `F7`, the script creates:

- `cms2021_scrap_config.json`
- `calibration_region.png`

Example config:

```json
{
  "REGION": {
    "left": 638,
    "top": 426,
    "width": 638,
    "height": 221
  }
}
```

## Usage

1. Start Car Mechanic Simulator 2021.
2. Open the salvage/scrap minigame screen.
3. Run calibration:

```powershell
python cms2021_scrap_calibrate.py
```

4. Move the mouse to the top-left of the minigame area and press `F6`.
5. Move the mouse to the bottom-right of the minigame area and press `F7`.
6. Confirm that `cms2021_scrap_config.json` was created.
7. Run the automation script:

```powershell
python cms2021_scrap_auto.py
```

8. Press `F8` to start or stop automation.

## Controls

- `F8` = toggle automation ON/OFF
- `F9` = manual `SPACE` test
- `ESC` = quit

## Configuration

`cms2021_scrap_config.json` stores the active screen capture region:

```json
{
  "REGION": {
    "left": 864,
    "top": 594,
    "width": 836,
    "height": 260
  }
}
```

In `cms2021_scrap_auto.py`:

- `USE_CONFIG_REGION` controls whether the script loads `cms2021_scrap_config.json`.
- `MANUAL_REGION` is used if config loading is disabled or fails.
- `APPROACH_DELAY_FROM_LEFT_SECONDS` and `APPROACH_DELAY_FROM_RIGHT_SECONDS` can be tuned if hits are slightly early or late.
- `QUIET_MODE` and `VERBOSE_LOGGING` control console output.

If you change monitor, resolution, display scaling, or window position, rerun calibration.

## Troubleshooting

- If the script does not detect the minigame correctly, rerun calibration.
- If the game resolution, monitor, display scaling, or window position changes, rerun calibration.
- Use Borderless Windowed or Windowed mode if fullscreen causes screen capture issues.
- Run PowerShell or CMD as Administrator if hotkeys or key presses are not detected.
- If `SPACE` is not registered by the game, press `F9` while the game is focused to test manual input.
- If detection is inaccurate, tune timing values such as `APPROACH_DELAY_FROM_LEFT_SECONDS` and `APPROACH_DELAY_FROM_RIGHT_SECONDS`.
- The `mss` `DeprecationWarning` is harmless and does not prevent the script from running.

## Safety / Limitations

- The script only uses screen capture and normal keyboard input.
- It does not modify game files.
- It does not edit memory.
- It does not use DLL injection.
- It does not use process injection.
- Detection accuracy depends on calibration, resolution, UI scaling, and lighting/color appearance.
- The game window should be focused while automation is running.

## Disclaimer

This tool is for personal experimentation and offline/single-player use. Use responsibly and respect the game's terms of service.
