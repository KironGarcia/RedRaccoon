# db/schema.py
# Cômodo: definição do schema SQLite por engagement.
# Por quê: DDL fixo e auditável — o cliente vê exatamente o que a DB guarda.

DDL_ENGAGEMENT_CONFIG = """
CREATE TABLE IF NOT EXISTS engagement_config (
    id INTEGER PRIMARY KEY,
    engagement_name TEXT,
    client_name TEXT,
    client_name_variants TEXT,
    domains TEXT,
    ip_ranges TEXT,
    known_contacts TEXT,
    allow_list TEXT,
    created_at TIMESTAMP,
    active BOOLEAN
);
"""

DDL_ENTITY_MAPPING = """
CREATE TABLE IF NOT EXISTS entity_mapping (
    id INTEGER PRIMARY KEY,
    engagement_id INTEGER,
    real_value TEXT,
    placeholder TEXT,
    entity_type TEXT,
    first_seen TIMESTAMP,
    occurrence_count INTEGER,
    UNIQUE(engagement_id, real_value)
);
"""

DDL_SANITIZATION_LOG = """
CREATE TABLE IF NOT EXISTS sanitization_log (
    id INTEGER PRIMARY KEY,
    engagement_id INTEGER,
    timestamp TIMESTAMP,
    action TEXT,
    entities_processed INTEGER
);
"""

ALL_DDL = (
    DDL_ENGAGEMENT_CONFIG,
    DDL_ENTITY_MAPPING,
    DDL_SANITIZATION_LOG,
)
