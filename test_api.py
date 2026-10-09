import requests
import json

response = requests.post('http://localhost:8000/api/v1/ml/signal/live', json={'ticker':'AAPL'}, timeout=180)
data = response.json()

# Save to file for inspection
with open('api_response.json', 'w') as f:
    json.dump(data, f, indent=2)

print("Response saved to api_response.json")
print(f"\nKeys in response: {list(data.keys())}")
print(f"\nHas market_mood: {'market_mood' in data}")
print(f"Has top_news: {'top_news' in data}")

if 'market_mood' in data:
    print(f"Market Mood: {data['market_mood']}")
if 'top_news' in data:
    print(f"Top News: {data['top_news']}")
