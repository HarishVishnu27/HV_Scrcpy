#!/bin/bash
# Device Farm Startup Script

echo "Starting Device Farm Application..."

# Check if we're in the correct directory
if [ ! -f "device_farm/app.py" ]; then
    echo "Error: Please run this script from the HV_Scrcpy root directory"
    exit 1
fi

# Install Python dependencies
echo "Installing Python dependencies..."
pip3 install -r device_farm/requirements.txt

# Check if adb is available
if ! command -v adb &> /dev/null; then
    echo "Warning: adb not found in PATH. Please ensure Android SDK platform-tools are installed."
fi

# Check if scrcpy is available  
if ! command -v scrcpy &> /dev/null; then
    echo "Warning: scrcpy not found in PATH. Please ensure scrcpy is installed and available."
fi

# Start the Device Farm application
echo "Starting Device Farm server..."
cd device_farm
python3 app.py