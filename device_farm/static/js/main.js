/**
 * Main JavaScript for Device Farm Index Page
 */

class DeviceFarm {
    constructor() {
        this.socket = null;
        this.statusLog = document.getElementById('status-log');
        this.deviceGrid = document.getElementById('device-grid');
        
        this.initializeSocket();
        this.bindEvents();
        this.startPeriodicRefresh();
    }
    
    initializeSocket() {
        this.socket = io();
        
        this.socket.on('connect', () => {
            this.log('Connected to device farm server');
        });
        
        this.socket.on('disconnect', () => {
            this.log('Disconnected from server');
        });
        
        this.socket.on('status', (data) => {
            this.log(`Status: ${data.message}`);
        });
        
        this.socket.on('error', (data) => {
            this.log(`Error: ${data.message}`, 'error');
        });
    }
    
    bindEvents() {
        // Connect buttons
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('connect-btn')) {
                const deviceId = e.target.dataset.deviceId;
                this.connectDevice(deviceId, e.target);
            }
            
            if (e.target.classList.contains('view-btn')) {
                const deviceId = e.target.dataset.deviceId;
                this.viewDevice(deviceId);
            }
            
            if (e.target.id === 'refresh-btn') {
                this.refreshDevices();
            }
        });
    }
    
    async connectDevice(deviceId, button) {
        const originalText = button.textContent;
        button.textContent = 'Connecting...';
        button.disabled = true;
        
        this.log(`Connecting to device ${deviceId}...`);
        
        try {
            const response = await fetch(`/api/device/${deviceId}/connect`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            const result = await response.json();
            
            if (response.ok) {
                this.log(`Successfully connected to device ${deviceId}`);
                button.textContent = 'Connected';
                button.classList.remove('btn-primary');
                button.classList.add('btn-success');
                
                // Enable view button
                const viewBtn = document.querySelector(`.view-btn[data-device-id="${deviceId}"]`);
                if (viewBtn) {
                    viewBtn.disabled = false;
                }
                
                // Update device card status
                this.updateDeviceCardStatus(deviceId, 'connected');
                
            } else {
                throw new Error(result.error || 'Connection failed');
            }
            
        } catch (error) {
            this.log(`Failed to connect to device ${deviceId}: ${error.message}`, 'error');
            button.textContent = originalText;
            button.disabled = false;
        }
    }
    
    viewDevice(deviceId) {
        this.log(`Opening device control for ${deviceId}`);
        window.open(`/device/${deviceId}`, '_blank');
    }
    
    updateDeviceCardStatus(deviceId, status) {
        const deviceCard = document.querySelector(`[data-device-id="${deviceId}"]`);
        if (deviceCard) {
            const statusElement = deviceCard.querySelector('.device-status');
            if (statusElement) {
                statusElement.textContent = status;
                statusElement.className = `device-status status-${status}`;
            }
        }
    }
    
    async refreshDevices() {
        this.log('Refreshing device list...');
        
        try {
            const response = await fetch('/api/devices');
            const devices = await response.json();
            
            this.updateDeviceGrid(devices);
            this.log(`Found ${devices.length} device(s)`);
            
        } catch (error) {
            this.log(`Failed to refresh devices: ${error.message}`, 'error');
        }
    }
    
    updateDeviceGrid(devices) {
        if (devices.length === 0) {
            this.deviceGrid.innerHTML = `
                <div class="no-devices">
                    <p>No devices found. Make sure:</p>
                    <ul>
                        <li>Android devices are connected via ADB</li>
                        <li>USB debugging is enabled</li>
                        <li>Devices are authorized for debugging</li>
                    </ul>
                    <button id="refresh-btn" class="btn btn-primary">Refresh</button>
                </div>
            `;
            return;
        }
        
        const html = devices.map(device => `
            <div class="device-card" data-device-id="${device.id}">
                <div class="device-header">
                    <h3>${device.model}</h3>
                    <span class="device-status status-${device.status}">${device.status}</span>
                </div>
                <div class="device-info">
                    <p><strong>Name:</strong> ${device.name}</p>
                    <p><strong>Android:</strong> ${device.android_version}</p>
                    <p><strong>Resolution:</strong> ${device.resolution}</p>
                    ${device.battery >= 0 ? `<p><strong>Battery:</strong> ${device.battery}%</p>` : ''}
                </div>
                <div class="device-actions">
                    <button class="btn btn-primary connect-btn" data-device-id="${device.id}">
                        Connect
                    </button>
                    <button class="btn btn-secondary view-btn" data-device-id="${device.id}" disabled>
                        View Screen
                    </button>
                </div>
            </div>
        `).join('');
        
        this.deviceGrid.innerHTML = html;
    }
    
    startPeriodicRefresh() {
        // Refresh device list every 30 seconds
        setInterval(() => {
            this.refreshDevices();
        }, 30000);
    }
    
    log(message, type = 'info') {
        const timestamp = new Date().toLocaleTimeString();
        const logEntry = `[${timestamp}] ${message}\n`;
        
        this.statusLog.textContent += logEntry;
        this.statusLog.scrollTop = this.statusLog.scrollHeight;
        
        // Limit log size
        const lines = this.statusLog.textContent.split('\n');
        if (lines.length > 100) {
            this.statusLog.textContent = lines.slice(-100).join('\n');
        }
        
        // Also log to console
        if (type === 'error') {
            console.error(message);
        } else {
            console.log(message);
        }
    }
}