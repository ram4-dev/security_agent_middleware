# Docs — Tranquera

Este índice es la puerta de entrada para navegar la documentación del repo sin tener que adivinar dónde vive cada decisión.

## Quick path

1. Si necesitás entender el producto, empezá por [`../README.md`](../README.md).
2. Si vas a tocar implementación, leé primero [`../CLAUDE.md`](../CLAUDE.md) y [`../specs/README.md`](../specs/README.md).
3. Si vas a tocar UI, copy o marca, sumá [`../identidad/design.md`](../identidad/design.md).
4. Si vas a tocar multi-provider o harnesses, arrancá por specs 12–16.
5. Si vas a explorar arquitectura futura antes de una spec canónica, revisá [`concepts/`](./concepts/).

## Índice por intención

| Necesito... | Leer primero | Después |
|---|---|---|
| Entender qué es Tranquera | [`../README.md`](../README.md) | [`../project-description.md`](../project-description.md) |
| Trabajar con specs SDD | [`../specs/README.md`](../specs/README.md) | [`../specs/00-constitution.md`](../specs/00-constitution.md) |
| Tocar el interceptor/proxy | [`../specs/01-engine-interceptor.md`](../specs/01-engine-interceptor.md) | [`../interceptor/README.md`](../interceptor/README.md), specs 12, 13 y 15 |
| Tocar el admin web | [`../specs/04-admin-web.md`](../specs/04-admin-web.md) | [`../web/README.md`](../web/README.md), [`../web/AGENTS.md`](../web/AGENTS.md) |
| Tocar landing, identidad o copy | [`../identidad/design.md`](../identidad/design.md) | [`../specs/03-landing-page.md`](../specs/03-landing-page.md) |
| Integrar otro harness/provider | [`../specs/14-harness-integrations.md`](../specs/14-harness-integrations.md) | [`../specs/12-provider-abstraction.md`](../specs/12-provider-abstraction.md), [`../specs/13-openai-compatible-adapter.md`](../specs/13-openai-compatible-adapter.md), [`../specs/16-skill-multi-provider-setup.md`](../specs/16-skill-multi-provider-setup.md) |
| Explorar arquitectura futura | [`./concepts/README.md`](./concepts/README.md) | Promover a `../specs/` cuando haya contratos técnicos y acceptance criteria implementables |
| Implementar Local Judge | [`../specs/17-local-judge-runtime.md`](../specs/17-local-judge-runtime.md) | Specs 18–21 para servicio, dataset/eval, training y deployment |
| Configurar providers localmente | [`../specs/16-skill-multi-provider-setup.md`](../specs/16-skill-multi-provider-setup.md) | [`../scripts/setup-multi-provider.sh`](../scripts/setup-multi-provider.sh) |
| Preparar demo/pitch | [`../specs/06-pitch-demo.md`](../specs/06-pitch-demo.md) | [`../research/landscape.md`](../research/landscape.md), [`../research/papers.md`](../research/papers.md) |

## Specs canónicas

| # | Doc | Tema |
|---|---|---|
| 00 | [`../specs/00-constitution.md`](../specs/00-constitution.md) | Principios, stack y convenciones |
| 01 | [`../specs/01-engine-interceptor.md`](../specs/01-engine-interceptor.md) | Interceptor Engine |
| 02 | [`../specs/02-vdb-bootstrap.md`](../specs/02-vdb-bootstrap.md) | VDB, embeddings y prefilter |
| 03 | [`../specs/03-landing-page.md`](../specs/03-landing-page.md) | Landing pública |
| 04 | [`../specs/04-admin-web.md`](../specs/04-admin-web.md) | Admin backoffice |
| 06 | [`../specs/06-pitch-demo.md`](../specs/06-pitch-demo.md) | Pitch, demo y runbook |
| 07 | [`../specs/07-requirements-docs.md`](../specs/07-requirements-docs.md) | Docs técnicos pendientes |
| 08 | [`../specs/08-ai-suggestor.md`](../specs/08-ai-suggestor.md) | AI Suggestor |
| 09 | [`../specs/09-google-workspace-import.md`](../specs/09-google-workspace-import.md) | Google Docs import |
| 11 | [`../specs/11-policy-packs.md`](../specs/11-policy-packs.md) | Policy packs |
| 12 | [`../specs/12-provider-abstraction.md`](../specs/12-provider-abstraction.md) | Multi-provider core |
| 13 | [`../specs/13-openai-compatible-adapter.md`](../specs/13-openai-compatible-adapter.md) | OpenAI-compatible adapter |
| 14 | [`../specs/14-harness-integrations.md`](../specs/14-harness-integrations.md) | opencode, Pi, Aider, Codex y otros harnesses |
| 15 | [`../specs/15-judge-provider-abstraction.md`](../specs/15-judge-provider-abstraction.md) | NL judge multiprovider |
| 16 | [`../specs/16-skill-multi-provider-setup.md`](../specs/16-skill-multi-provider-setup.md) | Skill + setup multi-provider |
| 17 | [`../specs/17-local-judge-runtime.md`](../specs/17-local-judge-runtime.md) | Local Judge runtime en interceptor |
| 18 | [`../specs/18-local-judge-service.md`](../specs/18-local-judge-service.md) | Servicio Local Judge con vLLM |
| 19 | [`../specs/19-local-judge-dataset-eval.md`](../specs/19-local-judge-dataset-eval.md) | Dataset y evaluación del Local Judge |
| 20 | [`../specs/20-local-judge-training.md`](../specs/20-local-judge-training.md) | Pipeline de entrenamiento del Local Judge |
| 21 | [`../specs/21-local-judge-deployment-observability.md`](../specs/21-local-judge-deployment-observability.md) | Deploy y observabilidad del Local Judge |

## Docs por carpeta

| Carpeta | Qué contiene | Regla de uso |
|---|---|---|
| [`../specs/`](../specs/) | Fuente de verdad SDD | Actualizar antes de cambios grandes de código |
| [`./concepts/`](./concepts/) | Specs conceptuales previas a specs canónicas | Usar para explorar arquitectura y decisiones abiertas sin prometer implementación |
| [`../identidad/`](../identidad/) | Sistema visual, voz y naming | Obligatorio para UI/copy |
| [`../research/`](../research/) | Landscape y papers | No tocar salvo agregar notas explícitas |
| [`../cli/`](../cli/) | CLI de onboarding | Mantener sincronizado con el flujo real de setup/logout |
| [`../interceptor/`](../interceptor/) | Docs del proxy FastAPI | Mantener cerca del código del interceptor |
| [`../web/`](../web/) | Docs del admin/landing | Mantener cerca del código Next.js |
| [`../scripts/`](../scripts/) | Scripts operativos locales | No imprimir tokens/API keys; documentar flags en cada script |

## Qué no indexamos

- Dependencias vendorizadas (`.venv`, `node_modules`, caches).
- Skills de terceros dentro de `.agents/` salvo que se vuelvan parte del producto.
- Reportes temporales de OpenSpec salvo que se archiven como decisión de producto.

## Mantenimiento

- Cuando agregues una spec nueva, actualizá este archivo y [`../specs/README.md`](../specs/README.md).
- Cuando agregues una guía operativa estable, linkeala en "Índice por intención".
- Si un doc queda obsoleto, marcá su reemplazo explícitamente antes de borrarlo.
