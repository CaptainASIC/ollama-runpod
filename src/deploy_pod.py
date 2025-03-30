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
            # For debugging
            # print(f"Query: {query_str}")
            # print(f"Variables: {json.dumps(variables, indent=2)}")
            
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
            
            data = response.json()
            
            # Check for GraphQL errors even with status 200
            if "errors" in data:
                print(f"GraphQL Error Response: {json.dumps(data['errors'], indent=2)}")
                # Return the data with errors so the caller can handle it
                return data
            
            return data
            
        except requests.exceptions.RequestException as e:
            print(f"Error communicating with RunPod API: {e}")
            sys.exit(1)
    
    def deploy_pod_web_format(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Use the exact format from the web interface"""
        print("Attempting deployment using web interface format...")
        
        # This query format is based on the actual requests made by the RunPod web interface
        query = """
        mutation OnDemandPodDeployMutation($input: OnDemandPodDeployInput!) {
            podDeployOnDemand(input: $input) {
                id
                name
                imageName
                templateId
                desiredStatus
                lastStatusChange
                env {
                    key
                    value
                }
                ports
                gpuCount
            }
        }
        """
        
        # Convert our config to the format used by the web interface
        web_config = {
            "containerDiskSize": config["containerDiskInGb"],
            "dockerArgs": "",
            "env": config["env"],
            "gpuCount": config["gpuCount"],
            "gpuTypeId": config["gpuTypeId"],
            "imageName": config["containerImageName"],
            "name": config["name"],
            "ports": config["ports"],
            "volumeSize": config["volumeInGb"],
            "volumeMountPath": config["volumeMountPath"]
        }
        
        try:
            result = self.query(query, {"input": web_config})
            
            if "errors" in result:
                print("Web format deployment failed:")
                for error in result["errors"]:
                    print(f"- {error['message']}")
                return None
            
            return result["data"]["podDeployOnDemand"]
        except Exception as e:
            print(f"Web format deployment failed: {e}")
            return None
    
    def deploy_pod_multi_attempt(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Try multiple deployment mutations until one succeeds"""
        print("Trying different RunPod API deployment methods...")
        
        # Try the web-based format first (most likely to work)
        web_result = self.deploy_pod_web_format(config)
        if web_result:
            print("Success with web interface format")
            return web_result
        
        # Try podGenerate 
        try:
            query = """
            mutation PodGenerate($input: PodGenerateInput!) {
              podGenerate(input: $input) {
                id
                name
                runtime {
                  uptimeSeconds
                  ports {
                    ip
                    publicPort
                  }
                }
                imageName
                templateId
              }
            }
            """
            
            print("Attempt 1: Using podGenerate mutation")
            
            # Adjust config for this mutation
            deploy_config = {
                "name": config["name"],
                "imageName": config["containerImageName"],
                "gpuCount": config["gpuCount"],
                "volumeSize": config["volumeInGb"],
                "containerDiskSize": config["containerDiskInGb"],
                "gpuType": config["gpuTypeId"],
                "env": config["env"],
                "ports": config["ports"],
                "volumeMountPath": config["volumeMountPath"]
            }
            
            result = self.query(query, {"input": deploy_config})
            
            if "errors" not in result and "data" in result and "podGenerate" in result["data"]:
                print("Success with podGenerate mutation")
                return result["data"]["podGenerate"]
            
        except Exception as e:
            print(f"Attempt 1 failed: {e}")
        
        # If that fails, try podDeploy
        try:
            query = """
            mutation podDeploy($input: PodDeployInput!) {
                podDeploy(input: $input) {
                    id
                    name
                    runtime {
                        ports {
                            ip
                            publicPort
                        }
                    }
                    imageName
                }
            }
            """
            
            print("Attempt 2: Using podDeploy mutation")
            
            # Adjust config for this mutation (might need different field names)
            deploy_config = {
                "name": config["name"],
                "imageName": config["containerImageName"],
                "gpuCount": config["gpuCount"],
                "volumeInGb": config["volumeInGb"],
                "containerDiskInGb": config["containerDiskInGb"],
                "gpuType": config["gpuTypeId"],
                "env": config["env"],
                "ports": config["ports"],
                "volumeMountPath": config["volumeMountPath"]
            }
            
            result = self.query(query, {"input": deploy_config})
            
            if "errors" not in result and "data" in result and "podDeploy" in result["data"]:
                print("Success with podDeploy mutation")
                return result["data"]["podDeploy"]
            
        except Exception as e:
            print(f"Attempt 2 failed: {e}")
        
        # Final attempt: podDeployOnDemand
        try:
            query = """
            mutation podDeployOnDemand($input: PodDeployOnDemandInput!) {
                podDeployOnDemand(input: $input) {
                    id
                    name
                    imageName
                }
            }
            """
            
            print("Attempt 3: Using podDeployOnDemand mutation")
            
            # Adjust config for this mutation
            deploy_config = {
                "cloudType": "ALL",
                "gpuCount": config["gpuCount"],
                "name": config["name"],
                "containerDiskSizeGB": config["containerDiskInGb"],
                "gpuType": config["gpuTypeId"],
                "volumeInGB": config["volumeInGb"],
                "volumeMountPath": config["volumeMountPath"],
                "containerImageName": config["containerImageName"],
                "env": config["env"],
                "ports": config["ports"]
            }
            
            result = self.query(query, {"input": deploy_config})
            
            if "errors" not in result and "data" in result and "podDeployOnDemand" in result["data"]:
                print("Success with podDeployOnDemand mutation")
                return result["data"]["podDeployOnDemand"]
            
        except Exception as e:
            print(f"Attempt 3 failed: {e}")
        
        # If all attempts fail
        print("All deployment attempts failed")
        sys.exit(1)


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
    
    # Correct GPU type format if needed
    gpu_type = args.gpu_type
    if "RTX 6000 Ada" in gpu_type and "Generation" not in gpu_type:
        gpu_type = "NVIDIA RTX 6000 Ada Generation"
        print(f"Note: Changed GPU type to '{gpu_type}' for compatibility")
    elif not gpu_type.startswith("NVIDIA ") and gpu_type not in ["A100", "A40", "V100"]:
        # Add NVIDIA prefix if needed for standard types
        gpu_type = f"NVIDIA {gpu_type}"
        print(f"Note: Changed GPU type to '{gpu_type}' for compatibility")
        
    # Format the pod configuration for podFindAndDeploy mutation
    return {
        "gpuCount": 1,
        "volumeInGb": args.volume_size_gb,
        "containerDiskInGb": args.container_disk_size_gb,
        "minVcpu": args.min_vcpu,
        "minMemoryInGb": args.min_memory_gb,
        "gpuTypeId": gpu_type,
        "containerImageName": args.image,
        "env": env_vars,
        "ports": "11434/http",
        "volumeMountPath": "/workspace",
        "name": args.name
    }

def display_pod_info(pod: Dict[str, Any], args: argparse.Namespace) -> None:
    """Display information about the deployed pod"""
    print("\n" + "="*50)
    print(f"Pod deployed successfully!")
    print("="*50)
    
    # Extract basic info
    pod_id = pod.get('id', 'Unknown')
    pod_name = pod.get('name', 'Unknown')
    image_name = pod.get('imageName', 'Unknown')
    
    # Extract runtime info if available
    runtime = pod.get('runtime', {})
    started_at = runtime.get('startedAt', 'Unknown')
    
    # Extract machine info if available
    machine = pod.get('machine', {})
    gpu_type = machine.get('gpuDisplayName', args.gpu_type)
    
    print(f"Pod ID: {pod_id}")
    print(f"Pod Name: {pod_name}")
    if started_at != 'Unknown':
        print(f"Started At: {started_at}")
    print(f"Container Image: {image_name}")
    print(f"GPU Type: {gpu_type}")
    
    print("\nConfiguration:")
    print(f"Auto-shutdown timeout: {args.timeout} seconds")
    
    print("\nEnvironment Variables:")
    print(f"OLLAMA_HOST: {args.ollama_host}")
    print(f"LOG_LEVEL: {args.log_level}")
    if args.preload_models:
        print(f"PRELOAD_MODELS: {args.preload_models}")
    if args.env_file:
        print(f"Additional variables loaded from: {args.env_file}")
    
    print("\nAccess Information:")
    print(f"Ollama API endpoint: https://{pod_id}-11434.proxy.runpod.net/")
    
    print("\nSample API Requests:")
    print(f"# List models")
    print(f"curl https://{pod_id}-11434.proxy.runpod.net/api/tags")
    print(f"\n# Generate text")
    print(f"curl -X POST https://{pod_id}-11434.proxy.runpod.net/api/generate \\")
    print(f"  -d '{{\"model\": \"mistral\", \"prompt\":\"Hello world!\"}}'\n")
    
    print(f"Auto-shutdown is configured for {args.timeout} seconds of inactivity.")
    print("="*50)

def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Deploy an Ollama pod on RunPod with auto-shutdown capability',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Basic deployment arguments
    parser.add_argument('--api-key', help='RunPod API key (optional if provided in env-file)')
    parser.add_argument('--gpu-type', default='NVIDIA RTX A5000', help='GPU type')
    parser.add_argument('--name', default='Ollama-Pod', help='Pod name')
    parser.add_argument('--timeout', type=int, default=60, 
                        help='Auto-shutdown timeout in seconds')
    parser.add_argument('--container-disk-size-gb', type=int, default=5, 
                        help='Container disk size in GB')
    parser.add_argument('--volume-size-gb', type=int, default=50,
                        help='Storage volume size in GB')
    parser.add_argument('--min-vcpu', type=int, default=2,
                        help='Minimum vCPU cores')
    parser.add_argument('--min-memory-gb', type=int, default=15,
                        help='Minimum memory in GB')
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
        
    # Check if API key looks like a valid RunPod API key
    if not api_key.startswith("rpa_"):
        print("Warning: API key doesn't start with 'rpa_'. This may not be a valid RunPod API key.")
        print(f"Current API key format: {api_key[:5]}...{api_key[-4:]}")
        confirm = input("Continue anyway? (y/n): ")
        if confirm.lower() not in ['y', 'yes']:
            print("Deployment cancelled.")
            return
    
    print(f"Deploying Ollama pod on RunPod with {args.gpu_type}...")
    
    # Display configuration summary
    print("\nDeployment configuration:")
    print(f"- Name: {args.name}")
    print(f"- GPU: {args.gpu_type}")
    print(f"- Auto-shutdown: {args.timeout} seconds")
    print(f"- System: {args.min_vcpu} vCPU, {args.min_memory_gb} GB RAM")
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
    try:
        # Try the multi-attempt approach which tries different mutations
        pod = client.deploy_pod_multi_attempt(pod_config)
    except Exception as e:
        print(f"Error deploying pod: {e}")
        sys.exit(1)
    
    # Display pod information
    display_pod_info(pod, args)


if __name__ == "__main__":
    main()