"""Backfill the company library from company names already on jobs.

Migration 0004 made name resolution idempotent, and the repository resolves a
company on every job create/update from then on — but only from then on. Every
job that already existed kept its company_name string and a NULL company_id, so
on an established account /companies renders empty next to a job list full of
real companies, and PRD v0.3 §3.6 ("jobs are never left as orphaned company
name strings") holds for new rows only.

One minimal company row is created per (tenant, normalised name), matching what
resolve_by_name would have created had the job been added today: name only, no
industry/size/website/notes. Grouping on lower(btrim(name)) is the same
normalisation as uq_companies_tenant_name, so the insert cannot collide with
itself, and rows a user already created by hand are reused rather than
duplicated.

The displayed spelling comes from the tenant's earliest job carrying that name —
"first sight creates the row" is exactly the rule resolve_by_name follows, so a
backfilled row is indistinguishable from an organically created one.

Blank company names are skipped: a job with no company is a legitimate state and
a company row named "" would be worse than a NULL link.

Revision ID: 0005
Revises: 0004
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

_SCHEMA = "job_schema"

# One row per (tenant, normalised name) with the spelling from the oldest job;
# job_id breaks created_at ties so the chosen spelling is deterministic.
_CANONICAL = f"""
    SELECT DISTINCT ON (tenant_id, lower(btrim(company_name)))
           tenant_id,
           btrim(company_name) AS name
      FROM {_SCHEMA}.jobs
     WHERE btrim(company_name) <> ''
     ORDER BY tenant_id, lower(btrim(company_name)), created_at, job_id
"""


def upgrade() -> None:
    op.execute(f"""
        INSERT INTO {_SCHEMA}.companies (company_id, tenant_id, name)
        SELECT gen_random_uuid(), c.tenant_id, c.name
          FROM ({_CANONICAL}) AS c
        ON CONFLICT DO NOTHING
    """)
    # Link every job to its tenant's row for that name — including jobs whose
    # company the user had already created by hand, which is why this matches on
    # the name rather than on the rows just inserted.
    op.execute(f"""
        UPDATE {_SCHEMA}.jobs AS j
           SET company_id = co.company_id
          FROM {_SCHEMA}.companies AS co
         WHERE j.company_id IS NULL
           AND co.tenant_id = j.tenant_id
           AND lower(btrim(co.name)) = lower(btrim(j.company_name))
    """)


def downgrade() -> None:
    """Deliberately a no-op.

    Nothing distinguishes a backfilled company row from one the user created by
    hand, so an automated reversal would have to guess — and would delete real
    user data when it guessed wrong. The rows are additive and harmless to leave
    in place; a downgrade past 0004 drops the unique index and no more.
    """
