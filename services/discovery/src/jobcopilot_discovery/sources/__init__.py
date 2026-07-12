"""Public job-source adapters (ADR-006: credential-free discovery).

Every adapter fetches from an official, no-login API/feed and normalizes to
RawJob. Global adapters run on every discovery run; company-board adapters
(Greenhouse/Lever) run for each board URL in the user's DiscoveryConfig.
"""

from jobcopilot_discovery.sources.base import RawJob, SearchCriteria
from jobcopilot_discovery.sources.company_boards import fetch_company_board
from jobcopilot_discovery.sources.hn_whoishiring import fetch_hn_whoishiring
from jobcopilot_discovery.sources.remoteok import fetch_remoteok
from jobcopilot_discovery.sources.remotive import fetch_remotive
from jobcopilot_discovery.sources.themuse import fetch_themuse

GLOBAL_SOURCES = {
    "remotive": fetch_remotive,
    "remoteok": fetch_remoteok,
    "themuse": fetch_themuse,
    "hn_whoishiring": fetch_hn_whoishiring,
}

__all__ = [
    "GLOBAL_SOURCES",
    "RawJob",
    "SearchCriteria",
    "fetch_company_board",
]
