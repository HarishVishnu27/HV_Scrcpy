"""
Device Manager Module
Handles device discovery and management
"""

import subprocess
import re
import json
from typing import List, Dict, Optional

class DeviceManager:
    """Manages Android device connections and information"""
    
    def __init__(self):
        self.devices_cache = {}
        self.cache_timeout = 5  # seconds
        self.last_update = 0
    
    def get_available_devices(self) -> List[Dict]:
        """Get list of available Android devices"""
        import time
        current_time = time.time()
        
        # Use cache if it's still valid
        if current_time - self.last_update < self.cache_timeout:
            return list(self.devices_cache.values())
        
        devices = []
        try:
            # Use adb to list devices
            result = subprocess.run(['adb', 'devices', '-l'], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                devices = self._parse_adb_devices(result.stdout)
                
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError) as e:
            print(f"Error getting devices: {e}")
            # Return demo devices if ADB is not available (for testing)
            devices = self._get_demo_devices()
            
        # Update cache
        self.devices_cache = {device['id']: device for device in devices}
        self.last_update = current_time
        
        return devices
    
    def _get_demo_devices(self) -> List[Dict]:
        """Return demo devices for testing when ADB is not available"""
        return [
            {
                'id': 'demo_device_1',
                'status': 'device',
                'name': 'Demo Phone',
                'model': 'Samsung Galaxy S21',
                'android_version': '12',
                'resolution': '1080x2400',
                'battery': 85
            },
            {
                'id': 'demo_device_2', 
                'status': 'device',
                'name': 'Demo Tablet',
                'model': 'Google Pixel Tablet',
                'android_version': '13',
                'resolution': '2560x1600',
                'battery': 72
            }
        ]
    
    def _parse_adb_devices(self, adb_output: str) -> List[Dict]:
        """Parse adb devices output"""
        devices = []
        lines = adb_output.strip().split('\n')[1:]  # Skip header
        
        for line in lines:
            line = line.strip()
            if not line or 'offline' in line:
                continue
                
            parts = line.split()
            if len(parts) < 2:
                continue
                
            device_id = parts[0]
            status = parts[1]
            
            if status != 'device':
                continue
            
            # Extract additional info if available
            device_info = {
                'id': device_id,
                'status': status,
                'name': self._get_device_name(device_id),
                'model': self._get_device_model(device_id),
                'android_version': self._get_android_version(device_id),
                'resolution': self._get_device_resolution(device_id),
                'battery': self._get_battery_level(device_id)
            }
            
            devices.append(device_info)
        
        return devices
    
    def _get_device_name(self, device_id: str) -> str:
        """Get device name"""
        try:
            result = subprocess.run(['adb', '-s', device_id, 'shell', 'getprop', 'ro.product.name'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass
        return "Unknown Device"
    
    def _get_device_model(self, device_id: str) -> str:
        """Get device model"""
        try:
            result = subprocess.run(['adb', '-s', device_id, 'shell', 'getprop', 'ro.product.model'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass
        return "Unknown Model"
    
    def _get_android_version(self, device_id: str) -> str:
        """Get Android version"""
        try:
            result = subprocess.run(['adb', '-s', device_id, 'shell', 'getprop', 'ro.build.version.release'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass
        return "Unknown"
    
    def _get_device_resolution(self, device_id: str) -> str:
        """Get device screen resolution"""
        try:
            result = subprocess.run(['adb', '-s', device_id, 'shell', 'wm', 'size'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                # Parse "Physical size: 1080x1920"
                match = re.search(r'(\d+)x(\d+)', result.stdout)
                if match:
                    return f"{match.group(1)}x{match.group(2)}"
        except:
            pass
        return "Unknown"
    
    def _get_battery_level(self, device_id: str) -> int:
        """Get battery level"""
        try:
            result = subprocess.run(['adb', '-s', device_id, 'shell', 'dumpsys', 'battery', '|', 'grep', 'level'], 
                                  capture_output=True, text=True, timeout=5, shell=True)
            if result.returncode == 0:
                # Parse "level: 85"
                match = re.search(r'level:\s*(\d+)', result.stdout)
                if match:
                    return int(match.group(1))
        except:
            pass
        return -1
    
    def get_device_info(self, device_id: str) -> Optional[Dict]:
        """Get detailed info for a specific device"""
        devices = self.get_available_devices()
        for device in devices:
            if device['id'] == device_id:
                return device
        return None
    
    def is_device_available(self, device_id: str) -> bool:
        """Check if device is available and connected"""
        devices = self.get_available_devices()
        return any(device['id'] == device_id and device['status'] == 'device' 
                  for device in devices)
    
    def get_device_capabilities(self, device_id: str) -> Dict:
        """Get device capabilities for streaming"""
        capabilities = {
            'video_encoding': [],
            'audio_encoding': [],
            'max_resolution': None,
            'supports_control': True
        }
        
        try:
            # Check video encoding capabilities
            result = subprocess.run(['adb', '-s', device_id, 'shell', 'dumpsys', 'media.codec'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                if 'h264' in result.stdout.lower():
                    capabilities['video_encoding'].append('H264')
                if 'h265' in result.stdout.lower() or 'hevc' in result.stdout.lower():
                    capabilities['video_encoding'].append('H265')
                if 'vp8' in result.stdout.lower():
                    capabilities['video_encoding'].append('VP8')
                if 'vp9' in result.stdout.lower():
                    capabilities['video_encoding'].append('VP9')
            
        except:
            # Default to basic H264 support
            capabilities['video_encoding'] = ['H264']
        
        return capabilities