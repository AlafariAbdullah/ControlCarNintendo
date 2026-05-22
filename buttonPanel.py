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
root.title("Switch Buttons")
root.resizable(False, False)

for btn in ["ZL", "A", "B", "PLUS"]:
    tk.Button(root, text=btn, font=("Courier", 13),
              width=20, bg="#2a2a2a", fg="white",
              command=lambda b=btn: press(b)).pack(pady=4, padx=16)

root.mainloop()
