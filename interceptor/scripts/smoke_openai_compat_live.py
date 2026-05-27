"""Live smoke for the OpenAI-compatible Tranquera route.

Safe secret handling:
- Loads API_KEY from the repository root .env at runtime.
- Never prints the key or request headers.
- Redacts common token shapes from provider error snippets.

This smoke intentionally bypasses the real DB/token lookup with in-process
FastAPI dependency overrides so it can validate the protocol adapter and real
OpenAI-compatible upstream without requiring a local Postgres setup.
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
from pathlib import Path
from uuid import uuid4

# Ensure Settings can import without a developer DB env. This smoke overrides
# FastAPI DB/token dependencies, so the value is never used for a real DB call.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/test")
os.environ.setdefault("OPENAI_COMPAT_UPSTREAM_URL", "https://opencode.ai/zen/go/v1")
os.environ.setdefault("OPENAI_COMPAT_PROVIDER", "opencode-go")
os.environ.setdefault("OPENAI_COMPAT_INTEGRATION", "opencode")
os.environ.setdefault("OPENAI_COMPAT_TEST_MODEL", "qwen3.6-plus")

ROOT = Path(__file__).resolve().parents[2]
INTERCEPTOR_ROOT = Path(__file__).resolve().parents[1]
ROOT_ENV = ROOT / ".env"

sys.path.insert(0, str(INTERCEPTOR_ROOT))

import httpx  # noqa: E402

from app import main  # noqa: E402
from app.cli_auth import CliCaller  # noqa: E402
from app.enums import Action, PolicyDomain, PolicyLayer, PolicySource, Severity  # noqa: E402
from app.models import Policy  # noqa: E402


class ExecResult:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class DummySession:
    def __init__(self, policies):
        self.policies = policies
        self.added = []
        self.commits = 0

    async def exec(self, _statement):
        return ExecResult(self.policies)

    def add(self, row):
        self.added.append(row)

    async def commit(self):
        self.commits += 1


async def override_session_empty():
    return DummySession([])


async def fake_caller(_session, _token):
    return CliCaller(member_id=uuid4(), org_id="demo", email="smoke@example.com")


def load_dotenv_key(path: Path, key: str) -> str | None:
    if not path.exists():
        return None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, value = line.split("=", 1)
        if k.strip() != key:
            continue
        value = value.strip().strip('"').strip("'")
        return value or None
    return None


def regex_block_policy() -> Policy:
    return Policy(
        id=uuid4(),
        org_id="demo",
        slug="aws-access-key",
        domain=PolicyDomain.credentials,
        layer=PolicyLayer.regex,
        rule="AWS Access Key ID expuesta en un prompt",
        pattern=r"AKIA[0-9A-Z]{16}",
        default_action=Action.BLOCK,
        severity=Severity.high,
        source=PolicySource.seed,
        is_active=True,
    )


def redact_output(text: str) -> str:
    text = re.sub(r"Bearer\s+[A-Za-z0-9._\-]+", "Bearer [REDACTED]", text)
    text = re.sub(r"sk-[A-Za-z0-9._\-]{8,}", "sk-[REDACTED]", text)
    text = re.sub(
        r"[A-Za-z0-9_\-]{24,}\.[A-Za-z0-9_\-]{12,}\.[A-Za-z0-9_\-]{12,}",
        "[REDACTED_TOKEN]",
        text,
    )
    return text


async def run_block_smoke(api_key: str, model: str) -> bool:
    session = DummySession([regex_block_policy()])

    async def override_session():
        return session

    main.app.dependency_overrides[main.get_session] = override_session
    original_resolver = main.resolve_cli_token
    main.resolve_cli_token = fake_caller
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://smoke") as client:
        resp = await client.post(
            "/openai/cli/smoke-token/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": "Smoke BLOCK with fake key AKIA1234567890ABCDEF",
                    }
                ],
            },
        )
    main.resolve_cli_token = original_resolver
    main.app.dependency_overrides.clear()

    ok = (
        resp.status_code == 200
        and resp.headers.get("x-tranquera-action") == "BLOCK"
        and resp.json().get("object") == "chat.completion"
        and not session.added[0].upstream_status
    )
    print(
        f"BLOCK smoke: {'PASS' if ok else 'FAIL'} "
        f"status={resp.status_code} action={resp.headers.get('x-tranquera-action')}"
    )
    return ok


async def run_passthrough_smoke(api_key: str, model: str) -> bool:
    session = DummySession([])

    async def override_session():
        return session

    main.app.dependency_overrides[main.get_session] = override_session
    original_resolver = main.resolve_cli_token
    main.resolve_cli_token = fake_caller
    main.init_client()
    try:
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://smoke",
            timeout=90,
        ) as client:
            resp = await client.post(
                "/openai/cli/smoke-token/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "messages": [
                        {
                            "role": "user",
                            "content": "Reply with exactly: tranquera-openai-smoke-ok",
                        }
                    ],
                    "temperature": 0,
                    "max_tokens": 32,
                },
            )
    finally:
        await main.close_client()
        main.resolve_cli_token = original_resolver
        main.app.dependency_overrides.clear()

    text = resp.text
    if resp.status_code != 200:
        print(f"Passthrough smoke: FAIL status={resp.status_code} body={redact_output(text[:300])}")
        return False

    try:
        data = resp.json()
    except Exception:
        print(f"Passthrough smoke: FAIL non-json body={redact_output(text[:300])}")
        return False

    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    ok = "tranquera-openai-smoke-ok" in str(content).lower()
    print(
        "Passthrough smoke: "
        f"{'PASS' if ok else 'WARN'} status={resp.status_code} "
        f"action={resp.headers.get('x-tranquera-action')} "
        f"provider={main.settings.openai_compat_provider} model={model}"
    )
    if not ok:
        print(f"Passthrough preview: {redact_output(str(content)[:180])}")
    return ok


async def amain() -> int:
    api_key = os.environ.get("API_KEY") or load_dotenv_key(ROOT_ENV, "API_KEY")
    if not api_key:
        print("Missing API_KEY in environment or repository root .env", file=sys.stderr)
        return 2

    model = (
        os.environ.get("OPENAI_COMPAT_TEST_MODEL")
        or load_dotenv_key(ROOT_ENV, "OPENAI_COMPAT_TEST_MODEL")
        or "qwen3.6-plus"
    )
    upstream = os.environ.get("OPENAI_COMPAT_UPSTREAM_URL", "https://opencode.ai/zen/go/v1")
    print(f"Upstream: {upstream}")
    print(f"Model: {model}")
    print("API_KEY: present (redacted)")

    block_ok = await run_block_smoke(api_key, model)
    pass_ok = await run_passthrough_smoke(api_key, model)
    return 0 if block_ok and pass_ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(amain()))
