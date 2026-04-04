import requests, json

# Test 1: usando /api/generate (non /api/chat) 
print("=== TEST 1: /api/generate ===")
r = requests.post('http://127.0.0.1:11434/api/generate', json={
    'model': 'gemma4:e4b',
    'prompt': 'You are a trading evaluator. Analyze: BTC/USDT at $67300, RSI=34 (oversold), MACD=-2.23. Return JSON: {"decision":"buy" or "hold","confidence":0-100,"thesis":"reason"}. JSON only:',
    'stream': False,
    'options': {'temperature': 0.1, 'num_predict': 300}
}, timeout=90)
data = r.json()
content = data.get('response', '')
print(f"Response length: {len(content)}")
print(f"Content: {repr(content[:500])}")

# Test 2: usando llama3.2 come alternativa
print("\n=== TEST 2: llama3.2 /api/chat ===")
r2 = requests.post('http://127.0.0.1:11434/api/chat', json={
    'model': 'llama3.2',
    'messages': [
        {'role': 'system', 'content': 'You are a trading evaluator. Return ONLY valid JSON.'},
        {'role': 'user', 'content': 'BTC/USDT $67300 RSI=34 MACD=-2.23. Return: {"decision":"buy or hold","confidence":0-100,"thesis":"reason"}'}
    ],
    'stream': False,
    'options': {'temperature': 0.1, 'num_predict': 300}
}, timeout=60)
data2 = r2.json()
content2 = data2.get('message', {}).get('content', '')
print(f"Response length: {len(content2)}")
print(f"Content: {repr(content2[:500])}")
