"""
Car Mechanic Simulator 2021 scrap minigame helper.

This script uses only screen capture plus normal mouse/keyboard input. It does
not read or modify game memory, game files, DLLs, saves, or the game process.

Hotkeys:
  F8  start/stop automation
  F9  send SPACE immediately for input testing
  ESC exit

Install:
  pip install pyautogui mss opencv-python keyboard numpy pydirectinput
"""

import json
import time
from pathlib import Path

import cv2
import keyboard
import mss
import numpy as np

try:
    import pydirectinput
except ImportError:
    pydirectinput = None


USE_CONFIG_REGION = True
MANUAL_REGION = {"left": 864, "top": 594, "width": 836, "height": 260}
CONFIG_PATH = "cms2021_scrap_config.json"


def load_active_region():
    if not USE_CONFIG_REGION:
        print(f"USE_CONFIG_REGION=False, using MANUAL_REGION: {MANUAL_REGION}")
        print(f"Using REGION: {MANUAL_REGION}")
        return MANUAL_REGION.copy()

    config_path = Path(__file__).resolve().parent / CONFIG_PATH
    try:
        with config_path.open("r", encoding="utf-8") as config_file:
            data = json.load(config_file)
        region = data["REGION"]
        active_region = {
            "left": int(region["left"]),
            "top": int(region["top"]),
            "width": int(region["width"]),
            "height": int(region["height"]),
        }
        print(f"Loaded REGION from config: {active_region}")
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        active_region = MANUAL_REGION.copy()
        print(f"Could not load config, using MANUAL_REGION: {active_region}")

    print(f"Using REGION: {active_region}")
    return active_region


# Active capture region for the salvaging UI.
REGION = load_active_region()

# CMS 2021 scrap action. Do not use mouse click for the actual scrap action.
ACTION_KEY = "space"
CLICK_MOUSE = False
KEY_HOLD_SECONDS = 0.10

# Restart and hit timing.
START_DELAY_SECONDS = 0.15
AUTO_RESTART_INTERVAL_SECONDS = 0.5
POST_HIT_DELAY_SECONDS = 0.10
LOOP_SLEEP_SECONDS = 0.001
COOLDOWN_MS = 220
HIT_LOCKOUT_SECONDS = 0.65
VERBOSE_LOGGING = False
QUIET_MODE = True
LOG_ONLY_ON_SLOT_CHANGE = True
LOG_ONLY_ON_HIT = True

# Slot timing. The triangle jumps between fixed positions, so hit by slot index.
TIMING_OFFSET_PX = 0
PREDICTION_SECONDS = 0
SLOT_COUNT = 20
BAR_X1 = None
BAR_X2 = None
SLOT_TOLERANCE = 1
# If it presses one slot before blue, try SLOT_OFFSET = 1.
# If it presses one slot after blue, try SLOT_OFFSET = -1.
SLOT_OFFSET = 0
CROSSED_BLUE_ENABLED = False
STRICT_SLOT_HIT_MODE = False
EXACT_HIT_ONLY = False
WAIT_FOR_EXACT_SLOT_IF_ADJACENT = True
ADJACENT_SLOT_WAIT_SECONDS = 0.015
ADJACENT_RECHECK_ENABLED = False
ADJACENT_RECHECK_DELAY_SECONDS = 0.012
FIRST_HIT_GRACE_SECONDS = 0.20
FIRST_HIT_DELAY_SECONDS = 0.004
APPROACH_DELAY_FROM_LEFT_SECONDS = 0.016
APPROACH_DELAY_FROM_RIGHT_SECONDS = 0.016

# Bright cyan/blue target column.
BLUE_HSV_LOWER = np.array((75, 80, 120), dtype=np.uint8)
BLUE_HSV_UPPER = np.array((110, 255, 255), dtype=np.uint8)

# Orange/yellow moving downward triangle and orange start button.
POINTER_HSV_LOWER = np.array((10, 80, 120), dtype=np.uint8)
POINTER_HSV_UPPER = np.array((40, 255, 255), dtype=np.uint8)
START_BUTTON_HSV_LOWER = np.array((5, 80, 100), dtype=np.uint8)
START_BUTTON_HSV_UPPER = np.array((35, 255, 255), dtype=np.uint8)

# Detection tuning.
BLUE_MIN_AREA_RATIO = 0.00025
BLUE_MIN_HEIGHT_RATIO = 0.12
BLUE_SEARCH_Y1 = 80
BLUE_SEARCH_Y2 = REGION["height"]
POINTER_SEARCH_HEIGHT_RATIO = 0.45
POINTER_MIN_AREA = 80
POINTER_MAX_AREA = 5000
POINTER_MIN_WIDTH = 10
POINTER_MAX_WIDTH = 100
POINTER_MIN_HEIGHT = 10
POINTER_MAX_HEIGHT = 100
POINTER_MIN_ASPECT = 0.5
POINTER_MAX_ASPECT = 2.0
POINTER_STATIC_WARNING_FRAMES = 20
START_BUTTON_MIN_AREA_RATIO = 0.015
START_BUTTON_MIN_WIDTH_RATIO = 0.12
START_BUTTON_MIN_HEIGHT_RATIO = 0.08
BAR_COLOR_SATURATION_MIN = 60
BAR_COLOR_VALUE_MIN = 80
BAR_COLUMN_MIN_PIXELS = 4

# Debug frame output.
DEBUG_SAVE_FRAMES = False
DEBUG_DIR = Path("debug_frames")
DEBUG_SAVE_EVERY_N_FRAMES = 5
SHOW_DEBUG_WINDOW = False


running = True
automation_enabled = False
last_action_time = 0.0
last_any_detection_time = 0.0
frame_index = 0
last_status_line = ""
previous_triangle_pointer_x = None
stationary_pointer_frames = 0
last_pointer_warning_time = 0.0
previous_pointer_slot = None
previous_blue_slot = None
last_pointer_slot_change_time = 0.0
last_seen_pointer_slot_time = 0.0
last_hit_time = 0.0
last_start_time = 0.0
hit_sent_for_current_attempt = False
first_hit_pending = False


def now_ms():
    return time.perf_counter() * 1000.0


def now_seconds():
    return time.perf_counter()


def region_center():
    return (
        REGION["left"] + REGION["width"] // 2,
        REGION["top"] + REGION["height"] // 2,
    )


def validate_region():
    required = ("left", "top", "width", "height")
    missing = [key for key in required if key not in REGION]
    if missing:
        raise ValueError(f"REGION is missing keys: {missing}")
    if REGION["width"] <= 1 or REGION["height"] <= 1:
        raise ValueError("REGION width and height must be greater than 1.")


def move_mouse_to_region_center():
    if pydirectinput is None:
        print("Install pydirectinput with: pip install pydirectinput", flush=True)
        return False

    x, y = region_center()
    pydirectinput.moveTo(x, y)
    return True


def send_space_action(reason):
    if pydirectinput is None:
        print("Install pydirectinput with: pip install pydirectinput", flush=True)
        return False

    move_mouse_to_region_center()
    pydirectinput.keyDown("space")
    time.sleep(KEY_HOLD_SECONDS)
    pydirectinput.keyUp("space")
    print(f"\nSPACE SENT: reason={reason}", flush=True)
    return True


def toggle_automation():
    global automation_enabled, last_action_time, last_any_detection_time, hit_sent_for_current_attempt, first_hit_pending, last_start_time
    automation_enabled = not automation_enabled
    state = "ON" if automation_enabled else "OFF"
    print(f"\nF8 pressed: automation {state}")
    if automation_enabled:
        reset_triangle_motion_debug()
        last_any_detection_time = now_seconds()
        if send_space_action("initial-start"):
            last_action_time = now_ms()
            hit_sent_for_current_attempt = False
            first_hit_pending = True
            last_start_time = time.time()


def send_manual_space_test():
    print("\nF9 pressed: sending SPACE test")
    send_space_action("manual-test")


def quit_script():
    global running
    running = False
    print("\nESC pressed: exiting.")


def capture_region(sct):
    shot = sct.grab(REGION)
    frame = np.asarray(shot, dtype=np.uint8)
    return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)


def clean_mask(mask, close_iterations=2):
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=close_iterations)
    return mask


def hsv_mask(frame_bgr, lower, upper):
    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    return clean_mask(cv2.inRange(hsv, lower, upper))


def detect_start_screen(frame_bgr):
    mask = hsv_mask(frame_bgr, START_BUTTON_HSV_LOWER, START_BUTTON_HSV_UPPER)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return False, None, mask

    frame_h, frame_w = mask.shape[:2]
    min_area = frame_w * frame_h * START_BUTTON_MIN_AREA_RATIO
    min_w = frame_w * START_BUTTON_MIN_WIDTH_RATIO
    min_h = frame_h * START_BUTTON_MIN_HEIGHT_RATIO
    candidates = []

    for contour in contours:
        area = cv2.contourArea(contour)
        x, y, w, h = cv2.boundingRect(contour)
        if area >= min_area and w >= min_w and h >= min_h:
            candidates.append((area, x, y, w, h))

    if not candidates:
        return False, None, mask

    _, x, y, w, h = max(candidates, key=lambda item: item[0])
    return True, (x, y, w, h), mask


def detect_blue_target(frame_bgr):
    frame_h = frame_bgr.shape[0]
    blue_y1 = max(0, min(BLUE_SEARCH_Y1, frame_h - 1))
    blue_y2 = max(blue_y1 + 1, min(BLUE_SEARCH_Y2, frame_h))
    search_frame = frame_bgr[blue_y1:blue_y2, :]
    mask = hsv_mask(search_frame, BLUE_HSV_LOWER, BLUE_HSV_UPPER)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None, None, mask

    frame_h, frame_w = mask.shape[:2]
    min_area = frame_w * frame_h * BLUE_MIN_AREA_RATIO
    min_h = frame_h * BLUE_MIN_HEIGHT_RATIO
    candidates = []

    for contour in contours:
        area = cv2.contourArea(contour)
        x, y, w, h = cv2.boundingRect(contour)
        vertical_enough = h >= min_h and h >= max(4, w * 1.15)
        if area >= min_area and vertical_enough:
            candidates.append((area, x, y, w, h))

    if not candidates:
        return None, None, mask

    _, x, y, w, h = max(candidates, key=lambda item: item[0])
    y += blue_y1
    center_x = x + w // 2
    return (x, y, x + w, y + h), center_x, mask


def detect_pointer_triangle(frame_bgr):
    frame_h, frame_w = frame_bgr.shape[:2]
    pointer_search_y1 = 0
    pointer_search_y2 = max(1, int(REGION["height"] * POINTER_SEARCH_HEIGHT_RATIO))
    pointer_search_y2 = min(pointer_search_y2, frame_h)
    upper_frame = frame_bgr[pointer_search_y1:pointer_search_y2, :]
    upper_mask = hsv_mask(upper_frame, POINTER_HSV_LOWER, POINTER_HSV_UPPER)
    contours, _ = cv2.findContours(upper_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        return None, None, upper_mask

    candidates = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < POINTER_MIN_AREA or area > POINTER_MAX_AREA:
            continue

        x, y, w, h = cv2.boundingRect(contour)
        if y < pointer_search_y1 or y + h > pointer_search_y2:
            continue
        if w < POINTER_MIN_WIDTH or w > POINTER_MAX_WIDTH:
            continue
        if h < POINTER_MIN_HEIGHT or h > POINTER_MAX_HEIGHT:
            continue

        # Avoid top UI text or other static orange/yellow UI pieces. The moving
        # pointer is a compact downward triangle above the colored vertical bars.
        if y <= 3 and w > 45:
            continue

        aspect = w / float(h)
        if aspect < POINTER_MIN_ASPECT or aspect > POINTER_MAX_ASPECT:
            continue

        candidates.append((area, x, y, w, h))

    if not candidates:
        return None, None, upper_mask

    # After shape filtering, prefer the largest orange/yellow triangle-like blob.
    _, x, y, w, h = max(candidates, key=lambda item: item[0])
    triangle_pointer_x = x + w // 2
    return triangle_pointer_x, (x, y, w, h), upper_mask


def format_blue_rect(blue_rect):
    if blue_rect is None:
        return None
    x1, y1, x2, y2 = blue_rect
    return (x1, y1, x2 - x1, y2 - y1)


def detect_slot_centers(frame_bgr):
    if BAR_X1 is not None and BAR_X2 is not None:
        min_x = float(BAR_X1)
        max_x = float(BAR_X2)
    else:
        frame_h = frame_bgr.shape[0]
        blue_y1 = max(0, min(BLUE_SEARCH_Y1, frame_h - 1))
        blue_y2 = max(blue_y1 + 1, min(BLUE_SEARCH_Y2, frame_h))
        search_frame = frame_bgr[blue_y1:blue_y2, :]
        hsv = cv2.cvtColor(search_frame, cv2.COLOR_BGR2HSV)
        colored_mask = cv2.inRange(
            hsv,
            np.array((0, BAR_COLOR_SATURATION_MIN, BAR_COLOR_VALUE_MIN), dtype=np.uint8),
            np.array((179, 255, 255), dtype=np.uint8),
        )
        colored_mask = clean_mask(colored_mask, close_iterations=1)
        column_counts = np.count_nonzero(colored_mask, axis=0)
        xs = np.where(column_counts >= BAR_COLUMN_MIN_PIXELS)[0]
        if len(xs) == 0:
            return None

        min_x = float(xs.min())
        max_x = float(xs.max())

    if max_x <= min_x:
        return None

    slot_width = (max_x - min_x) / float(SLOT_COUNT - 1)
    return [min_x + i * slot_width for i in range(SLOT_COUNT)]


def nearest_slot(slot_centers, x):
    if slot_centers is None or x is None:
        return None
    return min(range(len(slot_centers)), key=lambda index: abs(slot_centers[index] - x))


def status_print(line):
    global last_status_line
    if not VERBOSE_LOGGING and line == last_status_line:
        return
    print(f"\r{line}", end="", flush=True)
    last_status_line = line


def likely_result_text(slot_diff, reason=None):
    if slot_diff is None:
        return "unknown"
    if reason == "approach-left":
        return "delayed from left"
    if reason == "approach-right":
        return "delayed from right"
    if abs(slot_diff) == 0:
        return "exact"
    if slot_diff == -1:
        return "one slot before"
    if slot_diff == 1:
        return "one slot after"
    return f"off by {slot_diff}"


def print_hit_debug(pointer_slot, previous_slot, blue_slot, direction, reason, delay):
    slot_diff = None if pointer_slot is None or blue_slot is None else pointer_slot - blue_slot
    print(
        "\nHIT SENT | "
        f"pointer_slot={pointer_slot} | "
        f"previous_pointer_slot={previous_slot} | "
        f"blue_slot={blue_slot} | "
        f"direction={direction} | "
        f"slot_diff={slot_diff} | "
        f"delay={delay} | "
        f"reason={reason}",
        flush=True,
    )
    if not QUIET_MODE:
        print(f"Likely result: {likely_result_text(slot_diff, reason)}", flush=True)


def update_triangle_motion_debug(triangle_pointer_x):
    global previous_triangle_pointer_x, stationary_pointer_frames, last_pointer_warning_time

    previous = previous_triangle_pointer_x
    dx = None if previous is None or triangle_pointer_x is None else triangle_pointer_x - previous

    if triangle_pointer_x is None:
        stationary_pointer_frames = 0
    elif previous is not None and triangle_pointer_x == previous:
        stationary_pointer_frames += 1
    else:
        stationary_pointer_frames = 0

    if triangle_pointer_x is not None:
        previous_triangle_pointer_x = triangle_pointer_x

    warning_ready = now_seconds() - last_pointer_warning_time >= 1.0
    if (DEBUG_SAVE_FRAMES or VERBOSE_LOGGING) and stationary_pointer_frames >= POINTER_STATIC_WARNING_FRAMES and warning_ready:
        print("\nWARNING: pointer_x is not moving, detection may be locked onto a static object", flush=True)
        last_pointer_warning_time = now_seconds()

    return previous, dx


def reset_triangle_motion_debug():
    global previous_triangle_pointer_x, stationary_pointer_frames, previous_pointer_slot, previous_blue_slot
    previous_triangle_pointer_x = None
    stationary_pointer_frames = 0
    previous_pointer_slot = None
    previous_blue_slot = None


def annotate_frame(frame, state, blue_rect, triangle_pointer_x, pointer_bbox, hit, start_button_rect):
    annotated = frame.copy()

    if start_button_rect is not None:
        x, y, w, h = start_button_rect
        cv2.rectangle(annotated, (x, y), (x + w, y + h), (0, 140, 255), 2)
        cv2.putText(annotated, "START", (x, max(14, y - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 140, 255), 1)

    if blue_rect is not None:
        x1, y1, x2, y2 = blue_rect
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (255, 255, 0), 2)
        cv2.putText(annotated, "BLUE TARGET", (x1, max(14, y1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

    if pointer_bbox is not None:
        x, y, w, h = pointer_bbox
        cv2.rectangle(annotated, (x, y), (x + w, y + h), (0, 165, 255), 2)
        cv2.putText(annotated, "TRIANGLE", (x, min(frame.shape[0] - 5, y + h + 14)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 165, 255), 1)

    if triangle_pointer_x is not None:
        color = (0, 255, 0) if hit else (0, 255, 255)
        cv2.line(annotated, (triangle_pointer_x, 0), (triangle_pointer_x, frame.shape[0] - 1), color, 2)
        cv2.putText(annotated, f"triangle_x={triangle_pointer_x}", (max(4, triangle_pointer_x - 58), 30), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)

    hit_text = "hit=True" if hit else "hit=False"
    cv2.putText(annotated, f"state={state} {hit_text}", (8, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0) if hit else (0, 0, 255), 2)
    return annotated


def maybe_save_debug_frame(frame, state, blue_rect, triangle_pointer_x, pointer_bbox, hit, start_button_rect):
    global frame_index
    frame_index += 1

    if not DEBUG_SAVE_FRAMES:
        return
    if frame_index % DEBUG_SAVE_EVERY_N_FRAMES != 0 and not hit:
        return

    DEBUG_DIR.mkdir(exist_ok=True)
    annotated = annotate_frame(frame, state, blue_rect, triangle_pointer_x, pointer_bbox, hit, start_button_rect)
    filename = DEBUG_DIR / f"frame_{frame_index:06d}_{state}.png"
    cv2.imwrite(str(filename), annotated)


def handle_minigame(blue_rect, triangle_pointer_x, slot_centers, cooldown_ready, sct=None):
    global last_action_time, previous_pointer_slot, last_pointer_slot_change_time, last_seen_pointer_slot_time, last_hit_time, hit_sent_for_current_attempt, first_hit_pending

    if blue_rect is None or triangle_pointer_x is None:
        return False, None, previous_pointer_slot, None, None, False, None

    blue_x1, _, blue_x2, _ = blue_rect
    blue_center_x = blue_x1 + (blue_x2 - blue_x1) / 2.0
    blue_slot = nearest_slot(slot_centers, blue_center_x)
    pointer_slot = nearest_slot(slot_centers, triangle_pointer_x)
    if blue_slot is None or pointer_slot is None:
        return False, pointer_slot, previous_pointer_slot, blue_slot, None, False, None

    previous_slot_for_debug = previous_pointer_slot
    now = now_seconds()
    last_seen_pointer_slot_time = now
    if previous_pointer_slot is None or pointer_slot != previous_pointer_slot:
        last_pointer_slot_change_time = now

    effective_pointer_slot = pointer_slot + SLOT_OFFSET
    crossed_blue = not STRICT_SLOT_HIT_MODE and CROSSED_BLUE_ENABLED and (
        previous_pointer_slot is not None
        and min(previous_pointer_slot, pointer_slot) <= blue_slot <= max(previous_pointer_slot, pointer_slot)
    )
    exact_hit = effective_pointer_slot == blue_slot
    slot_diff = pointer_slot - blue_slot
    direction = 0
    if previous_pointer_slot is not None:
        if pointer_slot > previous_pointer_slot:
            direction = 1
        elif pointer_slot < previous_pointer_slot:
            direction = -1

    if first_hit_pending and time.time() - last_start_time < FIRST_HIT_GRACE_SECONDS:
        previous_pointer_slot = pointer_slot
        return False, pointer_slot, previous_slot_for_debug, blue_slot, effective_pointer_slot, crossed_blue, None

    hit = False
    hit_reason = None
    hit_delay = 0.0
    if exact_hit:
        hit = True
        hit_reason = "exact-slot"
    elif pointer_slot == blue_slot - 1 and direction == 1:
        hit = True
        hit_reason = "approach-left"
        hit_delay = APPROACH_DELAY_FROM_LEFT_SECONDS
    elif pointer_slot == blue_slot + 1 and direction == -1:
        hit = True
        hit_reason = "approach-right"
        hit_delay = APPROACH_DELAY_FROM_RIGHT_SECONDS

    adjacent = abs(pointer_slot - blue_slot) == 1
    if (
        not hit
        and not STRICT_SLOT_HIT_MODE
        and ADJACENT_RECHECK_ENABLED
        and adjacent
        and cooldown_ready
        and sct is not None
    ):
        old_pointer_slot = pointer_slot
        time.sleep(ADJACENT_RECHECK_DELAY_SECONDS)
        recheck_frame = capture_region(sct)
        recheck_blue_rect, _, _ = detect_blue_target(recheck_frame)
        recheck_pointer_x, _, _ = detect_pointer_triangle(recheck_frame)
        recheck_slot_centers = detect_slot_centers(recheck_frame)
        recheck_hit = False
        recheck_pointer_slot = None
        recheck_blue_slot = blue_slot
        if recheck_blue_rect is not None and recheck_pointer_x is not None and recheck_slot_centers is not None:
            recheck_blue_x1, _, recheck_blue_x2, _ = recheck_blue_rect
            recheck_blue_center_x = recheck_blue_x1 + (recheck_blue_x2 - recheck_blue_x1) / 2.0
            recheck_blue_slot = nearest_slot(recheck_slot_centers, recheck_blue_center_x)
            recheck_pointer_slot = nearest_slot(recheck_slot_centers, recheck_pointer_x)
            if recheck_pointer_slot == recheck_blue_slot:
                pointer_slot = recheck_pointer_slot
                blue_slot = recheck_blue_slot
                effective_pointer_slot = pointer_slot + SLOT_OFFSET
                hit = True
                exact_hit = True
                recheck_hit = True
                hit_reason = "adjacent-recheck"
        if not QUIET_MODE:
            print(
                "\nADJACENT RECHECK | "
                f"old_pointer_slot={old_pointer_slot} | "
                f"new_pointer_slot={recheck_pointer_slot} | "
                f"blue_slot={recheck_blue_slot} | "
                f"hit={recheck_hit}",
                flush=True,
            )

    hit_lockout_ready = time.time() - last_hit_time >= HIT_LOCKOUT_SECONDS
    if hit and cooldown_ready and hit_lockout_ready and not hit_sent_for_current_attempt:
        if hit_delay > 0:
            time.sleep(hit_delay)
        if send_space_action("blue-target-hit"):
            last_action_time = now_ms()
            last_hit_time = time.time()
            hit_sent_for_current_attempt = True
            first_hit_pending = False
            print_hit_debug(pointer_slot, previous_slot_for_debug, blue_slot, direction, hit_reason, hit_delay)
            time.sleep(POST_HIT_DELAY_SECONDS)

    previous_pointer_slot = pointer_slot
    return hit, pointer_slot, previous_slot_for_debug, blue_slot, effective_pointer_slot, crossed_blue, hit_reason


def main():
    global last_action_time, last_any_detection_time, previous_blue_slot, last_hit_time, hit_sent_for_current_attempt, first_hit_pending, last_start_time

    validate_region()
    if pydirectinput is None:
        print("Install pydirectinput with: pip install pydirectinput")
    else:
        pydirectinput.PAUSE = 0

    keyboard.add_hotkey("f8", toggle_automation)
    keyboard.add_hotkey("f9", send_manual_space_test)
    keyboard.add_hotkey("esc", quit_script)

    print("CMS 2021 scrap automation ready.")
    print("F8 = toggle automation, F9 = manual SPACE test, ESC = quit.")
    print(f"REGION = {REGION}")
    print(f"ACTION_KEY = {ACTION_KEY!r}, KEY_HOLD_SECONDS = {KEY_HOLD_SECONDS}")

    with mss.mss() as sct:
        while running:
            frame = capture_region(sct)
            state = "idle"
            blue_rect = None
            triangle_pointer_x = None
            pointer_bbox = None
            start_button_rect = None
            hit = False
            slot_centers = None
            pointer_slot = None
            previous_slot_for_debug = None
            blue_slot = None
            effective_pointer_slot = None
            crossed_blue = False
            hit_reason = None
            valid_minigame = False

            cooldown_ready = now_ms() - last_action_time >= COOLDOWN_MS

            if automation_enabled:
                state = "minigame"
                blue_rect, _, _ = detect_blue_target(frame)
                triangle_pointer_x, pointer_bbox, _ = detect_pointer_triangle(frame)
                slot_centers = detect_slot_centers(frame)
                update_triangle_motion_debug(triangle_pointer_x)

                valid_minigame = blue_rect is not None and triangle_pointer_x is not None and slot_centers is not None
                if blue_rect is not None or triangle_pointer_x is not None:
                    last_any_detection_time = now_seconds()

                (
                    hit,
                    pointer_slot,
                    previous_slot_for_debug,
                    blue_slot,
                    effective_pointer_slot,
                    crossed_blue,
                    hit_reason,
                ) = handle_minigame(blue_rect, triangle_pointer_x, slot_centers, cooldown_ready, sct)

                no_detection_for = now_seconds() - last_any_detection_time
                should_auto_restart = (
                    blue_rect is None
                    and triangle_pointer_x is None
                    and no_detection_for >= AUTO_RESTART_INTERVAL_SECONDS
                    and cooldown_ready
                    and time.time() - last_hit_time >= HIT_LOCKOUT_SECONDS
                )
                if should_auto_restart:
                    if send_space_action("auto-restart"):
                        last_action_time = now_ms()
                        hit_sent_for_current_attempt = False
                        first_hit_pending = True
                        last_start_time = time.time()
                    time.sleep(START_DELAY_SECONDS)
                    last_any_detection_time = now_seconds()

                pointer_slot_changed = pointer_slot is not None and pointer_slot != previous_slot_for_debug
                blue_slot_changed = blue_slot is not None and blue_slot != previous_blue_slot
                should_log = VERBOSE_LOGGING
                if should_log:
                    status_print(
                        "Watching | "
                        f"pointer_x={triangle_pointer_x} | "
                        f"pointer_slot={pointer_slot} | "
                        f"previous_pointer_slot={previous_slot_for_debug} | "
                        f"blue_x={format_blue_rect(blue_rect)} | "
                        f"blue_slot={blue_slot} | "
                        f"effective_pointer_slot={effective_pointer_slot} | "
                        f"slot_offset={SLOT_OFFSET} | "
                        f"slot_tolerance={SLOT_TOLERANCE} | "
                        f"crossed_blue={crossed_blue} | "
                        f"reason={hit_reason} | "
                        f"hit={hit}"
                    )
                if blue_slot is not None:
                    previous_blue_slot = blue_slot
            maybe_save_debug_frame(frame, state, blue_rect, triangle_pointer_x, pointer_bbox, hit, start_button_rect)

            if SHOW_DEBUG_WINDOW:
                cv2.imshow("CMS 2021 scrap debug", annotate_frame(frame, state, blue_rect, triangle_pointer_x, pointer_bbox, hit, start_button_rect))
                cv2.waitKey(1)

            time.sleep(LOOP_SLEEP_SECONDS)

    cv2.destroyAllWindows()
    print("\nExited.")


if __name__ == "__main__":
    main()
