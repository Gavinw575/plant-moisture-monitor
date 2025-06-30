#!/usr/bin/env python3
"""
Plant Moisture Monitor GUI Application for Raspberry Pi
Monitors multiple soil moisture sensors using multiple MCP3008 ADCs
Touch-friendly list layout with manual threshold entry
"""

import tkinter as tk
from tkinter import ttk
import board
import busio
import digitalio
import adafruit_mcp3xxx.mcp3008 as MCP
from adafruit_mcp3xxx.analog_in import AnalogIn
import threading
import time
from datetime import datetime
import json
import os


class PlantMoistureApp:
    def __init__(self, root, num_plants=40):
        self.root = root
        self.root.title("Plant Moisture Monitor")
        self.root.geometry("800x480")  # Optimized for touchscreen
        self.root.configure(bg='#2E8B57')  # Sea green background
        self.num_plants = num_plants
        self.channels_per_mcp = 8
        self.num_mcp = (self.num_plants + self.channels_per_mcp - 1) // self.channels_per_mcp

        # Configuration file
        self.config_file = "moisture_config.json"
        self.load_config()

        # Initialize hardware
        self.setup_hardware()

        # Create GUI
        self.setup_gui()

        # Start monitoring thread
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self.monitor_moisture, daemon=True)
        self.monitor_thread.start()

        # Handle window closing
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_hardware(self):
        """Initialize multiple MCP3008 ADCs and moisture sensors"""
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
            self.hardware_ready = True FormaTsunami: self.hardware_ready = True
        except Exception as e:
            self.hardware_ready = False
            print(f"Hardware initialization failed: {e}")

    def load_config(self):
        """Load configuration from file or use defaults"""
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
        except:
            self.config = default_config
            self.save_config()

    def save_config(self):
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"Could not save config: {e}")

    def setup_gui(self):
        """Create touch-friendly GUI with vertical list layout"""
        title_frame = tk.Frame(self.root, bg='#2E8B57')
        title_frame.pack(pady=5, fill='x')
        tk.Label(title_frame, text="Plant Moisture Monitor",
                 font=('Arial', 20, 'bold'), fg='white', bg='#2E8B57').pack()

        canvas = tk.Canvas(self.root, bg='#2E8B57')
        scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#2E8B57')

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        scrollbar.pack(side="right", fill="y")

        self.plant_widgets = []
        for i in range(self.num_plants):
            plant_frame = tk.Frame(scrollable_frame, bg='white', relief='raised', bd=2, width=750, height=120)
            plant_frame.grid(row=i, column=0, padx=5, pady=5, sticky='ew')
            plant_frame.grid_propagate(False)
            self.setup_plant_tile(plant_frame, i)

        self.hardware_status = tk.Label(self.root,
                                      text="Hardware: Ready" if self.hardware_ready else "Hardware: Error",
                                      font=('Arial', 10),
                                      fg='green' if self.hardware_ready else 'red',
                                      bg='#2E8B57')
        self.hardware_status.pack(side='bottom', pady=5)

    def setup_plant_tile(self, parent, plant_id):
        """Create touch-friendly plant tile"""
        plant_widgets = {}
        plant_widgets['frame'] = parent

        # Name and alert frame
        name_frame = tk.Frame(parent, bg='white')
        name_frame.pack(pady=5, fill='x', padx=5)
        plant_widgets['name_var'] = tk.StringVar(value=self.config[f'plant_{plant_id}']['name'])
        name_entry = tk.Entry(name_frame, textvariable=plant_widgets['name_var'], font=('Arial', 14), width=20)
        name_entry.pack(side='left', padx=5)
        name_entry.bind('<FocusIn>', lambda e: name_entry.select_range(0, tk.END))
        name_entry.bind('<FocusOut>', lambda e, pid=plant_id: self.update_plant_name(pid))

        plant_widgets['alert_label'] = tk.Label(name_frame, text="!",
                                              font=('Arial', 16, 'bold'), fg='red', bg='white')
        plant_widgets['alert_label'].pack(side='right', padx=5)
        plant_widgets['alert_label'].pack_forget()

        # Image placeholder
        plant_widgets['image_label'] = tk.Label(parent, text="[Plant Image]", bg='white',
                                             font=('Arial', 10), width=15, height=5, relief='sunken')
        plant_widgets['image_label'].pack(side='left', padx=5)

        # Status and controls frame
        controls_frame = tk.Frame(parent, bg='white')
        controls_frame.pack(side='left', fill='x', expand=True)

        # Moisture status
        plant_widgets['status_label'] = tk.Label(controls_frame, text="CHECKING...",
                                              font=('Arial', 14, 'bold'), bg='white', fg='orange')
        plant_widgets['status_label'].pack(pady=5)

        # Progress bar
        plant_widgets['moisture_progress'] = ttk.Progressbar(controls_frame, length=200, mode='determinate')
        plant_widgets['moisture_progress'].pack(pady=5)

        # Voltage
        plant_widgets['voltage_label'] = tk.Label(controls_frame, text="Voltage: --",
                                               font=('Arial', 12), bg='white')
        plant_widgets['voltage_label'].pack()

        # Manual threshold button
        tk.Button(controls_frame, text="Set Thresholds",
                 command=lambda: self.manual_thresholds(plant_id),
                 bg='#4CAF50', fg='white', font=('Arial', 12, 'bold'),
                 width=15, height=2).pack(pady=5)

        self.plant_widgets.append(plant_widgets)

    def update_plant_name(self, plant_id):
        """Update plant name in config"""
        name = self.plant_widgets[plant_id]['name_var'].get().strip()
        if name:
            self.config[f'plant_{plant_id}']['name'] = name
            self.save_config()

    def manual_thresholds(self, plant_id):
        """Open touch-friendly manual threshold entry dialog"""
        manual_window = tk.Toplevel(self.root)
        manual_window.title(f"Set Thresholds {self.config[f'plant_{plant_id}']['name']}")
        manual_window.geometry("400x300")
        manual_window.configure(bg='white')
        manual_window.attributes('-topmost', True)

        # Ensure window is focusable for touch
        manual_window.grab_set()

        tk.Label(manual_window, text=f"Set Thresholds for {self.config[f'plant_{plant_id}']['name']}",
                font=('Arial', 16, 'bold'), bg='white').pack(pady=10)

        plant_widgets = self.plant_widgets[plant_id]
        plant_widgets['dry_threshold_var'] = tk.DoubleVar(value=self.config[f'plant_{plant_id}']['dry_threshold'])
        plant_widgets['wet_threshold_var'] = tk.DoubleVar(value=self.config[f'plant_{plant_id}']['wet_threshold'])

        tk.Label(manual_window, text="Dry Threshold (V):", font=('Arial', 14), bg='white').pack(pady=5)
        dry_entry = tk.Entry(manual_window, textvariable=plant_widgets['dry_threshold_var'], font=('Arial', 14), width=10)
        dry_entry.pack(pady=5)
        dry_entry.bind('<FocusIn>', lambda e: dry_entry.select_range(0, tk.END))

        tk.Label(manual_window, text="Wet Threshold (V):", font=('Arial', 14), bg='white').pack(pady=5)
        wet_entry = tk.Entry(manual_window, textvariable=plant_widgets['wet_threshold_var'], font=('Arial', 14), width=10)
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
                    manual_window.destroy()
                else:
                    tk.Label(manual_window, text="Invalid values (0.0-3.3, dry < wet)", fg='red', bg='white').pack()
            except:
                tk.Label(manual_window, text="Enter valid numbers", fg='red', bg='white').pack()

        tk.Button(manual_window, text="Save",
                 command=save_manual,
                 bg='green', fg='white', font=('Arial', 14, 'bold'),
                 width=10, height=2).pack(pady=15)

    def get_moisture_status(self, voltage, plant_id):
        """Determine moisture status based on voltage reading"""
        dry_threshold = self.config[f'plant_{plant_id}']['dry_threshold']
        wet_threshold = self.config[f'plant_{plant_id}']['wet_threshold']

        if voltage < dry_threshold:
            return "DRY - WATER NEEDED!", "red", 20, True
        elif voltage > wet_threshold:
            return "TOO WET", "blue", 100, False
        else:
            return "PERFECT", "green", 60, False

    def monitor_moisture(self):
        """Main monitoring loop running in separate thread"""
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
                print(f"Monitoring error: {e}")
                self.root.after(0, self.update_gui_error)
                time.sleep(5)

    def update_gui(self, plant_id, raw_value, voltage, status_text, status_color, progress_value, show_alert):
        """Update GUI elements with new readings"""
        widgets = self.plant_widgets[plant_id]
        widgets['voltage_label'].config(text=f"Voltage: {voltage:.2f} V")
        widgets['status_label'].config(text=status_text, fg=status_color)
        widgets['moisture_progress']['value'] = progress_value
        if show_alert:
            widgets['alert_label'].pack(side='right', padx=5)
        else:
            widgets['alert_label'].pack_forget()

    def update_gui_error(self):
        """Update GUI when there's a hardware error"""
        for widgets in self.plant_widgets:
            widgets['voltage_label'].config(text="Voltage: ERROR")
            widgets['status_label'].config(text="SENSOR ERROR", fg="red")
            widgets['moisture_progress']['value'] = 0
            widgets['alert_label'].pack_forget()

    def on_closing(self):
        """Handle application closing"""
        self.monitoring = False
        self.save_config()
        self.root.destroy()


def main():
    """Main application entry point"""
    root = tk.Tk()
    app = PlantMoistureApp(root, num_plants=40)
    root.mainloop()


if __name__ == "__main__":
    main()
