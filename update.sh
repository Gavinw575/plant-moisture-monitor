#!/bin/bash
echo "Updating Plant Moisture Monitor..."

# Pull latest changes
git pull origin main

# Update dependencies if needed
pip3 install -r requirements.txt

# Make sure script is executable
chmod +x plant_monitor.py

echo "Update complete!"
echo "Restart the application to use the latest version"
