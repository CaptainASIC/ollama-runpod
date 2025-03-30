#!/bin/bash
# scripts/create-config.sh - Interactive script to create a custom environment configuration

# Define color codes for better output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Default values
OUTPUT_FILE="config/my-config.env"
DEFAULT_TIMEOUT=60
DEFAULT_LOG_LEVEL="INFO"
DEFAULT_HOST="0.0.0.0"

# Check for command line arguments
while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        -o|--output)
            OUTPUT_FILE="$2"
            shift
            shift
            ;;
        -h|--help)
            echo -e "${BLUE}Create Config - Interactive environment configuration creator${NC}"
            echo ""
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  -o, --output FILE    Output file path (default: config/my-config.env)"
            echo "  -h, --help           Show this help message"
            echo ""
            echo "Example:"
            echo "  $0 --output ./my-custom-config.env"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Create output directory if it doesn't exist
mkdir -p "$(dirname "$OUTPUT_FILE")"

# Check if file already exists
if [ -f "$OUTPUT_FILE" ]; then
    echo -e "${YELLOW}Warning: File $OUTPUT_FILE already exists.${NC}"
    read -p "Do you want to overwrite it? (y/n): " overwrite
    if [[ ! "$overwrite" =~ ^[Yy]$ ]]; then
        echo -e "${BLUE}Operation cancelled.${NC}"
        exit 0
    fi
fi

# Start creating the config file
echo -e "${BLUE}Creating configuration file: $OUTPUT_FILE${NC}"
echo -e "${YELLOW}Press Enter to accept default values${NC}"
echo ""

# Initialize the file with a header
cat > "$OUTPUT_FILE" << EOL
# Ollama RunPod configuration
# Generated on $(date)
# ----------------------------------

EOL

# Function to prompt for a value with default
prompt_value() {
    local prompt="$1"
    local default="$2"
    local var_name="$3"
    local description="$4"
    
    if [ -n "$description" ]; then
        echo -e "${BLUE}# $description${NC}"
    fi
    
    read -p "$prompt [$default]: " value
    value=${value:-$default}
    
    echo "" >> "$OUTPUT_FILE"
    if [ -n "$description" ]; then
        echo "# $description" >> "$OUTPUT_FILE"
    fi
    echo "$var_name=$value" >> "$OUTPUT_FILE"
    echo -e "${GREEN}Set $var_name=$value${NC}"
}

# Host configuration
prompt_value "Ollama host binding" "$DEFAULT_HOST" "OLLAMA_HOST" "Network interface to bind Ollama server to"

# Auto-shutdown timeout
prompt_value "Auto-shutdown timeout (seconds)" "$DEFAULT_TIMEOUT" "INACTIVITY_TIMEOUT" "Duration of inactivity before shutting down the pod"

# Log level
echo -e "${BLUE}# Logging verbosity level${NC}"
echo -e "${YELLOW}Available options: DEBUG, INFO, WARNING, ERROR${NC}"
read -p "Log level [INFO]: " log_level
log_level=${log_level:-$DEFAULT_LOG_LEVEL}
echo "" >> "$OUTPUT_FILE"
echo "# Logging verbosity level" >> "$OUTPUT_FILE"
echo "LOG_LEVEL=$log_level" >> "$OUTPUT_FILE"
echo -e "${GREEN}Set LOG_LEVEL=$log_level${NC}"

# Preload models
read -p "Preload models (comma-separated, e.g., mistral,llama2:7b) [none]: " preload_models
if [ -n "$preload_models" ]; then
    echo "" >> "$OUTPUT_FILE"
    echo "# Models to preload on startup" >> "$OUTPUT_FILE"
    echo "PRELOAD_MODELS=$preload_models" >> "$OUTPUT_FILE"
    echo -e "${GREEN}Set PRELOAD_MODELS=$preload_models${NC}"
fi

# Activity threshold
read -p "CPU activity threshold (%) [5.0]: " activity_threshold
activity_threshold=${activity_threshold:-5.0}
echo "" >> "$OUTPUT_FILE"
echo "# CPU usage threshold to detect activity" >> "$OUTPUT_FILE"
echo "ACTIVITY_THRESHOLD=$activity_threshold" >> "$OUTPUT_FILE"
echo -e "${GREEN}Set ACTIVITY_THRESHOLD=$activity_threshold${NC}"

# RunPod API key
read -p "Do you want to add a RunPod API key for auto-shutdown? (y/n) [n]: " add_api_key
if [[ "$add_api_key" =~ ^[Yy]$ ]]; then
    read -p "RunPod API key: " api_key
    if [ -n "$api_key" ]; then
        echo "" >> "$OUTPUT_FILE"
        echo "# RunPod API key for auto-shutdown functionality" >> "$OUTPUT_FILE"
        echo "RUNPOD_API_KEY=$api_key" >> "$OUTPUT_FILE"
        echo -e "${GREEN}Set RUNPOD_API_KEY=*****${NC}"
    fi
fi

# Custom pod name
read -p "Custom pod name [Ollama-RunPod]: " pod_name
pod_name=${pod_name:-"Ollama-RunPod"}
echo "" >> "$OUTPUT_FILE"
echo "# Custom pod name for easier identification" >> "$OUTPUT_FILE"
echo "POD_NAME=$pod_name" >> "$OUTPUT_FILE"
echo -e "${GREEN}Set POD_NAME=$pod_name${NC}"

# Advanced Ollama configuration
read -p "Do you want to configure advanced Ollama settings? (y/n) [n]: " advanced_config
if [[ "$advanced_config" =~ ^[Yy]$ ]]; then
    # Models directory
    read -p "Custom models directory [default Ollama location]: " models_dir
    if [ -n "$models_dir" ]; then
        echo "" >> "$OUTPUT_FILE"
        echo "# Custom directory for model storage" >> "$OUTPUT_FILE"
        echo "OLLAMA_MODELS=$models_dir" >> "$OUTPUT_FILE"
        echo -e "${GREEN}Set OLLAMA_MODELS=$models_dir${NC}"
    fi
    
    # GPU layers
    read -p "GPU layers limit (leave empty for default): " gpu_layers
    if [ -n "$gpu_layers" ]; then
        echo "" >> "$OUTPUT_FILE"
        echo "# Number of layers to run on GPU" >> "$OUTPUT_FILE"
        echo "OLLAMA_GPU_LAYERS=$gpu_layers" >> "$OUTPUT_FILE"
        echo -e "${GREEN}Set OLLAMA_GPU_LAYERS=$gpu_layers${NC}"
    fi
fi

echo -e "\n${GREEN}Configuration file created successfully: $OUTPUT_FILE${NC}"
echo -e "${BLUE}You can use this file with:${NC}"
echo "  - Python deployment: --env-file $OUTPUT_FILE"
echo "  - Podman build: --env-file $OUTPUT_FILE"
echo "  - Copy to pod: cp $OUTPUT_FILE /workspace/config/runtime.env"