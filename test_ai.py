import os
import requests
from dotenv import load_dotenv

load_dotenv(".env")
api_key = os.getenv("NVIDIA_API_KEY")
model = os.getenv("NVIDIA_MODEL", "nvidia/nemotron-3-super-120b-a12b")
url = "https://integrate.api.nvidia.com/v1/chat/completions"

print(f"Testing NVIDIA NIM API with model: {model}")
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}
payload = {
    "model": model,
    "messages": [{"role": "user", "content": "Ping"}],
    "temperature": 0.2,
    "max_tokens": 10
}

try:
    res = requests.post(url, json=payload, headers=headers, timeout=15)
    res.raise_for_status()
    print("NVIDIA NIM: OK")
    print(res.json()['choices'][0]['message']['content'])
except Exception as e:
    print(f"NVIDIA NIM: FAILED - {e}")

# Also test local Ollama if possible
ollama_url = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
try:
    res = requests.get(f"{ollama_url}/api/version", timeout=5)
    res.raise_for_status()
    print(f"Ollama: OK - {res.json()}")
except Exception as e:
    print(f"Ollama: FAILED - {e}")
