Plan: NFC URL-Triggered Med Tracker on Pi
TL;DR: Program NFC stickers with URLs that trigger API calls to a Flask web server on your Raspberry Pi. Simple web interface for management and web push notifications for reminders. Everything runs locally on your home network - no external dependencies or monthly costs.

Steps

Raspberry Pi Server Setup

Install Python 3 and Flask on your Pi at fixed IP (e.g., 192.168.1.100)
Create medTracker/server/app.py Flask application with REST API endpoints
Set up medTracker/server/database.py with SQLite for medication logs and settings
Configure Pi to run Flask server on boot at http://raspberrypi.local:8080
API Endpoints for NFC Triggers

Implement GET /track?med_id=pill_a&token=abc123 endpoint for NFC tap logging
Create GET /status for checking today's adherence status
Add POST /settings for configuring medication schedule and reminders
Build simple token-based authentication to prevent unauthorized access
Web Frontend Interface

Create mobile-responsive web UI at medTracker/static/index.html
Build dashboard showing today's status, recent logs, and medication info
Add settings page for schedule configuration and notification preferences
Design history view with simple calendar showing adherence patterns
Web Push Notification System

Implement VAPID key generation and web push service in Flask
Create medTracker/static/sw.js service worker for notification handling
Add browser notification permission request on first visit
Build reminder scheduler that checks adherence and sends notifications
NFC Sticker Programming

Program stickers with URLs like http://192.168.1.100:8080/track?med_id=daily_pill&token=secure123
Create one sticker for the medication bottle with unique identifier
Test URL triggers work on both iOS and Android devices
Document backup manual entry method via web interface
Local Network Integration

Configure Pi with static IP for reliable access
Set up mDNS so Pi is accessible at raspberrypi.local
Create simple startup script to launch Flask server on Pi boot
Add basic logging for debugging and usage tracking
Verification

Scan NFC sticker and verify it logs medication intake in web interface
Test web push notifications trigger at configured reminder times
Check system works from multiple phones on same WiFi network
Verify Pi server restarts properly after power cycling
Decisions

Local-only hosting: No external dependencies, works offline, zero monthly costs
Python/Flask stack: Simple setup, perfect for Pi's resources, easy to maintain
Web Push notifications: Free, reliable on modern browsers, no SMS costs
SQLite database: File-based, no server setup needed, sufficient for single-user scale
