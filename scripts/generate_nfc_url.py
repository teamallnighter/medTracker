#!/usr/bin/env python3
"""
NFC URL Generator for MedTracker
Generates the URL to program onto NFC stickers
"""

import sys
import secrets
import socket
import qrcode
from io import StringIO

def get_local_ip():
    """Get the Pi's local IP address"""
    try:
        # Connect to a remote server to get local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "192.168.1.100"  # Fallback IP

def generate_secure_token():
    """Generate a secure authentication token"""
    return secrets.token_urlsafe(32)

def create_qr_code(url):
    """Create QR code for the URL"""
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(url)
    qr.make(fit=True)
    
    # Print QR code to console
    qr.print_ascii(out=sys.stdout)

def main():
    print("🏥 MedTracker NFC URL Generator")
    print("=" * 40)
    
    # Get configuration
    pi_ip = input(f"Pi IP address [{get_local_ip()}]: ").strip() or get_local_ip()
    port = input("Port [8080]: ").strip() or "8080"
    med_id = input("Medication ID [daily_pill]: ").strip() or "daily_pill"
    
    # Get or generate token
    use_existing = input("Do you have an existing auth token? (y/N): ").lower().startswith('y')
    
    if use_existing:
        token = input("Enter your auth token: ").strip()
        if not token:
            print("❌ No token provided, generating new one...")
            token = generate_secure_token()
    else:
        token = generate_secure_token()
    
    # Generate URL
    base_url = f"http://{pi_ip}:{port}"
    nfc_url = f"{base_url}/track?med_id={med_id}&token={token}"
    
    print("\n✅ Generated URLs:")
    print("=" * 40)
    print(f"🌐 Web Interface: {base_url}")
    print(f"🏷️  NFC URL: {nfc_url}")
    print(f"🔐 Auth Token: {token}")
    
    print("\n📱 NFC Programming Instructions:")
    print("=" * 40)
    print("1. Install 'NFC Tools' app on your phone")
    print("2. Select 'Write' tab")
    print("3. Add a record > URL/URI")
    print("4. Paste this URL:")
    print(f"   {nfc_url}")
    print("5. Tap 'Write' and hold your NFC sticker to the phone")
    print("6. Stick the programmed NFC tag on your medication bottle")
    
    # Generate QR code
    print("\n📋 QR Code (for easy phone setup):")
    print("=" * 40)
    create_qr_code(base_url)
    
    print(f"\n💾 Save these details:")
    print("=" * 40)
    
    # Save to file
    filename = f"nfc_config_{med_id}.txt"
    with open(filename, 'w') as f:
        f.write(f"MedTracker Configuration\n")
        f.write(f"========================\n")
        f.write(f"Generated: {__import__('datetime').datetime.now().isoformat()}\n")
        f.write(f"Pi IP: {pi_ip}:{port}\n")
        f.write(f"Medication ID: {med_id}\n")
        f.write(f"Auth Token: {token}\n")
        f.write(f"Web Interface: {base_url}\n")
        f.write(f"NFC URL: {nfc_url}\n")
    
    print(f"Configuration saved to: {filename}")
    
    # Test connection
    test_connection = input("\n🧪 Test connection to Pi? (y/N): ").lower().startswith('y')
    if test_connection:
        try:
            import requests
            response = requests.get(f"{base_url}/health", timeout=5)
            if response.status_code == 200:
                print("✅ Connection successful!")
                print(f"Server status: {response.json().get('status', 'unknown')}")
            else:
                print(f"❌ Connection failed: HTTP {response.status_code}")
        except ImportError:
            print("⚠️  Install 'requests' library to test connection: pip install requests")
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            print("Make sure the Pi is running and accessible on your network")
    
    print("\n🎉 All done! Your NFC medication tracker is ready to use.")

if __name__ == "__main__":
    main()