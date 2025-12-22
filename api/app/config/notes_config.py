"""
Configuration settings for notes generation
"""
import os
from typing import Dict, Any

# Default token limits for different AI providers
DEFAULT_TOKEN_LIMITS = {
    "google": {
        "gemini-2.5-flash": 8192,
        "gemini-2.0-flash": 8192,
        "gemini-1.5-flash": 8192,
        "gemini-1.5-pro": 8192,
        "gemini-1.0-pro": 8192,
    },
    "openai": {
        "gpt-3.5-turbo": 4096,
        "gpt-4": 8192,
        "gpt-4-turbo": 128000,
        "gpt-4o": 128000,
    }
}

# Notes generation quality settings
NOTES_QUALITY_SETTINGS = {
    "high_quality": {

        "max_tokens": 32000,  # Higher token limit for comprehensive notes
        "temperature": 0.2,  # Lower temperature for more focused output
        "ensure_completeness": True,
        "truncation_detection": True,
    },
    "standard": {
        "max_tokens": 16000,  # Adequate tokens for complete notes
        "temperature": 0.3,
        "ensure_completeness": True,
        "truncation_detection": True,
    },
    "fast": {
        "max_tokens": 8000,  # Sufficient tokens for basic notes
        "temperature": 0.4,
        "ensure_completeness": True,
        "truncation_detection": True,
    }
}

def get_notes_config(quality: str = "standard", provider: str = None) -> Dict[str, Any]:
    """
    Get notes generation configuration based on quality level and provider
    
    Args:
        quality: Quality level ('high_quality', 'standard', 'fast')
        provider: AI provider ('google' or 'openai')
    
    Returns:
        Configuration dictionary
    """
    if quality not in NOTES_QUALITY_SETTINGS:
        quality = "standard"
    
    config = NOTES_QUALITY_SETTINGS[quality].copy()
    
    # Override with environment variables if set
    env_max_tokens = os.getenv("NOTES_MAX_TOKENS")
    if env_max_tokens:
        try:
            config["max_tokens"] = int(env_max_tokens)
        except ValueError:
            pass
    
    env_temperature = os.getenv("NOTES_TEMPERATURE")
    if env_temperature:
        try:
            config["temperature"] = float(env_temperature)
        except ValueError:
            pass
    
    return config

def get_provider_max_tokens(provider: str, model: str) -> int:
    """
    Get maximum tokens supported by a specific provider and model
    
    Args:
        provider: AI provider ('google' or 'openai')
        model: Model name
    
    Returns:
        Maximum tokens supported
    """
    if provider in DEFAULT_TOKEN_LIMITS:
        if model in DEFAULT_TOKEN_LIMITS[provider]:
            return DEFAULT_TOKEN_LIMITS[provider][model]
        # Return highest available for provider
        return max(DEFAULT_TOKEN_LIMITS[provider].values())
    
    # Default fallback
    return 4000 if provider == "openai" else 8192
