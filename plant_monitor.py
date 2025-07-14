import tkinter as tk
from tkinter import ttk
import json
import socket
import threading
import time
import random
import logging
import os

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/chicken/plant_monitor.log'),
        logging.StreamHandler()
    ]
)

class PlantMoistureApp:
    def __init__(self, root, num_plants=40, plants_config_file='/home/chicken/plants_config.json', 
                 moisture_config_file='/home/chicken/moisture_config.json'):
        self.root = root
        self.root.title("Plant Moisture Monitor")
        self.num_plants = num_plants
        self.plants_config_file = plants_config_file
        self.moisture_config_file = moisture_config_file
        self.monitoring = False
        self.hardware_ready = True  # Set to False to simulate data
        self.server_socket = None
        self.channels = [None] * self.num_plants
        self.plant_widgets = {}
        self.plants_config = {}
        self.moisture_config = {}
        
        # Load configurations
        self.load_configs()
        
        # Initialize GUI
        self.create_widgets()
        
        # Start server and monitoring
        self.start_server()
        self.start_monitoring()

    def load_configs(self):
        """Load plants_config.json and moisture_config.json, create defaults if invalid/empty."""
        # Default plants config
        default_plants_config = {
            f"plant_{i}": {"name": f"Plant {i}", "update_interval": 2, "dry_threshold": 1.0}
            for i in range(self.num_plants)
        }
        
        # Default moisture config
        default_moisture_config = {
            "last_dry_check": "",
            "server_port": 5000
        }
        
        # Load plants_config.json
        if not os.path.exists(self.plants_config_file) or os.path.getsize(self.plants_config_file) == 0:
            logging.warning(f"Plants config file {self.plants_config_file} is missing or empty, creating default")
            self.plants_config = default_plants_config
            self.save_plants_config()
        else:
            try:
                with open(self.plants_config_file, 'r') as f:
                    self.plants_config = json.load(f)
                logging.info("Plants config loaded successfully")
                # Ensure all plants are in config
                for i in range(self.num_plants):
                    key = f"plant_{i}"
                    if key not in self.plants_config:
                        logging.warning(f"Missing config for plant_{i}, adding default")
                        self.plants_config[key] = default_plants_config[key]
                self.save_plants_config()
            except Exception as e:
                logging.error(f"Plants config load failed, using default: {e}")
                self.plants_config = default_plants_config
                self.save_plants_config()

        # Load moisture_config.json
        if not os.path.exists(self.moisture_config_file) or os.path.getsize(self.moisture_config_file) == 0:
            logging.warning(f"Moisture config file {self.moisture_config_file} is missing or empty, creating default")
            self.moisture_config = default_moisture_config
            self.save_moisture_config()
        else:
            try:
                with open(self.moisture_config_file, 'r') as f:
                    self.moisture_config = json.load(f)
                logging.info("Moisture config loaded successfully")
            except Exception as e:
                logging.error(f"Moisture config load failed, using default: {e}")
                self.moisture_config = default_moisture_config
                self.save_moisture_config()

    def save_plants_config(self):
        """Save plants configuration to plants_config.json."""
        try:
            with open(self.plants_config_file, 'w') as f:
                json.dump(self.plants_config, f, indent=4)
            logging.info("Plants config saved successfully")
        except Exception as e:
            logging.error(f"Plants config save failed: {e}")

    def save_moisture_config(self):
        """Save moisture configuration to moisture_config.json."""
        try:
            with open(self.moisture_config_file, 'w') as f:
                json.dump(self.moisture_config, f, indent=4)
            logging.info("Moisture config saved successfully")
        except Exception as e:
            logging.error(f"Moisture config save failed: {e}")

    def create_widgets(self):
        """Create GUI widgets for each plant."""
        self.plant_widgets = {}
        for i in range(self.num_plants):
            self.plant_widgets[i] = {}
            # Main frame for the plant
            frame = tk.Frame(self.root, width=200, height=150, borderwidth=2, relief="groove")
            name_frame = tk.Frame(frame)
            main_frame = tk.Frame(frame)
            controls_frame = tk.Frame(frame)
            button_row_frame = tk.Frame(controls_frame)
            
            # Widgets
            name_label = tk.Label(name_frame, text=self.plants_config[f"plant_{i}"]["name"])
            voltage_label = tk.Label(main_frame, text="Voltage: 0.00V")
            status_label = tk.Label(main_frame, text="Status: Unknown")
            moisture_progress = ttk.Progressbar(main_frame, length=100, maximum=100)
            alert_label = tk.Label(main_frame, text="")
            
            # Store widgets
            self.plant_widgets[i] = {
                'frame': frame,
                'name_frame': name_frame,
                'main_frame': main_frame,
                'controls_frame': controls_frame,
                'button_row_frame': button_row_frame,
                'name_label': name_label,
                'voltage_label': voltage_label,
                'status_label': status_label,
                'moisture_progress': moisture_progress,
                'alert_label': alert_label
            }
            
            # Layout widgets
            frame.grid(row=i//2, column=i%2, padx=5, pady=5, sticky="nsew")
            name_frame.grid(row=0, column=0, sticky="ew")
            main_frame.grid(row=1, column=0, sticky="ew")
            controls_frame.grid(row=2, column=0, sticky="ew")
            button_row_frame.grid(row=0, column=0, sticky="ew")
            name_label.grid(row=0, column=0, sticky="w")
            voltage_label.grid(row=0, column=0, sticky="w")
            status_label.grid(row=1, column=0, sticky="w")
            moisture_progress.grid(row=2, column=0, sticky="ew")
            alert_label.grid(row=3, column=0, sticky="w")
        
        # Configure grid weights
        for i in range((self.num_plants + 1) // 2):
            self.root.grid_rowconfigure(i, weight=1)
        for i in range(2):
            self.root.grid_columnconfigure(i, weight=1)

    def update_gui(self, plant_id, raw_value, voltage, status_text, status_color, progress_value, show_alert):
        """Update GUI for a specific plant."""
        try:
            widgets = self.plant_widgets[plant_id]
            required_keys = ['frame', 'name_frame', 'main_frame', 'controls_frame', 
                           'button_row_frame', 'name_label', 'voltage_label', 
                           'status_label', 'moisture_progress', 'alert_label']
            for key in required_keys:
                if key not in widgets:
                    logging.error(f"Missing widget key '{key}' for plant_{plant_id}")
                    return
            widgets['voltage_label'].config(text=f"Voltage: {voltage:.2f}V")
            widgets['status_label'].config(text=f"Status: {status_text}", fg=status_color)
            widgets['moisture_progress'].config(value=progress_value)
            widgets['alert_label'].config(text="ALERT: Dry soil!" if show_alert else "")
            logging.debug(f"Updated GUI for plant_{plant_id}: raw={raw_value}, voltage={voltage:.2f}V, status={status_text}")
        except Exception as e:
            logging.error(f"GUI update failed for plant_{plant_id}: {e}")

    def get_moisture_status(self, voltage, plant_id):
        """Determine moisture status based on voltage."""
        threshold = self.plants_config[f"plant_{plant_id}"]["dry_threshold"]
        if voltage < threshold:
            return "Dry", "red", (voltage / 3.3) * 100, True
        elif voltage < 1.5:
            return "Low", "orange", (voltage / 3.3) * 100, False
        else:
            return "Good", "green", (voltage / 3.3) * 100, False

    def start_server(self):
        """Start TCP server to receive data from ESP32."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            port = self.moisture_config.get("server_port", 5000)
            self.server_socket.bind(('0.0.0.0', port))
            self.server_socket.listen(1)
            logging.info(f"Server started on port {port}")
            threading.Thread(target=self.receive_data, daemon=True).start()
        except Exception as e:
            logging.error(f"Server start failed: {e}")
            self.hardware_ready = False

    def receive_data(self):
        """Receive data from ESP32."""
        while self.monitoring:
            try:
                self.server_socket.settimeout(2.0)
                conn, addr = self.server_socket.accept()
                data = conn.recv(2048).decode().strip()
                conn.close()
                if data:
                    logging.info(f"Received data: {data}")
                    sensor_data = json.loads(data)
                    for i in range(self.num_plants):
                        key = f"plant_{i}"
                        if key in sensor_data:
                            voltage = sensor_data[key]
                            if not isinstance(voltage, (int, float)):
                                logging.error(f"Invalid voltage type for plant_{i}: {voltage}")
                                continue
                            if 0.0 <= voltage <= 3.3:
                                raw_value = int(voltage * 1023 / 3.3)
                                self.channels[i] = type('obj', (), {'value': raw_value, 'voltage': voltage})
                                logging.debug(f"Updated plant_{i}: raw={raw_value}, voltage={voltage:.2f}V")
                            else:
                                logging.error(f"Invalid voltage for plant_{i}: {voltage}")
            except socket.timeout:
                logging.debug("Socket timeout, continuing...")
                continue
            except json.JSONDecodeError as e:
                logging.error(f"JSON decode error: {e}, data: {data}")
                continue
            except Exception as e:
                if self.monitoring:
                    logging.error(f"Server receive failed: {e}")
                time.sleep(1)

    def monitor_moisture(self):
        """Monitor moisture levels and update GUI."""
        current_dry_plants = set()
        while self.monitoring:
            try:
                for i in range(self.num_plants):
                    if self.hardware_ready and self.channels[i]:
                        raw_value = self.channels[i].value
                        voltage = self.channels[i].voltage
                        logging.debug(f"Plant_{i}: raw={raw_value}, voltage={voltage:.2f}V")
                    else:
                        raw_value = 0
                        voltage = random.uniform(0.0, 3.3)
                        logging.debug(f"Plant_{i}: simulated voltage={voltage:.2f}V (hardware_ready={self.hardware_ready}, channels[{i}]={'set' if self.channels[i] else 'None'})")
                    status_text, status_color, progress_value, show_alert = self.get_moisture_status(voltage, i)
                    self.root.after(0, self.update_gui, i, raw_value, voltage, status_text, status_color, progress_value, show_alert)
                    if show_alert:
                        current_dry_plants.add(i)
                    else:
                        current_dry_plants.discard(i)
                if current_dry_plants:
                    logging.warning(f"Dry plants detected: {current_dry_plants}")
                    self.moisture_config["last_dry_check"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                    self.save_moisture_config()
                time.sleep(self.plants_config[f"plant_{i}"]["update_interval"])
            except Exception as e:
                logging.error(f"Monitoring error: {e}")
                time.sleep(5)

    def start_monitoring(self):
        """Start the monitoring thread."""
        self.monitoring = True
        threading.Thread(target=self.monitor_moisture, daemon=True).start()
        logging.info("Monitoring started")

    def stop_monitoring(self):
        """Stop monitoring and clean up."""
        self.monitoring = False
        if self.server_socket:
            self.server_socket.close()
        self.save_plants_config()
        self.save_moisture_config()
        logging.info("Application closed")

    def on_closing(self):
        """Handle window closing."""
        self.stop_monitoring()
        self.root.destroy()

if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = PlantMoistureApp(root)
        root.protocol("WM_DELETE_WINDOW", app.on_closing)
        root.mainloop()
    except Exception as e:
        logging.error(f"Initialization failed: {e}")
        raise
