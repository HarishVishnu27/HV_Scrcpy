#!/bin/bash

# Device Farm Setup Script
echo "🚀 Setting up Device Farm Application..."

# Check Python version
python_version=$(python3 --version 2>&1 | grep -o '[0-9]\+\.[0-9]\+' | head -1)
echo "📋 Python version: $python_version"

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip3 install -r requirements.txt

# Check for ADB
echo "🔍 Checking for ADB..."
if command -v adb &> /dev/null; then
    echo "✅ ADB is installed: $(adb --version | head -1)"
else
    echo "❌ ADB not found. Installing Android SDK platform tools..."
    
    # Try to install ADB via package manager
    if command -v apt-get &> /dev/null; then
        echo "🔧 Installing via apt-get..."
        sudo apt-get update
        sudo apt-get install -y android-tools-adb android-tools-fastboot
    elif command -v brew &> /dev/null; then
        echo "🔧 Installing via homebrew..."
        brew install android-platform-tools
    else
        echo "⚠️  Please install Android SDK platform tools manually:"
        echo "   - Download from: https://developer.android.com/studio/releases/platform-tools"
        echo "   - Add to PATH: export PATH=\$PATH:/path/to/platform-tools"
    fi
fi

# Final check
echo ""
echo "🔍 Final system check:"
echo "   Python: $(python3 --version)"
echo "   ADB: $(adb --version 2>/dev/null | head -1 || echo 'Not found')"
echo ""

# Check ADB devices
echo "📱 Checking connected devices..."
if command -v adb &> /dev/null; then
    adb devices
    echo ""
    echo "💡 If no devices are listed:"
    echo "   1. Connect your Android device via USB"
    echo "   2. Enable Developer Options"
    echo "   3. Enable USB Debugging"
    echo "   4. Accept the debugging authorization prompt"
else
    echo "❌ Cannot check devices - ADB not installed"
fi

echo ""
echo "✅ Setup complete! Run the application with:"
echo "   python3 app.py"
echo ""
echo "🌐 Then open your browser to: http://localhost:5000"