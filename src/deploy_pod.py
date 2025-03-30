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
            "Authorization": api_key
        }
    
    def query(self, query_str: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        """Execute GraphQL query against RunPod API"""
        try:
            response = requests.post(
                API_URL,
                headers=self.headers,
                json={"query": query_str, "variables": variables}
            )
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error communicating with RunPod API: {e}")
            sys.exit(1)
    
    def deploy_pod(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Deploy a pod with the given configuration"""
        query = """
        mutation podDeployOnDemand($input: PodDeployOnDemandInput!) {
            podDeployOnDemand(input: $input) {
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
        
        result = self.query(query, {"input": config})
        
        if "errors" in result:
            print("Error deploying pod:")
            for error in result["errors"]:
                print(f"- {error['message']}")
            sys.exit(1)
        
        return result["data"]["podDeployOnDemand"]


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Deploy an Ollama pod on RunPod with auto-shutdown capability',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument('--api-key', required=True, help='RunPod API key')
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
    parser.add_argument('--version', action='version', version=f'Ollama RunPod Deployer v{VERSION}')
    
    return parser.parse_args()


def create_pod_config(args: argparse.Namespace) -> Dict[str, Any]:
    """Create pod configuration from arguments"""
    return {
        "cloudType": args.cloud_type,
        "gpuCount": 1,
        "name": args.name,
        "containerDiskSizeGB": args.container_disk_size_gb,
        "gpuType": args.gpu_type,
        "volumeInGB": args.volume_size_gb,
        "volumeMountPath": "/workspace",
        "containerImageName": args.image,
        "dockerArgs": "",
        "ports": "11434/http",
        "env": [
            {
                "key": "OLLAMA_HOST",
                "value": "0.0.0.0"
            },
            {
                "key": "INACTIVITY_TIMEOUT",
                "value": str(args.timeout)
            },
            {
                "key": "RUNPOD_API_KEY",
                "value": args.api_key
            }
        ]
    }


def display_pod_info(pod: Dict[str, Any], timeout: int) -> None:
    """Display information about the deployed pod"""
    print("\n" + "="*50)
    print(f"Pod deployed successfully!")
    print("="*50)
    print(f"Pod ID: {pod['id']}")
    print(f"Pod Name: {pod['name']}")
    print(f"Started At: {pod['runtime']['startedAt']}")
    print(f"Container Image: {pod['imageName']}")
    
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
    
    print(f"Deploying Ollama pod on RunPod with {args.gpu_type}...")
    client = RunPodClient(args.api_key)
    
    # Create pod configuration
    pod_config = create_pod_config(args)
    
    # Deploy pod
    pod = client.deploy_pod(pod_config)
    
    # Display pod information
    display_pod_info(pod, args.timeout)


if __name__ == "__main__":
    main()