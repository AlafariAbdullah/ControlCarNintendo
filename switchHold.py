import nxbt
import threading
import time
from flask import Flask, request, jsonify

app = Flask(__name__)
nx    = None
index = None

_state = {
    "left_x":   0, "left_y":   0,
    "right_x":  0, "right_y":  0,
    "buttons":  set(),
}
_lock = threading.Lock()

def setup():
    global nx, index
    nx    = nxbt.Nxbt()
    index = nx.create_controller(
        nxbt.PRO_CONTROLLER,
        adapter_path=nx.get_available_adapters()[0],
        reconnect_address=nx.get_switch_addresses()
    )
    print("Waiting for Switch...")
    nx.wait_for_connection(index)
    print("Connected!")

def input_loop():
    while True:
        with _lock:
            lx = _state["left_x"]
            ly = _state["left_y"]
            rx = _state["right_x"]
            ry = _state["right_y"]
            btns = set(_state["buttons"])
        pkt = nx.create_input_packet()
        pkt["L_STICK"]["X_VALUE"] = lx
        pkt["L_STICK"]["Y_VALUE"] = ly
        pkt["R_STICK"]["X_VALUE"] = rx
        pkt["R_STICK"]["Y_VALUE"] = ry
        for btn in btns:
            if btn in pkt:
                pkt[btn] = True
        nx.set_controller_input(index, pkt)
        time.sleep(1/120)

def hold_button(btn, duration):
    with _lock:
        _state["buttons"].add(btn)
    time.sleep(duration)
    with _lock:
        _state["buttons"].discard(btn)

@app.route("/stick", methods=["POST"])
def set_stick():
    data = request.json
    side = data.get("stick", "").lower()
    x    = int(data.get("x", 0))
    y    = int(data.get("y", 0))
    with _lock:
        if "left" in side:
            _state["left_x"]  = x
            _state["left_y"]  = y
        elif "right" in side:
            _state["right_x"] = x
            _state["right_y"] = y
    return jsonify({"ok": True})

@app.route("/press", methods=["POST"])
def press():
    data = request.json
    btn  = data.get("button", "").upper()
    dur  = float(data.get("duration", 0.1))
    threading.Thread(target=hold_button, args=(btn, dur), daemon=True).start()
    return jsonify({"ok": True})

@app.route("/status")
def status():
    return jsonify({"status": nx.state[index]["state"] if nx else "not ready"})

if __name__ == "__main__":
    setup()
    threading.Thread(target=input_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=5001, debug=False, use_reloader=False)
