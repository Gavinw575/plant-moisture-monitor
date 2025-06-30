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
   git clone https://github.com/YOUR_USERNAME/plant-moisture-monitor.git
   cd plant-moisture-monitor
