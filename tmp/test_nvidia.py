import os
import requests
from dotenv import load_dotenv

load_dotenv("h:/ai-binance/.env")

api_key = os.getenv("NVIDIA_API_KEY")

if not api_key:
    print("Nessuna chiave API trovata nel file .env!")
    exit(1)

print(f"La chiave inizia con: {api_key[:5]}... (lunghezza: {len(api_key)})")

url = "https://integrate.api.nvidia.com/v1/chat/completions"
model = os.getenv("NVIDIA_MODEL", "nvidia/llama-3.1-nemotron-70b-instruct")

print(f"Testando il modello: {model}...")

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

payload = {
    "model": model,
    "messages": [
        {"role": "user", "content": "Hello. Say 'OK' if you can read this."}
    ],
    "max_tokens": 10
}

try:
    res = requests.post(url, json=payload, headers=headers, timeout=10)
    print(f"Status Code: {res.status_code}")
    print(f"Risposta raw: {res.text}")
except Exception as e:
    print(f"Errore di connessione: {e}")
