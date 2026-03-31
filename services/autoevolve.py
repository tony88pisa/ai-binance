import time
import subprocess
import schedule
from datetime import datetime
from pathlib import Path
import sys

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def run_evolution():
    print(f"[{datetime.now()}] --- V8.1.1 AUTO-EVOLUTION STARTED (Local Mode) ---")
    
    try:
        # 1. Daily Research
        print("1. Running Daily Research...")
        subprocess.run(["python", "-m", "research.daily_adapter"], check=False)

        # 2. Dataset Generation
        print("2. Generating fine-tuning dataset...")
        subprocess.run(["python", "-m", "ai.dataset.generate"], check=False)
        
        # 3. Training Status: DISABLED in local mode
        # Unsloth GPU training requires Linux/WSL with CUDA.
        # On Windows native, we skip this step and rely on Ollama's existing model.
        print("3. GPU Training: SKIPPED (local-only mode, no Docker)")
        print("   To train manually, use WSL2 with: python ai/training/unsloth_trainer.py")
        
        # 4. Update Ollama Model (if a new GGUF exists)
        print("4. Checking for updated inference model...")
        gguf_path = Path(__file__).resolve().parent.parent / "ai" / "qwen-trading-v7-gguf" / "unsloth.Q4_K_M.gguf"
        if gguf_path.exists():
            modelfile = f'FROM {gguf_path}\nPARAMETER temperature 0.1\nSYSTEM "You are a highly analytical trading bot. Formulate clear decisions with confidence scores and reasoning based ONLY on data provided."'
            modelfile_path = Path(__file__).resolve().parent.parent / "Modelfile"
            with open(modelfile_path, "w", encoding="utf-8") as f:
                f.write(modelfile)
            subprocess.run(["ollama", "create", "qwen-trading", "-f", str(modelfile_path)], check=False)
            print("   Model update submitted to Ollama.")
        else:
            print("   No GGUF model found. Skipping Ollama update.")
        
        print(f"[{datetime.now()}] --- EVOLUTION COMPLETED ---")
        
    except Exception as e:
        print(f"[{datetime.now()}] Evolution pipeline failed: {e}")

if __name__ == "__main__":
    schedule.every().monday.at("08:00").do(run_evolution)
    schedule.every().thursday.at("08:00").do(run_evolution)
    
    print(f"[{datetime.now()}] AutoEvolve Orchestrator Service Started (Local Mode).")
    print("Waiting for scheduled triggers (Mon/Thu 08:00).")
    
    # Initial dry run
    run_evolution()
    
    while True:
        schedule.run_pending()
        time.sleep(60)
