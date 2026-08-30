from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

CURRENT_SCHEMA_VERSION = 2


def ensure_migration_table(engine: Engine):
    with engine.begin() as conn:
        conn.execute(text('''CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)'''))


def applied_versions(engine: Engine):
    ensure_migration_table(engine)
    with engine.connect() as conn:
        return {row[0] for row in conn.execute(text('SELECT version FROM schema_migrations ORDER BY version'))}


def apply_migrations(engine: Engine):
    ensure_migration_table(engine)
    applied = applied_versions(engine)
    insp = inspect(engine)

    # v1: baseline marker for the RC schema.
    if 1 not in applied:
        with engine.begin() as conn:
            conn.execute(text('INSERT INTO schema_migrations(version) VALUES (1)'))

    # v2: class_id on students. Safe for existing RC databases and new installs.
    if 2 not in applied:
        cols = {c['name'] for c in insp.get_columns('students')} if insp.has_table('students') else set()
        with engine.begin() as conn:
            if 'class_id' not in cols and insp.has_table('students'):
                conn.execute(text('ALTER TABLE students ADD COLUMN class_id INTEGER'))
            conn.execute(text('INSERT INTO schema_migrations(version) VALUES (2)'))

    return CURRENT_SCHEMA_VERSION
