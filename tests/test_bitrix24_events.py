"""Tests for the Bitrix24 event API client."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.integrations.bitrix24.events import (
    Bitrix24EventAPIError,
    Bitrix24EventClient,
)


@pytest.fixture
def event_client() -> Bitrix24EventClient:
    """Provide a Bitrix24 event client."""
    return Bitrix24EventClient()


def mock_response(data: dict[str, object]) -> MagicMock:
    """Create a mocked HTTP response."""
    response = MagicMock()
    response.json.return_value = data
    response.raise_for_status = MagicMock()
    return response


@pytest.mark.asyncio
async def test_get_event_handlers(
    event_client: Bitrix24EventClient,
) -> None:
    """Registered event handlers are returned."""
    handlers = [{"event": "ONAPPUNINSTALL", "handler": "https://example.com/events"}]
    response = mock_response({"result": handlers})

    with patch("httpx.AsyncClient") as client_class:
        client = client_class.return_value.__aenter__.return_value
        client.post = AsyncMock(return_value=response)

        result = await event_client.get_event_handlers(
            client_endpoint="https://example.bitrix24.ru/rest/",
            access_token="access-token",
        )

    assert result == handlers
    client.post.assert_awaited_once()


@pytest.mark.asyncio
async def test_bind_event(
    event_client: Bitrix24EventClient,
) -> None:
    """An event handler is registered successfully."""
    response = mock_response({"result": True})

    with patch("httpx.AsyncClient") as client_class:
        client = client_class.return_value.__aenter__.return_value
        client.post = AsyncMock(return_value=response)

        result = await event_client.bind_event(
            client_endpoint="https://example.bitrix24.ru/rest/",
            access_token="access-token",
            event="ONAPPUNINSTALL",
            handler="https://example.com/events",
        )

    assert result is True
    client.post.assert_awaited_once()


@pytest.mark.asyncio
async def test_ensure_event_handler_skips_existing_subscription(
    event_client: Bitrix24EventClient,
) -> None:
    """An existing online subscription is not registered again."""
    with patch.object(
        event_client,
        "get_event_handlers",
        new_callable=AsyncMock,
    ) as get_handlers:
        with patch.object(
            event_client,
            "bind_event",
            new_callable=AsyncMock,
        ) as bind_event:
            get_handlers.return_value = [
                {
                    "event": "ONAPPUNINSTALL",
                    "handler": "https://example.com/events",
                    "offline": 0,
                }
            ]

            result = await event_client.ensure_event_handler(
                client_endpoint="https://example.bitrix24.ru/rest/",
                access_token="access-token",
                event="ONAPPUNINSTALL",
                handler="https://example.com/events",
            )

    assert result is False
    bind_event.assert_not_awaited()


@pytest.mark.asyncio
async def test_ensure_event_handler_registers_missing_subscription(
    event_client: Bitrix24EventClient,
) -> None:
    """A missing subscription is registered."""
    with patch.object(
        event_client,
        "get_event_handlers",
        new_callable=AsyncMock,
    ) as get_handlers:
        with patch.object(
            event_client,
            "bind_event",
            new_callable=AsyncMock,
        ) as bind_event:
            get_handlers.return_value = []
            bind_event.return_value = True

            result = await event_client.ensure_event_handler(
                client_endpoint="https://example.bitrix24.ru/rest/",
                access_token="access-token",
                event="ONAPPUNINSTALL",
                handler="https://example.com/events",
            )

    assert result is True
    bind_event.assert_awaited_once()


@pytest.mark.asyncio
async def test_request_raises_bitrix_api_error(
    event_client: Bitrix24EventClient,
) -> None:
    """Bitrix24 REST errors are converted to a typed exception."""
    response = mock_response(
        {
            "error": "ERROR_EVENT_NOT_FOUND",
            "error_description": "Event not found",
        }
    )

    with patch("httpx.AsyncClient") as client_class:
        client = client_class.return_value.__aenter__.return_value
        client.post = AsyncMock(return_value=response)

        with pytest.raises(Bitrix24EventAPIError) as exc_info:
            await event_client.get_event_handlers(
                client_endpoint="https://example.bitrix24.ru/rest/",
                access_token="access-token",
            )

    assert exc_info.value.error == "ERROR_EVENT_NOT_FOUND"
