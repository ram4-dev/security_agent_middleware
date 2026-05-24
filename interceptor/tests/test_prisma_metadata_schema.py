import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "web" / "prisma" / "schema.prisma"
MIGRATIONS = ROOT / "web" / "prisma" / "migrations"


def test_prisma_interaction_declares_protocol_metadata_fields():
    schema = SCHEMA.read_text()
    interaction = re.search(r"model Interaction \{(?P<body>.*?)\n\}", schema, re.DOTALL)

    assert interaction is not None
    body = interaction.group("body")
    assert re.search(r'protocol\s+String\s+@default\("anthropic_messages"\)', body)
    assert re.search(r'integration\s+String\s+@default\("claude-code"\)', body)
    assert re.search(r'upstreamProvider\s+String\?\s+@map\("upstream_provider"\)', body)
    assert re.search(r'upstreamModel\s+String\?\s+@map\("upstream_model"\)', body)


def test_prisma_migration_adds_interaction_protocol_metadata_columns():
    migration_sql = "\n".join(path.read_text() for path in MIGRATIONS.glob("*/migration.sql"))

    assert 'ALTER TABLE "interactions"' in migration_sql
    assert '"protocol"' in migration_sql
    assert '"integration"' in migration_sql
    assert '"upstream_provider"' in migration_sql
    assert '"upstream_model"' in migration_sql
