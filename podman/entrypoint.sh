#!/bin/bash
# podman/entrypoint.sh - Container entrypoint

set -e

# Create necessary directories
mkdir -p /workspace/logs
mkdir -p /workspace/config

# Copy default configuration if it doesn't exist
if [ ! -f "/workspace/config/runtime.env" ]; then
    echo "No runtime configuration found. Copying default configuration..."
    cp /app/config/default.env /workspace/config/runtime.env
fi

# Load runtime configuration
source /workspace/config/runtime.env

# Set environment variables from config
export OLLAMA_HOST=${OLLAMA_HOST:-0.0.0.0}
export INACTIVITY_TIMEOUT=${INACTIVITY_TIMEOUT:-60}
export LOG_LEVEL=${LOG_LEVEL:-INFO}
export PRELOAD_MODELS=${PRELOAD_MODELS:-""}

echo "Starting Ollama RunPod with:"
echo "- OLLAMA_HOST: $OLLAMA_HOST"
echo "- INACTIVITY_TIMEOUT: $INACTIVITY_TIMEOUT seconds"
echo "- LOG_LEVEL: $LOG_LEVEL"
if [ -n "$PRELOAD_MODELS" ]; then
    echo "- PRELOAD_MODELS: $PRELOAD_MODELS"
fi

# Start the main startup script
/app/scripts/startup.sh