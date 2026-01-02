#!/usr/bin/env python3
"""
Test script for read-only mode
Run this while your FastAPI server is running locally
"""
import requests
import json
import sys

BASE_URL = "http://localhost:8001"

def test_get_request():
    """Test GET request - should work"""
    print("\n[TEST 1] Testing GET request (should work)...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
        if response.status_code == 200:
            print("   ✅ PASS - GET request works")
            return True
        else:
            print("   ❌ FAIL - GET request failed")
            return False
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return False

def test_post_request():
    """Test POST request - should be blocked"""
    print("\n[TEST 2] Testing POST request (should be blocked)...")
    try:
        response = requests.post(
            f"{BASE_URL}/api/documents/upload",
            json={}
        )
        print(f"   Status: {response.status_code}")
        print(f"   Response: {json.dumps(response.json(), indent=2)}")
        if response.status_code == 503:
            print("   ✅ PASS - POST request correctly blocked")
            return True
        else:
            print("   ❌ FAIL - POST request should return 503")
            return False
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return False

def test_put_request():
    """Test PUT request - should be blocked"""
    print("\n[TEST 3] Testing PUT request (should be blocked)...")
    try:
        response = requests.put(
            f"{BASE_URL}/api/documents/123",
            json={}
        )
        print(f"   Status: {response.status_code}")
        print(f"   Response: {json.dumps(response.json(), indent=2)}")
        if response.status_code == 503:
            print("   ✅ PASS - PUT request correctly blocked")
            return True
        else:
            print("   ❌ FAIL - PUT request should return 503")
            return False
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return False

def test_delete_request():
    """Test DELETE request - should be blocked"""
    print("\n[TEST 4] Testing DELETE request (should be blocked)...")
    try:
        response = requests.delete(f"{BASE_URL}/api/documents/123")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {json.dumps(response.json(), indent=2)}")
        if response.status_code == 503:
            print("   ✅ PASS - DELETE request correctly blocked")
            return True
        else:
            print("   ❌ FAIL - DELETE request should return 503")
            return False
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return False

def test_health_endpoints():
    """Test health check endpoints - should work"""
    print("\n[TEST 5] Testing health check endpoints (should work)...")
    endpoints = ["/health", "/health/detailed", "/test"]
    all_passed = True
    
    for endpoint in endpoints:
        try:
            response = requests.get(f"{BASE_URL}{endpoint}")
            if response.status_code == 200:
                print(f"   ✅ {endpoint} - Works")
            else:
                print(f"   ❌ {endpoint} - Failed (status: {response.status_code})")
                all_passed = False
        except Exception as e:
            print(f"   ❌ {endpoint} - Error: {e}")
            all_passed = False
    
    return all_passed

def main():
    print("=" * 60)
    print("Read-Only Mode Test Suite")
    print("=" * 60)
    print("\nMake sure your FastAPI server is running on http://localhost:8001")
    print("Start it with: uvicorn app.main:app --reload --port 8001")
    print("\nStarting tests...")
    
    # Check if server is running
    print("Checking if server is running on http://localhost:8001...")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        print(f"✅ Server is running! (Status: {response.status_code})")
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Cannot connect to server!")
        print("   The server might not be running on port 8001")
        print("\nPlease start the server first:")
        print("  cd api")
        print("  uvicorn app.main:app --reload --port 8001")
        print("\nOr if your server is on a different port, update BASE_URL in this script.")
        sys.exit(1)
    except requests.exceptions.Timeout:
        print("\n❌ ERROR: Server connection timed out!")
        print("   The server might be slow to respond")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"\n❌ ERROR: {type(e).__name__}: {e}")
        print("Please start the server:")
        print("  cd api")
        print("  uvicorn app.main:app --reload --port 8001")
        sys.exit(1)
    
    results = []
    results.append(("GET Request", test_get_request()))
    results.append(("POST Request", test_post_request()))
    results.append(("PUT Request", test_put_request()))
    results.append(("DELETE Request", test_delete_request()))
    results.append(("Health Endpoints", test_health_endpoints()))
    
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name}: {status}")
    
    all_passed = all(result[1] for result in results)
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ All tests passed! Read-only mode is working correctly.")
    else:
        print("❌ Some tests failed. Check the output above for details.")
    print("=" * 60)

if __name__ == "__main__":
    main()

