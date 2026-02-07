/**
 * MedTracker Service Worker
 * Handles push notifications, caching, and offline functionality
 */

const CACHE_NAME = 'medtracker-v1';
const urlsToCache = [
    '/',
    '/static/app.js',
    '/static/manifest.json',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css',
    'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.7.2/font/bootstrap-icons.css'
];

// Install service worker and cache resources
self.addEventListener('install', event => {
    console.log('Service Worker installing...');
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => {
                console.log('Opened cache');
                return cache.addAll(urlsToCache);
            })
            .catch(error => {
                console.error('Failed to cache resources:', error);
            })
    );
});

// Fetch event - serve from cache when offline
self.addEventListener('fetch', event => {
    event.respondWith(
        caches.match(event.request)
            .then(response => {
                // Return cached version or fetch from network
                return response || fetch(event.request);
            })
            .catch(() => {
                // Fallback for offline API requests
                if (event.request.url.includes('/api/')) {
                    return new Response(JSON.stringify({
                        success: false,
                        error: 'Offline - please try again when connected'
                    }), {
                        headers: { 'Content-Type': 'application/json' }
                    });
                }
            })
    );
});

// Activate service worker and clean old caches
self.addEventListener('activate', event => {
    console.log('Service Worker activating...');
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(cacheName => {
                    if (cacheName !== CACHE_NAME) {
                        console.log('Deleting old cache:', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
});

// Handle push notifications
self.addEventListener('push', event => {
    console.log('Push notification received:', event);

    let notificationData = {
        title: 'MedTracker Reminder',
        body: 'Time to take your medication!',
        icon: '/static/icon-192.png',
        badge: '/static/badge-72.png',
        tag: 'medication-reminder',
        requireInteraction: true,
        actions: [
            {
                action: 'taken',
                title: '✅ Taken',
                icon: '/static/check-icon.png'
            },
            {
                action: 'snooze',
                title: '⏰ Snooze 15m',
                icon: '/static/snooze-icon.png'
            },
            {
                action: 'dismiss',
                title: '❌ Dismiss',
                icon: '/static/dismiss-icon.png'
            }
        ],
        data: {
            url: '/',
            medication_id: 'daily_pill',
            timestamp: Date.now()
        }
    };

    // Parse notification data if provided
    if (event.data) {
        try {
            const data = event.data.json();
            notificationData = { ...notificationData, ...data };
        } catch (error) {
            console.error('Error parsing push data:', error);
            notificationData.body = event.data.text() || notificationData.body;
        }
    }

    event.waitUntil(
        self.registration.showNotification(notificationData.title, notificationData)
    );
});

// Handle notification clicks
self.addEventListener('notificationclick', event => {
    console.log('Notification clicked:', event);

    event.notification.close();

    const action = event.action;
    const notificationData = event.notification.data || {};

    if (action === 'taken') {
        // Log medication as taken
        event.waitUntil(
            handleMedicationTaken(notificationData)
        );
    } else if (action === 'snooze') {
        // Schedule a snooze notification
        event.waitUntil(
            handleSnoozeNotification(notificationData)
        );
    } else if (action === 'dismiss') {
        // Just dismiss - no action needed
        console.log('Notification dismissed by user');
    } else {
        // Default click - open the app
        event.waitUntil(
            clients.matchAll({ type: 'window' }).then(clientList => {
                // If app is already open, focus it
                for (const client of clientList) {
                    if (client.url === notificationData.url && 'focus' in client) {
                        return client.focus();
                    }
                }
                // Otherwise open a new window
                if (clients.openWindow) {
                    return clients.openWindow(notificationData.url || '/');
                }
            })
        );
    }
});

// Handle notification close events
self.addEventListener('notificationclose', event => {
    console.log('Notification closed:', event.notification.tag);

    // Track notification dismiss for analytics
    const data = {
        action: 'notification_dismissed',
        tag: event.notification.tag,
        timestamp: Date.now()
    };

    // Send analytics (optional)
    event.waitUntil(
        sendAnalytics(data)
    );
});

// Helper function to handle medication taken action
async function handleMedicationTaken(data) {
    try {
        const token = await getAuthToken();
        if (!token) {
            console.error('No auth token available for medication logging');
            return;
        }

        const medication_id = data.medication_id || 'daily_pill';
        const url = `${self.location.origin}/track?med_id=${medication_id}&token=${token}&notes=notification_action`;

        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        if (response.ok) {
            // Show success notification
            await self.registration.showNotification('MedTracker', {
                body: '✅ Medication logged successfully!',
                icon: '/static/icon-192.png',
                tag: 'medication-logged',
                requireInteraction: false
            });

            // Notify any open clients to refresh
            const clients = await self.clients.matchAll();
            clients.forEach(client => {
                client.postMessage({ type: 'MEDICATION_LOGGED' });
            });
        } else {
            throw new Error('Failed to log medication');
        }
    } catch (error) {
        console.error('Failed to log medication from notification:', error);

        // Show error notification
        await self.registration.showNotification('MedTracker', {
            body: '❌ Failed to log medication. Please open the app.',
            icon: '/static/icon-192.png',
            tag: 'medication-error',
            requireInteraction: true
        });
    }
}

// Helper function to handle snooze
async function handleSnoozeNotification(data) {
    try {
        // Schedule a new notification in 15 minutes
        const snoozeTime = 15 * 60 * 1000; // 15 minutes in milliseconds

        setTimeout(() => {
            self.registration.showNotification('MedTracker - Reminder', {
                body: '⏰ Snooze time is up! Time to take your medication.',
                icon: '/static/icon-192.png',
                badge: '/static/badge-72.png',
                tag: 'medication-snooze',
                requireInteraction: true,
                actions: [
                    {
                        action: 'taken',
                        title: '✅ Taken',
                        icon: '/static/check-icon.png'
                    },
                    {
                        action: 'snooze',
                        title: '⏰ Snooze 15m',
                        icon: '/static/snooze-icon.png'
                    }
                ],
                data: data
            });
        }, snoozeTime);

        // Show confirmation
        await self.registration.showNotification('MedTracker', {
            body: '⏰ Reminder snoozed for 15 minutes',
            icon: '/static/icon-192.png',
            tag: 'snooze-confirmation',
            requireInteraction: false
        });

    } catch (error) {
        console.error('Failed to snooze notification:', error);
    }
}

// Helper function to get stored auth token
async function getAuthToken() {
    try {
        // Try to get token from IndexedDB or localStorage
        const clients = await self.clients.matchAll();
        if (clients.length > 0) {
            // Ask the main app for the token
            return new Promise((resolve) => {
                const channel = new MessageChannel();
                channel.port1.onmessage = (event) => {
                    resolve(event.data.token);
                };
                clients[0].postMessage({ type: 'GET_AUTH_TOKEN' }, [channel.port2]);
            });
        }

        // Fallback to default token (not recommended for production)
        return 'demo_token';
    } catch (error) {
        console.error('Failed to get auth token:', error);
        return null;
    }
}

// Helper function to send analytics (optional)
async function sendAnalytics(data) {
    try {
        await fetch('/analytics', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });
    } catch (error) {
        console.error('Failed to send analytics:', error);
    }
}

// Handle messages from main app
self.addEventListener('message', event => {
    console.log('Service Worker received message:', event.data);

    if (event.data && event.data.type === 'GET_AUTH_TOKEN') {
        // Respond with stored token if available
        const token = self.authToken || 'demo_token';
        event.ports[0].postMessage({ token });
    }

    if (event.data && event.data.type === 'SET_AUTH_TOKEN') {
        // Store auth token for API calls
        self.authToken = event.data.token;
    }
});

console.log('Service Worker script loaded');