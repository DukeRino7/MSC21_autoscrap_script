"""
Calibration helper for the Car Mechanic Simulator 2021 scrap minigame.

Run this first, move your mouse to the top-left of the minigame indicator,
press F6, then move to the bottom-right and press F7.

Hotkeys:
  F6  save top-left corner
  F7  save bottom-right corner and screenshot the selected region
  ESC exit
"""

import json
import time
from pathlib import Path

import keyboard
import mss
import mss.tools
import pyautogui


SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_IMAGE = SCRIPT_DIR / "calibration_region.png"
CONFIG_PATH = SCRIPT_DIR / "cms2021_scrap_config.json"

top_left = None
bottom_right = None
running = True


def current_mouse_pos():
    pos = pyautogui.position()
    return int(pos.x), int(pos.y)


def build_region(p1, p2):
    left = min(p1[0], p2[0])
    top = min(p1[1], p2[1])
    right = max(p1[0], p2[0])
    bottom = max(p1[1], p2[1])
    return {
        "left": left,
        "top": top,
        "width": max(1, right - left),
        "height": max(1, bottom - top),
    }


def save_region_screenshot(region):
    with mss.mss() as sct:
        shot = sct.grab(region)
        mss.tools.to_png(shot.rgb, shot.size, output=str(OUTPUT_IMAGE))


def save_region_config(region):
    config = {"REGION": region}
    CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")


def mark_top_left():
    global top_left
    top_left = current_mouse_pos()
    print(f"\nF6 top-left saved: {top_left}")


def mark_bottom_right():
    global bottom_right
    bottom_right = current_mouse_pos()
    print(f"\nF7 bottom-right saved: {bottom_right}")

    if top_left is None:
        print("Press F6 first to save the top-left corner.")
        return

    region = build_region(top_left, bottom_right)
    print(f'REGION = {region}')
    save_region_config(region)
    print(f"Saved config: {CONFIG_PATH.resolve()}")
    save_region_screenshot(region)
    print(f"Saved screenshot: {OUTPUT_IMAGE.resolve()}")


def quit_script():
    global running
    running = False
    print("\nESC pressed, exiting calibration.")


def main():
    keyboard.add_hotkey("f6", mark_top_left)
    keyboard.add_hotkey("f7", mark_bottom_right)
    keyboard.add_hotkey("esc", quit_script)

    print("Calibration running.")
    print("Move mouse over the minigame indicator region.")
    print("F6 = top-left, F7 = bottom-right + screenshot, ESC = quit.")

    while running:
        x, y = current_mouse_pos()
        tl_text = top_left if top_left else "not set"
        br_text = bottom_right if bottom_right else "not set"
        print(
            f"\rMouse: x={x:5d}, y={y:5d} | top-left: {tl_text} | bottom-right: {br_text}",
            end="",
            flush=True,
        )
        time.sleep(0.05)

    print()


if __name__ == "__main__":
    main()
