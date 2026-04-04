import requests
import json
import subprocess
import time
import os

def get_vram_usage():
    try:
        # Recupero memoria GPU via nvidia-smi
        output = subprocess.check_output(["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"], encoding='utf-8')
        used, total = map(int, output.strip().split(','))
        return used, total
    except Exception as e:
        print(f"Errore lettura VRAM: {e}")
        return 0, 0

def test_inference_vram():
    url = "http://localhost:11434/api/generate"
    model = "gemma4:e4b"
    
    # Prompt Complesso (Simulazione analisi trading multi-asset)
    prompt = """
    Sei un Decision Engine AI integrato su Binance. Analizza questa sequenza di 100 candele BTC/USDT 
    e Gold (XAUUSD). Il trend è ribassista (-2.5%) con volumi in aumento. Bollinger Bands indicano 
    ipervenduto. RSI a 28. 
    
    Esegui un'analisi profonda del rischio e produci un segnale di trading in JSON puro.
    Usa queste chiavi: action, confidence, stop_loss, take_profit, reasoning.
    """

    print(f"--- INIZIO STRESS TEST GEMMA 4 (E4B) --- 🚀")
    used_before, total = get_vram_usage()
    print(f"Stato VRAM Iniziale: {used_before}MB / {total}MB ✅")

    start_time = time.time()
    try:
        response = requests.post(url, json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_ctx": 8192, "temperature": 0.1}
        }, timeout=60)
        
        elapsed = time.time() - start_time
        used_after, _ = get_vram_usage()
        
        if response.status_code == 200:
            result = response.json()
            print(f"\nLOGICA AI RICEVUTA (MoE Response):")
            print(json.dumps(result.get('response', ''), indent=2))
            
            print(f"\n--- REPORT TELEMETRIA RTX 5080 --- 🏎️")
            print(f"Picco VRAM: {used_after}MB 🔋")
            print(f"Delta Memoria: {used_after - used_before}MB")
            print(f"Latenza Inferenza: {elapsed:.2f} secondi ⚡️")
            
            if used_after > 15000:
                print(f"ATTENZIONE: Memoria saturata (>15GB)! 🔴")
            else:
                print(f"STABILITÀ: VRAM Ottimale per RTX 5080! ✅")
        else:
            print(f"Errore API Ollama: {response.status_code} 🔴")
            
    except Exception as e:
        print(f"Eccezione durante il test: {e}")

if __name__ == "__main__":
    test_inference_vram()
