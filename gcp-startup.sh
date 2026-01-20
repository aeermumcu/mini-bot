#!/bin/bash
set -e

# Update packages
apt-get update
apt-get install -y python3 python3-pip python3-venv git

# Clone the repo
cd /opt
git clone https://github.com/aeermumcu/mini-bot.git
cd mini-bot

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browser
playwright install chromium --with-deps

# Create systemd service for auto-restart
cat > /etc/systemd/system/mini-monitor.service << 'EOF'
[Unit]
Description=Mini Countryman E Monitor
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/mini-bot
ExecStart=/opt/mini-bot/venv/bin/python3 /opt/mini-bot/mini_monitor.py
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

# Enable and start the service
systemctl daemon-reload
systemctl enable mini-monitor
systemctl start mini-monitor
