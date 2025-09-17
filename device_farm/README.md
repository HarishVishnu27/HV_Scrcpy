# Device Farm - Android Device Streaming

A web-based application for streaming Android device screens using scrcpy as the backend and WebRTC for browser-based streaming.

## Features

- Web interface for managing connected Android devices
- Real-time device screen streaming via WebRTC
- Support for multiple simultaneous device connections
- Automatic device discovery via ADB
- RESTful API for device management
- WebSocket signaling for WebRTC connections

## Prerequisites

1. **Android SDK Platform Tools** - for ADB command
   - Install from: https://developer.android.com/studio/releases/platform-tools
   - Ensure `adb` is in your system PATH

2. **scrcpy** - for device screen capture
   - Install from: https://github.com/Genymobile/scrcpy
   - Ensure `scrcpy` is in your system PATH
   - **Important**: Use scrcpy v2.0+ which supports `--no-playback` parameter

3. **Python 3.8+** with pip

4. **USB Debugging enabled** on Android devices
   - Go to Settings > Developer Options > USB Debugging

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/HarishVishnu27/HV_Scrcpy.git
   cd HV_Scrcpy
   ```

2. Install Python dependencies:
   ```bash
   pip3 install -r device_farm/requirements.txt
   ```

3. Make sure ADB and scrcpy are installed and available in PATH:
   ```bash
   adb version
   scrcpy --version
   ```

## Usage

### Quick Start

1. Connect Android device(s) via USB and enable USB debugging
2. Start the Device Farm server:
   ```bash
   ./start_device_farm.sh
   ```
   Or manually:
   ```bash
   cd device_farm
   python3 app.py
   ```

3. Open your browser and go to: http://localhost:3000

4. Select a device and click "Start Streaming"

### API Endpoints

- `GET /` - Main web interface
- `GET /devices` - List connected devices
- `POST /devices/{device_id}/start` - Start streaming for a device
- `POST /devices/{device_id}/stop` - Stop streaming for a device
- `GET /devices/{device_id}/status` - Get device streaming status
- `GET /ws` - WebSocket endpoint for WebRTC signaling

## Configuration

### Environment Variables

- `DEVICE_FARM_HOST` - Server host (default: localhost)
- `DEVICE_FARM_PORT` - Server port (default: 3000)

### Scrcpy Parameters

The application uses the following scrcpy parameters for optimal streaming:

- `--no-playback` - Disable video/audio playback on server (replaces deprecated `--no-display`)
- `--no-control` - Disable device control for streaming-only mode
- `--video-codec h264` - Use H.264 for better WebRTC compatibility  
- `--max-fps 30` - Limit frame rate for better streaming performance
- `--video-bit-rate 2M` - Set bit rate for streaming

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Browser   │◄──►│ Device Farm App │◄──►│ Android Device  │
│                 │    │                 │    │                 │
│ - HTML/CSS/JS   │    │ - Python/aiohttp│    │ - scrcpy server │
│ - WebRTC client │    │ - WebSocket     │    │ - USB/TCP       │
│ - Video stream  │    │ - Device mgmt   │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Components

1. **DeviceManager** - Manages ADB device discovery and status
2. **ScrcpyManager** - Handles scrcpy process lifecycle and port management
3. **WebRTCSignalingServer** - Manages WebSocket connections for WebRTC signaling
4. **DeviceFarmApp** - Main application with HTTP server and API endpoints

## Development

### Running in Development Mode

```bash
cd device_farm
python3 app.py
```

### Testing with Mock Devices

If you don't have physical devices available, you can test with Android emulators:

1. Start Android emulator via Android Studio
2. Verify connection: `adb devices`
3. Start Device Farm application

### Adding New Features

1. Device control endpoints
2. Video recording capabilities  
3. Multiple video quality options
4. Real-time device metrics
5. User authentication

## Troubleshooting

### Common Issues

1. **"ADB not found in PATH"**
   - Install Android SDK Platform Tools
   - Add platform-tools directory to system PATH

2. **"scrcpy not found in PATH"**
   - Install scrcpy from official releases
   - Ensure it's in system PATH

3. **"No devices connected"**
   - Check USB debugging is enabled
   - Verify device is connected: `adb devices`
   - Try different USB cable/port

4. **"Failed to start streaming"**
   - Check device is not already being used by another scrcpy instance
   - Verify device has sufficient permissions

5. **"Connecting to device..." hangs**
   - Check firewall settings
   - Verify WebSocket connection in browser console
   - Try refreshing the page

### Logs

Application logs are displayed in the console. For more detailed debugging:

```bash
cd device_farm
python3 app.py 2>&1 | tee device_farm.log
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is licensed under the Apache License 2.0 - see the LICENSE file for details.

## Acknowledgments

- [scrcpy](https://github.com/Genymobile/scrcpy) - The amazing Android screen mirroring tool
- [aiohttp](https://docs.aiohttp.org/) - Async HTTP client/server framework
- [WebRTC](https://webrtc.org/) - Real-time communication for the web