#!/usr/bin/env python3
"""
deploy_pod.py - RunPod deployment utility for Ollama with auto-shutdown
"""

import argparse
import json
import os
import requests
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional

# Constants
API_URL = "https://api.runpod.io/graphql"
VERSION = "1.0.0"


class RunPodClient:
    """Client for interacting with RunPod API"""
    
    def __init__(self, api_key: str):
        """Initialize with API key"""
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
    
    def verify_api_key(self) -> bool:
        """Verify that the API key is valid by making a simple query"""
        try:
            query = """
            query {
                myself {
                    id
                    email
                }
            }
            """
            
            response = requests.post(
                API_URL,
                headers=self.headers,
                json={"query": query}
            )
            
            if response.status_code != 200:
                print(f"API Key verification failed: {response.status_code} - {response.text}")
                return False
                
            data = response.json()
            
            if "errors" in data:
                print(f"API Key verification failed: {data['errors'][0]['message']}")
                return False
                
            if "data" in data and "myself" in data["data"] and data["data"]["myself"]:
                print(f"API Key verified for user: {data['data']['myself'].get('email', 'Unknown')}")
                return True
                
            return False
            
        except Exception as e:
            print(f"API Key verification failed: {e}")
            return False
    
    def query(self, query_str: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        """Execute GraphQL query against RunPod API"""
        try:
            response = requests.post(
                API_URL,
                headers=self.headers,
                json={"query": query_str, "variables": variables}
            )
            
            # Print detailed debug information for any error
            if response.status_code != 200:
                print(f"API Error Status Code: {response.status_code}")
                print(f"API Error Response: {response.text}")
                print(f"Request data: {json.dumps({'query': query_str, 'variables': variables}, indent=2)}")
                response.raise_for_status()
            
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error communicating with RunPod API: {e}")
            sys.exit(1)
    
    def deploy_pod(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Deploy a pod with the given configuration"""
        query = """
        mutation podDeploy($input: PodDeployInput!) {
            podDeploy(input: $input) {
                id
                name
                runtime {
                    ports {
                        ip
                        isIpPublic
                        privatePort
                        publicPort
                    }
                    startedAt
                    uptimeSeconds
                }
                desiredStatus
                imageName
            }
        }
        """
        
        # Debug information
        print(f"Sending pod deployment request to RunPod API")
        
        result = self.query(query, {"input": config})
        
        if "errors" in result:
            print("Error deploying pod:")
            for error in result["errors"]:
                print(f"- {error['message']}")
            sys.exit(1)
        
        return result["data"]["podDeploy"]


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Deploy an Ollama pod on RunPod with auto-shutdown capability',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Basic deployment arguments
    parser.add_argument('--api-key', help='RunPod API key (optional if provided in env-file)')
    parser.add_argument('--gpu-type', default='NVIDIA A40', help='GPU type')
    parser.add_argument('--cloud-type', default='ALL', help='Cloud type')
    parser.add_argument('--name', default='Ollama-Pod', help='Pod name')
    parser.add_argument('--timeout', type=int, default=60, 
                        help='Auto-shutdown timeout in seconds')
    parser.add_argument('--container-disk-size-gb', type=int, default=5, 
                        help='Container disk size in GB')
    parser.add_argument('--volume-size-gb', type=int, default=50,
                        help='Storage volume size in GB')
    parser.add_argument('--image', default='runpod/pytorch:latest',
                        help='Container image to use')
    
    # Environment variable arguments
    parser.add_argument('--env-file', help='Path to environment file with KEY=VALUE pairs')
    parser.add_argument('--preload-models', help='Comma-separated list of models to preload (e.g., "mistral,llama2")')
    parser.add_argument('--log-level', default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                        help='Logging level')
    parser.add_argument('--ollama-host', default='0.0.0.0', help='Ollama host interface binding')
    
    # Other arguments
    parser.add_argument('--version', action='version', version=f'Ollama RunPod Deployer v{VERSION}')
    
    return parser.parse_args()


def load_env_file(file_path: str) -> Dict[str, str]:
    """Load environment variables from a file"""
    env_vars = {}
    if not file_path or not os.path.exists(file_path):
        return env_vars
    
    try:
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
    except Exception as e:
        print(f"Warning: Failed to fully parse env file: {e}")
    
    return env_vars

def create_pod_config(args: argparse.Namespace) -> Dict[str, Any]:
    """Create pod configuration from arguments"""
    # Start with required environment variables
    env_vars = [
        {
            "key": "OLLAMA_HOST",
            "value": args.ollama_host
        },
        {
            "key": "INACTIVITY_TIMEOUT",
            "value": str(args.timeout)
        },
        {
            "key": "RUNPOD_API_KEY",
            "value": args.api_key
        },
        {
            "key": "LOG_LEVEL",
            "value": args.log_level
        }
    ]
    
    # Add preload models if specified
    if args.preload_models:
        env_vars.append({
            "key": "PRELOAD_MODELS",
            "value": args.preload_models
        })
    
    # Load additional environment variables from file if specified
    if args.env_file:
        file_env_vars = load_env_file(args.env_file)
        for key, value in file_env_vars.items():
            # Skip variables we've already set
            if key in ["OLLAMA_HOST", "INACTIVITY_TIMEOUT", "RUNPOD_API_KEY", "LOG_LEVEL", "PRELOAD_MODELS"]:
                continue
            env_vars.append({
                "key": key,
                "value": value
            })
    
    # Format the pod configuration according to RunPod API requirements
    return {
        "deploymentType": "GPU",
        "gpuType": args.gpu_type,
        "cloudType": args.cloud_type,
        "name": args.name,
        "volumeInGb": args.volume_size_gb,
        "containerDiskInGb": args.container_disk_size_gb,
        "dockerArgs": "",
        "ports": "11434/http",
        "volumeMountPath": "/workspace",
        "imageName": args.image,
        "env": env_vars
    }


def display_pod_info(pod: Dict[str, Any], args: argparse.Namespace) -> None:
    """Display information about the deployed pod"""
    print("\n" + "="*50)
    print(f"Pod deployed successfully!")
    print("="*50)
    print(f"Pod ID: {pod['id']}")
    print(f"Pod Name: {pod['name']}")
    print(f"Started At: {pod['runtime']['startedAt']}")
    print(f"Container Image: {pod['imageName']}")
    
    print("\nConfiguration:")
    print(f"Auto-shutdown timeout: {args.timeout} seconds")
    print(f"GPU Type: {args.gpu_type}")
    
    print("\nEnvironment Variables:")
    print(f"OLLAMA_HOST: {args.ollama_host}")
    print(f"LOG_LEVEL: {args.log_level}")
    if args.preload_models:
        print(f"PRELOAD_MODELS: {args.preload_models}")
    if args.env_file:
        print(f"Additional variables loaded from: {args.env_file}")
    
    print("\nAccess Information:")
    print(f"Ollama API endpoint: https://{pod['id']}-11434.proxy.runpod.net/")
    
    print("\nSample API Requests:")
    print(f"# List models")
    print(f"curl https://{pod['id']}-11434.proxy.runpod.net/api/tags")
    print(f"\n# Generate text")
    print(f"curl -X POST https://{pod['id']}-11434.proxy.runpod.net/api/generate \\")
    print(f"  -d '{{\"model\": \"mistral\", \"prompt\":\"Hello world!\"}}'\n")
    
    print(f"Auto-shutdown is configured for {timeout} seconds of inactivity.")
    print("="*50)


def main() -> None:
    """Main entry point"""
    print(f"Ollama RunPod Deployer v{VERSION}")
    args = parse_arguments()
    
    # Check for API key in env file if not provided directly
    api_key = args.api_key
    if not api_key and args.env_file:
        env_vars = load_env_file(args.env_file)
        if 'RUNPOD_API_KEY' in env_vars:
            api_key = env_vars['RUNPOD_API_KEY']
            print("Using API key from environment file")
    
    # Verify we have an API key from somewhere
    if not api_key:
        print("Error: RunPod API key is required. Provide it with --api-key or in your environment file.")
        sys.exit(1)
    
    # Validate API key format
    api_key = api_key.strip()
    if not api_key:
        print("Error: RunPod API key is empty.")
        sys.exit(1)
    
    print(f"Deploying Ollama pod on RunPod with {args.gpu_type}...")
    
    # Display configuration summary
    print("\nDeployment configuration:")
    print(f"- Name: {args.name}")
    print(f"- GPU: {args.gpu_type}")
    print(f"- Auto-shutdown: {args.timeout} seconds")
    if args.preload_models:
        print(f"- Preload models: {args.preload_models}")
    if args.env_file:
        print(f"- Environment file: {args.env_file}")
    
    # Ask for confirmation
    confirm = input("\nProceed with deployment? (y/n): ")
    if confirm.lower() not in ['y', 'yes']:
        print("Deployment cancelled.")
        return
    
    # Use API key from environment or command line
    client = RunPodClient(api_key)
    
    # Verify API key is valid
    print("Verifying RunPod API key...")
    if not client.verify_api_key():
        print("Error: Invalid RunPod API key. Please check your API key and try again.")
        sys.exit(1)
    
    # Store API key in args for config creation
    args.api_key = api_key
    
    # Create pod configuration
    pod_config = create_pod_config(args)
    
    # Deploy pod
    print("Deploying pod... (this may take a minute)")
    pod = client.deploy_pod(pod_config)
    
    # Display pod information
    display_pod_info(pod, args)


if __name__ == "__main__":
    main()