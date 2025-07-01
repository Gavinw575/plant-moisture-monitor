import tkinter as tk
from tkinter import ttk, filedialog
from PIL import Image, ImageTk
import board
import busio
import digitalio
import adafruit_mcp3xxx.mcp3008 as MCP
from adafruit_mcp3xxx.analog_in import AnalogIn
import threading
import time
import json
import os
import logging
import random  # For simulated voltages
from datetime import datetime, timedelta
print("DEBUG: PlantMoistureApp methods:", dir(self))
self.load_config()

# Setup logging
logging.basicConfig(filename='/home/chicken/plant_monitor.log', level=logging.DEBUG)

class PlantMoistureApp:
    def __init__(self, root, num_plants=40):
        try:
            self.root = root
            self.root.title("Plant Moisture Monitor")
            self.root.geometry("800x480")
            self.root.configure(bg='#2E8B57')
            self.num_plants = num_plants
            self.channels_per_mcp = 8
            self.num_mcp = (self.num_plants + self.channels_per_mcp - 1) // self.channels_per_mcp

            self.config_file = "/home/chicken/moisture_config.json"
            self.load_config()
            self.setup_hardware()
            self.setup_gui()
            self.monitoring = True
            self.monitor_thread = threading.Thread(target=self.monitor_moisture, daemon=True)
            self.monitor_thread.start()
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
            logging.info("Application initialized successfully")
        except Exception as e:
            logging.error(f"Initialization failed: {e}")
            raise

    def setup_hardware(self):
        try:
            self.mcps = []
            self.channels = []
            cs_pins = [board.D5, board.D6, board.D13, board.D19, board.D26]
            spi = busio.SPI(clock=board.SCK, MISO=board.MISO, MOSI=board.MOSI)
            for i in range(min(self.num_mcp, len(cs_pins))):
                cs = digitalio.DigitalInOut(cs_pins[i])
                mcp = MCP.MCP3008(spi, cs)
                self.mcps.append(mcp)
                for j in range(min(self.channels_per_mcp, self.num_plants - i * self.channels_per_mcp)):
                    channel = AnalogIn(mcp, getattr(MCP, f'P{j}'))
                    self.channels.append(channel)
            self.hardware_ready = True
            logging.info("Hardware initialized successfully")
        except Exception as e:
            self.hardware_ready = False
            logging.error(f"Hardware setup failed: {e}")

def load_config(self):
    default_config = {
        "last_dry_check": ""
    }

    for i in range(self.num_plants):
        default_config[f"plant_{i}"] = {
            "dry_threshold": 1.5,
            "wet_threshold": 2.5,
            "update_interval": 2,
            "name": f"Plant {i+1}",
            "image_path": ""
        }
        try:
            logging.debug(f"Loading config from {self.config_file}")
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
                logging.debug(f"Config loaded: {list(self.config.keys())}")
                for i in range(self.num_plants):
                    plant_key = f"plant_{i}"
                    if plant_key not in self.config:
                        logging.info(f"Missing config for {plant_key}, using default")
                        self.config[plant_key] = default_config[plant_key]
                if "last_dry_check" not in self.config:
                    logging.info("Missing last_dry_check, using default")
                    self.config["last_dry_check"] = default_config["last_dry_check"]
            else:
                logging.info("Config file not found, using default")
                self.config = default_config
                self.save_config()
            logging.info("Config loaded successfully")
        except Exception as e:
            logging.error(f"Config load failed, using default: {e}")
            self.config = default_config
            self.save_config()

    def save_config(self):
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            logging.info("Config saved successfully")
        except Exception as e:
            logging.error(f"Config save failed: {e}")

    def setup_gui(self):
        title_frame = tk.Frame(self.root, bg='#2E8B57')
        title_frame.pack(pady=5, fill='x')
        tk.Label(title_frame, text="Plant Moisture Monitor", font=('Arial', 20, 'bold'), fg='white', bg='#2E8B57').pack()

        style = ttk.Style()
        style.configure("TScrollbar", width=20, arrowsize=20)

        main_frame = tk.Frame(self.root, bg='#2E8B57')
        main_frame.pack(fill='both', expand=True, padx=5, pady=5)

        canvas = tk.Canvas(main_frame, bg='#2E8B57', width=600)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview, style="TScrollbar")
        scrollable_frame = tk.Frame(canvas, bg='#2E8B57')
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=(0, 0, 600, 300 * (self.num_plants // 3 + 1))))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="left", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        def scroll_canvas(event):
            if event.num == 5 or event.delta < 0:
                canvas.yview_scroll(1, "units")
            elif event.num == 4 or event.delta > 0:
                canvas.yview_scroll(-1, "units")

        def drag_scroll(event):
            canvas.yview_scroll(int(-event.delta_y / 30), "units")

        canvas.bind_all("<Button-4>", scroll_canvas)
        canvas.bind_all("<Button-5>", scroll_canvas)
        canvas.bind("<B1-Motion>", lambda e: canvas.yview_scroll(int(-e.delta_y / 30), "units"))

        dry_frame = tk.Frame(main_frame, bg='#2E8B57', width=180)
        dry_frame.pack(side="right", fill="y", padx=5)
        dry_frame.pack_propagate(False)
        tk.Label(dry_frame, text="Dry Plants", font=('Arial', 14, 'bold'), fg='white', bg='#2E8B57').pack(pady=5)
        self.dry_listbox = tk.Listbox(dry_frame, font=('Arial', 12), width=15, height=15, bg='white')
        self.dry_listbox.pack(fill="y", expand=True)

        self.plant_widgets = []
        columns = 3
        for i in range(self.num_plants):
            row = i // columns
            col = i % columns
            plant_frame = tk.Frame(scrollable_frame, bg='white', relief='raised', bd=2, width=190, height=300)
            plant_frame.grid(row=row, column=col, padx=5, pady=5, sticky='nsew')
            plant_frame.grid_propagate(False)
            self.setup_plant_tile(plant_frame, i)

    def setup_plant_tile(self, parent, plant_id):
        plant_widgets = {}
        plant_widgets['frame'] = parent

        name_frame = tk.Frame(parent, bg='white', width=180, height=30)
        name_frame.pack(pady=5, fill='x', padx=5)
        name_frame.pack_propagate(False)
        plant_widgets['name_frame'] = name_frame
        plant_widgets['name_var'] = tk.StringVar(value=self.config[f'plant_{plant_id}']['name'])
        name_entry = tk.Entry(name_frame, textvariable=plant_widgets['name_var'], font=('Arial', 12), width=12)
        name_entry.pack(side='left', padx=5)
        name_entry.bind('<FocusIn>', lambda e: name_entry.select_range(0, tk.END))
        name_entry.bind('<FocusOut>', lambda e, pid=plant_id: self.update_plant_name(pid))

        plant_widgets['alert_label'] = tk.Label(name_frame, text="", font=('Arial', 12, 'bold'), fg='red', bg='white', width=2)
        plant_widgets['alert_label'].pack(side='right', padx=5)

        main_frame = tk.Frame(parent, bg='white', width=180, height=250)
        main_frame.pack(fill='both', expand=True, padx=5)
        main_frame.pack_propagate(False)
        plant_widgets['main_frame'] = main_frame

        controls_frame = tk.Frame(main_frame, bg='white', width=120, height=190)
        controls_frame.pack(fill='x', padx=5)
        controls_frame.pack_propagate(False)
        plant_widgets['controls_frame'] = controls_frame

        image_path = self.config[f'plant_{plant_id}']['image_path']
        if image_path and os.path.exists(image_path):
            try:
                # To change image size, modify (60, 60) to desired size, e.g., (80, 80) or (50, 50)
                img = Image.open(image_path).resize((60, 60))
                plant_widgets['image'] = ImageTk.PhotoImage(img)
                plant_widgets['image_label'] = tk.Label(controls_frame, image=plant_widgets['image'], bg='white')
            except Exception as e:
                logging.error(f"Image load failed for plant_{plant_id}: {e}")
                plant_widgets['image_label'] = tk.Label(controls_frame, text="[Plant Image]", bg='white',
                                                      font=('Arial', 8), width=12, height=3, relief='sunken')
        else:
            plant_widgets['image_label'] = tk.Label(controls_frame, text="[Plant Image]", bg='white',
                                                  font=('Arial', 8), width=12, height=3, relief='sunken')
        plant_widgets['image_label'].pack(pady=5)

        plant_widgets['status_label'] = tk.Label(controls_frame, text="CHECKING...", font=('Arial', 10, 'bold'), bg='white', fg='orange', width=14, height=1)
        plant_widgets['status_label'].pack(pady=5)

        plant_widgets['voltage_label'] = tk.Label(controls_frame, text="Voltage: --", font=('Arial', 8), bg='white', width=14, height=1)
        plant_widgets['voltage_label'].pack(pady=5)

        plant_widgets['moisture_progress'] = ttk.Progressbar(controls_frame, length=120, mode='determinate')
        plant_widgets['moisture_progress'].pack(pady=5)

        button_row_frame = tk.Frame(main_frame, bg='white', width=180, height=30)
        button_row_frame.pack(fill='x', padx=5, pady=10)
        button_row_frame.pack_propagate(False)
        plant_widgets['button_row_frame'] = button_row_frame

        tk.Button(button_row_frame, text="Thresholds", command=lambda: self.manual_thresholds(plant_id),
                 bg='#4CAF50', fg='white', font=('Arial', 7, 'bold'), width=10, height=1).pack(side='left', padx=2)
        tk.Button(button_row_frame, text="Details", command=lambda: self.show_plant_details(plant_id),
                 bg='#2196F3', fg='white', font=('Arial', 7, 'bold'), width=10, height=1).pack(side='left', padx=2)
        tk.Button(button_row_frame, text="Add Image", command=lambda: self.select_image(plant_id),
                 bg='#FF9800', fg='white', font=('Arial', 7, 'bold'), width=10, height=1).pack(side='left', padx=2)

        self.plant_widgets.append(plant_widgets)

    def select_image(self, plant_id):
        try:
            path = filedialog.askopenfilename(filetypes=[("Image files", "*.jpg *.png *.jpeg")])
            if path:
                self.config[f'plant_{plant_id}']['image_path'] = path
                self.save_config()
                # To change image size, modify (60, 60) to desired size, e.g., (80, 80) or (50, 50)
                img = Image.open(path).resize((60, 60))
                self.plant_widgets[plant_id]['image'] = ImageTk.PhotoImage(img)
                self.plant_widgets[plant_id]['image_label'].config(image=self.plant_widgets[plant_id]['image'])
                logging.info(f"Updated image for plant_{plant_id}: {path}")
        except Exception as e:
            logging.error(f"Image selection failed for plant_{plant_id}: {e}")

    def show_plant_details(self, plant_id):
        details_window = tk.Toplevel(self.root)
        details_window.title(self.config[f'plant_{plant_id}']['name'])
        details_window.geometry("400x400")
        details_window.configure(bg='white')
        details_window.grab_set()

        tk.Label(details_window, text=self.config[f'plant_{plant_id}']['name'], font=('Arial', 16, 'bold'), bg='white').pack(pady=10)
        tk.Label(details_window, text=f"Status: {self.plant_widgets[plant_id]['status_label']['text']}", font=('Arial', 12), bg='white').pack()
        tk.Label(details_window, text=f"Voltage: {self.plant_widgets[plant_id]['voltage_label']['text']}", font=('Arial', 12), bg='white').pack()
        tk.Label(details_window, text=f"Dry Threshold: {self.config[f'plant_{plant_id}']['dry_threshold']:.2f} V", font=('Arial', 12), bg='white').pack()
        tk.Label(details_window, text=f"Wet Threshold: {self.config[f'plant_{plant_id}']['wet_threshold']:.2f} V", font=('Arial', 12), bg='white').pack()
        image_path = self.config[f'plant_{plant_id}']['image_path']
        if image_path and os.path.exists(image_path):
            try:
                # To change image size, modify (120, 120) to desired size, e.g., (100, 100) or (150, 150)
                img = Image.open(image_path).resize((120, 120))
                photo = ImageTk.PhotoImage(img)
                tk.Label(details_window, image=photo, bg='white').pack(pady=5)
                details_window.image = photo
            except Exception as e:
                logging.error(f"Details image load failed for plant_{plant_id}: {e}")
        tk.Button(details_window, text="Edit Thresholds", command=lambda: self.manual_thresholds(plant_id),
                 bg='#4CAF50', fg='white', font=('Arial', 12, 'bold'), width=12, height=2).pack(pady=10)

    def update_plant_name(self, plant_id):
        name = self.plant_widgets[plant_id]['name_var'].get().strip()
        if name:
            self.config[f'plant_{plant_id}']['name'] = name
            self.save_config()
            logging.info(f"Updated name for plant_{plant_id} to {name}")

    def manual_thresholds(self, plant_id):
        manual_window = tk.Toplevel(self.root)
        manual_window.title(f"Set Thresholds {self.config[f'plant_{plant_id}']['name']}")
        manual_window.geometry("400x300")
        manual_window.configure(bg='white')
        manual_window.grab_set()

        tk.Label(manual_window, text=f"Set Thresholds for {self.config[f'plant_{plant_id}']['name']}",
                font=('Arial', 14, 'bold'), bg='white').pack(pady=10)

        plant_widgets = self.plant_widgets[plant_id]
        plant_widgets['dry_threshold_var'] = tk.DoubleVar(value=self.config[f'plant_{plant_id}']['dry_threshold'])
        plant_widgets['wet_threshold_var'] = tk.DoubleVar(value=self.config[f'plant_{plant_id}']['wet_threshold'])

        tk.Label(manual_window, text="Dry Threshold (V):", font=('Arial', 12), bg='white').pack(pady=5)
        dry_entry = tk.Entry(manual_window, textvariable=plant_widgets['dry_threshold_var'], font=('Arial', 12), width=10)
        dry_entry.pack(pady=5)
        dry_entry.bind('<FocusIn>', lambda e: dry_entry.select_range(0, tk.END))

        tk.Label(manual_window, text="Wet Threshold (V):", font=('Arial', 12), bg='white').pack(pady=5)
        wet_entry = tk.Entry(manual_window, textvariable=plant_widgets['wet_threshold_var'], font=('Arial', 12), width=10)
        wet_entry.pack(pady=5)
        wet_entry.bind('<FocusIn>', lambda e: wet_entry.select_range(0, tk.END))

        def save_manual():
            try:
                dry = plant_widgets['dry_threshold_var'].get()
                wet = plant_widgets['wet_threshold_var'].get()
                if 0.0 <= dry <= 3.3 and 0.0 <= wet <= 3.3 and dry < wet:
                    self.config[f'plant_{plant_id}']['dry_threshold'] = dry
                    self.config[f'plant_{plant_id}']['wet_threshold'] = wet
                    self.save_config()
                    logging.info(f"Updated thresholds for plant_{plant_id}: dry={dry}, wet={wet}")
                    manual_window.destroy()
                else:
                    tk.Label(manual_window, text="Invalid values (0.0-3.3, dry < wet)", fg='red', bg='white').pack()
            except Exception as e:
                tk.Label(manual_window, text="Enter valid numbers", fg='red', bg='white').pack()
                logging.error(f"Threshold save failed for plant_{plant_id}: {e}")

        tk.Button(manual_window, text="Save", command=save_manual,
                 bg='green', fg='white', font=('Arial', 12, 'bold'), width=10, height=2).pack(pady=15)

    def get_moisture_status(self, voltage, plant_id):
        dry_threshold = self.config[f'plant_{plant_id}']['dry_threshold']
        wet_threshold = self.config[f'plant_{plant_id}']['wet_threshold']
        max_voltage = 3.3

        # Calculate progress bar value (0-100) based on voltage
        if voltage < dry_threshold:
            status_text = "DRY - WATER NEEDED!"
            status_color = "#FF9999"
            # Map 0 to dry_threshold -> 0 to 20
            progress_value = (voltage / dry_threshold) * 20 if dry_threshold > 0 else 0
            show_alert = True
        elif voltage > wet_threshold:
            status_text = "TOO WET"
            status_color = "#99CCFF"
            # Map wet_threshold to 3.3V -> 80 to 100
            progress_value = 80 + ((voltage - wet_threshold) / (max_voltage - wet_threshold)) * 20 if max_voltage > wet_threshold else 100
            show_alert = False
        else:
            status_text = "PERFECT"
            status_color = "#99FF99"
            # Map dry_threshold to wet_threshold -> 20 to 80
            progress_value = 20 + ((voltage - dry_threshold) / (wet_threshold - dry_threshold)) * 60 if wet_threshold > dry_threshold else 20
            show_alert = False

        # Clamp progress value to 0-100
        progress_value = max(0, min(100, progress_value))
        return status_text, status_color, progress_value, show_alert

    def monitor_moisture(self):
        # Track dry plants to avoid unnecessary listbox updates
        current_dry_plants = set()
        while self.monitoring:
            try:
                # Check if it's time for daily update for plants 2-40
                current_time = datetime.now()
                last_dry_check = self.config.get("last_dry_check", "")
                do_daily_check = False
                if not last_dry_check:
                    do_daily_check = True
                else:
                    try:
                        last_check_time = datetime.fromisoformat(last_dry_check)
                        if current_time.date() > last_check_time.date():
                            do_daily_check = True
                    except ValueError:
                        logging.error(f"Invalid last_dry_check format: {last_dry_check}")
                        do_daily_check = True

                if do_daily_check:
                    current_dry_plants.clear()
                    self.config["last_dry_check"] = current_time.isoformat()
                    self.save_config()
                    logging.info(f"Daily dryness check at {current_time}")

                # Always update plant 1 (index 0)
                if self.hardware_ready:
                    try:
                        raw_value = self.channels[0].value
                        voltage = self.channels[0].voltage
                        logging.debug(f"Plant_0: raw={raw_value}, voltage={voltage:.2f}V")
                    except Exception as e:
                        logging.error(f"Failed to read sensor for plant_0: {e}")
                        raw_value = 0
                        voltage = random.uniform(0.0, 3.3)  # Simulate for testing
                else:
                    logging.warning("Hardware not ready, simulating voltage for plant_0")
                    raw_value = 0
                    voltage = random.uniform(0.0, 3.3)
                status_text, status_color, progress_value, show_alert = self.get_moisture_status(voltage, 0)
                self.root.after(0, self.update_gui, 0, raw_value, voltage,
                               status_text, status_color, progress_value, show_alert)
                plant_name = self.config['plant_0']['name']
                if show_alert:
                    if plant_name not in current_dry_plants:
                        self.dry_listbox.insert(tk.END, plant_name)
                        current_dry_plants.add(plant_name)
                elif plant_name in current_dry_plants:
                    self.dry_listbox.delete(self.dry_listbox.get(0, tk.END).index(plant_name))
                    current_dry_plants.remove(plant_name)

                # Update plants 2-40 (indices 1-39) only for daily check
                if do_daily_check:
                    for i in range(1, self.num_plants):
                        if i < len(self.channels):
                            try:
                                raw_value = self.channels[i].value
                                voltage = self.channels[i].voltage
                                logging.debug(f"Plant_{i}: raw={raw_value}, voltage={voltage:.2f}V")
                            except Exception as e:
                                logging.error(f"Failed to read sensor for plant_{i}: {e}")
                                raw_value = 0
                                voltage = random.uniform(0.0, 3.3)  # Simulate for testing
                        else:
                            raw_value = 0
                            voltage = random.uniform(0.0, 3.3)  # Simulate for excess plants
                        status_text, status_color, progress_value, show_alert = self.get_moisture_status(voltage, i)
                        self.root.after(0, self.update_gui, i, raw_value, voltage,
                                       status_text, status_color, progress_value, show_alert)
                        plant_name = self.config[f'plant_{i}']['name']
                        if show_alert:
                            if plant_name not in current_dry_plants:
                                self.dry_listbox.insert(tk.END, plant_name)
                                current_dry_plants.add(plant_name)
                        elif plant_name in current_dry_plants:
                            self.dry_listbox.delete(self.dry_listbox.get(0, tk.END).index(plant_name))
                            current_dry_plants.remove(plant_name)

                time.sleep(self.config['plant_0']['update_interval'])
            except Exception as e:
                logging.error(f"Monitoring error: {e}")
                self.root.after(0, self.update_gui_error)
                time.sleep(5)

    def update_gui(self, plant_id, raw_value, voltage, status_text, status_color, progress_value, show_alert):
        try:
            widgets = self.plant_widgets[plant_id]
            required_keys = ['frame', 'name_frame', 'main_frame', 'controls_frame', 'button_row_frame',
                            'voltage_label', 'status_label', 'moisture_progress', 'alert_label']
            for key in required_keys:
                if key not in widgets:
                    logging.error(f"Missing widget key '{key}' for plant_{plant_id}")
                    return

            widgets['frame'].config(bg=status_color)
            widgets['name_frame'].config(bg=status_color)
            widgets['main_frame'].config(bg=status_color)
            widgets['controls_frame'].config(bg=status_color)
            widgets['button_row_frame'].config(bg=status_color)
            widgets['voltage_label'].config(text=f"Voltage: {voltage:.2f} V", bg=status_color)
            widgets['status_label'].config(text=status_text, fg='black', bg=status_color)
            widgets['moisture_progress']['value'] = progress_value
            widgets['alert_label'].config(text="!" if show_alert else "")
        except Exception as e:
            logging.error(f"GUI update failed for plant_{plant_id}: {e}")

    def update_gui_error(self):
        try:
            self.dry_listbox.delete(0, tk.END)
            for widgets in self.plant_widgets:
                required_keys = ['frame', 'name_frame', 'main_frame', 'controls_frame', 'button_row_frame',
                                'voltage_label', 'status_label', 'moisture_progress', 'alert_label']
                if not all(key in widgets for key in required_keys):
                    logging.error(f"Missing widget keys in update_gui_error: {list(widgets.keys())}")
                    continue
                widgets['frame'].config(bg='white')
                widgets['name_frame'].config(bg='white')
                widgets['main_frame'].config(bg='white')
                widgets['controls_frame'].config(bg='white')
                widgets['button_row_frame'].config(bg='white')
                widgets['voltage_label'].config(text="Voltage: ERROR", bg='white')
                widgets['status_label'].config(text="SENSOR ERROR", fg="red", bg='white')
                widgets['moisture_progress']['value'] = 0
                widgets['alert_label'].config(text="")
        except Exception as e:
            logging.error(f"GUI error update failed: {e}")

    def on_closing(self):
        self.monitoring = False
        self.save_config()
        self.root.destroy()
        logging.info("Application closed")

def main():
    try:
        root = tk.Tk()
        app = PlantMoistureApp(root, num_plants=40)
        root.mainloop()
    except Exception as e:
        logging.error(f"Main loop failed: {e}")

if __name__ == "__main__":
    main()
