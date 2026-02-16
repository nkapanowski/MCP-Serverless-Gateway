#!/bin/bash
# Setup script for EC2 deployment
# NOTE: This script is designed for Debian/Ubuntu-based systems only

set -e

echo "Setting up MCP Gateway on EC2 (Ubuntu/Debian)..."

# Check if running on Debian/Ubuntu
if ! command -v apt-get &> /dev/null; then
    echo "Error: This script requires a Debian/Ubuntu-based system with apt-get"
    exit 1
fi

# Update system
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv

# Create application directory
sudo mkdir -p /opt/mcp-gateway
sudo chown -R $USER:$USER /opt/mcp-gateway

# Copy application files
cp -r ../../* /opt/mcp-gateway/

# Create virtual environment
cd /opt/mcp-gateway
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create systemd service
sudo tee /etc/systemd/system/mcp-gateway.service > /dev/null <<EOF
[Unit]
Description=MCP Gateway Server
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/opt/mcp-gateway
Environment="PATH=/opt/mcp-gateway/venv/bin"
ExecStart=/opt/mcp-gateway/venv/bin/python deployments/ec2/server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable mcp-gateway
sudo systemctl start mcp-gateway

echo "MCP Gateway deployed and running on EC2"
echo "Check status: sudo systemctl status mcp-gateway"
echo "View logs: sudo journalctl -u mcp-gateway -f"
