#!/usr/bin/env python3
"""
Demo Device Server

Creates mock devices for testing the Device Farm application when no real devices are available.
"""

import asyncio
import json
import logging
import base64
import io
import random
from PIL import Image, ImageDraw, ImageFont
import time

logger = logging.getLogger(__name__)

class MockDeviceManager:
    """Creates mock Android devices for testing"""
    
    def __init__(self):
        self.mock_devices = [
            {'id': 'mock_device_001', 'status': 'device', 'streaming': False},
            {'id': 'mock_device_002', 'status': 'device', 'streaming': False},
        ]
    
    def get_devices(self):
        """Return mock devices"""
        return self.mock_devices
    
    def get_device(self, device_id):
        """Get specific mock device"""
        for device in self.mock_devices:
            if device['id'] == device_id:
                return device
        return None

class MockScreenStreamServer:
    """Mock screen streaming for testing without real devices"""
    
    def __init__(self):
        self.streams = {}
        self.capture_tasks = {}
        self.clients = {}
    
    def start_screen_stream(self, device_id):
        """Start mock screen streaming"""
        if device_id in self.streams:
            return self.streams[device_id]
        
        stream_info = {
            'device_id': device_id,
            'status': 'starting',
            'started_at': time.time(),
            'frame_count': 0
        }
        
        self.streams[device_id] = stream_info
        self.clients[device_id] = set()
        
        # Start mock capture task
        task = asyncio.create_task(self._generate_mock_frames(device_id))
        self.capture_tasks[device_id] = task
        
        return stream_info
    
    def stop_screen_stream(self, device_id):
        """Stop mock screen streaming"""
        if device_id not in self.streams:
            return False
        
        if device_id in self.capture_tasks:
            task = self.capture_tasks[device_id]
            task.cancel()
            del self.capture_tasks[device_id]
        
        if device_id in self.clients:
            del self.clients[device_id]
        
        del self.streams[device_id]
        return True
    
    def add_client(self, device_id, websocket):
        """Add client to mock stream"""
        if device_id in self.clients:
            self.clients[device_id].add(websocket)
    
    def remove_client(self, device_id, websocket):
        """Remove client from mock stream"""
        if device_id in self.clients:
            self.clients[device_id].discard(websocket)
    
    def get_stream_info(self, device_id):
        """Get mock stream info"""
        return self.streams.get(device_id)
    
    async def _generate_mock_frames(self, device_id):
        """Generate mock Android-like frames"""
        frame_interval = 1.0 / 5  # 5 FPS for demo
        
        while device_id in self.streams:
            try:
                # Generate mock screenshot
                screenshot_data = self._generate_mock_screenshot(device_id)
                
                if screenshot_data:
                    # Update stream info
                    self.streams[device_id]['status'] = 'running'
                    self.streams[device_id]['frame_count'] += 1
                    
                    # Broadcast to clients
                    await self._broadcast_frame(device_id, screenshot_data)
                
                await asyncio.sleep(frame_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error generating mock frame for {device_id}: {e}")
                await asyncio.sleep(1)
        
        if device_id in self.streams:
            self.streams[device_id]['status'] = 'stopped'
    
    def _generate_mock_screenshot(self, device_id):
        """Generate a mock Android screenshot"""
        try:
            # Create a mock Android-like screen
            width, height = 360, 640
            img = Image.new('RGB', (width, height), color='white')
            draw = ImageDraw.Draw(img)
            
            # Draw status bar
            draw.rectangle([(0, 0), (width, 50)], fill='#2196F3')
            
            # Add some text
            try:
                font = ImageFont.load_default()
            except:
                font = None
            
            current_time = time.strftime("%H:%M:%S")
            draw.text((10, 60), f"Mock Device: {device_id}", fill='black', font=font)
            draw.text((10, 80), f"Time: {current_time}", fill='black', font=font)
            draw.text((10, 100), f"Frame: {self.streams[device_id]['frame_count']}", fill='black', font=font)
            
            # Add some random colored rectangles to simulate app content
            for i in range(3):
                x1 = random.randint(10, width-100)
                y1 = random.randint(120, height-100)
                x2 = x1 + random.randint(50, 100)
                y2 = y1 + random.randint(30, 80)
                color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
                draw.rectangle([(x1, y1), (x2, y2)], fill=color)
            
            # Convert to base64
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            img_bytes = buffer.getvalue()
            return base64.b64encode(img_bytes).decode('utf-8')
            
        except Exception as e:
            logger.error(f"Error generating mock screenshot: {e}")
            return None
    
    async def _broadcast_frame(self, device_id, screenshot_data):
        """Broadcast mock frame to clients"""
        if device_id not in self.clients:
            return
        
        message = {
            'type': 'video_frame',
            'device_id': device_id,
            'frame_data': screenshot_data,
            'timestamp': time.time()
        }
        
        disconnected_clients = set()
        
        for websocket in self.clients[device_id].copy():
            try:
                # Use the correct method for aiohttp WebSocket
                if hasattr(websocket, 'send_str'):
                    await websocket.send_str(json.dumps(message))
                else:
                    await websocket.send(json.dumps(message))
            except Exception as e:
                disconnected_clients.add(websocket)
        
        for websocket in disconnected_clients:
            self.clients[device_id].discard(websocket)