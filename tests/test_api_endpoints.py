import os
import requests
from dotenv import load_dotenv

load_dotenv()

def test_endpoints():
    token = os.getenv('CR_API_TOKEN')
    location_id = "57000038" # Brasil
    headers = {'Authorization': f'Bearer {token}'}
    
    endpoints = [
        f"https://proxy.royaleapi.dev/v1/locations/{location_id}/rankings/players?limit=10",
        f"https://proxy.royaleapi.dev/v1/locations/{location_id}/rankings/pathoflegend?limit=10",
        f"https://proxy.royaleapi.dev/v1/locations/global/rankings/pathoflegend?limit=10"
    ]
    
    for url in endpoints:
        print(f"Testing: {url}")
        try:
            r = requests.get(url, headers=headers, timeout=10)
            print(f"Status: {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                items = data.get('items', [])
                print(f"Items found: {len(items)}")
                if items:
                    print(f"First item: {items[0].get('name')}")
            else:
                print(f"Error: {r.text}")
        except Exception as e:
            print(f"Exception: {e}")
        print("-" * 30)

if __name__ == "__main__":
    test_endpoints()
