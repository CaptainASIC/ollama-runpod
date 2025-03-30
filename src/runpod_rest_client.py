#!/usr/bin/env python3
"""
runpod_rest_client.py - RunPod REST API client for deploying pods
"""

import requests
import json
import sys
from typing import Dict, Any, Optional

class RunPodRestClient:
    """Client for interacting with RunPod REST API"""
    
    def __init__(self, api_key: str):
        """Initialize with API key"""
        self.api_key = api_key
        self.base_url = "https://rest.runpod.io/v1"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
    
    def verify_api_key(self) -> bool:
        """Verify that the API key is valid by making a simple request"""
        try:
            # Try to list pods as a simple check
            response = requests.get(
                f"{self.base_url}/pods",
                headers=self.headers
            )
            
            if response.status_code != 200:
                print(f"API Key verification failed: {response.status_code} - {response.text}")
                return False
            
            # Any 200 response means the API key is valid
            print(f"API Key verified successfully!")
            return True
            
        except Exception as e:
            print(f"API Key verification failed: {e}")
            return False
    
    def deploy_pod(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Deploy a pod using the REST API"""
        try:
            print(f"Sending pod deployment request to RunPod REST API")
            
            # Convert env list to object (dictionary)
            env_dict = {}
            if "env" in config and isinstance(config["env"], list):
                for env_var in config["env"]:
                    if "key" in env_var and "value" in env_var:
                        env_dict[env_var["key"]] = env_var["value"]
            
            # Convert ports string to array
            ports_array = []
            if "ports" in config and isinstance(config["ports"], str):
                # Split by comma if multiple ports are provided
                port_strings = config["ports"].split(",")
                for port_str in port_strings:
                    port_str = port_str.strip()
                    if "/" in port_str:
                        port, protocol = port_str.split("/", 1)
                        ports_array.append({
                            "port": int(port),
                            "protocol": protocol.strip().upper()
                        })
                    else:
                        # Default to TCP if protocol not specified
                        ports_array.append({
                            "port": int(port_str),
                            "protocol": "TCP"
                        })
            
            # Format the config for the REST API
            rest_config = {
                "name": config.get("name", "Ollama-Pod"),
                "imageName": config.get("containerImageName", "runpod/pytorch:latest"),
                "gpuCount": config.get("gpuCount", 1),
                "volumeInGb": config.get("volumeInGb", 50),
                "containerDiskInGb": config.get("containerDiskInGb", 5),
                "gpuTypeId": config.get("gpuTypeId", "NVIDIA RTX A5000"),
                "env": env_dict,
                "ports": ports_array,
                "volumeMountPath": config.get("volumeMountPath", "/workspace")
            }
            
            # Print request data for debugging
            print(f"Request URL: {self.base_url}/pods")
            print(f"Request body: {json.dumps(rest_config, indent=2)}")
            
            # Send request to create pod
            response = requests.post(
                f"{self.base_url}/pods", 
                headers=self.headers, 
                json=rest_config
            )
            
            # Check for errors
            if response.status_code != 200:
                print(f"REST API Error - Status Code: {response.status_code}")
                print(f"Response: {response.text}")
                raise Exception(f"Failed to deploy pod: {response.text}")
            
            # Parse response
            pod_data = response.json()
            print(f"Pod deployed successfully via REST API!")
            
            return pod_data
            
        except Exception as e:
            print(f"Error deploying pod: {e}")
            raise