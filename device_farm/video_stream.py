#!/usr/bin/env python3
"""
Device Screen Streaming Server

This module handles capturing device screens and streaming them via WebSocket
"""

import asyncio
import json
import logging
import subprocess
import threading
import time
from typing import Dict, Optional
import base64
import os
import tempfile

logger = logging.getLogger(__name__)

class ScreenStreamServer:
    """Manages screen streaming from Android devices"""
    
    def __init__(self):
        self.streams: Dict[str, Dict] = {}  # device_id -> stream_info
        self.capture_tasks: Dict[str, asyncio.Task] = {}
        self.clients: Dict[str, set] = {}  # device_id -> set of websocket clients
    
    def start_screen_stream(self, device_id: str) -> Optional[Dict]:
        """Start screen streaming for a device using ADB screenshots"""
        if device_id in self.streams:
            logger.warning(f"Screen stream for device {device_id} already exists")
            return self.streams[device_id]
        
        try:
            stream_info = {
                'device_id': device_id,
                'status': 'starting',
                'started_at': time.time(),
                'frame_count': 0
            }
            
            self.streams[device_id] = stream_info
            self.clients[device_id] = set()
            
            # Start capturing screenshots in a background task
            task = asyncio.create_task(self._capture_screenshots(device_id))
            self.capture_tasks[device_id] = task
            
            return stream_info
            
        except Exception as e:
            logger.error(f"Failed to start screen stream for device {device_id}: {e}")
            return None
    
    def stop_screen_stream(self, device_id: str) -> bool:
        """Stop screen streaming for a device"""
        if device_id not in self.streams:
            return False
        
        # Cancel capture task
        if device_id in self.capture_tasks:
            task = self.capture_tasks[device_id]
            task.cancel()
            del self.capture_tasks[device_id]
        
        # Clean up clients and stream info
        if device_id in self.clients:
            del self.clients[device_id]
        
        del self.streams[device_id]
        
        logger.info(f"Stopped screen stream for device {device_id}")
        return True
    
    def add_client(self, device_id: str, websocket):
        """Add a WebSocket client to receive frames for a device"""
        if device_id in self.clients:
            self.clients[device_id].add(websocket)
    
    def remove_client(self, device_id: str, websocket):
        """Remove a WebSocket client"""
        if device_id in self.clients:
            self.clients[device_id].discard(websocket)
    
    def get_stream_info(self, device_id: str) -> Optional[Dict]:
        """Get stream information for a device"""
        return self.streams.get(device_id)
    
    async def _capture_screenshots(self, device_id: str):
        """Capture screenshots from device and broadcast to clients"""
        frame_interval = 1.0 / 10  # 10 FPS
        
        while device_id in self.streams:
            try:
                # Capture screenshot using ADB
                screenshot_data = await self._capture_screenshot(device_id)
                
                if screenshot_data:
                    # Update stream info
                    self.streams[device_id]['status'] = 'running'
                    self.streams[device_id]['frame_count'] += 1
                    
                    # Broadcast to all connected clients
                    await self._broadcast_frame(device_id, screenshot_data)
                else:
                    logger.warning(f"Failed to capture screenshot for device {device_id}")
                
                # Wait for next frame
                await asyncio.sleep(frame_interval)
                
            except asyncio.CancelledError:
                logger.info(f"Screenshot capture cancelled for device {device_id}")
                break
            except Exception as e:
                logger.error(f"Error capturing screenshot for device {device_id}: {e}")
                await asyncio.sleep(1)  # Wait before retry
        
        # Mark stream as stopped
        if device_id in self.streams:
            self.streams[device_id]['status'] = 'stopped'
    
    async def _capture_screenshot(self, device_id: str) -> Optional[str]:
        """Capture a screenshot from the device and return as base64"""
        try:
            # Use ADB to capture screenshot
            process = await asyncio.create_subprocess_exec(
                'adb', '-s', device_id, 'exec-out', 'screencap', '-p',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0 and stdout:
                # Convert to base64
                screenshot_b64 = base64.b64encode(stdout).decode('utf-8')
                return screenshot_b64
            else:
                logger.error(f"ADB screenshot failed for device {device_id}: {stderr.decode() if stderr else 'Unknown error'}")
                return None
                
        except Exception as e:
            logger.error(f"Exception capturing screenshot for device {device_id}: {e}")
            return None
    
    async def _broadcast_frame(self, device_id: str, screenshot_data: str):
        """Broadcast a frame to all connected clients"""
        if device_id not in self.clients:
            return
        
        message = {
            'type': 'video_frame',
            'device_id': device_id,
            'frame_data': screenshot_data,
            'timestamp': time.time()
        }
        
        # Send to all connected clients
        disconnected_clients = set()
        
        for websocket in self.clients[device_id].copy():
            try:
                # Use the correct method for aiohttp WebSocket
                if hasattr(websocket, 'send_str'):
                    await websocket.send_str(json.dumps(message))
                else:
                    await websocket.send(json.dumps(message))
            except Exception as e:
                logger.warning(f"Failed to send frame to client: {e}")
                disconnected_clients.add(websocket)
        
        # Remove disconnected clients
        for websocket in disconnected_clients:
            self.clients[device_id].discard(websocket)