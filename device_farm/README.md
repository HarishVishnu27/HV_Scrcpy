# Device Farm - Android Screen Mirror

A web-based application for viewing Android device screens directly in the browser using Flask and WebSocket streaming.

## Features

- 🖥️ **Browser-based**: View Android screens directly in your web browser
- 📱 **Real-time streaming**: Live screen updates via WebSocket
- 🔌 **Simple connection**: Connect via USB with ADB
- 🎯 **Multiple devices**: Support for multiple connected devices
- 🚀 **Easy setup**: Simple installation and configuration

## Requirements

- Python 3.8+ (tested with Python 3.12+)
- Android device with USB debugging enabled
- ADB (Android Debug Bridge) installed
- USB cable for device connection

## Installation

1. **Clone and navigate to device farm directory:**
   ```bash
   cd device_farm
   ```

2. **Run the setup script:**
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```

3. **Or install manually:**
   ```bash
   pip3 install -r requirements.txt
   ```

## Usage

1. **Connect your Android device:**
   - Enable Developer Options on your Android device
   - Enable USB Debugging in Developer Options
   - Connect device via USB cable
   - Accept the USB debugging authorization prompt

2. **Start the application:**
   ```bash
   python3 app.py
   ```

3. **Open your browser:**
   Navigate to `http://localhost:5000`

4. **Control your device:**
   - Click "Start Device Control"
   - Select your device from the list
   - Click "Connect Device"
   - View the live screen in your browser!

## Architecture

The application consists of:

- **Flask Web Server**: Serves the web interface and handles HTTP requests
- **WebSocket Server**: Provides real-time communication for screen updates
- **ADB Integration**: Uses Android Debug Bridge to capture screenshots
- **Device Manager**: Handles device detection and screen capture

### Key Components

- `app.py` - Main Flask application with WebSocket support
- `templates/device_control.html` - Main control interface
- `templates/index.html` - Landing page
- `static/css/style.css` - Custom styling

## Configuration

The application can be configured by modifying `app.py`:

- **Screenshot interval**: Adjust `time.sleep(0.5)` in `_screenshot_loop` for faster/slower updates
- **Server port**: Change `port=5000` in the `socketio.run()` call
- **Image quality**: Modify ADB screenshot parameters

## Troubleshooting

### No devices found
- Ensure USB debugging is enabled
- Check ADB connection: `adb devices`
- Try different USB cable or port
- Restart ADB: `adb kill-server && adb start-server`

### Connection fails
- Check device authorization
- Ensure only one ADB instance is running
- Verify device compatibility (Android 5.0+)

### Slow performance
- Increase screenshot interval in `_screenshot_loop`
- Check USB cable quality
- Close other applications using ADB

## Python 3.13 Compatibility

This application is designed to work with Python 3.13+ by:
- Using `async_mode='threading'` instead of eventlet
- Proper asyncio task handling
- Compatible Flask-SocketIO configuration

## Security Notes

- This application is intended for development/testing purposes
- Only connect trusted devices
- Use on secure networks only
- ADB connections can be intercepted on untrusted networks

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is based on scrcpy and follows the same Apache 2.0 license.