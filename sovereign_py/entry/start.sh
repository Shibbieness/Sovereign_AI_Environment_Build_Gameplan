#!/bin/bash

# ML Filesystem - Quick Start Script
# This script sets up and runs the ML Filesystem application

set -e

echo "╔══════════════════════════════════════════════════════════╗"
echo "║         ML Filesystem - Installation & Setup            ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# Check Python version
echo "→ Checking Python version..."
python3 --version || { echo "Error: Python 3 is required"; exit 1; }

# Check if .env exists
if [ ! -f .env ]; then
    echo ""
    echo "→ Creating .env file..."
    echo "⚠️  Please enter your Anthropic API key (or press Enter to skip):"
    read -p "API Key: " api_key
    
    if [ -n "$api_key" ]; then
        echo "ANTHROPIC_API_KEY=$api_key" > .env
    else
        echo "ANTHROPIC_API_KEY=your_api_key_here" > .env
        echo "⚠️  Warning: No API key provided. ML features will be limited."
    fi
    
    # Generate random secret key
    secret_key=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    echo "SECRET_KEY=$secret_key" >> .env
    
    echo "✓ .env file created"
fi

# Install dependencies
echo ""
echo "→ Installing Python dependencies..."
pip install -r requirements.txt --break-system-packages --quiet

echo "✓ Dependencies installed"

# Initialize database
echo ""
echo "→ Initializing database..."
python3 models.py

echo "✓ Database initialized"

# Create necessary directories
echo ""
echo "→ Creating directories..."
mkdir -p sandbox
mkdir -p chroma_db
mkdir -p templates
mkdir -p static

echo "✓ Directories created"

# Check if templates/index.html needs to be created
if [ ! -f templates/index.html ]; then
    echo ""
    echo "⚠️  Warning: templates/index.html not found"
    echo "Please ensure all project files are in place"
fi

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║              Installation Complete!                      ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "Default Login Credentials:"
echo "  Username: admin"
echo "  Password: admin"
echo ""
echo "⚠️  IMPORTANT: Change the default password after first login!"
echo ""

# Ask to start server
read -p "Start the server now? (y/n): " start_server

if [ "$start_server" = "y" ] || [ "$start_server" = "Y" ]; then
    echo ""
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║              Starting ML Filesystem Server              ║"
    echo "╚══════════════════════════════════════════════════════════╝"
    echo ""
    echo "Server will start on: http://localhost:5000"
    echo ""
    echo "Press Ctrl+C to stop the server"
    echo ""
    sleep 2
    python3 app.py
else
    echo ""
    echo "To start the server manually, run:"
    echo "  python3 app.py"
    echo ""
    echo "Then open: http://localhost:5000"
fi
