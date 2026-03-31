import logging
import os
import yaml
from pathlib import Path
from datetime import datetime
from unsloth import FastLanguageModel
import torch
from trl import SFTTrainer
from transformers import TrainingArguments
from datasets import load_dataset

logger = logging.getLogger("ai.training.unsloth_trainer")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = PROJECT_ROOT / "ai" / "training" / "training_config.yaml"

def run_training_v811(dataset_path: str):
    """
    V8.1.1 Sincronizzato Training Pipeline.
    Legge la configurazione YAML e usa il campo 'text' (Alpaca format) nel dataset.
    """
    # 0. Load Configuration
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    logger.info(f"Starting V8.1.1 Fine-tuning on {dataset_path}")
    
    # 1. Load model and tokenizer
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name = config["base_model"],
        max_seq_length = 2048,
        load_in_4bit = True,
    )

    # 2. Add LoRA adapters
    model = FastLanguageModel.get_peft_model(
        model,
        r = config["lora"]["r"],
        target_modules = config["lora"]["target_modules"],
        lora_alpha = config["lora"]["alpha"],
        lora_dropout = config["lora"]["dropout"],
        bias = "none",
        use_gradient_checkpointing = "unsloth",
        random_state = 3407,
        use_rslora = False,
        loftq_config = None,
    )

    # 3. Load dataset
    # V8.1.1 Sincronizzato: Il dataset builder produce già il campo 'text' (Alpaca format)
    dataset = load_dataset("json", data_files=dataset_path, split="train")

    # 4. Initialize Trainer
    trainer = SFTTrainer(
        model = model,
        tokenizer = tokenizer,
        train_dataset = dataset,
        dataset_text_field = "text", # Sincronizzato col Builder
        max_seq_length = 2048,
        dataset_num_proc = 2,
        args = TrainingArguments(
            per_device_train_batch_size = config["training"]["batch_size"],
            gradient_accumulation_steps = config["training"]["accumulation_steps"],
            warmup_steps = 5,
            max_steps = config["training"]["max_steps"],
            learning_rate = config["training"]["learning_rate"],
            fp16 = not torch.cuda.is_bf16_supported(),
            bf16 = torch.cuda.is_bf16_supported(),
            logging_steps = 1,
            optim = config["training"]["optim"],
            weight_decay = config["training"]["weight_decay"],
            lr_scheduler_type = "linear",
            seed = 3407,
            output_dir = "outputs",
        ),
    )

    # 5. Train
    trainer_stats = trainer.train()
    
    # 6. Save LoRA / GGUF
    adapter_name = f"adapter_v811_{int(datetime.now().timestamp())}"
    model.save_pretrained_gguf(f"models/{adapter_name}", tokenizer, quantization_method = config["export"]["quantization"])
    
    logger.info(f"Training V8.1.1 SUCCESS. Adapter saved at models/{adapter_name}")
    return adapter_name

if __name__ == "__main__":
    print("Unsloth trainer V8.1.1 ready.")
