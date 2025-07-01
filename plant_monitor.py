import tkinter as tk
from tkinter import ttk
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
            f"plant_{i}": {
                "dry_threshold": 1.5,
                "wet_threshold": 2.5,
                "update_interval": 2,
                "name": f"Plant {i+1}",
                "image_path": ""
            } for i in range(self.num_plants)
        }
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
                for i in range(self.num_plants):
                    plant_key = f"plant_{i}"
                    if plant_key not in self.config:
                        self.config[plant_key] = default_config[plant_key]
            else:
                self.config = default_config
                self.save_config()
            logging.info("Config loaded successfully")
        except Exception as e:
            self.config = default_config
            self.save_config()
            logging.error(f"Config load failed, using default: {e}")

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

        canvas = tk.Canvas(self.root, bg='#2E8B57')
        scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#2E8B57')
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        scrollbar.pack(side="right", fill="y")
        scrollbar.config(width=30)  # Larger scrollbar for touch

        # Enable finger scrolling
        def scroll_canvas(event):
            if event.num == 5 or event.delta < 0:  # Scroll down
                canvas.yview_scroll(1, "units")
            elif event.num == 4 or event.delta > 0:  # Scroll up
                canvas.yview_scroll(-1, "units")

        def drag_scroll(event):
            canvas.yview_scroll(int(-event.delta_y / 30), "units")

        canvas.bind_all("<Button-4>", scroll_canvas)
        canvas.bind_all("<Button-5>", scroll_canvas)
        canvas.bind("<B1-Motion>", lambda e: canvas.yview_scroll(int(-e.delta_y / 30), "units"))

        self.plant_widgets = []
        columns = 3
        for i in range(self.num_plants):
            row = i // columns
            col = i % columns
            plant_frame = tk.Frame(scrollable_frame, bg='white', relief='raised', bd=2, width=260, height=300)
            plant_frame.grid(row=row, column=col, padx=5, pady=5, sticky='nsew')
            plant_frame.grid_propagate(False)
            self.setup_plant_tile(plant_frame, i)

    def setup_plant_tile(self, parent, plant_id):
        plant_widgets = {}
        plant_widgets['frame'] = parent

        name_frame = tk.Frame(parent, bg='white')
        name_frame.pack(pady=5, fill='x', padx=5)
        plant_widgets['name_var'] = tk.StringVar(value=self.config[f'plant_{plant_id}']['name'])
        name_entry = tk.Entry(name_frame, textvariable=plant_widgets['name_var'], font=('Arial', 14), width=15)
        name_entry.pack(side='left', padx=5)
        name_entry.bind('<FocusIn>', lambda e: name_entry.select_range(0, tk.END))
        name_entry.bind('<FocusOut>', lambda e, pid=plant_id: self.update_plant_name(pid))

        plant_widgets['alert_label'] = tk.Label(name_frame, text="!", font=('Arial', 14, 'bold'), fg='red', bg='white')
        plant_widgets['alert_label'].pack(side='right', padx=5)
        plant_widgets['alert_label'].pack_forget()

        main_frame = tk.Frame(parent, bg='white')
        main_frame.pack(fill='both', expand=True)

        controls_frame = tk.Frame(main_frame, bg='white')
        controls_frame.pack(fill='x', padx=5)

        plant_widgets['image_label'] = tk.Label(controls_frame, text="[Plant Image]", bg='white',
                                              font=('Arial', 10), width=15, height=5, relief='sunken')
        plant_widgets['image_label'].pack(pady=5)

        plant_widgets['status_label'] = tk.Label(controls_frame, text="CHECKING...", font=('Arial', 12, 'bold'), bg='white', fg='orange')
        plant_widgets['status_label'].pack(pady=5)

        plant_widgets['voltage_label'] = tk.Label(controls_frame, text="Voltage: --", font=('Arial', 10), bg='white')
        plant_widgets['voltage_label'].pack()

        plant_widgets['moisture_progress'] = ttk.Progressbar(controls_frame, length=150, mode='determinate')
        plant_widgets['moisture_progress'].pack(pady=5)

        button_frame = tk.Frame(main_frame, bg='white')
        button_frame.pack(side='right', padx=5, pady=5)
        tk.Button(button_frame, text="Set Thresholds", command=lambda: self.manual_thresholds(plant_id),
                 bg='#4CAF50', fg='white', font=('Arial', 10, 'bold'), width=12, height=2).pack()

        self.plant_widgets.append(plant_widgets)

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
        if voltage < dry_threshold:
            return "DRY - WATER NEEDED!", "red", 20, True
        elif voltage > wet_threshold:
            return "TOO WET", "blue", 100, False
        else:
            return "PERFECT", "green", 60, False

    def monitor_moisture(self):
        while self.monitoring:
            try:
                if self.hardware_ready:
                    for i in range(self.num_plants):
                        if i < len(self.channels):
                            raw_value = self.channels[i].value
                            voltage = self.channels[i].voltage
                            status_text, status_color, progress_value, show_alert = self.get_moisture_status(voltage, i)
                            self.root.after(0, self.update_gui, i, raw_value, voltage,
                                          status_text, status_color, progress_value, show_alert)
                else:
                    self.root.after(0, self.update_gui_error)
                time.sleep(self.config['plant_0']['update_interval'])
            except Exception as e:
                logging.error(f"Monitoring error: {e}")
                self.root.after(0, self.update_gui_error)
                time.sleep(5)

    def update_gui(self, plant_id, raw_value, voltage, status_text, status_color, progress_value, show_alert):
        try:
            widgets = self.plant_widgets[plant_id]
            widgets['voltage_label'].config(text=f"Voltage: {voltage:.2f} V")
            widgets['status_label'].config(text=status_text, fg=status_color)
            widgets['moisture_progress']['value'] = progress_value
            if show_alert:
                widgets['alert_label'].pack(side='right', padx=5)
            else:
                widgets['alert_label'].pack_forget()
        except Exception as e:
            logging.error(f"GUI update failed for plant_{plant_id}: {e}")

    def update_gui_error(self):
        try:
            for widgets in self.plant_widgets:
                widgets['voltage_label'].config(text="Voltage: ERROR")
                widgets['status_label'].config(text="SENSOR ERROR", fg="red")
                widgets['moisture_progress']['value'] = 0
                widgets['alert_label'].pack_forget()
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
