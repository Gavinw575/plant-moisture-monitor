# Plant Moisture Monitor

A Raspberry Pi application that monitors soil moisture using an MCP3008 ADC and provides a user-friendly GUI interface.

## Features
- Real-time moisture monitoring
- Visual GUI with color-coded status
- Configurable dry/wet thresholds
- Built-in sensor calibration
- Auto-saving settings

## Hardware Requirements
- Raspberry Pi (any model with GPIO)
- MCP3008 ADC chip
- Soil moisture sensor
- Jumper wires for connections

## Wiring
- MCP3008 VDD → 3.3V
- MCP3008 VREF → 3.3V
- MCP3008 AGND → GND
- MCP3008 DGND → GND
- MCP3008 CLK → GPIO 11 (SCLK)
- MCP3008 DOUT → GPIO 9 (MISO)
- MCP3008 DIN → GPIO 10 (MOSI)
- MCP3008 CS → GPIO 5
- Moisture sensor → MCP3008 CH0

## Installation
1. Clone this repository:
   ```bash
   git clone https://github.com/Gavinw575/plant-moisture-monitor
   cd plant-moisture-monitor

2. Run installation script:
   ```bash
   chmod +x install.sh
   ./install.sh --break-system-packages

3. Run the application:
   ```bash
   python3 plant_monitor.py


## Updating
1. To get to the latest version:
   ```bash
   ./update.sh
   
## Usage

- Connect your hardware according to the wiring diagram
- Run the application
- Use the "Calibrate Sensor" button to set up your specific sensor
- Monitor your plant's moisture in real-time!

## Configuration
- Settings are automatically saved in moisture_config.json and persist between runs.

## Step 3: Setup on Raspberry Pi

### Initial Setup (do this once):

1. **Open terminal on your Pi**

2. **Install git** (if not already installed):
   ```bash
   sudo apt update
   sudo apt install git -y

3. Clone your repository:
   ```bash
   cd ~/Documents  # or wherever you want it
   git clone https://github.com/Gavinw575/plant-moisture-monitor
   cd plant-moisture-monitor

4. Run the installation:
   ```bash
   chmod +x install.sh
   ./install.sh

5. Test the application:
   ```bash
   python3 plant_monitor.py


# For Future Updates (super easy):
Whenever you want to update to the latest version:
   ```bash
   cd ~/Documents/plant-moisture-monitor
   chmod +x ./update.sh
   ./update.sh --break-system-packages
   ```
## Step 4: Making Updates
To update the code:

Edit files on GitHub.com directly in the web interface, OR
Clone to your computer, make changes, and push:
   ```bash
   git clone https://github.com/Gavinw575/plant-moisture-monitor
   cd plant-moisture-monitor
```
# make your changes
```
   git add .
   git commit -m "Description of changes"
   git push
   ```

Then on your Pi:
   ```bash
   cd ~/Documents/plant-moisture-monitor
   ./update.sh
   ```
## Step 5: Auto-start (Optional)
To make the app start automatically when your Pi boots:

Create a service file:
   ```bash
   sudo nano /etc/systemd/system/plant-monitor.service
   ```
Add this content:
   ```
   ini[Unit]
   Description=Plant Moisture Monitor
   After=network.target

   [Service]
   Type=simple
   User=pi
   WorkingDirectory=/home/pi/Documents/plant-moisture-monitor
   ExecStart=/usr/bin/python3 /home/pi/Documents/plant-moisture-monitor/plant_monitor.py
   Restart=always
   RestartSec=5
   Environment=DISPLAY=:0

   [Install]
   WantedBy=multi-user.target
   ```
Enable and start the service:

   ```bash
   sudo systemctl enable plant-monitor.service
   sudo systemctl start plant-monitor.service
   ```
