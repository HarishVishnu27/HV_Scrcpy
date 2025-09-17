#!/usr/bin/env python3
"""
Device Farm Launcher Script
"""

import os
import sys
import subprocess

def check_dependencies():
    """Check if required dependencies are available"""
    try:
        subprocess.run(['adb', 'version'], capture_output=True, check=True)
        print("✓ ADB is available")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("✗ ADB not found. Please install Android Debug Bridge (ADB)")
        return False
    
    try:
        subprocess.run(['scrcpy', '--version'], capture_output=True, check=True)
        print("✓ Scrcpy is available")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("✗ Scrcpy not found. Please install scrcpy")
        print("  Visit: https://github.com/Genymobile/scrcpy")
        return False
    
    return True

def install_python_deps():
    """Install Python dependencies"""
    try:
        print("Installing Python dependencies...")
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'], 
                      check=True)
        print("✓ Python dependencies installed")
        return True
    except subprocess.CalledProcessError:
        print("✗ Failed to install Python dependencies")
        return False

def main():
    """Main launcher function"""
    print("🚀 Device Farm Launcher")
    print("=" * 40)
    
    # Change to device_farm directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    # Check system dependencies
    if not check_dependencies():
        print("\nPlease install required dependencies and try again.")
        sys.exit(1)
    
    # Install Python dependencies
    if not install_python_deps():
        print("\nFailed to install Python dependencies.")
        sys.exit(1)
    
    print("\n🎯 Starting Device Farm Web Application...")
    print("Access the application at: http://localhost:5000")
    print("Press Ctrl+C to stop the server")
    print("-" * 40)
    
    # Start the Flask application
    try:
        os.execv(sys.executable, [sys.executable, 'app.py'])
    except KeyboardInterrupt:
        print("\n👋 Device Farm stopped")

if __name__ == '__main__':
    main()