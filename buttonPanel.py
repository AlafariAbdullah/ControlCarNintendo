import tkinter as tk
import requests

SWITCH_URL = "http://localhost:5001"

def press(btn):
    try:
        requests.post(f"{SWITCH_URL}/press",
                      json={"button": btn, "duration": 0.1}, timeout=1)
    except Exception as e:
        print(f"error: {e}")

root = tk.Tk()
root.title("Switch Controller")
root.resizable(False, False)
root.configure(bg="#1a1a1a")

def make_label(text):
    tk.Label(root, text=text, font=("Courier", 10, "bold"),
             bg="#1a1a1a", fg="#888888").pack(pady=(10, 2))

def make_row(buttons):
    frame = tk.Frame(root, bg="#1a1a1a")
    frame.pack(pady=2, padx=16)
    for btn, label in buttons:
        tk.Button(frame, text=label, font=("Courier", 12),
                  width=9, bg="#2a2a2a", fg="white", relief="flat",
                  command=lambda b=btn: press(b)).pack(side="left", padx=4)

# Face buttons
make_label("── Face ──")
make_row([("A", "A"), ("B", "B"), ("X", "X"), ("Y", "Y")])

# Triggers
make_label("── Triggers ──")
make_row([("L", "L"), ("R", "R")])
make_row([("ZL", "ZL"), ("ZR", "ZR")])

# D-Pad
make_label("── D-Pad ──")
make_row([("DPAD_UP", "▲")])
make_row([("DPAD_LEFT", "◄"), ("DPAD_DOWN", "▼"), ("DPAD_RIGHT", "►")])

# Stick clicks
make_label("── Sticks ──")
make_row([("L_STICK_PRESS", "L Click"), ("R_STICK_PRESS", "R Click")])

# System
make_label("── System ──")
make_row([("MINUS", "−"), ("PLUS", "+"), ("HOME", "⌂"), ("CAPTURE", "●")])

root.mainloop()
