import hashlib
import secrets
import json
import os
from datetime import datetime

# Create data directory
os.makedirs("data", exist_ok=True)

# Generate API key
api_key = secrets.token_urlsafe(64)

# Create key data
key_data = {
    "name": "Internal Server-to-Server AI Access",
    "description": "Lifetime API key for internal server-to-server communication, scoped exclusively to /api/ai/ask endpoint",
    "allowed_endpoints": ["/api/ai/ask"],
    "created_at": datetime.utcnow().isoformat(),
    "last_used": None,
    "usage_count": 0,
    "is_active": True
}

# Hash the key for storage
key_hash = hashlib.sha256(api_key.encode()).hexdigest()

# Load existing keys or create new
keys = {}
if os.path.exists("data/api_keys.json"):
    with open("data/api_keys.json", "r") as f:
        keys = json.load(f)

# Store the key
keys[key_hash] = key_data

# Save to file
with open("data/api_keys.json", "w") as f:
    json.dump(keys, f, indent=2)

print("API Key Generated Successfully!")
print("=" * 50)
print("Key Name: Internal Server-to-Server AI Access")
print("Allowed Endpoints: /api/ai/ask only")
print("Expiration: Never (Lifetime key)")
print("Scope: Read access only to /api/ai/ask")
print()
print("YOUR NEW API KEY:")
print("=" * 50)
print(api_key)
print("=" * 50)
print()
print("USAGE:")
print("1. Include in X-API-Key header")
print("2. Can ONLY access: /api/ai/ask")
print("3. Other endpoints return 403 Forbidden")
print("4. Store securely - cannot be retrieved again")

