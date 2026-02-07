/**
 * MedTracker Frontend JavaScript
 * Handles UI interactions and API communication
 */

class MedTracker {
    constructor() {
        this.baseUrl = window.location.origin;
        this.medicationId = 'daily_pill';
        this.authToken = this.getStoredToken();
        this.isOnline = navigator.onLine;

        this.init();
    }

    init() {
        this.setupEventListeners();
        this.setupOfflineHandler();
        this.setupServiceWorker();
        this.loadInitialData();
        this.startPeriodicUpdates();
    }

    setupEventListeners() {
        // Page visibility API to refresh when app becomes visible
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) {
                this.loadInitialData();
            }
        });

        // Online/offline events
        window.addEventListener('online', () => {
            this.isOnline = true;
            this.hideOfflineIndicator();
            this.loadInitialData();
        });

        window.addEventListener('offline', () => {
            this.isOnline = false;
            this.showOfflineIndicator();
        });
    }

    setupOfflineHandler() {
        const indicator = document.getElementById('offline-indicator');
        if (!this.isOnline) {
            indicator.classList.add('show');
        }
    }

    showOfflineIndicator() {
        document.getElementById('offline-indicator').classList.add('show');
    }

    hideOfflineIndicator() {
        document.getElementById('offline-indicator').classList.remove('show');
    }

    async setupServiceWorker() {
        if ('serviceWorker' in navigator) {
            try {
                const registration = await navigator.serviceWorker.register('/static/sw.js');
                console.log('Service Worker registered:', registration);

                // Request notification permissions
                await this.requestNotificationPermission();
            } catch (error) {
                console.error('Service Worker registration failed:', error);
            }
        }
    }

    async requestNotificationPermission() {
        if ('Notification' in window && 'serviceWorker' in navigator) {
            const permission = await Notification.requestPermission();
            if (permission === 'granted') {
                await this.subscribeToNotifications();
            }
        }
    }

    async subscribeToNotifications() {
        try {
            const registration = await navigator.serviceWorker.ready;
            const pushManager = registration.pushManager;

            const subscription = await pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: this.urlBase64ToUint8Array('your-vapid-public-key-here')
            });

            // Send subscription to server
            await this.apiCall('/subscribe', {
                method: 'POST',
                body: JSON.stringify(subscription)
            });

            console.log('Push notification subscription successful');
        } catch (error) {
            console.error('Failed to subscribe to push notifications:', error);
        }
    }

    urlBase64ToUint8Array(base64String) {
        const padding = '='.repeat((4 - base64String.length % 4) % 4);
        const base64 = (base64String + padding).replace(/\-/g, '+').replace(/_/g, '/');
        const rawData = window.atob(base64);
        return new Uint8Array([...rawData].map((char) => char.charCodeAt(0)));
    }

    getStoredToken() {
        // In a real implementation, this would come from server setup
        // For demo, extract from current page or localStorage
        const urlParams = new URLSearchParams(window.location.search);
        const token = urlParams.get('token') || localStorage.getItem('medtracker_token');

        if (token) {
            localStorage.setItem('medtracker_token', token);
        }

        return token || 'demo_token';
    }

    async apiCall(endpoint, options = {}) {
        const defaultOptions = {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json'
            }
        };

        const finalOptions = { ...defaultOptions, ...options };

        try {
            const response = await fetch(`${this.baseUrl}${endpoint}`, finalOptions);
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'API request failed');
            }

            return data;
        } catch (error) {
            if (!this.isOnline) {
                // Return cached data or default values when offline
                return this.getOfflineData(endpoint);
            }
            throw error;
        }
    }

    getOfflineData(endpoint) {
        // Simple offline fallback - in production you'd use IndexedDB
        const cached = localStorage.getItem(`cache_${endpoint}`);
        if (cached) {
            return JSON.parse(cached);
        }

        // Default offline response
        return {
            success: false,
            error: 'Offline - no cached data available'
        };
    }

    async loadInitialData() {
        try {
            await Promise.all([
                this.updateStatus(),
                this.updateRecentActivity()
            ]);
        } catch (error) {
            console.error('Failed to load initial data:', error);
            this.showError('Failed to load medication data');
        }
    }

    async updateStatus() {
        try {
            const response = await this.apiCall(`/status?med_id=${this.medicationId}`);

            if (response.success) {
                this.renderStatus(response);

                // Cache the response for offline use
                localStorage.setItem('cache_/status', JSON.stringify(response));
            }
        } catch (error) {
            console.error('Failed to update status:', error);
        }
    }

    renderStatus(data) {
        const indicator = document.getElementById('status-indicator');
        const title = document.getElementById('status-title');
        const subtitle = document.getElementById('status-subtitle');
        const lastTaken = document.getElementById('last-taken');

        // Determine status
        const takenToday = data.today_taken > 0;
        const medication = data.medication || {};

        if (takenToday) {
            indicator.className = 'status-indicator taken';
            indicator.innerHTML = '<i class="bi bi-check-circle"></i>';
            title.textContent = 'Medication Taken';
            subtitle.textContent = `${medication.name || 'Daily Medication'} - ${medication.dosage || '1 pill'}`;

            if (data.today_logs && data.today_logs.length > 0) {
                const lastLog = data.today_logs[0];
                const time = new Date(lastLog.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                lastTaken.textContent = `Last taken at ${time}`;
            }
        } else {
            indicator.className = 'status-indicator missed';
            indicator.innerHTML = '<i class="bi bi-exclamation-circle"></i>';
            title.textContent = 'Medication Due';
            subtitle.textContent = `${medication.name || 'Daily Medication'} - ${medication.dosage || '1 pill'}`;
            lastTaken.textContent = 'Not taken today';
        }

        // Update stock information
        this.updateStockInfo(data);
    }

    updateStockInfo(data) {
        const medication = data.medication || { current_stock: 0, low_stock_threshold: 7 };
        const currentStock = medication.current_stock || 0;
        const threshold = medication.low_stock_threshold || 7;
        const maxStock = 30; // Assume typical bottle size

        // Update progress bar
        const progress = document.querySelector('#stock-progress .progress-bar');
        const percentage = Math.max(0, (currentStock / maxStock) * 100);
        progress.style.width = `${percentage}%`;

        // Color coding
        if (currentStock <= threshold) {
            progress.className = 'progress-bar bg-danger';
        } else if (currentStock <= threshold * 2) {
            progress.className = 'progress-bar bg-warning';
        } else {
            progress.className = 'progress-bar bg-success';
        }

        // Update text
        document.getElementById('stock-current').textContent = `${currentStock} pills remaining`;
        document.getElementById('stock-days').textContent = `~${currentStock} days left`;

        // Show/hide low stock alert
        const alert = document.getElementById('low-stock-alert');
        if (data.low_stock) {
            alert.classList.remove('d-none');
        } else {
            alert.classList.add('d-none');
        }
    }

    async updateRecentActivity() {
        try {
            const response = await this.apiCall(`/history?med_id=${this.medicationId}&days=7`);

            if (response.success) {
                this.renderRecentActivity(response.history);
            }
        } catch (error) {
            console.error('Failed to update recent activity:', error);
        }
    }

    renderRecentActivity(history) {
        const container = document.getElementById('recent-activity');

        if (!history || history.length === 0) {
            container.innerHTML = '<div class="text-center text-muted">No recent activity</div>';
            return;
        }

        const items = history.slice(0, 5).map(entry => {
            const date = new Date(entry.date).toLocaleDateString();
            const icon = entry.doses_taken > 0 ?
                '<i class="bi bi-check-circle text-success"></i>' :
                '<i class="bi bi-x-circle text-danger"></i>';

            return `
                <div class="list-group-item">
                    <div class="d-flex align-items-center">
                        ${icon}
                        <div class="ms-2 flex-grow-1">
                            <div class="fw-bold">${date}</div>
                            <small class="text-muted">
                                ${entry.doses_taken > 0 ?
                    `Taken ${entry.doses_taken} time${entry.doses_taken > 1 ? 's' : ''}` :
                    'Not taken'}
                            </small>
                        </div>
                        ${entry.times ? `<small class="text-muted">${entry.times.split(',')[0]}</small>` : ''}
                    </div>
                </div>
            `;
        }).join('');

        container.innerHTML = items;
    }

    async manualTrack() {
        try {
            const response = await this.apiCall(`/track?med_id=${this.medicationId}&token=${this.authToken}&notes=manual_entry`, {
                method: 'POST'
            });

            if (response.success) {
                this.showSuccess('Medication logged successfully!');
                await this.loadInitialData(); // Refresh the display
            } else {
                this.showError(response.error || 'Failed to log medication');
            }
        } catch (error) {
            console.error('Manual tracking failed:', error);
            this.showError('Failed to log medication - check your connection');
        }
    }

    async showSettings() {
        try {
            const response = await this.apiCall(`/settings?med_id=${this.medicationId}`);

            if (response.success && response.medication) {
                const med = response.medication;
                document.getElementById('med-name').value = med.name || '';
                document.getElementById('med-dosage').value = med.dosage || '';
                document.getElementById('med-time').value = med.schedule_time || '09:00';
                document.getElementById('med-stock').value = med.current_stock || 30;
                document.getElementById('med-threshold').value = med.low_stock_threshold || 7;
                document.getElementById('notifications-enabled').checked = med.reminder_enabled !== false;
            }

            const modal = new bootstrap.Modal(document.getElementById('settingsModal'));
            modal.show();
        } catch (error) {
            console.error('Failed to load settings:', error);
            this.showError('Failed to load settings');
        }
    }

    async saveSettings() {
        try {
            const settings = {
                medication_id: this.medicationId,
                name: document.getElementById('med-name').value,
                dosage: document.getElementById('med-dosage').value,
                schedule_time: document.getElementById('med-time').value,
                current_stock: parseInt(document.getElementById('med-stock').value),
                low_stock_threshold: parseInt(document.getElementById('med-threshold').value),
                reminder_enabled: document.getElementById('notifications-enabled').checked
            };

            const response = await this.apiCall('/settings', {
                method: 'POST',
                body: JSON.stringify(settings)
            });

            if (response.success) {
                this.showSuccess('Settings saved successfully!');
                bootstrap.Modal.getInstance(document.getElementById('settingsModal')).hide();
                await this.loadInitialData(); // Refresh display
            } else {
                this.showError(response.error || 'Failed to save settings');
            }
        } catch (error) {
            console.error('Failed to save settings:', error);
            this.showError('Failed to save settings');
        }
    }

    async showHistory() {
        const modal = new bootstrap.Modal(document.getElementById('historyModal'));
        modal.show();

        try {
            const response = await this.apiCall(`/history?med_id=${this.medicationId}&days=30`);

            if (response.success) {
                this.renderHistory(response.history);
            } else {
                document.getElementById('history-content').innerHTML =
                    '<div class="text-center text-danger">Failed to load history</div>';
            }
        } catch (error) {
            console.error('Failed to load history:', error);
            document.getElementById('history-content').innerHTML =
                '<div class="text-center text-danger">Failed to load history</div>';
        }
    }

    renderHistory(history) {
        const container = document.getElementById('history-content');

        if (!history || history.length === 0) {
            container.innerHTML = '<div class="text-center text-muted">No history available</div>';
            return;
        }

        // Create calendar-like view
        const rows = history.map(entry => {
            const date = new Date(entry.date);
            const status = entry.doses_taken > 0 ? 'success' : 'danger';
            const icon = entry.doses_taken > 0 ? 'check-circle' : 'x-circle';

            return `
                <tr>
                    <td>${date.toLocaleDateString()}</td>
                    <td>
                        <span class="badge bg-${status}">
                            <i class="bi bi-${icon}"></i>
                            ${entry.doses_taken > 0 ? 'Taken' : 'Missed'}
                        </span>
                    </td>
                    <td>${entry.doses_taken || 0}</td>
                    <td><small class="text-muted">${entry.times || 'N/A'}</small></td>
                </tr>
            `;
        }).join('');

        container.innerHTML = `
            <div class="table-responsive">
                <table class="table table-sm">
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Status</th>
                            <th>Count</th>
                            <th>Times</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${rows}
                    </tbody>
                </table>
            </div>
        `;
    }

    showSuccess(message) {
        this.showToast(message, 'success');
    }

    showError(message) {
        this.showToast(message, 'danger');
    }

    showToast(message, type = 'info') {
        // Simple toast implementation
        const toastContainer = document.createElement('div');
        toastContainer.className = 'position-fixed top-0 end-0 p-3';
        toastContainer.style.zIndex = '1055';

        const toast = document.createElement('div');
        toast.className = `toast show`;
        toast.innerHTML = `
            <div class="toast-header bg-${type} text-white">
                <strong class="me-auto">MedTracker</strong>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast"></button>
            </div>
            <div class="toast-body">${message}</div>
        `;

        toastContainer.appendChild(toast);
        document.body.appendChild(toastContainer);

        // Auto remove after 5 seconds
        setTimeout(() => {
            toastContainer.remove();
        }, 5000);
    }

    startPeriodicUpdates() {
        // Update status every 5 minutes
        setInterval(() => {
            if (this.isOnline && !document.hidden) {
                this.updateStatus();
            }
        }, 5 * 60 * 1000);
    }
}

// Global functions for HTML onclick handlers
function manualTrack() {
    medTracker.manualTrack();
}

function showSettings() {
    medTracker.showSettings();
}

function saveSettings() {
    medTracker.saveSettings();
}

function showHistory() {
    medTracker.showHistory();
}

// Initialize the app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.medTracker = new MedTracker();
});