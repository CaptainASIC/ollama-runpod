#!/bin/bash
# scripts/startup.sh - Primary startup script for Ollama RunPod

# Create logs directory
mkdir -p /workspace/logs

# Output to log file and console
exec > >(tee -a /workspace/logs/startup.log) 2>&1

echo "$(date): Starting Ollama setup on RunPod..."

# Source configurations if available
if [ -f "/workspace/config/runtime.env" ]; then
    echo "$(date): Loading configuration from /workspace/config/runtime.env"
    source /workspace/config/runtime.env
fi

# Set default values if not specified in config
INACTIVITY_TIMEOUT=${INACTIVITY_TIMEOUT:-60}
OLLAMA_HOST=${OLLAMA_HOST:-0.0.0.0}

# Install required packages
echo "$(date): Installing required packages..."
apt-get update
apt-get install -y lshw curl jq procps net-tools bc

# Check if Ollama is already installed
if command -v ollama >/dev/null 2>&1; then
    echo "$(date): Ollama is already installed"
else
    echo "$(date): Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
    echo "$(date): Ollama installation completed"
fi

# Ensure OLLAMA_HOST is set
export OLLAMA_HOST
echo "$(date): OLLAMA_HOST set to $OLLAMA_HOST"

# Start Ollama in the background
echo "$(date): Starting Ollama server..."
ollama serve > /workspace/logs/ollama.log 2>&1 &
OLLAMA_PID=$!
echo "$(date): Ollama server started with PID: $OLLAMA_PID"

# Wait for Ollama to be ready
echo "$(date): Waiting for Ollama server to be ready..."
max_attempts=20
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
        echo "$(date): Ollama server is ready"
        break
    fi
    attempt=$((attempt + 1))
    echo "$(date): Waiting for Ollama server... attempt $attempt/$max_attempts"
    sleep 3
done

if [ $attempt -eq $max_attempts ]; then
    echo "$(date): ERROR: Ollama server failed to start properly"
    exit 1
fi

# Export the inactivity timeout for the auto-shutdown script
export INACTIVITY_TIMEOUT

# Start the auto-shutdown script
echo "$(date): Starting auto-shutdown monitor with timeout: $INACTIVITY_TIMEOUT seconds..."
bash /workspace/scripts/auto-shutdown.sh > /workspace/logs/autoshutdown.log 2>&1 &
SHUTDOWN_PID=$!
echo "$(date): Auto-shutdown monitor started with PID: $SHUTDOWN_PID"

echo "$(date): Setup complete! Ollama is running and accessible at port 11434"
echo "$(date): Auto-shutdown will occur after $INACTIVITY_TIMEOUT seconds of inactivity"
echo "$(date): You can access the API at https://POD_ID-11434.proxy.runpod.net/"

# Keep the container running
tail -f /workspace/logs/startup.log