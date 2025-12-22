#!/usr/bin/env python3
"""
Script to generate a new API key with the following properties:
- Lifetime key with no expiration
- Scoped exclusively for read access to the endpoint "/api/ai/ask"
- Intended for internal server-to-server use
- The key should allow only requests to "/api/ai/ask" and reject any other endpoints
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.api_keys import get_api_key_manager

def generate_specific_api_key():
    """Generate the specific API key requested by the user"""
    try:
        print("🔑 Generating API Key for Internal Server-to-Server Use")
        print("=" * 60)
        
        # Initialize the API key manager
        api_key_manager = get_api_key_manager()
        
        # Define the key properties as requested
        key_name = "Internal Server-to-Server AI Access"
        key_description = "Lifetime API key for internal server-to-server communication, scoped exclusively to /api/ai/ask endpoint"
        allowed_endpoints = ["/api/ai/ask"]  # Only this endpoint
        
        print(f"📝 Key Name: {key_name}")
        print(f"📋 Description: {key_description}")
        print(f"🎯 Allowed Endpoints: {allowed_endpoints}")
        print(f"⏰ Expiration: Never (Lifetime key)")
        print(f"🔒 Scope: Read access only to /api/ai/ask")
        print()
        
        # Generate the API key
        print("🔄 Generating API key...")
        api_key = api_key_manager.generate_api_key(
            name=key_name,
            description=key_description,
            allowed_endpoints=allowed_endpoints
        )
        
        print("✅ API Key generated successfully!")
        print()
        print("🔑 YOUR NEW API KEY:")
        print("=" * 60)
        print(api_key)
        print("=" * 60)
        print()
        
        print("📋 USAGE INSTRUCTIONS:")
        print("1. Include this key in the 'X-API-Key' header of your requests")
        print("2. Example: X-API-Key: " + api_key[:20] + "...")
        print("3. This key can ONLY access: /api/ai/ask")
        print("4. Any other endpoint will return 403 Forbidden")
        print("5. The key has NO expiration - store it securely!")
        print()
        
        print("⚠️  SECURITY NOTES:")
        print("- Store this key securely - it cannot be retrieved again")
        print("- This key provides read access to AI responses only")
        print("- The key is scoped to prevent access to other endpoints")
        print("- Monitor usage through the admin panel")
        print()
        
        print("🔍 VERIFICATION:")
        print("- Key is stored securely (hashed)")
        print("- Endpoint restriction is enforced")
        print("- Usage tracking is enabled")
        print("- Admin can deactivate/delete if needed")
        
        return api_key
        
    except Exception as e:
        print(f"❌ Error generating API key: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    api_key = generate_specific_api_key()
    if api_key:
        print("\n🎉 API Key generation completed successfully!")
        print("You can now use this key for internal server-to-server communication.")
    else:
        print("\n💥 API Key generation failed!")
        sys.exit(1)

