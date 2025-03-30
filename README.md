# Ollama on RunPod with Auto-Shutdown

A professional-grade implementation for running Ollama on RunPod GPU instances with automatic shutdown capability to optimize costs.

## Features

- Production-ready deployment of Ollama on RunPod GPU instances
- Smart auto-shutdown functionality that monitors inactivity (default: 60 seconds)
- Comprehensive API access through RunPod's proxy system
- Support for the full range of LLMs available through Ollama
- Configurable timeouts and resource allocation
- Built with Podman for daemonless container management

## Repository Structure

```
ollama-runpod/
├── scripts/        # Shell scripts for pod management
├── src/            # Source code for deployment utilities
├── podman/         # Podman container configuration
├── config/         # Configuration templates
└── docs/           # Documentation
```

## Quick Start

### Option 1: Deploy using Python script

```bash
# Clone this repository
git clone https://github.com/yourusername/ollama-runpod.git
cd ollama-runpod

# Install dependencies
pip install -r requirements.txt

# Deploy a pod (requires RunPod API key)
python src/deploy_pod.py --api-key YOUR_API_KEY
```

### Option 2: Build and Push Container with Podman

```bash
# Build the container image
./scripts/podman-build.sh --name ollama-runpod --tag latest

# Push to a registry (optional)
./scripts/podman-build.sh --name ollama-runpod --tag latest --push --registry quay.io/yourusername
```

### Option 3: Manual Deployment on RunPod

1. Log in to your RunPod account and select "+ GPU Pod"
2. Choose an appropriate GPU (A40 recommended for larger models)
3. Select a custom deployment with the following settings:
   - Container Image: `quay.io/yourusername/ollama-runpod:latest` (or your custom image)
   - Expose port: `11434` (required for Ollama API)
   - Set environment variables:
     - `OLLAMA_HOST=0.0.0.0`
     - `INACTIVITY_TIMEOUT=60` (seconds)
     - `RUNPOD_API_KEY=your_api_key` (for auto-shutdown)
4. Deploy the pod

## Auto-Shutdown Functionality

The pod automatically monitors activity and will shut down after the specified period of inactivity (default: 60 seconds) to optimize costs. Inactivity is determined by monitoring:

- API requests to the Ollama endpoint
- Terminal activity 
- Active model operations

## Documentation

- [Usage Guide](docs/USAGE.md) - Detailed usage instructions
- [Testing Guide](docs/TESTING.md) - Instructions for testing your deployment

## Development

### Building Container Image Locally

```bash
# Build with default settings
./scripts/podman-build.sh

# Build with custom name and tag
./scripts/podman-build.sh --name my-ollama --tag v1.0.0
```

### Running Locally with Podman

```bash
podman run -p 11434:11434 -e OLLAMA_HOST=0.0.0.0 -e INACTIVITY_TIMEOUT=60 ollama-runpod:latest
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.