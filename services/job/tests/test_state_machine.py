"""Unit tests for application status state machine — no DB required."""

import pytest
from app.models.application import VALID_TRANSITIONS


def all_statuses() -> list[str]:
    return list(VALID_TRANSITIONS.keys())


def test_all_statuses_present() -> None:
    expected = {"discovered", "applied", "interviewing", "offer", "rejected", "withdrawn"}
    assert set(VALID_TRANSITIONS.keys()) == expected


def test_terminal_states_have_no_transitions() -> None:
    for terminal in ("offer", "rejected", "withdrawn"):
        assert VALID_TRANSITIONS[terminal] == set(), f"{terminal} should be terminal"


def test_discovered_can_go_to_applied_and_withdrawn() -> None:
    assert VALID_TRANSITIONS["discovered"] == {"applied", "withdrawn"}


def test_applied_transitions() -> None:
    assert VALID_TRANSITIONS["applied"] == {"interviewing", "rejected", "withdrawn"}


def test_interviewing_transitions() -> None:
    assert VALID_TRANSITIONS["interviewing"] == {"offer", "rejected", "withdrawn"}


@pytest.mark.parametrize(
    "from_status,to_status",
    [
        ("discovered", "interviewing"),
        ("discovered", "offer"),
        ("discovered", "rejected"),
        ("applied", "discovered"),
        ("applied", "offer"),
        ("interviewing", "discovered"),
        ("interviewing", "applied"),
        ("offer", "applied"),
        ("rejected", "applied"),
        ("withdrawn", "applied"),
    ],
)
def test_invalid_transitions_are_not_allowed(from_status: str, to_status: str) -> None:
    assert to_status not in VALID_TRANSITIONS[from_status]


def test_transition_map_targets_are_all_valid_statuses() -> None:
    valid = set(VALID_TRANSITIONS.keys())
    for targets in VALID_TRANSITIONS.values():
        for t in targets:
            assert t in valid, f"Transition target '{t}' is not a known status"
