import tkinter as tk
from tkinter import ttk, filedialog
from PIL import Image, ImageTk
import threading
import time
import json
import os
import logging
import random
import socket
from datetime import datetime, timedelta

# Setup logging
logging.basicConfig(filename='/home/chicken/plant_monitor.log', level=logging.DEBUG)

class PlantMoistureApp:
    def __init__(self, root, num_plants=40):
        try:
            self.root = root
            self.root.title("Plant Moisture Monitor")
            self.root.geometry("800x480")
            self.root.configure(bg='#2E8B57')
            if not isinstance(num_plants, int) or num_plants <= 0:
                raise ValueError(f"Invalid num_plants: {num_plants}")
            self.num_plants = num_plants
            self.config_file = "/home/chicken/moisture_config.json"
            self.monitoring = True  # Set this BEFORE setup_server()
            self.load_config()
            self.hardware_ready = True
            self.channels = [None] * num_plants
            self.plant_widgets = []  # Initialize this before setup_gui()
            self.setup_server()
            self.setup_gui()
            self.monitor_thread = threading.Thread(target=self.monitor_moisture, daemon=True)
            self.monitor_thread.start()
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
            logging.info("Application initialized successfully")
        except Exception as e:
            logging.error(f"Initialization failed: {e}")
            raise

    def setup_server(self):
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Allow socket reuse
            self.server_socket.bind(('0.0.0.0', 5000))
            self.server_socket.listen(1)
            self.server_thread = threading.Thread(target=self.receive_data, daemon=True)
            self.server_thread.start()
            logging.info("TCP server started on port 5000")
        except Exception as e:
            logging.error(f"Server setup failed: {e}")
            self.hardware_ready = False

    def receive_data(self):
        while self.monitoring:
            try:
                self.server_socket.settimeout(1.0)  # Add timeout to prevent blocking
                conn, addr = self.server_socket.accept()
                data = conn.recv(2048).decode().strip()
                conn.close()
                if data:
                    try:
                        sensor_data = json.loads(data)
                        for i in range(self.num_plants):
                            key = f"plant_{i}"
                            if key in sensor_data:
                                self.channels[i] = type('obj', (), {'value': int(sensor_data[key] * 1023 / 3.3), 'voltage': sensor_data[key]})
                    except json.JSONDecodeError as e:
                        logging.error(f"JSON decode failed: {e} | Raw data: {data}")
            except socket.timeout:
                continue  # Normal timeout, continue loop
            except Exception as e:
                if self.monitoring:  # Only log if we're still monitoring
                    logging.error(f"Server receive failed: {e}")
                time.sleep(1)  # Brief pause before retrying

    def load_config(self):
        default_config = {
            "last_dry_check": "",
            **{f"plant_{i}": {
                "dry_threshold": 1.5,
                "wet_threshold": 2.5,
                "update_interval": 2,
                "name": f"Plant {i+1}",
                "image_path": ""
            } for i in range(self.num_plants)}
        }
        try:
            logging.debug(f"Loading config from {self.config_file} with num_plants={self.num_plants}")
            if not os.access(self.config_file, os.R_OK):
                logging.warning(f"Config file {self.config_file} not readable, using default")
                self.config = default_config
                self.save_config()
                return
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
        except json.JSONDecodeError as e:
            logging.error(f"Config file corrupted: {e}")
            self.config = default_config
            self.save_config()
        except Exception as e:
            logging.error(f"Config load failed: {e}")
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
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="left", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        def scroll_canvas(event):
            if event.num == 5 or event.delta < 0:
                canvas.yview_scroll(1, "units")
            elif event.num == 4 or event.delta > 0:
                canvas.yview_scroll(-1, "units")

        canvas.bind_all("<Button-4>", scroll_canvas)
        canvas.bind_all("<Button-5>", scroll_canvas)
        canvas.bind_all("<MouseWheel>", scroll_canvas)  # Added for Windows compatibility

        dry_frame = tk.Frame(main_frame, bg='#2E8B57', width=180)
        dry_frame.pack(side="right", fill="y", padx=5)
        dry_frame.pack_propagate(False)
        tk.Label(dry_frame, text="Dry Plants", font=('Arial', 14, 'bold'), fg='white', bg='#2E8B57').pack(pady=5)
        self.dry_listbox = tk.Listbox(dry_frame, font=('Arial', 12), width=15, height=15, bg='white')
        self.dry_listbox.pack(fill="y", expand=True)

        columns = 3
        for i in range(self.num_plants):
            row = i // columns
            col = i % columns
            plant_frame = tk.Frame(scrollable_frame, bg='white', relief='raised', bd=2, width=190, height=300)
            plant_frame.grid(row=row, column=col, padx=5, pady=5, sticky='nsew')
            plant_frame.grid_propagate(False)
            self.setup_plant_tile(plant_frame, i)
        canvas.configure(scrollregion=(0, 0, 600, 350 * (self.num_plants // 3 + 1)))

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

        main_frame = tk.Frame(parent, bg='white', width=180, height=230)
        main_frame.pack(fill='both', expand=True, padx=5)
        main_frame.pack_propagate(False)
        plant_widgets['main_frame'] = main_frame

        controls_frame = tk.Frame(main_frame, bg='white', width=120, height=180)
        controls_frame.pack(fill='x', padx=5)
        controls_frame.pack_propagate(False)
        plant_widgets['controls_frame'] = controls_frame

        image_path = self.config[f'plant_{plant_id}']['image_path']
        plant_widgets['image'] = None  # Initialize the image key

        if image_path and os.path.exists(image_path):
            try:
                img = Image.open(image_path).resize((40, 40))
                plant_widgets['image'] = ImageTk.PhotoImage(img)
                plant_widgets['image_label'] = tk.Label(controls_frame, image=plant_widgets['image'], bg='white')
            except Exception as e:
                logging.error(f"Image load failed for plant_{plant_id}: {e}")
                plant_widgets['image_label'] = tk.Label(controls_frame, text="[Plant Image]", bg='white',
                                                      font=('Arial', 7), width=12, height=3, relief='sunken')
        else:
            plant_widgets['image_label'] = tk.Label(controls_frame, text="[Plant Image]", bg='white',
                                                  font=('Arial', 7), width=12, height=3, relief='sunken')
        plant_widgets['image_label'].pack(pady=5)

        plant_widgets['status_label'] = tk.Label(controls_frame, text="CHECKING...", font=('Arial', 10, 'bold'), bg='white', fg='orange', width=14, height=2)
        plant_widgets['status_label'].pack(pady=5)

        plant_widgets['voltage_label'] = tk.Label(controls_frame, text="Voltage: --", font=('Arial', 8), bg='white', width=14, height=2)
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
            # Check if plant_id is valid
            if plant_id >= len(self.plant_widgets):
                logging.error(f"Invalid plant_id: {plant_id}, max: {len(self.plant_widgets)-1}")
                return
                
            path = filedialog.askopenfilename(filetypes=[("Image files", "*.jpg *.png *.jpeg")])
            if path:
                self.config[f'plant_{plant_id}']['image_path'] = path
                self.save_config()
                img = Image.open(path).resize((40, 40))
                
                # Update the image in the plant widgets
                self.plant_widgets[plant_id]['image'] = ImageTk.PhotoImage(img)
                self.plant_widgets[plant_id]['image_label'].config(image=self.plant_widgets[plant_id]['image'])
                logging.info(f"Updated image for plant_{plant_id}: {path}")
        except Exception as e:
            logging.error(f"Image selection failed for plant_{plant_id}: {e}")

    def show_plant_details(self, plant_id):
        try:
            # Check if plant_id is valid
            if plant_id >= len(self.plant_widgets):
                logging.error(f"Invalid plant_id: {plant_id}, max: {len(self.plant_widgets)-1}")
                return
                
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
                    img = Image.open(image_path).resize((120, 120))
                    photo = ImageTk.PhotoImage(img)
                    tk.Label(details_window, image=photo, bg='white').pack(pady=5)
                    details_window.image = photo
                except Exception as e:
                    logging.error(f"Details image load failed for plant_{plant_id}: {e}")
            tk.Button(details_window, text="Edit Thresholds", command=lambda: self.manual_thresholds(plant_id),
                     bg='#4CAF50', fg='white', font=('Arial', 12, 'bold'), width=12, height=2).pack(pady=10)
        except Exception as e:
            logging.error(f"Show plant details failed for plant_{plant_id}: {e}")

    def update_plant_name(self, plant_id):
        try:
            # Check if plant_id is valid
            if plant_id >= len(self.plant_widgets):
                logging.error(f"Invalid plant_id: {plant_id}, max: {len(self.plant_widgets)-1}")
                return
                
            name = self.plant_widgets[plant_id]['name_var'].get().strip()
            if name:
                self.config[f'plant_{plant_id}']['name'] = name
                self.save_config()
                logging.info(f"Updated name for plant_{plant_id} to {name}")
        except Exception as e:
            logging.error(f"Update plant name failed for plant_{plant_id}: {e}")

    def manual_thresholds(self, plant_id):
        try:
            # Check if plant_id is valid
            if plant_id >= len(self.plant_widgets):
                logging.error(f"Invalid plant_id: {plant_id}, max: {len(self.plant_widgets)-1}")
                return
                
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
        except Exception as e:
            logging.error(f"Manual thresholds failed for plant_{plant_id}: {e}")

    def get_moisture_status(self, voltage, plant_id):
        dry_threshold = self.config[f'plant_{plant_id}']['dry_threshold']
        wet_threshold = self.config[f'plant_{plant_id}']['wet_threshold']
        max_voltage = 3.3

        if voltage < dry_threshold:
            status_text = "DRY - WATER NEEDED!"
            status_color = "#FF9999"
            progress_value = (voltage / dry_threshold) * 20 if dry_threshold > 0 else 0
            show_alert = True
        elif voltage > wet_threshold:
            status_text = "TOO WET"
            status_color = "#99CCFF"
            progress_value = 80 + ((voltage - wet_threshold) / (max_voltage - wet_threshold)) * 20 if max_voltage > wet_threshold else 100
            show_alert = False
        else:
            status_text = "PERFECT"
            status_color = "#99FF99"
            progress_value = 20 + ((voltage - dry_threshold) / (wet_threshold - dry_threshold)) * 60 if wet_threshold > dry_threshold else 20
            show_alert = False

        progress_value = max(0, min(100, progress_value))
        return status_text, status_color, progress_value, show_alert

    def monitor_moisture(self):
        current_dry_plants = set()
        while self.monitoring:
            try:
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

                # Update all plants during monitoring
                for i in range(self.num_plants):
                    if self.hardware_ready and self.channels[i]:
                        raw_value = self.channels[i].value
                        voltage = self.channels[i].voltage
                    else:
                        raw_value = 0
                        voltage = random.uniform(0.0, 3.3)
                    
                    status_text, status_color, progress_value, show_alert = self.get_moisture_status(voltage, i)
                    self.root.after(0, self.update_gui, i, raw_value, voltage, status_text, status_color, progress_value, show_alert)
                    
                    plant_name = self.config[f'plant_{i}']['name']
                    if show_alert:
                        if plant_name not in current_dry_plants:
                            self.root.after(0, lambda name=plant_name: self.dry_listbox.insert(tk.END, name))
                            current_dry_plants.add(plant_name)
                    elif plant_name in current_dry_plants:
                        self.root.after(0, lambda name=plant_name: self.remove_from_dry_list(name))
                        current_dry_plants.remove(plant_name)

                time.sleep(self.config['plant_0']['update_interval'])
            except Exception as e:
                logging.error(f"Monitoring error: {e}")
                self.root.after(0, self.update_gui_error)
                time.sleep(5)

    def remove_from_dry_list(self, plant_name):
        """Helper method to safely remove plant from dry list"""
        try:
            items = self.dry_listbox.get(0, tk.END)
            if plant_name in items:
                index = items.index(plant_name)
                self.dry_listbox.delete(index)
        except (ValueError, tk.TclError):
            pass  # Plant not in list or list has changed

    def update_gui(self, plant_id, raw_value, voltage, status_text, status_color, progress_value, show_alert):
        try:
            # Check if plant_id is valid
            if plant_id >= len(self.plant_widgets):
                logging.error(f"Invalid plant_id in update_gui: {plant_id}, max: {len(self.plant_widgets)-1}")
                return
                
            widgets = self.plant_widgets[plant_id]
            required_keys = ['frame', 'name_frame', 'main_frame', 'controls_frame', 'button_row_frame',
                            'voltage_label', 'status_label', 'moisture_progress', 'alert_label']
            for key in required_keys:
                if key not in widgets:
                    logging.error(f"Missing widget key '{key}' for plant_{plant_id}")
                    return
            
            # Only update if the color has actually changed to prevent flickering
            current_bg = widgets['frame'].cget('bg')
            if current_bg != status_color:
                widgets['frame'].config(bg=status_color)
                widgets['name_frame'].config(bg=status_color)
                widgets['main_frame'].config(bg=status_color)
                widgets['controls_frame'].config(bg=status_color)
                widgets['button_row_frame'].config(bg=status_color)
                widgets['voltage_label'].config(bg=status_color)
                widgets['status_label'].config(bg=status_color)
                
                # Update image label background if it exists
                if 'image_label' in widgets:
                    widgets['image_label'].config(bg=status_color)
            
            # Update text only if it has changed
            current_voltage_text = widgets['voltage_label'].cget('text')
            new_voltage_text = f"Voltage: {voltage:.2f} V"
            if current_voltage_text != new_voltage_text:
                widgets['voltage_label'].config(text=new_voltage_text)
            
            current_status_text = widgets['status_label'].cget('text')
            if current_status_text != status_text:
                widgets['status_label'].config(text=status_text, fg='black')
            
            # Update progress bar
            widgets['moisture_progress']['value'] = progress_value
            
            # Update alert
            current_alert = widgets['alert_label'].cget('text')
            new_alert = "!" if show_alert else ""
            if current_alert != new_alert:
                widgets['alert_label'].config(text=new_alert)
                
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
        try:
            self.server_socket.close()
        except:
            pass
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
