#!/usr/bin/env python3
from __future__ import annotations

import argparse
import inspect
import json
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser(description="Train a Local Judge LoRA/QLoRA adapter from an SFT JSONL config.")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate config/dataset/dependencies without starting training.",
    )
    args = parser.parse_args()

    config = _load_yaml(args.config)
    _validate_config(config)
    counts = _dataset_counts(config)
    deps = _dependency_status()
    hardware = _hardware_status()
    ready_to_train = all(deps.values()) and _hardware_supports_config(config, hardware)
    summary = {
        "config": str(args.config),
        "run_id": config["run_id"],
        "base_model": config["base_model"],
        "dataset_counts": counts,
        "dependencies": deps,
        "hardware": hardware,
        "ready_to_train": ready_to_train,
        "artifact_dir": config["output"]["artifact_dir"],
    }
    if args.dry_run:
        print(json.dumps({"ok": True, **summary}, indent=2, sort_keys=True))
        return 0
    missing = [name for name, ok in deps.items() if not ok]
    if missing:
        raise SystemExit(
            "Missing training dependencies: "
            + ", ".join(missing)
            + ". Install torch, transformers, datasets, trl, peft, bitsandbytes, and pyyaml in the training environment."
        )
    if not _hardware_supports_config(config, hardware):
        raise SystemExit(
            "This config requires CUDA-capable GPU training. Use a CUDA machine for QLoRA, "
            "or switch to a non-QLoRA/CPU debug config."
        )
    _train(config)
    return 0


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
    except ModuleNotFoundError as exc:
        raise SystemExit("Missing pyyaml. Install training dependencies before running train_lora.py.") from exc
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("training config must be a YAML object")
    return data


def _validate_config(config: dict[str, Any]) -> None:
    required = ["run_id", "base_model", "dataset", "method", "training", "output"]
    missing = [key for key in required if key not in config]
    if missing:
        raise SystemExit(f"training config missing required keys: {', '.join(missing)}")
    for key in ["train", "validation", "test", "manifest"]:
        path = Path(config["dataset"][key])
        if not path.exists():
            raise SystemExit(f"dataset.{key} does not exist: {path}")


def _dataset_counts(config: dict[str, Any]) -> dict[str, int]:
    return {
        split: _count_jsonl(Path(config["dataset"][split]))
        for split in ["train", "validation", "test"]
    }


def _count_jsonl(path: Path) -> int:
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def _dependency_status() -> dict[str, bool]:
    deps = {}
    for name in ["torch", "transformers", "datasets", "trl", "peft", "bitsandbytes", "yaml"]:
        try:
            __import__(name)
            deps[name] = True
        except ModuleNotFoundError:
            deps[name] = False
    return deps


def _hardware_status() -> dict[str, Any]:
    status: dict[str, Any] = {"cuda_available": False, "mps_available": False, "device_count": 0}
    try:
        import torch

        status["cuda_available"] = bool(torch.cuda.is_available())
        status["device_count"] = int(torch.cuda.device_count()) if torch.cuda.is_available() else 0
        status["mps_available"] = bool(getattr(torch.backends, "mps", None) and torch.backends.mps.is_available())
        if torch.cuda.is_available():
            status["devices"] = [torch.cuda.get_device_name(index) for index in range(torch.cuda.device_count())]
    except ModuleNotFoundError:
        status["torch_missing"] = True
    return status


def _hardware_supports_config(config: dict[str, Any], hardware: dict[str, Any]) -> bool:
    if config["method"].get("type") == "qlora":
        return bool(hardware.get("cuda_available"))
    return bool(hardware.get("cuda_available") or hardware.get("mps_available"))


def _train(config: dict[str, Any]) -> None:
    import torch
    from datasets import load_dataset
    from peft import LoraConfig
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, TrainingArguments
    from trl import SFTTrainer

    output_dir = Path(config["output"]["artifact_dir"])
    adapter_dir = Path(config["output"].get("adapter_dir", output_dir / "adapter"))
    output_dir.mkdir(parents=True, exist_ok=True)

    train_dataset = load_dataset("json", data_files=str(config["dataset"]["train"]), split="train")
    eval_dataset = load_dataset("json", data_files=str(config["dataset"]["validation"]), split="train")

    tokenizer = AutoTokenizer.from_pretrained(config["base_model"], trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    quantization_config = None
    if config["method"].get("type") == "qlora":
        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=_torch_compute_dtype(torch, config["training"]),
            bnb_4bit_use_double_quant=True,
        )

    model = AutoModelForCausalLM.from_pretrained(
        config["base_model"],
        quantization_config=quantization_config,
        device_map="auto",
        trust_remote_code=True,
    )

    peft_config = LoraConfig(
        r=int(config["method"]["lora_r"]),
        lora_alpha=int(config["method"]["lora_alpha"]),
        lora_dropout=float(config["method"].get("lora_dropout", 0.05)),
        target_modules=list(config["method"].get("target_modules", [])),
        bias="none",
        task_type="CAUSAL_LM",
    )
    train_cfg = config["training"]
    training_args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=float(train_cfg["epochs"]),
        learning_rate=float(train_cfg["learning_rate"]),
        per_device_train_batch_size=int(train_cfg["batch_size"]),
        per_device_eval_batch_size=int(train_cfg["batch_size"]),
        gradient_accumulation_steps=int(train_cfg["gradient_accumulation_steps"]),
        max_steps=int(train_cfg.get("max_steps", -1)),
        warmup_ratio=float(train_cfg.get("warmup_ratio", 0.03)),
        weight_decay=float(train_cfg.get("weight_decay", 0.0)),
        logging_steps=int(train_cfg.get("logging_steps", 10)),
        eval_steps=int(train_cfg.get("eval_steps", 100)),
        save_steps=int(train_cfg.get("save_steps", 250)),
        eval_strategy="steps",
        save_strategy="steps",
        bf16=bool(train_cfg.get("bf16", True)),
        fp16=bool(train_cfg.get("fp16", False)),
        gradient_checkpointing=bool(train_cfg.get("gradient_checkpointing", True)),
        report_to=[],
        seed=int(train_cfg.get("seed", 22)),
    )

    trainer = SFTTrainer(**_sft_trainer_kwargs(
        SFTTrainer,
        model=model,
        tokenizer=tokenizer,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        peft_config=peft_config,
        training_args=training_args,
        max_seq_length=int(train_cfg["max_seq_length"]),
    ))
    trainer.train()
    trainer.model.save_pretrained(adapter_dir)
    tokenizer.save_pretrained(adapter_dir)
    (output_dir / "training_summary.json").write_text(
        json.dumps(
            {
                "run_id": config["run_id"],
                "base_model": config["base_model"],
                "dataset": config["dataset"],
                "adapter_dir": str(adapter_dir),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _torch_compute_dtype(torch_module: Any, train_cfg: dict[str, Any]) -> Any:
    if bool(train_cfg.get("bf16", True)):
        return torch_module.bfloat16
    return torch_module.float16


def _sft_trainer_kwargs(
    trainer_cls: Any,
    *,
    model: Any,
    tokenizer: Any,
    train_dataset: Any,
    eval_dataset: Any,
    peft_config: Any,
    training_args: Any,
    max_seq_length: int,
) -> dict[str, Any]:
    """Build kwargs for both old and new TRL SFTTrainer APIs.

    TRL changed `tokenizer=` to `processing_class=` and moved some SFT-specific
    options out of the constructor in newer releases. Keeping this small
    compatibility shim lets the same training script run on Colab's latest TRL
    and on older pinned environments.
    """
    params = set(inspect.signature(trainer_cls.__init__).parameters)
    kwargs: dict[str, Any] = {
        "model": model,
        "train_dataset": train_dataset,
        "eval_dataset": eval_dataset,
        "peft_config": peft_config,
        "args": training_args,
    }
    if "tokenizer" in params:
        kwargs["tokenizer"] = tokenizer
    elif "processing_class" in params:
        kwargs["processing_class"] = tokenizer
    if "max_seq_length" in params:
        kwargs["max_seq_length"] = max_seq_length
    if "dataset_kwargs" in params:
        kwargs["dataset_kwargs"] = {"add_special_tokens": False}
    return kwargs


if __name__ == "__main__":
    raise SystemExit(main())
