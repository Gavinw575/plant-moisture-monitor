```python
# Modified setup_gui and setup_plant_tile for minimal list
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

    self.plant_widgets = []
    for i in range(self.num_plants):
        plant_frame = tk.Frame(scrollable_frame, bg='white', relief='raised', bd=2, width=750, height=60)
        plant_frame.grid(row=i, column=0, padx=5, pady=5, sticky='ew')
        plant_frame.grid_propagate(False)
        self.setup_plant_tile(plant_frame, i)

    self.hardware_status = tk.Label(self.root, text="Hardware: Ready" if self.hardware_ready else "Hardware: Error",
                                   font=('Arial', 10), fg='green' if self.hardware_ready else 'red', bg='#2E8B57')
    self.hardware_status.pack(side='bottom', pady=5)

def setup_plant_tile(self, parent, plant_id):
    plant_widgets = {}
    plant_widgets['frame'] = parent

    name_frame = tk.Frame(parent, bg='white')
    name_frame.pack(pady=5, fill='x', padx=5)
    plant_widgets['name_var'] = tk.StringVar(value=self.config[f'plant_{plant_id}']['name'])
    name_label = tk.Label(name_frame, textvariable=plant_widgets['name_var'], font=('Arial', 16), bg='white')
    name_label.pack(side='left', padx=5)
    name_label.bind('<Button-1>', lambda e, pid=plant_id: self.show_plant_details(pid))

    plant_widgets['status_label'] = tk.Label(name_frame, text="CHECKING...", font=('Arial', 14, 'bold'), bg='white', fg='orange')
    plant_widgets['status_label'].pack(side='left', padx=10)

    plant_widgets['alert_label'] = tk.Label(name_frame, text="!", font=('Arial', 16, 'bold'), fg='red', bg='white')
    plant_widgets['alert_label'].pack(side='right', padx=5)
    plant_widgets['alert_label'].pack_forget()

    self.plant_widgets.append(plant_widgets)

def show_plant_details(self, plant_id):
    detail_window = tk.Toplevel(self.root)
    detail_window.title(f"{self.config[f'plant_{plant_id}']['name']} Details")
    detail_window.geometry("400x400")
    detail_window.configure(bg='white')
    detail_window.grab_set()

    tk.Label(detail_window, text=f"{self.config[f'plant_{plant_id}']['name']}", font=('Arial', 16, 'bold'), bg='white').pack(pady=10)
    tk.Label(detail_window, text="[Plant Image]", font=('Arial', 10), bg='white', width=15, height=5, relief='sunken').pack(pady=5)

    plant_widgets = self.plant_widgets[plant_id]
    plant_widgets['voltage_label'] = tk.Label(detail_window, text="Voltage: --", font=('Arial', 12), bg='white')
    plant_widgets['voltage_label'].pack(pady=5)
    plant_widgets['moisture_progress'] = ttk.Progressbar(detail_window, length=200, mode='determinate')
    plant_widgets['moisture_progress'].pack(pady=5)

    tk.Button(detail_window, text="Set Thresholds", command=lambda: self.manual_thresholds(plant_id),
             bg='#4CAF50', fg='white', font=('Arial', 14, 'bold'), width=15, height=2).pack(pady=10)

    tk.Button(detail_window, text="Rename", command=lambda: self.rename_plant(plant_id),
             bg='#FFA500', fg='white', font=('Arial', 14, 'bold'), width=15, height=2).pack(pady=10)

def rename_plant(self, plant_id):
    rename_window = tk.Toplevel(self.root)
    rename_window.title(f"Rename {self.config[f'plant_{plant_id}']['name']}")
    rename_window.geometry("400x200")
    rename_window.configure(bg='white')
    rename_window.grab_set()

    tk.Label(rename_window, text="Enter New Name:", font=('Arial', 14), bg='white').pack(pady=5)
    name_var = tk.StringVar(value=self.config[f'plant_{plant_id}']['name'])
    name_entry = tk.Entry(rename_window, textvariable=name_var, font=('Arial', 14), width=20)
    name_entry.pack(pady=5)
    name_entry.bind('<FocusIn>', lambda e: name_entry.select_range(0, tk.END))

    def save_name():
        name = name_var.get().strip()
        if name:
            self.config[f'plant_{plant_id}']['name'] = name
            self.plant_widgets[plant_id]['name_var'].set(name)
            self.save_config()
        rename_window.destroy()

    tk.Button(rename_window, text="Save", command=save_name,
             bg='green', fg='white', font=('Arial', 14, 'bold'), width=10, height=2).pack(pady=10)
```
