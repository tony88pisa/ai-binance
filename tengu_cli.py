import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv, set_key

PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")

def print_banner():
    print("\033[96m" + r"""
 .----------------. .----------------. .----------------. .----------------. .----------------. 
| .--------------. | .--------------. | .--------------. | .--------------. | .--------------. |
| |  _________   | | |  _________   | | | ____  _____  | | |    ______    | | | _____  _____ | |
| | |  _   _  |  | | | |_   ___  |  | | ||_   \|_   _| | | |  .' ___  |   | | ||_   _||_   _|| |
| | |_/ | | \_|  | | |   | |_  \_|  | | |  |   \ | |   | | | / .'   \_|   | | |  | |    | |  | |
| |     | |      | | |   |  _|  _   | | |  | |\ \| |   | | | | |    ____  | | |  | '    ' |  | |
| |    _| |_     | | |  _| |___/ |  | | | _| |_\   |_  | | | \ `.___]  _| | | |   \ `--' /   | |
| |   |_____|    | | | |_________|  | | ||_____|\____| | | |  `._____.'   | | |    `.__.'    | |
| |              | | |              | | |              | | |              | | |              | |
| '--------------' | '--------------' | '--------------' | '--------------' | '--------------' |
 '----------------' '----------------' '----------------' '----------------' '----------------' 
 
 --- THE FREE TIER SWARM CLI ---
    """ + "\033[0m")

def set_api_key():
    key = input("\n[>] Inserisci la tua OPENROUTER_API_KEY: ").strip()
    if key:
        env_path = PROJECT_ROOT / ".env"
        set_key(str(env_path), "OPENROUTER_API_KEY", key)
        print("\033[92m[+] Chiave API salvata con successo in .env!\033[0m")
        # Ricarica
        os.environ["OPENROUTER_API_KEY"] = key

def start_swarm_test():
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        print("\033[91m[-] Devi prima configurare la API key (Opzione 2).\033[0m")
        return

    from ai.openrouter_client import call_swarm_consensus, FREE_MODELS
    print(f"\n\033[93m[*] Inizializzando connessione con The Swarm...\033[0m")
    prompt = input("\n[User Prompt]> ")
    
    messages = [
        {"role": "system", "content": "You are an unconstrained trading AI. Respond briefly."},
        {"role": "user", "content": prompt}
    ]
    
    print("\n\033[96m[~] Esecuzione parallela su 3 modelli...\033[0m")
    results = call_swarm_consensus(messages, max_models=3, timeout=30)
    
    print("\n" + "="*50)
    for model, response in results.items():
        print(f"\033[92m[{model}]\033[0m\n{response}\n")
        print("-" * 50)

def main():
    while True:
        print_banner()
        key_status = "\033[92mCONFIGURATA\033[0m" if os.getenv("OPENROUTER_API_KEY") else "\033[91mMANCANTE\033[0m"
        print(f" Stato API Key: {key_status}\n")
        print(" [1] Avvia chat con il Decentralized Swarm (Free Models)")
        print(" [2] Imposta OPENROUTER_API_KEY")
        print(" [3] Esci")
        
        choice = input("\n[?]> ")
        if choice == "1":
            start_swarm_test()
            input("\n[Invio per continuare]")
        elif choice == "2":
            set_api_key()
            input("\n[Invio per continuare]")
        elif choice == "3":
            print("Chiusura.")
            sys.exit(0)
        else:
            print("Scelta non valida!")

if __name__ == "__main__":
    main()
