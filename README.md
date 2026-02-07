# 🏥 MedTracker - NFC Medication Monitor

A simple, privacy-focused medication tracking system using NFC stickers and a Raspberry Pi. Your roommate can tap her phone on an NFC sticker attached to her medication bottle to log when she's taken her pills, with smart reminders and low-stock alerts.

## ✨ Features

- **🏷️ NFC Tap Logging**: Tap phone on medication bottle to instantly log intake
- **📱 Mobile Web Interface**: Clean, responsive design optimized for phones  
- **🔔 Smart Reminders**: Web push notifications for missed medications
- **📊 Adherence Tracking**: Visual history and streak tracking
- **📦 Stock Management**: Low-stock alerts and inventory tracking
- **🔒 Privacy-First**: All data stays on your local network
- **💰 Zero Monthly Costs**: No subscriptions or cloud dependencies
- **🚀 Easy Setup**: One-command installation on Raspberry Pi

## 📡 How It Works

1. **NFC Stickers**: Program NFC stickers with a medication tracking URL
2. **Phone Integration**: Native iOS/Android NFC handling (no app required)
3. **API Logging**: Sticker tap triggers HTTP request to log medication intake
4. **Web Dashboard**: Mobile-optimized interface for management and history
5. **Smart Reminders**: Automated notifications for missed doses

## 🚀 Quick Start

### Prerequisites
- Raspberry Pi (3B+ or newer recommended)
- NFC stickers (NTAG213/215 compatible)
- Smartphone with NFC capability
- Home WiFi network

### Installation

1. **Clone and run setup on your Pi:**
```bash
git clone <repository-url> medTracker
cd medTracker
./setup.sh
```

2. **The setup script will:**
   - Install all dependencies
   - Generate secure authentication tokens  
   - Configure systemd service for auto-startup
   - Set up optional static IP
   - Create your NFC programming URL

3. **Program your NFC stickers:**
   - Install "NFC Tools" app on your phone
   - Use the generated URL from setup
   - Attach programmed stickers to medication bottles

## 📁 Project Structure

```
medTracker/
├── server/
│   ├── app.py              # Flask web server
│   ├── notifications.py    # Push notification system
├── templates/
│   └── index.html          # Web interface
├── static/
│   ├── app.js              # Frontend JavaScript
│   ├── sw.js               # Service worker for notifications
│   └── manifest.json       # PWA configuration
├── scripts/
│   ├── medtracker.service  # Systemd service file
│   └── generate_nfc_url.py # NFC URL generator tool
├── setup.sh                # Installation script
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## 🔧 API Endpoints

### Core Tracking
- `GET /track?med_id=daily_pill&token=auth_token` - Log medication intake (NFC trigger)
- `GET /status` - Get today's adherence status and recent logs
- `GET /history?days=30` - Get medication history for calendar view

### Configuration  
- `GET/POST /settings` - Medication settings and schedule configuration
- `POST /subscribe` - Subscribe to web push notifications
- `GET /vapid-public-key` - Get public key for push notification setup

### Utility
- `GET /health` - Server health check
- `POST /test-notification` - Send test notification (debugging)

## 📱 Usage

### Daily Use
1. **Taking Medication**: Tap phone on NFC sticker attached to medication bottle
2. **Manual Entry**: Use web interface if NFC isn't working
3. **Check Status**: Visit web interface to see today's status and history

### NFC Setup
```bash
# Generate NFC URL using the included script
python3 scripts/generate_nfc_url.py

# Example generated URL:
http://192.168.1.100:8080/track?med_id=daily_pill&token=abc123xyz
```

### Web Push Notifications
- Browser will request notification permission on first visit
- Reminders sent for missed medications based on schedule
- Low-stock alerts when pill count gets low
- Notifications work even when browser isn't open

## ⚙️ Configuration

### Environment Variables
Set in `/home/pi/medTracker/.env`:
```bash
MEDTRACKER_TOKEN=your_secure_auth_token
VAPID_PRIVATE_KEY=your_vapid_private_key  
VAPID_PUBLIC_KEY=your_vapid_public_key
FLASK_ENV=production
```

### Service Management
```bash
# Start/stop the service
sudo systemctl start medtracker
sudo systemctl stop medtracker
sudo systemctl restart medtracker

# View logs
sudo journalctl -u medtracker -f

# Check status
sudo systemctl status medtracker
```

### Database Schema
SQLite database automatically created with tables:
- `medication_settings` - Medication info, schedule, stock levels
- `medication_logs` - Timestamped intake logs  
- `notification_subscriptions` - Web push subscription data

## 🔒 Security Considerations

### Authentication
- Secure random token authentication for API endpoints
- Tokens included in NFC URLs prevent unauthorized logging
- No user accounts required - single-user system

### Network Security  
- Runs on local network only by default
- HTTPS can be added with reverse proxy (nginx)
- No external internet dependencies

### Privacy
- All data stored locally on your Pi
- No cloud services or third-party analytics
- Medication data never leaves your home network

## 🛠️ Development

### Local Development
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run development server
cd server
python app.py
```

### Testing
```bash
# Test NFC URL
curl "http://localhost:8080/track?med_id=daily_pill&token=demo_token"

# Check status
curl "http://localhost:8080/status"

# Send test notification
curl -X POST http://localhost:8080/test-notification \
  -H "Content-Type: application/json" \
  -d '{"title":"Test","body":"Test notification"}'
```

## 🐛 Troubleshooting

### Server Won't Start
```bash
# Check logs
sudo journalctl -u medtracker -n 50

# Common issues:
# - Missing Python dependencies: pip install -r requirements.txt  
# - Port conflicts: Check if port 8080 is free
# - Permission issues: Ensure pi user owns /home/pi/medTracker
```

### NFC Not Working
- Ensure phone has NFC enabled
- Check NFC sticker placement (must be close to phone's NFC antenna)
- Test URL manually in browser first
- iOS requires screen unlocked for NFC reading

### Push Notifications Not Working
```bash
# Check notification service status
curl http://your-pi-ip:8080/health

# Verify VAPID keys are set
grep VAPID /home/pi/medTracker/.env

# Browser must grant notification permission
```

### Network Issues
```bash
# Find Pi IP address
hostname -I

# Test from phone browser
ping your-pi-ip

# Check if service is listening
sudo netstat -tlnp | grep :8080
```

## 📈 Future Enhancements

Possible additions for v2:
- Multiple medication support with complex schedules
- SMS backup notifications via Twilio
- Pharmacy API integration for automatic refill alerts  
- Family/caregiver sharing with separate dashboards
- Export data to CSV/PDF for doctor visits
- Integration with fitness trackers or smart home systems

## 🤝 Contributing

This is a personal project but contributions are welcome:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly on actual Pi hardware
5. Submit a pull request

## 📄 License

MIT License - feel free to modify and use for personal projects.

---

## 🎯 Perfect for:
- **Single medication tracking** (like your roommate's daily pill)
- **Privacy-conscious users** who want data to stay local
- **Raspberry Pi enthusiasts** who enjoy self-hosted solutions
- **NFC experiment projects** exploring practical applications
- **Medication adherence improvement** with minimal complexity

**Total monthly cost: $0** (just electricity for the Pi!) 💡

Built with ❤️ for simple, reliable medication tracking.