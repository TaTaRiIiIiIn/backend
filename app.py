from flask import Flask, jsonify, request
from flask_socketio import SocketIO
import requests
import time
import threading
from flask_cors import CORS

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")
CORS(app)
CORS(app, origins=["http://localhost:8081", "http://localhost:3000"])


REAL_DATA_URL = 'https://pilot.incomtek.kg/api/api.php?cmd=list'

username = "tehnocenter"
password = "128565"
latest_truck_data = []
fuel_logs = []
@app.route('/api/truck-list', methods=['GET'])
def get_truck_list():
    raw_data = fetch_real_truck_data()  # This uses your real data source
    truck_numbers = sorted({
        truck.get("vehiclenumber", "Unknown")
        for truck in raw_data
        if truck.get("vehiclenumber")
    })
    return jsonify(truck_numbers)

@app.route('/api/fuel-log', methods=['POST'])
def log_fuel():
    data = request.get_json()
    required_keys = {'vehiclenumber', 'fuel_used', 'start_timestamp', 'end_timestamp'}
    if not required_keys.issubset(data.keys()):
        return jsonify({"error": "Missing one or more required fields"}), 400
    
    fuel_logs.append(data)
    return jsonify({"message": "Fuel log saved"}), 200


@app.route('/api/fuel-log', methods=['GET'])
def get_fuel_logs():
    return jsonify(fuel_logs)

def fetch_real_truck_data():
    try:
        response = requests.get(REAL_DATA_URL,  auth=(username, password), timeout=5)
        response.raise_for_status()
        data = response.json()
        if data.get("code") == 0 and "list" in data:
            return data["list"]
        else:
            return []
    except Exception as e:
        print(f"Error fetching real truck data: {e}")
        return []

def process_truck_data(raw_list):
    processed = []
    for truck in raw_list:
        ignition = next((s['hum_value'] for s in truck.get('sensors_status', []) if s['name'] == 'зажигание'), "Unknown")
        power = next((s['hum_value'] for s in truck.get('sensors_status', []) if s['name'] == 'Внешнее питание'), "Unknown")
        
        try:
            timestamp = int(truck["status"]["unixtimestamp"])
            formatted_time = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(timestamp))
        except (ValueError, TypeError):
            formatted_time = "Invalid Timestamp"

        processed.append({
            "vehiclenumber": truck.get("vehiclenumber", "Unknown"),
            "last_update": formatted_time,
            "speed": truck["status"]["speed"],
            "ignition": "On" if ignition == "вкл" else "Off",
            "power": power,
            "lat": truck["status"]["lat"],
            "lon": truck["status"]["lon"],
        })
    return processed

def background_fetch():
    global latest_truck_data
    while True:
        raw_data = fetch_real_truck_data()
        processed_data = process_truck_data(raw_data)
        if processed_data != latest_truck_data:
            latest_truck_data = processed_data
            socketio.emit('truck_update', latest_truck_data)
        time.sleep(10)  # Fetch every 10 seconds

@app.route('/')
def index():
    return "Fleet WebSocket server running."

if __name__ == '__main__':
    # Start background thread
    thread = threading.Thread(target=background_fetch)
    thread.daemon = True
    thread.start()
    
    socketio.run(app, debug=True)
