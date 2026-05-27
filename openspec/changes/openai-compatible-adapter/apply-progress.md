# Apply Progress — openai-compatible-adapter

## Status

Implemented a focused OpenAI Chat Completions adapter in the interceptor, covering T1–T7 from `specs/13-openai-compatible-adapter.md` at unit/route-test level. Verification-gap follow-up added OpenAI NL cascade parity tests/implementation, canonical Prisma metadata fields plus migration, and route-level streaming BLOCK coverage. A live OpenCode Go upstream smoke now passes via the Tranquera OpenAI route using the root `.env` `API_KEY` without printing the secret. opencode/Aider CLI client smokes remain unrun because those clients are not installed in this environment.

## Completed tasks

- [x] T1 — OpenAI schema subset with permissive Pydantic models (`extra="allow"`).
- [x] T2 — Text extraction for `system`, `developer`, and `user` roles; string content and `{type:"text", text}` blocks; assistant/tool skipped by default.
- [x] T3 — Non-streaming Chat Completions BLOCK synthesizer.
- [x] T4 — Streaming Chat Completions SSE BLOCK synthesizer with `[DONE]`.
- [x] T5 — REDACT mutator for strings and text blocks only, preserving extra fields and non-text blocks.
- [x] T6 — OpenAI-compatible upstream forwarding to `/v1/chat/completions`, with base URL normalization to avoid `/v1/v1/chat/completions`.
- [x] T7 — `POST /openai/cli/{token}/v1/chat/completions` route with path-token attribution, canonical `x-tranquera-*` headers, temporary `x-team22-*` aliases, and OpenAI protocol metadata persistence fields in SQLModel.

## Files changed

- `interceptor/app/protocols.py` — minimal `TextPart`/`NormalizedRequest` dataclasses.
- `interceptor/app/openai_adapter.py` — OpenAI Chat schema, extractor, redactor, BLOCK JSON/SSE synthesizers, upstream path helper.
- `interceptor/app/cascade.py` — protocol-neutral regex text runner while preserving Anthropic wrapper behavior.
- `interceptor/app/config.py` — OpenAI-compatible upstream/provider/integration settings.
- `interceptor/app/upstream.py` — reusable upstream opener and OpenAI-compatible client with `/v1` base URL normalization.
- `interceptor/app/main.py` — OpenAI route, canonical diagnostic headers, metadata-aware interaction persistence, and OpenAI NL cascade seam using normalized/evaluable texts.
- `interceptor/app/nl_layer.py` — protocol-neutral `run_nl_texts` judge entrypoint while preserving the Anthropic `run_nl_layer` wrapper.
- `interceptor/app/models.py` — SQLModel metadata fields: `protocol`, `integration`, `upstream_provider`, `upstream_model`.
- `interceptor/pyproject.toml` — pytest `pythonpath = ["."]` so tests import `app` consistently.
- `interceptor/tests/test_openai_adapter.py` — adapter unit tests.
- `interceptor/tests/test_openai_route.py` — FastAPI route tests with mocked token resolution/session/upstream, covering invalid token, benign LOG forward, BLOCK, REDACT, route-level streaming BLOCK SSE, NL WARN, and NL BLOCK.
- `interceptor/tests/test_prisma_metadata_schema.py` — schema/migration guard for Interaction protocol metadata.
- `interceptor/scripts/smoke_openai_compat_live.py` — secret-redacting live smoke for OpenCode Go upstream via the Tranquera OpenAI route, bypassing local DB with FastAPI dependency overrides.
- `web/prisma/schema.prisma` — canonical Prisma `Interaction` metadata fields.
- `web/prisma/migrations/20260523000000_add_interaction_protocol_metadata/migration.sql` — migration adding protocol/integration/upstream metadata columns.

## TDD Cycle Evidence

| Cycle | RED | GREEN | TRIANGULATE | REFACTOR |
|---|---|---|---|---|
| OpenAI adapter primitives (T1–T6) | Wrote `tests/test_openai_adapter.py`; first run failed during collection because app test import path / adapter module support was absent (`ModuleNotFoundError: No module named 'app'`). | Added pytest pythonpath plus `protocols.py`/`openai_adapter.py`; `UV_INDEX_URL=https://pypi.org/simple uv run pytest tests/test_openai_adapter.py` passed 7 tests. | Added cases for permissive extras, mixed blocks, skipped assistant/tool roles, non-text preservation, SSE ordering, and `/v1` path behavior. | Ran focused ruff and adjusted imports/line length. |
| OpenAI route + attribution (T7) | Added `tests/test_openai_route.py` for unknown token, benign LOG forwarding, BLOCK without upstream, and REDACT forwarding/persistence. These were authored before route verification but after the adapter skeleton existed. | Implemented `/openai/cli/{token}/v1/chat/completions`; `UV_INDEX_URL=https://pypi.org/simple uv run pytest tests/test_openai_route.py` passed 4 tests. | Route tests assert canonical and alias headers, no upstream on BLOCK, original benign forwarding, redacted forwarded body, query propagation, metadata fields, and no original matched secret in persisted prompt. | Extracted `_diagnostic_headers`; kept Anthropic path behavior intact while adding canonical headers. |
| Full interceptor check | Exact `uv run pytest` failed in this environment before tests due a configured private package index returning 403 for `asyncpg`. | `UV_INDEX_URL=https://pypi.org/simple uv run pytest` passed 11 tests. | Focused adapter and route coverage is isolated from real DB/upstream/API keys. | `UV_INDEX_URL=https://pypi.org/simple uv run ruff check app/main.py app/openai_adapter.py app/protocols.py app/models.py tests/test_openai_adapter.py tests/test_openai_route.py` passed. |
| Verification gap fixes — NL cascade parity | Added OpenAI route tests for NL WARN and NL BLOCK using a mocked `run_nl_texts` seam; first run failed because OpenAI route stayed LOG and NL BLOCK still touched upstream. | Added protocol-neutral `run_nl_texts` in `nl_layer.py` and invoked it from `_process_openai_chat` after regex when NL is enabled; focused route/schema tests passed 9 tests. | Tests assert system/developer/user OpenAI texts are passed to NL, assistant text is skipped, WARN forwards with headers/persistence, and NL BLOCK returns Chat Completions shape without upstream. | Preserved Anthropic behavior by keeping `run_nl_layer(req, policies)` as a wrapper over extracted Anthropic texts. |
| Verification gap fixes — Prisma metadata | Added schema/migration guard test; first run failed because canonical Prisma `Interaction` lacked protocol/integration/upstream fields and no migration mentioned the columns. | Added `web/prisma/schema.prisma` fields plus migration `20260523000000_add_interaction_protocol_metadata`; schema tests passed. | Test checks Prisma field names/defaults and DB column mappings stay consistent with SQLModel columns. | Kept SQLModel field names unchanged and mapped Prisma camelCase fields to snake_case columns. |
| Verification gap fixes — streaming BLOCK route | Added route-level streaming BLOCK test that consumes SSE bytes and asserts Chat Completions chunks, `[DONE]`, headers, and no upstream. | Existing synthesizer/route behavior satisfied the new route-level coverage after test addition. | This covers the HTTP route path, not only the adapter generator unit. | Combined async context managers for Ruff SIM117. |

## Verification commands run

- `cd interceptor && DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/test uv run pytest tests/test_openai_adapter.py` — RED/tooling check failed initially because default uv resolution used a private index that returned 403; rerun with explicit public index.
- `cd interceptor && DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/test uv run --locked --index-url https://pypi.org/simple pytest tests/test_openai_adapter.py` — first meaningful RED failed with `ModuleNotFoundError: No module named 'app'` before adapter implementation/path config.
- `cd interceptor && DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/test uv run --locked --index-url https://pypi.org/simple pytest tests/test_openai_adapter.py` — 7 passed.
- `cd interceptor && DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/test uv run --locked --index-url https://pypi.org/simple pytest tests/test_openai_route.py` — 3 passed before adding the benign LOG route case.
- `cd interceptor && UV_INDEX_URL=https://pypi.org/simple uv run pytest tests/test_openai_route.py` — 4 passed.
- `cd interceptor && uv run pytest` — failed before running tests because configured package index `https://pypi.artifacts.furycloud.io/simple` returned 403 for dependency resolution.
- `cd interceptor && UV_INDEX_URL=https://pypi.org/simple uv run pytest` — 11 passed, 7 warnings about `datetime.utcnow()` defaults in existing SQLModel factories.
- `cd interceptor && uv run ruff check .` — failed before linting for the same private-index dependency resolution issue.
- `cd interceptor && UV_INDEX_URL=https://pypi.org/simple uv run ruff check .` — ran and failed on pre-existing lint in `scripts/seed_prod.py` and `app/enums.py`, plus new-file formatting before refactor.
- `cd interceptor && UV_INDEX_URL=https://pypi.org/simple uv run ruff check --fix app/main.py app/openai_adapter.py app/protocols.py app/models.py tests/test_openai_adapter.py tests/test_openai_route.py` — fixed import ordering; two manual fixes remained.
- `cd interceptor && UV_INDEX_URL=https://pypi.org/simple uv run ruff check app/main.py app/openai_adapter.py app/protocols.py app/models.py tests/test_openai_adapter.py tests/test_openai_route.py` — passed.
- `cd interceptor && UV_INDEX_URL=https://pypi.org/simple uv run pytest` — 11 passed.
- `cd interceptor && UV_INDEX_URL=https://pypi.org/simple uv run pytest tests/test_openai_route.py tests/test_prisma_metadata_schema.py` — RED for verification-gap tests: NL WARN returned LOG, NL BLOCK touched upstream, Prisma schema fields missing, migration columns missing.
- `cd interceptor && UV_INDEX_URL=https://pypi.org/simple uv run pytest tests/test_openai_route.py tests/test_prisma_metadata_schema.py` — GREEN after fixes: 9 passed, 16 warnings.
- `cd interceptor && uv run pytest` — still failed before tests because configured private package index returned 403 resolving `asyncpg`; rerun with explicit public index.
- `cd interceptor && UV_INDEX_URL=https://pypi.org/simple uv run pytest` — 16 passed, 16 warnings.
- `cd interceptor && uv run ruff check .` — still failed before linting because configured private package index returned 403 resolving `asyncpg`; rerun with explicit public index.
- `cd interceptor && UV_INDEX_URL=https://pypi.org/simple uv run ruff check app/main.py app/nl_layer.py app/openai_adapter.py app/protocols.py app/models.py tests/test_openai_adapter.py tests/test_openai_route.py tests/test_prisma_metadata_schema.py` — passed after formatting fixes.
- `cd interceptor && UV_INDEX_URL=https://pypi.org/simple uv run ruff check .` — executed but failed on pre-existing lint in `app/enums.py` and `scripts/seed_prod.py`, outside the touched verification-gap scope.
- `cd interceptor && UV_INDEX_URL=https://pypi.org/simple uv run ruff check scripts/smoke_openai_compat_live.py` — passed.
- `cd interceptor && UV_INDEX_URL=https://pypi.org/simple uv run python scripts/smoke_openai_compat_live.py` — passed: BLOCK smoke PASS and passthrough smoke PASS against OpenCode Go with `API_KEY` redacted.

## Deviations / remaining work

- Live OpenCode Go upstream smoke via the Tranquera OpenAI route passes: BLOCK returns synthetic Chat Completions without upstream and benign passthrough returns LOG from `https://opencode.ai/zen/go/v1` with model `qwen3.6-plus`.
- opencode CLI and Aider CLI smokes were not run because those clients are not installed in this environment; this remains unverified at client-rendering level.
- Exact unmodified `uv run ...` commands fail in this environment due a configured private package index returning 403; using `UV_INDEX_URL=https://pypi.org/simple` verifies the code path without exposing secrets.
- Full-project Ruff still reports pre-existing issues in `app/enums.py` and `scripts/seed_prod.py`; focused Ruff over touched OpenAI/NL/schema-test files passes.

## Workload / PR boundary

Single-PR scope accepted by parent. Approximate implemented workload is a bounded interceptor-only change: adapter module, route, upstream client support, metadata fields, and tests. No commits made.
