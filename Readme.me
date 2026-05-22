# ControlCarNintendo

Control a Nintendo Switch using real car sensor data (steering wheel, gear, signals) via a Raspberry Pi.

---

## How it works

```
Car (Android head unit)
    └── ADB over USB
        └── carStateHelper.py   reads logcat → angle, speed, gear, signals
            └── controlSwitch.py   maps angle → left + right stick
                └── switchHold.py   sends continuous input to Switch via Bluetooth
```

The steering wheel angle controls both sticks simultaneously:
- **Left stick X** — character movement
- **Right stick X** — camera pan (same direction, slower)

---

## Files

| File | Purpose |
|---|---|
| `carStateHelper.py` | Reads live car data from ADB logcat |
| `carStateMock.py` | GUI mock — drop-in replacement for testing without a car |
| `controlSwitch.py` | Maps car state to Switch inputs. Pass `--mock` to use the GUI |
| `switchHold.py` | Flask server that holds Switch inputs continuously via nxbt |
| `buttonPanel.py` | Simple tkinter window to press buttons manually (real car mode) |

---

## Dependencies

Your project needs three packages:

```bash
pip install flask requests nxbt
```

> These are already installed in `~/.venv` on the Pi.
> `nxbt` and `switchHold.py` require `sudo` to access Bluetooth.

---

## First-time setup

```bash
# 1. Install ADB (only needed once, for real car mode)
sudo apt install adb

# 2. Confirm car head unit is connected over USB
adb devices
# should show a device, not empty
```

---

## Running

### Terminal 1 — Switch server (always needed)
```bash
sudo ~/.venv/bin/python3 switchHold.py
```
Wait for `Connected!` before starting anything else.

---

### Terminal 2 — Control

**Testing (no car, GUI mock):**
```bash
python3 controlSwitch.py --mock
```
A window opens with sliders for angle, speed, gear, signals, HVAC, and doors.
Buttons on the right: `ZL` (reset camera), `A`, `B`, `PLUS`.

**In the car (real data):**
```bash
python3 controlSwitch.py
```
A small button panel opens for manual button presses.

---

## Tuning (in controlSwitch.py)

| Variable | Effect |
|---|---|
| `DEAD_ZONE` | Degrees of wheel ignored near center |
| `EFFECTIVE` | Degrees to reach full stick — lower = more sensitive |
| `CURVE` | 1.0 = linear, 2.0 = gentle then aggressive |

Right stick speed is 50% of left stick by default (`val * 0.5`).

---

## Sending buttons manually (curl)

```bash
# from any machine on the same network
curl -X POST http://raspberrypi.local:5001/press \
  -H "Content-Type: application/json" \
  -d '{"button": "A", "duration": 0.1}'
```

Available buttons: `A B X Y L R ZL ZR PLUS MINUS HOME CAPTURE DPAD_UP DPAD_DOWN DPAD_LEFT DPAD_RIGHT L_STICK_PRESS R_STICK_PRESS`

---

## Swapping mock ↔ real car

`controlSwitch.py` handles this automatically via the `--mock` flag.
If you import the helper in another script:

```python
# testing
import carStateMock as car

# real car
import carStateHelper as car

# identical from here on
car.start()
print(car.get_angle())
```
