# Verify Report — openai-compatible-adapter

## Status

**PARTIAL PASS — code/test blockers are fixed and live OpenCode Go upstream smoke passes; installed opencode/Aider CLI client smokes remain unrun.**

Within the locally verifiable scope, the OpenAI adapter, route behavior, NL cascade parity, streaming BLOCK route, Prisma metadata schema/migration, and live OpenCode Go passthrough now pass. The smoke used the root `.env` `API_KEY` at runtime and printed only redacted presence/status.

## Scope verified

- Spec: `specs/13-openai-compatible-adapter.md`
- Dependency context: `specs/12-provider-abstraction.md`
- Apply evidence: `openspec/changes/openai-compatible-adapter/apply-progress.md`
- Previous verify report: `openspec/changes/openai-compatible-adapter/verify-report.md`
- Changed code/tests:
  - `interceptor/app/openai_adapter.py`
  - `interceptor/app/protocols.py`
  - `interceptor/app/main.py`
  - `interceptor/app/cascade.py`
  - `interceptor/app/nl_layer.py`
  - `interceptor/app/upstream.py`
  - `interceptor/app/config.py`
  - `interceptor/app/models.py`
  - `interceptor/tests/test_openai_adapter.py`
  - `interceptor/tests/test_openai_route.py`
  - `interceptor/tests/test_prisma_metadata_schema.py`
  - `web/prisma/schema.prisma`
  - `web/prisma/migrations/20260523000000_add_interaction_protocol_metadata/migration.sql`

## Spec coverage

| Acceptance criterion | Result | Evidence / finding |
|---|---:|---|
| `POST /openai/cli/{token}/v1/chat/completions` validates JSON and resolves caller by token | PASS | Route exists; invalid token test passes; invalid JSON/Pydantic validation paths exist in code. |
| Benign prompt forwards to upstream and returns compatible body/stream | PASS for non-stream live upstream / PARTIAL for streaming passthrough | Non-stream benign LOG forwarding is route-tested with mocked upstream and live-smoked against OpenCode Go (`https://opencode.ai/zen/go/v1`, `qwen3.6-plus`). Streaming passthrough is implemented through the same streamed relay path but has no dedicated benign streaming live test. |
| Prompt with policy `BLOCK` returns `200` with Chat Completions-shaped response and no upstream call | PASS | Non-stream route test and streaming route test both assert Chat Completions shape/SSE and no upstream call. |
| Prompt with policy `REDACT` forwards mutated body without persisting original secret | PASS | Route test asserts redacted forwarded system/user text, non-text preservation, upstream path, query propagation, and redacted persisted prompt. |
| Streaming `BLOCK` renders correctly in at least one OpenAI-compatible client | PARTIAL | Route-level SSE bytes are tested. Live upstream smoke now passes for non-stream passthrough, but installed opencode/Aider client rendering was not run because those clients are unavailable in this environment. |
| Canonical `x-tranquera-*` headers are present | PASS | `_diagnostic_headers` emits `x-tranquera-trace-id`, `x-tranquera-action`, and `x-tranquera-protocol`; route tests assert action/protocol on relevant paths. |
| `interactions.protocol = 'openai_chat'` and `integration` are set by route/config | PASS at schema/test level | SQLModel fields, Prisma schema fields, and migration are present; route tests assert persisted metadata. Real DB migration was not executed in this verify pass. |
| Tests do not require real API keys for BLOCK and parse/redact | PASS | Unit/route tests use fake placeholders and monkeypatched upstream/NL seams. |

## Previous blocker re-check

| Previous blocker | Current result | Evidence |
|---|---:|---|
| OpenAI route skipped NL cascade parity | FIXED | `_process_openai_chat` calls `run_nl_texts` after regex when NL is enabled; tests cover NL WARN and NL BLOCK. |
| Canonical Prisma schema/migration missing metadata fields | FIXED | `web/prisma/schema.prisma` declares `protocol`, `integration`, `upstreamProvider`, and `upstreamModel`; migration adds the four DB columns. |
| External client smoke acceptance unmet | STILL OPEN | opencode/Aider/local smokes remain unavailable/unrun. |
| Route-level streaming BLOCK verification missing | FIXED | `test_openai_route_streaming_block_returns_chat_sse_and_done` consumes route SSE and asserts chunks, `[DONE]`, headers, and no upstream call. |

## Task completion

| Task | Result | Notes |
|---|---:|---|
| T1 — OpenAI schema subset | PASS | Permissive Pydantic model and extra preservation covered. |
| T2 — Text extraction | PASS | Covers string content, mixed text/non-text blocks, system/developer/user roles, and skipped assistant/tool roles. |
| T3 — BLOCK JSON synthesizer | PASS | Shape covered by unit and route tests. |
| T4 — BLOCK SSE synthesizer | PASS | Unit test covers order; route test covers streamed HTTP response and `[DONE]`. |
| T5 — REDACT mutator | PASS | Preserves extras/non-text and redacts evaluable text only. |
| T6 — OpenAI-compatible provider forwarder | PASS | Mocked route verifies `/v1/chat/completions`, query propagation, and header/body forwarding. Live smoke also passes against OpenCode Go using `interceptor/scripts/smoke_openai_compat_live.py`. |
| T7 — Route + token attribution | PASS | Token rejection, caller metadata, route persistence, headers, and no-upstream BLOCK are covered. |
| T8 — opencode smoke | PARTIAL | Live OpenCode Go upstream smoke passes through Tranquera route. opencode CLI itself is not installed, so custom provider client smoke remains unrun. |
| T9 — Aider/local smoke | FAIL / UNVERIFIED | Not run; unavailable in this worker session. |

## Strict TDD compliance

**Result: PASS with caveats.**

- `openspec/config.yaml` declares `strict_tdd: true` and test runner `cd interceptor && uv run pytest`.
- `apply-progress.md` contains a `TDD Cycle Evidence` table.
- Reported test files exist and were re-run: `interceptor/tests/test_openai_adapter.py`, `interceptor/tests/test_openai_route.py`, and `interceptor/tests/test_prisma_metadata_schema.py`.
- Evidence includes meaningful RED/GREEN cycles for adapter primitives, route behavior, NL parity, Prisma metadata, and streaming BLOCK route coverage.
- Assertion quality is meaningful: tests assert response shape, SSE order/content, no-upstream BLOCK behavior, forwarded/redacted payloads, role filtering, metadata persistence, and schema/migration guards.
- Caveats:
  - External smoke task T8 has live upstream execution evidence, but not opencode CLI client evidence. T9 has no Aider/local CLI execution evidence.
  - Plain `uv run ...` fails before test execution in this environment due a private package index 403; public-index override was required to execute tests.
  - Real DB migration was not applied during verification.

## Review workload / PR boundary

- Preflight requested `single-pr-default` and `review_budget=no-fixed-limit`.
- Current tracked diff stat: 371 insertions / 50 deletions across 9 tracked files, plus untracked adapter/tests/spec/OpenSpec/migration files.
- The change is broad but still one coherent OpenAI-adapter slice: interceptor route/adapter, NL seam, tests, and Prisma metadata.
- No commits were made.

## Validation commands

| Command | Outcome |
|---|---|
| `git status --short && git diff --name-only && git ls-files --others --exclude-standard && git diff --stat` | Reviewed modified/untracked scope and tracked diff stat. |
| `cd interceptor && uv run pytest` | Failed before tests due configured private package index returning 403 while resolving `asyncpg`; environment/tooling failure, not a test failure. |
| `cd interceptor && UV_INDEX_URL=https://pypi.org/simple uv run pytest tests/test_openai_adapter.py tests/test_openai_route.py tests/test_prisma_metadata_schema.py` | Passed: 16 tests, 16 warnings. |
| `cd interceptor && UV_INDEX_URL=https://pypi.org/simple uv run pytest` | Passed: 16 tests, 16 warnings. |
| `cd interceptor && uv run ruff check .` | Failed before linting due the same private-index 403 resolving `asyncpg`; environment/tooling failure. |
| `cd interceptor && UV_INDEX_URL=https://pypi.org/simple uv run ruff check app/main.py app/nl_layer.py app/openai_adapter.py app/protocols.py app/models.py app/cascade.py app/config.py app/upstream.py tests/test_openai_adapter.py tests/test_openai_route.py tests/test_prisma_metadata_schema.py` | Passed. |
| `cd interceptor && UV_INDEX_URL=https://pypi.org/simple uv run ruff check .` | Executed and failed on pre-existing lint in `app/enums.py` and `scripts/seed_prod.py`, outside the touched OpenAI adapter scope. |
| `git diff --check` | Passed; no whitespace errors in tracked diff. |
| `cd interceptor && UV_INDEX_URL=https://pypi.org/simple uv run ruff check scripts/smoke_openai_compat_live.py` | Passed. |
| `cd interceptor && UV_INDEX_URL=https://pypi.org/simple uv run python scripts/smoke_openai_compat_live.py` | Passed: OpenCode Go BLOCK smoke and benign passthrough smoke via Tranquera route. API key was loaded at runtime and redacted from output. |

## Validation not run

- `pnpm prisma validate`, `pnpm typecheck`, and `pnpm build` were not run because `web/prisma.config.ts` unconditionally calls `dotenv.config({ path: '.env.local' })` and `dotenv.config({ path: '.env' })`; Safe Secrets Guardrail forbids reading secret files. Prisma schema/migration were instead verified by static test coverage.
- opencode CLI and Aider/local CLI smokes were not run because those clients are unavailable. Live OpenCode Go upstream smoke was run through Tranquera and passed; no CLI client pass is claimed.

## Findings

### Remaining blocker

1. **Installed OpenAI-compatible client smokes are still missing.**  
   Spec 13 requires streaming BLOCK to render in an OpenAI-compatible client and lists opencode/Aider/local smoke tasks. Route-level SSE coverage and live OpenCode Go upstream passthrough are good, but they are not a substitute for running an installed opencode/Aider/local client or explicitly re-scoping that acceptance criterion.

### Non-blocking gaps / risks

- OpenAI benign streaming passthrough lacks a dedicated route test; current confidence comes from shared streamed upstream relay code and non-stream LOG route coverage.
- Real Prisma migration application was not verified against a database in this pass.
- Full-project Ruff still fails on pre-existing lint in untouched files (`app/enums.py`, `scripts/seed_prod.py`). Focused Ruff over changed files passes.
- `web/prisma.config.ts` loads `.env.local`/`.env` unconditionally, which prevents secret-safe Prisma CLI validation in this harness without a secure execution path or config override.

## Final recommendation

Do not mark `openai-compatible-adapter` fully verified until one of these happens:

1. Install/run and record at least one real OpenAI-compatible client smoke for streaming BLOCK plus opencode/Aider/local coverage where available; or
2. Explicitly re-scope the CLI client-rendering parts of T8/T9 to a follow-up change, keeping this PR as adapter/route/schema/test/live-upstream coverage only.
