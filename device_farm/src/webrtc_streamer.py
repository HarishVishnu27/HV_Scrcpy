"""
WebRTC Streamer Module
Handles WebRTC connections for device video streaming
"""

import asyncio
import json
import threading
import time
import subprocess
import os
import tempfile
from typing import Dict, Optional, Any
import logging

try:
    from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack, RTCConfiguration, RTCIceServer
    from aiortc.contrib.media import MediaPlayer
    import cv2
    import numpy as np
except ImportError as e:
    print(f"Warning: aiortc not available: {e}")
    print("WebRTC functionality will be limited")

class DeviceVideoTrack(VideoStreamTrack):
    """Custom video track that reads from device stream"""
    
    def __init__(self, device_id: str):
        super().__init__()
        self.device_id = device_id
        self.frame_queue = asyncio.Queue(maxsize=10)
        self.is_running = True
        
    async def recv(self):
        """Receive video frame"""
        try:
            frame = await asyncio.wait_for(self.frame_queue.get(), timeout=1.0)
            return frame
        except asyncio.TimeoutError:
            # Return a black frame if no frame is available
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            from av import VideoFrame
            return VideoFrame.from_ndarray(frame, format="bgr24")
    
    def add_frame(self, frame):
        """Add frame to queue (non-blocking)"""
        try:
            if not self.frame_queue.full():
                self.frame_queue.put_nowait(frame)
        except:
            pass
    
    def stop(self):
        """Stop the video track"""
        self.is_running = False

class WebRTCStreamer:
    """Manages WebRTC connections for device streaming"""
    
    def __init__(self):
        self.connections: Dict[str, RTCPeerConnection] = {}
        self.video_tracks: Dict[str, DeviceVideoTrack] = {}
        self.stream_processes: Dict[str, subprocess.Popen] = {}
        self.loop = None
        self.thread = None
        self._start_event_loop()
    
    def _start_event_loop(self):
        """Start asyncio event loop in separate thread"""
        def run_loop():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_forever()
        
        self.thread = threading.Thread(target=run_loop, daemon=True)
        self.thread.start()
        
        # Wait for loop to be ready
        while self.loop is None:
            time.sleep(0.1)
    
    def create_connection(self, device_id: str) -> bool:
        """Create WebRTC connection for device"""
        if not self.loop:
            return False
        
        return asyncio.run_coroutine_threadsafe(
            self._create_connection_async(device_id), 
            self.loop
        ).result()
    
    async def _create_connection_async(self, device_id: str) -> bool:
        """Create WebRTC connection asynchronously"""
        try:
            # Create ICE configuration
            config = RTCConfiguration(
                iceServers=[
                    RTCIceServer(urls=["stun:stun.l.google.com:19302"]),
                    RTCIceServer(urls=["stun:stun1.l.google.com:19302"])
                ]
            )
            
            # Create peer connection
            pc = RTCPeerConnection(configuration=config)
            self.connections[device_id] = pc
            
            # Create video track
            video_track = DeviceVideoTrack(device_id)
            self.video_tracks[device_id] = video_track
            
            # Add video track to peer connection
            pc.addTrack(video_track)
            
            # Set up event handlers
            @pc.on("connectionstatechange")
            async def on_connectionstatechange():
                print(f"Connection state for {device_id}: {pc.connectionState}")
                if pc.connectionState == "closed":
                    await self._cleanup_connection(device_id)
            
            # Start video capture for this device
            await self._start_video_capture(device_id)
            
            return True
            
        except Exception as e:
            print(f"Error creating WebRTC connection for {device_id}: {e}")
            return False
    
    async def _start_video_capture(self, device_id: str):
        """Start video capture from device using scrcpy"""
        try:
            # Handle demo mode
            if device_id.startswith('demo_device'):
                print(f"Demo mode: simulating video capture for {device_id}")
                await self._create_demo_video_stream(device_id)
                return
            
            # Create named pipe for video stream
            pipe_name = f"/tmp/scrcpy_video_{device_id}"
            if os.path.exists(pipe_name):
                os.remove(pipe_name)
            os.mkfifo(pipe_name)
            
            # Start scrcpy with video output to pipe
            cmd = [
                'scrcpy',
                '--serial', device_id,
                '--no-display',
                '--no-control',
                '--video-encoder', 'h264',
                '--max-fps', '30',
                '--bit-rate', '2M',
                '--record', pipe_name
            ]
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid
            )
            
            self.stream_processes[device_id] = process
            
            # Start reading frames from pipe
            task = asyncio.create_task(self._read_video_frames(device_id, pipe_name))
            # Store task reference to prevent it from being garbage collected
            if not hasattr(self, 'tasks'):
                self.tasks = []
            self.tasks.append(task)
            
        except Exception as e:
            print(f"Error starting video capture for {device_id}: {e}")
    
    async def _create_demo_video_stream(self, device_id: str):
        """Create a demo video stream with generated content"""
        try:
            import cv2
            import numpy as np
            from av import VideoFrame
            
            video_track = self.video_tracks.get(device_id)
            if not video_track:
                return
            
            # Generate demo frames
            frame_count = 0
            while video_track.is_running and device_id in self.connections:
                # Create a simple animated frame
                frame = np.zeros((720, 480, 3), dtype=np.uint8)
                
                # Add a moving circle
                center_x = int(240 + 200 * np.sin(frame_count * 0.1))
                center_y = int(360 + 200 * np.cos(frame_count * 0.1))
                cv2.circle(frame, (center_x, center_y), 50, (0, 255, 0), -1)
                
                # Add text
                cv2.putText(frame, f"Demo Device: {device_id}", (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                cv2.putText(frame, f"Frame: {frame_count}", (10, 60), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                cv2.putText(frame, "This is a demo stream", (10, 650), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
                
                # Convert frame to VideoFrame
                video_frame = VideoFrame.from_ndarray(frame, format="bgr24")
                video_frame.pts = int(time.time() * 1000000)  # timestamp in microseconds
                video_frame.time_base = 1000000
                
                # Add frame to track
                video_track.add_frame(video_frame)
                
                frame_count += 1
                await asyncio.sleep(0.033)  # ~30 FPS
                
        except Exception as e:
            print(f"Error creating demo video stream for {device_id}: {e}")
    
    async def _read_video_frames(self, device_id: str, pipe_name: str):
        """Read video frames from pipe and feed to WebRTC"""
        try:
            import cv2
            from av import VideoFrame
            
            # Wait for pipe to be ready
            await asyncio.sleep(2)
            
            # Open video stream
            cap = cv2.VideoCapture(pipe_name)
            if not cap.isOpened():
                print(f"Failed to open video stream for {device_id}")
                return
            
            video_track = self.video_tracks.get(device_id)
            if not video_track:
                return
            
            while video_track.is_running and device_id in self.connections:
                ret, frame = cap.read()
                if not ret:
                    await asyncio.sleep(0.033)  # ~30 FPS
                    continue
                
                # Convert frame to VideoFrame
                video_frame = VideoFrame.from_ndarray(frame, format="bgr24")
                video_frame.pts = int(time.time() * 1000000)  # timestamp in microseconds
                video_frame.time_base = 1000000
                
                # Add frame to track
                video_track.add_frame(video_frame)
                
                await asyncio.sleep(0.033)  # ~30 FPS
            
            cap.release()
            
        except Exception as e:
            print(f"Error reading video frames for {device_id}: {e}")
        finally:
            # Clean up pipe
            if os.path.exists(pipe_name):
                os.remove(pipe_name)
    
    def handle_offer(self, device_id: str, offer: dict) -> Optional[dict]:
        """Handle WebRTC offer and return answer"""
        if not self.loop:
            return None
        
        return asyncio.run_coroutine_threadsafe(
            self._handle_offer_async(device_id, offer),
            self.loop
        ).result()
    
    async def _handle_offer_async(self, device_id: str, offer: dict) -> Optional[dict]:
        """Handle WebRTC offer asynchronously"""
        try:
            pc = self.connections.get(device_id)
            if not pc:
                return None
            
            # Set remote description
            await pc.setRemoteDescription(RTCSessionDescription(
                sdp=offer["sdp"],
                type=offer["type"]
            ))
            
            # Create answer
            answer = await pc.createAnswer()
            await pc.setLocalDescription(answer)
            
            return {
                "sdp": pc.localDescription.sdp,
                "type": pc.localDescription.type
            }
            
        except Exception as e:
            print(f"Error handling offer for {device_id}: {e}")
            return None
    
    def add_ice_candidate(self, device_id: str, candidate: dict):
        """Add ICE candidate"""
        if not self.loop:
            return
        
        asyncio.run_coroutine_threadsafe(
            self._add_ice_candidate_async(device_id, candidate),
            self.loop
        )
    
    async def _add_ice_candidate_async(self, device_id: str, candidate: dict):
        """Add ICE candidate asynchronously"""
        try:
            pc = self.connections.get(device_id)
            if pc and candidate:
                from aiortc import RTCIceCandidate
                ice_candidate = RTCIceCandidate(
                    component=candidate.get("component"),
                    foundation=candidate.get("foundation"),
                    ip=candidate.get("ip"),
                    port=candidate.get("port"),
                    priority=candidate.get("priority"),
                    protocol=candidate.get("protocol"),
                    type=candidate.get("type")
                )
                await pc.addIceCandidate(ice_candidate)
                
        except Exception as e:
            print(f"Error adding ICE candidate for {device_id}: {e}")
    
    def close_connection(self, device_id: str):
        """Close WebRTC connection"""
        if not self.loop:
            return
        
        asyncio.run_coroutine_threadsafe(
            self._cleanup_connection(device_id),
            self.loop
        )
    
    async def _cleanup_connection(self, device_id: str):
        """Clean up connection resources"""
        try:
            # Stop video track
            video_track = self.video_tracks.get(device_id)
            if video_track:
                video_track.stop()
                del self.video_tracks[device_id]
            
            # Close peer connection
            pc = self.connections.get(device_id)
            if pc:
                await pc.close()
                del self.connections[device_id]
            
            # Stop stream process
            process = self.stream_processes.get(device_id)
            if process:
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                del self.stream_processes[device_id]
                
        except Exception as e:
            print(f"Error cleaning up connection for {device_id}: {e}")
    
    def cleanup_all(self):
        """Clean up all connections"""
        for device_id in list(self.connections.keys()):
            self.close_connection(device_id)
        
        if self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)