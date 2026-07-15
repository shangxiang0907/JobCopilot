"""Unit tests for the notification dispatcher — no real DB or MQ required."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from jobcopilot_notification.services.dispatcher import dispatch

_REPO = "jobcopilot_notification.services.dispatcher.NotificationRepository"
_SEND_EMAIL = "jobcopilot_notification.services.dispatcher.send_email"


@pytest.fixture()
def mock_session() -> AsyncMock:
    session = AsyncMock()
    session.flush = AsyncMock()
    return session


@pytest.fixture()
def mock_repo() -> MagicMock:
    repo = MagicMock()
    repo.create = AsyncMock()
    repo.mark_sent = AsyncMock()
    repo.mark_failed = AsyncMock()
    repo.get_preference = AsyncMock(return_value=None)
    return repo


@pytest.mark.asyncio
async def test_dispatch_in_app_no_preference(mock_session: AsyncMock, mock_repo: MagicMock) -> None:
    """in_app channel should be marked sent even when preference row is absent."""
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()

    fake_notification = MagicMock(id=uuid.uuid4())
    mock_repo.create.return_value = fake_notification

    with patch(_REPO, return_value=mock_repo):
        result = await dispatch(
            mock_session,
            tenant_id=tenant_id,
            user_id=user_id,
            type="test",
            title="Hello",
            body="World",
            channels=["in_app"],
        )

    assert len(result) == 1
    mock_repo.mark_sent.assert_awaited_once_with(fake_notification)
    mock_repo.mark_failed.assert_not_awaited()


@pytest.mark.asyncio
async def test_dispatch_email_without_preference_marks_failed(
    mock_session: AsyncMock, mock_repo: MagicMock
) -> None:
    """email channel with no preference should be marked failed."""
    fake_notification = MagicMock(id=uuid.uuid4())
    mock_repo.create.return_value = fake_notification
    mock_repo.get_preference.return_value = None

    with patch(_REPO, return_value=mock_repo):
        await dispatch(
            mock_session,
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            type="test",
            title="Hi",
            body="Body",
            channels=["email"],
        )

    mock_repo.mark_failed.assert_awaited_once()
    call_args = mock_repo.mark_failed.call_args[0]
    assert call_args[1] == "email_not_configured"


@pytest.mark.asyncio
async def test_dispatch_email_with_preference_sends(
    mock_session: AsyncMock, mock_repo: MagicMock
) -> None:
    """email channel sends when preference has email_enabled + address."""
    fake_notification = MagicMock(id=uuid.uuid4())
    mock_repo.create.return_value = fake_notification

    pref = MagicMock(
        email_enabled=True,
        email_address="user@example.com",
    )
    mock_repo.get_preference.return_value = pref

    with (
        patch(_REPO, return_value=mock_repo),
        patch(_SEND_EMAIL, new_callable=AsyncMock) as mock_email,
    ):
        await dispatch(
            mock_session,
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            type="test",
            title="Subject",
            body="Content",
            channels=["email"],
        )

    mock_email.assert_awaited_once_with(
        to_address="user@example.com", subject="Subject", body="Content"
    )
    mock_repo.mark_sent.assert_awaited_once_with(fake_notification)


@pytest.mark.asyncio
@pytest.mark.parametrize("channel", ["wechat", "dingtalk"])
async def test_dispatch_removed_im_channels_fail_as_unknown(
    mock_session: AsyncMock, mock_repo: MagicMock, channel: str
) -> None:
    """WeChat/DingTalk were removed in v0.2 — any stale producer gets unknown_channel."""
    fake_notification = MagicMock(id=uuid.uuid4())
    mock_repo.create.return_value = fake_notification

    with patch(_REPO, return_value=mock_repo):
        await dispatch(
            mock_session,
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            type="test",
            title="T",
            body="B",
            channels=[channel],
        )

    mock_repo.mark_failed.assert_awaited_once_with(fake_notification, f"unknown_channel:{channel}")
    mock_repo.mark_sent.assert_not_awaited()


@pytest.mark.asyncio
async def test_dispatch_multiple_channels(mock_session: AsyncMock, mock_repo: MagicMock) -> None:
    """Multiple channels each get their own Notification row."""
    notifications = [MagicMock(id=uuid.uuid4()), MagicMock(id=uuid.uuid4())]
    mock_repo.create.side_effect = notifications
    mock_repo.get_preference.return_value = None

    with patch(_REPO, return_value=mock_repo):
        result = await dispatch(
            mock_session,
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            type="test",
            title="T",
            body="B",
            channels=["in_app", "email"],
        )

    assert len(result) == 2
    assert mock_repo.create.call_count == 2
