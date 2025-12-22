"""
API Key Management System for Internal Server-to-Server Communication

This module provides a secure way to generate and validate API keys for specific endpoints
with controlled access and no expiration.
"""

import hashlib
import secrets
import os
from datetime import datetime
from typing import Optional, Dict, List, Set
from fastapi import HTTPException, status
import json

# Configuration
API_KEYS_FILE = "data/api_keys.json"
API_KEY_LENGTH = 64  # 64 character API keys for security

class APIKeyManager:
    """Manages API keys for internal server-to-server communication"""
    
    def __init__(self):
        self.keys_file = API_KEYS_FILE
        self.keys: Dict[str, Dict] = {}
        self.load_keys()
    
    def load_keys(self):
        """Load API keys from storage"""
        try:
            if os.path.exists(self.keys_file):
                with open(self.keys_file, 'r') as f:
                    self.keys = json.load(f)
                print(f"[API_KEYS] Loaded {len(self.keys)} API keys from storage")
            else:
                self.keys = {}
                print("[API_KEYS] No existing API keys found, starting fresh")
        except Exception as e:
            print(f"[API_KEYS] Error loading keys: {e}")
            self.keys = {}
    
    def save_keys(self):
        """Save API keys to storage"""
        try:
            os.makedirs(os.path.dirname(self.keys_file), exist_ok=True)
            with open(self.keys_file, 'w') as f:
                json.dump(self.keys, f, indent=2)
            print(f"[API_KEYS] Saved {len(self.keys)} API keys to storage")
        except Exception as e:
            print(f"[API_KEYS] Error saving keys: {e}")
    
    def generate_api_key(self, name: str, description: str, allowed_endpoints: List[str]) -> str:
        """
        Generate a new API key with specific permissions
        
        Args:
            name: Human-readable name for the key
            description: Description of the key's purpose
            allowed_endpoints: List of endpoints this key can access
            
        Returns:
            str: The generated API key
        """
        # Generate a secure random API key
        api_key = secrets.token_urlsafe(API_KEY_LENGTH)
        
        # Create key metadata
        key_data = {
            "name": name,
            "description": description,
            "allowed_endpoints": allowed_endpoints,
            "created_at": datetime.utcnow().isoformat(),
            "last_used": None,
            "usage_count": 0,
            "is_active": True
        }
        
        # Store the key (hash the actual key for security)
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        self.keys[key_hash] = key_data
        
        # Save to storage
        self.save_keys()
        
        print(f"[API_KEYS] Generated new API key '{name}' with access to {len(allowed_endpoints)} endpoints")
        
        return api_key
    
    def validate_api_key(self, api_key: str, endpoint: str) -> Dict:
        """
        Validate an API key for a specific endpoint
        
        Args:
            api_key: The API key to validate
            endpoint: The endpoint being accessed
            
        Returns:
            Dict: Key metadata if valid
            
        Raises:
            HTTPException: If key is invalid or doesn't have access
        """
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key is required"
            )
        
        # Hash the provided key for comparison
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        if key_hash not in self.keys:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key"
            )
        
        key_data = self.keys[key_hash]
        
        # Check if key is active
        if not key_data.get("is_active", True):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key is deactivated"
            )
        
        # Check if endpoint is allowed
        if endpoint not in key_data["allowed_endpoints"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"API key does not have access to endpoint: {endpoint}"
            )
        
        # Update usage statistics
        key_data["last_used"] = datetime.utcnow().isoformat()
        key_data["usage_count"] += 1
        
        # Save updated data
        self.save_keys()
        
        return key_data
    
    def list_keys(self) -> List[Dict]:
        """List all API keys (without exposing the actual keys)"""
        return [
            {
                "name": data["name"],
                "description": data["description"],
                "allowed_endpoints": data["allowed_endpoints"],
                "created_at": data["created_at"],
                "last_used": data["last_used"],
                "usage_count": data["usage_count"],
                "is_active": data["is_active"]
            }
            for data in self.keys.values()
        ]
    
    def deactivate_key(self, key_hash: str) -> bool:
        """Deactivate an API key"""
        if key_hash in self.keys:
            self.keys[key_hash]["is_active"] = False
            self.save_keys()
            print(f"[API_KEYS] Deactivated API key: {self.keys[key_hash]['name']}")
            return True
        return False
    
    def delete_key(self, key_hash: str) -> bool:
        """Delete an API key permanently"""
        if key_hash in self.keys:
            key_name = self.keys[key_hash]["name"]
            del self.keys[key_hash]
            self.save_keys()
            print(f"[API_KEYS] Deleted API key: {key_name}")
            return True
        return False

# Global instance
api_key_manager = APIKeyManager()

def get_api_key_manager() -> APIKeyManager:
    """Get the global API key manager instance"""
    return api_key_manager

def validate_api_key_for_endpoint(api_key: str, endpoint: str) -> Dict:
    """
    Validate an API key for a specific endpoint
    
    Args:
        api_key: The API key from the request
        endpoint: The endpoint being accessed
        
    Returns:
        Dict: Key metadata if valid
    """
    return api_key_manager.validate_api_key(api_key, endpoint)

