#!/usr/bin/env python3
"""
Device Farm Web Application
Provides web-based device control with embedded scrcpy streaming
"""

import os
import sys
import asyncio
import subprocess
import threading
import time
import json
from datetime import datetime
from typing import Dict, List, Optional
import warnings

from flask import Flask, render_template, request, jsonify, Response
from flask_socketio import SocketIO, emit, disconnect
import eventlet
import requests

# Fix for Python 3.13 compatibility
warnings.filterwarnings('ignore', category=DeprecationWarning)

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from device_manager import DeviceManager
from webrtc_streamer import WebRTCStreamer
from scrcpy_bridge import ScrcpyBridge

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Global instances
device_manager = DeviceManager()
webrtc_streamer = WebRTCStreamer()
scrcpy_bridge = ScrcpyBridge()

# Store active device connections
active_connections: Dict[str, dict] = {}

@app.route('/')
def index():
    """Main page showing available devices"""
    devices = device_manager.get_available_devices()
    return render_template('index.html', devices=devices)

@app.route('/device/<device_id>')
def device_control(device_id):
    """Device control page with embedded streaming"""
    device_info = device_manager.get_device_info(device_id)
    if not device_info:
        return "Device not found", 404
    
    return render_template('device_control.html', 
                         device_id=device_id, 
                         device_info=device_info)

@app.route('/api/devices')
def api_devices():
    """API endpoint to get available devices"""
    devices = device_manager.get_available_devices()
    return jsonify(devices)

@app.route('/api/device/<device_id>/connect', methods=['POST'])
def api_connect_device(device_id):
    """Connect to a device and start streaming"""
    try:
        if device_id in active_connections:
            return jsonify({'error': 'Device already connected'}), 400
        
        # Start scrcpy for this device
        scrcpy_process = scrcpy_bridge.start_device_streaming(device_id)
        if not scrcpy_process:
            return jsonify({'error': 'Failed to start device streaming'}), 500
        
        # Initialize WebRTC for this device
        webrtc_conn = webrtc_streamer.create_connection(device_id)
        
        active_connections[device_id] = {
            'scrcpy_process': scrcpy_process,
            'webrtc_connection': webrtc_conn,
            'connected_at': datetime.now().isoformat(),
            'status': 'connected'
        }
        
        return jsonify({'status': 'connected', 'device_id': device_id})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/device/<device_id>/disconnect', methods=['POST'])
def api_disconnect_device(device_id):
    """Disconnect from a device"""
    try:
        if device_id not in active_connections:
            return jsonify({'error': 'Device not connected'}), 400
        
        conn = active_connections[device_id]
        
        # Stop scrcpy process
        if 'scrcpy_process' in conn:
            scrcpy_bridge.stop_device_streaming(device_id, conn['scrcpy_process'])
        
        # Close WebRTC connection
        if 'webrtc_connection' in conn:
            webrtc_streamer.close_connection(device_id)
        
        del active_connections[device_id]
        
        return jsonify({'status': 'disconnected', 'device_id': device_id})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connection"""
    print(f"Client connected: {request.sid}")
    emit('status', {'message': 'Connected to device farm'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection"""
    print(f"Client disconnected: {request.sid}")

@socketio.on('join_device')
def handle_join_device(data):
    """Join a device room for real-time communication"""
    device_id = data.get('device_id')
    if device_id and device_id in active_connections:
        # Join the device-specific room
        from flask_socketio import join_room
        join_room(f"device_{device_id}")
        emit('joined_device', {'device_id': device_id})
    else:
        emit('error', {'message': 'Device not found or not connected'})

@socketio.on('device_input')
def handle_device_input(data):
    """Handle input events for device control"""
    device_id = data.get('device_id')
    if device_id not in active_connections:
        emit('error', {'message': 'Device not connected'})
        return
    
    input_type = data.get('type')
    
    if input_type == 'touch':
        scrcpy_bridge.send_touch_event(device_id, data)
    elif input_type == 'key':
        scrcpy_bridge.send_key_event(device_id, data)
    elif input_type == 'scroll':
        scrcpy_bridge.send_scroll_event(device_id, data)

@socketio.on('webrtc_offer')
def handle_webrtc_offer(data):
    """Handle WebRTC offer for video streaming"""
    device_id = data.get('device_id')
    offer = data.get('offer')
    
    if device_id in active_connections:
        # Process WebRTC offer and send answer
        answer = webrtc_streamer.handle_offer(device_id, offer)
        emit('webrtc_answer', {
            'device_id': device_id,
            'answer': answer
        })

@socketio.on('webrtc_ice_candidate')
def handle_ice_candidate(data):
    """Handle WebRTC ICE candidates"""
    device_id = data.get('device_id')
    candidate = data.get('candidate')
    
    if device_id in active_connections:
        webrtc_streamer.add_ice_candidate(device_id, candidate)

def cleanup_on_exit():
    """Cleanup function to stop all active connections"""
    for device_id in list(active_connections.keys()):
        conn = active_connections[device_id]
        if 'scrcpy_process' in conn:
            scrcpy_bridge.stop_device_streaming(device_id, conn['scrcpy_process'])
        if 'webrtc_connection' in conn:
            webrtc_streamer.close_connection(device_id)

if __name__ == '__main__':
    import atexit
    atexit.register(cleanup_on_exit)
    
    print("Starting Device Farm Web Application...")
    print("Access the application at: http://localhost:5000")
    
    # Run with eventlet for WebSocket support
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)