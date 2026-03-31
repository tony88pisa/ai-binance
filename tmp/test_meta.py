import requests, os
from dotenv import load_dotenv

load_dotenv("h:/ai-binance/.env")
api_key = os.getenv("NVIDIA_API_KEY")

url = "https://integrate.api.nvidia.com/v1/chat/completions"
headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
payload = {"model": "nvidia/llama-3.1-nemotron-70b-instruct", "messages": [{"role": "user", "content": "Test"}], "max_tokens": 10}

models_to_test = [
    "meta/llama-3.1-70b-instruct", 
    "nvidia/llama-3.1-nemotron-70b-instruct", 
    "nvidia/nemotron-4-340b-instruct"
]

for m in models_to_test:
    payload["model"] = m
    print(f"Testing {m}...")
    res = requests.post(url, json=payload, headers=headers)
    print(f"Code: {res.status_code}")
    if res.status_code == 200:
        print("SUCCESS!!!")
    else:
        print(f"Error: {res.text}")
    print("-" * 40)
