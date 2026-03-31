import subprocess
import os
import logging
from pathlib import Path

logger = logging.getLogger("ai.training.export_to_ollama")

def create_model_in_ollama(tag: str, gguf_path: str):
    """
    Export the trained GGUF model to Ollama.
    Expects a GGUF file and creates a new model with a specific Modelfile.
    """
    modelfile_content = f"""
FROM {gguf_path}
TEMPLATE "[INST] <<SYS>>\nYou are a quantitative trading evaluator. You receive market data and return a JSON decision.\n<</SYS>>\n\n{{{{ .Prompt }}}} [/INST]"
PARAMETER temperature 0.1
PARAMETER stop "[INST]"
PARAMETER stop "[/INST]"
"""
    modelfile_path = Path("models") / f"Modelfile_{tag}"
    with open(modelfile_path, "w", encoding="utf-8") as f:
        f.write(modelfile_content)

    logger.info(f"Creating Ollama model: {tag} from {gguf_path}")
    try:
        # Check if Ollama is accessible
        subprocess.run(["ollama", "create", tag, "-f", str(modelfile_path)], check=True)
        logger.info(f"Ollama model {tag} created successfully.")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to create Ollama model: {e}")
        return False
    except FileNotFoundError:
        logger.error("Ollama CLI not found. Ensure Ollama is installed and in PATH.")
        return False

if __name__ == "__main__":
    # Test call
    print("Ollama export script ready.")
