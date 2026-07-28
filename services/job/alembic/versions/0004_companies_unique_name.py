"""One company row per tenant per name, case- and whitespace-insensitively.

Job creation and import resolve a free-text company_name to a companies row.
Without a unique key that resolution is a duplicate factory: every import of
"Acme ", "acme" and "Acme" mints another row, and the /companies page fills with
near-identical entries that each own a slice of the user's jobs.

The index is on `(tenant_id, lower(btrim(name)))` so the upsert can be
idempotent while the display name keeps the user's original capitalisation.
Companies are per-tenant private (PRD v0.3 §6), so tenant_id leads the key.

Existing duplicates are merged before the index is created — the oldest row of
each group wins and its duplicates' jobs are repointed at it, so no job loses
its company.

Revision ID: 0004
Revises: 0003
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

_SCHEMA = "job_schema"

# The surviving row per (tenant, normalised name): oldest first, company_id as a
# deterministic tiebreak so a re-run picks the same winner.
_RANKED = f"""
    SELECT company_id,
           first_value(company_id) OVER (
               PARTITION BY tenant_id, lower(btrim(name))
               ORDER BY created_at, company_id
           ) AS keeper_id
      FROM {_SCHEMA}.companies
"""


def upgrade() -> None:
    # Repoint jobs BEFORE deleting, or they would be orphaned mid-migration.
    op.execute(f"""
        WITH ranked AS ({_RANKED})
        UPDATE {_SCHEMA}.jobs AS j
           SET company_id = r.keeper_id
          FROM ranked AS r
         WHERE j.company_id = r.company_id
           AND r.company_id <> r.keeper_id
    """)
    op.execute(f"""
        WITH ranked AS ({_RANKED})
        DELETE FROM {_SCHEMA}.companies AS c
         USING ranked AS r
         WHERE c.company_id = r.company_id
           AND r.company_id <> r.keeper_id
    """)
    op.execute(f"""
        CREATE UNIQUE INDEX uq_companies_tenant_name
            ON {_SCHEMA}.companies (tenant_id, lower(btrim(name)))
    """)


def downgrade() -> None:
    op.execute(f"DROP INDEX {_SCHEMA}.uq_companies_tenant_name")
