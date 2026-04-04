import requests
import json
import time

def verify_logic():
    url = "http://localhost:11434/api/generate"
    model = "gemma4:e4b"
    
    # Scenario: Gold (XAUUSD) Flash Rejection
    scenario = """
    Scenario Trading: XAUUSD ha appena toccato una resistenza a 2530 ed è stato respinto con una 
    candela Engulfing bearish su M15. Supporto a 2510. RSI sta uscendo dall'ipercomprato.
    
    Esegui una decisione di trading immediata.
    FORMATO RISPOSTA: JSON puro con chiavi: action (BUY/SELL/WAIT), confidence (0.0-1.0), 
    stop_loss (float), take_profit (float), risk_multiplier (1-5).
    """

    print(f"--- VERIFICA LOGICA GEMMA 4 (E4B) --- 🧪🏎️")
    
    start_time = time.time()
    try:
        response = requests.post(url, json={
            "model": model,
            "prompt": scenario,
            "format": "json", # Forza output JSON (v1.x feature)
            "stream": False,
            "options": {"num_ctx": 4096, "temperature": 0.0}
        }, timeout=45)
        
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            raw_content = result.get('response', '')
            
            # Parsing JSON
            try:
                data = json.loads(raw_content)
                print(f"Decisione Validata con Successo! ✅")
                print(json.dumps(data, indent=4))
                
                # Check chiavi obbligatorie
                required = ["action", "confidence", "stop_loss", "take_profit"]
                missing = [k for k in required if k not in data]
                
                if not missing:
                    print(f"Protocollo JSON: INTEGRO 🛡️")
                else:
                    print(f"Protocollo JSON: CORROTTO (Mancano: {missing}) 🔴")
                
                print(f"Tempo di Reazione: {elapsed:.2f}s ⚡️")
                
            except json.JSONDecodeError as je:
                print(f"Errore Formato: L'AI ha prodotto testo anziché JSON. Content: {raw_content[:200]}... 🔴")
        else:
            print(f"Errore API Ollama: {response.status_code} 🔴")
            
    except Exception as e:
        print(f"Eccezione durante la verifica logica: {e}")

if __name__ == "__main__":
    verify_logic()
