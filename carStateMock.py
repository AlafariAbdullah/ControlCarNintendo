"""
carStateMock.py
---------------
Drop-in replacement for carStateHelper.py with an interactive GUI.

Swap:
    import carStateHelper as car   →   import carStateMock as car

All public functions are identical:
    start(), stop()
    get_angle(), get_speed(), get_gear()
    get_doors(), get_signals(), get_hvac(), get_power()
    get_state(), get_event()

Run standalone to open the control window:
    python carStateMock.py
"""

import random
import time
import threading
import tkinter as tk
from tkinter import ttk

# ── internal state (mirrors carStateHelper._state) ────────────────────────────

_state = {
    "angle":        0.0,
    "angle_target": 0.0,
    "speed_kmh":    0.0,
    "speed_target": 0.0,
    "gear_raw":     0,
    "doors": {
        "driver":          "closed",
        "front_passenger": "closed",
        "rear_right":      "closed",
        "rear_left":       "closed",
        "trunk":           "closed",
    },
    "signals": {
        "left":          "off",
        "right":         "off",
        "direction":     "none",
        "hazard":        "off",
        "last_left_on":  0.0,
        "last_right_on": 0.0,
    },
    "hvac": {
        "driver_temp":    22.0,
        "passenger_temp": 22.0,
        "blow_speed":     3,
        "blow_mode_raw":  0,
        "blow_mode":      "face",
    },
    "power": {
        "mode_raw":   2,
        "mode":       "on",
        "engine_raw": 2,
        "engine":     "on",
    },
}

_lock    = threading.Lock()
_running = False

# ── helpers (identical to carStateHelper.py) ──────────────────────────────────

def _map_gear(raw):
    return {0: "P", 5: "D", 6: "N", 7: "R", 8: "M"}.get(raw, f"unknown({raw})")

def _map_blow_mode(raw):
    return {
        0: "face", 1: "face_and_feet",
        2: "feet", 3: "defrost_and_feet",
    }.get(raw, f"unknown({raw})")

def _map_power_mode(raw):
    return {0: "off", 2: "on", 3: "acc"}.get(raw, f"unknown({raw})")

def _map_engine(raw):
    return {0: "off", 1: "starting", 2: "on"}.get(raw, f"unknown({raw})")

def _update_signal_state(now):
    active_window = 0.9
    last_l = _state["signals"]["last_left_on"]
    last_r = _state["signals"]["last_right_on"]
    left_active  = bool(last_l) and (now - last_l <= active_window)
    right_active = bool(last_r) and (now - last_r <= active_window)

    if left_active and right_active:
        _state["signals"]["direction"] = "hazard"
        _state["signals"]["hazard"]    = "on"
    elif left_active:
        _state["signals"]["direction"] = "left"
        _state["signals"]["hazard"]    = "off"
    elif right_active:
        _state["signals"]["direction"] = "right"
        _state["signals"]["hazard"]    = "off"
    else:
        _state["signals"]["direction"] = "none"
        _state["signals"]["hazard"]    = "off"

# ── simulation tick ───────────────────────────────────────────────────────────

def _sim_loop():
    while _running:
        with _lock:
            now = time.monotonic()
            noise = 0.0

            diff = _state["angle_target"] - _state["angle"]
            _state["angle"] = round(_state["angle"] + diff * 0.1 + noise, 2)

            sdiff = _state["speed_target"] - _state["speed_kmh"]
            _state["speed_kmh"] = round(max(0.0, _state["speed_kmh"] + sdiff * 0.06), 1)

            _update_signal_state(now)
        time.sleep(0.05)

# ── event detection (identical to carStateHelper.py) ─────────────────────────

def detect_event():
    with _lock:
        return _detect_event_nolock()

def _detect_event_nolock():
    speed      = _state["speed_kmh"]
    angle      = _state["angle"]
    gear       = _map_gear(_state["gear_raw"])
    signal_dir = _state["signals"]["direction"]
    hazard     = _state["signals"]["hazard"]
    abs_angle  = abs(angle)
    STRAIGHT, TURN, SHARP, MOVING = 3, 10, 25, 1

    if speed <= MOVING:
        if gear == "R":
            return "reversing_and_turning" if abs_angle >= TURN else "reversing"
        return "stopped_wheel_turned" if abs_angle >= TURN else "stopped"

    if hazard == "on":
        if abs_angle >= SHARP: return "moving_with_hazard_sharp_turn"
        if abs_angle >= TURN:  return "moving_with_hazard_turning"
        return "moving_with_hazard"

    if angle <= -SHARP:
        if signal_dir == "left":  return "sharp_left_turn_with_signal"
        if signal_dir == "right": return "sharp_left_turn_wrong_signal"
        return "sharp_left_turn_no_signal"

    if angle >= SHARP:
        if signal_dir == "right": return "sharp_right_turn_with_signal"
        if signal_dir == "left":  return "sharp_right_turn_wrong_signal"
        return "sharp_right_turn_no_signal"

    if angle <= -TURN:
        if signal_dir == "left":  return "left_turn_with_signal"
        if signal_dir == "right": return "left_turn_wrong_signal"
        return "left_turn_no_signal"

    if angle >= TURN:
        if signal_dir == "right": return "right_turn_with_signal"
        if signal_dir == "left":  return "right_turn_wrong_signal"
        return "right_turn_no_signal"

    if signal_dir == "left":  return "left_signal_on_straight"
    if signal_dir == "right": return "right_signal_on_straight"
    if abs_angle <= STRAIGHT: return "stable_drive"
    return "minor_steering_adjustment"

# ── public API (identical signatures to carStateHelper.py) ────────────────────

def start(clear_log=False):
    start_sim()

def stop():
    global _running
    _running = False

def get_angle():
    with _lock:
        return _state["angle"]

def get_speed():
    with _lock:
        return _state["speed_kmh"]

def get_gear():
    with _lock:
        return _map_gear(_state["gear_raw"])

def get_doors():
    with _lock:
        return dict(_state["doors"])

def get_signals():
    with _lock:
        return {
            "left":      _state["signals"]["left"],
            "right":     _state["signals"]["right"],
            "direction": _state["signals"]["direction"],
            "hazard":    _state["signals"]["hazard"],
        }

def get_hvac():
    with _lock:
        return dict(_state["hvac"])

def get_power():
    with _lock:
        return dict(_state["power"])

def get_event():
    return detect_event()

def get_state():
    with _lock:
        return {
            "angle":     _state["angle"],
            "speed_kmh": _state["speed_kmh"],
            "gear":      _map_gear(_state["gear_raw"]),
            "doors":     dict(_state["doors"]),
            "signals": {
                "left":      _state["signals"]["left"],
                "right":     _state["signals"]["right"],
                "direction": _state["signals"]["direction"],
                "hazard":    _state["signals"]["hazard"],
            },
            "hvac":  dict(_state["hvac"]),
            "power": dict(_state["power"]),
            "event": _detect_event_nolock(),
        }

# ── GUI ───────────────────────────────────────────────────────────────────────

class MockGUI:
    def __init__(self, root):
        self.root = root
        root.title("Car State Mock")
        root.resizable(False, False)

        pad = {"padx": 10, "pady": 6}

        # ── Steering angle ────────────────────────────────────────────────────
        f_angle = tk.LabelFrame(root, text="Steering angle", padx=8, pady=6)
        f_angle.grid(row=0, column=0, columnspan=2, sticky="ew", **pad)

        self.angle_var = tk.DoubleVar(value=0.0)
        self.angle_label = tk.Label(f_angle, text="0.0°", font=("Courier", 22, "bold"), width=8)
        self.angle_label.grid(row=0, column=0, rowspan=2, padx=(0, 12))

        self.angle_slider = tk.Scale(
            f_angle, from_=-465, to=465, resolution=1,
            orient=tk.HORIZONTAL, length=340,
            variable=self.angle_var,
            command=self._on_angle,
            showvalue=False,
        )
        self.angle_slider.grid(row=0, column=1, sticky="ew")

        btn_frame = tk.Frame(f_angle)
        btn_frame.grid(row=1, column=1, sticky="w")
        for label, val in [("Full L", -465), ("-90", -90), ("Center", 0), ("+90", 90), ("Full R", 465)]:
            tk.Button(btn_frame, text=label, width=6,
                      command=lambda v=val: self._set_angle(v)).pack(side=tk.LEFT, padx=2)

        # ── Speed ─────────────────────────────────────────────────────────────
        f_speed = tk.LabelFrame(root, text="Speed", padx=8, pady=6)
        f_speed.grid(row=1, column=0, columnspan=2, sticky="ew", **pad)

        self.speed_var = tk.DoubleVar(value=0.0)
        self.speed_label = tk.Label(f_speed, text="0.0 km/h", font=("Courier", 14), width=10)
        self.speed_label.grid(row=0, column=0, rowspan=2, padx=(0, 12))

        self.speed_slider = tk.Scale(
            f_speed, from_=0, to=200, resolution=1,
            orient=tk.HORIZONTAL, length=340,
            variable=self.speed_var,
            command=self._on_speed,
            showvalue=False,
        )
        self.speed_slider.grid(row=0, column=1, sticky="ew")

        spd_btn = tk.Frame(f_speed)
        spd_btn.grid(row=1, column=1, sticky="w")
        for label, val in [("0", 0), ("30", 30), ("60", 60), ("100", 100), ("130", 130)]:
            tk.Button(spd_btn, text=label, width=5,
                      command=lambda v=val: self._set_speed(v)).pack(side=tk.LEFT, padx=2)

        # ── Gear ──────────────────────────────────────────────────────────────
        f_gear = tk.LabelFrame(root, text="Gear", padx=8, pady=6)
        f_gear.grid(row=2, column=0, sticky="nsew", **pad)

        self.gear_var = tk.StringVar(value="P")
        for g, raw in [("P", 0), ("D", 5), ("N", 6), ("R", 7), ("M", 8)]:
            tk.Radiobutton(
                f_gear, text=g, value=g, variable=self.gear_var,
                command=lambda r=raw: self._set_gear(r),
                font=("Courier", 13, "bold"), width=3,
            ).pack(side=tk.LEFT)

        # ── Engine / Power ────────────────────────────────────────────────────
        f_power = tk.LabelFrame(root, text="Engine", padx=8, pady=6)
        f_power.grid(row=2, column=1, sticky="nsew", **pad)

        self.engine_var = tk.StringVar(value="on")
        for label, raw in [("Off", 0), ("Starting", 1), ("On", 2)]:
            tk.Radiobutton(
                f_power, text=label, value=label.lower(),
                variable=self.engine_var,
                command=lambda r=raw: self._set_engine(r),
            ).pack(side=tk.LEFT, padx=4)

        # ── Signals ───────────────────────────────────────────────────────────
        f_sig = tk.LabelFrame(root, text="Turn signals", padx=8, pady=6)
        f_sig.grid(row=3, column=0, sticky="nsew", **pad)

        self.sig_left_var   = tk.BooleanVar()
        self.sig_right_var  = tk.BooleanVar()

        tk.Checkbutton(f_sig, text="◀ Left",  variable=self.sig_left_var,
                       command=self._on_signals).pack(side=tk.LEFT, padx=6)
        tk.Checkbutton(f_sig, text="Right ▶", variable=self.sig_right_var,
                       command=self._on_signals).pack(side=tk.LEFT, padx=6)
        tk.Button(f_sig, text="Off", command=self._signals_off).pack(side=tk.LEFT, padx=6)

        # ── Doors ─────────────────────────────────────────────────────────────
        f_doors = tk.LabelFrame(root, text="Doors", padx=8, pady=6)
        f_doors.grid(row=3, column=1, sticky="nsew", **pad)

        self.door_vars = {}
        for door in ["driver", "front_passenger", "rear_right", "rear_left", "trunk"]:
            v = tk.BooleanVar()
            self.door_vars[door] = v
            short = {"driver": "Driver", "front_passenger": "F.Pass",
                     "rear_right": "R.R", "rear_left": "R.L", "trunk": "Trunk"}[door]
            tk.Checkbutton(f_doors, text=short, variable=v,
                           command=lambda d=door, var=v: self._on_door(d, var)).pack(side=tk.LEFT, padx=4)

        # ── HVAC ──────────────────────────────────────────────────────────────
        f_hvac = tk.LabelFrame(root, text="HVAC", padx=8, pady=6)
        f_hvac.grid(row=4, column=0, columnspan=2, sticky="ew", **pad)

        tk.Label(f_hvac, text="Driver temp:").grid(row=0, column=0, sticky="e")
        self.dtemp_var = tk.DoubleVar(value=22.0)
        tk.Scale(f_hvac, from_=16, to=30, resolution=0.5, orient=tk.HORIZONTAL,
                 length=160, variable=self.dtemp_var,
                 command=self._on_dtemp).grid(row=0, column=1, sticky="w")
        self.dtemp_label = tk.Label(f_hvac, text="22.0°", width=6)
        self.dtemp_label.grid(row=0, column=2)

        tk.Label(f_hvac, text="Pass temp:").grid(row=0, column=3, sticky="e", padx=(16, 0))
        self.ptemp_var = tk.DoubleVar(value=22.0)
        tk.Scale(f_hvac, from_=16, to=30, resolution=0.5, orient=tk.HORIZONTAL,
                 length=160, variable=self.ptemp_var,
                 command=self._on_ptemp).grid(row=0, column=4, sticky="w")
        self.ptemp_label = tk.Label(f_hvac, text="22.0°", width=6)
        self.ptemp_label.grid(row=0, column=5)

        tk.Label(f_hvac, text="Blow speed:").grid(row=1, column=0, sticky="e")
        self.blow_var = tk.IntVar(value=3)
        tk.Scale(f_hvac, from_=0, to=7, resolution=1, orient=tk.HORIZONTAL,
                 length=160, variable=self.blow_var,
                 command=self._on_blow).grid(row=1, column=1, sticky="w")
        self.blow_label = tk.Label(f_hvac, text="3", width=6)
        self.blow_label.grid(row=1, column=2)

        tk.Label(f_hvac, text="Blow mode:").grid(row=1, column=3, sticky="e", padx=(16, 0))
        self.blow_mode_var = tk.StringVar(value="face")
        blow_modes = ["face", "face_and_feet", "feet", "defrost_and_feet"]
        ttk.Combobox(f_hvac, textvariable=self.blow_mode_var,
                     values=blow_modes, width=16, state="readonly",
                     ).grid(row=1, column=4, columnspan=2, sticky="w", padx=4)
        self.blow_mode_var.trace_add("write", self._on_blow_mode)

        # ── Live readout ──────────────────────────────────────────────────────
        f_out = tk.LabelFrame(root, text="Live state  (updates every 200 ms)", padx=8, pady=6)
        f_out.grid(row=5, column=0, columnspan=2, sticky="ew", **pad)

        self.readout = tk.Text(f_out, height=6, width=62,
                               font=("Courier", 10), state=tk.DISABLED,
                               bg="#1e1e1e", fg="#d4d4d4", relief=tk.FLAT)
        self.readout.pack(fill=tk.X)

        self.root.after(100, self._refresh_readout)

        # ── Reset camera ──────────────────────────────────────────────────────
        f_reset = tk.Frame(root)
        f_reset.grid(row=0, column=2, rowspan=2, padx=10, pady=6, sticky="n")
        tk.Button(f_reset, text="Reset Camera (ZL)", font=("Courier", 11),
                  width=20, bg="#2a2a2a", fg="white",
                  command=self._reset_camera).pack(pady=2)
        tk.Button(f_reset, text="A", font=("Courier", 11),
                  width=20, bg="#2a2a2a", fg="white",
                  command=self._press_a).pack(pady=2)
        tk.Button(f_reset, text="B", font=("Courier", 11),
                  width=20, bg="#2a2a2a", fg="white",
                  command=self._press_b).pack(pady=2)
        tk.Button(f_reset, text="PLUS", font=("Courier", 11),
                  width=20, bg="#2a2a2a", fg="white",
                  command=lambda: self._press_button("PLUS")).pack(pady=2)

    # ── control handlers ──────────────────────────────────────────────────────

    def _press_button(self, btn):
        try:
            import requests
            requests.post("http://localhost:5001/press",
                          json={"button": btn, "duration": 0.1}, timeout=1)
        except Exception as e:
            print(f"button error: {e}")

    def _reset_camera(self):
        try:
            import requests
            self._press_button("ZL")
        except Exception as e:
            print(f"reset error: {e}")

    def _press_a(self): self._press_button("A")
    def _press_b(self): self._press_button("B")

    def _on_angle(self, val):
        with _lock:
            _state["angle_target"] = float(val)
        self.angle_label.config(text=f"{float(val):+.0f}°")

    def _set_angle(self, val):
        self.angle_var.set(val)
        self._on_angle(val)

    def _on_speed(self, val):
        with _lock:
            _state["speed_target"] = float(val)
        self.speed_label.config(text=f"{float(val):.0f} km/h")

    def _set_speed(self, val):
        self.speed_var.set(val)
        self._on_speed(val)

    def _set_gear(self, raw):
        with _lock:
            _state["gear_raw"] = raw

    def _set_engine(self, raw):
        with _lock:
            _state["power"]["engine_raw"] = raw
            _state["power"]["engine"]     = _map_engine(raw)
            mode_raw = 2 if raw > 0 else 0
            _state["power"]["mode_raw"]   = mode_raw
            _state["power"]["mode"]       = _map_power_mode(mode_raw)

    def _on_signals(self):
        now = time.monotonic()
        with _lock:
            l = self.sig_left_var.get()
            r = self.sig_right_var.get()
            _state["signals"]["left"]  = "on" if l else "off"
            _state["signals"]["right"] = "on" if r else "off"
            if l: _state["signals"]["last_left_on"]  = now
            if r: _state["signals"]["last_right_on"] = now
            _update_signal_state(now)

    def _signals_off(self):
        self.sig_left_var.set(False)
        self.sig_right_var.set(False)
        with _lock:
            _state["signals"]["left"]      = "off"
            _state["signals"]["right"]     = "off"
            _state["signals"]["direction"] = "none"
            _state["signals"]["hazard"]    = "off"

    def _on_door(self, door, var):
        with _lock:
            _state["doors"][door] = "open" if var.get() else "closed"

    def _on_dtemp(self, val):
        with _lock:
            _state["hvac"]["driver_temp"] = float(val)
        self.dtemp_label.config(text=f"{float(val):.1f}°")

    def _on_ptemp(self, val):
        with _lock:
            _state["hvac"]["passenger_temp"] = float(val)
        self.ptemp_label.config(text=f"{float(val):.1f}°")

    def _on_blow(self, val):
        with _lock:
            _state["hvac"]["blow_speed"] = int(float(val))
        self.blow_label.config(text=str(int(float(val))))

    def _on_blow_mode(self, *_):
        mode_map = {"face": 0, "face_and_feet": 1, "feet": 2, "defrost_and_feet": 3}
        raw = mode_map.get(self.blow_mode_var.get(), 0)
        with _lock:
            _state["hvac"]["blow_mode_raw"] = raw
            _state["hvac"]["blow_mode"]     = self.blow_mode_var.get()

    # ── live readout ──────────────────────────────────────────────────────────

    def _refresh_readout(self):
        s = get_state()
        sig = s["signals"]
        lines = (
            f"  angle    {s['angle']:>8.1f}°    speed  {s['speed_kmh']:>6.1f} km/h    gear  {s['gear']}\n"
            f"  engine   {s['power']['engine']:<10}  power  {s['power']['mode']}\n"
            f"  signal   {sig['direction']:<10}  hazard {sig['hazard']}\n"
            f"  hvac     driver {s['hvac']['driver_temp']}°  pass {s['hvac']['passenger_temp']}°  "
            f"blow {s['hvac']['blow_speed']} / {s['hvac']['blow_mode']}\n"
            f"  doors    { {k: v for k, v in s['doors'].items() if v == 'open'} or 'all closed' }\n"
            f"  event    {s['event']}"
        )
        self.readout.config(state=tk.NORMAL)
        self.readout.delete("1.0", tk.END)
        self.readout.insert(tk.END, lines)
        self.readout.config(state=tk.DISABLED)

        # keep angle label in sync with simulated noise
        with _lock:
            actual = _state["angle"]
        self.angle_label.config(text=f"{actual:+.1f}°")

        self.root.after(200, self._refresh_readout)

# ── entry point ───────────────────────────────────────────────────────────────

def start_sim():
    global _running
    if _running:
        return
    _running = True
    threading.Thread(target=_sim_loop, daemon=True).start()

def run_gui():
    root = tk.Tk()
    MockGUI(root)
    root.protocol("WM_DELETE_WINDOW", lambda: (stop(), root.destroy()))
    start_sim()
    root.mainloop()

if __name__ == "__main__":
    run_gui()
