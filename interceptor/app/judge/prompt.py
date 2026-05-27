import json
from json import JSONDecoder

from app.cascade import PolicyHit
from app.enums import Action, PolicyLayer
from app.models import Policy

JUDGE_MAX_TOKENS = 256
JUDGE_TIMEOUT_S = 60.0

JUDGE_SYSTEM = (
    "Sos un judge de seguridad de datos. "
    "Recibís reglas activas y texto evaluable del prompt. "
    'Respondé SOLO JSON: {"matched": ["<policy_id>", ...]}. '
    'Si nada matchea: {"matched": []}.\n\n'
    "Reglas para decidir:\n"
    "- Marcá una regla SOLO si el prompt claramente la viola.\n"
    "- En la duda, NO marques. Falsos positivos son peores que falsos negativos: "
    "bloquean trabajo legítimo.\n"
    "- Considerá ejemplos, contexto y sinónimos razonables.\n"
    "- No agregues explicación, prefijos ni markdown."
)


def _enum_value(v: object) -> str:
    """Postgres enums may roundtrip as raw strings instead of Enum instances."""
    return v.value if hasattr(v, "value") else str(v)


def format_rules_block(policies: list[Policy]) -> str:
    lines = []
    for policy in policies:
        lines.append(
            f"- id={policy.id} | accion={_enum_value(policy.default_action)} | "
            f"dominio={_enum_value(policy.domain)}\n"
            f"  regla: {policy.rule}"
        )
    return "\n".join(lines)


def format_prompt_texts(texts: list[str]) -> str:
    return "\n---\n".join(texts) if texts else ""


def build_judge_user_content(policies: list[Policy], texts: list[str]) -> str:
    return (
        "REGLAS ACTIVAS:\n"
        f"{format_rules_block(policies)}\n\n"
        "PROMPT DEL USUARIO:\n"
        f"```\n{format_prompt_texts(texts)}\n```\n\n"
        'Respondé SOLO el JSON: {"matched": ["<id>", ...]}'
    )


def build_anthropic_messages(policies: list[Policy], texts: list[str]) -> list[dict[str, str]]:
    return [{"role": "user", "content": build_judge_user_content(policies, texts)}]


def build_openai_messages(policies: list[Policy], texts: list[str]) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": JUDGE_SYSTEM},
        {"role": "user", "content": build_judge_user_content(policies, texts)},
    ]


def build_gemini_prompt(policies: list[Policy], texts: list[str]) -> str:
    return f"{JUDGE_SYSTEM}\n\n{build_judge_user_content(policies, texts)}"


def parse_matched_ids(content_text: str) -> list[str]:
    """Extract matched policy ids from clean JSON, fenced JSON, or text with noise."""
    if not content_text:
        return []

    decoder = JSONDecoder()
    text = content_text.strip()
    candidates = [text]
    candidates.extend(text[index:] for index, char in enumerate(text) if char == "{")

    for candidate in candidates:
        try:
            data, _ = decoder.raw_decode(candidate.lstrip())
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            continue
        raw = data.get("matched")
        if not isinstance(raw, list):
            continue
        return [str(item) for item in raw if isinstance(item, str)]
    return []


def policy_hits_from_ids(matched_ids: list[str], policies: list[Policy]) -> list[PolicyHit]:
    by_id = {str(policy.id): policy for policy in policies}
    hits: list[PolicyHit] = []
    for policy_id in matched_ids:
        policy = by_id.get(policy_id)
        if policy is None:
            continue
        hits.append(
            PolicyHit(
                policy_id=str(policy.id),
                slug=policy.slug,
                layer=PolicyLayer.nl,
                action=Action(_enum_value(policy.default_action)),
                rule=policy.rule,
                matched_text="",
            )
        )
    return hits
