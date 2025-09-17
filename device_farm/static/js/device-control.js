/**
 * Device Control JavaScript
 * Handles WebRTC streaming, input events, and device control
 */

class DeviceControl {
    constructor(deviceId, deviceInfo) {
        this.deviceId = deviceId;
        this.deviceInfo = deviceInfo;
        this.socket = null;
        this.peerConnection = null;
        this.isConnected = false;
        this.videoElement = document.getElementById('device-video');
        this.videoOverlay = document.getElementById('video-overlay');
        this.touchCanvas = document.getElementById('touch-canvas');
        this.connectionLog = document.getElementById('connection-log');
        this.connectionStatus = document.getElementById('connection-status');
        
        this.initializeSocket();
        this.initializeWebRTC();
        this.bindEvents();
        this.connectToDevice();
        
        this.log(`Initializing control for device: ${deviceId}`);
    }
    
    initializeSocket() {
        this.socket = io();
        
        this.socket.on('connect', () => {
            this.log('Connected to server');
            this.socket.emit('join_device', { device_id: this.deviceId });
        });
        
        this.socket.on('disconnect', () => {
            this.log('Disconnected from server');
            this.updateConnectionStatus('disconnected');
        });
        
        this.socket.on('joined_device', (data) => {
            this.log(`Joined device room: ${data.device_id}`);
        });
        
        this.socket.on('webrtc_answer', (data) => {
            if (data.device_id === this.deviceId) {
                this.handleWebRTCAnswer(data.answer);
            }
        });
        
        this.socket.on('error', (data) => {
            this.log(`Error: ${data.message}`, 'error');
        });
    }
    
    async initializeWebRTC() {
        try {
            this.peerConnection = new RTCPeerConnection({
                iceServers: [
                    { urls: 'stun:stun.l.google.com:19302' },
                    { urls: 'stun:stun1.l.google.com:19302' }
                ]
            });
            
            this.peerConnection.onicecandidate = (event) => {
                if (event.candidate) {
                    this.socket.emit('webrtc_ice_candidate', {
                        device_id: this.deviceId,
                        candidate: event.candidate
                    });
                }
            };
            
            this.peerConnection.ontrack = (event) => {
                this.log('Received video stream');
                this.videoElement.srcObject = event.streams[0];
                this.hideVideoOverlay();
                this.updateConnectionStatus('connected');
                this.enableTouchCanvas();
            };
            
            this.peerConnection.onconnectionstatechange = () => {
                this.log(`WebRTC connection state: ${this.peerConnection.connectionState}`);
                
                switch (this.peerConnection.connectionState) {
                    case 'connected':
                        this.isConnected = true;
                        this.updateConnectionStatus('connected');
                        break;
                    case 'disconnected':
                    case 'failed':
                    case 'closed':
                        this.isConnected = false;
                        this.updateConnectionStatus('disconnected');
                        break;
                    case 'connecting':
                        this.updateConnectionStatus('connecting');
                        break;
                }
            };
            
        } catch (error) {
            this.log(`WebRTC initialization error: ${error.message}`, 'error');
        }
    }
    
    async connectToDevice() {
        try {
            this.updateConnectionStatus('connecting');
            this.log('Creating WebRTC offer...');
            
            const offer = await this.peerConnection.createOffer();
            await this.peerConnection.setLocalDescription(offer);
            
            this.socket.emit('webrtc_offer', {
                device_id: this.deviceId,
                offer: {
                    sdp: offer.sdp,
                    type: offer.type
                }
            });
            
        } catch (error) {
            this.log(`Connection error: ${error.message}`, 'error');
            this.updateConnectionStatus('disconnected');
        }
    }
    
    async handleWebRTCAnswer(answer) {
        try {
            await this.peerConnection.setRemoteDescription(answer);
            this.log('WebRTC answer processed');
        } catch (error) {
            this.log(`WebRTC answer error: ${error.message}`, 'error');
        }
    }
    
    bindEvents() {
        // Disconnect button
        document.getElementById('disconnect-btn').addEventListener('click', () => {
            this.disconnectDevice();
        });
        
        // Video controls
        document.getElementById('fullscreen-btn').addEventListener('click', () => {
            this.toggleFullscreen();
        });
        
        document.getElementById('screenshot-btn').addEventListener('click', () => {
            this.takeScreenshot();
        });
        
        // Device control buttons
        document.getElementById('home-btn').addEventListener('click', () => {
            this.sendKeyEvent('home');
        });
        
        document.getElementById('back-btn').addEventListener('click', () => {
            this.sendKeyEvent('back');
        });
        
        document.getElementById('menu-btn').addEventListener('click', () => {
            this.sendKeyEvent('menu');
        });
        
        // Quick action buttons
        document.querySelectorAll('.action-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const action = btn.dataset.action;
                this.sendQuickAction(action);
            });
        });
        
        // Text input
        document.getElementById('send-text-btn').addEventListener('click', () => {
            this.sendTextInput();
        });
        
        document.getElementById('text-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.sendTextInput();
            }
        });
        
        // Touch events on video
        this.bindTouchEvents();
        
        // Keyboard events
        document.addEventListener('keydown', (e) => {
            if (e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {
                this.handleKeyboardEvent(e);
            }
        });
    }
    
    bindTouchEvents() {
        const canvas = this.touchCanvas;
        const video = this.videoElement;
        
        let isTouch = false;
        let lastTouch = null;
        
        const getCoordinates = (e) => {
            const rect = video.getBoundingClientRect();
            const scaleX = this.deviceInfo.resolution.split('x')[0] / rect.width;
            const scaleY = this.deviceInfo.resolution.split('x')[1] / rect.height;
            
            const clientX = e.clientX || (e.touches && e.touches[0].clientX);
            const clientY = e.clientY || (e.touches && e.touches[0].clientY);
            
            const x = Math.round((clientX - rect.left) * scaleX);
            const y = Math.round((clientY - rect.top) * scaleY);
            
            return { x, y };
        };
        
        const showTouchIndicator = (x, y) => {
            const indicator = document.createElement('div');
            indicator.className = 'touch-indicator';
            indicator.style.left = x + 'px';
            indicator.style.top = y + 'px';
            indicator.style.width = '30px';
            indicator.style.height = '30px';
            indicator.style.marginLeft = '-15px';
            indicator.style.marginTop = '-15px';
            
            video.parentElement.appendChild(indicator);
            
            setTimeout(() => {
                indicator.remove();
            }, 600);
        };
        
        // Mouse events
        canvas.addEventListener('mousedown', (e) => {
            e.preventDefault();
            isTouch = true;
            const coords = getCoordinates(e);
            this.sendTouchEvent('down', coords.x, coords.y);
            showTouchIndicator(e.offsetX, e.offsetY);
        });
        
        canvas.addEventListener('mousemove', (e) => {
            if (isTouch) {
                e.preventDefault();
                const coords = getCoordinates(e);
                this.sendTouchEvent('move', coords.x, coords.y);
            }
        });
        
        canvas.addEventListener('mouseup', (e) => {
            if (isTouch) {
                e.preventDefault();
                isTouch = false;
                const coords = getCoordinates(e);
                this.sendTouchEvent('up', coords.x, coords.y);
            }
        });
        
        // Touch events for mobile
        canvas.addEventListener('touchstart', (e) => {
            e.preventDefault();
            isTouch = true;
            const coords = getCoordinates(e);
            this.sendTouchEvent('down', coords.x, coords.y);
            lastTouch = coords;
        });
        
        canvas.addEventListener('touchmove', (e) => {
            e.preventDefault();
            const coords = getCoordinates(e);
            this.sendTouchEvent('move', coords.x, coords.y);
            lastTouch = coords;
        });
        
        canvas.addEventListener('touchend', (e) => {
            e.preventDefault();
            if (lastTouch) {
                this.sendTouchEvent('up', lastTouch.x, lastTouch.y);
            }
            isTouch = false;
            lastTouch = null;
        });
        
        // Scroll events
        canvas.addEventListener('wheel', (e) => {
            e.preventDefault();
            const coords = getCoordinates(e);
            this.sendScrollEvent(coords.x, coords.y, e.deltaX, e.deltaY);
        });
    }
    
    enableTouchCanvas() {
        this.touchCanvas.style.display = 'block';
        const rect = this.videoElement.getBoundingClientRect();
        this.touchCanvas.width = rect.width;
        this.touchCanvas.height = rect.height;
    }
    
    sendTouchEvent(action, x, y, pointerId = 0) {
        if (!this.isConnected) return;
        
        this.socket.emit('device_input', {
            device_id: this.deviceId,
            type: 'touch',
            action: action,
            x: x,
            y: y,
            pointer_id: pointerId,
            pressure: 1.0
        });
    }
    
    sendKeyEvent(key) {
        if (!this.isConnected) return;
        
        const keyMap = {
            'home': 3,
            'back': 4,
            'menu': 82,
            'power': 26,
            'volume_up': 24,
            'volume_down': 25,
            'recent': 187
        };
        
        const keycode = keyMap[key];
        if (keycode) {
            this.socket.emit('device_input', {
                device_id: this.deviceId,
                type: 'key',
                action: 'down',
                keycode: keycode,
                meta_state: 0
            });
            
            setTimeout(() => {
                this.socket.emit('device_input', {
                    device_id: this.deviceId,
                    type: 'key',
                    action: 'up',
                    keycode: keycode,
                    meta_state: 0
                });
            }, 50);
        }
    }
    
    sendScrollEvent(x, y, hScroll, vScroll) {
        if (!this.isConnected) return;
        
        this.socket.emit('device_input', {
            device_id: this.deviceId,
            type: 'scroll',
            x: x,
            y: y,
            h_scroll: hScroll / 100,
            v_scroll: vScroll / 100
        });
    }
    
    sendQuickAction(action) {
        this.sendKeyEvent(action);
        this.log(`Quick action: ${action}`);
    }
    
    sendTextInput() {
        const textInput = document.getElementById('text-input');
        const text = textInput.value.trim();
        
        if (text && this.isConnected) {
            // Send text via socket (will be implemented in bridge)
            this.socket.emit('device_input', {
                device_id: this.deviceId,
                type: 'text',
                text: text
            });
            
            this.log(`Sent text: ${text}`);
            textInput.value = '';
        }
    }
    
    handleKeyboardEvent(e) {
        if (!this.isConnected) return;
        
        // Map common keys
        const keyMap = {
            'Escape': 'back',
            'Enter': 66,
            'Space': 62,
            'ArrowUp': 19,
            'ArrowDown': 20,
            'ArrowLeft': 21,
            'ArrowRight': 22
        };
        
        const mapped = keyMap[e.key];
        if (mapped) {
            e.preventDefault();
            if (typeof mapped === 'string') {
                this.sendKeyEvent(mapped);
            } else {
                this.socket.emit('device_input', {
                    device_id: this.deviceId,
                    type: 'key',
                    action: 'down',
                    keycode: mapped,
                    meta_state: 0
                });
                
                setTimeout(() => {
                    this.socket.emit('device_input', {
                        device_id: this.deviceId,
                        type: 'key',
                        action: 'up',
                        keycode: mapped,
                        meta_state: 0
                    });
                }, 50);
            }
        }
    }
    
    toggleFullscreen() {
        const wrapper = document.querySelector('.video-wrapper');
        
        if (!document.fullscreenElement) {
            wrapper.requestFullscreen().then(() => {
                wrapper.classList.add('fullscreen');
            });
        } else {
            document.exitFullscreen().then(() => {
                wrapper.classList.remove('fullscreen');
            });
        }
    }
    
    takeScreenshot() {
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        
        canvas.width = this.videoElement.videoWidth;
        canvas.height = this.videoElement.videoHeight;
        
        ctx.drawImage(this.videoElement, 0, 0);
        
        canvas.toBlob((blob) => {
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `screenshot_${this.deviceId}_${Date.now()}.png`;
            a.click();
            URL.revokeObjectURL(url);
        });
        
        this.log('Screenshot captured');
    }
    
    async disconnectDevice() {
        try {
            const response = await fetch(`/api/device/${this.deviceId}/disconnect`, {
                method: 'POST'
            });
            
            if (response.ok) {
                this.log('Device disconnected');
                window.location.href = '/';
            }
        } catch (error) {
            this.log(`Disconnect error: ${error.message}`, 'error');
        }
    }
    
    hideVideoOverlay() {
        this.videoOverlay.classList.add('hidden');
    }
    
    updateConnectionStatus(status) {
        this.connectionStatus.textContent = status;
        this.connectionStatus.className = `status-${status}`;
        
        // Add WebRTC status indicator
        let indicator = document.querySelector('.webrtc-status');
        if (!indicator) {
            indicator = document.createElement('div');
            indicator.className = 'webrtc-status';
            this.videoElement.parentElement.appendChild(indicator);
        }
        
        indicator.textContent = status.toUpperCase();
        indicator.className = `webrtc-status ${status}`;
    }
    
    log(message, type = 'info') {
        const timestamp = new Date().toLocaleTimeString();
        const logEntry = `[${timestamp}] ${message}\n`;
        
        this.connectionLog.textContent += logEntry;
        this.connectionLog.scrollTop = this.connectionLog.scrollHeight;
        
        // Limit log size
        const lines = this.connectionLog.textContent.split('\n');
        if (lines.length > 50) {
            this.connectionLog.textContent = lines.slice(-50).join('\n');
        }
        
        console.log(message);
    }
}