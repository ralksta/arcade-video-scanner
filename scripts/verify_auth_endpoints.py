import requests
import sys

BASE_URL = "http://localhost:8000"

def test_endpoint(name, path, valid_params=None):
    url = f"{BASE_URL}{path}"
    print(f"Testing {name} ({path})...", end=" ")
    try:
        # Send request without cookies
        if valid_params:
            url += f"?{valid_params}"
            
        r = requests.get(url, timeout=2)
        if r.status_code == 401:
            print("✅ Protected (401)")
            return True
        elif r.status_code == 404:
            print(f"⚠️ Not Found (404) - Endpoint might be POST or path wrong.")
            return False
        else:
            print(f"❌ FAILED! Status: {r.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def verify_all():
    print("🔐 Verifying Critical Endpoints are Secured...")
    
    endpoints = [
        ("Backup", "/api/backup", ""),
        ("Rescan", "/api/rescan", ""),
        ("Compress", "/compress", "path=/tmp/test.mp4"),
        ("Keep Optimized", "/api/keep_optimized", "original=/tmp/a&optimized=/tmp/b"),
        ("Discard Optimized", "/api/discard_optimized", "path=/tmp/test.mp4"),
        ("Batch Compress", "/batch_compress", "paths=/tmp/a|||/tmp/b")
    ]
    
    success = True
    for name, path, params in endpoints:
        if not test_endpoint(name, path, params):
            success = False
            
    if success:
        print("\n🎉 ALL CRITICAL ENDPOINTS SECURED!")
        sys.exit(0)
    else:
        print("\n❌ SOME ENDPOINTS ARE VULNERABLE or UNREACHABLE.")
        sys.exit(1)

if __name__ == "__main__":
    verify_all()
