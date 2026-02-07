#!/usr/bin/env python3
"""
MedTracker Flask Server
NFC-triggered medication tracking system for Raspberry Pi
"""

from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
from datetime import datetime, timedelta
import sqlite3
import os
import secrets
import json
from werkzeug.serving import WSGIRequestHandler
import logging
from notifications import create_notification_manager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='../static', template_folder='../templates')
CORS(app)

# Configuration
DATABASE_PATH = 'medtracker.db'
AUTH_TOKEN = os.environ.get('MEDTRACKER_TOKEN', 'change_me_for_security')

class DatabaseManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize the SQLite database with required tables"""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS medication_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    medication_id TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    ip_address TEXT,
                    user_agent TEXT,
                    notes TEXT
                );
                
                CREATE TABLE IF NOT EXISTS medication_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    medication_id TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    dosage TEXT,
                    schedule_time TEXT,
                    reminder_enabled BOOLEAN DEFAULT 1,
                    low_stock_threshold INTEGER DEFAULT 7,
                    current_stock INTEGER DEFAULT 30,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS notification_subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    endpoint TEXT UNIQUE NOT NULL,
                    p256dh_key TEXT NOT NULL,
                    auth_key TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                
                -- Insert default medication if none exists
                INSERT OR IGNORE INTO medication_settings 
                (medication_id, name, schedule_time, dosage) 
                VALUES ('daily_pill', 'Daily Medication', '09:00', '1 pill');
            ''')
            logger.info("Database initialized successfully")

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        return conn

# Initialize database
db_manager = DatabaseManager(DATABASE_PATH)

# Initialize notification manager
notification_manager = create_notification_manager(
    DATABASE_PATH,
    os.environ.get('VAPID_PRIVATE_KEY'),
    os.environ.get('VAPID_PUBLIC_KEY')
)

def verify_token(token):
    """Simple token verification"""
    return token == AUTH_TOKEN

def get_client_info():
    """Extract client information from request"""
    return {
        'ip_address': request.environ.get('HTTP_X_REAL_IP', request.remote_addr),
        'user_agent': request.headers.get('User-Agent', '')
    }

@app.route('/')
def index():
    """Serve the main web interface"""
    return render_template('index.html')

@app.route('/track', methods=['GET', 'POST'])
def track_medication():
    """
    Log medication intake - triggered by NFC tap
    URL format: /track?med_id=daily_pill&token=auth_token&notes=optional
    """
    try:
        # Get parameters
        med_id = request.args.get('med_id', 'daily_pill')
        token = request.args.get('token', '')
        notes = request.args.get('notes', '')
        
        # Verify authentication
        if not verify_token(token):
            return jsonify({
                'success': False, 
                'error': 'Invalid authentication token'
            }), 401
        
        # Get client info
        client_info = get_client_info()
        
        # Log the medication intake
        with db_manager.get_connection() as conn:
            conn.execute('''
                INSERT INTO medication_logs 
                (medication_id, ip_address, user_agent, notes)
                VALUES (?, ?, ?, ?)
            ''', (med_id, client_info['ip_address'], client_info['user_agent'], notes))
            
            # Update stock count (decrease by 1)
            conn.execute('''
                UPDATE medication_settings 
                SET current_stock = current_stock - 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE medication_id = ?
            ''', (med_id,))
        
        logger.info(f"Medication tracked: {med_id} from {client_info['ip_address']}")
        
        return jsonify({
            'success': True,
            'message': 'Medication intake logged successfully',
            'timestamp': datetime.now().isoformat(),
            'medication_id': med_id
        })
        
    except Exception as e:
        logger.error(f"Error tracking medication: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/status')
def get_status():
    """Get today's medication status and recent logs"""
    try:
        med_id = request.args.get('med_id', 'daily_pill')
        
        with db_manager.get_connection() as conn:
            # Get today's logs
            today_logs = conn.execute('''
                SELECT * FROM medication_logs 
                WHERE medication_id = ? 
                AND DATE(timestamp) = DATE('now')
                ORDER BY timestamp DESC
            ''', (med_id,)).fetchall()
            
            # Get medication settings
            medication = conn.execute('''
                SELECT * FROM medication_settings 
                WHERE medication_id = ?
            ''', (med_id,)).fetchone()
            
            # Get recent logs (last 7 days)
            recent_logs = conn.execute('''
                SELECT DATE(timestamp) as date, COUNT(*) as count
                FROM medication_logs 
                WHERE medication_id = ? 
                AND timestamp >= DATE('now', '-7 days')
                GROUP BY DATE(timestamp)
                ORDER BY date DESC
            ''', (med_id,)).fetchall()
        
        return jsonify({
            'success': True,
            'today_taken': len(today_logs),
            'today_logs': [dict(log) for log in today_logs],
            'medication': dict(medication) if medication else None,
            'recent_logs': [dict(log) for log in recent_logs],
            'low_stock': medication and medication['current_stock'] <= medication['low_stock_threshold']
        })
        
    except Exception as e:
        logger.error(f"Error getting status: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/settings', methods=['GET', 'POST'])
def medication_settings():
    """Get or update medication settings"""
    try:
        if request.method == 'GET':
            med_id = request.args.get('med_id', 'daily_pill')
            
            with db_manager.get_connection() as conn:
                medication = conn.execute('''
                    SELECT * FROM medication_settings 
                    WHERE medication_id = ?
                ''', (med_id,)).fetchone()
            
            return jsonify({
                'success': True,
                'medication': dict(medication) if medication else None
            })
        
        elif request.method == 'POST':
            data = request.get_json()
            med_id = data.get('medication_id', 'daily_pill')
            
            # Update medication settings
            with db_manager.get_connection() as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO medication_settings 
                    (medication_id, name, dosage, schedule_time, reminder_enabled, 
                     low_stock_threshold, current_stock, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (
                    med_id,
                    data.get('name', 'Daily Medication'),
                    data.get('dosage', '1 pill'),
                    data.get('schedule_time', '09:00'),
                    data.get('reminder_enabled', True),
                    data.get('low_stock_threshold', 7),
                    data.get('current_stock', 30)
                ))
            
            return jsonify({'success': True, 'message': 'Settings updated successfully'})
    
    except Exception as e:
        logger.error(f"Error handling settings: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/history')
def get_history():
    """Get medication history for calendar view"""
    try:
        med_id = request.args.get('med_id', 'daily_pill')
        days = int(request.args.get('days', 30))  # Default to 30 days
        
        with db_manager.get_connection() as conn:
            history = conn.execute('''
                SELECT DATE(timestamp) as date, 
                       COUNT(*) as doses_taken,
                       GROUP_CONCAT(TIME(timestamp)) as times
                FROM medication_logs 
                WHERE medication_id = ? 
                AND timestamp >= DATE('now', '-{} days')
                GROUP BY DATE(timestamp)
                ORDER BY date DESC
            '''.format(days), (med_id,)).fetchall()
        
        return jsonify({
            'success': True,
            'history': [dict(row) for row in history]
        })
        
    except Exception as e:
        logger.error(f"Error getting history: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/subscribe', methods=['POST'])
def subscribe_notifications():
    """Subscribe to web push notifications"""
    try:
        data = request.get_json()
        
        success = notification_manager.add_subscription(data)
        
        if success:
            logger.info("New notification subscription added")
            return jsonify({'success': True, 'message': 'Subscription successful'})
        else:
            return jsonify({'success': False, 'error': 'Failed to save subscription'}), 500
        
    except Exception as e:
        logger.error(f"Error subscribing to notifications: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/vapid-public-key')
def get_vapid_public_key():
    """Get VAPID public key for web push notifications"""
    return jsonify({
        'success': True,
        'public_key': notification_manager.vapid_public_key
    })

@app.route('/test-notification', methods=['POST'])
def test_notification():
    """Send a test notification (for debugging)"""
    try:
        data = request.get_json() or {}
        title = data.get('title', 'MedTracker Test')
        body = data.get('body', 'This is a test notification')
        
        success = notification_manager.send_notification(title, body)
        
        return jsonify({
            'success': success,
            'message': 'Test notification sent' if success else 'Failed to send notification'
        })
        
    except Exception as e:
        logger.error(f"Error sending test notification: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/health')
def health_check():
    """Simple health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'database': os.path.exists(DATABASE_PATH),
        'notifications': notification_manager.scheduler_running
    })

# Custom request handler to log requests
class CustomRequestHandler(WSGIRequestHandler):
    def log_request(self, code='-', size='-'):
        if self.path.startswith('/track'):
            logger.info(f"NFC Request: {self.address_string()} {self.requestline} {code}")
        else:
            super().log_request(code, size)

if __name__ == '__main__':
    # Generate a secure token if using default
    if AUTH_TOKEN == 'change_me_for_security':
        AUTH_TOKEN = secrets.token_urlsafe(32)
        logger.warning(f"Generated temporary auth token: {AUTH_TOKEN}")
        logger.warning("Set MEDTRACKER_TOKEN environment variable for production use")
    
    print(f"\n🏥 MedTracker Server Starting...")
    print(f"📱 NFC URL: http://raspberrypi.local:8080/track?med_id=daily_pill&token={AUTH_TOKEN}")
    print(f"🌐 Web Interface: http://raspberrypi.local:8080")
    print(f"🔐 Auth Token: {AUTH_TOKEN}")
    print(f"💾 Database: {os.path.abspath(DATABASE_PATH)}\n")
    
    # Run the development server
    app.run(
        host='0.0.0.0',  # Listen on all network interfaces
        port=8080,
        debug=True,
        request_handler=CustomRequestHandler
    )