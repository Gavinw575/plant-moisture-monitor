#!/bin/bash
echo "Installing Plant Moisture Monitor..."

# Update system
sudo apt update

# Install Python dependencies
pip3 install -r requirements.txt

# Make the main script executable
chmod +x plant_monitor.py

# Create desktop shortcut
cat > ~/Desktop/PlantMonitor.desktop << EOF
[Desktop Entry]
Name=Plant Monitor
Comment=Monitor plant moisture levels
Exec=python3 $(pwd)/plant_monitor.py
Icon=applications-science
Terminal=false
Type=Application
Categories=Utility;
EOF

chmod +x ~/Desktop/PlantMonitor.desktop

echo "Installation complete!"
echo "You can now run: python3 plant_monitor.py"
echo "Or double-click the desktop shortcut"
