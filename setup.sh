#!/bin/bash
# CFO Silvia Pipeline - One-command setup
# Run: bash setup.sh

set -e

echo "=================================="
echo " CFO Silvia Pipeline Setup"
echo "=================================="
echo ""

# Python deps
echo "[1/3] Installing Python packages..."
pip install anthropic tweepy requests beautifulsoup4 playwright lxml 2>/dev/null || \
pip3 install anthropic tweepy requests beautifulsoup4 playwright lxml

# Playwright browser
echo "[2/3] Installing Chromium for card rendering..."
playwright install chromium

# Env file
echo "[3/3] Creating config..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "  Created .env from template. Fill in your API keys."
else
    echo "  .env already exists. Skipping."
fi

mkdir -p silvia_logs

echo ""
echo "=================================="
echo " Setup complete."
echo "=================================="
echo ""
echo " Next steps:"
echo "   1. Edit .env with your API keys"
echo "   2. Test:  python silvia_auto.py daily"
echo "   3. Cron:  python silvia_auto.py cron"
echo ""
echo " Commands:"
echo "   python silvia_auto.py earnings NVDA"
echo "   python silvia_auto.py macro CPI"
echo "   python silvia_auto.py daily"
echo "   python silvia_auto.py cron     # daemon mode"
echo ""
