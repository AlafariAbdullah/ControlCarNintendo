import sys
import requests
import threading
import time
import math

SWITCH_URL  = "http://localhost:5001"
DEAD_ZONE   = 3.0
EFFECTIVE   = 12.0
CURVE       = 1.5
DELTA_NOISE = 0.5

use_mock = "--mock" in sys.argv
if use_mock:
    import carStateMock as car
else:
    import carStateHelper as car


def shaped(angle):
    if abs(angle) < DEAD_ZONE:
        return 0.0
    adjusted   = abs(angle) - DEAD_ZONE
    normalized = min(adjusted / EFFECTIVE, 1.0)
    curved     = math.pow(normalized, CURVE)
    return math.copysign(curved * 100.0, angle)


def send_stick(stick, x):
    try:
        requests.post(f"{SWITCH_URL}/stick", json={
            "stick": stick,
            "x": max(-100, min(100, round(x))),
            "y": 0,
            "duration": 0.2
        }, timeout=0.5)
    except Exception as e:
        print(f"error: {e}")


def press(btn):
    try:
        requests.post(f"{SWITCH_URL}/press",
                      json={"button": btn, "duration": 0.1}, timeout=1)
    except Exception as e:
        print(f"error: {e}")


# --- Steering wheel button mappings ---

@car.on_button("media_next")
def on_media_next():
    threading.Thread(target=press, args=("ZL",), daemon=True).start()

@car.on_button("media_prev")
def on_media_prev():
    threading.Thread(target=press, args=("PLUS",), daemon=True).start()

@car.on_button("voice")
def on_voice():
    threading.Thread(target=press, args=("A",), daemon=True).start()

@car.on_button("phone")
def on_phone():
    pass

@car.on_button("volume_up")
def on_volume_up():
    threading.Thread(target=press, args=("B",), daemon=True).start()

@car.on_button("volume_down")
def on_volume_down():
    threading.Thread(target=press, args=("DPAD_DOWN",), daemon=True).start()


# --- Control loop ---

def control_loop():
    last_l = last_r = None
    last_angle = car.get_angle()

    while True:
        angle = car.get_angle()
        last_angle = angle

        val = shaped(angle)
        l   = round(val) / 1.5
        r   = round(val) / 1.5

        if l != last_l:
            send_stick("left_stick", l)
            last_l = l
        if r != last_r:
            send_stick("right_stick", r)
            last_r = r

        time.sleep(0.05)


car.start()
t = threading.Thread(target=control_loop, daemon=True)
t.start()

if use_mock:
    car.run_gui()
else:
    import buttonPanel
