"""
FunctionGemma 270M — LoRA fine-tuning script.

Uses Unsloth for fast training on Mac / Colab.  Falls back to standard PEFT
if Unsloth is not installed.

Run:
    python fine_tuning/function_gemma/train.py

Output:
    fine_tuning/function_gemma/adapter/  (LoRA adapter weights)

Estimated training time: ~15-30 min on Apple Silicon M-series or Colab T4.
"""

from __future__ import annotations

import json
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_MODEL = "google/gemma-3-1b-it"      # Swap for FunctionGemma 270M when available on HF
DATASET_PATH = Path(__file__).parent / "dataset.jsonl"
OUTPUT_DIR = Path(__file__).parent / "adapter"
MAX_SEQ_LEN = 512
LORA_RANK = 16
LORA_ALPHA = 32
BATCH_SIZE = 4
GRAD_ACCUM = 4
LEARNING_RATE = 2e-4
NUM_EPOCHS = 3


def load_dataset(path: Path) -> list[str]:
    texts = []
    with open(path) as f:
        for line in f:
            item = json.loads(line)
            texts.append(item["text"])
    return texts


def train():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    try:
        from unsloth import FastLanguageModel  # type: ignore[import]
        _train_unsloth()
    except ImportError:
        print("Unsloth not found — falling back to standard PEFT / transformers")
        _train_peft()


def _train_unsloth():
    from unsloth import FastLanguageModel  # type: ignore[import]
    from datasets import Dataset  # type: ignore[import]
    from trl import SFTTrainer  # type: ignore[import]
    from transformers import TrainingArguments  # type: ignore[import]

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=BASE_MODEL,
        max_seq_length=MAX_SEQ_LEN,
        load_in_4bit=True,
    )
    model = FastLanguageModel.get_peft_model(
        model,
        r=LORA_RANK,
        lora_alpha=LORA_ALPHA,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_dropout=0.05,
        bias="none",
        use_gradient_checkpointing=True,
    )

    texts = load_dataset(DATASET_PATH)
    dataset = Dataset.from_dict({"text": texts})

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=MAX_SEQ_LEN,
        args=TrainingArguments(
            output_dir=str(OUTPUT_DIR),
            per_device_train_batch_size=BATCH_SIZE,
            gradient_accumulation_steps=GRAD_ACCUM,
            learning_rate=LEARNING_RATE,
            num_train_epochs=NUM_EPOCHS,
            save_strategy="epoch",
            logging_steps=10,
            fp16=True,
        ),
    )
    trainer.train()
    model.save_pretrained(str(OUTPUT_DIR))
    tokenizer.save_pretrained(str(OUTPUT_DIR))
    print(f"Adapter saved to {OUTPUT_DIR}")


def _train_peft():
    from peft import LoraConfig, get_peft_model  # type: ignore[import]
    from transformers import (  # type: ignore[import]
        AutoModelForCausalLM,
        AutoTokenizer,
        DataCollatorForLanguageModeling,
        Trainer,
        TrainingArguments,
    )
    from datasets import Dataset  # type: ignore[import]

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    model = AutoModelForCausalLM.from_pretrained(BASE_MODEL, device_map="auto")

    lora_config = LoraConfig(
        r=LORA_RANK,
        lora_alpha=LORA_ALPHA,
        target_modules=["q_proj", "v_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    texts = load_dataset(DATASET_PATH)
    encodings = tokenizer(texts, truncation=True, max_length=MAX_SEQ_LEN, padding="max_length")
    dataset = Dataset.from_dict(encodings)

    trainer = Trainer(
        model=model,
        args=TrainingArguments(
            output_dir=str(OUTPUT_DIR),
            per_device_train_batch_size=BATCH_SIZE,
            gradient_accumulation_steps=GRAD_ACCUM,
            learning_rate=LEARNING_RATE,
            num_train_epochs=NUM_EPOCHS,
            save_strategy="epoch",
            logging_steps=10,
        ),
        train_dataset=dataset,
        data_collator=DataCollatorForLanguageModeling(tokenizer, mlm=False),
    )
    trainer.train()
    model.save_pretrained(str(OUTPUT_DIR))
    tokenizer.save_pretrained(str(OUTPUT_DIR))
    print(f"Adapter saved to {OUTPUT_DIR}")


if __name__ == "__main__":
    train()
