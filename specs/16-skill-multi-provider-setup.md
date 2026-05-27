# 16 — Skill + Multi-provider Setup

> Especifica una skill operativa y un script modular para configurar Tranquera en múltiples harnesses/providers. En v1 cubre **opencode** vía OpenAI-compatible y **Anthropic/Claude Code** vía `ANTHROPIC_BASE_URL`, sin exponer tokens ni API keys en logs.

---

## Estado actual

Draft inicial. Existe un primer script en [`../scripts/setup-multi-provider.sh`](../scripts/setup-multi-provider.sh) que instala configuración local para `opencode`, `anthropic` o ambos. La skill todavía no está materializada como carpeta `SKILL.md`; esta spec define el contrato antes de crearla.

---

## Decisión corta

El setup multi-provider debe ser una frontera fina:

```text
usuario/admin → skill de setup → script modular → config local del harness → Tranquera proxy
```

La skill no debe duplicar la lógica del script. La skill explica cuándo usar cada integración, qué datos pedir y cómo validar. El script hace las escrituras repetibles y secret-safe.

---

## Goals

- Crear una skill reusable para instalar Tranquera en harnesses soportados.
- Mantener `opencode` y `anthropic` como primeros targets.
- Diseñar el script para agregar providers sin reescribir parsing, validación ni logging.
- Evitar imprimir tokens, API keys o URLs completas con token embebido.
- Permitir modo interactivo con menú de providers y prompts guiados.
- Permitir `--dry-run` para revisar qué archivos cambiarían.
- Dejar un camino claro para sumar Pi, Aider, Codex y LiteLLM después.

## Non-Goals

- No guardar API keys en el repo.
- No leer `.env` ni imprimir variables sensibles.
- No implementar device flow dentro del script en esta fase.
- No prometer soporte completo para todos los modelos de opencode.
- No reemplazar `npx tranquera setup`; este flujo complementa integraciones multi-provider.

---

## Skill target

### Nombre propuesto

```text
tranquera-setup
```

### Ubicación propuesta

```text
.skills/tranquera-setup/SKILL.md
```

Si el runtime elegido requiere otra convención, mantener el nombre de skill y adaptar solo la carpeta.

### Frontmatter propuesto

```yaml
---
name: tranquera-setup
description: Configure Tranquera as a policy-enforcing proxy for coding-agent harnesses such as opencode and Anthropic/Claude Code. Use when installing, validating, rotating, or removing local Tranquera provider setup without exposing tokens or API keys.
---
```

### Cuerpo mínimo de la skill

La skill debe ser corta y operativa:

1. Identificar el harness: `opencode`, `anthropic`, `all`.
2. Pedir o confirmar:
   - `TRANQUERA_BASE_URL` público o local;
   - token de dev/org emitido por Tranquera;
   - modelo default para OpenAI-compatible si aplica;
   - archivo de config destino si no se usa default.
3. Ejecutar [`scripts/setup-multi-provider.sh`](../scripts/setup-multi-provider.sh) con flags explícitos.
4. Validar sin exponer secretos:
   - archivo creado/modificado;
   - comando de smoke benigno;
   - evento visible en admin con `integration` correcto.
5. Para errores, reportar paths y acciones, nunca valores secretos.

---

## Script contract

### Comando base

```bash
# Wizard interactivo
./scripts/setup-multi-provider.sh

# Modo no interactivo / automatizable
./scripts/setup-multi-provider.sh --provider all --base-url https://proxy.tranquera.dev --token "$TRANQUERA_TOKEN"
```

### Providers v1

| Provider | Qué configura | Protocolo | Archivo destino |
|---|---|---|---|
| `opencode` | Custom provider `tranquera` | OpenAI Chat Completions | `~/.config/opencode/opencode.json` por default |
| `anthropic` | `ANTHROPIC_BASE_URL` para Claude Code | Anthropic Messages | shell rc detectado (`.zshrc`, `.bashrc`, etc.) |
| `all` | Ejecuta `opencode` + `anthropic` | mixto | ambos |

### Reglas secret-safe

- El token puede entrar por `--token` o `TRANQUERA_TOKEN`.
- El script puede escribir el token en configs locales, porque esos clientes lo necesitan para rutear por path.
- El script no imprime el token ni URLs completas con token.
- El script no lee `.env`.
- El script no valida API keys llamando a proveedores externos en esta fase.

---

## Modularidad requerida

Agregar un provider nuevo debe requerir solo:

1. Agregar el nombre a `SUPPORTED_PROVIDERS`.
2. Implementar `setup_<provider>()`.
3. Agregar una fila en esta spec.
4. Agregar un smoke manual en spec 14 o spec específica.

No se debe tocar la lógica común de:

- parsing de flags;
- normalización de `base_url`;
- detección de shell rc;
- backup de archivos;
- logging seguro;
- `--dry-run`.

---

## Acceptance Criteria

- [x] `./scripts/setup-multi-provider.sh --help` muestra providers y flags.
- [x] `./scripts/setup-multi-provider.sh` o `--interactive` muestra menú `all|opencode|anthropic`, pide URL/token/opciones y no imprime el token.
- [x] `--provider opencode --dry-run` no escribe archivos y no imprime token.
- [x] `--provider anthropic --dry-run` muestra el rc destino sin imprimir token.
- [x] `--provider opencode` crea o mergea config `provider.tranquera` sin borrar providers existentes.
- [x] `--provider anthropic` escribe un bloque idempotente de `ANTHROPIC_BASE_URL`.
- [x] Correr dos veces el script no duplica bloques ni rompe JSON.
- [ ] Un prompt benigno desde opencode llega al admin con `integration='opencode'`.
- [ ] Un prompt benigno desde Claude Code llega al admin con `integration='claude-code'` o el default configurado.

---

## Tasks

- [x] **T1 — Script skeleton.** Crear `scripts/setup-multi-provider.sh` con flags, `--help`, `--dry-run` y providers `opencode|anthropic|all`.
- [x] **T1b — Interactive wizard.** Si se ejecuta sin argumentos o con `--interactive`, pedir provider, base URL, token oculto, modelo/config/rc según corresponda y confirmación final.
- [x] **T2 — Docs index.** Crear `docs/README.md` como índice general del repo.
- [ ] **T3 — Skill materialization.** Crear `SKILL.md` de `tranquera-setup` usando el contrato de esta spec.
- [ ] **T4 — opencode smoke doc.** Agregar guía copiável de menos de 10 líneas para opencode.
- [ ] **T5 — Anthropic smoke doc.** Agregar guía de verificación para Claude Code/Anthropic.
- [ ] **T6 — Uninstall/logout mode.** Definir `--remove` para limpiar config local sin tocar otros providers.

---

## Verification

```bash
./scripts/setup-multi-provider.sh --help
./scripts/setup-multi-provider.sh --interactive
./scripts/setup-multi-provider.sh --provider opencode --token dummy --dry-run
./scripts/setup-multi-provider.sh --provider anthropic --token dummy --dry-run
bash -n ./scripts/setup-multi-provider.sh
# Idempotency check: run --provider all twice against temp --opencode-config/--shell-rc paths,
# then assert valid JSON and a single Tranquera rc block.
```

Smokes reales quedan fuera del script porque requieren token y upstream API key válidos.

---

## Dependencias

- [12 — Provider Abstraction / Multi-provider Core](./12-provider-abstraction.md)
- [13 — OpenAI-compatible Adapter](./13-openai-compatible-adapter.md)
- [14 — Harness Integrations](./14-harness-integrations.md)
- [15 — Judge Provider Abstraction](./15-judge-provider-abstraction.md)
