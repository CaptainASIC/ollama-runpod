#!/bin/bash
# scripts/podman-build.sh - Build the Ollama RunPod container using Podman

# Set default values
IMAGE_NAME="ollama-runpod"
IMAGE_TAG="latest"
CONTAINERFILE="podman/Containerfile"

# Define color codes for better output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to show help message
show_help() {
    echo -e "${BLUE}Podman Build Script for Ollama RunPod${NC}"
    echo ""
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  -n, --name NAME      Set image name (default: ollama-runpod)"
    echo "  -t, --tag TAG        Set image tag (default: latest)"
    echo "  -f, --file FILE      Set containerfile path (default: podman/Containerfile)"
    echo "  -p, --push           Push the image after building"
    echo "  -r, --registry URL   Registry URL to push to"
    echo "  -e, --env-file FILE  Path to environment file for container build args"
    echo "  -m, --models LIST    Comma-separated list of models to include in image"
    echo "  -d, --dry-run        Show build command without executing"
    echo "  -h, --help           Show this help message"
    echo ""
    echo "Example:"
    echo "  $0 --name my-ollama --tag v1.0.0 --push --registry quay.io/myuser --env-file ./my-config.env"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        -n|--name)
            IMAGE_NAME="$2"
            shift
            shift
            ;;
        -t|--tag)
            IMAGE_TAG="$2"
            shift
            shift
            ;;
        -f|--file)
            CONTAINERFILE="$2"
            shift
            shift
            ;;
        -p|--push)
            PUSH_IMAGE=true
            shift
            ;;
        -r|--registry)
            REGISTRY_URL="$2"
            shift
            shift
            ;;
        -e|--env-file)
            ENV_FILE="$2"
            shift
            shift
            ;;
        -m|--models)
            PRELOAD_MODELS="$2"
            shift
            shift
            ;;
        -d|--dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# Check if podman is installed
if ! command -v podman &> /dev/null; then
    echo -e "${RED}Error: Podman is not installed. Please install it first.${NC}"
    echo "Visit https://podman.io/getting-started/installation for installation instructions."
    exit 1
fi

# Set full image name with registry if provided
if [ -n "$REGISTRY_URL" ]; then
    FULL_IMAGE_NAME="${REGISTRY_URL}/${IMAGE_NAME}:${IMAGE_TAG}"
else
    FULL_IMAGE_NAME="${IMAGE_NAME}:${IMAGE_TAG}"
fi

echo -e "${BLUE}Building container image:${NC} ${FULL_IMAGE_NAME}"
echo -e "${BLUE}Using containerfile:${NC} ${CONTAINERFILE}"

# Prepare build arguments
BUILD_ARGS=()

# Add environment file if specified
if [ -n "$ENV_FILE" ]; then
    if [ -f "$ENV_FILE" ]; then
        echo -e "${BLUE}Using environment file: ${ENV_FILE}${NC}"
        # Read environment file and add each non-comment line as a build arg
        while IFS= read -r line || [ -n "$line" ]; do
            # Skip comments and empty lines
            if [[ "$line" =~ ^[[:space:]]*# ]] || [[ -z "$line" ]]; then
                continue
            fi
            # Extract key and value
            if [[ "$line" == *"="* ]]; then
                key=$(echo "$line" | cut -d '=' -f 1)
                value=$(echo "$line" | cut -d '=' -f 2-)
                BUILD_ARGS+=("--build-arg" "${key}=${value}")
            fi
        done < "$ENV_FILE"
    else
        echo -e "${YELLOW}Warning: Environment file $ENV_FILE not found.${NC}"
    fi
fi

# Add preload models if specified
if [ -n "$PRELOAD_MODELS" ]; then
    echo -e "${BLUE}Setting preload models: ${PRELOAD_MODELS}${NC}"
    BUILD_ARGS+=("--build-arg" "PRELOAD_MODELS=${PRELOAD_MODELS}")
fi

# Build command
BUILD_CMD=(podman build)
BUILD_CMD+=(-t "${FULL_IMAGE_NAME}")
BUILD_CMD+=(-f "${CONTAINERFILE}")
BUILD_CMD+=(--format docker)
BUILD_CMD+=("${BUILD_ARGS[@]}")
BUILD_CMD+=(.)

# Show the build command
echo -e "${YELLOW}Build command:${NC}"
echo "${BUILD_CMD[@]}"

# Execute the build command if not in dry run mode
if [ "$DRY_RUN" = true ]; then
    echo -e "${BLUE}Dry run mode. Skipping build.${NC}"
else
    echo -e "${YELLOW}Starting build process...${NC}"
    "${BUILD_CMD[@]}"
fi

# Check if build was successful
if [ $? -eq 0 ]; then
    echo -e "${GREEN}Build completed successfully!${NC}"
    
    # Show image information
    echo -e "${BLUE}Image details:${NC}"
    podman image inspect "${FULL_IMAGE_NAME}" --format '{{.Id}} {{.Size}}'
    
    # Push the image if requested
    if [ "$PUSH_IMAGE" = true ]; then
        if [ -z "$REGISTRY_URL" ]; then
            echo -e "${YELLOW}Warning: No registry URL provided. Using default registry.${NC}"
        fi
        
        echo -e "${BLUE}Pushing image to ${FULL_IMAGE_NAME}...${NC}"
        podman push "${FULL_IMAGE_NAME}"
        
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}Image successfully pushed to ${FULL_IMAGE_NAME}${NC}"
        else
            echo -e "${RED}Error pushing image. Please check your authentication and network connection.${NC}"
            exit 1
        fi
    fi
else
    echo -e "${RED}Build failed!${NC}"
    exit 1
fi

echo -e "${GREEN}Process completed.${NC}"
echo -e "${BLUE}To run this container:${NC}"
echo "podman run -p 11434:11434 ${FULL_IMAGE_NAME}"