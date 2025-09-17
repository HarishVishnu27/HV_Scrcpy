#!/usr/bin/env python3
"""
Device Farm Application - Simple Web Server
Shows Android device screens directly in browser.
"""

import os
import sys
import time
import base64
import threading
import subprocess
import logging
import json
from io import BytesIO
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import webbrowser

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DeviceManager:
    """Manages Android device connections and screen capture"""
    
    def __init__(self):
        self.connected_devices = {}
        self.active_streams = {}
        
    def get_devices(self):
        """Get list of connected Android devices using ADB"""
        try:
            result = subprocess.run(['adb', 'devices'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                logger.error(f"ADB command failed: {result.stderr}")
                return []
            
            devices = []
            lines = result.stdout.strip().split('\n')[1:]  # Skip header
            for line in lines:
                if line.strip() and '\tdevice' in line:
                    device_id = line.split('\t')[0]
                    devices.append(device_id)
            
            return devices
        except subprocess.TimeoutExpired:
            logger.error("ADB command timed out")
            return []
        except FileNotFoundError:
            logger.error("ADB not found. Please install Android SDK platform tools.")
            return []
        except Exception as e:
            logger.error(f"Error getting devices: {e}")
            return []
    
    def capture_screenshot(self, device_id):
        """Capture a single screenshot from device"""
        try:
            result = subprocess.run([
                'adb', '-s', device_id, 'exec-out', 'screencap', '-p'
            ], capture_output=True, timeout=5)
            
            if result.returncode == 0 and result.stdout:
                return base64.b64encode(result.stdout).decode('utf-8')
            else:
                logger.warning(f"Screenshot failed for {device_id}: {result.stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            logger.warning(f"Screenshot timeout for device {device_id}")
            return None
        except Exception as e:
            logger.error(f"Screenshot error for device {device_id}: {e}")
            return None

# Global device manager instance
device_manager = DeviceManager()

class DeviceFarmHandler(BaseHTTPRequestHandler):
    """HTTP request handler for device farm web interface"""
    
    def do_GET(self):
        """Handle GET requests"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        if path == '/' or path == '/index.html':
            self.serve_index()
        elif path == '/device_control' or path == '/device_control.html':
            self.serve_device_control()
        elif path == '/api/devices':
            self.serve_devices_api()
        elif path.startswith('/api/screenshot/'):
            device_id = path.split('/')[-1]
            self.serve_screenshot_api(device_id)
        elif path.startswith('/static/'):
            self.serve_static_file(path)
        else:
            self.send_error(404)
    
    def do_POST(self):
        """Handle POST requests"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        if path.startswith('/api/connect/'):
            device_id = path.split('/')[-1]
            self.handle_connect(device_id)
        elif path.startswith('/api/disconnect/'):
            device_id = path.split('/')[-1]
            self.handle_disconnect(device_id)
        else:
            self.send_error(404)
    
    def serve_index(self):
        """Serve index page"""
        html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Device Farm - Android Screen Mirror</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #f8f9fa; }
        .hero { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
    </style>
</head>
<body>
    <div class="hero text-white py-5">
        <div class="container text-center">
            <h1 class="display-4">📱 Device Farm</h1>
            <p class="lead">Android Screen Mirror in Your Browser</p>
            <a href="/device_control" class="btn btn-light btn-lg mt-3">🚀 Start Device Control</a>
        </div>
    </div>
    <div class="container mt-5">
        <div class="row">
            <div class="col-md-6">
                <div class="card">
                    <div class="card-body">
                        <h5>🎯 Features</h5>
                        <ul>
                            <li>Real-time screen viewing</li>
                            <li>Web-based interface</li>
                            <li>Multiple device support</li>
                            <li>No app installation needed</li>
                        </ul>
                    </div>
                </div>
            </div>
            <div class="col-md-6">
                <div class="card">
                    <div class="card-body">
                        <h5>📋 Setup</h5>
                        <ol>
                            <li>Enable USB debugging on Android</li>
                            <li>Connect device via USB</li>
                            <li>Accept debugging authorization</li>
                            <li>Click "Start Device Control"</li>
                        </ol>
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>"""
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(html.encode())
    
    def serve_device_control(self):
        """Serve device control page"""
        html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Device Control - Android Screen Mirror</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #f8f9fa; }
        .device-screen {
            border: 2px solid #ddd;
            border-radius: 15px;
            background: #000;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 600px;
            position: relative;
            overflow: hidden;
        }
        .device-screen img {
            max-width: 100%;
            max-height: 100%;
            height: auto;
            width: auto;
            border-radius: 10px;
        }
        .no-device {
            color: #6c757d;
            text-align: center;
            padding: 2rem;
        }
        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }
        .status-connected { background-color: #28a745; }
        .status-disconnected { background-color: #dc3545; }
        .status-connecting { background-color: #ffc107; }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .spinning { animation: spin 1s linear infinite; }
    </style>
</head>
<body>
    <div class="container-fluid">
        <header class="bg-primary text-white p-3 mb-4">
            <div class="d-flex justify-content-between align-items-center">
                <div>
                    <h1 class="h3 mb-0">📱 Device Control</h1>
                    <p class="mb-0">Real-time Android screen mirroring</p>
                </div>
                <a href="/" class="btn btn-outline-light">← Back to Home</a>
            </div>
        </header>

        <div class="row">
            <div class="col-md-4">
                <div class="card mb-4">
                    <div class="card-header d-flex justify-content-between align-items-center">
                        <h5 class="mb-0">Device Selection</h5>
                        <button class="btn btn-sm btn-outline-primary" id="refreshDevices">
                            🔄 Refresh
                        </button>
                    </div>
                    <div class="card-body">
                        <div id="deviceList">
                            <div class="text-center text-muted">
                                <div class="spinner-border spinner-border-sm" role="status"></div>
                                <p class="mt-2">Scanning for devices...</p>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="card mb-4">
                    <div class="card-header"><h5 class="mb-0">Connection Status</h5></div>
                    <div class="card-body">
                        <div id="connectionStatus">
                            <span class="status-indicator status-disconnected"></span>
                            <span>Disconnected</span>
                        </div>
                        <div class="mt-3" id="deviceInfo" style="display: none;">
                            <strong>Device:</strong> <span id="currentDeviceId">-</span><br>
                            <strong>Status:</strong> <span id="currentStatus">-</span>
                        </div>
                    </div>
                </div>

                <div class="card">
                    <div class="card-header"><h5 class="mb-0">Controls</h5></div>
                    <div class="card-body">
                        <div class="d-grid gap-2">
                            <button class="btn btn-success" id="connectBtn" disabled>📱 Connect Device</button>
                            <button class="btn btn-danger" id="disconnectBtn" disabled>❌ Disconnect</button>
                            <button class="btn btn-info" id="screenshotBtn" disabled>📸 Take Screenshot</button>
                        </div>
                    </div>
                </div>
            </div>

            <div class="col-md-8">
                <div class="card">
                    <div class="card-header"><h5 class="mb-0">Device Screen</h5></div>
                    <div class="card-body p-2">
                        <div class="device-screen" id="deviceScreen">
                            <div class="no-device">
                                <h3>📱</h3>
                                <p>No device connected</p>
                                <small class="text-muted">Select and connect a device to view its screen here</small>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let selectedDevice = null;
        let isConnected = false;
        let pollInterval = null;
        
        const deviceList = document.getElementById('deviceList');
        const connectionStatus = document.getElementById('connectionStatus');
        const deviceInfo = document.getElementById('deviceInfo');
        const currentDeviceId = document.getElementById('currentDeviceId');
        const currentStatus = document.getElementById('currentStatus');
        const connectBtn = document.getElementById('connectBtn');
        const disconnectBtn = document.getElementById('disconnectBtn');
        const screenshotBtn = document.getElementById('screenshotBtn');
        const refreshBtn = document.getElementById('refreshDevices');
        const deviceScreen = document.getElementById('deviceScreen');
        
        function loadDevices() {
            refreshBtn.classList.add('spinning');
            fetch('/api/devices')
                .then(response => response.json())
                .then(data => displayDevices(data.devices))
                .catch(error => {
                    console.error('Error loading devices:', error);
                    deviceList.innerHTML = '<div class="alert alert-danger">Error loading devices</div>';
                })
                .finally(() => refreshBtn.classList.remove('spinning'));
        }
        
        function displayDevices(devices) {
            if (devices.length === 0) {
                deviceList.innerHTML = `
                    <div class="alert alert-warning">
                        <strong>No devices found</strong><br>
                        Make sure your Android device is:
                        <ul class="mb-0 mt-2">
                            <li>Connected via USB</li>
                            <li>USB debugging enabled</li>
                            <li>Authorized for debugging</li>
                        </ul>
                    </div>
                `;
                return;
            }
            
            let html = '<div class="list-group">';
            devices.forEach(device => {
                const isSelected = device === selectedDevice;
                html += `
                    <button class="list-group-item list-group-item-action ${isSelected ? 'active' : ''}" 
                            onclick="selectDevice('${device}')">
                        <div class="d-flex w-100 justify-content-between">
                            <h6 class="mb-1">📱 ${device}</h6>
                            ${isSelected ? '<span class="badge bg-primary">Selected</span>' : ''}
                        </div>
                        <small>Android Device</small>
                    </button>
                `;
            });
            html += '</div>';
            deviceList.innerHTML = html;
        }
        
        function selectDevice(deviceId) {
            selectedDevice = deviceId;
            loadDevices();
            connectBtn.disabled = false;
            connectBtn.textContent = `📱 Connect to ${deviceId}`;
        }
        
        function startPolling() {
            if (pollInterval) return;
            pollInterval = setInterval(() => {
                if (selectedDevice && isConnected) {
                    fetch(`/api/screenshot/${selectedDevice}`)
                        .then(response => response.json())
                        .then(data => {
                            if (data.success) {
                                updateDeviceScreen(data.image_data);
                            }
                        })
                        .catch(error => console.error('Screenshot error:', error));
                }
            }, 2000);
        }
        
        function stopPolling() {
            if (pollInterval) {
                clearInterval(pollInterval);
                pollInterval = null;
            }
        }
        
        connectBtn.addEventListener('click', function() {
            if (!selectedDevice) return;
            updateConnectionStatus('connecting', 'Connecting...');
            
            fetch(`/api/connect/${selectedDevice}`, { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        isConnected = true;
                        updateConnectionStatus('connected', 'Connected');
                        connectBtn.disabled = true;
                        disconnectBtn.disabled = false;
                        screenshotBtn.disabled = false;
                        deviceInfo.style.display = 'block';
                        currentDeviceId.textContent = selectedDevice;
                        currentStatus.textContent = 'Active';
                        startPolling();
                    } else {
                        updateConnectionStatus('disconnected', 'Connection failed');
                    }
                })
                .catch(error => {
                    console.error('Connection error:', error);
                    updateConnectionStatus('disconnected', 'Connection error');
                });
        });
        
        disconnectBtn.addEventListener('click', function() {
            if (!selectedDevice) return;
            
            fetch(`/api/disconnect/${selectedDevice}`, { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    isConnected = false;
                    updateConnectionStatus('disconnected', 'Disconnected');
                    connectBtn.disabled = false;
                    disconnectBtn.disabled = true;
                    screenshotBtn.disabled = true;
                    deviceInfo.style.display = 'none';
                    stopPolling();
                    deviceScreen.innerHTML = `
                        <div class="no-device">
                            <h3>📱</h3>
                            <p>Device disconnected</p>
                            <small class="text-muted">Select and connect a device to view its screen here</small>
                        </div>
                    `;
                });
        });
        
        screenshotBtn.addEventListener('click', function() {
            if (!selectedDevice) return;
            
            screenshotBtn.disabled = true;
            screenshotBtn.textContent = '📸 Taking...';
            
            fetch(`/api/screenshot/${selectedDevice}`)
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        updateDeviceScreen(data.image_data);
                    } else {
                        alert('Failed to take screenshot: ' + data.error);
                    }
                })
                .catch(error => {
                    console.error('Screenshot error:', error);
                    alert('Screenshot failed');
                })
                .finally(() => {
                    screenshotBtn.disabled = false;
                    screenshotBtn.textContent = '📸 Take Screenshot';
                });
        });
        
        refreshBtn.addEventListener('click', loadDevices);
        
        function updateConnectionStatus(status, message) {
            const indicator = connectionStatus.querySelector('.status-indicator');
            const text = connectionStatus.querySelector('span:last-child');
            indicator.className = `status-indicator status-${status}`;
            text.textContent = message;
        }
        
        function updateDeviceScreen(imageData) {
            deviceScreen.innerHTML = `<img src="${imageData}" alt="Device Screen" />`;
        }
        
        // Initial load
        document.addEventListener('DOMContentLoaded', loadDevices);
    </script>
</body>
</html>"""
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(html.encode())
    
    def serve_devices_api(self):
        """Serve devices API"""
        devices = device_manager.get_devices()
        response = {'devices': devices}
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())
    
    def serve_screenshot_api(self, device_id):
        """Serve screenshot API"""
        img_data = device_manager.capture_screenshot(device_id)
        if img_data:
            response = {
                'success': True,
                'image_data': f"data:image/png;base64,{img_data}"
            }
        else:
            response = {'success': False, 'error': 'Failed to capture screenshot'}
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())
    
    def handle_connect(self, device_id):
        """Handle device connection"""
        success = True  # Simple connection - just mark as connected
        response = {'success': success, 'device_id': device_id}
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())
    
    def handle_disconnect(self, device_id):
        """Handle device disconnection"""
        response = {'success': True, 'device_id': device_id}
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())
    
    def serve_static_file(self, path):
        """Serve static files (placeholder)"""
        self.send_error(404)
    
    def log_message(self, format, *args):
        """Override to reduce logging noise"""
        return

def check_adb():
    """Check if ADB is available"""
    try:
        result = subprocess.run(['adb', 'version'], capture_output=True, check=True)
        logger.info("ADB is available")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.warning("ADB not found")
        return False

def main():
    """Main function"""
    if not check_adb():
        print("Warning: ADB not found. Device detection may not work.")
        print("Install with: sudo apt install android-tools-adb")
    
    port = 5000
    server = HTTPServer(('0.0.0.0', port), DeviceFarmHandler)
    
    logger.info(f"Starting Device Farm server on port {port}")
    print(f"🚀 Device Farm server running at http://localhost:{port}")
    print("📱 Open the URL in your browser to view connected Android devices")
    print("Press Ctrl+C to stop the server")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        server.shutdown()

if __name__ == '__main__':
    main()