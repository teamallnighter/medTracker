#!/bin/bash

# MedTracker Installation Script for Raspberry Pi
# Run this script to set up MedTracker on your Pi

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🏥 MedTracker Installation Script${NC}"
echo -e "${BLUE}===============================${NC}"
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo -e "${RED}❌ Please don't run this script as root/sudo${NC}"
    echo "Run as regular user (pi): ./setup.sh"
    exit 1
fi

# Check if on Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
    echo -e "${YELLOW}⚠️  Warning: This doesn't appear to be a Raspberry Pi${NC}"
    echo "The script will continue, but some features may not work properly."
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Get current user info
CURRENT_USER=$(whoami)
USER_HOME=$(eval echo ~$CURRENT_USER)
echo -e "${BLUE}👤 Running as user: $CURRENT_USER${NC}"
echo -e "${BLUE}🏠 Home directory: $USER_HOME${NC}"

echo -e "${GREEN}📋 Step 1: Updating system packages${NC}"
sudo apt update
sudo apt upgrade -y

echo -e "${GREEN}📋 Step 2: Installing Python and system dependencies${NC}"
sudo apt install -y python3 python3-pip python3-venv git sqlite3

echo -e "${GREEN}📋 Step 3: Creating project directory${NC}"

# Get the absolute path of the script directory FIRST, before any changes
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "📂 Source directory: $SCRIPT_DIR"

PROJECT_DIR="$USER_HOME/medTracker"
echo "📁 Installing to: $PROJECT_DIR"

# If we're running the script from inside the target directory, we need to handle it carefully
if [[ "$SCRIPT_DIR" == "$PROJECT_DIR"* ]]; then
    echo "⚠️  Running setup from target directory - using special handling"
    TEMP_SOURCE="/tmp/medtracker_source_$$"
    cp -r "$SCRIPT_DIR" "$TEMP_SOURCE"
    SCRIPT_DIR="$TEMP_SOURCE"
fi

if [ -d "$PROJECT_DIR" ]; then
    echo -e "${YELLOW}⚠️  MedTracker directory already exists${NC}"
    read -p "Remove existing installation? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Change to home directory before removing target
        cd "$USER_HOME"
        rm -rf "$PROJECT_DIR"
    else
        echo "Installation cancelled."
        exit 1
    fi
fi

# Copy files to Pi home directory
echo -e "${GREEN}📋 Step 4: Setting up project files${NC}"

# Create project directory
mkdir -p "$PROJECT_DIR"

# Copy all files except .git and existing venv
echo "📁 Copying files to $PROJECT_DIR..."
rsync -av --exclude='.git' --exclude='venv' --exclude='*.pyc' --exclude='__pycache__' "$SCRIPT_DIR/" "$PROJECT_DIR/"

# Clean up temp directory if we created one
if [[ "$SCRIPT_DIR" == "/tmp/medtracker_source_"* ]]; then
    rm -rf "$SCRIPT_DIR"
fi

cd "$PROJECT_DIR"

echo -e "${GREEN}📋 Step 5: Creating Python virtual environment${NC}"
echo "🐍 Creating virtual environment..."
python3 -m venv venv --clear

# Verify venv was created successfully
if [ ! -f "venv/bin/python3" ]; then
    echo -e "${RED}❌ Failed to create virtual environment${NC}"
    echo "Trying alternative approach..."
    
    # Try with system-wide venv package
    sudo apt install -y python3-venv
    python3 -m venv venv --clear
    
    if [ ! -f "venv/bin/python3" ]; then
        echo -e "${RED}❌ Virtual environment creation failed${NC}"
        exit 1
    fi
fi

echo "✅ Virtual environment created successfully"
source venv/bin/activate

# Verify activation worked
if [ "$VIRTUAL_ENV" != "$PROJECT_DIR/venv" ]; then
    echo -e "${YELLOW}⚠️  Virtual environment activation may have failed${NC}"
    echo "VIRTUAL_ENV=$VIRTUAL_ENV"
    echo "Expected: $PROJECT_DIR/venv"
fi

echo -e "${GREEN}📋 Step 6: Installing Python dependencies${NC}"
pip install --upgrade pip
pip install -r requirements.txt

# Verify Flask installation
echo "🧪 Verifying Flask installation..."
python3 -c "import flask; print('✅ Flask version:', flask.__version__)" || {
    echo -e "${RED}❌ Flask installation failed${NC}"
    exit 1
}

# Test app.py imports
echo "🧪 Testing app imports..."
cd server
python3 -c "
import sys
sys.path.insert(0, '.')
try:
    from app import app
    print('✅ App imports successfully')
except Exception as e:
    print('❌ App import failed:', e)
    sys.exit(1)
" || {
    echo -e "${RED}❌ App import test failed${NC}"
    exit 1
}
cd ..

echo -e "${GREEN}📋 Step 7: Generating secure tokens${NC}"
# Generate secure authentication token
AUTH_TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
echo "Generated authentication token: $AUTH_TOKEN"

# Generate VAPID keys for web push notifications
echo "Generating VAPID keys for push notifications..."
python3 << 'EOF' > .env_temp
try:
    from pywebpush import generate_vapid_keys
    import json
    vapid = generate_vapid_keys()
    print('VAPID_PRIVATE_KEY=' + vapid['private_key'])
    print('VAPID_PUBLIC_KEY=' + vapid['public_key'])
    
    # Save to file
    with open('vapid_keys.json', 'w') as f:
        json.dump(vapid, f, indent=2)
    print('# VAPID keys saved to vapid_keys.json')
except ImportError:
    print('# pywebpush not available - using fallback keys')
    import secrets
    print('VAPID_PRIVATE_KEY=' + secrets.token_urlsafe(32))
    print('VAPID_PUBLIC_KEY=' + secrets.token_urlsafe(32))
except Exception as e:
    print('# Error generating VAPID keys - using fallback')  
    import secrets
    print('VAPID_PRIVATE_KEY=' + secrets.token_urlsafe(32))
    print('VAPID_PUBLIC_KEY=' + secrets.token_urlsafe(32))
EOF

source .env_temp
VAPID_PRIVATE_KEY=$(grep VAPID_PRIVATE_KEY .env_temp | cut -d'=' -f2)
VAPID_PUBLIC_KEY=$(grep VAPID_PUBLIC_KEY .env_temp | cut -d'=' -f2)

echo -e "${GREEN}📋 Step 8: Creating environment file${NC}"
cat > .env << EOF
# MedTracker Configuration
MEDTRACKER_TOKEN=$AUTH_TOKEN
VAPID_PRIVATE_KEY=$VAPID_PRIVATE_KEY
VAPID_PUBLIC_KEY=$VAPID_PUBLIC_KEY

# Flask Configuration
FLASK_ENV=production
FLASK_DEBUG=false
EOF

rm .env_temp

echo -e "${GREEN}📋 Step 9: Setting up systemd service${NC}"
# Update service file with actual paths, user, and tokens
sed -i "s|User=pi|User=$CURRENT_USER|g" scripts/medtracker.service
sed -i "s|Group=pi|Group=$CURRENT_USER|g" scripts/medtracker.service
sed -i "s|/home/pi/medTracker|$PROJECT_DIR|g" scripts/medtracker.service
sed -i "s|your_secure_token_here|$AUTH_TOKEN|g" scripts/medtracker.service
sed -i "s|your_vapid_private_key_here|$VAPID_PRIVATE_KEY|g" scripts/medtracker.service
sed -i "s|your_vapid_public_key_here|$VAPID_PUBLIC_KEY|g" scripts/medtracker.service

sudo cp scripts/medtracker.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable medtracker.service

# Test the service configuration without full startup
echo "🧪 Testing service configuration..."
sudo systemd-analyze verify /etc/systemd/system/medtracker.service || {
    echo -e "${YELLOW}⚠️  Service configuration issues detected${NC}"
}

# Show final service file for debugging
echo "📋 Final service configuration:"
echo "ExecStart path: $(grep ExecStart /etc/systemd/system/medtracker.service)"
echo "Working directory: $(grep WorkingDirectory /etc/systemd/system/medtracker.service)"
echo "User: $(grep "^User=" /etc/systemd/system/medtracker.service)"

echo -e "${GREEN}📋 Step 10: Setting up static IP (optional)${NC}"
read -p "Do you want to set up a static IP address? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Get current network info
    CURRENT_IP=$(hostname -I | awk '{print $1}')
    GATEWAY=$(ip route | grep default | awk '{print $3}' | head -1)
    
    echo "Current IP: $CURRENT_IP"
    echo "Gateway: $GATEWAY"
    
    read -p "Enter desired static IP (e.g., 192.168.1.100): " STATIC_IP
    read -p "Enter subnet mask (e.g., 255.255.255.0): " NETMASK
    read -p "Enter DNS server (e.g., 8.8.8.8): " DNS
    
    echo "Setting up static IP configuration..."
    sudo tee -a /etc/dhcpcd.conf > /dev/null << EOF

# MedTracker Static IP Configuration
interface wlan0
static ip_address=$STATIC_IP/24
static routers=$GATEWAY
static domain_name_servers=$DNS

interface eth0
static ip_address=$STATIC_IP/24
static routers=$GATEWAY  
static domain_name_servers=$DNS
EOF
fi

echo -e "${GREEN}📋 Step 11: Testing installation${NC}"
echo "🧪 Testing manual Flask startup..."

# Test that Flask can start (briefly)
timeout 10s python3 server/app.py 2>&1 | head -20 &
FLASK_PID=$!
sleep 3

if ps -p $FLASK_PID > /dev/null 2>&1; then
    echo "✅ Flask app starts successfully"
    kill $FLASK_PID 2>/dev/null || true
else
    echo -e "${RED}❌ Flask app failed to start manually${NC}"
    echo "Check for errors above. The service may also fail."
fi

echo "🚀 Starting MedTracker service..."
sudo systemctl start medtracker.service
sleep 5

# Check if service is running
if sudo systemctl is-active --quiet medtracker.service; then
    echo -e "${GREEN}✅ MedTracker service is running!${NC}"
else
    echo -e "${RED}❌ Failed to start MedTracker service${NC}"
    echo "Check logs with: sudo journalctl -u medtracker.service -f"
fi

echo -e "${GREEN}📋 Step 12: Creating NFC URL${NC}"
PI_IP=$(hostname -I | awk '{print $1}')
NFC_URL="http://$PI_IP:8080/track?med_id=daily_pill&token=$AUTH_TOKEN"

echo ""
echo -e "${BLUE}🎉 Installation Complete!${NC}"
echo -e "${BLUE}======================${NC}"
echo ""
echo -e "${GREEN}📱 Web Interface:${NC} http://$PI_IP:8080"
echo -e "${GREEN}🏷️  NFC URL:${NC} $NFC_URL"
echo -e "${GREEN}🔐 Auth Token:${NC} $AUTH_TOKEN"
echo ""
echo -e "${YELLOW}📋 Next Steps:${NC}"
echo "1. Program your NFC stickers with this URL:"
echo "   $NFC_URL"
echo ""
echo "2. Access the web interface from your phone:"
echo "   http://$PI_IP:8080"
echo ""
echo "3. Place NFC stickers on medication bottles"
echo ""
echo "4. Test by tapping your phone on an NFC sticker"
echo ""
echo -e "${YELLOW}🔧 Service Management:${NC}"
echo "Start:   sudo systemctl start medtracker"
echo "Stop:    sudo systemctl stop medtracker"
echo "Restart: sudo systemctl restart medtracker"
echo "Logs:    sudo journalctl -u medtracker -f"
echo "Status:  sudo systemctl status medtracker"
echo ""
echo -e "${YELLOW}🔒 Security Note:${NC}"
echo "Your authentication token and VAPID keys are saved in:"
echo "- $PROJECT_DIR/.env"
echo "- $PROJECT_DIR/vapid_keys.json"
echo ""
echo "Keep these files secure and backed up!"
echo ""

if [ -n "$STATIC_IP" ]; then
    echo -e "${YELLOW}🔄 Reboot Required:${NC}"
    echo "A reboot is required to apply the static IP configuration."
    read -p "Reboot now? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo reboot
    fi
fi

echo -e "${GREEN}Happy medication tracking! 💊${NC}"