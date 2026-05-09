# Top Papers — AI Safety (HF / arXiv, últimos meses)

Enfoque: papers que ya aparecen en HF Papers o arXiv recientes y son **accionables como base para un hack** (técnica clara, idealmente con código o demo).

## 1. Jailbreaking to Jailbreak (J2)
- **ID**: arXiv 2502.09638 — [HF](https://huggingface.co/papers/2502.09638)
- **Idea**: un humano jailbreakea un LLM refusal-trained y lo convierte en *J2 attacker* que sistemáticamente jailbreakea otros modelos.
- **Resultados**: Sonnet 3.5 logra 93% ASR contra GPT-4o, Gemini 1.5 Pro logra 91% (HarmBench).
- **Por qué importa**: red teaming automatizado de baja fricción — un ingeniero solo necesita un modelo "convertido" para auditar otros.

## 2. JBFuzz — Fuzzing-Based Jailbreaks
- **Idea**: trata el espacio de inputs del LLM como un binario y aplica fuzzing con feedback evolutivo.
- **Resultados**: 99% ASR contra GPT-4o, Gemini 2.0, DeepSeek-V3. ~60s y ~7 queries en promedio por jailbreak exitoso.
- **Por qué importa**: muestra que las defensas reactivas (rate limiting, classifier post-hoc) son insuficientes.

## 3. M2S — Multi-turn to Single-turn Jailbreak
- **Venue**: ACL 2025 ([paper](https://aclanthology.org/2025.acl-long.805/))
- **Idea**: reformatea diálogos multi-turno (donde la mayoría de defensas asumen contexto coherente) en un único prompt estructurado.
- **Resultados**: 70.6%–95.9% ASR cross-modelos.
- **Por qué importa**: empuja a las defensas a no asumir el formato de la conversación.

## 4. GPTFUZZER
- **ID**: arXiv 2309.10253 — [HF](https://huggingface.co/papers/2309.10253)
- **Idea**: red teaming con prompts auto-generados via fuzzing.
- **Por qué importa**: paper seminal del enfoque automated red teaming, código abierto disponible.

## 5. Autonomous Jailbreaking (Nature Communications 2026)
- **Idea**: modelos de razonamiento (DeepSeek-R1, Gemini 2.5 Flash, Grok 3 Mini, Qwen3) jailbreakean a otros modelos sin intervención humana.
- **Resultado**: 97.14% overall success rate.
- **Por qué importa**: confirma que la era "agente vs agente" en seguridad ya empezó.

## 6. The Landscape of Prompt Injection Threats in LLM Agents
- **ID**: arXiv 2602.10453 — [PDF](https://arxiv.org/pdf/2602.10453)
- **Idea**: taxonomía de ataques de prompt injection en agentes (delivery vectors, attack modalities, propagation).
- **Por qué importa**: mapa conceptual indispensable para ubicar dónde se ataca un agente.

## 7. Prompt Injection on Agentic Coding Assistants
- **ID**: arXiv 2601.17548
- **Idea**: taxonomía 3D de ataques contra coding agents (delivery / modality / propagation).
- **Resultado**: >85% de los ataques comprometen al menos una plataforma mayor.
- **Por qué importa**: directamente aplicable a la ola de "AI for code" + agentes.

## 8. ARGUS — Context-Aware Prompt Injection Defense
- **ID**: arXiv 2605.03378
- **Idea**: defensa para agentes LLM que incorpora contexto de la sesión, no solo el prompt aislado.
- **Por qué importa**: representa el state-of-the-art de defensas a nivel runtime.

## 9. ML-Bench&Guard — Policy-Grounded Multilingual Safety
- **ID**: arXiv 2605.00689
- **Idea**: benchmark + guardrail multilingüe (14 idiomas) construido directamente desde regulaciones regionales.
- **Por qué importa**: el primer intento serio de safety culturalmente alineado a jurisdicciones — gap directo para LATAM (incluyendo PT-BR).

## 10. XL-SafetyBench — Country-Grounded Cross-Cultural
- **ID**: arXiv 2605.05662
- **Idea**: 5,500 test cases en 10 país-idioma pairs (US, FR, DE, ES, KR, JP, IN, ID, TR, AE).
- **Hallazgo crítico**: modelos *locales* muestran trade-off lineal ASR-NSR (r=-0.81) → su "safety aparente" es solo *generation failure*, no alineamiento real.
- **Por qué importa**: **no incluye Portugués ni países LATAM** — gap explícito y verificable.

---

## Tendencias agregadas

1. **Red teaming es el subárea más caliente** — varios papers con ASR > 90% en 2025-2026. La industria está corriendo para construir defensas runtime.
2. **El frente de batalla se movió de modelo aislado → agentes con tool use**. Las defensas que funcionan en chat fallan en workflows con web/MCP/tools.
3. **Multilingual safety está crónicamente sub-investigado**: >90% de la literatura de safety es en inglés. Los benchmarks que existen traducen prompts en lugar de capturar cómo el daño se manifiesta nativamente.
4. **"Local models" son frágiles**: los modelos entrenados en países con menos data parecen safe pero solo porque generan basura. Riesgo enterprise real para empresas que quieren modelos en español/portugués.

## Aplicabilidad para el hack

| Paper | ¿Qué se puede demostrar en 48h? |
|---|---|
| J2 | Pipeline open-source que toma cualquier modelo OSS y lo convierte en red-teamer |
| ML-Bench&Guard | Benchmark localizado AR/BR/MX construido desde leyes locales (PL 2338, S-0071/2025) |
| XL-SafetyBench | Extender el benchmark a `pt-BR` y `es-AR` con prompts culturalmente nativos |
| ARGUS | Wrapper de runtime defense para frameworks LATAM (ej. integración con LangChain en español) |
