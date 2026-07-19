"""strip resurrected HTML tags from discovery-sourced raw_jd

Greenhouse's board API serves job content HTML-escaped; the discovery adapter's
strip_html ran before unescaping, so every Greenhouse-crawled job was stored
with literal HTML tags in raw_jd (rendered raw in the UI and fed to the LLM).
The adapter is fixed at ingestion; this migration cleans rows already stored.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-20
"""

import html
import re

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

_SCHEMA = "job_schema"

# Mirrors jobcopilot_discovery.sources.base.strip_html (inlined: migrations must
# not import application code that can change under them).
_BLOCK_TAG_RE = re.compile(r"</?(p|div|li|br|h[1-6])(\s[^>]*)?/?>", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t]{2,}")
_RAW_TEXT_LIMIT = 8000


def _strip_html(text: str) -> str:
    text = _BLOCK_TAG_RE.sub("\n", text)
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    text = _WS_RE.sub(" ", text)
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())[:_RAW_TEXT_LIMIT]


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            f"SELECT job_id, raw_jd FROM {_SCHEMA}.jobs "
            "WHERE source = 'discovery' AND raw_jd ~ '<[a-zA-Z][^>]*>'"
        )
    ).fetchall()
    for job_id, raw_jd in rows:
        bind.execute(
            sa.text(f"UPDATE {_SCHEMA}.jobs SET raw_jd = :raw_jd WHERE job_id = :job_id"),
            {"raw_jd": _strip_html(raw_jd), "job_id": job_id},
        )


def downgrade() -> None:
    # Data cleanup is one-way: the escaped originals are not retained.
    pass
