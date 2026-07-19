"""Unit tests for public source adapters — all HTTP mocked via MockTransport."""

import json
from typing import Any

import httpx
import pytest
from jobcopilot_discovery.sources import GLOBAL_SOURCES, fetch_company_board
from jobcopilot_discovery.sources.base import SearchCriteria, matches_location, strip_html
from jobcopilot_discovery.sources.company_boards import parse_board_url


def _client(routes: dict[str, Any]) -> httpx.AsyncClient:
    """MockTransport client: url-prefix → JSON payload (or (status, payload))."""

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        for prefix, payload in routes.items():
            if url.startswith(prefix):
                if isinstance(payload, tuple):
                    return httpx.Response(payload[0], json=payload[1])
                return httpx.Response(200, json=payload)
        return httpx.Response(404, json={"error": f"unrouted: {url}"})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


# ── base helpers ──────────────────────────────────────────────────────────────


def test_strip_html_flattens_tags_and_entities() -> None:
    text = strip_html("<p>Senior &amp; Staff</p><ul><li>Python</li><li>Go</li></ul>")
    assert "Senior & Staff" in text
    assert "Python" in text and "Go" in text
    assert "<" not in text


def test_matches_location_is_lenient_both_directions() -> None:
    c = SearchCriteria(locations=["Europe"])
    assert matches_location(c, "Remote - Europe only")
    assert matches_location(c, "")  # job without location data passes
    assert not matches_location(c, "USA only")
    assert matches_location(SearchCriteria(), "anywhere")  # no filter


# ── Remotive ──────────────────────────────────────────────────────────────────


async def test_remotive_maps_fields_and_filters_location() -> None:
    payload = {
        "jobs": [
            {
                "url": "https://remotive.com/j/1",
                "title": "Python Engineer",
                "company_name": "Acme",
                "candidate_required_location": "Europe",
                "publication_date": "2026-07-01",
                "description": "<p>Build APIs</p>",
            },
            {
                "url": "https://remotive.com/j/2",
                "title": "Go Engineer",
                "company_name": "Other",
                "candidate_required_location": "USA only",
                "description": "x",
            },
        ]
    }
    async with _client({"https://remotive.com/api": payload}) as client:
        jobs = await GLOBAL_SOURCES["remotive"](
            client, SearchCriteria(keywords=["python"], locations=["Europe"])
        )
    assert len(jobs) == 1
    assert jobs[0].title == "Python Engineer"
    assert jobs[0].raw_text == "Build APIs"
    assert jobs[0].source == "remotive"


# ── RemoteOK ──────────────────────────────────────────────────────────────────


async def test_remoteok_skips_legal_notice_and_filters_keywords() -> None:
    payload = [
        {"legal": "API ToS notice"},
        {
            "position": "Senior Python Developer",
            "company": "Acme",
            "url": "https://remoteok.com/j/1",
            "location": "Worldwide",
            "tags": ["python", "api"],
            "description": "<b>FastAPI</b> work",
            "date": "2026-07-01",
        },
        {
            "position": "Designer",
            "company": "Other",
            "url": "https://remoteok.com/j/2",
            "location": "Worldwide",
            "tags": ["figma"],
            "description": "design",
        },
    ]
    async with _client({"https://remoteok.com/api": payload}) as client:
        jobs = await GLOBAL_SOURCES["remoteok"](client, SearchCriteria(keywords=["python"]))
    assert [j.title for j in jobs] == ["Senior Python Developer"]
    assert jobs[0].raw_text == "FastAPI work"


# ── The Muse ──────────────────────────────────────────────────────────────────


async def test_themuse_paginates_and_maps() -> None:
    page1 = {
        "results": [
            {
                "name": "Backend Engineer",
                "company": {"name": "Acme"},
                "locations": [{"name": "Remote"}, {"name": "NYC"}],
                "contents": "<p>Python backend</p>",
                "refs": {"landing_page": "https://themuse.com/j/1"},
                "publication_date": "2026-07-01",
            }
        ]
    }
    empty: dict[str, list[dict[str, object]]] = {"results": []}
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json=page1 if calls["n"] == 1 else empty)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        jobs = await GLOBAL_SOURCES["themuse"](client, SearchCriteria(keywords=["python"]))
    assert len(jobs) == 1
    assert jobs[0].location == "Remote, NYC"
    assert calls["n"] == 2  # stopped on first empty page


# ── HN Who is hiring ──────────────────────────────────────────────────────────


async def test_hn_parses_pipe_convention_and_keywords() -> None:
    routes = {
        "https://hn.algolia.com/api/v1/search_by_date": {"hits": [{"objectID": "999"}]},
        "https://hn.algolia.com/api/v1/items/999": {
            "children": [
                {
                    "id": 1001,
                    "created_at": "2026-07-01",
                    "text": (
                        "Acme Corp | Senior Python Engineer | Remote (EU)"
                        "<p>We build tools. FastAPI, Postgres.</p>"
                    ),
                },
                {"id": 1002, "created_at": "2026-07-01", "text": "Rust shop | Rust dev | onsite"},
            ]
        },
    }
    async with _client(routes) as client:
        jobs = await GLOBAL_SOURCES["hn_whoishiring"](client, SearchCriteria(keywords=["python"]))
    assert len(jobs) == 1
    job = jobs[0]
    assert job.company_name == "Acme Corp"
    assert job.title == "Senior Python Engineer"
    assert job.location == "Remote (EU)"
    assert job.url == "https://news.ycombinator.com/item?id=1001"


# ── Company boards ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://boards.greenhouse.io/stripe", ("greenhouse", "stripe")),
        ("https://job-boards.greenhouse.io/acme-co", ("greenhouse", "acme-co")),
        ("https://jobs.lever.co/spotify", ("lever", "spotify")),
        ("https://jobs.eu.lever.co/acme", ("lever", "acme")),
        ("https://linkedin.com/company/x", None),
    ],
)
def test_parse_board_url(url: str, expected: tuple[str, str] | None) -> None:
    assert parse_board_url(url) == expected


async def test_greenhouse_board_uses_meta_company_name() -> None:
    routes = {
        "https://boards-api.greenhouse.io/v1/boards/stripe/jobs": {
            "jobs": [
                {
                    "absolute_url": "https://stripe.com/jobs/1",
                    "title": "Python Engineer",
                    "location": {"name": "Remote"},
                    # Greenhouse escapes the HTML itself, as observed live:
                    # tags arrive as &lt;h2&gt;, entities double-escaped (&amp;amp;)
                    "content": (
                        "&lt;h2&gt;Who we are&lt;/h2&gt;\n"
                        "&lt;p&gt;Payments &amp;amp; Python&lt;/p&gt;"
                    ),
                    "updated_at": "2026-07-01",
                }
            ]
        },
        "https://boards-api.greenhouse.io/v1/boards/stripe": {"name": "Stripe"},
    }
    async with _client(routes) as client:
        jobs = await fetch_company_board(
            client, "https://boards.greenhouse.io/stripe", SearchCriteria(keywords=["python"])
        )
    assert len(jobs) == 1
    assert jobs[0].company_name == "Stripe"
    assert jobs[0].source == "greenhouse:stripe"
    assert "<" not in jobs[0].raw_text  # tags stripped, not resurrected by unescape
    assert "Payments & Python" in jobs[0].raw_text  # entities unescaped
    assert "Who we are\n" in jobs[0].raw_text  # block tags became line breaks


async def test_lever_board_maps_and_titles_company_from_token() -> None:
    routes = {
        "https://api.lever.co/v0/postings/acme-co": [
            {
                "text": "Python Backend",
                "hostedUrl": "https://jobs.lever.co/acme-co/1",
                "categories": {"location": "Remote"},
                "descriptionPlain": "Django and Python services",
                "createdAt": 1783800000000,
            }
        ]
    }
    async with _client(routes) as client:
        jobs = await fetch_company_board(
            client, "https://jobs.lever.co/acme-co", SearchCriteria(keywords=["python"])
        )
    assert len(jobs) == 1
    assert jobs[0].company_name == "Acme Co"
    assert jobs[0].source == "lever:acme-co"


async def test_unrecognized_board_url_raises() -> None:
    async with _client({}) as client:
        with pytest.raises(ValueError, match="unrecognized board URL"):
            await fetch_company_board(client, "https://example.com/careers", SearchCriteria())


# ── round-trip sanity: adapters produce JSON-serializable RawJobs ─────────────


async def test_rawjob_fields_json_serializable() -> None:
    payload = {
        "jobs": [
            {
                "url": "https://remotive.com/j/1",
                "title": "T",
                "company_name": "C",
                "candidate_required_location": "",
                "description": "d",
            }
        ]
    }
    async with _client({"https://remotive.com/api": payload}) as client:
        jobs = await GLOBAL_SOURCES["remotive"](client, SearchCriteria())
    json.dumps(jobs[0].__dict__)
