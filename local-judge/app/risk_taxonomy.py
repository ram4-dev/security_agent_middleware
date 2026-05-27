from .schemas import RiskType

RISK_TAXONOMY_VERSION = "risk_taxonomy_v1"

RISK_TYPES: tuple[RiskType, ...] = (
    RiskType.SECRET_LEAK,
    RiskType.PII_LEAK,
    RiskType.PROMPT_INJECTION,
    RiskType.POLICY_BYPASS,
    RiskType.DATA_EXFILTRATION,
    RiskType.DESTRUCTIVE_ACTION,
    RiskType.UNSAFE_TOOL_USE,
    RiskType.CREDENTIAL_ABUSE,
    RiskType.PRIVATE_CODE_LEAK,
    RiskType.BENIGN_REQUEST,
)
