#!/usr/bin/env python3
"""
Plant Moisture Monitor GUI Application for Raspberry Pi
Monitors soil moisture using MCP3008 ADC and moisture sensor
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
    def __init__(self, root):
        self.root = root
        self.root.title("Blehhhhhh")
        self.root.geometry("1200x1000")
        self.root.configure(bg='#2E8B57')  # Sea green background

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
        """Initialize the MCP3008 ADC and moisture sensor"""
        try:
            # Create the SPI bus
            spi = busio.SPI(clock=board.SCK, MISO=board.MISO, MOSI=board.MOSI)
            # Create the chip select
            cs = digitalio.DigitalInOut(board.D5)
            # Create the MCP object
            self.mcp = MCP.MCP3008(spi, cs)
            # Create analog input channel on pin 0
            self.chan = AnalogIn(self.mcp, MCP.P0)
            self.hardware_ready = True
        except Exception as e:
            self.hardware_ready = False
            print(f"Hardware initialization failed: {e}")

    def load_config(self):
        """Load configuration from file or use defaults"""
        default_config = {
            "dry_threshold": 1.5,  # Voltage below this = dry
            "wet_threshold": 2.5,  # Voltage above this = wet
            "update_interval": 2  # Seconds between readings
        }

        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
            else:
                self.config = default_config
                self.save_config()
        except:
            self.config = default_config

    def save_config(self):
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"Could not save config: {e}")

    def setup_gui(self):
        """Create the main GUI interface"""
        # Main title
        title_frame = tk.Frame(self.root, bg='#2E8B57')
        title_frame.pack(pady=20)

        title_label = tk.Label(title_frame, text="Plant Moisture Monitor",
                               font=('Arial', 24, 'bold'),
                               fg='white', bg='#2E8B57')
        title_label.pack()

        # Status display frame
        status_frame = tk.Frame(self.root, bg='white', relief='raised', bd=2)
        status_frame.pack(pady=20, padx=20, fill='x')

        # Current readings
        self.voltage_label = tk.Label(status_frame, text="Voltage: --",
                                      font=('Arial', 16), bg='white')
        self.voltage_label.pack(pady=10)

        self.raw_label = tk.Label(status_frame, text="Raw ADC: --",
                                  font=('Arial', 12), bg='white', fg='gray')
        self.raw_label.pack()

        # Moisture status with large indicator
        self.status_label = tk.Label(status_frame, text="CHECKING...",
                                     font=('Arial', 20, 'bold'),
                                     bg='white', fg='orange')
        self.status_label.pack(pady=15)

        # Visual moisture indicator
        self.create_moisture_indicator(status_frame)

        # Last updated time
        self.time_label = tk.Label(status_frame, text="Last updated: --",
                                   font=('Arial', 10), bg='white', fg='gray')
        self.time_label.pack(pady=5)

        # Control panel
        control_frame = tk.LabelFrame(self.root, text="Settings",
                                      font=('Arial', 12, 'bold'),
                                      bg='#90EE90', fg='#2E8B57')
        control_frame.pack(pady=20, padx=20, fill='x')

        # Threshold settings
        tk.Label(control_frame, text="Dry Threshold (V):",
                 bg='#90EE90').grid(row=0, column=0, sticky='w', padx=5, pady=5)

        self.dry_threshold_var = tk.DoubleVar(value=self.config['dry_threshold'])
        dry_spinbox = tk.Spinbox(control_frame, from_=0.0, to=3.3, increment=0.1,
                                 textvariable=self.dry_threshold_var, width=10,
                                 command=self.update_thresholds)
        dry_spinbox.grid(row=0, column=1, padx=5, pady=5)

        tk.Label(control_frame, text="Wet Threshold (V):",
                 bg='#90EE90').grid(row=1, column=0, sticky='w', padx=5, pady=5)

        self.wet_threshold_var = tk.DoubleVar(value=self.config['wet_threshold'])
        wet_spinbox = tk.Spinbox(control_frame, from_=0.0, to=3.3, increment=0.1,
                                 textvariable=self.wet_threshold_var, width=10,
                                 command=self.update_thresholds)
        wet_spinbox.grid(row=1, column=1, padx=5, pady=5)

        # Calibration button
        calibrate_btn = tk.Button(control_frame, text="Calibrate Sensor",
                                  command=self.calibrate_sensor,
                                  bg='#4CAF50', fg='white', font=('Arial', 10, 'bold'))
        calibrate_btn.grid(row=2, column=0, columnspan=2, pady=10)

        # Hardware status
        self.hardware_status = tk.Label(self.root,
                                        text="Hardware: Ready" if self.hardware_ready else "Hardware: Error",
                                        font=('Arial', 10),
                                        fg='green' if self.hardware_ready else 'red',
                                        bg='#2E8B57')
        self.hardware_status.pack(side='bottom', pady=5)

    def create_moisture_indicator(self, parent):
        """Create a visual moisture level indicator"""
        indicator_frame = tk.Frame(parent, bg='white')
        indicator_frame.pack(pady=10)

        tk.Label(indicator_frame, text="Moisture Level:",
                 font=('Arial', 12), bg='white').pack()

        # Progress bar style indicator
        self.moisture_progress = ttk.Progressbar(indicator_frame, length=300, mode='determinate')
        self.moisture_progress.pack(pady=5)

        # Scale labels
        scale_frame = tk.Frame(indicator_frame, bg='white')
        scale_frame.pack()

        tk.Label(scale_frame, text="Dry", font=('Arial', 8),
                 fg='red', bg='white').pack(side='left')
        tk.Label(scale_frame, text="Perfect", font=('Arial', 8),
                 fg='green', bg='white').pack(side='right')

    def update_thresholds(self):
        """Update threshold values from GUI"""
        self.config['dry_threshold'] = self.dry_threshold_var.get()
        self.config['wet_threshold'] = self.wet_threshold_var.get()
        self.save_config()

    def calibrate_sensor(self):
        """Open calibration dialog"""
        cal_window = tk.Toplevel(self.root)
        cal_window.title("Sensor Calibration")
        cal_window.geometry("400x300")
        cal_window.configure(bg='white')

        tk.Label(cal_window, text="Sensor Calibration",
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
            if self.hardware_ready:
                voltage = self.chan.voltage
                current_reading.config(text=f"Current: {voltage:.2f} V")
            cal_window.after(1000, update_reading)

        def set_dry():
            if self.hardware_ready:
                self.dry_threshold_var.set(round(self.chan.voltage, 2))

        def set_wet():
            if self.hardware_ready:
                self.wet_threshold_var.set(round(self.chan.voltage, 2))

        def apply_calibration():
            self.update_thresholds()
            cal_window.destroy()

        button_frame = tk.Frame(cal_window, bg='white')
        button_frame.pack(pady=20)

        tk.Button(button_frame, text="Set Dry", command=set_dry,
                  bg='red', fg='white').pack(side='left', padx=5)
        tk.Button(button_frame, text="Set Wet", command=set_wet,
                  bg='blue', fg='white').pack(side='left', padx=5)
        tk.Button(button_frame, text="Apply", command=apply_calibration,
                  bg='green', fg='white').pack(side='left', padx=5)

        update_reading()

    def get_moisture_status(self, voltage):
        """Determine moisture status based on voltage reading"""
        dry_threshold = self.config['dry_threshold']
        wet_threshold = self.config['wet_threshold']

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
                    # Read sensor values
                    raw_value = self.chan.value
                    voltage = self.chan.voltage

                    # Get moisture status
                    status_text, status_color, progress_value = self.get_moisture_status(voltage)

                    # Update GUI (must be done in main thread)
                    self.root.after(0, self.update_gui, raw_value, voltage,
                                    status_text, status_color, progress_value)
                else:
                    # Hardware not ready
                    self.root.after(0, self.update_gui_error)

                time.sleep(self.config['update_interval'])

            except Exception as e:
                print(f"Monitoring error: {e}")
                self.root.after(0, self.update_gui_error)
                time.sleep(5)

    def update_gui(self, raw_value, voltage, status_text, status_color, progress_value):
        """Update GUI elements with new readings"""
        self.voltage_label.config(text=f"Voltage: {voltage:.2f} V")
        self.raw_label.config(text=f"Raw ADC: {raw_value}")
        self.status_label.config(text=status_text, fg=status_color)
        self.moisture_progress['value'] = progress_value
        self.time_label.config(text=f"Last updated: {datetime.now().strftime('%H:%M:%S')}")

    def update_gui_error(self):
        """Update GUI when there's a hardware error"""
        self.voltage_label.config(text="Voltage: ERROR")
        self.raw_label.config(text="Raw ADC: ERROR")
        self.status_label.config(text="SENSOR ERROR", fg="red")
        self.time_label.config(text="Check sensor connection")

    def on_closing(self):
        """Handle application closing"""
        self.monitoring = False
        self.save_config()
        self.root.destroy()


def main():
    """Main application entry point"""
    root = tk.Tk()
    app = PlantMoistureApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
