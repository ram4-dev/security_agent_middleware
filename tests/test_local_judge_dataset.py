from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import threading
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts" / "local-judge"
DATASET = ROOT / "datasets" / "local-judge" / "golden_v1.jsonl"
PYTHON = sys.executable


def load_common():
    spec = importlib.util.spec_from_file_location("dataset_common", SCRIPTS / "dataset_common.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["dataset_common"] = module
    spec.loader.exec_module(module)
    return module


def run_script(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_golden_dataset_validates():
    common = load_common()
    cases = common.read_jsonl(DATASET)
    result = common.validate_dataset(cases)

    assert result.ok, result.errors
    assert {case["expected"]["risk_type"] for case in cases} == common.RISK_TYPES


def test_validate_dataset_script_accepts_golden():
    result = run_script(
        "scripts/local-judge/validate_dataset.py",
        "--dataset",
        str(DATASET),
        "--taxonomy",
        "datasets/local-judge/taxonomy.yaml",
    )

    assert result.returncode == 0, result.stderr
    assert "OK:" in result.stdout


def test_generate_synthetic_with_gpt_calls_openai_compatible_endpoint(tmp_path):
    common = load_common()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers["content-length"])
            payload = json.loads(self.rfile.read(length))
            assert self.path == "/v1/chat/completions"
            assert self.headers["authorization"] == "Bearer fake-test-key"
            assert payload["model"] == "cheap-test-model"
            user_prompt = json.loads(payload["messages"][1]["content"])
            risk_type = user_prompt["risk_type"]
            content = f"Synthetic case for {risk_type.lower()} with fake_value_invalid"
            case = {
                "case_id": f"{risk_type.lower()}_gpt_test_0001",
                "split": "synthetic_seed",
                "source": "synthetic_gpt",
                "language": "es-AR",
                "integration": "claude-code",
                "wire_api": "anthropic_messages",
                "input": {
                    "normalized_request": {
                        "system": "You are a coding assistant.",
                        "messages": [{"role": "user", "content": content}],
                        "tools": [],
                    },
                    "deterministic_signals": [],
                    "candidate_policies": [],
                },
                "expected": {
                    "decision": "LOG" if risk_type == "BENIGN_REQUEST" else "WARN",
                    "risk_type": risk_type,
                    "severity": "LOW" if risk_type == "BENIGN_REQUEST" else "HIGH",
                    "critical": risk_type != "BENIGN_REQUEST",
                    "redaction_targets": [],
                },
                "notes": "Synthetic GPT test case.",
            }
            raw = json.dumps(
                {"choices": [{"message": {"content": json.dumps({"cases": [case]})}}]}
            ).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    out = tmp_path / "synthetic_gpt.jsonl"
    try:
        result = subprocess.run(
            [
                PYTHON,
                "scripts/local-judge/generate_synthetic_with_gpt.py",
                "--provider",
                "openai-compatible",
                "--base-url",
                f"http://127.0.0.1:{server.server_port}/v1",
                "--model",
                "cheap-test-model",
                "--per-risk",
                "1",
                "--batch-size",
                "1",
                "--out",
                str(out),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
            env={**dict(os.environ), "OPENAI_API_KEY": "fake-test-key"},
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)

    assert result.returncode == 0, result.stderr
    cases = common.read_jsonl(out)
    assert len(cases) == len(common.RISK_TYPES)
    assert common.validate_dataset(cases).ok


def test_generate_synthetic_with_local_os_does_not_require_api_key(tmp_path):
    common = load_common()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers["content-length"])
            payload = json.loads(self.rfile.read(length))
            assert self.path == "/v1/chat/completions"
            assert self.headers.get("authorization") is None
            user_prompt = json.loads(payload["messages"][1]["content"])
            risk_type = user_prompt["risk_type"]
            content = f"Synthetic local OS case for {risk_type.lower()}"
            case = {
                "case_id": f"{risk_type.lower()}_local_os_test_0001",
                "split": "synthetic_seed",
                "source": "synthetic_gpt",
                "language": "es-AR",
                "integration": "claude-code",
                "wire_api": "anthropic_messages",
                "input": {
                    "normalized_request": {
                        "system": "You are a coding assistant.",
                        "messages": [{"role": "user", "content": content}],
                        "tools": [],
                    },
                    "deterministic_signals": [],
                    "candidate_policies": [],
                },
                "expected": {
                    "decision": "LOG" if risk_type == "BENIGN_REQUEST" else "WARN",
                    "risk_type": risk_type,
                    "severity": "LOW" if risk_type == "BENIGN_REQUEST" else "HIGH",
                    "critical": risk_type != "BENIGN_REQUEST",
                    "redaction_targets": [],
                },
                "notes": "Synthetic local open-source model test case.",
            }
            raw = json.dumps(
                {"choices": [{"message": {"content": json.dumps({"cases": [case]})}}]}
            ).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    out = tmp_path / "synthetic_local_os.jsonl"
    env = dict(os.environ)
    env.pop("OPENAI_API_KEY", None)
    try:
        result = subprocess.run(
            [
                PYTHON,
                "scripts/local-judge/generate_synthetic_with_gpt.py",
                "--provider",
                "local-os",
                "--base-url",
                f"http://127.0.0.1:{server.server_port}/v1",
                "--per-risk",
                "1",
                "--batch-size",
                "1",
                "--out",
                str(out),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)

    assert result.returncode == 0, result.stderr
    cases = common.read_jsonl(out)
    assert len(cases) == len(common.RISK_TYPES)
    assert common.validate_dataset(cases).ok


def test_generate_synthetic_dataset_outputs_valid_jsonl(tmp_path):
    out = tmp_path / "synthetic.jsonl"

    result = run_script(
        "scripts/local-judge/generate_synthetic_dataset.py",
        "--taxonomy",
        "datasets/local-judge/taxonomy.yaml",
        "--out",
        str(out),
    )

    assert result.returncode == 0, result.stderr
    common = load_common()
    cases = common.read_jsonl(out)
    assert len(cases) == 10
    assert common.validate_dataset(cases).ok


def test_generate_synthetic_parallel_calls_openai_compatible_endpoint(tmp_path):
    common = load_common()
    seen_paths = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers["content-length"])
            payload = json.loads(self.rfile.read(length))
            seen_paths.append(self.path)
            assert self.path == "/v1/chat/completions"
            assert self.headers["authorization"] == "Bearer fake-test-key"
            assert payload["model"] == "cheap-test-model"
            user_prompt = json.loads(payload["messages"][1]["content"])
            risk_type = user_prompt["risk_type"]
            count = user_prompt["count"]
            cases = []
            for index in range(count):
                content = f"Parallel synthetic case {index} for {risk_type.lower()} with fake_value_invalid"
                cases.append(
                    {
                        "case_id": f"model_supplied_{risk_type.lower()}_{index}",
                        "split": "synthetic_seed",
                        "source": "synthetic_gpt",
                        "language": "es-AR",
                        "integration": "claude-code",
                        "wire_api": "anthropic_messages",
                        "input": {
                            "normalized_request": {
                                "system": "You are a coding assistant.",
                                "messages": [{"role": "user", "content": content}],
                                "tools": [],
                            },
                            "deterministic_signals": [],
                            "candidate_policies": [],
                        },
                        "expected": {
                            "decision": "LOG" if risk_type == "BENIGN_REQUEST" else "BLOCK",
                            "risk_type": risk_type,
                            "severity": "LOW" if risk_type == "BENIGN_REQUEST" else "HIGH",
                            "critical": risk_type != "BENIGN_REQUEST",
                            "redaction_targets": [],
                        },
                        "notes": "Synthetic parallel test case.",
                    }
                )
            raw = json.dumps({"choices": [{"message": {"content": json.dumps({"cases": cases})}}]}).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    out = tmp_path / "synthetic_parallel.jsonl"
    try:
        result = subprocess.run(
            [
                PYTHON,
                "scripts/local-judge/generate_synthetic_parallel.py",
                "--provider",
                "openai-compatible",
                "--base-url",
                f"http://127.0.0.1:{server.server_port}/v1",
                "--model",
                "cheap-test-model",
                "--risk-types",
                "BENIGN_REQUEST,CREDENTIAL_ABUSE",
                "--per-risk",
                "2",
                "--batch-size",
                "1",
                "--workers",
                "2",
                "--out",
                str(out),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
            env={**dict(os.environ), "OPENAI_API_KEY": "fake-test-key"},
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)

    assert result.returncode == 0, result.stderr
    cases = common.read_jsonl(out)
    assert len(cases) == 4
    assert common.validate_dataset(cases).ok
    assert len(seen_paths) == 4
    assert {case["source"] for case in cases} == {"synthetic_gpt"}
    assert all("opencode_parallel" in case["case_id"] for case in cases)


def test_generate_synthetic_variants_outputs_balanced_jsonl(tmp_path):
    out = tmp_path / "synthetic_variants.jsonl"

    result = run_script(
        "scripts/local-judge/generate_synthetic_variants.py",
        "--in",
        str(tmp_path / "missing_seed.jsonl"),
        "--out",
        str(out),
        "--target-per-risk",
        "2",
    )

    assert result.returncode == 0, result.stderr
    common = load_common()
    cases = common.read_jsonl(out)
    assert len(cases) == 20
    assert common.validate_dataset(cases).ok
    counts = Counter(case["expected"]["risk_type"] for case in cases)
    assert set(counts) == common.RISK_TYPES
    assert set(counts.values()) == {2}


def test_prepare_sft_dataset_writes_balanced_splits(tmp_path):
    source = tmp_path / "source.jsonl"
    out_dir = tmp_path / "training"

    generated = run_script(
        "scripts/local-judge/generate_synthetic_variants.py",
        "--in",
        str(tmp_path / "missing_seed.jsonl"),
        "--out",
        str(source),
        "--target-per-risk",
        "4",
    )
    assert generated.returncode == 0, generated.stderr

    result = run_script(
        "training/local-judge/scripts/prepare_sft_dataset.py",
        "--input",
        str(source),
        "--out-dir",
        str(out_dir),
        "--dataset-version",
        "test_candidate",
        "--train-ratio",
        "0.5",
        "--validation-ratio",
        "0.25",
        "--test-ratio",
        "0.25",
    )

    assert result.returncode == 0, result.stderr
    manifest = json.loads((out_dir / "test_candidate_manifest.json").read_text(encoding="utf-8"))
    assert manifest["summary"]["selected_rows"] == 40
    assert manifest["summary"]["train_rows"] == 20
    assert manifest["summary"]["validation_rows"] == 10
    assert manifest["summary"]["test_rows"] == 10
    train_rows = [json.loads(line) for line in (out_dir / "test_candidate_train.sft.jsonl").read_text().splitlines()]
    assert len(train_rows) == 20
    assert train_rows[0]["messages"][0]["content"].startswith("You are Tranquera Local Judge")
    assistant = json.loads(train_rows[0]["messages"][2]["content"])
    assert assistant["decision"] in {"LOG", "WARN", "BLOCK", "REDACT", "ESCALATE"}


def test_score_predictions_detects_perfect_report():
    common = load_common()
    cases = common.read_jsonl(DATASET)
    predictions = []
    for case in cases:
        output = {
            "decision": case["expected"]["decision"],
            "confidence": 0.99,
            "risk_type": case["expected"]["risk_type"],
            "severity": case["expected"]["severity"],
            "matched_policy_ids": [],
            "explanation": "Audit-safe explanation.",
            "redaction_targets": [],
            "model_version": "test",
        }
        if case["expected"]["decision"] == "REDACT":
            targets = []
            for target in case["expected"]["redaction_targets"]:
                content = common.text_at_path(case["input"]["normalized_request"], target["path"])
                start = content.index(target["span_text"])
                targets.append(
                    {
                        "path": target["path"],
                        "span": {"start": start, "end": start + len(target["span_text"])},
                        "replacement_type": target["replacement_type"],
                    }
                )
            output["redaction_targets"] = targets
        predictions.append(
            {
                "case_id": case["case_id"],
                "ok": True,
                "status_code": 200,
                "latency_ms": 10,
                "output": output,
                "error": None,
            }
        )

    scored = common.score_predictions(cases, predictions)

    assert scored["metrics"]["json_parse_success_rate"] == 1.0
    assert scored["metrics"]["critical_miss_rate"] == 0
    assert scored["metrics"]["redact_target_accuracy"] == 1.0
    assert scored["recommendation"] == "candidate_for_runtime_shadow"


def test_run_benchmark_calls_endpoint_and_writes_report(tmp_path):
    common = load_common()
    cases = common.read_jsonl(DATASET)
    cases_by_id = {case["case_id"]: case for case in cases}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers["content-length"])
            payload = json.loads(self.rfile.read(length))
            case = cases_by_id[payload["trace_id"]]
            expected = case["expected"]
            response = {
                "decision": expected["decision"],
                "confidence": 0.99,
                "risk_type": expected["risk_type"],
                "severity": expected["severity"],
                "matched_policy_ids": [],
                "explanation": "Audit-safe explanation.",
                "redaction_targets": [],
                "model_version": "benchmark-test",
            }
            if expected["decision"] == "REDACT":
                for target in expected["redaction_targets"]:
                    content = common.text_at_path(case["input"]["normalized_request"], target["path"])
                    start = content.index(target["span_text"])
                    response["redaction_targets"].append(
                        {
                            "path": target["path"],
                            "span": {"start": start, "end": start + len(target["span_text"])},
                            "replacement_type": target["replacement_type"],
                        }
                    )
            raw = json.dumps(response).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    out = tmp_path / "benchmark.json"
    try:
        result = run_script(
            "scripts/local-judge/run_benchmark.py",
            "--dataset",
            str(DATASET),
            "--endpoint",
            f"http://127.0.0.1:{server.server_port}/v1/judge",
            "--model-version",
            "benchmark-test",
            "--out",
            str(out),
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)

    assert result.returncode == 0, result.stderr
    report = json.loads(out.read_text(encoding="utf-8"))
    assert len(report["predictions"]) == 10
    assert report["recommendation"] == "candidate_for_runtime_shadow"


def test_export_training_data_writes_assistant_json(tmp_path):
    out = tmp_path / "train.jsonl"

    result = run_script(
        "scripts/local-judge/export_training_data.py",
        "--dataset",
        str(DATASET),
        "--out",
        str(out),
    )

    assert result.returncode == 0, result.stderr
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 10
    assistant = json.loads(rows[1]["messages"][2]["content"])
    assert assistant["decision"] == "REDACT"
    assert "span" in assistant["redaction_targets"][0]
