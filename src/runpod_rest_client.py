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
            
            # Check if we got a valid response
            data = response.json()
            if "pods" in data:
                print(f"API Key verified successfully!")
                return True
            
            return False
            
        except Exception as e:
            print(f"API Key verification failed: {e}")
            return False
    
    def deploy_pod(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Deploy a pod using the REST API"""
        try:
            print(f"Sending pod deployment request to RunPod REST API")
            
            # Format the config for the REST API
            rest_config = {
                "name": config.get("name", "Ollama-Pod"),
                "imageName": config.get("containerImageName", "runpod/pytorch:latest"),
                "gpuCount": config.get("gpuCount", 1),
                "volumeInGb": config.get("volumeInGb", 50),
                "containerDiskInGb": config.get("containerDiskInGb", 5),
                "gpuTypeId": config.get("gpuTypeId", "NVIDIA RTX A5000"),
                "env": config.get("env", []),
                "ports": config.get("ports", "11434/http"),
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