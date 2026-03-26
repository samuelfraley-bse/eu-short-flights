import requests
import json

# We optimized by:
# 1. Increasing timeout to 120
# 2. Removing 'node' and 'relation' calls
# 3. Using 'out geom' which is significantly lighter
query = """
[out:json][timeout:120];
way["railway"="rail"]["highspeed"="yes"](34,-11,60,25);
out geom;
"""

url = "https://overpass-api.de/api/interpreter"
print("Requesting data (this may take 45-60 seconds)...")

try:
    r = requests.post(url, data={'data': query}, timeout=130)
    r.raise_for_status()
    with open('hsr_light.json', 'w') as f:
        json.dump(r.json(), f)
    print("Success! File saved as hsr_light.json")
except Exception as e:
    print(f"Failed: {e}")