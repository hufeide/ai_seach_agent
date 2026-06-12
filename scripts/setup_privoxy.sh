#!/bin/bash
#
# Privoxy SOCKS5 to HTTP proxy converter setup script
# 
# This script configures Privoxy to act as an HTTP proxy that forwards
# traffic to a SOCKS5 proxy. This is needed because Chrome/Playwright
# (used by Crawl4AI) does not support SOCKS5 proxies directly.
#
# Usage:
#   sudo ./scripts/setup_privoxy.sh [socks5_host] [socks5_port]
#
# Defaults:
#   SOCKS5 Host: 127.0.0.1
#   SOCKS5 Port: 1080
#   Privoxy HTTP port: 8118 (fixed)
#
# Example:
#   sudo ./scripts/setup_privoxy.sh 192.168.1.159 10808
#


set -e

# Default SOCKS5 host and port
SOCKS5_HOST="${1:-127.0.0.1}"
SOCKS5_PORT="${2:-1080}"
PRIVOXY_PORT="8118"
PRIVOXY_CONFIG="/etc/privoxy/config"
FORWARD_LINE="forward-socks5 / ${SOCKS5_HOST}:${SOCKS5_PORT} ."

echo "======================================"
echo "Privoxy SOCKS5 to HTTP Proxy Setup"
echo "======================================"
echo "SOCKS5 Host: ${SOCKS5_HOST}"
echo "SOCKS5 Port: ${SOCKS5_PORT}"
echo "HTTP Port: ${PRIVOXY_PORT}"
echo ""

# Check if running as root
if [ "$(id -u)" != "0" ]; then
    echo "ERROR: This script must be run as root (use sudo)"
    exit 1
fi

# Install Privoxy if not installed
echo "[1/4] Checking for Privoxy installation..."
if ! command -v privoxy &> /dev/null; then
    echo "Installing Privoxy..."
    apt-get update && apt-get install -y privoxy
else
    echo "Privoxy is already installed"
fi

# Check if forward rule already exists
echo "[2/4] Configuring SOCKS5 forwarding..."
if grep -q "^${FORWARD_LINE}" "${PRIVOXY_CONFIG}"; then
    echo "Forward rule already exists: ${FORWARD_LINE}"
else
    echo "Adding forward rule to ${PRIVOXY_CONFIG}..."
    echo "${FORWARD_LINE}" >> "${PRIVOXY_CONFIG}"
    echo "Forward rule added successfully"
fi

# Enable and start/restart Privoxy service
echo "[3/4] Starting Privoxy service..."
systemctl enable privoxy
systemctl restart privoxy

# Wait for service to start
sleep 2

# Verify service status
echo "[4/4] Verifying Privoxy status..."
if systemctl is-active --quiet privoxy; then
    echo ""
    echo "======================================"
    echo "✅ Privoxy setup completed successfully!"
    echo "======================================"
    echo ""
    echo "Configuration Summary:"
    echo "----------------------"
    echo "  SOCKS5 Proxy: socks5://${SOCKS5_HOST}:${SOCKS5_PORT}"
    echo "  HTTP Proxy:   http://127.0.0.1:${PRIVOXY_PORT}"
    echo ""
    echo "To use this proxy, set these environment variables:"
    echo "  export HTTP_PROXY=http://127.0.0.1:${PRIVOXY_PORT}"
    echo "  export HTTPS_PROXY=http://127.0.0.1:${PRIVOXY_PORT}"
    echo ""
    echo "Or update your .env file:"
    echo "  HTTP_PROXY=http://127.0.0.1:${PRIVOXY_PORT}"
    echo "  HTTPS_PROXY=http://127.0.0.1:${PRIVOXY_PORT}"
    echo ""
else
    echo ""
    echo "❌ Failed to start Privoxy service"
    echo "Please check logs: journalctl -u privoxy"
    exit 1
fi