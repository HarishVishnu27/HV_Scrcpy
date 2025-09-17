# Device Farm - Web-based Android Device Control

A web-based device farm that allows controlling Android devices through a browser with embedded video streaming using WebRTC.

## Features

- 🌐 **Web-based Interface**: Control devices from any browser
- 📱 **Embedded Video Streaming**: View device screen directly in the browser using WebRTC
- 🖱️ **Touch & Click Control**: Full touch, click, and gesture support
- ⌨️ **Keyboard Input**: Send text and key events to devices
- 🎮 **Quick Actions**: Home, Back, Menu, Volume controls
- 📊 **Device Management**: View device status, battery, resolution
- 🔄 **Real-time Communication**: WebSocket-based control events

## Prerequisites

1. **ADB (Android Debug Bridge)**
   ```bash
   # Ubuntu/Debian
   sudo apt-get install adb
   
   # macOS
   brew install android-platform-tools
   
   # Windows
   # Download from https://developer.android.com/studio/releases/platform-tools
   ```

2. **Scrcpy**
   ```bash
   # Ubuntu/Debian
   sudo apt-get install scrcpy
   
   # macOS
   brew install scrcpy
   
   # Windows
   # Download from https://github.com/Genymobile/scrcpy/releases
   ```

3. **Python 3.8+**
   ```bash
   python3 --version
   ```

## Installation

1. **Navigate to device farm directory**:
   ```bash
   cd device_farm
   ```

2. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Connect Android devices via USB** and enable USB debugging

4. **Authorize devices for debugging** when prompted

## Usage

### Starting the Device Farm

```bash
# Using the launcher script (recommended)
python3 run_device_farm.py

# Or directly
python3 app.py
```

### Accessing the Web Interface

1. Open your browser and go to: `http://localhost:5000`
2. You'll see a list of connected Android devices
3. Click "Connect" to start streaming a device
4. Click "View Screen" to open the device control interface

### Device Control

- **Touch/Click**: Click on the device screen to send touch events
- **Scroll**: Use mouse wheel to scroll on the device
- **Keyboard**: Type text in the text input box and click "Send"
- **Quick Actions**: Use the buttons for Home, Back, Menu, Volume controls
- **Fullscreen**: Click the fullscreen button for better viewing
- **Screenshot**: Capture screenshots of the device screen

## Architecture

### Backend Components

- **Flask Web Server**: Main HTTP server with WebSocket support
- **Device Manager**: Discovers and manages Android devices via ADB
- **WebRTC Streamer**: Handles real-time video streaming from devices
- **Scrcpy Bridge**: Interfaces with scrcpy processes for device control
- **WebSocket Server**: Real-time communication for control events

### Frontend Components

- **Device List Page**: Shows available devices and connection status
- **Device Control Page**: Embedded video player with touch/keyboard controls
- **WebRTC Client**: Handles video streaming and peer connections
- **Input Handler**: Captures and forwards touch, keyboard, and scroll events

### Communication Flow

1. **Device Discovery**: ADB lists connected devices
2. **Connection**: Start scrcpy process for selected device
3. **WebRTC Setup**: Establish peer connection for video streaming
4. **Control Events**: WebSocket forwards input events to device
5. **Video Stream**: WebRTC streams device screen to browser

## Troubleshooting

### Common Issues

1. **No devices found**:
   - Ensure devices are connected via USB
   - Enable USB debugging in Developer Options
   - Authorize computer for debugging when prompted
   - Run `adb devices` to verify connection

2. **Scrcpy fails to start**:
   - Check device permissions
   - Ensure scrcpy is installed and in PATH
   - Try `scrcpy --serial DEVICE_ID` manually

3. **Video not streaming**:
   - Check WebRTC browser support
   - Verify firewall/network settings
   - Check browser console for errors

4. **Touch events not working**:
   - Ensure device is unlocked
   - Check scrcpy control connection
   - Verify device supports input injection

### Browser Compatibility

- ✅ Chrome/Chromium 60+
- ✅ Firefox 60+
- ✅ Safari 12+
- ✅ Edge 79+

### Device Compatibility

- Android 5.0+ (API level 21)
- USB debugging enabled
- Screen unlocked for control events

## Configuration

### Environment Variables

- `DEVICE_FARM_HOST`: Server host (default: 0.0.0.0)
- `DEVICE_FARM_PORT`: Server port (default: 5000)
- `DEVICE_FARM_DEBUG`: Enable debug mode (default: True)

### Scrcpy Options

The device farm uses optimized scrcpy settings:
- Video encoder: H.264
- Max FPS: 30
- Bitrate: 2 Mbps
- No audio (for performance)

## Security Considerations

- The device farm is intended for local/trusted network use
- Devices have full control access when connected
- Consider firewall rules for production deployments
- Use HTTPS in production environments

## Development

### Project Structure

```
device_farm/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── run_device_farm.py    # Launcher script
├── src/                  # Backend modules
│   ├── device_manager.py # Device discovery and management
│   ├── webrtc_streamer.py # WebRTC video streaming
│   └── scrcpy_bridge.py  # Scrcpy integration
├── templates/            # HTML templates
│   ├── index.html        # Device list page
│   └── device_control.html # Device control page
└── static/               # Frontend assets
    ├── css/              # Stylesheets
    └── js/               # JavaScript files
```

### Adding Features

1. **New Control Actions**: Add to `scrcpy_bridge.py` and device control JS
2. **UI Improvements**: Modify templates and CSS files
3. **Device Info**: Extend `device_manager.py` for additional device data
4. **Streaming Options**: Configure WebRTC settings in `webrtc_streamer.py`

## License

This project extends the scrcpy ecosystem and follows similar open-source principles.