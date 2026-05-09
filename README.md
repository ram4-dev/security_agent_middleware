<img src="./project-logo.png" alt="Tranquera" width="160" align="right" />

# Tranquera

> Un paso controlado entre la intención y la respuesta.

**Tranquera** es el firewall de Claude Code corporativo. Las empresas configuran `ANTHROPIC_BASE_URL` apuntando a un proxy modificable que aplica reglas no-code en runtime con cascada **Regex → Haiku judge** (<200 ms overhead) y cuatro acciones: `BLOCK · REDACT · WARN · LOG`. Compliance officers no técnicos arman las reglas con un visual builder; un AI Suggestor propone reglas nuevas en base a logs.

Pensado para empresas LATAM que dan Claude Code a sus devs y necesitan evidencia auditable frente a LGPD, Habeas Data y la regulación IA emergente.

— Track **AI Security** · Platanus Hack 26 · Buenos Aires · Team 22.

---

## Las 4 layers

```
Layer 4: AI Suggestor          (spec 08) ───────────────────────┐
Layer 3: Admin Backoffice       (spec 04) — visual rule builder │
Layer 2: Interceptor Engine     (spec 01) — proxy modificable   │
Layer 1: Claude Code (cliente)                                  │
                                                                ▼
       (compliance-ready, regulator-friendly, LATAM-first)
```

## Repo

| Carpeta | Qué hay |
|---|---|
| `specs/` | Spec-Driven Development. **Fuente de verdad**. Empezá por [`specs/README.md`](./specs/README.md) y [`specs/00-constitution.md`](./specs/00-constitution.md). |
| `web/` | Next.js 16 + Tailwind 4 + Prisma 7 + Auth.js v5 (Google). Landing pública, back-office del admin y device-flow del CLI. Detalles en [`web/README.md`](./web/README.md). |
| `interceptor/` | Python 3.12 + FastAPI. Proxy Layer 2 — recibe `POST /v1/messages` de Claude Code, aplica la cascada **Regex → Haiku judge** y reenvía a Anthropic. Comparte la misma DB que `web/`. Deployado en Railway. Detalles en [`interceptor/README.md`](./interceptor/README.md). |
| `cli/` | Paquete npm `tranquera`. Onboarding de devs en un comando (`npx tranquera setup`). Device flow contra el back-office, guarda token en `~/.tranquera/config.json`. Detalles en [`cli/README.md`](./cli/README.md). |
| `identidad/` | Sistema de marca. [`identidad/design.md`](./identidad/design.md) es input obligatorio para todo lo que tenga UI o copy. |
| `research/` | Landscape de mercado, papers y datasets. **No tocar** salvo agregar notas. |
| `.claude/`, `.agents/` | Agents y skills compartidos para Claude Code del equipo. |

## Quick start

### Para un dev que va a usar Claude Code detrás de un firewall existente

Una sola línea:

```bash
npx tranquera setup
```

El CLI abre el browser para que loguees con Google, te asocia a tu org y configura `ANTHROPIC_BASE_URL` en tu shell rc. Después usás `claude` igual que siempre. Ver [`cli/README.md`](./cli/README.md) para más detalles.

### Para correr Tranquera localmente (admin + interceptor + DB)

Requiere Docker, Node 20+, pnpm y Python 3.12+ con `uv`.

```bash
# 1. Postgres + extensión vector
docker compose up -d

# 2. Web (admin + landing)
cd web
pnpm install
pnpm db:migrate          # idempotente
cp .env.example .env.local
# editar .env.local: GOOGLE_CLIENT_ID/SECRET para auth real, o dejar vacío para modo demo
pnpm dev                 # http://localhost:3000

# 3. Interceptor (en otra terminal)
cd interceptor
cp .env.example .env
# editar .env: pegar ANTHROPIC_JUDGE_API_KEY (sacala de console.anthropic.com)
uv sync
uv run python scripts/seed_policies.py    # 4 reglas regex de credenciales
uv run uvicorn app.main:app --reload --port 8080

# 4. Probar el proxy con Claude Code
export ANTHROPIC_BASE_URL=http://localhost:8080
claude "AKIAIOSFODNN7EXAMPLE"     # debería bloquearse por la regla aws-access-key
```

Más sobre cada componente: [`web/README.md`](./web/README.md), [`interceptor/README.md`](./interceptor/README.md), [`cli/README.md`](./cli/README.md).

## Cómo se usa Tranquera (vista del producto)

### Para el admin (compliance / security lead)

1. Loguea con Google en `https://<tu-dominio>/admin/login`. El primer login crea automáticamente la org y deja al usuario como **admin owner**.
2. En `/admin/team` invita a sus devs por email — quedan en estado *pendiente* hasta que se loguéen.
3. En `/admin/rules` arma las políticas (reglas en lenguaje natural o regex).
4. En `/admin/events` ve cada prompt que pasó por el firewall, qué regla matcheó, latencia desglosada por capa, etc.

### Para el dev

1. Recibe del admin: *"te agregué a la org en Tranquera, corré `npx tranquera setup`"*.
2. Corre el comando, loguea con Google, listo. Su CLI queda vinculado.
3. Sigue usando `claude` normal. Cada prompt pasa por la cascada de la org y queda atribuido a su cuenta.

## Equipo

- Christian Rojas Rodriguez — [@Christian-Rojas-Rodriguez](https://github.com/Christian-Rojas-Rodriguez)
- Federico Hörl — [@fede-h](https://github.com/fede-h)
- Mauricio Genta — [@5y5F4il](https://github.com/5y5F4il)
- Jaime Aza — [@Jjat00](https://github.com/Jjat00)
- Tomás Leonel Degese — [@tomileonel](https://github.com/tomileonel)
