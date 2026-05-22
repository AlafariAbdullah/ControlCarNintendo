import sys
import requests
import threading
import time
import math

SWITCH_URL = "http://localhost:5001"
DEAD_ZONE  = 3.0
EFFECTIVE  = 12.0
CURVE      = 1.5

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

def control_loop():
    last_l = last_r = None
    while True:
        val = shaped(car.get_angle())
        l   = round(val)
        r   = round(val)
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
