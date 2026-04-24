#!/bin/bash

# Create necessary directories
mkdir -p docs 

# Check if backend directory exists
if [ ! -d "backend" ]; then
    echo "Error: backend directory not found"
    exit 1
fi

echo "Starting Course Materials RAG System..."
echo "Make sure you have set your ANTHROPIC_API_KEY in .env"

# Change to backend directory and start the server
LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
echo ""
echo "  Local:   http://localhost:8000"
echo "  Network: http://${LOCAL_IP}:8000  (use this on your iPhone)"
echo ""

cd backend && uv run uvicorn app:app --reload --host 0.0.0.0 --port 8000