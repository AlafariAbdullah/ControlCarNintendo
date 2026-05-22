import re
import subprocess
import threading
import time

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


def _compute_signed_angle(angle, sign):
    return -angle if sign == 0 else angle


def _map_gear(raw):
    return {
        0: "P",
        5: "D",
        6: "N",
        7: "R",
        8: "M",
    }.get(raw, f"unknown({raw})")


def _map_blow_mode(raw):
    return {
        0: "face",
        1: "face_and_feet",
        2: "feet",
        3: "defrost_and_feet",
    }.get(raw, f"unknown({raw})")


def _map_power_mode(raw):
    return {
        0: "off",
        2: "on",
        3: "acc",
    }.get(raw, f"unknown({raw})")


def _map_engine(raw):
    return {
        0: "off",
        1: "starting",
        2: "on",
    }.get(raw, f"unknown({raw})")


def _update_signal_state(now):
    active_window = 0.9

    left_active = now - _state["signals"]["last_left_on"] <= active_window if _state["signals"]["last_left_on"] else False
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

    cmd = ["adb", "logcat", "-v", "raw"]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    angle_re = re.compile(r"SteerWheelAngle =([0-9.]+)")
    sign_re = re.compile(r"SteerWheelAngleSign =([01])")
    speed_re = re.compile(r"SENSOR_TYPE_CAR_SPEED ([0-9.]+)")
    tgs_re = re.compile(r"TGSLever =([0-9]+)")
    door_re = re.compile(r"(DRVDoorStatus|PASSDoorStatus|RRDoorStatus|RLDoorStatus|TrunkStatus) =([01])")
    left_signal_re = re.compile(r"LeftTurnSWStatus =([01])")
    right_signal_re = re.compile(r"RightTurnSWStatus =([01])")

    driver_temp_re = re.compile(r"Driver Temp=([0-9.]+)")
    passenger_temp_re = re.compile(r"Passenger Temp=([0-9.]+)")
    blow_speed_re = re.compile(r"Blow Speed(?: Set)?=([0-9]+)")
    blow_mode_re = re.compile(r"Blow Mode=([0-9]+)")
    power_mode_re = re.compile(r"GWMV2_SYSTEMPOWERMODE\s+CarPropertyValue\s+==\s+([0-9]+)")
    engine_re = re.compile(r"(?:updateProperty: )?Engine=([0-9]+)")

    try:
        for line in proc.stdout:
            if not _running:
                break
            now = time.monotonic()

            # Steering
            angle_match = angle_re.search(line)
            sign_match = sign_re.search(line)

            if sign_match:
                _state["angle_sign"] = int(sign_match.group(1))

            if angle_match:
                angle = float(angle_match.group(1))
                _state["angle"] = _compute_signed_angle(angle, _state["angle_sign"])

            # Speed
            speed_match = speed_re.search(line)
            if speed_match:
                speed_ms = float(speed_match.group(1))
                _state["speed_kmh"] = speed_ms * 3.6

            # Gearbox
            tgs_match = tgs_re.search(line)
            if tgs_match:
                _state["gear_raw"] = int(tgs_match.group(1))

            # Doors and trunk
            door_match = door_re.search(line)
            if door_match:
                signal_name = door_match.group(1)
                is_open = "open" if int(door_match.group(2)) == 1 else "closed"

                door_map = {
                    "DRVDoorStatus": "driver",
                    "PASSDoorStatus": "front_passenger",
                    "RRDoorStatus": "rear_right",
                    "RLDoorStatus": "rear_left",
                    "TrunkStatus": "trunk",
                }
                _state["doors"][door_map[signal_name]] = is_open

            # Turn signals
            left_signal_match = left_signal_re.search(line)
            if left_signal_match:
                left_value = int(left_signal_match.group(1))
                _state["signals"]["left"] = "on" if left_value == 1 else "off"
                if left_value == 1:
                    _state["signals"]["last_left_on"] = now

            right_signal_match = right_signal_re.search(line)
            if right_signal_match:
                right_value = int(right_signal_match.group(1))
                _state["signals"]["right"] = "on" if right_value == 1 else "off"
                if right_value == 1:
                    _state["signals"]["last_right_on"] = now

            _update_signal_state(now)

            # HVAC
            driver_temp_match = driver_temp_re.search(line)
            if driver_temp_match:
                _state["hvac"]["driver_temp"] = float(driver_temp_match.group(1))

            passenger_temp_match = passenger_temp_re.search(line)
            if passenger_temp_match:
                _state["hvac"]["passenger_temp"] = float(passenger_temp_match.group(1))

            blow_speed_match = blow_speed_re.search(line)
            if blow_speed_match:
                _state["hvac"]["blow_speed"] = int(blow_speed_match.group(1))

            blow_mode_match = blow_mode_re.search(line)
            if blow_mode_match:
                raw_mode = int(blow_mode_match.group(1))
                _state["hvac"]["blow_mode_raw"] = raw_mode
                _state["hvac"]["blow_mode"] = _map_blow_mode(raw_mode)

            # Power state
            power_mode_match = power_mode_re.search(line)
            if power_mode_match:
                raw_power_mode = int(power_mode_match.group(1))
                _state["power"]["mode_raw"] = raw_power_mode
                _state["power"]["mode"] = _map_power_mode(raw_power_mode)

            engine_match = engine_re.search(line)
            if engine_match:
                raw_engine = int(engine_match.group(1))
                _state["power"]["engine_raw"] = raw_engine
                _state["power"]["engine"] = _map_engine(raw_engine)

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


def get_angle():
    return _state["angle"]


def get_speed():
    return _state["speed_kmh"]


def get_gear():
    return _map_gear(_state["gear_raw"])


def get_doors():
    return dict(_state["doors"])


def get_signals():
    return {
        "left": _state["signals"]["left"],
        "right": _state["signals"]["right"],
        "direction": _state["signals"]["direction"],
        "hazard": _state["signals"]["hazard"],
    }


def get_hvac():
    return dict(_state["hvac"])


def get_power():
    return dict(_state["power"])


def get_state():
    return {
        "angle": _state["angle"],
        "speed_kmh": _state["speed_kmh"],
        "gear": _map_gear(_state["gear_raw"]),
        "doors": dict(_state["doors"]),
        "signals": get_signals(),
        "hvac": dict(_state["hvac"]),
        "power": dict(_state["power"]),
        "event": detect_event(),
    }
def detect_event():
    speed = _state["speed_kmh"]
    angle = _state["angle"]          # already signed
    gear = _map_gear(_state["gear_raw"])
    signal_dir = _state["signals"]["direction"]
    hazard = _state["signals"]["hazard"]

    abs_angle = abs(angle)

    straight_threshold = 3
    turn_threshold = 10
    sharp_turn_threshold = 25
    moving_threshold = 1

    if speed <= moving_threshold:
        if gear == "R":
            if abs_angle >= turn_threshold:
                return "reversing_and_turning"
            return "reversing"
        if abs_angle >= turn_threshold:
            return "stopped_wheel_turned"
        return "stopped"

    if hazard == "on":
        if abs_angle >= sharp_turn_threshold:
            return "moving_with_hazard_sharp_turn"
        if abs_angle >= turn_threshold:
            return "moving_with_hazard_turning"
        return "moving_with_hazard"

    if angle <= -sharp_turn_threshold:
        if signal_dir == "left":
            return "sharp_left_turn_with_signal"
        if signal_dir == "right":
            return "sharp_left_turn_wrong_signal"
        return "sharp_left_turn_no_signal"

    if angle >= sharp_turn_threshold:
        if signal_dir == "right":
            return "sharp_right_turn_with_signal"
        if signal_dir == "left":
            return "sharp_right_turn_wrong_signal"
        return "sharp_right_turn_no_signal"

    if angle <= -turn_threshold:
        if signal_dir == "left":
            return "left_turn_with_signal"
        if signal_dir == "right":
            return "left_turn_wrong_signal"
        return "left_turn_no_signal"

    if angle >= turn_threshold:
        if signal_dir == "right":
            return "right_turn_with_signal"
        if signal_dir == "left":
            return "right_turn_wrong_signal"
        return "right_turn_no_signal"

    if signal_dir == "left":
        return "left_signal_on_straight"

    if signal_dir == "right":
        return "right_signal_on_straight"

    if abs_angle <= straight_threshold:
        return "stable_drive"

    return "minor_steering_adjustment"
def get_event():
    return detect_event()


