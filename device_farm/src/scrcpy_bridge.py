"""
Scrcpy Bridge Module
Handles communication with scrcpy processes and input events
"""

import subprocess
import os
import signal
import socket
import struct
import threading
import time
from typing import Dict, Optional, Any
import json

class ScrcpyBridge:
    """Bridge between web interface and scrcpy processes"""
    
    def __init__(self):
        self.processes: Dict[str, subprocess.Popen] = {}
        self.control_sockets: Dict[str, socket.socket] = {}
        self.base_port = 27183  # Default scrcpy port
        self.port_offset = 0
    
    def start_device_streaming(self, device_id: str) -> Optional[subprocess.Popen]:
        """Start scrcpy process for device streaming"""
        try:
            if device_id in self.processes:
                self._stop_existing_process(device_id)
            
            # Check if this is a demo device
            if device_id.startswith('demo_device'):
                print(f"Demo mode: simulating scrcpy for device {device_id}")
                # Create a mock process for demo mode
                process = type('MockProcess', (), {
                    'pid': 12345,
                    'poll': lambda: None,  # Return None to indicate still running
                    'communicate': lambda: (b'demo output', b''),
                    'terminate': lambda: None,
                    'wait': lambda timeout=None: 0,
                    'kill': lambda: None
                })()
                
                self.processes[device_id] = process
                return process
            
            # Allocate ports for this device
            video_port = self.base_port + (self.port_offset * 2)
            control_port = self.base_port + (self.port_offset * 2) + 1
            self.port_offset += 1
            
            # Start scrcpy process
            cmd = [
                'scrcpy',
                '--serial', device_id,
                '--no-display',  # Don't show window
                '--port', str(video_port),
                '--max-fps', '30',
                '--bit-rate', '2M',
                '--video-encoder', 'h264',
                '--no-audio',  # Disable audio for now
                '--stay-awake',
                '--turn-screen-on'
            ]
            
            print(f"Starting scrcpy for device {device_id} with command: {' '.join(cmd)}")
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid
            )
            
            # Wait a moment for process to start
            time.sleep(2)
            
            # Check if process is still running
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                print(f"Scrcpy failed to start for {device_id}:")
                print(f"stdout: {stdout.decode()}")
                print(f"stderr: {stderr.decode()}")
                return None
            
            self.processes[device_id] = process
            
            # Try to establish control connection
            self._setup_control_connection(device_id, control_port)
            
            return process
            
        except Exception as e:
            print(f"Error starting scrcpy for device {device_id}: {e}")
            return None
    
    def _setup_control_connection(self, device_id: str, control_port: int):
        """Set up control socket connection"""
        try:
            # Create socket for control communication
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            
            # Connect to scrcpy control port
            sock.connect(('localhost', control_port))
            
            self.control_sockets[device_id] = sock
            print(f"Control connection established for device {device_id}")
            
        except Exception as e:
            print(f"Failed to establish control connection for {device_id}: {e}")
    
    def _stop_existing_process(self, device_id: str):
        """Stop existing scrcpy process for device"""
        if device_id in self.processes:
            process = self.processes[device_id]
            try:
                # Terminate the process group
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                process.wait(timeout=5)
            except (subprocess.TimeoutExpired, ProcessLookupError):
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                except ProcessLookupError:
                    pass
            del self.processes[device_id]
        
        # Close control socket
        if device_id in self.control_sockets:
            self.control_sockets[device_id].close()
            del self.control_sockets[device_id]
    
    def stop_device_streaming(self, device_id: str, process: subprocess.Popen):
        """Stop scrcpy streaming for device"""
        try:
            self._stop_existing_process(device_id)
            print(f"Stopped scrcpy streaming for device {device_id}")
        except Exception as e:
            print(f"Error stopping scrcpy for device {device_id}: {e}")
    
    def send_touch_event(self, device_id: str, event_data: Dict[str, Any]):
        """Send touch event to device"""
        try:
            sock = self.control_sockets.get(device_id)
            if not sock:
                print(f"No control socket for device {device_id}")
                return
            
            # Parse touch event data
            action = event_data.get('action', 'down')  # down, up, move
            x = int(event_data.get('x', 0))
            y = int(event_data.get('y', 0))
            pointer_id = event_data.get('pointer_id', 0)
            pressure = float(event_data.get('pressure', 1.0))
            
            # Convert to scrcpy control message format
            # Message type for touch event is 2
            msg_type = 2
            
            # Action mapping
            action_map = {
                'down': 0,
                'up': 1,
                'move': 2
            }
            action_code = action_map.get(action, 0)
            
            # Pack the message (simplified format)
            # This is a basic implementation - real scrcpy protocol is more complex
            message = struct.pack('>BBIIFFB',
                                msg_type,       # Message type (1 byte)
                                action_code,    # Action (1 byte)
                                pointer_id,     # Pointer ID (4 bytes)
                                x,              # X coordinate (4 bytes)
                                y,              # Y coordinate (4 bytes)  
                                pressure,       # Pressure (4 bytes)
                                0               # Buttons (1 byte)
                                )
            
            sock.send(message)
            
        except Exception as e:
            print(f"Error sending touch event to device {device_id}: {e}")
    
    def send_key_event(self, device_id: str, event_data: Dict[str, Any]):
        """Send key event to device"""
        try:
            sock = self.control_sockets.get(device_id)
            if not sock:
                print(f"No control socket for device {device_id}")
                return
            
            # Parse key event data
            action = event_data.get('action', 'down')  # down, up
            keycode = int(event_data.get('keycode', 0))
            meta_state = int(event_data.get('meta_state', 0))
            
            # Message type for key event is 0
            msg_type = 0
            
            # Action mapping
            action_map = {
                'down': 0,
                'up': 1
            }
            action_code = action_map.get(action, 0)
            
            # Pack the message
            message = struct.pack('>BBIII',
                                msg_type,       # Message type (1 byte)
                                action_code,    # Action (1 byte)
                                keycode,        # Keycode (4 bytes)
                                0,              # Repeat (4 bytes)
                                meta_state      # Meta state (4 bytes)
                                )
            
            sock.send(message)
            
        except Exception as e:
            print(f"Error sending key event to device {device_id}: {e}")
    
    def send_scroll_event(self, device_id: str, event_data: Dict[str, Any]):
        """Send scroll event to device"""
        try:
            sock = self.control_sockets.get(device_id)
            if not sock:
                print(f"No control socket for device {device_id}")
                return
            
            # Parse scroll event data
            x = int(event_data.get('x', 0))
            y = int(event_data.get('y', 0))
            h_scroll = float(event_data.get('h_scroll', 0))
            v_scroll = float(event_data.get('v_scroll', 0))
            
            # Message type for scroll event is 3
            msg_type = 3
            
            # Pack the message
            message = struct.pack('>BIIFF',
                                msg_type,       # Message type (1 byte)
                                x,              # X coordinate (4 bytes)
                                y,              # Y coordinate (4 bytes)
                                h_scroll,       # Horizontal scroll (4 bytes)
                                v_scroll        # Vertical scroll (4 bytes)
                                )
            
            sock.send(message)
            
        except Exception as e:
            print(f"Error sending scroll event to device {device_id}: {e}")
    
    def send_text_input(self, device_id: str, text: str):
        """Send text input to device"""
        try:
            sock = self.control_sockets.get(device_id)
            if not sock:
                print(f"No control socket for device {device_id}")
                return
            
            # Message type for text input is 1
            msg_type = 1
            
            # Encode text as UTF-8
            text_bytes = text.encode('utf-8')
            text_length = len(text_bytes)
            
            # Pack the message
            message = struct.pack('>BI', msg_type, text_length) + text_bytes
            
            sock.send(message)
            
        except Exception as e:
            print(f"Error sending text input to device {device_id}: {e}")
    
    def get_device_screen_size(self, device_id: str) -> tuple:
        """Get device screen dimensions"""
        try:
            result = subprocess.run([
                'adb', '-s', device_id, 'shell', 'wm', 'size'
            ], capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                # Parse "Physical size: 1080x1920"
                import re
                match = re.search(r'(\d+)x(\d+)', result.stdout)
                if match:
                    return (int(match.group(1)), int(match.group(2)))
        except:
            pass
        
        return (1080, 1920)  # Default resolution
    
    def cleanup_all(self):
        """Clean up all processes and connections"""
        for device_id in list(self.processes.keys()):
            self._stop_existing_process(device_id)