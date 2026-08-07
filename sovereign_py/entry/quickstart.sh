#!/bin/bash
# Quick Start Script for ML Filesystem v1.8

echo "================================================"
echo "ML Filesystem v1.8 - Quick Start"
echo "================================================"
echo ""

# Check Python version
echo "Checking Python version..."
python3 --version || { echo "Error: Python 3 not found"; exit 1; }

# Create virtual environment
echo ""
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate || . venv/Scripts/activate

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install -r requirements.txt

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo ""
    echo "Creating .env file..."
    cp .env.example .env
    echo "✓ Created .env file (edit if needed)"
fi

# Initialize directories
echo ""
echo "Creating directories..."
mkdir -p data/vector_store data/training_blocks sandbox

echo ""
echo "================================================"
echo "✓ Setup complete!"
echo "================================================"
echo ""
echo "To start the application:"
echo "  1. Activate venv: source venv/bin/activate"
echo "  2. Run: python app.py"
echo ""
echo "The system will:"
echo "  - Initialize database"
echo "  - Check for ML models"
echo "  - Offer to download models (if missing)"
echo "  - Start server on http://localhost:5000"
echo ""
echo "Default login: admin / admin"
echo ""
echo "Optional: Download ML models now"
echo "  python -c 'from ml.model_manager import MLModelManager; MLModelManager().download_models()'"
echo ""
echo "See README.md for full documentation"
echo "================================================"
