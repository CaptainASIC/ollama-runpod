#!/bin/bash
# scripts/model-manager.sh - Utility for managing Ollama models

# Load runtime environment if available
if [ -f "/workspace/config/runtime.env" ]; then
    source /workspace/config/runtime.env
fi

# Set default values for environment variables if not already set
OLLAMA_HOST=${OLLAMA_HOST:-"0.0.0.0"}
LOG_LEVEL=${LOG_LEVEL:-"INFO"}
OLLAMA_MODELS=${OLLAMA_MODELS:-""}

# Export Ollama variables
if [ -n "$OLLAMA_MODELS" ]; then
    export OLLAMA_MODELS
fi
export OLLAMA_HOST

# Ensure logs directory exists
mkdir -p /workspace/logs
LOG_FILE="/workspace/logs/model-manager.log"

# Define color codes for better output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Logging function
log() {
    local level=$1
    local message=$2
    local color=$NC
    
    case $level in
        INFO) color=$BLUE ;;
        SUCCESS) color=$GREEN ;;
        WARNING) color=$YELLOW ;;
        ERROR) color=$RED ;;
    esac
    
    echo -e "${color}[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $message${NC}" | tee -a "$LOG_FILE"
}

# Ensure jq is installed
ensure_jq() {
    if ! command -v jq >/dev/null 2>&1; then
        log "INFO" "Installing jq..."
        apt-get update && apt-get install -y jq
        if [ $? -ne 0 ]; then
            log "ERROR" "Failed to install jq. Some functionality may be limited."
            return 1
        fi
    fi
    return 0
}

# Function to list available models in the Ollama library
list_available_models() {
    log "INFO" "Fetching available models from Ollama library..."
    
    ensure_jq || return 1
    
    # Use curl to get the JSON response from Ollama's library API
    response=$(curl -s https://ollama.ai/api/tags)
    
    if [ -z "$response" ]; then
        log "ERROR" "Failed to fetch models from Ollama library. Check your internet connection."
        return 1
    fi
    
    # Parse and display the models
    model_count=$(echo "$response" | jq -r '.models | length')
    
    if [ -z "$model_count" ] || [ "$model_count" -eq 0 ]; then
        log "WARNING" "No models found in the Ollama library or unexpected API response format."
        return 1
    fi
    
    log "SUCCESS" "Found $model_count models in the Ollama library"
    echo -e "\n${GREEN}Available models:${NC}"
    echo "$response" | jq -r '.models[].name' | sort | nl
    
    return 0
}

# Function to list locally available models
list_local_models() {
    log "INFO" "Listing locally available models..."
    
    ensure_jq || return 1
    
    # Use Ollama's API to list local models
    response=$(curl -s http://localhost:11434/api/tags)
    
    if [ -z "$response" ]; then
        log "ERROR" "Failed to get response from Ollama API. Is Ollama running?"
        return 1
    fi
    
    # Check if the response contains models
    model_count=$(echo "$response" | jq '.models | length')
    
    if [ "$model_count" -eq 0 ]; then
        log "WARNING" "No models found locally. Use 'pull' command to download models."
        return 0
    fi
    
    log "SUCCESS" "Found $model_count models installed locally"
    echo -e "\n${GREEN}Locally available models:${NC}"
    echo "$response" | jq -r '.models[] | "\(.name) (\(.size/1024/1024 | floor) MB)"' | sort | nl
    
    return 0
}

# Function to pull a model
pull_model() {
    if [ -z "$1" ]; then
        log "WARNING" "Please specify a model name to pull"
        echo "Usage: $0 pull <model_name>"
        return 1
    fi
    
    model_name=$1
    log "INFO" "Pulling model: $model_name..."
    
    start_time=$(date +%s)
    
    # Check if model exists locally already
    local_check=$(curl -s http://localhost:11434/api/tags | jq -r ".models[] | select(.name == \"$model_name\") | .name")
    
    if [ -n "$local_check" ]; then
        log "WARNING" "Model '$model_name' is already installed locally."
        echo -e "${YELLOW}If you want to update it, use: ${NC}ollama pull $model_name:latest"
        return 0
    fi
    
    # Pull the model
    ollama pull "$model_name"
    pull_result=$?
    
    end_time=$(date +%s)
    duration=$((end_time - start_time))
    
    if [ $pull_result -eq 0 ]; then
        log "SUCCESS" "Successfully pulled model: $model_name (took $duration seconds)"
        return 0
    else
        log "ERROR" "Failed to pull model: $model_name"
        return 1
    fi
}

# Function to run a model with a prompt
run_model() {
    if [ -z "$1" ] || [ -z "$2" ]; then
        log "WARNING" "Please specify a model name and prompt"
        echo "Usage: $0 run <model_name> \"<your prompt>\""
        return 1
    fi
    
    model_name=$1
    prompt="${@:2}"
    
    log "INFO" "Running model: $model_name with prompt: '$prompt'"
    
    # Check if model exists locally
    local_check=$(curl -s http://localhost:11434/api/tags | jq -r ".models[] | select(.name == \"$model_name\") | .name")
    
    if [ -z "$local_check" ]; then
        log "WARNING" "Model '$model_name' is not installed locally. Would you like to pull it now? (y/n)"
        read -r response
        if [[ "$response" =~ ^[Yy]$ ]]; then
            pull_model "$model_name"
            if [ $? -ne 0 ]; then
                log "ERROR" "Failed to pull model. Cannot continue."
                return 1
            fi
        else
            log "ERROR" "Aborted. Model not available."
            return 1
        fi
    fi
    
    # Run the model with the prompt
    echo -e "\n${GREEN}Response from $model_name:${NC}\n"
    ollama run "$model_name" "$prompt"
    
    log "INFO" "Model execution completed"
    return 0
}

# Function to show help message
show_help() {
    echo -e "${GREEN}Ollama Model Manager${NC}"
    echo -e "${BLUE}A utility for managing Ollama models${NC}\n"
    echo "Usage: $0 [command] [options]"
    echo ""
    echo "Commands:"
    echo "  list-available    List all models available in the Ollama library"
    echo "  list              List locally available models"
    echo "  pull <model>      Pull a model from the Ollama library"
    echo "  run <model> <prompt>  Run a model with the specified prompt"
    echo "  help              Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 list-available               # Show all available models"
    echo "  $0 pull mistral                 # Download the Mistral model"
    echo "  $0 run llama2 \"Hello world\"     # Run the llama2 model"
}

# Main logic
case "$1" in
    list-available)
        list_available_models
        ;;
    list)
        list_local_models
        ;;
    pull)
        pull_model "$2"
        ;;
    run)
        run_model "${@:2}"
        ;;
    help|*)
        show_help
        ;;
esac