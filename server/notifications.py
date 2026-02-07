#!/usr/bin/env python3
"""
MedTracker Notification System
Handles web push notifications and reminder scheduling
"""

import json
import secrets
import sqlite3
import schedule
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

try:
    from pywebpush import webpush, WebPushException
    WEBPUSH_AVAILABLE = True
except ImportError:
    WEBPUSH_AVAILABLE = False
    logging.warning("pywebpush not installed. Web push notifications will not work.")

logger = logging.getLogger(__name__)

class NotificationManager:
    def __init__(self, db_path: str, vapid_private_key: Optional[str] = None, vapid_public_key: Optional[str] = None):
        self.db_path = db_path
        self.vapid_private_key = vapid_private_key
        self.vapid_public_key = vapid_public_key
        self.scheduler_running = False
        
        # Generate VAPID keys if not provided
        if not self.vapid_private_key:
            self.generate_vapid_keys()
        
        # Start the scheduler in a separate thread
        self.start_scheduler()
    
    def generate_vapid_keys(self):
        """Generate VAPID keys for web push notifications"""
        if WEBPUSH_AVAILABLE:
            try:
                from pywebpush import generate_vapid_keys
                vapid = generate_vapid_keys()
                self.vapid_private_key = vapid['private_key']
                self.vapid_public_key = vapid['public_key']
                
                logger.info("Generated new VAPID keys for web push notifications")
                print(f"VAPID Public Key: {self.vapid_public_key}")
                print("Save these keys for production use!")
            except Exception as e:
                logger.error(f"Failed to generate VAPID keys: {e}")
        else:
            # Fallback for when pywebpush is not available
            self.vapid_private_key = secrets.token_urlsafe(32)
            self.vapid_public_key = secrets.token_urlsafe(32) 
            logger.warning("Using fallback keys - web push notifications may not work")
    
    def get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def add_subscription(self, subscription_data: Dict) -> bool:
        """Add a push notification subscription"""
        try:
            with self.get_connection() as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO notification_subscriptions 
                    (endpoint, p256dh_key, auth_key)
                    VALUES (?, ?, ?)
                ''', (
                    subscription_data['endpoint'],
                    subscription_data['keys']['p256dh'],
                    subscription_data['keys']['auth']
                ))
                
            logger.info(f"Added/updated push subscription: {subscription_data['endpoint'][:50]}...")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add subscription: {e}")
            return False
    
    def get_all_subscriptions(self) -> List[Dict]:
        """Get all active push subscriptions"""
        try:
            with self.get_connection() as conn:
                rows = conn.execute('''
                    SELECT endpoint, p256dh_key, auth_key 
                    FROM notification_subscriptions
                ''').fetchall()
                
                return [
                    {
                        'endpoint': row['endpoint'],
                        'keys': {
                            'p256dh': row['p256dh_key'],
                            'auth': row['auth_key']
                        }
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Failed to get subscriptions: {e}")
            return []
    
    def send_notification(self, title: str, body: str, data: Optional[Dict] = None) -> bool:
        """Send push notification to all subscribed users"""
        if not WEBPUSH_AVAILABLE:
            logger.warning("Cannot send push notification - pywebpush not available")
            return False
        
        subscriptions = self.get_all_subscriptions()
        if not subscriptions:
            logger.info("No subscriptions available for push notification")
            return True
        
        notification_payload = {
            'title': title,
            'body': body,
            'icon': '/static/icon-192.png',
            'badge': '/static/badge-72.png',
            'tag': 'medication-reminder',
            'requireInteraction': True,
            'actions': [
                {
                    'action': 'taken',
                    'title': '✅ Taken'
                },
                {
                    'action': 'snooze',
                    'title': '⏰ Snooze 15m'
                }
            ],
            'data': data or {}
        }
        
        successful_sends = 0
        failed_subscriptions = []
        
        for subscription in subscriptions:
            try:
                webpush(
                    subscription_info=subscription,
                    data=json.dumps(notification_payload),
                    vapid_private_key=self.vapid_private_key,
                    vapid_claims={
                        "sub": "mailto:medtracker@localhost"
                    }
                )
                successful_sends += 1
                
            except WebPushException as ex:
                logger.error(f"Failed to send push notification: {ex}")
                
                # Remove invalid subscriptions
                if ex.response and ex.response.status_code in [410, 413, 429]:
                    failed_subscriptions.append(subscription['endpoint'])
                    
            except Exception as e:
                logger.error(f"Unexpected error sending notification: {e}")
        
        # Clean up invalid subscriptions
        if failed_subscriptions:
            self.remove_subscriptions(failed_subscriptions)
        
        logger.info(f"Sent notifications to {successful_sends}/{len(subscriptions)} subscribers")
        return successful_sends > 0
    
    def remove_subscriptions(self, endpoints: List[str]):
        """Remove invalid subscriptions"""
        if not endpoints:
            return
        
        try:
            with self.get_connection() as conn:
                placeholders = ','.join(['?' for _ in endpoints])
                conn.execute(f'''
                    DELETE FROM notification_subscriptions 
                    WHERE endpoint IN ({placeholders})
                ''', endpoints)
                
            logger.info(f"Removed {len(endpoints)} invalid subscriptions")
        except Exception as e:
            logger.error(f"Failed to remove invalid subscriptions: {e}")
    
    def check_medication_adherence(self):
        """Check if medications have been taken and send reminders"""
        try:
            with self.get_connection() as conn:
                # Get all medications that need checking
                medications = conn.execute('''
                    SELECT * FROM medication_settings 
                    WHERE reminder_enabled = 1
                ''').fetchall()
                
                for med in medications:
                    if self.should_send_reminder(med):
                        self.send_medication_reminder(med)
                        
        except Exception as e:
            logger.error(f"Error checking medication adherence: {e}")
    
    def should_send_reminder(self, medication) -> bool:
        """Check if a reminder should be sent for this medication"""
        try:
            with self.get_connection() as conn:
                # Check if medication was taken today
                today_logs = conn.execute('''
                    SELECT COUNT(*) as count FROM medication_logs 
                    WHERE medication_id = ? 
                    AND DATE(timestamp) = DATE('now')
                ''', (medication['medication_id'],)).fetchone()
                
                # If already taken today, no reminder needed
                if today_logs['count'] > 0:
                    return False
                
                # Check scheduled time
                scheduled_time = medication['schedule_time'] or '09:00'
                scheduled_datetime = datetime.strptime(scheduled_time, '%H:%M').time()
                current_time = datetime.now().time()
                
                # Send reminder if it's past the scheduled time
                return current_time >= scheduled_time
                
        except Exception as e:
            logger.error(f"Error checking reminder status: {e}")
            return False
    
    def send_medication_reminder(self, medication):
        """Send a medication reminder notification"""
        med_name = medication['name'] or 'Your medication'
        dosage = medication['dosage'] or '1 pill'
        
        title = "💊 Medication Reminder"
        body = f"Time to take {med_name} ({dosage})"
        
        data = {
            'medication_id': medication['medication_id'],
            'medication_name': med_name,
            'url': '/',
            'timestamp': datetime.now().isoformat()
        }
        
        success = self.send_notification(title, body, data)
        
        if success:
            # Log the reminder
            with self.get_connection() as conn:
                conn.execute('''
                    INSERT INTO medication_logs 
                    (medication_id, notes, ip_address, user_agent)
                    VALUES (?, ?, ?, ?)
                ''', (
                    medication['medication_id'],
                    'reminder_sent',
                    'system',
                    'notification_system'
                ))
            
            logger.info(f"Sent medication reminder for {med_name}")
    
    def send_low_stock_alert(self, medication):
        """Send low stock alert"""
        med_name = medication['name'] or 'Your medication'
        remaining = medication['current_stock'] or 0
        
        title = "📦 Low Stock Alert"
        body = f"{med_name}: Only {remaining} pills remaining. Time to refill!"
        
        data = {
            'type': 'low_stock',
            'medication_id': medication['medication_id'],
            'stock_remaining': remaining
        }
        
        self.send_notification(title, body, data)
        logger.info(f"Sent low stock alert for {med_name} ({remaining} remaining)")
    
    def start_scheduler(self):
        """Start the reminder scheduler"""
        if self.scheduler_running:
            return
        
        # Schedule reminder checks every 15 minutes
        schedule.every(15).minutes.do(self.check_medication_adherence)
        
        # Schedule daily stock level checks
        schedule.every().day.at("08:00").do(self.check_stock_levels)
        
        def run_scheduler():
            self.scheduler_running = True
            logger.info("Notification scheduler started")
            
            while self.scheduler_running:
                try:
                    schedule.run_pending()
                    time.sleep(60)  # Check every minute
                except Exception as e:
                    logger.error(f"Scheduler error: {e}")
                    time.sleep(60)
        
        scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()
    
    def check_stock_levels(self):
        """Check medication stock levels and send alerts"""
        try:
            with self.get_connection() as conn:
                low_stock_meds = conn.execute('''
                    SELECT * FROM medication_settings 
                    WHERE current_stock <= low_stock_threshold 
                    AND current_stock > 0
                ''').fetchall()
                
                for med in low_stock_meds:
                    self.send_low_stock_alert(med)
                    
        except Exception as e:
            logger.error(f"Error checking stock levels: {e}")
    
    def stop_scheduler(self):
        """Stop the reminder scheduler"""
        self.scheduler_running = False
        logger.info("Notification scheduler stopped")


# Utility function to create a notification manager instance
def create_notification_manager(db_path: str, vapid_private_key: str = None, vapid_public_key: str = None):
    """Create and return a notification manager instance"""
    return NotificationManager(db_path, vapid_private_key, vapid_public_key)