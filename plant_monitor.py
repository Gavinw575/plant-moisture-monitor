#!/usr/bin/env python3
"""
Plant Moisture Monitor GUI Application for Raspberry Pi
Monitors multiple soil moisture sensors using MCP3008 ADC
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
    def __init__(self, root, num_plants=3):
        self.root = root
        self.root.title("Multi-Plant Moisture Monitor")
        self.root.geometry("1200x1000")
        self.root.configure(bg='#2E8B57')  # Sea green background
        self.num_plants = num_plants

        # Configuration file for storing thresholds
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
        """Initialize the MCP3008 ADC and moisture sensors"""
        try:
            # Create the SPI bus
            spi = busio.SPI(clock=board.SCK, MISO=board.MISO, MOSI=board.MOSI)
            # Create the chip select
            cs = digitalio.DigitalInOut(board.D5)
            # Create the MCP object
            self.mcp = MCP.MCP3008(spi, cs)
            # Create analog input channels for multiple plants
            self.channels = [AnalogIn(self.mcp, getattr(MCP, f'P{i}')) for i in range(self.num_plants)]
            self.hardware_ready = True
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
                "name": f"Plant {i+1}"
            } for i in range(self.num_plants)
        }

        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
                # Ensure config has entries for all plants
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
        """Create the main GUI interface with tabs for each plant"""
        # Main title
        title_frame = tk.Frame(self.root, bg='#2E8B57')
        title_frame.pack(pady=20)
        title_label = tk.Label(title_frame, text="Multi-Plant Moisture Monitor",
                             font=('Arial', 24, 'bold'), fg='white', bg='#2E8B57')
        title_label.pack()

        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(pady=10, padx=20, fill='both', expand=True)

        self.plant_frames = []
        self.plant_widgets = []

        for i in range(self.num_plants):
            plant_frame = tk.Frame(self.notebook, bg='white')
            self.notebook.add(plant_frame, text=self.config[f'plant_{i}']['name'])
            self.plant_frames.append(plant_frame)
            self.setup_plant_gui(plant_frame, i)

        # Hardware status
        self.hardware_status = tk.Label(self.root,
                                      text="Hardware: Ready" if self.hardware_ready else "Hardware: Error",
                                      font=('Arial', 10),
                                      fg='green' if self.hardware_ready else 'red',
                                      bg='#2E8B57')
        self.hardware_status.pack(side='bottom', pady=5)

    def setup_plant_gui(self, parent, plant_id):
        """Create GUI for a single plant"""
        plant_widgets = {}

        # Status display frame
        status_frame = tk.Frame(parent, bg='white', relief='raised', bd=2)
        status_frame.pack(pady=20, padx=20, fill='x')

        # Current readings
        plant_widgets['voltage_label'] = tk.Label(status_frame, text="Voltage: --",
                                               font=('Arial', 16), bg='white')
        plant_widgets['voltage_label'].pack(pady=10)

        plant_widgets['raw_label'] = tk.Label(status_frame, text="Raw ADC: --",
                                           font=('Arial', 12), bg='white', fg='gray')
        plant_widgets['raw_label'].pack()

        # Moisture status
        plant_widgets['status_label'] = tk.Label(status_frame, text="CHECKING...",
                                              font=('Arial', 20, 'bold'),
                                              bg='white', fg='orange')
        plant_widgets['status_label'].pack(pady=15)

        # Visual moisture indicator
        plant_widgets['moisture_progress'] = ttk.Progressbar(status_frame, length=300, mode='determinate')
        plant_widgets['moisture_progress'].pack(pady=5)

        scale_frame = tk.Frame(status_frame, bg='white')
        scale_frame.pack()
        tk.Label(scale_frame, text="Dry", font=('Arial', 8),
                fg='red', bg='white').pack(side='left')
        tk.Label(scale_frame, text="Perfect", font=('Arial', 8),
                fg='green', bg='white').pack(side='right')

        # Last updated time
        plant_widgets['time_label'] = tk.Label(status_frame, text="Last updated: --",
                                            font=('Arial', 10), bg='white', fg='gray')
        plant_widgets['time_label'].pack(pady=5)

        # Control panel
        control_frame = tk.LabelFrame(parent, text="Settings",
                                   font=('Arial', 12, 'bold'),
                                   bg='#90EE90', fg='#2E8B57')
        control_frame.pack(pady=20, padx=20, fill='x')

        # Plant name
        tk.Label(control_frame, text="Plant Name:",
                bg='#90EE90').grid(row=0, column=0, sticky='w', padx=5, pady=5)
        plant_widgets['name_var'] = tk.StringVar(value=self.config[f'plant_{plant_id}']['name'])
        name_entry = tk.Entry(control_frame, textvariable=plant_widgets['name_var'])
        name_entry.grid(row=0, column=1, padx=5, pady=5)
        name_entry.bind('<FocusOut>', lambda e, pid=plant_id: self.update_plant_name(pid))

        # Threshold settings
        tk.Label(control_frame, text="Dry Threshold (V):",
                bg='#90EE90').grid(row=1, column=0, sticky='w', padx=5, pady=5)
        plant_widgets['dry_threshold_var'] = tk.DoubleVar(value=self.config[f'plant_{plant_id}']['dry_threshold'])
        dry_spinbox = tk.Spinbox(control_frame, from_=0.0, to=3.3, increment=0.1,
                               textvariable=plant_widgets['dry_threshold_var'], width=10,
                               command=lambda: self.update_thresholds(plant_id))
        dry_spinbox.grid(row=1, column=1, padx=5, pady=5)

        tk.Label(control_frame, text="Wet Threshold (V):",
                bg='#90EE90').grid(row=2, column=0, sticky='w', padx=5, pady=5)
        plant_widgets['wet_threshold_var'] = tk.DoubleVar(value=self.config[f'plant_{plant_id}']['wet_threshold'])
        wet_spinbox = tk.Spinbox(control_frame, from_=0.0, to=3.3, increment=0.1,
                               textvariable=plant_widgets['wet_threshold_var'], width=10,
                               command=lambda: self.update_thresholds(plant_id))
        wet_spinbox.grid(row=2, column=1, padx=5, pady=5)

        # Calibration button
        calibrate_btn = tk.Button(control_frame, text="Calibrate Sensor",
                                command=lambda: self.calibrate_sensor(plant_id),
                                bg='#4CAF50', fg='white', font=('Arial', 10, 'bold'))
        calibrate_btn.grid(row=3, column=0, columnspan=2, pady=10)

        self.plant_widgets.append(plant_widgets)

    def update_plant_name(self, plant_id):
        """Update plant name in config and tab"""
        self.config[f'plant_{plant_id}']['name'] = self.plant_widgets[plant_id]['name_var'].get()
        self.notebook.tab(plant_id, text=self.config[f'plant_{plant_id}']['name'])
        self.save_config()

    def update_thresholds(self, plant_id):
        """Update threshold values for a specific plant"""
        self.config[f'plant_{plant_id}']['dry_threshold'] = self.plant_widgets[plant_id]['dry_threshold_var'].get()
        self.config[f'plant_{plant_id}']['wet_threshold'] = self.plant_widgets[plant_id]['wet_threshold_var'].get()
        self.save_config()

    def calibrate_sensor(self, plant_id):
        """Open calibration dialog for a specific plant"""
        cal_window = tk.Toplevel(self.root)
        cal_window.title(f"Calibrate {self.config[f'plant_{plant_id}']['name']}")
        cal_window.geometry("400x300")
        cal_window.configure(bg='white')

        tk.Label(cal_window, text=f"Calibrating {self.config[f'plant_{plant_id}']['name']}",
                font=('Arial', 16, 'bold'), bg='white').pack(pady=10)

        instructions = """
1. Insert sensor in DRY soil and click 'Set Dry'
2. Insert sensor in WET soil and click 'Set Wet'
3. Click 'Apply' to save calibration
        """

        tk.Label(cal_window, text=instructions,
                font=('Arial', 10), bg='white', justify='left').pack(pady=10)

        current_reading = tk.Label(cal_window, text="Current: -- V",
                                 font=('Arial', 12), bg='white')
        current_reading.pack(pady=10)

        def update_reading():
            if self.hardware_ready and cal_window.winfo_exists():
                voltage = self.channels[plant_id].voltage
                current_reading.config(text=f"Current: {voltage:.2f} V")
                cal_window.after(1000, update_reading)

        def set_dry():
            if self.hardware_ready:
                self.plant_widgets[plant_id]['dry_threshold_var'].set(round(self.channels[plant_id].voltage, 2))

        def set_wet():
            if self.hardware_ready:
                self.plant_widgets[plant_id]['wet_threshold_var'].set(round(self.channels[plant_id].voltage, 2))

        def apply_calibration():
            self.update_thresholds(plant_id)
            cal_window.destroy()

        button_frame = tk.Frame(cal_window, bg='white')
        button_frame.pack(pady=20)

        tk.Button(button_frame, text="Set Dry", command=set_dry,
                 bg='red', fg='white').pack(side='left', padx=5)
        tk.Button(button_frame, text="Set Wet", command=set_wet,
                 bg='blue', fg='white').pack(side='left', padx=5)
        tk.Button(button_frame, text="Apply", command=apply_calibration,
                 bg='green', fg='white').pack(side10=5, padx=5, pady=5)

        update_reading()

    def get_moisture_status(self, voltage, plant_id):
        """Determine moisture status based on voltage reading for a specific plant"""
        dry_threshold = self.config[f'plant_{plant_id}']['dry_threshold']
        wet_threshold = self.config[f'plant_{plant_id}']['wet_threshold']

        if voltage < dry_threshold:
            return "DRY - WATER NEEDED!", "red", 20
        elif voltage > wet_threshold:
            return "TOO WET", "blue", 100
        else:
            return "PERFECT", "green", 60

    def monitor_moisture(self):
        """Main monitoring loop running in separate thread"""
        while self.monitoring:
            try:
                if self.hardware_ready:
                    for i in range(self.num_plants):
                        # Read sensor values
                        raw_value = self.channels[i].value
                        voltage = self.channels[i].voltage

                        # Get moisture status
                        status_text, status_color, progress_value = self.get_moisture_status(voltage, i)

                        # Update GUI (must be done in main thread)
                        self.root.after(0, self.update_gui, i, raw_value, voltage,
                                      status_text, status_color, progress_value)
                else:
                    # Hardware not ready
                    self.root.after(0, self.update_gui_error)

                time.sleep(self.config['plant_0']['update_interval'])

            except Exception as e:
                print(f"Monitoring error: {e}")
                self.root.after(0, self.update_gui_error)
                time.sleep(5)

    def update_gui(self, plant_id, raw_value, voltage, status_text, status_color, progress_value):
        """Update GUI elements with new readings for a specific plant"""
        widgets = self.plant_widgets[plant_id]
        widgets['voltage_label'].config(text=f"Voltage: {voltage:.2f} V")
        widgets['raw_label'].config(text=f"Raw ADC: {raw_value}")
        widgets['status_label'].config(text=status_text, fg=status_color)
        widgets['moisture_progress']['value'] = progress_value
        widgets['time_label'].config(text=f"Last updated: {datetime.now().strftime('%H:%M:%S')}")

    def update_gui_error(self):
        """Update GUI when there's a hardware error"""
        for widgets in self.plant_widgets:
            widgets['voltage_label'].config(text="Voltage: ERROR")
            widgets['raw_label'].config(text="Raw ADC: ERROR")
            widgets['status_label'].config(text="SENSOR ERROR", fg="red")
            widgets['time_label'].config(text="Check sensor connection")

    def on_closing(self):
        """Handle application closing"""
        self.monitoring = False
        self.save_config()
        self.root.destroy()


def main():
    """Main application entry point"""
    root = tk.Tk()
    app = PlantMoistureApp(root, num_plants=3)  # Configure number of plants here
    root.mainloop()


if __name__ == "__main__":
    main()
