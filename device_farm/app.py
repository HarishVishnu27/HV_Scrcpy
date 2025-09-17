#!/usr/bin/env python3
"""
Device Farm Application - WebRTC Streaming Server

This application provides a web-based interface for streaming Android device screens
using scrcpy as the backend and WebRTC for browser-based streaming.
"""

import asyncio
import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from typing import Dict, List, Optional, Set
import weakref

from video_stream import ScreenStreamServer
from demo_devices import MockDeviceManager, MockScreenStreamServer

try:
    import websockets
except ImportError:
    print("websockets library not found. Installing...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "websockets"])
    import websockets

try:
    import aiohttp
    from aiohttp import web, web_ws
except ImportError:
    print("aiohttp library not found. Installing...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "aiohttp"])
    import aiohttp
    from aiohttp import web, web_ws

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DeviceManager:
    """Manages connected Android devices via ADB"""
    
    def __init__(self):
        self.devices = {}
        self.use_mock = False
        self.mock_manager = None
        self.refresh_devices()
    
    def refresh_devices(self):
        """Refresh the list of connected devices"""
        try:
            result = subprocess.run(
                ['adb', 'devices'], 
                capture_output=True, 
                text=True, 
                check=True
            )
            
            devices = {}
            lines = result.stdout.strip().split('\n')[1:]  # Skip header
            
            for line in lines:
                if line.strip() and '\t' in line:
                    device_id, status = line.strip().split('\t')
                    if status == 'device':
                        devices[device_id] = {
                            'id': device_id,
                            'status': status,
                            'streaming': False
                        }
            
            self.devices = devices
            self.use_mock = False
            logger.info(f"Found {len(devices)} connected devices")
            
            # If no real devices found, fall back to mock devices
            if len(devices) == 0:
                logger.info("No real devices found, using mock devices for demonstration")
                self.use_mock = True
                self.mock_manager = MockDeviceManager()
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get device list: {e}")
            self._setup_mock_devices()
        except FileNotFoundError:
            logger.error("ADB not found in PATH, using mock devices for demonstration")
            self._setup_mock_devices()
    
    def _setup_mock_devices(self):
        """Setup mock devices for demonstration"""
        self.use_mock = True
        self.mock_manager = MockDeviceManager()
    
    def get_devices(self) -> List[Dict]:
        """Get list of available devices"""
        if self.use_mock and self.mock_manager:
            return self.mock_manager.get_devices()
        return list(self.devices.values())
    
    def get_device(self, device_id: str) -> Optional[Dict]:
        """Get specific device info"""
        if self.use_mock and self.mock_manager:
            return self.mock_manager.get_device(device_id)
        return self.devices.get(device_id)

class ScrcpyManager:
    """Manages scrcpy processes for device streaming"""
    
    def __init__(self):
        self.processes = {}
        self.ports = set(range(8000, 8100))  # Available port range
        self.used_ports = set()
    
    def get_available_port(self) -> Optional[int]:
        """Get an available port for streaming"""
        available = self.ports - self.used_ports
        if available:
            port = min(available)
            self.used_ports.add(port)
            return port
        return None
    
    def release_port(self, port: int):
        """Release a port back to the available pool"""
        self.used_ports.discard(port)
    
    def start_streaming(self, device_id: str) -> Optional[Dict]:
        """Start scrcpy streaming for a device"""
        if device_id in self.processes:
            logger.warning(f"Device {device_id} is already streaming")
            return None
        
        port = self.get_available_port()
        if not port:
            logger.error("No available ports for streaming")
            return None
        
        try:
            # Updated scrcpy command with --no-playback instead of --no-display
            cmd = [
                'scrcpy',
                '--serial', device_id,
                '--no-playback',  # Use --no-playback instead of deprecated --no-display
                '--no-control',   # Disable device control for streaming-only
                '--port', str(port),
                '--video-codec', 'h264',  # Use H.264 for better WebRTC compatibility
                '--max-fps', '30',        # Limit FPS for better streaming performance
                '--video-bit-rate', '2M'  # Set bit rate for streaming
            ]
            
            logger.info(f"Starting scrcpy for device {device_id} on port {port}")
            logger.debug(f"Command: {' '.join(cmd)}")
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            self.processes[device_id] = {
                'process': process,
                'port': port,
                'device_id': device_id,
                'started_at': time.time()
            }
            
            return {
                'device_id': device_id,
                'port': port,
                'status': 'starting'
            }
            
        except FileNotFoundError:
            logger.error("scrcpy not found in PATH")
            self.release_port(port)
            return None
        except Exception as e:
            logger.error(f"Failed to start scrcpy for device {device_id}: {e}")
            self.release_port(port)
            return None
    
    def stop_streaming(self, device_id: str) -> bool:
        """Stop scrcpy streaming for a device"""
        if device_id not in self.processes:
            return False
        
        process_info = self.processes[device_id]
        process = process_info['process']
        port = process_info['port']
        
        try:
            process.terminate()
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        except Exception as e:
            logger.error(f"Error stopping scrcpy process for device {device_id}: {e}")
        
        self.release_port(port)
        del self.processes[device_id]
        
        logger.info(f"Stopped streaming for device {device_id}")
        return True
    
    def get_streaming_info(self, device_id: str) -> Optional[Dict]:
        """Get streaming information for a device"""
        if device_id not in self.processes:
            return None
        
        process_info = self.processes[device_id]
        process = process_info['process']
        
        # Check if process is still running
        if process.poll() is not None:
            # Process has terminated
            self.stop_streaming(device_id)
            return None
        
        return {
            'device_id': device_id,
            'port': process_info['port'],
            'status': 'running',
            'uptime': time.time() - process_info['started_at']
        }

class WebRTCSignalingServer:
    """WebRTC signaling server for establishing peer connections"""
    
    def __init__(self):
        self.clients: Dict[str, any] = {}  # Use any instead of WebSocketServerProtocol
        self.device_streams: Dict[str, Set[str]] = {}  # device_id -> set of client_ids
    
    async def register_client(self, client_id: str, websocket):
        """Register a new client connection"""
        self.clients[client_id] = websocket
        logger.info(f"Client {client_id} connected")
    
    async def unregister_client(self, client_id: str):
        """Unregister a client connection"""
        if client_id in self.clients:
            del self.clients[client_id]
            
            # Remove client from all device streams
            for device_id, clients in self.device_streams.items():
                clients.discard(client_id)
            
            logger.info(f"Client {client_id} disconnected")
    
    async def handle_message(self, client_id: str, message: Dict):
        """Handle incoming WebRTC signaling messages"""
        msg_type = message.get('type')
        
        if msg_type == 'join_stream':
            await self.handle_join_stream(client_id, message)
        elif msg_type == 'leave_stream':
            await self.handle_leave_stream(client_id, message)
        elif msg_type in ['offer', 'answer', 'ice_candidate']:
            await self.handle_webrtc_message(client_id, message)
        else:
            logger.warning(f"Unknown message type from client {client_id}: {msg_type}")
    
    async def handle_join_stream(self, client_id: str, message: Dict):
        """Handle client joining a device stream"""
        device_id = message.get('device_id')
        if not device_id:
            await self.send_error(client_id, "Missing device_id")
            return
        
        if device_id not in self.device_streams:
            self.device_streams[device_id] = set()
        
        self.device_streams[device_id].add(client_id)
        
        await self.send_message(client_id, {
            'type': 'stream_joined',
            'device_id': device_id
        })
    
    async def handle_leave_stream(self, client_id: str, message: Dict):
        """Handle client leaving a device stream"""
        device_id = message.get('device_id')
        if device_id and device_id in self.device_streams:
            self.device_streams[device_id].discard(client_id)
        
        await self.send_message(client_id, {
            'type': 'stream_left',
            'device_id': device_id
        })
    
    async def handle_webrtc_message(self, client_id: str, message: Dict):
        """Handle WebRTC signaling messages (offer, answer, ICE candidates)"""
        # For now, just echo back the message for peer-to-peer setup
        # In a full implementation, this would handle routing between peers
        pass
    
    async def send_message(self, client_id: str, message: Dict):
        """Send message to a specific client"""
        if client_id in self.clients:
            websocket = self.clients[client_id]
            try:
                # Use the correct method for aiohttp WebSocket
                if hasattr(websocket, 'send_str'):
                    await websocket.send_str(json.dumps(message))
                else:
                    await websocket.send(json.dumps(message))
            except Exception as e:
                logger.error(f"Failed to send message to client {client_id}: {e}")
                await self.unregister_client(client_id)
    
    async def send_error(self, client_id: str, error: str):
        """Send error message to client"""
        await self.send_message(client_id, {
            'type': 'error',
            'message': error
        })
    
    async def broadcast_to_device_stream(self, device_id: str, message: Dict):
        """Broadcast message to all clients watching a device stream"""
        if device_id in self.device_streams:
            for client_id in self.device_streams[device_id].copy():
                await self.send_message(client_id, message)

class DeviceFarmApp:
    """Main Device Farm application"""
    
    def __init__(self, host='localhost', port=3000):
        self.host = host
        self.port = port
        
        self.device_manager = DeviceManager()
        self.scrcpy_manager = ScrcpyManager()
        self.signaling_server = WebRTCSignalingServer()
        
        # Use real or mock screen streaming based on device availability
        if self.device_manager.use_mock:
            logger.info("Using mock screen streaming for demonstration")
            self.screen_stream_server = MockScreenStreamServer()
        else:
            logger.info("Using real device screen streaming")
            self.screen_stream_server = ScreenStreamServer()
        
        self.app = web.Application()
        self.setup_routes()
        
        # For graceful shutdown
        self.shutdown_event = asyncio.Event()
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        if sys.platform != 'win32':
            # Python 3.13 compatibility: use add_signal_handler properly
            def signal_handler():
                logger.info("Received shutdown signal")
                self.shutdown_event.set()
            
            # Register signal handlers in the event loop when it's running
            loop = None
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                pass
            
            if loop:
                for sig in (signal.SIGTERM, signal.SIGINT):
                    loop.add_signal_handler(sig, signal_handler)
    
    def setup_routes(self):
        """Setup HTTP and WebSocket routes"""
        # Serve static files
        self.app.router.add_get('/', self.serve_index)
        self.app.router.add_get('/devices', self.get_devices)
        self.app.router.add_post('/devices/{device_id}/start', self.start_device_stream)
        self.app.router.add_post('/devices/{device_id}/stop', self.stop_device_stream)
        self.app.router.add_get('/devices/{device_id}/status', self.get_device_status)
        
        # WebSocket for signaling
        self.app.router.add_get('/ws', self.websocket_handler)
        
        # Serve static files (will be created later)
        self.app.router.add_static('/', path=os.path.join(os.path.dirname(__file__), 'static'), name='static')
    
    async def serve_index(self, request):
        """Serve the main index page"""
        # Return a simple HTML page for now
        html = """
<!DOCTYPE html>
<html>
<head>
    <title>Device Farm</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .device-card { border: 1px solid #ccc; margin: 10px; padding: 15px; border-radius: 5px; }
        .device-card.streaming { border-color: #4CAF50; background-color: #f9fff9; }
        button { padding: 8px 16px; margin: 5px; cursor: pointer; }
        .start-btn { background-color: #4CAF50; color: white; border: none; }
        .stop-btn { background-color: #f44336; color: white; border: none; }
        .status { font-weight: bold; }
        .video-container { margin-top: 20px; }
        video { width: 100%; max-width: 480px; border: 1px solid #ccc; }
        .connecting { color: #ff9800; }
        .connected { color: #4CAF50; }
        .error { color: #f44336; }
    </style>
</head>
<body>
    <h1>Device Farm - Android Device Streaming</h1>
    <div id="devices-container">
        <p>Loading devices...</p>
    </div>
    
    <script>
        let ws = null;
        let devices = [];
        
        async function loadDevices() {
            try {
                const response = await fetch('/devices');
                devices = await response.json();
                renderDevices();
            } catch (error) {
                console.error('Failed to load devices:', error);
                document.getElementById('devices-container').innerHTML = 
                    '<p class="error">Failed to load devices</p>';
            }
        }
        
        function renderDevices() {
            const container = document.getElementById('devices-container');
            
            if (devices.length === 0) {
                container.innerHTML = '<p>No devices connected. Please connect an Android device via USB and enable USB debugging.</p>';
                return;
            }
            
            container.innerHTML = devices.map(device => `
                <div class="device-card" id="device-${device.id}">
                    <h3>Device: ${device.id}</h3>
                    <p class="status">Status: <span id="status-${device.id}">${device.status}</span></p>
                    <button class="start-btn" onclick="startStreaming('${device.id}')" id="start-${device.id}">
                        Start Streaming
                    </button>
                    <button class="stop-btn" onclick="stopStreaming('${device.id}')" id="stop-${device.id}" style="display: none;">
                        Stop Streaming
                    </button>
                    <div class="video-container" id="video-${device.id}" style="display: none;">
                        <p class="connecting">Connecting to device...</p>
                        <video id="stream-${device.id}" autoplay muted></video>
                    </div>
                </div>
            `).join('');
        }
        
        async function startStreaming(deviceId) {
            try {
                updateDeviceStatus(deviceId, 'Starting...');
                
                const response = await fetch(`/devices/${deviceId}/start`, {
                    method: 'POST'
                });
                
                if (response.ok) {
                    const result = await response.json();
                    updateDeviceStatus(deviceId, 'Streaming');
                    showVideoContainer(deviceId);
                    
                    // Initialize WebRTC connection
                    initWebRTC(deviceId);
                } else {
                    const error = await response.text();
                    updateDeviceStatus(deviceId, `Error: ${error}`);
                }
            } catch (error) {
                console.error('Failed to start streaming:', error);
                updateDeviceStatus(deviceId, 'Error');
            }
        }
        
        async function stopStreaming(deviceId) {
            try {
                const response = await fetch(`/devices/${deviceId}/stop`, {
                    method: 'POST'
                });
                
                if (response.ok) {
                    updateDeviceStatus(deviceId, 'Stopped');
                    hideVideoContainer(deviceId);
                } else {
                    console.error('Failed to stop streaming');
                }
            } catch (error) {
                console.error('Failed to stop streaming:', error);
            }
        }
        
        function updateDeviceStatus(deviceId, status) {
            const statusElement = document.getElementById(`status-${deviceId}`);
            if (statusElement) {
                statusElement.textContent = status;
            }
            
            const startBtn = document.getElementById(`start-${deviceId}`);
            const stopBtn = document.getElementById(`stop-${deviceId}`);
            const deviceCard = document.getElementById(`device-${deviceId}`);
            
            if (status === 'Streaming') {
                startBtn.style.display = 'none';
                stopBtn.style.display = 'inline-block';
                deviceCard.classList.add('streaming');
            } else {
                startBtn.style.display = 'inline-block';
                stopBtn.style.display = 'none';
                deviceCard.classList.remove('streaming');
            }
        }
        
        function showVideoContainer(deviceId) {
            const videoContainer = document.getElementById(`video-${deviceId}`);
            if (videoContainer) {
                videoContainer.style.display = 'block';
            }
        }
        
        function hideVideoContainer(deviceId) {
            const videoContainer = document.getElementById(`video-${deviceId}`);
            if (videoContainer) {
                videoContainer.style.display = 'none';
            }
        }
        
        function initWebRTC(deviceId) {
            // Join video stream via WebSocket
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({
                    type: 'join_stream',
                    device_id: deviceId
                }));
                
                console.log('Joining video stream for device:', deviceId);
                
                // Show connecting message
                const videoContainer = document.getElementById(`video-${deviceId}`);
                if (videoContainer) {
                    videoContainer.innerHTML = `
                        <p class="connecting">Connecting to device stream...</p>
                        <canvas id="canvas-${deviceId}" width="480" height="800" style="border: 1px solid #ccc; max-width: 100%;"></canvas>
                    `;
                }
            } else {
                console.error('WebSocket not connected');
                setTimeout(() => initWebRTC(deviceId), 1000);
            }
        }
        
        function connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws`;  // Use same port as main server
            
            ws = new WebSocket(wsUrl);
            
            ws.onopen = function() {
                console.log('WebSocket connected');
            };
            
            ws.onmessage = function(event) {
                const message = JSON.parse(event.data);
                console.log('WebSocket message:', message);
                
                // Handle video frames
                if (message.type === 'video_frame') {
                    displayVideoFrame(message.device_id, message.frame_data);
                }
            };
            
            ws.onclose = function() {
                console.log('WebSocket disconnected');
                // Attempt to reconnect after 3 seconds
                setTimeout(connectWebSocket, 3000);
            };
            
            ws.onerror = function(error) {
                console.error('WebSocket error:', error);
            };
        }
        
        function displayVideoFrame(deviceId, frameData) {
            const canvas = document.getElementById(`canvas-${deviceId}`);
            if (!canvas) return;
            
            const ctx = canvas.getContext('2d');
            const img = new Image();
            
            img.onload = function() {
                // Calculate aspect ratio and resize canvas if needed
                const aspectRatio = img.width / img.height;
                const maxWidth = 480;
                const maxHeight = 800;
                
                let newWidth, newHeight;
                if (aspectRatio > maxWidth / maxHeight) {
                    newWidth = maxWidth;
                    newHeight = maxWidth / aspectRatio;
                } else {
                    newHeight = maxHeight;
                    newWidth = maxHeight * aspectRatio;
                }
                
                canvas.width = newWidth;
                canvas.height = newHeight;
                
                // Draw the image
                ctx.drawImage(img, 0, 0, newWidth, newHeight);
                
                // Update status
                const statusText = document.querySelector(`#video-${deviceId} .connecting`);
                if (statusText) {
                    statusText.textContent = 'Streaming...';
                    statusText.className = 'connected';
                }
            };
            
            img.src = 'data:image/png;base64,' + frameData;
        }
        
        // Initialize the application
        document.addEventListener('DOMContentLoaded', function() {
            loadDevices();
            connectWebSocket();
            
            // Refresh devices every 10 seconds
            setInterval(loadDevices, 10000);
        });
    </script>
</body>
</html>
        """
        return web.Response(text=html, content_type='text/html')
    
    async def get_devices(self, request):
        """API endpoint to get connected devices"""
        self.device_manager.refresh_devices()
        devices = self.device_manager.get_devices()
        return web.json_response(devices)
    
    async def start_device_stream(self, request):
        """API endpoint to start device streaming"""
        device_id = request.match_info['device_id']
        
        device = self.device_manager.get_device(device_id)
        if not device:
            return web.json_response(
                {'error': 'Device not found'}, 
                status=404
            )
        
        # Start screen streaming
        stream_result = self.screen_stream_server.start_screen_stream(device_id)
        
        if stream_result:
            return web.json_response(stream_result)
        else:
            return web.json_response(
                {'error': 'Failed to start streaming'}, 
                status=500
            )
    
    async def stop_device_stream(self, request):
        """API endpoint to stop device streaming"""
        device_id = request.match_info['device_id']
        
        # Stop both scrcpy and screen streaming
        scrcpy_stopped = self.scrcpy_manager.stop_streaming(device_id)
        screen_stopped = self.screen_stream_server.stop_screen_stream(device_id)
        
        if scrcpy_stopped or screen_stopped:
            return web.json_response({'status': 'stopped'})
        else:
            return web.json_response(
                {'error': 'Device not streaming'}, 
                status=404
            )
    
    async def get_device_status(self, request):
        """API endpoint to get device streaming status"""
        device_id = request.match_info['device_id']
        
        # Check both scrcpy and screen streaming status
        scrcpy_info = self.scrcpy_manager.get_streaming_info(device_id)
        screen_info = self.screen_stream_server.get_stream_info(device_id)
        
        if scrcpy_info or screen_info:
            return web.json_response({
                'scrcpy': scrcpy_info,
                'screen_stream': screen_info
            })
        else:
            return web.json_response(
                {'status': 'not_streaming'}, 
                status=404
            )
    
    async def websocket_handler(self, request):
        """WebSocket handler for WebRTC signaling and video streaming"""
        ws = web_ws.WebSocketResponse()
        await ws.prepare(request)
        
        client_id = f"client_{id(ws)}"
        await self.signaling_server.register_client(client_id, ws)
        
        current_device_id = None
        
        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        msg_type = data.get('type')
                        
                        if msg_type == 'join_stream':
                            device_id = data.get('device_id')
                            if device_id:
                                # Add client to video stream
                                self.screen_stream_server.add_client(device_id, ws)
                                current_device_id = device_id
                                logger.info(f"Client {client_id} joined video stream for device {device_id}")
                        
                        elif msg_type == 'leave_stream':
                            if current_device_id:
                                self.screen_stream_server.remove_client(current_device_id, ws)
                                current_device_id = None
                                logger.info(f"Client {client_id} left video stream")
                        
                        # Handle other signaling messages
                        await self.signaling_server.handle_message(client_id, data)
                        
                    except json.JSONDecodeError:
                        await self.signaling_server.send_error(client_id, "Invalid JSON")
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(f'WebSocket error: {ws.exception()}')
        except Exception as e:
            logger.error(f"WebSocket handler error: {e}")
        finally:
            # Clean up client connections
            if current_device_id:
                self.screen_stream_server.remove_client(current_device_id, ws)
            await self.signaling_server.unregister_client(client_id)
        
        return ws
    
    async def cleanup(self):
        """Cleanup resources before shutdown"""
        logger.info("Cleaning up resources...")
        
        # Stop all streaming processes
        for device_id in list(self.scrcpy_manager.processes.keys()):
            self.scrcpy_manager.stop_streaming(device_id)
        
        # Stop all screen streams
        for device_id in list(self.screen_stream_server.streams.keys()):
            self.screen_stream_server.stop_screen_stream(device_id)
        
        logger.info("Cleanup completed")
    
    async def run(self):
        """Run the Device Farm application"""
        # Setup signal handlers in the event loop
        if sys.platform != 'win32':
            loop = asyncio.get_running_loop()
            def signal_handler():
                logger.info("Received shutdown signal")
                self.shutdown_event.set()
            
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(sig, signal_handler)
        
        # Start the HTTP server
        runner = web.AppRunner(self.app)
        await runner.setup()
        
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        
        logger.info(f"Device Farm server started at http://{self.host}:{self.port}")
        logger.info("Press Ctrl+C to stop")
        
        try:
            # Wait for shutdown signal
            await self.shutdown_event.wait()
        finally:
            await self.cleanup()
            await runner.cleanup()

def main():
    """Main entry point"""
    app = DeviceFarmApp()
    
    try:
        asyncio.run(app.run())
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Application error: {e}")
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main())