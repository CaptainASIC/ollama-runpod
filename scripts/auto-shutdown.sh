#!/bin/bash
# scripts/auto-shutdown.sh - Monitor activity and shut down the pod if inactive

# Create logs directory if it doesn't exist
mkdir -p /workspace/logs

# Load environment variables
if [ -f "/workspace/config/runtime.env" ]; then
    source /workspace/config/runtime.env
fi

# Define the inactivity timeout in seconds (default: 60 seconds if not set)
INACTIVITY_TIMEOUT=${INACTIVITY_TIMEOUT:-60}
LOG_LEVEL=${LOG_LEVEL:-INFO}
LOG_FILE="/workspace/logs/autoshutdown.log"
ACTIVITY_THRESHOLD=${ACTIVITY_THRESHOLD:-5.0}  # CPU threshold to consider active

# Configure logging based on LOG_LEVEL
LOG_DEBUG=true
LOG_INFO=true
LOG_WARN=true
LOG_ERROR=true

case "$LOG_LEVEL" in
  DEBUG)
    # All logging enabled by default
    ;;
  INFO)
    LOG_DEBUG=false
    ;;
  WARNING|WARN)
    LOG_DEBUG=false
    LOG_INFO=false
    ;;
  ERROR)
    LOG_DEBUG=false
    LOG_INFO=false
    LOG_WARN=false
    ;;
  *)
    echo "Unknown LOG_LEVEL: $LOG_LEVEL, defaulting to INFO"
    LOG_DEBUG=false
    ;;
esac

# Log functions
log_debug() {
    if [ "$LOG_DEBUG" = true ]; then
        echo "$(date): [DEBUG] $1" | tee -a "$LOG_FILE"
    fi
}

log_info() {
    if [ "$LOG_INFO" = true ]; then
        echo "$(date): [INFO] $1" | tee -a "$LOG_FILE"
    fi
}

log_warn() {
    if [ "$LOG_WARN" = true ]; then
        echo "$(date): [WARN] $1" | tee -a "$LOG_FILE"
    fi
}

log_error() {
    if [ "$LOG_ERROR" = true ]; then
        echo "$(date): [ERROR] $1" | tee -a "$LOG_FILE"
    fi
}

# Function to check if there's any API activity
check_api_activity() {
    # Use netstat to check connections to the Ollama port
    if ! command -v netstat >/dev/null 2>&1; then
        apt-get update && apt-get install -y net-tools
    fi

    connections=$(netstat -ant | grep ":11434" | grep ESTABLISHED | wc -l)
    if [ "$connections" -gt 0 ]; then
        log_info "Active connections detected: $connections"
        return 0 # Activity detected
    fi
    return 1 # No activity
}

# Function to check if any Ollama operations are in progress
check_ollama_activity() {
    # Check if Ollama is using significant CPU (indicating active processing)
    ollama_pid=$(pgrep ollama)
    if [ -z "$ollama_pid" ]; then
        log_warn "Ollama process not found"
        return 1
    fi

    cpu_usage=$(ps -p "$ollama_pid" -o %cpu --no-headers 2>/dev/null | awk '{s+=$1} END {print s}')
    
    if [[ -n "$cpu_usage" ]]; then
        log_debug "Ollama CPU usage: $cpu_usage% (threshold: $ACTIVITY_THRESHOLD%)"
        if [[ $(echo "$cpu_usage > $ACTIVITY_THRESHOLD" | bc -l) -eq 1 ]]; then
            log_info "Ollama CPU activity detected: $cpu_usage%"
            return 0 # Activity detected
        fi
    fi
    
    # Check for ongoing requests in Ollama logs
    if grep -q "streaming response" /workspace/logs/ollama.log 2>/dev/null; then
        last_stream=$(grep "streaming response" /workspace/logs/ollama.log | tail -1)
        log_info "Active streaming detected: $last_stream"
        return 0 # Activity detected
    fi
    
    return 1 # No activity
}

# Log start of monitoring
log_info "Starting inactivity monitoring. Pod will shut down after $INACTIVITY_TIMEOUT seconds of inactivity."

# Initialize the inactivity counter
inactivity_counter=0

# Main monitoring loop
while true; do
    if check_api_activity || check_ollama_activity; then
        # Activity detected, reset the counter
        if [ $inactivity_counter -gt 0 ]; then
            log_info "Activity detected, resetting inactivity counter."
        fi
        inactivity_counter=0
    else
        # No activity, increment the counter
        inactivity_counter=$((inactivity_counter + 5))
        
        # Log every 15 seconds
        if [ $((inactivity_counter % 15)) -eq 0 ]; then
            log_info "No activity detected for $inactivity_counter seconds."
        fi
        
        # Check if the inactivity threshold has been reached
        if [ $inactivity_counter -ge $INACTIVITY_TIMEOUT ]; then
            log_info "Inactivity threshold reached ($INACTIVITY_TIMEOUT seconds). Shutting down the pod..."
            
            # Use the RunPod API if key is available
            if [ -n "$RUNPOD_API_KEY" ]; then
                # Get the pod ID from the RunPod environment variables
                POD_ID=$(curl -s https://api.runpod.io/graphql/info | jq -r '.id')
                if [ -n "$POD_ID" ]; then
                    log_info "Terminating pod with ID: $POD_ID using RunPod API"
                    
                    response=$(curl -s "https://api.runpod.io/graphql?api_key=${RUNPOD_API_KEY}" \
                         -H "Content-Type: application/json" \
                         -d "{\"query\":\"mutation { podTerminate(input: {podId: \\\"$POD_ID\\\"}) { success } }\"}")
                    
                    success=$(echo "$response" | jq -r '.data.podTerminate.success')
                    if [ "$success" = "true" ]; then
                        log_info "Shutdown request successful. Pod will terminate shortly."
                    else
                        log_error "API shutdown failed: $response"
                        log_info "Falling back to system shutdown..."
                        sudo shutdown -h now
                    fi
                else
                    log_error "Could not determine pod ID."
                    log_info "Falling back to system shutdown..."
                    sudo shutdown -h now
                fi
            else
                log_info "RUNPOD_API_KEY not set. Using system shutdown..."
                sudo shutdown -h now
            fi
            break
        fi
    fi
    
    # Sleep for 5 seconds before checking again
    sleep 5
done