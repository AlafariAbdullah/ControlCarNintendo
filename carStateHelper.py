import re
import subprocess
import threading
import time
from datetime import datetime

# Internal state
_running = False
_thread = None
_state = {
    "angle": 0.0,
    "speed_kmh": 0.0,
    "angle_sign": 1,
    "gear_raw": 0,
    "doors": {
        "driver": "closed",
        "front_passenger": "closed",
        "rear_right": "closed",
        "rear_left": "closed",
        "trunk": "closed",
    },
    "signals": {
        "left": "off",
        "right": "off",
        "direction": "none",
        "hazard": "off",
        "last_left_on": 0.0,
        "last_right_on": 0.0,
    },
    "hvac": {
        "driver_temp": 0.0,
        "passenger_temp": 0.0,
        "blow_speed": 0,
        "blow_mode_raw": 0,
        "blow_mode": "face",
    },
    "power": {
        "mode_raw": 0,
        "mode": "off",
        "engine_raw": 0,
        "engine": "off",
    },
}

# Button keycodes
BUTTON = {
    "media_next":  87,
    "media_prev":  88,
    "voice":      285,
    "phone":      292,
    "volume_up":   24,
    "volume_down": 25,
}

_KEYCODE_TO_NAME = {v: k for k, v in BUTTON.items()}
_button_callbacks = {}


def on_button(button, action="press"):
    def decorator(fn):
        keycode = BUTTON.get(button)
        if keycode is None:
            raise ValueError(f"Unknown button: {button}. Valid: {list(BUTTON.keys())}")
        if keycode not in _button_callbacks:
            _button_callbacks[keycode] = {}
        _button_callbacks[keycode][action] = fn
        return fn
    return decorator


def _fire_button(keycode, action, is_long_press):
    callbacks = _button_callbacks.get(keycode)
    if not callbacks:
        return
    if is_long_press and "long_press" in callbacks:
        callbacks["long_press"]()
    elif action == 0 and "press" in callbacks:
        callbacks["press"]()
    elif action == 1 and "release" in callbacks:
        callbacks["release"]()


def _compute_signed_angle(angle, sign):
    return -angle if sign == 0 else angle


def _map_gear(raw):
    return {0: "P", 5: "D", 6: "N", 7: "R", 8: "M"}.get(raw, f"unknown({raw})")


def _map_blow_mode(raw):
    return {0: "face", 1: "face_and_feet", 2: "feet", 3: "defrost_and_feet"}.get(raw, f"unknown({raw})")


def _map_power_mode(raw):
    return {0: "off", 2: "on", 3: "acc"}.get(raw, f"unknown({raw})")


def _map_engine(raw):
    return {0: "off", 1: "starting", 2: "on"}.get(raw, f"unknown({raw})")


def _update_signal_state(now):
    active_window = 0.9
    left_active  = now - _state["signals"]["last_left_on"]  <= active_window if _state["signals"]["last_left_on"]  else False
    right_active = now - _state["signals"]["last_right_on"] <= active_window if _state["signals"]["last_right_on"] else False

    if left_active and right_active:
        _state["signals"]["direction"] = "hazard"
        _state["signals"]["hazard"] = "on"
    elif left_active:
        _state["signals"]["direction"] = "left"
        _state["signals"]["hazard"] = "off"
    elif right_active:
        _state["signals"]["direction"] = "right"
        _state["signals"]["hazard"] = "off"
    else:
        _state["signals"]["direction"] = "none"
        _state["signals"]["hazard"] = "off"


def _parse_logcat():
    global _running

    # Record start time as "MM-DD HH:MM:SS.mmm" to match logcat -v time format
    now_dt = datetime.now()
    start_ts = now_dt.strftime("%m-%d %H:%M:%S.") + f"{now_dt.microsecond // 1000:03d}"

    proc = subprocess.Popen(
        ["adb", "logcat", "-v", "time"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    # MM-DD HH:MM:SS.mmm at start of line
    ts_re = re.compile(r"^(\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})")

    angle_re          = re.compile(r"SteerWheelAngle =([0-9.]+)")
    sign_re           = re.compile(r"SteerWheelAngleSign =([01])")
    speed_re          = re.compile(r"SENSOR_TYPE_CAR_SPEED ([0-9.]+)")
    tgs_re            = re.compile(r"TGSLever =([0-9]+)")
    door_re           = re.compile(r"(DRVDoorStatus|PASSDoorStatus|RRDoorStatus|RLDoorStatus|TrunkStatus) =([01])")
    left_sig_re       = re.compile(r"LeftTurnSWStatus =([01])")
    right_sig_re      = re.compile(r"RightTurnSWStatus =([01])")
    driver_temp_re    = re.compile(r"Driver Temp=([0-9.]+)")
    passenger_temp_re = re.compile(r"Passenger Temp=([0-9.]+)")
    blow_speed_re     = re.compile(r"Blow Speed(?: Set)?=([0-9]+)")
    blow_mode_re      = re.compile(r"Blow Mode=([0-9]+)")
    power_mode_re     = re.compile(r"GWMV2_SYSTEMPOWERMODE\s+CarPropertyValue\s+==\s+([0-9]+)")
    engine_re         = re.compile(r"(?:updateProperty: )?Engine=([0-9]+)")
    button_re         = re.compile(r"HK event received! keycode:(\d+) action:(\d+) repeat:(\d+) flags:(\d+)")

    try:
        for line in proc.stdout:
            if not _running:
                break
            now = time.monotonic()

            # Skip lines older than start time
            ts_match = ts_re.match(line)
            if ts_match and ts_match.group(1) < start_ts:
                continue

            # Buttons
            m = button_re.search(line)
            if m:
                _fire_button(int(m.group(1)), int(m.group(2)), int(m.group(4)) == 128)

            # Steering
            m = sign_re.search(line)
            if m: _state["angle_sign"] = int(m.group(1))

            m = angle_re.search(line)
            if m: _state["angle"] = _compute_signed_angle(float(m.group(1)), _state["angle_sign"])

            # Speed
            m = speed_re.search(line)
            if m: _state["speed_kmh"] = float(m.group(1)) * 3.6

            # Gear
            m = tgs_re.search(line)
            if m: _state["gear_raw"] = int(m.group(1))

            # Doors
            m = door_re.search(line)
            if m:
                door_map = {"DRVDoorStatus": "driver", "PASSDoorStatus": "front_passenger", "RRDoorStatus": "rear_right", "RLDoorStatus": "rear_left", "TrunkStatus": "trunk"}
                _state["doors"][door_map[m.group(1)]] = "open" if int(m.group(2)) == 1 else "closed"

            # Turn signals
            m = left_sig_re.search(line)
            if m:
                v = int(m.group(1))
                _state["signals"]["left"] = "on" if v else "off"
                if v: _state["signals"]["last_left_on"] = now

            m = right_sig_re.search(line)
            if m:
                v = int(m.group(1))
                _state["signals"]["right"] = "on" if v else "off"
                if v: _state["signals"]["last_right_on"] = now

            _update_signal_state(now)

            # HVAC
            m = driver_temp_re.search(line)
            if m: _state["hvac"]["driver_temp"] = float(m.group(1))

            m = passenger_temp_re.search(line)
            if m: _state["hvac"]["passenger_temp"] = float(m.group(1))

            m = blow_speed_re.search(line)
            if m: _state["hvac"]["blow_speed"] = int(m.group(1))

            m = blow_mode_re.search(line)
            if m:
                _state["hvac"]["blow_mode_raw"] = int(m.group(1))
                _state["hvac"]["blow_mode"] = _map_blow_mode(int(m.group(1)))

            # Power
            m = power_mode_re.search(line)
            if m:
                _state["power"]["mode_raw"] = int(m.group(1))
                _state["power"]["mode"] = _map_power_mode(int(m.group(1)))

            m = engine_re.search(line)
            if m:
                _state["power"]["engine_raw"] = int(m.group(1))
                _state["power"]["engine"] = _map_engine(int(m.group(1)))

    finally:
        proc.kill()


def start(clear_log=False):
    global _running, _thread
    if _running:
        return
    if clear_log:
        subprocess.run(["adb", "logcat", "-c"])
    _running = True
    _thread = threading.Thread(target=_parse_logcat, daemon=True)
    _thread.start()


def stop():
    global _running
    _running = False


def get_angle():   return _state["angle"]
def get_speed():   return _state["speed_kmh"]
def get_gear():    return _map_gear(_state["gear_raw"])
def get_doors():   return dict(_state["doors"])
def get_signals(): return {"left": _state["signals"]["left"], "right": _state["signals"]["right"], "direction": _state["signals"]["direction"], "hazard": _state["signals"]["hazard"]}
def get_hvac():    return dict(_state["hvac"])
def get_power():   return dict(_state["power"])
def get_event():   return detect_event()

def get_state():
    return {
        "angle":     _state["angle"],
        "speed_kmh": _state["speed_kmh"],
        "gear":      _map_gear(_state["gear_raw"]),
        "doors":     dict(_state["doors"]),
        "signals":   get_signals(),
        "hvac":      dict(_state["hvac"]),
        "power":     dict(_state["power"]),
        "event":     detect_event(),
    }


def detect_event():
    speed      = _state["speed_kmh"]
    angle      = _state["angle"]
    gear       = _map_gear(_state["gear_raw"])
    signal_dir = _state["signals"]["direction"]
    hazard     = _state["signals"]["hazard"]
    abs_angle  = abs(angle)

    straight_threshold   = 3
    turn_threshold       = 10
    sharp_turn_threshold = 25
    moving_threshold     = 1

    if speed <= moving_threshold:
        if gear == "R":
            return "reversing_and_turning" if abs_angle >= turn_threshold else "reversing"
        return "stopped_wheel_turned" if abs_angle >= turn_threshold else "stopped"

    if hazard == "on":
        if abs_angle >= sharp_turn_threshold: return "moving_with_hazard_sharp_turn"
        if abs_angle >= turn_threshold:       return "moving_with_hazard_turning"
        return "moving_with_hazard"

    if angle <= -sharp_turn_threshold:
        if signal_dir == "left":  return "sharp_left_turn_with_signal"
        if signal_dir == "right": return "sharp_left_turn_wrong_signal"
        return "sharp_left_turn_no_signal"

    if angle >= sharp_turn_threshold:
        if signal_dir == "right": return "sharp_right_turn_with_signal"
        if signal_dir == "left":  return "sharp_right_turn_wrong_signal"
        return "sharp_right_turn_no_signal"

    if angle <= -turn_threshold:
        if signal_dir == "left":  return "left_turn_with_signal"
        if signal_dir == "right": return "left_turn_wrong_signal"
        return "left_turn_no_signal"

    if angle >= turn_threshold:
        if signal_dir == "right": return "right_turn_with_signal"
        if signal_dir == "left":  return "right_turn_wrong_signal"
        return "right_turn_no_signal"

    if signal_dir == "left":  return "left_signal_on_straight"
    if signal_dir == "right": return "right_signal_on_straight"
    if abs_angle <= straight_threshold: return "stable_drive"
    return "minor_steering_adjustment"
